# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt
import json
import uuid
from urllib.parse import urljoin

import frappe
import requests
from frappe import _
from frappe.utils import cint, flt, nowdate
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


class CashPro:
	def get_base_url_and_header(self, company):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": company})
		if not settings:
			frappe.msgprint(_(f"No Electronic Payment Settings found for {company}"))
		else:
			api_key_field = "api_key" if settings.provider == "CashPro" else "sending_api_key"
			endpoint_field = "endpoint" if settings.provider == "CashPro" else "sending_endpoint"
			api_key = get_decrypted_password(
				settings.doctype, settings.name, api_key_field, raise_exception=False
			)
			base_url = settings.get(endpoint_field)
			cashpro_application_id = settings.cashpro_application_id
			cashpro_client_id = settings.cashpro_client_id

			# Get access token
			data = {
				"applicationID": cashpro_application_id,
				"authn": {"client_id": cashpro_client_id, "client_secret": api_key},
			}
			try:
				response = requests.post(
					f"{base_url}authn/v1/client-authentication",
					headers={"Content-Type": "application/json"},
					data=json.dumps(data),
				)
			except HTTPError as e_http:
				err_msg = response.json().get("errors", {}).get("message", e_http)
				frappe.log_error(
					message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
					title="Error requesting a list of accounts associated with this CashPro account.",
				)
				return {"error": f"{err_msg}"}
			except requests.exceptions.RequestException as e:
				frappe.log_error(
					message=f"{e}\n\n{frappe.get_traceback()}",
					title="Request error getting a list of accounts associated with this CashPro account.",
				)
				return {"error": f"{e}"}

			headers = {
				"Authorization": f"Bearer {response.json()['access_token']}",
				"Content-Type": "application/json",
				"X-Idempotency-Key": str(uuid.uuid4()),
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

	def create_party_payment_profile(self, doc, data):
		party = get_party_details(doc)
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
		mop = data.mode_of_payment.replace("New ", "")
		save_data = data.save_data in [
			"Retain payment data for this party and process",
			"Save payment data only",
		]

		if mop not in ["ACH", "Wire"]:
			return {"error": _("Mode of Payment not supported")}

		try:
			account_number = str(data.get("account_number"))
			last4 = account_number[-4:]
			payload = {
				"templateIdentification": {
					"templateRequestIdentification": "",  # optional
					"templateCode": "",
					"templateName": "",
					"isTemplateInternal": True,  # optional
				},
				"creditInitiation": {
					"paymentMethod": "TRF",
					"amount": {
						"value": "",  # optional?
						"type": "",  # optional?
					},
					"debtorAccount": {
						"identification": "",
						"schemeName": "",
						"currency": "USD",
					},
					"debtorAgent": {
						"institution": {"name": "", "identification": "", "schemeName": ""},  # optional  # optional
						"postalAddress": {
							"addressLine": [],
							"city": "",
							"country": "",
						},
					},
					"creditor": {
						"name": data.get("account_holders_name"),  # optional?
						"postalAddress": {  # optional?
							"addressLine": [data.get("address_firstline"), data.get("address_secondline", "")],
							"city": data.get("city"),
							"country": data.get("country", "US").upper(),
						},
					},
					"creditorAccount": {
						"identification": account_number,
						"schemeName": "IBAN",  # TODO
						"currency": "USD",
					},
					"creditorAgent": {
						"institution": {"name": "", "identification": "", "schemeName": ""},  # optional  # optional
					},
					"instructionForCreditorAgent": [],
					"paymentType": {
						"priority": "",  # optional?
						"serviceLevel": "",  # optional?
						"categoryOfPurpose": "",  # optional?
					},
					"purpose": {
						"code": "",
						"description": "",  # optional
					},
				},
			}
			base_url, headers = self.get_base_url_and_header(doc.company)
			response = requests.post(
				urljoin(base_url, "/cashpro/repetitive/v1/template"),
				headers=headers,
				timeout=10,
				data=json.dumps(payload),
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				payment_profile = frappe.new_doc("Electronic Payment Profile")
				payment_profile.party_type = party.doctype
				payment_profile.party = party.name
				payment_profile.payment_type = mop
				payment_profile.payment_gateway = "CashPro"
				payment_profile.reference = f"*{last4}"
				payment_profile.payment_profile_id = str(r.get("id"))
				payment_profile.party_profile = None  # Not used in CashPro
				payment_profile.retain = int(save_data)
				payment_profile.company = doc.company
				payment_profile.save(ignore_permissions=True)

				if payment_profile.retain and settings.create_ppm:
					ppm = frappe.new_doc("Portal Payment Method")
					ppm.mode_of_payment = f"CashPro {mop}"
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

	def delete_payment_profile(self, company, payment_profile_id):
		# Delete from ERPNext
		epp_name, party = frappe.get_value(
			"Electronic Payment Profile",
			{"payment_profile_id": payment_profile_id},
			["name", "party"],
		)
		pmm_name = frappe.get_value("Portal Payment Method", {"electronic_payment_profile": epp_name})

		frappe.delete_doc("Portal Payment Method", pmm_name, ignore_permissions=True)
		frappe.delete_doc("Electronic Payment Profile", epp_name, ignore_permissions=True)

		# Delete from API
		try:
			base_url, headers = self.get_base_url_and_header(company)
			headers["templateIdentification"] = payment_profile_id
			response = requests.delete(
				urljoin(base_url, "/cashpro/repetitive/v1/template"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			return {"message": "Success"}

		except HTTPError as e_http:
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error deleting payment profile for {party}",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error deleting payment profile for {party}",
			)
			return {"error": f"{e}"}

	def charge_party_profile(self, doc, data):
		return {"error": _("Not supported")}

	def create_transfer_to_party_profile(self, doc, data):
		party = get_party_details(doc)
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
			customer_txn_id_uuid = str(uuid.uuid4())  # TODO: save to doc if transfer fails?

			# ACH
			payment_data = {
				"paymentIdentification": {
					"instructionIdentification": "USACHTest1",
					"endToEndIdentification": "USACHTest1",
				},
				"paymentMethod": "TRF",  # CHK
				"requestedExecutionDate": nowdate(),  # optional: If not provided, the “Value Date Rollover” setting in CashPro Payments applies
				"amount": {"value": str(total_to_pay)},
				"debtor": {
					"name": data.get(),
					"identifiers": [{"identification": "1234567890", "schemeName": "ACHCOMPANYID"}],
				},
				"debtorAccount": {"identification": "1234567890", "currency": "USD"},
				"debtorAgent": {
					"institution": {
						"name": "Bank of America",
						"identification": "987654321",
						"postalAddress": {"country": "US"},
					}
				},
				"creditor": {
					"name": data.get("account_holders_name"),
					"postalAddress": {
						"addressLine": [data.get("address_firstline"), data.get("address_secondline")],
						"postalCode": data.get("postcode"),
						"city": data.get("city"),
						"countrySubDivision": data.get("state"),
						"country": data.get("country"),
					},
				},
				"creditorAccount": {"identification": data.get("account_number"), "currency": "USD"},
				"creditorAgent": {
					"institution": {
						"identification": data.get("routing_number"),
						"postalAddress": {"country": "US"},
					}
				},
				"paymentType": {
					"serviceLevel": "NURG",
					"localInstrument": "CCD",  # PPD
					"categoryOfPurpose": "PAYMENT",
				},
				# "unstructuredRemittance": "Unstructured Remittance"
			}

			# US Domestic Wire
			payment_data = {
				"paymentIdentification": {"endToEndIdentification": "USFEDWIRETest1"},
				"paymentMethod": "TRF",
				"requestedExecutionDate": nowdate(),
				"amount": {"value": str(total_to_pay)},
				"debtor": {"name": "Debtor Name"},
				"debtorAccount": {"identification": "1234567890", "currency": "USD"},
				"debtorAgent": {
					"institution": {"identification": "987654321", "postalAddress": {"country": "US"}}
				},
				"creditor": {
					"name": data.get("account_holders_name"),
					"postalAddress": {
						"addressLine": [data.get("address_firstline"), data.get("address_secondline")],
						"postalCode": data.get("postcode"),
						"city": data.get("city"),
						"countrySubDivision": data.get("state"),
						"country": data.get("country"),
					},
				},
				"creditorAccount": {"identification": data.get("account_number"), "currency": "USD"},
				"creditorAgent": {
					"institution": {
						"name": "CreditorAgentName",
						"identification": data.get("routing_number"),
						"postalAddress": {"country": "US"},
					}
				},
				"paymentType": {"serviceLevel": "URGP"},
				"unstructuredRemittance": "Unstructured Remittance",
			}

			response = requests.post(
				urljoin(base_url, "/cashpro/payments/v2/payment-initiations"),
				headers=headers,
				timeout=10,
				data=json.dumps(payment_data),
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
					frappe.get_doc(
						"Electronic Payment Profile",
						{"party": party.name, "payment_profile_id": payment_profile_id},
					).delete()

					try:
						headers["templateIdentification"] = payment_profile_id
						del_response = requests.delete(
							urljoin(base_url, "/cashpro/repetitive/v1/template"),
							headers=headers,
							timeout=10,
						)
						del_response.raise_for_status()

					# If deletion on API-side fails, log error but continue processing
					except HTTPError as e_http:
						err_msg = " ".join([err.get("message") for err in del_response.json().get("errors", [])])
						frappe.log_error(
							message=f"{del_response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
							title=f"Error deleting payment profile used for {doc.name}",
						)

					except requests.exceptions.RequestException as e:
						frappe.log_error(
							message=f"{e}\n\n{frappe.get_traceback()}",
							title=f"Request error deleting payment profile used for {doc.name}",
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
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title="Error creating Transfer.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}", title="Request error creating Transfer."
			)
			return {"error": f"{e}"}


def fetch_cashpro_transactions(settings):
	# TODO
	settings = frappe._dict(json.loads(settings)) if isinstance(settings, str) else settings
	return []
