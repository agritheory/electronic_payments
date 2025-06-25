# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import json
import uuid
from urllib.parse import urljoin

import frappe
import requests
from frappe import _
from frappe.utils import cint, flt
from frappe.utils.password import get_decrypted_password
from requests.exceptions import HTTPError

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	calculate_payment_method_fees,
	exceeds_credit_limit,
	get_discount_amount,
	get_party_details,
	get_payment_amount,
	process_electronic_payment,
	queue_method_as_admin,
	state_label_lookup,
)


class Mercury:
	def get_base_url_and_header(self, company):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": company})
		if not settings:
			frappe.msgprint(_(f"No Electronic Payment Settings found for {company}"))
		else:
			api_key_field = "api_key" if settings.provider == "Mercury" else "sending_api_key"
			endpoint_field = "endpoint" if settings.provider == "Mercury" else "sending_endpoint"
			api_key = get_decrypted_password(
				settings.doctype, settings.name, api_key_field, raise_exception=False
			)
			base_url = settings.get(endpoint_field)
			headers = {
				"Accept": "application/json",
				"Authorization": f"Bearer {api_key}",
				"Content-Type": "application/json",
			}
			return base_url, headers

	def process_transaction(self, doc, data, bypass_je_pe_creation=False):
		mop = data.mode_of_payment.replace("New ", "")
		party = get_party_details(doc)
		save_only = data.save_data == "Save payment data only"

		if party.doctype == "Customer" or mop == "Card":
			return {"error": _("Not Supported.")}

		if (
			mop.startswith("Saved")
			and data.get("subject_to_credit_limit")
			and exceeds_credit_limit(doc, data)
		):
			return {"error": "Credit Limit exceeded for selected Mode of Payment"}

		if not mop.startswith("Saved"):
			# new ACH, save payment data (temporarily if txn only - payment profile deleted once charge is successful)
			pmt_profile_response = self.create_party_payment_profile(doc, data)
			if pmt_profile_response.get("message") == "Success":
				pp_doc = pmt_profile_response.get("payment_profile_doc")
				data.update({"payment_profile_id": pp_doc.payment_profile_id})
				if save_only:
					return pmt_profile_response
			else:  # error creating the customer payment profile
				return pmt_profile_response

		response = self.create_transfer_to_party_profile(
			doc, data, bypass_je_pe_creation=bypass_je_pe_creation
		)
		return response

	def process_credit_card(self, doc, data):
		"""
		Unsupported
		"""
		return {"error": _("Not supported.")}

	def get_accounts(self, company):
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.get(
				urljoin(base_url, "/api/v1/accounts"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()
			if r.get("accounts"):
				accounts_data = []
				for account in r["accounts"]:
					balance = account.get("availableBalance", 0)
					a_type = account.get("kind", "unknown")
					accounts_data.append(
						f"Account {account['name']} of type {a_type} with available balance ${balance:,.0f} has ID: {account['id']}"
					)

				return {"message": "Success", "data": accounts_data}

		except HTTPError as e_http:
			err_msg = response.json().get("errors", {}).get("message", e_http)
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title="Error requesting a list of accounts associated with this Mercury account.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title="Request error getting a list of accounts associated with this Mercury account.",
			)
			return {"error": f"{e}"}

	def edit_customer_payment_profile(self, company, electronic_payment_profile_name, data):
		payment_profile = frappe.get_doc(
			"Electronic Payment Profile", {"name": electronic_payment_profile_name}
		)
		profile_id = payment_profile.payment_profile_id
		epps = frappe.get_all("Electronic Payment Profile", {"payment_profile_id": profile_id})
		num_profiles = len(epps)
		update_wire = num_profiles > 1 or data.get("accept_wire")
		create_wire_epp = num_profiles == 1 and data.get("accept_wire")

		try:
			account_number = str(data.get("account_number"))
			routing_number = str(data.get("routing_number"))
			last4 = account_number[-4:]
			address = {
				"address1": data.get("address_firstline"),
				"address2": data.get("address_secondline", ""),
				"city": data.get("city"),
				"region": data.get("state"),
				"postalCode": data.get("postcode"),
				"country": data.get("country", "US").upper(),
			}
			recipient_data = {
				"name": data.get("account_holders_name"),
				"emails": [data.get("email")],
				"paymentMethod": "electronic",
				"electronicRoutingInfo": {
					"accountNumber": account_number,
					"routingNumber": routing_number,
					"electronicAccountType": "businessChecking",
					"address": address,
				},
				"nickname": f"{payment_profile.party}-*{last4}",
			}
			if update_wire:
				recipient_data.update(
					{
						"domesticWireRoutingInfo": {
							"accountNumber": account_number,
							"routingNumber": routing_number,
							"address": address,
						}
					}
				)

			base_url, headers = self.get_base_url_and_header(company)
			response = requests.post(
				urljoin(base_url, f"/api/v1/recipient/{payment_profile.payment_profile_id}"),
				headers=headers,
				timeout=10,
				data=json.dumps(recipient_data),
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				for ep in epps:
					payment_profile = frappe.get_doc("Electronic Payment Profile", ep)
					payment_profile.reference = (
						f"**** **** **** {last4}" if payment_profile.payment_type == "Card" else f"*{last4}"
					)
					payment_profile.save(ignore_permissions=True)
					ppm = frappe.get_doc(
						"Portal Payment Method", {"electronic_payment_profile": payment_profile.name}
					)
					ppm.label = f"{payment_profile.payment_type}-{last4}"
					ppm.default = (
						cint(data.get("default", 0))
						if payment_profile.name == electronic_payment_profile_name
						else 0
					)
					ppm.electronic_payment_profile = payment_profile.name
					ppm.save(ignore_permissions=True)
				# Get the original profile doc
				opp = frappe.get_doc("Electronic Payment Profile", {"name": electronic_payment_profile_name})
				if create_wire_epp:
					payment_profile = frappe.new_doc("Electronic Payment Profile")
					payment_profile.party_type = opp.party_type
					payment_profile.party = opp.party
					payment_profile.payment_type = "Wire"
					payment_profile.payment_gateway = opp.payment_gateway
					payment_profile.reference = opp.reference
					payment_profile.payment_profile_id = opp.payment_profile_id
					payment_profile.party_profile = None  # Not used in Mercury
					payment_profile.retain = 1
					payment_profile.save(ignore_permissions=True)

					ppm = frappe.new_doc("Portal Payment Method")
					ppm.mode_of_payment = "Mercury Wire"
					ppm.label = f"Wire-{last4}"
					ppm.default = 0
					ppm.electronic_payment_profile = payment_profile.name
					ppm.service_charge = 0
					ppm.parent = payment_profile.party
					ppm.parenttype = payment_profile.party_type
					ppm.save(ignore_permissions=True)

					party_obj = frappe.get_doc(payment_profile.party_type, payment_profile.party)
					party_obj.append("portal_payment_method", ppm)
					party_obj.save(ignore_permissions=True)

				return {"message": "Success", "payment_profile_doc": opp}

		except HTTPError as e_http:
			err_msg = response.json().get("errors", {}).get("message", e_http)
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title="Error trying to edit Recipient Account.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title="Request error while trying to edit Recipient Account.",
			)
			return {"error": f"{e}"}

	def get_customer_payment_profile(self, company, electronic_payment_profile_name):
		party, payment_profile_id = frappe.get_value(
			"Electronic Payment Profile",
			{"name": electronic_payment_profile_name},
			["party", "payment_profile_id"],
		)
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.get(
				urljoin(base_url, f"/api/v1/recipient/{payment_profile_id}"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				state = r.get("electronicRoutingInfo", {}).get("address", {}).get("region", "")
				state_label = state_label_lookup(state)
				return {
					"message": "Success",
					"data": {
						"first_name": r.get("name"),
						"last_name": "",
						"email": r.get("emails", [""])[0],
						"account_type": r.get("electronicRoutingInfo", {}).get("electronicAccountType", ""),
						"routing_number": str(r.get("electronicRoutingInfo", {}).get("routingNumber", "")),
						"account_number": str(r.get("electronicRoutingInfo", {}).get("accountNumber", "")),
						"name_on_account": r.get("name", ""),
						"address_firstline": r.get("electronicRoutingInfo", {})
						.get("address", {})
						.get("address1", ""),
						"address_secondline": r.get("electronicRoutingInfo", {})
						.get("address", {})
						.get("address2", ""),
						"city": r.get("electronicRoutingInfo", {}).get("address", {}).get("city", ""),
						"state": state,
						"state_label": state_label,
						"postcode": r.get("electronicRoutingInfo", {}).get("address", {}).get("postalCode", ""),
						"country": r.get("electronicRoutingInfo", {}).get("address", {}).get("country", ""),
						"echeck_type": None,
					},
				}

		except HTTPError as e_http:
			err_msg = response.json().get("errors", {}).get("message", e_http)
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error collecting payment profile for {party}",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error collecting payment profile for {party}",
			)
			return {"error": f"{e}"}

	def create_party_payment_profile(self, doc, data):
		party = get_party_details(doc)
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
		mop = data.mode_of_payment.replace("New ", "")
		pmt_types = [mop]
		save_data = data.save_data in [
			"Retain payment data for this party and process",
			"Save payment data only",
		]

		if mop not in ["ACH", "Wire"]:
			return {"error": _("Mode of Payment not supported")}

		try:
			account_number = str(data.get("account_number"))
			last4 = account_number[-4:]
			address = {
				"address1": data.get("address_firstline"),
				"address2": data.get("address_secondline", ""),
				"city": data.get("city"),
				"region": data.get("state"),
				"postalCode": data.get("postcode"),
				"country": data.get("country", "US").upper(),
			}
			recipient_data = {
				"name": data.get("account_holders_name"),
				"nickname": f"{party.name}-*{last4}",
				"emails": [data.get("email")],
				"paymentMethod": "electronic",
				"electronicRoutingInfo": {
					"accountNumber": account_number,
					"routingNumber": str(data.get("routing_number")),
					"electronicAccountType": "businessChecking",
					"address": address,
				},
			}
			if data.get("accept_wire"):
				recipient_data.update(
					{
						"domesticWireRoutingInfo": {
							"accountNumber": account_number,
							"routingNumber": str(data.get("routing_number")),
							"address": address,
						}
					}
				)
				if save_data:
					# Create a separate Wire profile
					pmt_types = ["Wire"] + pmt_types

			base_url, headers = self.get_base_url_and_header(doc.company)
			response = requests.post(
				urljoin(base_url, "/api/v1/recipients"),
				headers=headers,
				timeout=10,
				data=json.dumps(recipient_data),
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				for pmt_type in pmt_types:
					payment_profile = frappe.new_doc("Electronic Payment Profile")
					payment_profile.party_type = party.doctype
					payment_profile.party = party.name
					payment_profile.payment_type = pmt_type
					payment_profile.payment_gateway = "Mercury"
					payment_profile.reference = f"*{last4}"
					payment_profile.payment_profile_id = str(r.get("id"))
					payment_profile.party_profile = None  # Not used in Mercury
					payment_profile.retain = int(save_data)
					payment_profile.save(ignore_permissions=True)

					if payment_profile.retain and settings.create_ppm:
						ppm = frappe.new_doc("Portal Payment Method")
						ppm.mode_of_payment = f"Mercury {pmt_type}"
						ppm.label = f"{pmt_type}-{last4}"
						ppm.default = cint(data.get("default", 0))
						ppm.electronic_payment_profile = payment_profile.name
						ppm.service_charge = 0
						ppm.parent = payment_profile.party
						ppm.parenttype = payment_profile.party_type
						ppm.save(ignore_permissions=True)

						party_obj = frappe.get_doc(party.doctype, party.name)
						party_obj.append("portal_payment_method", ppm)
						party_obj.save(ignore_permissions=True)
						data.update({"ppm_name": ppm.name})

				return {"message": "Success", "payment_profile_doc": payment_profile}

		except HTTPError as e_http:
			err_msg = response.json().get("errors", {}).get("message", e_http)
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error trying to create a Recipient Account for {party.name}.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error while trying to create a Recipient Account for {party.name}.",
			)
			return {"error": f"{e}"}

	def charge_party_profile(self, doc, data):
		return {"error": _("Not supported")}

	def create_transfer_to_party_profile(self, doc, data, bypass_je_pe_creation=False):
		"""
		Sends a payment to specified party profile in the data dict.

		:param doc: typically expects a PO or PI doc. If calling from Check Run, can pass a
		frappe._dict with company, supplier, supplier_name, and currency (and the data dict must
		specify the amount)
		:param data: frappe._dict must include payment_profile_id. Can optionally include amount
		(to override calculated amount), payment_term (to calculate payment total and discounts),
		and ppm_name (to calculate fees configured for that portal payment method)
		:param bypass_je_pe_creation: bool; default is False. If True, will not queue method that
		creates a Journal Entry or Payment Entry following a successful API response - useful when
		method is called from a Check Run, and a Payment Entry already exists
		:return: dict; either {"message": "Success", "transaction_id": ...} or {"error": ...}

		Side effects:
		- if the associated Electronic Payment Profile does not have "retain" checked,
		it will be deleted after a successful transfer
		- if bypass_je_pe_creation is False, will create a Journal Entry or Payment Entry tied to
		the transfer and doc following a successful API response
		"""
		party = get_party_details(doc)
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
		merch_id_field = "ref_id" if settings.provider == "Mercury" else "sending_ref_id"
		account_id = settings.get(merch_id_field)
		payment_profile_id = data.get("payment_profile_id")
		payment_amount = data.get("amount") or get_payment_amount(doc, data)
		discount_amount = 0 if data.get("amount") else get_discount_amount(doc, data)
		if data.get("ppm_name") and not data.get("additional_charges"):
			data.update({"additional_charges": calculate_payment_method_fees(doc, data)})
		total_to_pay = flt(
			payment_amount - discount_amount + data.get("additional_charges", 0),
			frappe.get_precision(doc.doctype, "grand_total"),
		)
		try:
			base_url, headers = self.get_base_url_and_header(doc.company)
			idempotency_key = str(uuid.uuid4())  # TODO: save to doc if transfer fails?
			response = requests.post(
				urljoin(base_url, f"/api/v1/account/{account_id}/transactions"),
				headers=headers,
				timeout=10,
				data=json.dumps(
					{
						"recipientId": payment_profile_id,
						"amount": total_to_pay,
						"paymentMethod": "ach",
						"idempotencyKey": idempotency_key,
					}
				),
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				transaction_id = r.get("id")
				if not frappe.get_value(
					"Electronic Payment Profile",
					{"party": party.name, "payment_profile_id": payment_profile_id},
					"retain",
				):
					reference = frappe.get_value("Electronic Payment Profile", "reference")
					frappe.get_doc(
						"Electronic Payment Profile",
						{"party": party.name, "payment_profile_id": payment_profile_id},
					).delete()

					# Deleting Recipients not available via API, log error that it must be done manually
					frappe.log_error(
						message=f"Mercury does not allow deleting Recipients via the API. Please visit mercury.com to manually remove the payment profile {reference} used for {doc.name}.",
						title=f"Payment profile used for {doc.name} must be deleted manually at Mercury.com",
					)

				if not bypass_je_pe_creation:
					queue_method_as_admin(
						process_electronic_payment,
						doc=doc,
						data=data,
						transaction_id=str(transaction_id),
					)
				return {
					"message": "Success",
					"transaction_id": str(transaction_id),
				}

		except HTTPError as e_http:
			err_msg = response.json().get("errors", {}).get("message", e_http)
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error creating Transfer for {doc.name}.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error creating Transfer for {doc.name}.",
			)
			return {"error": f"{e}"}

	def refund_transaction(self, doc, data):
		"""
		TODO: how to request refund?
		"""
		orig_transaction_id = doc.electronic_payment_reference
		amount = data.get("amount")

		# Validate amount is <= doc grand total less any other refunds
		prev_refunded_amt = 0
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
		# TODO refund in API and ERPNext

	def void_transaction(self, doc, data):
		return {"error": _("Not supported.")}

	def get_transaction_details(self, company, transaction_id):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": company})
		merch_id_field = "ref_id" if settings.provider == "Mercury" else "sending_ref_id"
		account_id = settings.get(merch_id_field)
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.get(
				urljoin(base_url, f"/api/v1/account/{account_id}/transaction/{transaction_id}"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				payment_dict = frappe._dict(
					{
						"type": "bankAccount",
						"accountType": r.get("details", {})
						.get("electronicRoutingInfo", {})
						.get("electronicAccountType", ""),
						"routingNumber": str(
							r.get("details", {}).get("electronicRoutingInfo", {}).get("routingNumber", "")
						),
						"accountNumber": str(
							r.get("details", {}).get("electronicRoutingInfo", {}).get("accountNumber", "")
						),
						"nameOnAccount": r.get("counterpartyName", ""),
					}
				)
				return {"message": "Success", "payment_details": payment_dict}

		except HTTPError as e_http:
			err_msg = response.json().get("errors", {}).get("message", e_http)
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error collecting transfer details for {transaction_id}",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error collecting transfer details for {transaction_id}",
			)
			return {"error": f"{e}"}

	def delete_payment_profile(self, company, payment_profile_id):
		# Delete from ERPNext
		# In event a Wire EPP were also created (which would have the same ID), collect all
		epps = frappe.get_all("Electronic Payment Profile", {"payment_profile_id": payment_profile_id})
		for ep in epps:
			epp_name, party, reference = frappe.get_value(
				"Electronic Payment Profile",
				ep,
				["name", "party", "reference"],
			)
			pmm_name = frappe.get_value("Portal Payment Method", {"electronic_payment_profile": epp_name})

			frappe.delete_doc("Portal Payment Method", pmm_name, ignore_permissions=True)
			frappe.delete_doc("Electronic Payment Profile", epp_name, ignore_permissions=True)

		# Deleting Recipients not available via API, log error that it must be done manually
		frappe.log_error(
			message=f"Mercury does not allow deleting Recipients via the API. Please visit mercury.com to manually remove the payment profile {reference} for {party}.",
			title=f"Payment profile for {party} must be deleted manually at Mercury.com",
		)
		return {"message": "Success"}

	def delete_customer_profile(self, company, customer):
		# Not used in Mercury
		frappe.set_value("Customer", customer, "electronic_payment_profile", "")
		return {"message": "Success"}


def fetch_mercury_transactions(settings):
	# TODO
	settings = frappe._dict(json.loads(settings)) if isinstance(settings, str) else settings
	return []
