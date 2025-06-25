# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _

# from frappe.utils.data import today
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.utils import getdate
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

	def on_update(self):
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

		if self.enable_sending and self.sending_provider:
			sending_mop_name = self.sending_provider + " ACH"
			if not frappe.db.exists("Mode of Payment", sending_mop_name):
				mop = frappe.new_doc("Mode of Payment")
				mop.mode_of_payment = sending_mop_name
				mop.enabled = 1
				mop.type = "General"
				mop.save()
			self.sending_mode_of_payment = sending_mop_name

			# Create Wire MOP for providers supporting it
			if self.sending_provider in ["Mercury", "Wise"]:
				wire_mop = self.sending_provider + " Wire"
				if not frappe.db.exists("Mode of Payment", wire_mop):
					mop = frappe.new_doc("Mode of Payment")
					mop.mode_of_payment = wire_mop
					mop.enabled = 1
					mop.type = "General"
					mop.save()

	def copy_api_config_if_same_providers(self):
		"""
		If sending payments is enabled and accepting and sending providers match, copies API
		configuration fields (if empty)
		"""
		if self.enable_accepting and self.enable_sending and self.provider == self.sending_provider:
			if self.ref_id and not self.sending_ref_id:
				self.sending_ref_id = self.sending_ref_id
			elif self.sending_ref_id and not self.ref_id:
				self.ref_id = self.sending_ref_id

			if self.endpoint and not self.sending_endpoint:
				self.sending_endpoint = self.endpoint
			elif self.sending_endpoint and not self.endpoint:
				self.endpoint = self.sending_endpoint

			if self.api_key and not self.sending_api_key:
				api_key = get_decrypted_password(self.doctype, self.name, "api_key", raise_exception=False)
				self.sending_api_key = api_key
			elif self.sending_api_key and not self.api_key:
				api_key = get_decrypted_password(
					self.doctype, self.name, "sending_api_key", raise_exception=False
				)
				self.api_key = api_key

			if self.transaction_key and not self.sending_transaction_key:
				t_key = get_decrypted_password(
					self.doctype, self.name, "transaction_key", raise_exception=False
				)
				self.sending_transaction_key = t_key
			elif self.sending_transaction_key and not self.transaction_key:
				t_key = get_decrypted_password(
					self.doctype, self.name, "sending_transaction_key", raise_exception=False
				)
				self.transaction_key = t_key

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
			frappe.msgprint(msg=message, title="Missing Required Field")

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
			frappe.msgprint(msg=message, title="Missing Required Field")

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
			frappe.msgprint(msg=message, title="Missing Required Field")

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
def get_payment_profiles_and_billing_address(doc):
	doc = frappe._dict(json.loads(doc)) if isinstance(doc, str) else doc
	party = doc.supplier if "Purchase" in doc.doctype else doc.customer

	billing_address = get_billing_address(doc)
	payment_profiles = get_payment_profiles(doc)
	results = frappe._dict({"billing_address": billing_address, "payment_profiles": payment_profiles})
	return results


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
		.where(epp.payment_type != "Wire")  # Exclude Wire methods until supported by Mercury API
		.orderby(ppm.default, order=Order.desc)
	)
	return query.run(as_dict=True)


def get_billing_address(doc):
	party = doc.supplier if "Purchase" in doc.doctype else doc.customer
	address_field = "supplier_address" if "Purchase" in doc.doctype else "customer_address"
	uses_billing = "Billing" in doc.get(address_field)

	address = frappe.qb.DocType("Address")
	dynamic_link = frappe.qb.DocType("Dynamic Link")

	query = (
		frappe.qb.from_(address)
		.inner_join(dynamic_link)
		.on(address.name == dynamic_link.parent)
		.select(
			address.address_line1,
			address.address_line2,
			address.city,
			address.state,
			address.pincode,
		)
		.where(dynamic_link.link_name == party)
		.where(address.address_type == "Billing")
		.orderby(address.modified, order=Order.desc)
		.limit(1)
	)

	if uses_billing:
		query = query.where(address.name == doc.get(address_field))

	results = query.run(as_dict=True)

	# Form address wasn't Billing and none found in query, re-run query to return form address
	if not results:
		query = query.where(address.name == doc.get(address_field))
		results = query.run(as_dict=True)
	return results[0]


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


@frappe.whitelist()
def get_check_run_button_info(cr_doc):
	"""
	Called from Check Run. Indicates whether to include a "Send [Provider] ACH" button and the
	appropriate button text. Check Run must be submitted and include transaction(s) with a
	"[Provider] ACH" mode of payment.

	:param cr_doc: a Check Run document
	:return: dict with "include_button" (bool) and "button_text" (str) keys
	"""
	cr_doc = frappe._dict(json.loads(cr_doc)) if isinstance(cr_doc, str) else cr_doc
	settings = frappe.get_doc("Electronic Payment Settings", {"company": cr_doc.company})

	include_button = False
	button_text = ""

	if settings.enable_sending and settings.sending_provider:
		sending_provider = settings.sending_provider
		cr_txns = json.loads(cr_doc.transactions)
		valid_mop_txns = [txn for txn in cr_txns if txn["mode_of_payment"] == f"{sending_provider} ACH"]
		if valid_mop_txns:
			button_text = f"Send {sending_provider} ACH"
			include_button = True
	return {"include_button": include_button, "button_text": button_text}


@frappe.whitelist()
def process_check_run_electronic_payments(cr_doc):
	"""
	Called from Check Run. Collects Payment Entries linked to given cr_doc with "[Provider] ACH"
	mode of payment, processes a transfer with the provider, and stores the transaction ID in the
	Payment Entry's reference_no field.

	:param cr_doc: a Check Run document
	:return: dict with either an Error or Success message, and errors if encountered.
	"""
	cr_doc = frappe._dict(json.loads(cr_doc)) if isinstance(cr_doc, str) else cr_doc
	settings = frappe.get_doc("Electronic Payment Settings", {"company": cr_doc.company})
	payment_types = ["ACH"]
	errors = []
	for pmt_type in payment_types:
		mode_of_payment = f"{settings.sending_provider} {pmt_type}"
		pes = frappe.get_all(
			"Payment Entry", {"check_run": cr_doc.name, "mode_of_payment": mode_of_payment}
		)
		if not pes:
			continue
		for pe in pes:
			pe_doc = frappe.get_doc("Payment Entry", pe)
			party = pe_doc.party
			pmt_profiles = get_payment_profiles(
				frappe._dict({"doctype": "Purchase Invoice", "supplier": party})
			)
			pmt_profiles = [pp for pp in pmt_profiles if pp.payment_type == pmt_type]
			if not pmt_profiles:
				err_msg = f"No {pmt_type} payment profiles found for {party}"
				frappe.log_error(
					title=_(f"Error Processing Electronic Payment to {party} for Check Run Payment Entry"),
					message=_(err_msg),
					reference_doctype="Check Run",
					reference_name=cr_doc.name,
				)
				errors.append(err_msg)
				continue
			doc = frappe._dict(
				{
					"doctype": "Purchase Invoice",
					"company": cr_doc.company,
					"supplier": party,
					"supplier_name": party,
					"currency": pe_doc.paid_to_account_currency,
				}
			)
			data = frappe._dict(
				{
					"payment_profile_id": pmt_profiles[0].payment_profile_id,
					"ppm_name": pmt_profiles[0].ppm_name,
					"subject_to_credit_limit": pmt_profiles[0].subject_to_credit_limit,
					"amount": pe_doc.paid_amount,
					"mode_of_payment": "Saved",
				}
			)
			client = settings.client(doc)
			response = client.process_transaction(doc, data, bypass_je_pe_creation=True)
			if response.get("message") == "Success":
				transaction_id = response.get("transaction_id")
				frappe.db.set_value(pe_doc.doctype, pe_doc.name, "reference_no", transaction_id)
				frappe.db.set_value(pe_doc.doctype, pe_doc.name, "reference_date", getdate())
			else:
				errors.append(response.get("error"))

	if not errors:
		return {"message": "Success"}
	else:
		err_list = "</li><li>".join(errors)
		full_msg = f"Processing {settings.sending_provider} payments generated the following errors:<br><ul><li>{err_list}</li></ul>"
		return {"message": "Error", "errors": full_msg}
