import frappe
import json
import uuid
from decimal import *
import datetime

import authorizenet
from authorizenet import apicontractsv1
from authorizenet.apicontrollers import *
# TODO: fix circular import error when trying to import create_payment_entry
# from electronic_payments.electronic_payments.doctype.electronic_payment_settings.electronic_payment_settings import create_payment_entry


class AuthorizeNet():
	def get_password(self):
		pass

	def merchant_auth(self):
		merchantAuth = apicontractsv1.merchantAuthenticationType()
		merchantAuth.name = self.get_password('api_key') # get_password
		merchantAuth.transactionKey = self.get_password('transaction_key') # get_password
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
		transactionrequest.payment = payment
		
		createtransactionrequest = apicontractsv1.createTransactionRequest()
		createtransactionrequest.merchantAuthentication = self.merchant_auth()
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
		createCustomerProfile.merchantAuthentication = self.merchant_auth()
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
		merchantAuth = self.merchant_auth()
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
		merchantAuth = self.merchant_auth()

		profileToCharge = apicontractsv1.customerProfilePaymentType()
		profileToCharge.customerProfileId = customer_profile_id
		profileToCharge.paymentProfile = apicontractsv1.paymentProfile()
		profileToCharge.paymentProfile.paymentProfileId = payment_profile_id

		transactionrequest = apicontractsv1.transactionRequestType()
		transactionrequest.transactionType = "authCaptureTransaction"
		transactionrequest.amount = str(doc.grand_total)
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
					create_payment_entry(doc, data, response.transactionResponse.transId)  # TODO: fix circular import above
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

	def refund_credit_card(self, data):
		pass

	def void_transaction(self, data):
		pass