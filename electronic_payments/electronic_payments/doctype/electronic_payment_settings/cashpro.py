# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password



class Wise:
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
			headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
			return base_url, headers
