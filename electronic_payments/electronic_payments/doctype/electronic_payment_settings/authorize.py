import json
import uuid
from decimal import *
import datetime

import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password

import authorizenet
from authorizenet import apicontractsv1
from authorizenet.apicontrollers import *
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import create_payment_entry


class AuthorizeNet():
	def merchant_auth(self, company):
		settings = frappe.get_doc('Electronic Payment Settings', {'company': company})
		if not settings:
			frappe.msgprint(_(f'No Electronic Payment Settings found for {company}-Authorize.net'))
		else:
			merchantAuth = apicontractsv1.merchantAuthenticationType()
			merchantAuth.name = get_decrypted_password(settings.doctype, settings.name, 'api_key')
			merchantAuth.transactionKey = get_decrypted_password(settings.doctype, settings.name, 'transaction_key')
			return merchantAuth


	def process_transaction(self, doc, data):
		mop = data.mode_of_payment.replace('New ', '')
		if mop == 'Saved Payment Method':
			response = self.charge_customer_profile(doc, data)
		elif mop == 'Card' and data.get('save_data') == 'Charge now':
			response = self.process_credit_card(doc, data)
		else:  # charge new Card/ACH, save payment data (temporarilty if txn only - payment profile deleted once charge is successful)
			customer_response = self.create_customer_profile(doc, data)
			if customer_response.get('message') == 'Success':
				data.update({'customer_profile': customer_response.get('transaction_id')})
				pmt_profile_response = self.create_customer_payment_profile(doc, data)
				if pmt_profile_response.get('message') == 'Success':
					response = self.charge_customer_profile(doc, data)
				else:  # error creating the customer payment profile
					return pmt_profile_response
			else:  # error creating customer profile
				return customer_response
		return response


	def process_credit_card(self, doc, data):
		card_number = data.get('card_number')
		creditCard = apicontractsv1.creditCardType()
		creditCard.cardNumber = card_number.replace(' ', '')
		creditCard.expirationDate = data.get('card_expiration_date')
		creditCard.cardCode = str(data.get('card_cvc'))
		payment = apicontractsv1.paymentType()
		payment.creditCard = creditCard

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType ="authCaptureTransaction"
		transactionrequest.amount = Decimal(str(doc.grand_total))
		transactionrequest.currencyCode = frappe.defaults.get_global_default('currency')
		transactionrequest.payment = payment
		
		createtransactionrequest = apicontractsv1.createTransactionRequest()
		createtransactionrequest.merchantAuthentication = self.merchant_auth(doc.company)
		createtransactionrequest.refId = doc.name
		createtransactionrequest.transactionRequest = transactionrequest

		createtransactioncontroller = createTransactionController(createtransactionrequest)
		createtransactioncontroller.execute()

		response = createtransactioncontroller.getresponse()
		error_message = None

		if response is not None:
			if response.messages.resultCode == "Ok":
				create_payment_entry(doc, data, response.transactionResponse.transId)
				return {'message': 'Success', 'transaction_id': response.transactionResponse.transId}
			else:
				if hasattr(response, 'transactionResponse') and hasattr(
						response.transactionResponse, 'errors'):
					error_message = response.transactionResponse.errors.error[0].errorText
				else:
					error_message = response.messages.message[0]['text'].text
		else:
			error_message = 'No response'
		
		frappe.log_error(message=frappe.get_traceback(), title=error_message)
		return {'error': error_message}


	def create_customer_profile(self, doc, data):
		existing_customer_id = frappe.get_value('Customer', doc.customer, 'electronic_payment_profile')
		if existing_customer_id:
			return {'message': 'Success', 'transaction_id': existing_customer_id}
		else:
			createCustomerProfile = apicontractsv1.createCustomerProfileRequest()
			createCustomerProfile.merchantAuthentication = self.merchant_auth(doc.company)
			createCustomerProfile.profile = apicontractsv1.customerProfileType(
				merchantCustomerId=f'{uuid.uuid4().int>>64}',
				description=doc.customer_name,
				email=''
			)
			controller = createCustomerProfileController(createCustomerProfile)
			controller.execute()
			response = controller.getresponse()

			if response.messages.resultCode == "Ok":
				print(f'Customer profile created - type: {type(response.customerProfileId)}')
				customer_profile_id = str(response.customerProfileId)
				frappe.db.set_value('Customer', doc.customer, 'electronic_payment_profile', customer_profile_id)
				return {'message': 'Success', 'transaction_id': response.customerProfileId}
			else:
				error_message = str(response.messages.message[0]['text'].text)
				frappe.log_error(message=frappe.get_traceback(), title=error_message)
				return {'error': error_message}


	def create_customer_payment_profile(self, doc, data):
		if not data.get('customer_profile'):
			customer_profile_id = frappe.get_value('Customer', doc.customer, 'electronic_payment_profile')
		else:
			customer_profile_id = data.get('customer_profile')

		merchantAuth = self.merchant_auth(doc.company)
		payment = apicontractsv1.paymentType()
		profile = apicontractsv1.customerPaymentProfileType()

		mop = data.mode_of_payment.replace('New ', '')
		if mop == 'Card':
			card_number = data.get('card_number')
			card_number = card_number.replace(' ', '')
			last4 = card_number[-4:]

			creditCard = apicontractsv1.creditCardType()
			creditCard.cardNumber = card_number
			creditCard.expirationDate = data.get('card_expiration_date')
			creditCard.cardCode = str(data.get('card_cvc'))
			payment.creditCard = creditCard
			billTo = apicontractsv1.customerAddressType()
			billTo.firstName = ' '.join(data.get('cardholder_name').split(' ')[0:-1])
			billTo.lastName = data.get('cardholder_name').split(' ')[-1][0]
		elif mop == 'ACH':
			account_number = str(data.get('account_number'))
			last4 = account_number[-4:]

			bankAccount = apicontractsv1.bankAccountType()
			accountType = apicontractsv1.bankAccountTypeEnum
			bankAccount.accountType = accountType.checking
			bankAccount.routingNumber = str(data.get('routing_number'))
			bankAccount.accountNumber = account_number
			bankAccount.nameOnAccount = data.get('account_holders_name')
			payment.bankAccount = bankAccount
			billTo = apicontractsv1.customerAddressType()
			billTo.firstName = ' '.join(data.get('account_holders_name').split(' ')[0:-1])
			billTo.lastName = data.get('account_holders_name').split(' ')[-1][0]

		profile.payment = payment
		profile.billTo = billTo

		createCustomerPaymentProfile = apicontractsv1.createCustomerPaymentProfileRequest()
		createCustomerPaymentProfile.merchantAuthentication = merchantAuth
		createCustomerPaymentProfile.paymentProfile = profile
		createCustomerPaymentProfile.customerProfileId = str(customer_profile_id)

		controller = createCustomerPaymentProfileController(createCustomerPaymentProfile)
		controller.execute()

		response = controller.getresponse()

		if response.messages.resultCode == "Ok":
			payment_profile = frappe.new_doc('Electronic Payment Profile')
			payment_profile.party_type = 'Customer'
			payment_profile.party = doc.customer
			payment_profile.payment_type = mop
			payment_profile.reference = f"**** **** **** {last4}" if mop == 'Card' else f"*{last4}"
			payment_profile.payment_profile_id = str(response.customerPaymentProfileId)
			payment_profile.party_profile = str(customer_profile_id)
			payment_profile.retain = 1 if data.save_data == 'Retain payment data for this party' else 0
			payment_profile.save()
			return {'message': 'Success', 'payment_profile_doc': payment_profile}
		else:
			error_message = str(response.messages.message[0]['text'].text)
			frappe.log_error(message=frappe.get_traceback(), title=error_message)
			return {'error': error_message}


	def charge_customer_profile(self, doc, data):
		if not data.get('customer_profile'):
			customer_profile_id = frappe.get_value('Customer', doc.customer, 'electronic_payment_profile')
		else: 
			customer_profile_id = data.get('customer_profile')
		if not customer_profile_id:
			customer_profile_id = frappe.get_value(
				'Electronic Payment Profile',
				{'party': doc.customer},
				'party_profile'
			)
		payment_profile_id = frappe.get_value(
			'Electronic Payment Profile',
			{'party': doc.customer},
			'payment_profile_id'
		)
		merchantAuth = self.merchant_auth(doc.company)

		profileToCharge = apicontractsv1.customerProfilePaymentType()
		profileToCharge.customerProfileId = str(customer_profile_id)
		profileToCharge.paymentProfile = apicontractsv1.paymentProfile()
		profileToCharge.paymentProfile.paymentProfileId = str(payment_profile_id)

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType = "authCaptureTransaction"
		transactionrequest.amount = Decimal(str(doc.grand_total))
		transactionrequest.currencyCode = frappe.defaults.get_global_default('currency')
		transactionrequest.profile = profileToCharge

		createtransactionrequest = apicontractsv1.createTransactionRequest()
		createtransactionrequest.merchantAuthentication = merchantAuth
		createtransactionrequest.refId = doc.name

		createtransactionrequest.transactionRequest = transactionrequest
		createtransactioncontroller = createTransactionController(createtransactionrequest)
		createtransactioncontroller.execute()

		response = createtransactioncontroller.getresponse()
		error_message = None

		if response is not None:
			if response.messages.resultCode == "Ok":
				if hasattr(response.transactionResponse, 'messages'):
					if not frappe.get_value('Electronic Payment Profile', {'party': doc.customer, 'payment_profile_id': payment_profile_id}, 'retain'):
						frappe.get_doc('Electronic Payment Profile', {'party': doc.customer, 'payment_profile_id': payment_profile_id}).delete()
						deleteCustomerPaymentProfile = apicontractsv1.deleteCustomerPaymentProfileRequest()
						deleteCustomerPaymentProfile.merchantAuthentication = merchantAuth
						deleteCustomerPaymentProfile.customerProfileId = str(customer_profile_id)
						deleteCustomerPaymentProfile.customerPaymentProfileId = payment_profile_id

						controller = deleteCustomerPaymentProfileController(deleteCustomerPaymentProfile)
						controller.execute()
						pmt_delete_response = controller.getresponse()

						if pmt_delete_response is None or (hasattr(pmt_delete_response, 'messages') and pmt_delete_response.messages.resultCode != 'Ok'):
							frappe.log_error(message=frappe.get_traceback(), title=f'Error deleting customer payment profile used for {doc.name}')

					create_payment_entry(doc, data, response.transactionResponse.transId)
					return {"message": "Success", "transaction_id": str(response.transactionResponse.transId)}
				else:
					if hasattr(response.transactionResponse, 'errors'):
						error_message = str(response.transactionResponse.errors.error[0].errorText)
			else:
				if hasattr(response, 'transactionResponse') == True and hasattr(response.transactionResponse, 'errors') == True:
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = str(response.messages.message[0]['text'].text)
		else:
			error_message = 'No response'
		
		frappe.log_error(message=frappe.get_traceback(), title=error_message)
		return {'error': error_message}
		
	
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
		- transaction ID (saved in doc.remarks or payment entry)
		- amount of refund (assumes contained in data)
		- currency
		- payment info (can request with transaction ID)
		  - CC refunds need either original transaction ID and CC's last 4 digits
		  - Bank account refunds need routing number, account number, and account holder's name
		"""
		merchantAuth = self.merchant_auth(doc.company)
		orig_transaction_id = doc.remarks
		amount = data.get('amount')

		# Validate amount is <= doc grand total less any other refunds
		prev_refunded_amt = 0  # TODO: collect any other refunds made on this doc
		if amount > (doc.grand_total - prev_refunded_amt):
			frappe.throw(_('The refund amount must be less than or equal to the grand total less any previously refunded amounts.'))
		
		# Request transaction details for payment information
		txn_details_response = self.get_transaction_details(doc.company, orig_transaction_id)
		error_message = None

		if txn_details_response.get('message') == 'Success':
			payment_details = txn_details_response.get('payment_details')
		else:
			return txn_details_response

		if payment_details.type == 'creditCard':
			creditCard = apicontractsv1.creditCardType()
			creditCard.cardNumber = payment_details.cardNumber[-4:]
			creditCard.expirationDate = payment_details.expirationDate  # will be XXXX as it's masked for refunds. Per docs: "For refunds, use XXXX instead of the card expiration date."
			payment = apicontractsv1.paymentType()
			payment.creditCard = creditCard
		elif payment_details.type == 'bankAccount':
			bankAccount = apicontractsv1.bankAccountType()
			bankAccount.accountType = payment_details.accountType
			bankAccount.routingNumber = payment_details.routingNumber
			bankAccount.accountNumber = payment_details.accountNumber
			bankAccount.nameOnAccount = payment_details.nameOnAccount
			payment = apicontractsv1.paymentType()
			payment.bankAccount = bankAccount
		else:
			error_message = 'Unrecognized payment type for given transaction ID'

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType = "refundTransaction"
		transactionrequest.amount = Decimal(str(amount))
		transactionrequest.currencyCode = frappe.defaults.get_global_default('currency')
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
				if hasattr(response.transactionResponse, 'messages'):
					# TODO: handle refund in ERPNext
					# pe = frappe.get_doc('Payment Entry', {'reference_no': orig_transaction_id})
					# pe.cancel()
					return {'message': 'Success', 'transaction_id': str(response.transactionResponse.transId)}
				elif hasattr(response.transactionResponse, 'errors'):
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = 'Transaction request error'
			else:
				if hasattr(response, 'transactionResponse') and hasattr(response.transactionResponse, 'errors'):
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = str(response.messages.message[0]['text'].text)
		else:
			error_message = 'No Repsonse'
		
		frappe.log_error(message=frappe.get_traceback(), title=error_message)
		return {'error': error_message}


	def void_transaction(self, doc, data):
		merchantAuth = self.merchant_auth(doc.company)
		orig_transaction_id = doc.remarks

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType = "voidTransaction"
		transactionrequest.refTransId = orig_transaction_id

		createtransactionrequest = apicontractsv1.createTransactionRequest()
		createtransactionrequest.merchantAuthentication = merchantAuth

		createtransactionrequest.transactionRequest = transactionrequest
		createtransactioncontroller = createTransactionController(createtransactionrequest)
		createtransactioncontroller.execute()

		response = createtransactioncontroller.getresponse()
		error_message = None
		
		if response is not None:
			if response.messages.resultCode == "Ok":
				if hasattr(response.transactionResponse, 'messages'):
					# TODO: handle refund in ERPNext
					# pe = frappe.get_doc('Payment Entry', {'reference_no': orig_transaction_id})
					# pe.cancel()
					return {'message': 'Success', 'transaction_id': str(response.transactionResponse.transId)}
				elif hasattr(response.transactionResponse, 'errors'):
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = 'Transaction request error'
			else:
				if hasattr(response, 'transactionResponse') and hasattr(response.transactionResponse, 'errors'):
					error_message = str(response.transactionResponse.errors.error[0].errorText)
				else:
					error_message = str(response.messages.message[0]['text'].text)
		else:
			error_message = 'No Repsonse'
		
		frappe.log_error(message=frappe.get_traceback(), title=error_message)
		return {'error': error_message}


	def get_transaction_details(self, company, transaction_id):
		"""
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
		error_message = None

		if response is not None:
			if response.messages.resultCode == 'Ok':
				if hasattr(response.transaction.payment, 'creditCard'):
					payment_dict = frappe._dict({
						'type': 'creditCard',
						'cardNumber': str(response.transaction.payment.creditCard.cardNumber),
						'expirationDate': str(response.transaction.payment.creditCard.expirationDate),
					})
					return {'message': 'Success', 'payment_details': payment_dict}
				elif hasattr(response.transaction.payment, 'bankAccount'):
					payment_dict = frappe._dict({
						'type': 'bankAccount',
						'accountType': str(response.transaction.payment.bankAccount.accountType),
						'routingNumber': str(response.transaction.payment.bankAccount.routingNumber),
						'accountNumber': str(response.transaction.payment.bankAccount.accountNumber),
						'nameOnAccount': str(response.transaction.payment.bankAccount.nameOnAccount),
					})
					return {'message': 'Success', 'payment_details': payment_dict}
				else:
					error_message = 'Transaction details have unrecognized payment type'
			else:
				if response.messages is not None:
					error_message = response.messages.message[0]['text'].text
				else:
					error_message = 'Failed to get transaction details'
		else:
			error_message = 'No response'
	
		frappe.log_error(message=frappe.get_traceback(), title=error_message)
		return {'error': error_message}

