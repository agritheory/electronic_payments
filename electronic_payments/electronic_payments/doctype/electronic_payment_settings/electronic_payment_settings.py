from __future__ import unicode_literals

import frappe
import json
import uuid
from decimal import *
import datetime

from authorizenet import apicontractsv1
from authorizenet.apicontrollers import *

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.authorize import AuthorizeNet
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.stripe import Stripe

from frappe.utils.data import today
from frappe.model.document import Document


class ElectronicPaymentSettings(Document):
	def validate(self):
		# create mode of payment if one is not selected 
		pass


	def client(self):
		if self.provider == 'Authorize.Net':
			return AuthorizeNet(self)
		if self.provider == 'Stripe':
			return Stripe(self)


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
		transactionListRequest.sorting = sorting
		transactionListRequest.paging = paging

		transactionListController = getTransactionListController(transactionListRequest)
		transactionListController.execute()
		response = transactionListController.getresponse()

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
			'clearance_date': batch.settlementTimeLocal,  # TODO: import batch
			'amount': entry.statistics.statistic.chargeAmount
		})
	return response
