# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt
import json

import frappe
import requests
from frappe import _
from frappe.utils.password import get_decrypted_password
from requests.exceptions import HTTPError


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
					f"{base_url}client-authentication",
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

			# Prepare headers
			headers = {
				"Authorization": f"Bearer {response.json()['access_token']}",
				"Content-Type": "application/json",
			}

			return base_url, headers
