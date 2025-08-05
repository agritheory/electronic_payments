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
			api_key_field = "api_key" if settings.provider == "CashPro" else "sending_api_key"
			endpoint_field = "endpoint" if settings.provider == "CashPro" else "sending_endpoint"
			api_key = get_decrypted_password(
				settings.doctype, settings.name, api_key_field, raise_exception=False
			)
			base_url = settings.get(endpoint_field)
			headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
			return base_url, headers