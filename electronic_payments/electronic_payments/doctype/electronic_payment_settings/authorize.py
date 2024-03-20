import uuid
from decimal import Decimal
import json

import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password
from frappe.utils.data import today, flt
from frappe.utils import cint

from authorizenet import apicontractsv1
from authorizenet.apicontrollers import (
	createTransactionController,
	createCustomerProfileController,
	deleteCustomerProfileController,
	deleteCustomerPaymentProfileController,
	getTransactionDetailsController,
	createCustomerPaymentProfileController,
	updateCustomerPaymentProfileController,
	getTransactionListController,
	getCustomerPaymentProfileController,
)
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	exceeds_credit_limit,
	calculate_payment_method_fees,
	process_electronic_payment,
	queue_method_as_admin,
)


class AuthorizeNet:
	def merchant_auth(self, company):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": company})
		if not settings:
			frappe.msgprint(_(f"No Electronic Payment Settings found for {company}-Authorize.net"))
		else:
			merchantAuth = apicontractsv1.merchantAuthenticationType()
			merchantAuth.name = get_decrypted_password(
				settings.doctype, settings.name, "api_key", raise_exception=False
			)
			merchantAuth.transactionKey = get_decrypted_password(
				settings.doctype, settings.name, "transaction_key", raise_exception=False
			)
			return merchantAuth

	def process_transaction(self, doc, data):
		mop = data.mode_of_payment.replace("New ", "")
		if mop.startswith("Saved"):
			if data.get("subject_to_credit_limit") and exceeds_credit_limit(doc, data):
				return {"error": "Credit Limit exceeded for selected Mode of Payment"}
			if data.get("ppm_name"):
				data.update({"additional_charges": calculate_payment_method_fees(doc, data)})
			response = self.charge_party_profile(doc, data)
		elif mop == "Card" and data.get("save_data") == "Charge now":
			response = self.process_credit_card(doc, data)
		else:  # charge new Card/ACH, save payment data (temporarily if txn only - payment profile deleted once charge is successful)
			customer_response = self.create_party_profile(doc)
			if customer_response.get("message") == "Success":
				data.update({"party_profile_id": customer_response.get("transaction_id")})
				pmt_profile_response = self.create_party_payment_profile(doc, data)
				if pmt_profile_response.get("message") == "Success":
					pp_doc = pmt_profile_response.get("payment_profile_doc")
					data.update({"payment_profile_id": pp_doc.payment_profile_id})
					response = self.charge_party_profile(doc, data)
				else:  # error creating the customer payment profile
					return pmt_profile_response
			else:  # error creating customer profile
				return customer_response
		return response

	def process_credit_card(self, doc, data):
		card_number = data.get("card_number")
		creditCard = apicontractsv1.creditCardType()
		creditCard.cardNumber = card_number.replace(" ", "")
		creditCard.expirationDate = data.get("card_expiration_date")
		creditCard.cardCode = str(data.get("card_cvc"))
		payment = apicontractsv1.paymentType()
		payment.creditCard = creditCard

		total_to_charge = flt(
			doc.grand_total + (data.get("additional_charges") or 0),
			frappe.get_precision(doc.doctype, "grand_total"),
		)

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType = "authCaptureTransaction"
		transactionrequest.amount = Decimal(str(total_to_charge))
		transactionrequest.currencyCode = frappe.defaults.get_global_default("currency")
		transactionrequest.payment = payment

		createtransactionrequest = apicontractsv1.createTransactionRequest()
		createtransactionrequest.merchantAuthentication = self.merchant_auth(doc.company)
		createtransactionrequest.refId = doc.name
		createtransactionrequest.transactionRequest = transactionrequest

		createtransactioncontroller = createTransactionController(createtransactionrequest)
		createtransactioncontroller.execute()

		response = createtransactioncontroller.getresponse()
		error_message = ""

		if response is not None:
			if response.messages.resultCode == "Ok":
				frappe.db.set_value(
					doc.doctype,
					doc.name,
					"electronic_payment_reference",
					str(response.transactionResponse.transId),
				)
				queue_method_as_admin(
					process_electronic_payment,
					doc=doc,
					data=data,
					transaction_id=str(response.transactionResponse.transId),
				)
				return {
					"message": "Success",
					"transaction_id": str(response.transactionResponse.transId),
				}
			else:
				if hasattr(response, "transactionResponse") and hasattr(
					response.transactionResponse, "errors"
				):
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = str(response.messages.message[0]["text"].text)
		else:
			error_message = "No response"

		frappe.log_error(message=frappe.get_traceback(), title=error_message)
		return {"error": error_message}
	
	def get_party_details(self, doc):
		if getattr(doc, "customer"):
			return frappe._dict({
				"doctype": "Customer",
				"name": doc.customer,
				"description": doc.customer_name
			})
		else:
			if getattr(doc, "supplier"):
				return frappe._dict({
					"doctype": "Supplier",
					"name": doc.supplier,
					"description": doc.supplier_name
				})

	def create_party_profile(self, doc):
		party = self.get_party_details(doc)
		existing_party_id = frappe.get_value(party.doctype, party.name, "electronic_payment_profile")
	
		if existing_party_id:
			return {"message": "Success", "transaction_id": existing_party_id}
		else:
			createCustomerProfile = apicontractsv1.createCustomerProfileRequest()
			createCustomerProfile.merchantAuthentication = self.merchant_auth(doc.company)
			createCustomerProfile.profile = apicontractsv1.customerProfileType(
				merchantCustomerId=f"{uuid.uuid4().int>>64}",
				description=party.description,
				email="",
			)
			controller = createCustomerProfileController(createCustomerProfile)
			controller.execute()
			response = controller.getresponse()

			if response.messages.resultCode == "Ok":
				party_profile_id = str(response.customerProfileId)
				frappe.db.set_value(
					party.doctype, party.name, "electronic_payment_profile", party_profile_id
				)
				return {"message": "Success", "transaction_id": party_profile_id}
			else:
				error_message = str(response.messages.message[0]["text"].text)
				frappe.log_error(message=frappe.get_traceback(), title=error_message)
				return {"error": error_message}

	def edit_customer_payment_profile(self, company, electronic_payment_profile_name, data):
		merchantAuth = self.merchant_auth(company)
		payment_profile = frappe.get_doc(
			"Electronic Payment Profile", {"name": electronic_payment_profile_name}
		)

		payment = apicontractsv1.paymentType()
		paymentProfile = apicontractsv1.customerPaymentProfileExType()
		paymentProfile.billTo = apicontractsv1.customerAddressType()

		if payment_profile.payment_type == "Card":
			creditCard = apicontractsv1.creditCardType()
			creditCard.cardNumber = data.get("card_number")
			last4 = data.get("card_number")[-4:]
			creditCard.expirationDate = data.get("card_expiration_date")
			creditCard.cardCode = str(data.get("card_cvc"))
			payment.creditCard = creditCard
			paymentProfile.billTo.firstName = " ".join(data.get("cardholder_name").split(" ")[0:-1])
			paymentProfile.billTo.lastName = data.get("cardholder_name").split(" ")[-1]
		elif payment_profile.payment_type == "ACH":
			account_number = str(data.get("account_number"))
			last4 = account_number[-4:]
			bankAccount = apicontractsv1.bankAccountType()
			accountType = apicontractsv1.bankAccountTypeEnum
			bankAccount.accountType = accountType.checking
			bankAccount.routingNumber = str(data.get("routing_number"))
			bankAccount.accountNumber = account_number
			bankAccount.nameOnAccount = data.get("account_holders_name")
			payment.bankAccount = bankAccount
			paymentProfile.billTo.firstName = " ".join(data.get("account_holders_name").split(" ")[0:-1])
			paymentProfile.billTo.lastName = data.get("account_holders_name").split(" ")[-1]

		paymentProfile.payment = payment
		paymentProfile.customerPaymentProfileId = str(payment_profile.payment_profile_id)

		updateCustomerPaymentProfile = apicontractsv1.updateCustomerPaymentProfileRequest()
		updateCustomerPaymentProfile.merchantAuthentication = merchantAuth
		updateCustomerPaymentProfile.paymentProfile = paymentProfile
		updateCustomerPaymentProfile.customerProfileId = str(payment_profile.party_profile)

		controller = updateCustomerPaymentProfileController(updateCustomerPaymentProfile)
		controller.execute()

		response = controller.getresponse()

		if response.messages.resultCode == "Ok":
			payment_profile.reference = (
				f"**** **** **** {last4}" if payment_profile.payment_type == "Card" else f"*{last4}"
			)
			payment_profile.save(ignore_permissions=True)
			ppm = frappe.get_doc(
				"Portal Payment Method", {"electronic_payment_profile": payment_profile.name}
			)
			ppm.label = f"{payment_profile.payment_type}-{last4}"
			ppm.default = cint(data.get("default", 0))
			ppm.electronic_payment_profile = payment_profile.name
			ppm.save(ignore_permissions=True)
			return {"message": "Success", "payment_profile_doc": payment_profile}
		else:
			error_message = str(response.messages.message[0]["text"].text)
			frappe.log_error(message=frappe.get_traceback(), title=error_message)
			return {"error": error_message}

	def get_customer_payment_profile(self, company, electronic_payment_profile_name):
		merchantAuth = self.merchant_auth(company)

		electronic_payment_profile = frappe.get_doc(
			"Electronic Payment Profile", {"name": electronic_payment_profile_name}
		)
		getCustomerPaymentProfile = apicontractsv1.getCustomerPaymentProfileRequest()
		getCustomerPaymentProfile.merchantAuthentication = merchantAuth
		getCustomerPaymentProfile.customerProfileId = electronic_payment_profile.party_profile
		getCustomerPaymentProfile.customerPaymentProfileId = (
			electronic_payment_profile.payment_profile_id
		)
		controller = getCustomerPaymentProfileController(getCustomerPaymentProfile)
		controller.execute()
		response = controller.getresponse()

		if response.messages.resultCode != "Ok":
			error_message = str(response.messages.message[0]["text"].text)
			frappe.log_error(message=frappe.get_traceback(), title=error_message)
			return {"error": error_message}

		if electronic_payment_profile.payment_type == "Card":
			return {
				"message": "Success",
				"data": {
					"first_name": response.paymentProfile.billTo.firstName,
					"last_name": response.paymentProfile.billTo.lastName,
					"card_number": response.paymentProfile.payment.creditCard.cardNumber,
					"expiration_date": response.paymentProfile.payment.creditCard.expirationDate,
					"card_type": response.paymentProfile.payment.creditCard.cardType,
				},
			}
		elif electronic_payment_profile.payment_type == "ACH":
			return {
				"message": "Success",
				"data": {
					"first_name": response.paymentProfile.billTo.firstName,
					"last_name": response.paymentProfile.billTo.lastName,
					"account_type": response.paymentProfile.payment.bankAccount.accountType,
					"routing_number": response.paymentProfile.payment.bankAccount.routingNumber,
					"account_number": response.paymentProfile.payment.bankAccount.accountNumber,
					"name_on_account": response.paymentProfile.payment.bankAccount.nameOnAccount,
					"echeck_type": response.paymentProfile.payment.bankAccount.echeckType,
				},
			}

	def create_party_payment_profile(self, doc, data):
		party = self.get_party_details(doc)

		if not data.get("party_profile_id"):
			party_profile_id = frappe.get_value(party.doctype, party.name, "electronic_payment_profile")
		else:
			party_profile_id = data.get("party_profile_id")

		merchantAuth = self.merchant_auth(doc.company)
		payment = apicontractsv1.paymentType()
		profile = apicontractsv1.customerPaymentProfileType()

		mop = data.mode_of_payment.replace("New ", "")
		if mop == "Card":
			card_number = data.get("card_number")
			card_number = card_number.replace(" ", "")
			last4 = card_number[-4:]

			creditCard = apicontractsv1.creditCardType()
			creditCard.cardNumber = card_number
			creditCard.expirationDate = data.get("card_expiration_date")
			creditCard.cardCode = str(data.get("card_cvc"))
			payment.creditCard = creditCard
			billTo = apicontractsv1.customerAddressType()
			billTo.firstName = " ".join(data.get("cardholder_name").split(" ")[0:-1])
			billTo.lastName = data.get("cardholder_name").split(" ")[-1]
		elif mop == "ACH":
			account_number = str(data.get("account_number"))
			last4 = account_number[-4:]

			bankAccount = apicontractsv1.bankAccountType()
			accountType = apicontractsv1.bankAccountTypeEnum
			bankAccount.accountType = accountType.checking
			bankAccount.routingNumber = str(data.get("routing_number"))
			bankAccount.accountNumber = account_number
			bankAccount.nameOnAccount = data.get("account_holders_name")
			payment.bankAccount = bankAccount
			billTo = apicontractsv1.customerAddressType()
			billTo.firstName = " ".join(data.get("account_holders_name").split(" ")[0:-1])
			billTo.lastName = data.get("account_holders_name").split(" ")[-1]

		profile.payment = payment
		profile.billTo = billTo

		createCustomerPaymentProfile = apicontractsv1.createCustomerPaymentProfileRequest()
		createCustomerPaymentProfile.merchantAuthentication = merchantAuth
		createCustomerPaymentProfile.paymentProfile = profile
		createCustomerPaymentProfile.customerProfileId = str(party_profile_id)

		controller = createCustomerPaymentProfileController(createCustomerPaymentProfile)
		controller.execute()

		response = controller.getresponse()

		if response.messages.resultCode == "Ok":
			payment_profile = frappe.new_doc("Electronic Payment Profile")
			payment_profile.party_type = party.doctype
			payment_profile.party = party.name
			payment_profile.payment_type = mop
			payment_profile.payment_gateway = "Authorize"
			payment_profile.reference = f"**** **** **** {last4}" if mop == "Card" else f"*{last4}"
			payment_profile.payment_profile_id = str(response.customerPaymentProfileId)
			payment_profile.party_profile = str(party_profile_id)
			payment_profile.retain = 1 if data.save_data == "Retain payment data for this party" else 0
			payment_profile.save(ignore_permissions=True)

			if payment_profile.retain and frappe.get_value(
				"Electronic Payment Settings", {"company": doc.company}, "create_ppm"
			):
				# TODO: review assumptions around MOP, service charge, default
				ppm = frappe.new_doc("Portal Payment Method")
				ppm.mode_of_payment = frappe.get_value(
					"Electronic Payment Settings", {"company": doc.company}, "mode_of_payment"
				)
				ppm.label = f"{mop}-{last4}"
				ppm.default = cint(data.get("default", 0))
				ppm.electronic_payment_profile = payment_profile.name
				ppm.service_charge = 0
				ppm.parent = payment_profile.party
				ppm.parenttype = payment_profile.party_type
				ppm.save(ignore_permissions=True)
				
				party_obj = frappe.get_doc(party.doctype, party.name)
				party_obj.append("portal_payment_method", ppm)
				party_obj.save(ignore_permissions=True)

			return {"message": "Success", "payment_profile_doc": payment_profile}
		else:
			error_message = str(response.messages.message[0]["text"].text)
			frappe.log_error(message=frappe.get_traceback(), title=error_message)
			return {"error": error_message}

	def charge_party_profile(self, doc, data):
		party = self.get_party_details(doc)

		if not data.get("party_profile_id"):
			party_profile_id = frappe.get_value(party.doctype, party.name, "electronic_payment_profile")
		else:
			party_profile_id = data.get("party_profile_id")

		payment_profile_id = data.get("payment_profile_id")
		total_to_charge = flt(
			doc.grand_total + (data.get("additional_charges") or 0),
			frappe.get_precision(doc.doctype, "grand_total"),
		)
		merchantAuth = self.merchant_auth(doc.company)

		profileToCharge = apicontractsv1.customerProfilePaymentType()
		profileToCharge.customerProfileId = str(party_profile_id)
		profileToCharge.paymentProfile = apicontractsv1.paymentProfile()
		profileToCharge.paymentProfile.paymentProfileId = str(payment_profile_id)

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType = "authCaptureTransaction"
		transactionrequest.amount = Decimal(str(total_to_charge))
		transactionrequest.currencyCode = frappe.defaults.get_global_default("currency")
		transactionrequest.profile = profileToCharge

		createtransactionrequest = apicontractsv1.createTransactionRequest()
		createtransactionrequest.merchantAuthentication = merchantAuth
		createtransactionrequest.refId = doc.name

		createtransactionrequest.transactionRequest = transactionrequest
		createtransactioncontroller = createTransactionController(createtransactionrequest)
		createtransactioncontroller.execute()

		response = createtransactioncontroller.getresponse()
		error_message = ""

		if response is not None:
			if response.messages.resultCode == "Ok":
				if hasattr(response.transactionResponse, "messages"):
					if not frappe.get_value(
						"Electronic Payment Profile",
						{"party": party.name, "payment_profile_id": payment_profile_id},
						"retain",
					):
						frappe.get_doc(
							"Electronic Payment Profile",
							{"party": party.name, "payment_profile_id": payment_profile_id},
						).delete()
						deleteCustomerPaymentProfile = apicontractsv1.deleteCustomerPaymentProfileRequest()
						deleteCustomerPaymentProfile.merchantAuthentication = merchantAuth
						deleteCustomerPaymentProfile.customerProfileId = str(party_profile_id)
						deleteCustomerPaymentProfile.customerPaymentProfileId = payment_profile_id

						controller = deleteCustomerPaymentProfileController(deleteCustomerPaymentProfile)
						controller.execute()
						pmt_delete_response = controller.getresponse()

						if pmt_delete_response is None or (
							hasattr(pmt_delete_response, "messages") and pmt_delete_response.messages.resultCode != "Ok"
						):
							frappe.log_error(
								message=frappe.get_traceback(),
								title=f"Error deleting customer payment profile used for {doc.name}",
							)

					frappe.db.set_value(
						doc.doctype,
						doc.name,
						"electronic_payment_reference",
						str(response.transactionResponse.transId),
					)
					queue_method_as_admin(
						process_electronic_payment,
						doc=doc,
						data=data,
						transaction_id=str(response.transactionResponse.transId),
					)
					return {
						"message": "Success",
						"transaction_id": str(response.transactionResponse.transId),
					}
				else:
					if hasattr(response.transactionResponse, "errors"):
						error_message = str(response.transactionResponse.errors.error[0].errorText)
			else:
				if (
					hasattr(response, "transactionResponse") == True
					and hasattr(response.transactionResponse, "errors") == True
				):
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = str(response.messages.message[0]["text"].text)
		else:
			error_message = "No response"

		frappe.log_error(message=frappe.get_traceback(), title=error_message)
		return {"error": error_message}

	# def credit_bank_account(self, data):
	# 	# https://github.com/AuthorizeNet/sample-code-python/blob/master/PaymentTransactions/credit-bank-account.py
	# 	pass

	# def debit_bank_account(self, data):
	# 	#https://github.com/AuthorizeNet/sample-code-python/blob/master/PaymentTransactions/debit-bank-account.py
	# 	pass

	def refund_transaction(self, doc, data):
		"""
		Handles both credit card refunds and bank account credits
		TODO: clarify where this function is called and if orig doc / what data can be passed
		Function needs:
		- transaction ID (saved in custom field doc.electronic_payment_reference or payment entry/journal entry)
		- amount of refund (assumes contained in data)
		- currency
		- payment info (can request with transaction ID)
		  - CC refunds need either original transaction ID and CC's last 4 digits
		  - Bank account refunds need routing number, account number, and account holder's name
		"""
		merchantAuth = self.merchant_auth(doc.company)
		orig_transaction_id = doc.electronic_payment_reference
		amount = data.get("amount")

		# Validate amount is <= doc grand total less any other refunds
		prev_refunded_amt = 0  # TODO: collect any other refunds made on this doc
		if amount > (doc.grand_total - prev_refunded_amt):
			frappe.throw(
				_(
					"The refund amount must be less than or equal to the grand total less any previously refunded amounts."
				)
			)

		# Request transaction details for payment information
		txn_details_response = self.get_transaction_details(doc.company, orig_transaction_id)
		error_message = ""

		if txn_details_response.get("message") == "Success":
			payment_details = txn_details_response.get("payment_details")
		else:
			return txn_details_response

		if payment_details.type == "creditCard":
			creditCard = apicontractsv1.creditCardType()
			creditCard.cardNumber = payment_details.cardNumber[-4:]
			creditCard.expirationDate = (
				payment_details.expirationDate
			)  # will be XXXX as it's masked for refunds. Per docs: "For refunds, use XXXX instead of the card expiration date."
			payment = apicontractsv1.paymentType()
			payment.creditCard = creditCard
		elif payment_details.type == "bankAccount":
			bankAccount = apicontractsv1.bankAccountType()
			bankAccount.accountType = payment_details.accountType
			bankAccount.routingNumber = payment_details.routingNumber
			bankAccount.accountNumber = payment_details.accountNumber
			bankAccount.nameOnAccount = payment_details.nameOnAccount
			payment = apicontractsv1.paymentType()
			payment.bankAccount = bankAccount
		else:
			error_message = "Unrecognized payment type for given transaction ID"

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType = "refundTransaction"
		transactionrequest.amount = Decimal(str(amount))
		transactionrequest.currencyCode = frappe.defaults.get_global_default("currency")
		transactionrequest.refTransId = orig_transaction_id
		transactionrequest.payment = payment

		createtransactionrequest = apicontractsv1.createTransactionRequest()
		createtransactionrequest.merchantAuthentication = merchantAuth

		createtransactionrequest.transactionRequest = transactionrequest
		createtransactioncontroller = createTransactionController(createtransactionrequest)
		createtransactioncontroller.execute()

		response = createtransactioncontroller.getresponse()

		if response is not None:
			if response.messages.resultCode == "Ok":
				if hasattr(response.transactionResponse, "messages"):
					# TODO: handle refund in ERPNext
					# pe = frappe.get_doc('Payment Entry', {'reference_no': orig_transaction_id})
					# pe.cancel()
					return {
						"message": "Success",
						"transaction_id": str(response.transactionResponse.transId),
					}
				elif hasattr(response.transactionResponse, "errors"):
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = "Transaction request error"
			else:
				if hasattr(response, "transactionResponse") and hasattr(
					response.transactionResponse, "errors"
				):
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = str(response.messages.message[0]["text"].text)
		else:
			error_message = "No Repsonse"

		frappe.log_error(message=frappe.get_traceback(), title=error_message)
		return {"error": error_message}

	def void_transaction(self, doc, data):
		merchantAuth = self.merchant_auth(doc.company)
		orig_transaction_id = doc.electronic_payment_reference

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType = "voidTransaction"
		transactionrequest.refTransId = orig_transaction_id

		createtransactionrequest = apicontractsv1.createTransactionRequest()
		createtransactionrequest.merchantAuthentication = merchantAuth

		createtransactionrequest.transactionRequest = transactionrequest
		createtransactioncontroller = createTransactionController(createtransactionrequest)
		createtransactioncontroller.execute()

		response = createtransactioncontroller.getresponse()
		error_message = ""

		if response is not None:
			if response.messages.resultCode == "Ok":
				if hasattr(response.transactionResponse, "messages"):
					# TODO: handle refund in ERPNext
					# pe = frappe.get_doc('Payment Entry', {'reference_no': orig_transaction_id})
					# pe.cancel()
					return {
						"message": "Success",
						"transaction_id": str(response.transactionResponse.transId),
					}
				elif hasattr(response.transactionResponse, "errors"):
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = "Transaction request error"
			else:
				if hasattr(response, "transactionResponse") and hasattr(
					response.transactionResponse, "errors"
				):
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = str(response.messages.message[0]["text"].text)
		else:
			error_message = "No Repsonse"

		frappe.log_error(message=frappe.get_traceback(), title=error_message)
		return {"error": error_message}

	def get_transaction_details(self, company, transaction_id):
		"""
		# Structure of payment information from request
		"payment": {
		        "creditCard": {
		                "cardNumber": "XXXX1111",
		                "expirationDate": "XXXX",
		                "cardType": "Visa"
		        }
		}
		"payment": {
		        "bankAccount": {
		                "accountType": "checking",
		                "routingNumber": "121042882",
		                "accountNumber": "123456789",
		                "nameOnAccount": "John Doe"
		        }
		}
		"""
		merchantAuth = self.merchant_auth(company)

		transactionDetailsRequest = apicontractsv1.getTransactionDetailsRequest()
		transactionDetailsRequest.merchantAuthentication = merchantAuth
		transactionDetailsRequest.transId = transaction_id

		transactionDetailsController = getTransactionDetailsController(transactionDetailsRequest)

		transactionDetailsController.execute()

		response = transactionDetailsController.getresponse()
		error_message = ""

		if response is not None:
			if response.messages.resultCode == "Ok":
				if hasattr(response.transaction.payment, "creditCard"):
					payment_dict = frappe._dict(
						{
							"type": "creditCard",
							"cardNumber": str(response.transaction.payment.creditCard.cardNumber),
							"expirationDate": str(response.transaction.payment.creditCard.expirationDate),
						}
					)
					return {"message": "Success", "payment_details": payment_dict}
				elif hasattr(response.transaction.payment, "bankAccount"):
					payment_dict = frappe._dict(
						{
							"type": "bankAccount",
							"accountType": str(response.transaction.payment.bankAccount.accountType),
							"routingNumber": str(response.transaction.payment.bankAccount.routingNumber),
							"accountNumber": str(response.transaction.payment.bankAccount.accountNumber),
							"nameOnAccount": str(response.transaction.payment.bankAccount.nameOnAccount),
						}
					)
					return {"message": "Success", "payment_details": payment_dict}
				else:
					error_message = "Transaction details have unrecognized payment type"
			else:
				if response.messages is not None:
					error_message = response.messages.message[0]["text"].text
				else:
					error_message = "Failed to get transaction details"
		else:
			error_message = "No response"

		frappe.log_error(message=frappe.get_traceback(), title=error_message)
		return {"error": error_message}

	def delete_payment_profile(self, company, payment_profile_id):
		# Delete from ERPNext
		epp_name, party, customer_profile_id = frappe.get_value(
			"Electronic Payment Profile",
			{"payment_profile_id": payment_profile_id},
			["name", "party", "party_profile"],
		)
		pmm_name = frappe.get_value("Portal Payment Method", {"electronic_payment_profile": epp_name})

		frappe.delete_doc("Portal Payment Method", pmm_name, ignore_permissions=True)
		frappe.delete_doc("Electronic Payment Profile", epp_name, ignore_permissions=True)

		# Delete from API
		merchantAuth = self.merchant_auth(company)
		deleteCustomerPaymentProfile = apicontractsv1.deleteCustomerPaymentProfileRequest()
		deleteCustomerPaymentProfile.merchantAuthentication = merchantAuth
		deleteCustomerPaymentProfile.customerProfileId = str(customer_profile_id)
		deleteCustomerPaymentProfile.customerPaymentProfileId = str(payment_profile_id)

		controller = deleteCustomerPaymentProfileController(deleteCustomerPaymentProfile)
		controller.execute()
		response = controller.getresponse()

		if response is None or (hasattr(response, "messages") and response.messages.resultCode != "Ok"):
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Error deleting payment profile attached to {party}.",
			)
		else:
			return {"message": "Success"}

	def delete_customer_profile(self, company, customer):
		# Delete from ERPNext
		customer_profile_id = frappe.get_value(
			"Customer",
			customer,
			"electronic_payment_profile",
		)
		frappe.set_value("Customer", customer, "electronic_payment_profile", "")

		# Delete from API
		merchantAuth = self.merchant_auth(company)
		deleteCustomerProfile = apicontractsv1.deleteCustomerProfileRequest()
		deleteCustomerProfile.merchantAuthentication = merchantAuth
		deleteCustomerProfile.customerProfileId = customer_profile_id

		controller = deleteCustomerProfileController(deleteCustomerProfile)
		controller.execute()

		response = controller.getresponse()

		if response is None or (hasattr(response, "messages") and response.messages.resultCode != "Ok"):
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Error deleting profile for {customer}",
			)
		else:
			return {"message": "Success"}


def fetch_authorize_transactions(settings):
	settings = frappe._dict(json.loads(settings)) if isinstance(settings, str) else settings
	sorting = apicontractsv1.TransactionListSorting()
	sorting.orderBy = apicontractsv1.TransactionListOrderFieldEnum.id
	sorting.orderDescending = True
	paging = apicontractsv1.Paging()
	paging.limit = 1000
	paging.offset = 1

	transactionListRequest = apicontractsv1.getTransactionListRequest()
	transactionListRequest.merchantAuthentication = settings.merchant_auth()
	abbr = frappe.get_value("Company", settings.company, "abbr")
	transactionListRequest.refId = f"{today()} {abbr}"
	transactionListRequest.sorting = sorting
	transactionListRequest.paging = paging

	transactionListController = getTransactionListController(transactionListRequest)
	transactionListController.execute()

	response = transactionListController.getresponse()
	error_message = ""

	if response is not None:
		if response.messages.resultCode == apicontractsv1.messageTypeEnum.Ok:
			if hasattr(response, "transactions"):
				return {
					"message": "Success",
					"transactions": response.transactions,
				}  # TODO: handle response to create a list of frappe._dict objects for each transaction
	else:
		error_message = "No response"

	frappe.log_error(message=frappe.get_traceback(), title=error_message)
	return {"error": error_message}
