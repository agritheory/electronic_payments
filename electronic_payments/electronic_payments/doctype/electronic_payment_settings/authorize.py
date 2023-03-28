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

	def process_credit_card(self, doc, data):
		card_number = data.get('card_number')
		creditCard = apicontractsv1.creditCardType()
		creditCard.cardNumber = card_number.replace(' ', '')
		creditCard.expirationDate = data.get('card_expiration_date')
		creditCard.cardCode = data.get('card_cvc')
		payment = apicontractsv1.paymentType()
		payment.creditCard = creditCard

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType ="authCaptureTransaction"
		transactionrequest.amount = data.get('amount')
		transactionrequest.currencyCode = frappe.defaults.get_global_default('currency')
		transactionrequest.payment = payment
		
		createtransactionrequest = apicontractsv1.createTransactionRequest()
		createtransactionrequest.merchantAuthentication = self.merchant_auth(doc.company)
		createtransactionrequest.refId = self.ref_id

		createtransactionrequest.transactionRequest = transactionrequest
		createtransactioncontroller = createTransactionController(createtransactionrequest)
		createtransactioncontroller.execute()

		response = createtransactioncontroller.getresponse()
		if response.messages.resultCode == "Ok":
			return {'message': 'Success', 'transaction_id': response.transactionResponse.transId}
		else:
			# frappe.log_error
			return {'error': response.messages.resultCode}

	def create_customer_profile(self, doc, data):
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
				frappe.db.set_value('Customer', doc.customer, 'electronic_payment_profile', response.customerProfileId)
				return response.customerProfileId
		else:
			# frappe.log_error(message='', title='')
			return {'error': str(response.messages.message[0]['text'].text)}

	def create_customer_payment_profile(self, doc, data):
		if not data.get('customer_profile'):
			customer_profile_id = frappe.get_value('Customer', doc.customer, 'electronic_payment_profile')
		else:
			customer_profile_id = data.get('customer_profile')
		payment_profile_id = frappe.get_value(
			'Electronic Payment Profile',
			{'payment_type': data.mode_of_payment.replace('New ', ''), 'customer': doc.customer},
			'payment_profile_id'
		)
		# if data.get('save_data') # TODO: check if customer wants payment method saved
		# frappe.db.set_value('Customer', doc.customer, 'electronic_payment_profile', payment_profile_id)  # TODO: commented because field is used to save customer ID in other areas
		merchantAuth = self.merchant_auth(doc.company)
		payment = apicontractsv1.paymentType()
		profile = apicontractsv1.customerProfilePaymentType()
		card_number = data.get('card_number')
		card_number = card_number.replace(' ', '')
		if data.mode_of_payment.replace('New ', '') == 'Card':
			creditCard = apicontractsv1.creditCardType()
			creditCard.cardNumber = card_number
			creditCard.expirationDate = data.get('card_expiration_date')
			creditCard.cardCode = data.get('card_cvc')
			payment.creditCard = creditCard
			billTo = apicontractsv1.customerAddressType()
			billTo.firstName = ' '.join(data.get('cardholder_name').split(' ')[0:-1])
			billTo.lastName = data.get('cardholder_name').split(' ')[-1][0]
		elif data.mode_of_payment.replace('New ', '') == 'ACH':
			bankAccount = apicontractsv1.bankAccountType()
			accountType = apicontractsv1.bankAccountTypeEnum
			bankAccount.accountType = accountType.checking
			bankAccount.routingNumber = str(data.get('routing_number'))
			bankAccount.accountNumber = str(data.get('account_number'))
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
			payment_profile.payment_type = data.mode_of_payment.replace('New ', '')
			payment_profile.reference = f"**** **** **** {card_number[-4:]}" if card_number else f"*{data.get('account_number')[-4:]}"
			payment_profile.payment_profile_id = str(response.customerPaymentProfileId)
			payment_profile.party_profile = str(customer_profile_id)
			payment_profile.retain = 1 if data.save_data == 'Save payment data for this customer' else 0
			payment_profile.save()
			return payment_profile
		else:
			return {'error': str(response.messages.message[0]['text'].text)}

	def charge_customer_profile(self, doc, data):
		if not data.get('customer_profile'):
			customer_profile_id = frappe.get_value('Customer', doc.customer, 'electronic_payment_profile')
		else: 
			customer_profile_id = data.get('customer_profile')
		if not customer_profile_id:
			customer_profile_id = frappe.get_value(
				'Electronic Payment Profile',
				{'customer': doc.customer},
				'party_profile'
			)	
		payment_profile_id = frappe.get_value(
			'Electronic Payment Profile',
			{'customer': doc.customer},
			'payment_profile_id'
		)
		merchantAuth = self.merchant_auth(doc.company)

		profileToCharge = apicontractsv1.customerProfilePaymentType()
		profileToCharge.customerProfileId = customer_profile_id
		profileToCharge.paymentProfile = apicontractsv1.paymentProfile()
		profileToCharge.paymentProfile.paymentProfileId = payment_profile_id

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType = "authCaptureTransaction"
		transactionrequest.amount = str(doc.grand_total)
		transactionrequest.currencyCode = frappe.defaults.get_global_default('currency')
		transactionrequest.profile = profileToCharge

		createtransactionrequest = apicontractsv1.createTransactionRequest()
		createtransactionrequest.merchantAuthentication = merchantAuth
		createtransactionrequest.refId = self.ref_id

		createtransactionrequest.transactionRequest = transactionrequest
		createtransactioncontroller = createTransactionController(createtransactionrequest)
		createtransactioncontroller.execute()

		response = createtransactioncontroller.getresponse()

		if response is not None:
			if response.messages.resultCode == "Ok":
				if hasattr(response.transactionResponse, 'messages') == True:
					if not frappe.get_value('Electronic Payment Profile', {'customer': doc.customer, 'payment_profile_id': payment_profile_id}, 'retain'):
						frappe.get_doc('Electronic Payment Profile', {'customer': doc.customer, 'payment_profile_id': payment_profile_id}).delete()
					create_payment_entry(doc, data, response.transactionResponse.transId)
					return {"message": "Success", "transaction_id": str(response.transactionResponse.transId)}
				else:
					if hasattr(response.transactionResponse, 'errors') == True:
						return {'error': str(response.transactionResponse.errors.error[0].errorText)}
			else:
				if hasattr(response, 'transactionResponse') == True and hasattr(response.transactionResponse, 'errors') == True:
					return {'error': str(response.transactionResponse.errors.error[0].errorText)}
				else:
					return {'error': str(response.messages.message[0]['text'].text)}
		else:
			return {'error': 'No Repsonse'}
		
	
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
		- amount of refund (assume doc's grand_total? handle partial refunds?)
		- currency
		- payment info (can request with transaction ID)
		  - CC refunds need either original transaction ID and CC's last 4 digits
		  - Bank account refunds need routing number, account number, and account holder's name
		"""
		merchantAuth = self.merchant_auth(doc.company)
		orig_transaction_id = doc.remarks
		amount = Decimal(data.get('amount'))

		# Validate amount is <= doc grand total less any other refunds
		prev_refunded_amt = 0  # TODO: collect any other refunds made on this doc
		if amount > (doc.grand_total - prev_refunded_amt):
			frappe.throw(_('The refund amount must be less than or equal to the grand total less any previously refunded amounts.'))
		
		# Request transaction details for payment information # TODO: verify structure of response for bank account
		txn_details_response = self.get_transaction_details(doc.company, orig_transaction_id)
		if txn_details_response.get('message') == 'Success':
			payment_details = txn_details_response.get('payment_details')
		else:
			return txn_details_response

		if hasattr(payment_details, 'creditCard'):
			creditCard = apicontractsv1.creditCardType()
			creditCard.cardNumber = payment_details.creditCard.cardNumber[-4:]
			creditCard.expirationDate = payment_details.creditCard.expirationDate  # will be XXXX as it's masked for refunds. Per docs: "For refunds, use XXXX instead of the card expiration date."
			payment = apicontractsv1.paymentType()
			payment.creditCard = creditCard
		elif hasattr(payment_details, 'bankAccount'):
			bankAccount = apicontractsv1.bankAccountType()
			accountType = apicontractsv1.bankAccountTypeEnum
			bankAccount.accountType = accountType.checking
			bankAccount.routingNumber = str(payment_details.bankAccount.routingNumber)
			bankAccount.accountNumber = str(payment_details.bankAccount.accountNumber)
			bankAccount.nameOnAccount = payment_details.bankAccount.nameOnAccount
			payment = apicontractsv1.paymentType()
			payment.bankAccount = bankAccount
		else:
			return {'error': 'Unrecognized payment type for given transaction ID.'}

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType = "refundTransaction"
		transactionrequest.amount = amount
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
					return {'error': str(response.transactionResponse.errors.error[0].errorText)}
				else:
					return {'error': 'Transaction request error'}
			else:
				if hasattr(response, 'transactionResponse') and hasattr(response.transactionResponse, 'errors'):
					return {'error': str(response.transactionResponse.errors.error[0].errorText)}
				else:
					return {'error': str(response.messages.message[0]['text'].text)}
		else:
			return {'error': 'No Repsonse'}

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
		
		if response is not None:
			if response.messages.resultCode == "Ok":
				if hasattr(response.transactionResponse, 'messages'):
					# TODO: handle refund in ERPNext
					# pe = frappe.get_doc('Payment Entry', {'reference_no': orig_transaction_id})
					# pe.cancel()
					return {'message': 'Success', 'transaction_id': str(response.transactionResponse.transId)}
				elif hasattr(response.transactionResponse, 'errors'):
					return {'error': str(response.transactionResponse.errors.error[0].errorText)}
				else:
					return {'error': 'Transaction request error'}
			else:
				if hasattr(response, 'transactionResponse') and hasattr(response.transactionResponse, 'errors'):
					return {'error': str(response.transactionResponse.errors.error[0].errorText)}
				else:
					return {'error': str(response.messages.message[0]['text'].text)}
		else:
			return {'error': 'No Repsonse'}

	def get_transaction_details(self, company, transaction_id):
		merchantAuth = self.merchant_auth(company)

		transactionDetailsRequest = apicontractsv1.getTransactionDetailsRequest()
		transactionDetailsRequest.merchantAuthentication = merchantAuth
		transactionDetailsRequest.transId = transaction_id

		transactionDetailsController = getTransactionDetailsController(transactionDetailsRequest)

		transactionDetailsController.execute()

		response = transactionDetailsController.getresponse()

		if response is not None:
			if hasattr(response, 'getTransactionDetailsResponse') and hasattr(response.getTransactionDetailsResponse, 'messages'):
				if response.getTransactionDetailsResponse.messages.resultCode == "Ok":  # messages attribute not at response's top level
					if hasattr(response.getTransactionDetailsResponse.transaction, 'payment'):
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
						return {'message': 'Success', 'payment_details': response.getTransactionDetailsResponse.transaction.payment}
					else:
						return {'error': 'Error retrieving transaction payment information.'}
				else:
					if response.getTransactionDetailsResponse.messages.message is not None:
						return {'error': response.getTransactionDetailsResponse.messages.message[0].text}
					else:
						return {'error': 'Request error'}
			else:
				if hasattr(response, 'messages') and hasattr(response.messages, 'message'):
					return {'error', response.messages.message[0].text}
				else:
					return {'error': 'Request error'}
		else:
			return {'error', 'No response'}
