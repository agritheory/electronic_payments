from __future__ import unicode_literals

import frappe
import json
import uuid
from decimal import *
import datetime

import authorizenet
from authorizenet import apicontractsv1
from authorizenet.apicontrollers import *

from frappe.utils.data import today
from frappe.model.document import Document


# TODO: move to electronic_payments/__init__.py
@frappe.whitelist()
def process(doc, data):
	if isinstance(data, str):
		doc = json.loads(doc)
		doc = frappe.get_doc(doc['doctype'], doc['name'])
		data = frappe._dict(json.loads(data))
	eps = frappe.get_doc('Electronic Payments Settings', doc.company)
	if eps.provider = 'Authorize.Net':
		# TODO: Move this to a separate function
		if data.mode_of_payment == 'New Card' and data.save_data == 'Charge now':
			return eps.process_credit_card(doc, data)
		elif data.mode_of_payment == 'New ACH' and data.save_data == 'Charge now':
			return eps.debit_bank_account(doc, data)
		elif data.mode_of_payment == 'Saved Payment Method':
			return eps.charge_customer_profile(doc, data)
		elif data.save_data != 'Charge now':
			data["customer_profile"] = eps.create_customer_profile(doc, data)
			payment_profile = eps.create_customer_payment_profile(doc, data)
			if payment_profile.get('error'):
				return payment_profile
			if payment_profile.retain == 0:
				frappe.db.set_value(doc.doctype, doc.name, 'pre_authorization_token', payment_profile.payment_profile_id)
			else:
				frappe.db.set_value('Customer', doc.customer, 'electronic_payment_profile', payment_profile.customer_profile)
			return payment_profile
		else:
			frappe.throw('Invalid options')
	if eps.provider = 'Stripe':
		... # do stripe stuff


class ElectronicPaymentSettings(Document):
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
		payment = apicontractsv1.paymentType()
		
		payment.creditCard = apicontractsv1.transactionRequestType()
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
			return {'transaction_id': response.transactionResponse.transId}
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
				return response.customerProfileId
		else:
			# frappe.log_error(message='', title='')
			return {'error': str(response.messages.message[0]['text'].text)}

	def create_customer_payment_profile(self, doc, data):
		if not data.get('customer_profile'):
			customer_profile_id = frappe.get_value('Customer', doc.customer, 'authorize_customer_profile')
		else:
			customer_profile_id = data.get('customer_profile')
		payment_profile_id = frappe.get_value(
			'Electronic Payment Profile',
			{'payment_type': data.mode_of_payment.replace('New ', ''), 'customer': doc.customer},
			'payment_profile_id'
		)
		# if data.get('save_data') # TODO: check if customer wants payment method saved
		frappe.db.set_value('Customer', doc.customer, 'authorize_customer_profile', payment_profile_id)
		merchantAuth = self.merchant_auth()
		payment = apicontractsv1.paymentType()
		profile = apicontractsv1.customerPaymentProfileType()
		card_number = data.get('card_number')
		card_number = card_number.replace(' ', '')
		if data.mode_of_payment.replace('New ', '') == 'Card':
			creditCard = apicontractsv1.creditCardType()
			creditCard.cardNumber = card_number
			creditCard.expirationDate = data.get('card_expiration_date')
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
			payment_profile.payment_type = data.mode_of_payment.replace('New ', '')
			payment_profile.customer = doc.customer
			payment_profile.reference = f"**** **** **** {card_number[-4:]}" if card_number else f"*{data.get('account_number')[-4:]}"
			payment_profile.payment_profile_id = str(response.customerPaymentProfileId)
			payment_profile.customer_profile = str(customer_profile_id)
			payment_profile.retain = 1 if data.save_data == 'Save payment data for this customer' else 0
			payment_profile.save()
			return payment_profile
		else:
			return {'error': str(response.messages.message[0]['text'].text)}

	def charge_customer_profile(self, doc, data):
		if not data.get('customer_profile'):
			customer_profile_id = frappe.get_value('Customer', doc.customer, 'authorize_customer_profile')
		else: 
			customer_profile_id = data.get('customer_profile')
		if not customer_profile_id:
			customer_profile_id = frappe.get_value(
				'Electronic Payment Profile',
				{'customer': doc.customer},
				'customer_profile'
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
					if not frappe.get_value('Electronic Payment Profile', {'customer': doc.customer}, 'retain'):
						frappe.get_doc('Electronic Payment Profile', {'customer': doc.customer}).delete()
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

	def refund_credit_card(self, data):
		pass

	def void_transaction(self, data):
		pass

def create_payment_entry(doc, data, transaction_id):
	settings = frappe.get_doc('Electronic Payments Settings', doc.company)
	pe = frappe.new_doc('Payment Entry')
	pe.mode_of_payment = settings.mode_of_payment
	pe.payment_type = 'Receive'
	pe.posting_date = today()
	pe.party_type = 'Customer'
	pe.party = doc.customer
	pe.paid_to = settings.clearing_account
	pe.paid_amount = doc.grand_total
	pe.received_amount = doc.grand_total
	pe.reference_no = str(transaction_id)
	pe.reference_date = pe.posting_date
	pe.append('references', {
		'reference_doctype': doc.doctype,
		'reference_name': doc.name,
		'allocated_amount': doc.grand_total,
	})
	pe.save()
	pe.submit()
	frappe.db.set_value(doc.doctype, doc.name, 'remarks', str(transaction_id))
	return

@frappe.whitelist()
def fetch_transactions():
	for settings in frappe.get_all('Electronic Payments Settings'):
		settings = frappe.get_doc('Electronic Payments Settings', settings)
		sorting = apicontractsv1.TransactionListSorting()
		sorting.orderBy = apicontractsv1.TransactionListOrderFieldEnum.id
		sorting.orderDescending = True
		paging = apicontractsv1.Paging()
		paging.limit = 1000
		paging.offset = 1

		transactionListRequest = apicontractsv1.getTransactionListRequest()
		transactionListRequest.merchantAuthentication = settings.merchant_auth()
		abbr = frappe.get_value('Company', settings.company, 'abbr')
		transactionListRequest.refId = f"{today()} {abbr}"
		# transactionListRequest.batchId = "4606008"  # is this required
		transactionListRequest.sorting = sorting
		transactionListRequest.paging = paging

		transactionListController = getTransactionListController(transactionListRequest)
		transactionListController.execute()
		if response is not None:
			if response.messages.resultCode == apicontractsv1.messageTypeEnum.Ok:
				if hasattr(response, 'transactions'):
					process_transactions(settings, response)


def process_transactions(settings, response):
	je = frappe.new_doc('Journal Entry')
	for entry in response.transactions:
		# handle voided transaction
		je.append('accounts', {
			'account': '',
			'party_type': '',
			'party': '',
			'clearance_date': batch.settlementTimeLocal,
			'amount': entry.statistics.statistic.chargeAmount
		})
	return response