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


class Wise:
	def get_base_url_and_header(self, company):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": company})
		if not settings:
			frappe.msgprint(_(f"No Electronic Payment Settings found for {company}"))
		else:
			api_key_field = "api_key" if settings.provider == "Wise" else "sending_api_key"
			endpoint_field = "endpoint" if settings.provider == "Wise" else "sending_endpoint"
			api_key = get_decrypted_password(
				settings.doctype, settings.name, api_key_field, raise_exception=False
			)
			base_url = settings.get(endpoint_field)
			headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
			return base_url, headers

	def process_transaction(self, doc, data):
		mop = data.mode_of_payment.replace("New ", "")
		party = get_party_details(doc)
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
		use_batch = settings.sending_provider == "Wise" and settings.wise_linked_bank_account_id

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

		quote_response = self.create_quote(doc, data)
		if quote_response.get("message") == "Success":
			# TODO: serialize and save payment options from quote response?
			data.update(
				{"quote_id": quote_response["quote_id"], "target_amount": quote_response["target_amount"]}
			)
			if not use_batch:
				response = self.create_transfer_to_party_profile(doc, data)
			else:
				batch_response = self.create_batch_group(doc, data)
				if batch_response.get("message") == "Success":
					data.update({"batch_id": batch_response["transaction_id"]})
					batch_txfr_response = self.create_batch_group_transfer(doc, data)
					if batch_txfr_response.get("message") == "Success":
						comp_response = self.complete_batch_group(doc, data)
						if comp_response.get("message") == "Success":
							data.update({"total_amount": comp_response["total_amount"]})
							response = self.fund_batch_group_with_direct_debit(doc, data)
						else:  # error completing the batch group
							return comp_response
					else:  # error creating batch group transfer
						return batch_txfr_response
				else:  # error creating a batch group
					return batch_response
		else:  # error requesting quote
			return quote_response

		return response

	def process_credit_card(self, doc, data):
		"""
		Currently unsupported - replace with code to generate a Wise payment request link
		"""
		return {"error": _("Not supported")}

	def get_profiles(self, company):
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.get(
				urljoin(base_url, "/v2/profiles"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()
			if r:
				profile_data = []
				for profile in r:
					p_type = profile["type"].lower()
					name = profile["businessName"] if p_type == "business" else profile["fullName"]
					profile_data.append(f"{p_type.title()} Account for {name} has ID: {profile['id']}")

				return {"message": "Success", "data": profile_data}

		except HTTPError as e_http:
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title="Error requesting a list of profiles associated with this Wise account.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title="Error requesting a list of profiles associated with this Wise account.",
			)
			return {"error": f"{e}"}

	def create_quote(self, doc, data):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
		merch_id_field = "ref_id" if settings.provider == "Wise" else "sending_ref_id"
		profile_id = settings.get(merch_id_field)

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
			response = requests.post(
				urljoin(base_url, f"/v3/profiles/{profile_id}/quotes"),
				headers=headers,
				timeout=10,
				data=json.dumps(
					{
						"sourceCurrency": frappe.defaults.get_global_default("currency"),
						"targetCurrency": doc.currency,
						"sourceAmount": None,
						"targetAmount": total_to_charge,
						"payOut": "BANK_TRANSFER",
						"preferredPayIn": "BANK_TRANSFER",  # TODO: give user choice? BALANCE if funding via multi-currency balance
						"targetAccount": data.get("payment_profile_id"),
						"pricingConfiguration": {},  # required when configured in client ID
					}
				),
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				return {
					"message": "Success",
					"quote_id": r["id"],
					"target_amount": total_to_charge,
					"quotes": r.get("paymentOptions"),
				}
			else:
				return {"error": "No quote payment options found."}

		except HTTPError as e_http:
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title="Error trying to create a Quote.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title="Request error while trying to create a Quote.",
			)
			return {"error": f"{e}"}

	def edit_customer_payment_profile(self, company, electronic_payment_profile_name, data):
		# Per docs, can't edit an existing recipient account - must delete, then re-add
		return {
			"error": _(
				"Wise does not support editing payment methods. Please delete the payment method then re-create it."
			)
		}

	def get_customer_payment_profile(self, company, electronic_payment_profile_name):
		party, payment_profile_id = frappe.get_value(
			"Electronic Payment Profile",
			{"name": electronic_payment_profile_name},
			["party", "payment_profile_id"],
		)
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.get(
				urljoin(base_url, f"/v2/accounts/{payment_profile_id}"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				return {
					"message": "Success",
					"data": {
						"first_name": r.get("name", {}).get("givenName"),
						"last_name": r.get("name", {}).get("familyName"),
						"account_type": r.get("details", {}).get("accountType", "").title(),
						"routing_number": str(r.get("details", {}).get("abartn", "")),
						"account_number": str(r.get("details", {}).get("accountNumber", "")),
						"name_on_account": r.get("name", {}).get("fullName"),
						"echeck_type": None,
					},
				}

		except HTTPError as e_http:
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
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
		merch_id_field = "ref_id" if settings.provider == "Wise" else "sending_ref_id"
		mop_field = "mode_of_payment" if settings.provider == "Wise" else "sending_mode_of_payment"
		profile_id = settings.get(merch_id_field)
		mop = data.mode_of_payment.replace("New ", "")

		try:
			if mop != "ACH":
				return {"error": _("Mode of Payment not supported")}

			# Wire Transfers have same required fields
			account_number = str(data.get("account_number"))
			last4 = account_number[-4:]
			address_sl = data.get("address_secondline", "")
			recipient_data = {
				"accountHolderName": data.get("account_holders_name"),
				"currency": doc.get("currency", "USD").upper(),
				"type": "ABA",
				"profile": int(profile_id),
				"ownedByCustomer": False,
				"details": {
					"address": {
						"firstLine": data.get("address_firstline", "") + (f" {address_sl}" if address_sl else ""),
						"city": data.get("city"),
						"state": data.get("state"),
						"postCode": data.get("postcode"),
						"countryCode": data.get("country", "US").upper(),
					},
					"legalType": "BUSINESS",
					"abartn": str(data.get("routing_number")),
					"accountNumber": account_number,
					"accountType": "CHECKING",
				},
			}
			base_url, headers = self.get_base_url_and_header(doc.company)
			response = requests.post(
				urljoin(base_url, "/v1/accounts"), headers=headers, timeout=10, data=json.dumps(recipient_data)
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				payment_profile = frappe.new_doc("Electronic Payment Profile")
				payment_profile.party_type = party.doctype
				payment_profile.party = party.name
				payment_profile.payment_type = mop
				payment_profile.payment_gateway = "Wise"
				payment_profile.reference = f"*{last4}"
				payment_profile.payment_profile_id = str(r.get("id"))
				payment_profile.party_profile = None  # Not used in Wise
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

		except HTTPError as e_http:
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title="Error trying to create a Recipient Account.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title="Request error while trying to create a Recipient Account.",
			)
			return {"error": f"{e}"}

	def charge_party_profile(self, doc, data):
		return {"error": _("Not supported")}

	def create_batch_group(self, doc, data):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
		merch_id_field = "ref_id" if settings.provider == "Wise" else "sending_ref_id"
		profile_id = settings.get(merch_id_field)
		pmt_term = f"|{data.get('payment_term')}" if data.get("payment_term") else ""
		batch_name = f"{doc.name}{pmt_term}"
		try:
			base_url, headers = self.get_base_url_and_header(doc.company)
			response = requests.post(
				urljoin(base_url, f"/v3/profiles/{profile_id}/batch-groups"),
				headers=headers,
				timeout=10,
				data=json.dumps(
					{
						"sourceCurrency": frappe.defaults.get_global_default("currency"),
						"name": batch_name,
					}
				),
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				return {"message": "Success", "transaction_id": r["id"]}

		except HTTPError as e_http:
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error creating a batch group to create a transfer for {doc.name}.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error creating a batch group to create a transfer for {doc.name}.",
			)
			return {"error": f"{e}"}

	def create_batch_group_transfer(self, doc, data):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
		merch_id_field = "ref_id" if settings.provider == "Wise" else "sending_ref_id"
		profile_id = settings.get(merch_id_field)
		payment_profile_id = data.get("payment_profile_id")
		batch_id = data.get("batch_id")
		quote_id = data.get("quote_id")
		try:
			base_url, headers = self.get_base_url_and_header(doc.company)
			customer_txn_id_uuid = str(uuid.uuid4())  # TODO: save to doc if transfer fails?
			response = requests.post(
				urljoin(base_url, f"/v3/profiles/{profile_id}/batch-groups/{batch_id}/transfers"),
				headers=headers,
				timeout=10,
				data=json.dumps(
					{
						"sourceAccount": "",  # TODO: (refund recipient account ID) field in settings?
						"targetAccount": payment_profile_id,
						"quoteUuid": quote_id,
						"customerTransactionId": customer_txn_id_uuid,
						"details": {
							"reference": doc.name[-10:],
							"transferPurpose": "verification.transfers.purpose.pay.bills",
						},
					}
				),
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				return {"message": "Success", "transaction_id": r["id"]}

		except HTTPError as e_http:
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error creating a batch group transfer for {doc.name}.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error creating a batch group transfer for {doc.name}.",
			)
			return {"error": f"{e}"}

	def complete_batch_group(self, doc, data):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
		merch_id_field = "ref_id" if settings.provider == "Wise" else "sending_ref_id"
		profile_id = settings.get(merch_id_field)
		batch_id = data.get("batch_id")
		try:
			base_url, headers = self.get_base_url_and_header(doc.company)
			# Get batch version number
			response = requests.get(urljoin(base_url, f"v3/profiles/{profile_id}/batch-groups/{batch_id}"))
			response.raise_for_status()
			r = response.json()
			if r.get("version"):
				batch_version = r["version"]
			else:
				return {"error": "Failed to get batch version number trying to complete batch."}

			try:
				comp_response = requests.patch(
					urljoin(base_url, f"/v3/profiles/{profile_id}/batch-groups/{batch_id}"),
					headers=headers,
					timeout=10,
					data=json.dumps(
						{
							"status": "COMPLETED",
							"version": batch_version,
						}
					),
				)
				comp_response.raise_for_status()
				cr = comp_response.json()
				if cr.get("id"):
					return {
						"message": "Success",
						"transaction_id": cr["id"],
						"total_amount": cr["payInDetails"][0]["amount"],
					}

			except HTTPError as e_http:
				err_msg = " ".join([err.get("message") for err in comp_response.json().get("errors", [])])
				frappe.log_error(
					message=f"{comp_response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
					title=f"Error completing batch group for transfer to {doc.name}.",
				)
				return {"error": f"{err_msg}"}

			except requests.exceptions.RequestException as e:
				frappe.log_error(
					message=f"{e}\n\n{frappe.get_traceback()}",
					title=f"Request error completing batch group for transfer to {doc.name}.",
				)
				return {"error": f"{e}"}

		except HTTPError as e_http:
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error collecting batch group version for transfer to {doc.name}.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error collecting batch group version for transfer to {doc.name}.",
			)
			return {"error": f"{e}"}

	def fund_batch_group_with_direct_debit(self, doc, data):
		party = get_party_details(doc)
		payment_profile_id = data.get("payment_profile_id")
		settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
		merch_id_field = "ref_id" if settings.provider == "Wise" else "sending_ref_id"
		profile_id = settings.get(merch_id_field)
		batch_id = data.get("batch_id")
		account_id = settings.wise_linked_bank_account_id
		fees = flt(
			data["total_amount"] - data["target_amount"],
			frappe.get_precision(doc.doctype, "grand_total"),
		)
		data.update({"additional_charges": fees})

		try:
			base_url, headers = self.get_base_url_and_header(doc.company)
			response = requests.post(
				urljoin(base_url, f"/v1/profiles/{profile_id}/batch-groups/{batch_id}/payment-initiations"),
				headers=headers,
				timeout=10,
				data=json.dumps(
					{
						"type": "DIRECT_DEBIT",
						"accountId": account_id,
					}
				),
			)
			response.raise_for_status()
			r = response.json()
			if r:
				transaction_id = str(batch_id)
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
						del_response = requests.delete(
							urljoin(base_url, f"/v2/accounts/{payment_profile_id}"),
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
			try:
				resp_error = response.json()
				err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			except requests.exceptions.JSONDecodeError as e_json:
				resp_error = e_http
				err_msg = e_http
			frappe.log_error(
				message=f"{resp_error}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title="Error funding batch group transfer with a direct debit account.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title="Error funding batch group transfer with a direct debit account.",
			)
			return {"error": f"{e}"}

	def create_transfer_to_party_profile(self, doc, data):
		party = get_party_details(doc)
		payment_profile_id = data.get("payment_profile_id")
		quote_id = data.get("quote_id")
		try:
			base_url, headers = self.get_base_url_and_header(doc.company)
			customer_txn_id_uuid = str(uuid.uuid4())  # TODO: save to doc if transfer fails?
			response = requests.post(
				urljoin(base_url, "/v1/transfers"),  # assumes regular transfer
				headers=headers,
				timeout=10,
				data=json.dumps(
					{
						"targetAccount": payment_profile_id,
						"quoteUuid": quote_id,
						"customerTransactionId": customer_txn_id_uuid,
						"details": {
							"reference": doc.name[-10:],
							"transferPurpose": "verification.transfers.purpose.pay.bills",
						},
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
					frappe.get_doc(
						"Electronic Payment Profile",
						{"party": party.name, "payment_profile_id": payment_profile_id},
					).delete()

					try:
						del_response = requests.delete(
							urljoin(base_url, f"/v2/accounts/{payment_profile_id}"),
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
		# Cancels a transfer
		orig_transaction_id = doc.electronic_payment_reference
		try:
			base_url, headers = self.get_base_url_and_header(doc.company)
			response = requests.put(
				urljoin(base_url, f"/v1/transfers/{orig_transaction_id}/cancel"),
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
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error canceling transfer related to {doc.name}",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error canceling transfer related to {doc.name}",
			)
			return {"error": f"{e}"}

	def get_transaction_details(self, company, transaction_id):
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.get(
				urljoin(base_url, f"/v1/transfers/{transaction_id}"),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()
			if r.get("targetAccount"):
				account_id = r["targetAccount"]
				try:
					acct_response = requests.get(
						urljoin(base_url, f"/v2/accounts/{account_id}"),
						headers=headers,
						timeout=10,
					)
					acct_response.raise_for_status()
					ar = acct_response.json()
					if ar.get("id"):
						payment_dict = frappe._dict(
							{
								"type": "bankAccount",
								"accountType": ar.get("details", {}).get("accountType", "").title(),
								"routingNumber": str(ar.get("details", {}).get("abartn", "")),
								"accountNumber": str(ar.get("details", {}).get("accountNumber", "")),
								"nameOnAccount": ar.get("name", {}).get("fullName"),
							}
						)
						return {"message": "Success", "payment_details": payment_dict}

				except HTTPError as e_http:
					err_msg = " ".join([err.get("message") for err in acct_response.json().get("errors", [])])
					frappe.log_error(
						message=f"{acct_response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
						title=f"Error collecting transfer details for {transaction_id}",
					)
					return {"error": f"{err_msg}"}

				except requests.exceptions.RequestException as e:
					frappe.log_error(
						message=f"{e}\n\n{frappe.get_traceback()}",
						title=f"Request error collecting transfer details for {transaction_id}",
					)
					return {"error": f"{e}"}

		except HTTPError as e_http:
			err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			frappe.log_error(
				message=f"{response.json()}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error collecting transfer details for {transaction_id.name}",
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
			response = requests.delete(
				urljoin(base_url, f"/v2/accounts/{payment_profile_id}"),
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

	def delete_customer_profile(self, company, customer):
		# Not used in Wise
		frappe.set_value("Customer", customer, "electronic_payment_profile", "")
		return {"message": "Success"}

	def create_direct_debit_account(self, company, data):
		"""
		:param company: the company to collect Electronic Payment Settings for
		:param data: dict, should contain keys for "account_currency" (should be "USD"),
		"routing_number", "account_number", and "account_type" (either "Checking" or "Savings")
		"""
		settings = frappe.get_doc("Electronic Payment Settings", {"company": company})
		profile_id = settings.sending_ref_id
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.post(
				urljoin(base_url, f"/v1/profiles/{profile_id}/direct-debit-accounts"),
				headers=headers,
				timeout=10,
				data=json.dumps(
					{
						"currency": data.get("account_currency"),
						"type": "ACH",
						"details": {
							"routingNumber": str(data.get("routing_number")),
							"accountNumber": str(data.get("account_number")),
							"accountType": data.get("account_type").upper(),
						},
					}
				),
			)
			response.raise_for_status()
			r = response.json()
			if r.get("id"):
				return {"message": "Success", "transaction_id": r["id"]}

		except HTTPError as e_http:
			try:
				resp_error = response.json()
				err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			except requests.exceptions.JSONDecodeError as e_json:
				resp_error = e_http
				err_msg = e_http

			frappe.log_error(
				message=f"{resp_error}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error creating a direct debit account associated with profile ID {profile_id}.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Request error creating a direct debit account associated with profile ID {profile_id}.",
			)
			return {"error": f"{e}"}

	def get_direct_debit_accounts(self, company):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": company})
		profile_id = settings.sending_ref_id
		account_type = settings.wise_bank_account_type.upper()
		account_currency = settings.wise_bank_account_currency
		try:
			base_url, headers = self.get_base_url_and_header(company)
			response = requests.get(
				urljoin(
					base_url,
					f"/v1/profiles/{profile_id}/direct-debit-accounts?type={account_type}&currency={account_currency}",
				),
				headers=headers,
				timeout=10,
			)
			response.raise_for_status()
			r = response.json()
			if r:
				account_data = []
				print(r)
				for account in r:
					a_type = account["type"]
					last_4 = account.get("details", {}).get("accountNumber", "")[-4:]
					account_data.append(f"{a_type} Account ending in {last_4} has ID: {account['id']}")

				return {"message": "Success", "data": account_data}

		except HTTPError as e_http:
			try:
				resp_error = response.json()
				err_msg = " ".join([err.get("message") for err in response.json().get("errors", [])])
			except requests.exceptions.JSONDecodeError as e_json:
				resp_error = e_http
				err_msg = e_http

			frappe.log_error(
				message=f"{resp_error}\n\n{e_http}\n\n{frappe.get_traceback()}",
				title=f"Error requesting a list of direct debit accounts associated with profile ID {profile_id}.",
			)
			return {"error": f"{err_msg}"}

		except requests.exceptions.RequestException as e:
			frappe.log_error(
				message=f"{e}\n\n{frappe.get_traceback()}",
				title=f"Error requesting a list of direct debit accounts associated with profile ID {profile_id}.",
			)
			return {"error": f"{e}"}


def fetch_wise_transactions(settings):
	# TODO
	settings = frappe._dict(json.loads(settings)) if isinstance(settings, str) else settings
	return []
