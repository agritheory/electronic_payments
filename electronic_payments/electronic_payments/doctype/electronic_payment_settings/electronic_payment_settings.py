import frappe
import json

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.authorize import (
	AuthorizeNet,
	fetch_authorize_transactions,
)
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.stripe import (
	Stripe,
	fetch_stripe_transactions,
)

# from frappe.utils.data import today
from frappe.model.document import Document


class ElectronicPaymentSettings(Document):
	def validate(self):
		# create mode of payment if one is not selected
		mop_name = self.provider + " API"
		if not frappe.db.exists("Mode of Payment", mop_name):
			mop = frappe.new_doc("Mode of Payment")
			mop.mode_of_payment = mop_name
			mop.enabled = 1
			mop.type = "General"  # TODO: confirm selection
			# mop.append(  # TODO: need this?
			# 	"accounts",
			# 	{
			# 		"company": self.company,
			# 		"default_account": frappe.get_value("Company", self.company, "default_bank_account")  # TODO: use deposit or withdrawal account field instead?
			# 	},
			# )
			mop.save()
		self.mode_of_payment = mop_name

	def client(self):
		if self.provider == "Authorize.net":
			return AuthorizeNet()
		if self.provider == "Stripe":
			return Stripe()


@frappe.whitelist()
def process(doc, data):
	doc = frappe._dict(json.loads(doc)) if isinstance(doc, str) else doc
	data = frappe._dict(json.loads(data)) if isinstance(data, str) else data
	settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
	if not settings:
		frappe.msgprint(frappe._(f"No Electronic Payment Settings found for {doc.company}"))
	client = settings.client()
	response = client.process_transaction(doc, data)
	return response


@frappe.whitelist()
def fetch_transactions():
	for settings in frappe.get_all("Electronic Payments Settings"):
		settings = frappe.get_doc("Electronic Payments Settings", settings)

		if settings.provider == "Authorize.net":
			response = fetch_authorize_transactions(settings)
		elif settings.provider == "Stripe":
			response = fetch_stripe_transactions(settings)

		if response.get("message") == "Success":
			transactions = response.get("transactions")
			process_transactions(settings, transactions)
		else:  # TODO: handle error in way to notify users
			return response


def process_transactions(settings, transactions):
	"""
	Reconciliation function to loop over transactions and create draft
	        Journal Entry depending on type of transaction.

	:param settings:
	:param transactions: list of frappe._dict object with transactional
	        data per transaction from provider

	Requirements:
	- Try to link to original order/invoice, tracks transactions that aren't matched
	- Accommodate different workflow for Payment Entry or Journal Entry with Clearing Account options
	    - Payment Entry (SO/SI): charge had credit to A/R, debit to Deposit Account. This JE needs to credit Deposit Account, debit fee expense account by fee amount
	    - Payment Entry (PI): debit to A/P, credit to Withdrawal Account. This JE needs to credit Withdrawal Account, debit fee expense account by fee amount
	    - Journal Entry (SO/SI): charge had credit to A/R, debit to EP A/R account. This JE needs to credit EP A/R account (total), debit Deposit Account (total less fees) and fee account (fees)
	    - Journal Entry (PI): charge had debit to A/P, credit to EP A/P account. This JE needs to debit EP A/P account (total), credit Withdrawal Account (total less fees) and fee account (fees)
	- JE's handle charges, refunds, voids, and any other transaction type
	- JE remains in draft form for user to review, then cancel/amend/submit
	"""
	je = frappe.new_doc("Journal Entry")
	for entry in transactions:
		# handle voided transaction
		je.append(
			"accounts",
			{
				"account": "",
				"party_type": "",
				"party": "",
				# "clearance_date": batch.settlementTimeLocal,  # TODO: import batch
				"amount": entry.statistics.statistic.chargeAmount,
			},
		)
	return None
