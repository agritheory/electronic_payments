# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	state_label_lookup,
)
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.electronic_payment_settings import (
	get_billing_address,
)
from electronic_payments.www.payment_methods.index import (
	get_electronic_payment_settings,
	get_party,
	get_provider,
)

no_cache = 1


def get_context(context):
	party_data = get_party()
	context.party = party_data["party"]
	context.party_type = party_data["party_type"]
	context.add_breadcrumbs = 1

	doc = frappe._dict(
		{
			"doctype": "Purchase" if party_data["party_type"] == "Supplier" else "Sales",
			party_data["party_type"].lower(): party_data["party"],
		}
	)
	billing_address = get_billing_address(doc)
	context.address_firstline = billing_address.get("address_line1", "")
	context.address_secondline = billing_address.get("address_line2", "")
	context.city = billing_address.get("city", "")
	context.state = billing_address.get("state", "")
	context.state_label = state_label_lookup(billing_address.get("state", ""))
	context.postcode = billing_address.get("pincode", "")
	context.email = frappe.session.user


@frappe.whitelist()
def new_portal_payment_method(payment_method):
	party_data = get_party()
	data = frappe._dict(json.loads(payment_method))

	settings = get_electronic_payment_settings(party_data["company"])
	provider = get_provider()

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
	data.save_data = "Retain payment data for this party and process"

	try:
		if provider not in ["Mercury", "Wise"]:
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
