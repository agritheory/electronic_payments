# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import json

import frappe

# from frappe.utils.data import today
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.utils.password import get_decrypted_password

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.authorize import (
	AuthorizeNet,
	fetch_authorize_transactions,
)
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.mercury import (
	Mercury,
	fetch_mercury_transactions,
)
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.stripe import (
	Stripe,
	fetch_stripe_transactions,
)
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.wise import (
	Wise,
	fetch_wise_transactions,
)


class ElectronicPaymentSettings(Document):
	def validate(self):
		self.create_electronic_payment_mop()
		self.copy_api_config_if_same_providers()
		self.validate_mercury_merchant_id()
		self.validate_wise_merchant_id()
		self.validate_wise_direct_debit_account_id()

	def create_electronic_payment_mop(self):
		if self.provider:
			mop_name = self.provider + " API"
			if not frappe.db.exists("Mode of Payment", mop_name):
				mop = frappe.new_doc("Mode of Payment")
				mop.mode_of_payment = mop_name
				mop.enabled = 1
				mop.type = "General"
				mop.save()
			self.mode_of_payment = mop_name

		if self.enable_sending and self.provider == self.sending_provider:
			self.sending_mode_of_payment = mop_name
		elif self.enable_sending and self.sending_provider:
			sending_mop_name = self.sending_provider + " API"
			if not frappe.db.exists("Mode of Payment", sending_mop_name):
				mop = frappe.new_doc("Mode of Payment")
				mop.mode_of_payment = sending_mop_name
				mop.enabled = 1
				mop.type = "General"
				mop.save()
			self.sending_mode_of_payment = sending_mop_name

	def copy_api_config_if_same_providers(self):
		"""
		If sending payments is enabled and accepting and sending providers match, copies API
		configuration fields (if empty)
		"""
		if self.enable_sending and self.provider == self.sending_provider:
			if self.ref_id and not self.sending_ref_id:
				self.sending_ref_id = self.sending_ref_id
			if self.endpoint and not self.sending_endpoint:
				self.sending_endpoint = self.endpoint
			if self.api_key and not self.sending_api_key:
				api_key = get_decrypted_password(self.doctype, self.name, "api_key", raise_exception=False)
				self.sending_api_key = api_key
			if self.transaction_key and not self.sending_transaction_key:
				t_key = get_decrypted_password(
					self.doctype, self.name, "transaction_key", raise_exception=False
				)
				self.sending_transaction_key = t_key

	def validate_mercury_merchant_id(self):
		if self.enable_sending and self.sending_provider == "Mercury" and not self.sending_ref_id:
			client = Mercury()
			accounts_resp = client.get_accounts(self.company)
			if accounts_resp.get("message") == "Success":
				if not accounts_resp.get("data"):
					message = "Please fill in the Merchant ID field for Mercury with the Account ID of the account making transfers. There were no accounts found associated with the provided Mercury credentials, you can create them in the Mercury platform."
				else:
					m1 = "</li><li>".join(accounts_resp["data"])
					message = f"Please fill in the Merchant ID field for Mercury with the Account ID of the account making transfers. The following account options were found:<br><ul><li>{m1}</li></ul>"
			else:
				message = f"Please fill in the Merchant ID field for Mercury with the Account ID of the account making transfers. {accounts_resp['error']}"
			frappe.throw(msg=message, title="Missing Required Field")

	def validate_wise_merchant_id(self):
		if self.enable_sending and self.sending_provider == "Wise" and not self.sending_ref_id:
			client = Wise()
			profiles_resp = client.get_profiles(self.company)
			if profiles_resp.get("message") == "Success":
				if not profiles_resp["data"]:
					message = "Please fill in the Merchant ID field for Wise. There were no profiles found associated with this Wise account, you can create them in the Wise platform."
				else:
					m1 = "</li><li>".join(profiles_resp["data"])
					message = f"Please fill in the Merchant ID field for Wise. The following profiles were found for this account:<br><ul><li>{m1}</li></ul>"
			else:
				message = f"Please fill in the Merchant ID field for Wise. {profiles_resp['error']}"
			frappe.throw(msg=message, title="Missing Required Field")

	def validate_wise_direct_debit_account_id(self):
		if not self.enable_sending or not self.sending_provider == "Wise":
			return
		if self.fund_wise_with_direct_debit and not self.wise_linked_bank_account_id:
			client = Wise()
			accounts_resp = client.get_direct_debit_accounts(self.company)
			if accounts_resp.get("message") == "Success":
				if not accounts_resp["data"]:
					message = "Please fill in the Wise Linked Bank Account ID field. There were no Direct Debit Accounts found associated with this Wise profile, you can create one in the Wise platform."
				else:
					m1 = "</li><li>".join(accounts_resp["data"])
					message = f"Please fill in the Wise Linked Bank Account ID field. The following Direct Debit Accounts were found for this profile:<br><ul><li>{m1}</li></ul>"
			else:
				message = f"Please fill in the Wise Linked Bank Account ID field. {accounts_resp['error']}"
			frappe.throw(msg=message, title="Missing Required Field")

	def client(self, doc):
		"""
		Returns the class instance for the appropriate provider, depending on the doc's party.

		If `supplier` field found and sending payments is enabled, returns the sending provider,
		otherwise returns the provider to accept payments.

		:param doc: may be an actual system document or dict with a party type key like "customer"
		or "supplier".
		:return: class instance for relevant provider.
		"""
		if hasattr(doc, "supplier") and doc.get("supplier") and self.enable_sending:
			provider_field = "sending_provider"
		else:  # accepting payment workflow
			provider_field = "provider"

		if self.get(provider_field) == "Authorize.net":
			return AuthorizeNet()
		if self.get(provider_field) == "Stripe":
			return Stripe()
		if self.get(provider_field) == "Wise":
			return Wise()
		if self.get(provider_field) == "Mercury":
			return Mercury()


@frappe.whitelist()
def process(doc, data):
	doc = frappe._dict(json.loads(doc)) if isinstance(doc, str) else doc
	data = frappe._dict(json.loads(data)) if isinstance(data, str) else data
	settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
	if not settings:
		frappe.msgprint(frappe._(f"No Electronic Payment Settings found for {doc.company}"))
	client = settings.client(doc)
	response = client.process_transaction(doc, data)
	return response


@frappe.whitelist()
def get_payment_profiles(doc):
	doc = frappe._dict(json.loads(doc)) if isinstance(doc, str) else doc
	party = doc.supplier if "Purchase" in doc.doctype else doc.customer
	epp = frappe.qb.DocType("Electronic Payment Profile")
	ppm = frappe.qb.DocType("Portal Payment Method")

	query = (
		frappe.qb.from_(epp)
		.inner_join(ppm)
		.on(ppm.electronic_payment_profile == epp.name)
		.select(
			epp.payment_profile_id,
			epp.reference,
			epp.payment_type,
			epp.party_profile,
			(ppm.name).as_("ppm_name"),
			ppm.default,
			ppm.subject_to_credit_limit,
		)
		.where(epp.party == party)
		.orderby(ppm.default, order=Order.desc)
	)
	return frappe.db.sql(query, as_dict=True)


@frappe.whitelist()
def fetch_transactions():
	errors = []
	for settings in frappe.get_all("Electronic Payments Settings"):
		settings = frappe.get_doc("Electronic Payments Settings", settings)

		# Collect and process accepting payment transactions
		if settings.provider == "Authorize.net":
			response = fetch_authorize_transactions(settings)
			provider = "Authorize.net"
		elif settings.provider == "Stripe":
			response = fetch_stripe_transactions(settings)
			provider = "Stripe"

		if response.get("message") == "Success":
			transactions = response.get("transactions")
			process_transactions(settings, transactions, provider)
		else:  # TODO: handle error in way to notify users
			errors.append(response["error"])

		# Collect and process sending payment transactions
		if settings.sending_provider == "Wise":
			s_response = fetch_wise_transactions(settings)
			s_provider = "Wise"
		if settings.sending_provider == "Mercury":
			s_response = fetch_mercury_transactions(settings)
			s_provider = "Mercury"
		elif settings.sending_provider == "Authorize.net" and not settings.provider == "Authorize.net":
			s_response = fetch_authorize_transactions(settings)
			s_provider = "Authorize.net"

		if s_response.get("message") == "Success":
			s_transactions = s_response.get("transactions")
			process_transactions(settings, s_transactions, s_provider)
		else:  # TODO: handle error in way to notify users
			errors.append(response["error"])

	if errors:
		return ", ".join(errors)


def process_transactions(settings, transactions, provider):
	"""
	Reconciliation function to loop over transactions and create draft
	        Journal Entry depending on type of transaction.

	:param settings: Electronic Payments Settings doc
	:param transactions: list of frappe._dict objects with prover's transactional data
	:param provider: string indicating which provider to know data structure format

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
