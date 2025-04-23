# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _

from electronic_payments.www.payment_methods.index import (
	get_electronic_payment_settings,
	get_party,
)

no_cache = 1


def get_context(context):
	party_data = get_party()
	context.party = party_data["party"]
	context.party_type = party_data["party_type"]
	context.add_breadcrumbs = 1


@frappe.whitelist()
def new_portal_payment_method(payment_method):
	party_data = get_party()
	data = frappe._dict(json.loads(payment_method))

	settings = get_electronic_payment_settings()
	provider_field = "provider" if party_data["party_type"] == "Customer" else "sending_provider"
	provider = settings.get(provider_field)

	if not settings:
		return {"error_message": _("You cannot add a new Payment Method.")}

	doc = frappe._dict(
		{
			"company": settings.company,
			party_data["party_type"].lower(): data.party,
			"currency": data.get("account_currency", "USD").upper(),
		}
	)
	client = settings.client(doc)
	data.mode_of_payment = data.payment_type
	data.save_data = "Retain payment data for this party"

	try:
		if provider != "Wise":
			response = client.create_party_profile(doc)
			if response.get("error"):
				return {"error_message": response["error"]}

			data["party_profile_id"] = response.get("transaction_id")
		response = client.create_party_payment_profile(doc, data)

		if response.get("error"):
			return {"error_message": response["error"]}
		return {"success_message": _("Your Payment Method has been created successfully")}

	except Exception as e:
		return {"error_message": str(e)}
