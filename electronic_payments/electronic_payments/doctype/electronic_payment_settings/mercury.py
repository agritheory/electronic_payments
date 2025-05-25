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
			base_url = settings.get(endpoint_field) or "https://backend.mercury.com/api/v1"
			headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
			return base_url, headers

	def process_transaction(self, doc, data):
		mop = data.mode_of_payment.replace("New ", "")
		party = get_party_details(doc)

		if party.doctype == "Customer" or (mop == "Card" and data.get("save_data") == "Charge now"):
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
			else:  # error creating the customer payment profile
				return pmt_profile_response

		response = self.create_outbound_ach_transfer(doc, data)
		return response

	def process_credit_card(self, doc, data):
		"""
		Currently unsupported - Mercury focuses on banking/ACH
		"""
		return {"error": _("Not supported")}

	def get_accounts(self, company):
		"""
		Get list of Mercury accounts for configuration
		"""
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.get(
				urljoin(base_url, "/accounts"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()
			if r:
				account_data = []
				for account in r:
					account_type = account.get("type", "")
					name = account.get("name", "")
					account_id = account.get("id", "")
					account_data.append(f"{account_type.title()} Account '{name}' has ID: {account_id}")
				return {"message": "Success", "data": account_data}

		except HTTPError as e_http:
			try:
				err_msg = response.json().get("error", {}).get("message", str(e_http))
			except Exception as e:
				err_msg = str(e_http)
			frappe.log_error(
				message=f"{response.text}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title="Error requesting Mercury accounts list.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title="Error requesting Mercury accounts list.",
			)
			return {"error": f"{e}"}

	def create_counterparty(self, doc, data):
		"""
		Create a counterparty (recipient) for ACH transfers
		"""
		party = get_party_details(doc)
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})

		try:
			base_url, headers = self.get_base_url_and_header(doc.company)
			counterparty_data = {
				"name": data.get("account_holders_name"),
				"accountNumber": str(data.get("account_number")),
				"routingNumber": str(data.get("routing_number")),
				"accountType": "checking",  # Mercury supports checking/savings
				"address": {
					"address1": data.get("address_firstline"),
					"city": data.get("city"),
					"region": data.get("state"),
					"postalCode": data.get("postcode"),
					"country": data.get("country", "US").upper(),
				},
			}

			response = requests.post(
				urljoin(base_url, "/counterparties"),
				headers=headers,
				timeout=10,
				data=json.dumps(counterparty_data),
			)
			response.raise_for_status()
			r = response.json()

			if r.get("id"):
				return {"message": "Success", "counterparty_id": r["id"]}
			else:
				return {"error": "Failed to create counterparty"}

		except HTTPError as e_http:
			try:
				err_msg = response.json().get("error", {}).get("message", str(e_http))
			except Exception as e:
				err_msg = str(e_http)
			frappe.log_error(
				message=f"{response.text}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title="Error creating Mercury counterparty.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title="Request error creating Mercury counterparty.",
			)
			return {"error": f"{e}"}

	def edit_customer_payment_profile(self, company, electronic_payment_profile_name, data):
		return {
			"error": _(
				"Mercury does not support editing payment methods. Please delete the payment method then re-create it."
			)
		}

	def get_customer_payment_profile(self, company, electronic_payment_profile_name):
		"""
		Get counterparty details from Mercury
		"""
		party, payment_profile_id = frappe.get_value(
			"Electronic Payment Profile",
			{"name": electronic_payment_profile_name},
			["party", "payment_profile_id"],
		)
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.get(
				urljoin(base_url, f"/counterparties/{payment_profile_id}"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()

			if r.get("id"):
				return {
					"message": "Success",
					"data": {
						"first_name": " ".join(r.get("name", "").split(" ")[0:-1]),
						"last_name": r.get("name", "").split(" ")[-1],
						"account_type": r.get("accountType", "").title(),
						"routing_number": str(r.get("routingNumber", "")),
						"account_number": "*" + str(r.get("accountNumber", ""))[-4:],
						"name_on_account": r.get("name", ""),
						"echeck_type": None,
					},
				}

		except HTTPError as e_http:
			try:
				err_msg = response.json().get("error", {}).get("message", str(e_http))
			except Exception as e:
				err_msg = str(e_http)
			frappe.log_error(
				message=f"{response.text}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error collecting Mercury counterparty for {party}",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error collecting Mercury counterparty for {party}",
			)
			return {"error": f"{e}"}

	def create_party_payment_profile(self, doc, data):
		"""
		Create counterparty in Mercury and Electronic Payment Profile in ERPNext
		"""
		party = get_party_details(doc)
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
		mop_field = "mode_of_payment" if settings.provider == "Mercury" else "sending_mode_of_payment"
		mop = data.mode_of_payment.replace("New ", "")

		# Create counterparty in Mercury
		counterparty_response = self.create_counterparty(doc, data)
		if counterparty_response.get("message") != "Success":
			return counterparty_response

		counterparty_id = counterparty_response["counterparty_id"]
		account_number = str(data.get("account_number"))
		last4 = account_number[-4:]

		try:
			payment_profile = frappe.new_doc("Electronic Payment Profile")
			payment_profile.party_type = party.doctype
			payment_profile.party = party.name
			payment_profile.payment_type = mop
			payment_profile.payment_gateway = "Mercury"
			payment_profile.reference = f"*{last4}"
			payment_profile.payment_profile_id = str(counterparty_id)
			payment_profile.party_profile = None  # Not used in Mercury
			payment_profile.retain = 1 if data.save_data == "Retain payment data for this party" else 0
			payment_profile.save(ignore_permissions=True)

			if payment_profile.retain and settings.create_ppm:
				ppm = frappe.new_doc("Portal Payment Method")
				ppm.mode_of_payment = settings.get(mop_field)
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

		except Exception as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title="Error creating Electronic Payment Profile for Mercury counterparty.",
			)
			return {"error": f"{e}"}

	def charge_party_profile(self, doc, data):
		return {"error": _("Not supported")}

	def create_outbound_ach_transfer(self, doc, data):
		"""
		Create an outbound ACH transfer using Mercury API
		"""
		party = get_party_details(doc)
		payment_profile_id = data.get("payment_profile_id")
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})

		# Get Mercury account ID from settings
		mercury_account_id = (
			settings.get("ref_id") if settings.provider == "Mercury" else settings.get("sending_ref_id")
		)
		if not mercury_account_id:
			return {"error": "Mercury account ID not configured in Electronic Payment Settings"}

		payment_amount = get_payment_amount(doc, data)
		discount_amount = get_discount_amount(doc, data)
		if data.get("ppm_name") and not data.get("additional_charges"):
			data.update({"additional_charges": calculate_payment_method_fees(doc, data)})

		total_to_charge = flt(
			payment_amount - discount_amount + data.get("additional_charges", 0),
			frappe.get_precision(doc.doctype, "grand_total"),
		)

		try:
			base_url, headers = self.get_base_url_and_header(doc.company)

			# Create outbound ACH transfer
			transfer_data = {
				"accountId": mercury_account_id,
				"counterpartyId": payment_profile_id,
				"amount": int(total_to_charge * 100),  # Mercury expects cents
				"details": f"Payment for {doc.name}",
				"idempotencyKey": str(uuid.uuid4()),
			}

			response = requests.post(
				urljoin(base_url, "/outbound-transfers"),
				headers=headers,
				timeout=10,
				data=json.dumps(transfer_data),
			)
			response.raise_for_status()
			r = response.json()

			if r.get("id"):
				transaction_id = r.get("id")

				# Delete temporary payment profile if not retained
				if not frappe.get_value(
					"Electronic Payment Profile",
					{"party": party.name, "payment_profile_id": payment_profile_id},
					"retain",
				):
					# Delete from ERPNext
					frappe.get_doc(
						"Electronic Payment Profile",
						{"party": party.name, "payment_profile_id": payment_profile_id},
					).delete()

					# Delete counterparty from Mercury
					try:
						del_response = requests.delete(
							urljoin(base_url, f"/counterparties/{payment_profile_id}"),
							headers=headers,
							timeout=10,
						)
						del_response.raise_for_status()
					except Exception as del_e:
						frappe.log_error(
							message=f"Error deleting Mercury counterparty: {del_e}\n\n{frappe.get_traceback()}",
							title=f"Error deleting counterparty used for {doc.name}",
						)

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
			try:
				err_msg = response.json().get("error", {}).get("message", str(e_http))
			except Exception as e:
				err_msg = str(e_http)
			frappe.log_error(
				message=f"{response.text}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title="Error creating Mercury outbound ACH transfer.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title="Request error creating Mercury outbound ACH transfer.",
			)
			return {"error": f"{e}"}

	def refund_transaction(self, doc, data):
		"""
		Mercury doesn't have a direct refund API - would need to create a new inbound transfer
		"""
		return {"error": _("Refunds not supported - please create a new inbound transfer manually")}

	def void_transaction(self, doc, data):
		"""
		Cancel an outbound transfer (if still pending)
		"""
		orig_transaction_id = doc.electronic_payment_reference
		try:
			base_url, headers = self.get_base_url_and_header(doc.company)
			response = requests.post(
				urljoin(base_url, f"/outbound-transfers/{orig_transaction_id}/cancel"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()

			if r.get("id"):
				return {
					"message": "Success",
					"transaction_id": str(r["id"]),
				}

		except HTTPError as e_http:
			try:
				err_msg = response.json().get("error", {}).get("message", str(e_http))
			except Exception as e:
				err_msg = str(e_http)
			frappe.log_error(
				message=f"{response.text}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error canceling Mercury transfer for {doc.name}",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error canceling Mercury transfer for {doc.name}",
			)
			return {"error": f"{e}"}

	def get_transaction_details(self, company, transaction_id):
		"""
		Get details of a Mercury transfer
		"""
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.get(
				urljoin(base_url, f"/outbound-transfers/{transaction_id}"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()

			if r.get("id"):
				# Get counterparty details
				counterparty_id = r.get("counterpartyId")
				counterparty_response = requests.get(
					urljoin(base_url, f"/counterparties/{counterparty_id}"),
					headers=headers,
					timeout=10,
				)
				counterparty_response.raise_for_status()
				counterparty = counterparty_response.json()

				payment_dict = frappe._dict(
					{
						"type": "bankAccount",
						"accountType": counterparty.get("accountType", "").title(),
						"routingNumber": str(counterparty.get("routingNumber", "")),
						"accountNumber": str(counterparty.get("accountNumber", "")),
						"nameOnAccount": counterparty.get("name", ""),
					}
				)
				return {"message": "Success", "payment_details": payment_dict}

		except HTTPError as e_http:
			try:
				err_msg = response.json().get("error", {}).get("message", str(e_http))
			except Exception as e:
				err_msg = str(e_http)
			frappe.log_error(
				message=f"{response.text}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error collecting Mercury transfer details for {transaction_id}",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error collecting Mercury transfer details for {transaction_id}",
			)
			return {"error": f"{e}"}

	def delete_payment_profile(self, company, payment_profile_id):
		# Delete from ERPNext
		epp_name, party = frappe.get_value(
			"Electronic Payment Profile",
			{"payment_profile_id": payment_profile_id},
			["name", "party"],
		)
		pmm_name = frappe.get_value("Portal Payment Method", {"electronic_payment_profile": epp_name})

		if pmm_name:
			frappe.delete_doc("Portal Payment Method", pmm_name, ignore_permissions=True)
		frappe.delete_doc("Electronic Payment Profile", epp_name, ignore_permissions=True)

		# Delete from Mercury API
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.delete(
				urljoin(base_url, f"/counterparties/{payment_profile_id}"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			return {"message": "Success"}

		except HTTPError as e_http:
			try:
				err_msg = response.json().get("error", {}).get("message", str(e_http))
			except Exception as e:
				err_msg = str(e_http)
			frappe.log_error(
				message=f"{response.text}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error deleting Mercury counterparty for {party}",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error deleting Mercury counterparty for {party}",
			)
			return {"error": f"{e}"}

	def delete_customer_profile(self, company, customer):
		# Not used in Mercury - counterparties are individual entities
		return {"message": "Success"}


def fetch_mercury_transactions(settings):
	# TODO: Implement transaction fetching from Mercury API
	settings = frappe._dict(json.loads(settings)) if isinstance(settings, str) else settings
	return []
