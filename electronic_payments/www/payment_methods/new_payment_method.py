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
from electronic_payments.www.payment_methods.index import get_party

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

	if party_data["party_type"] == "Customer":
		filters = {"enable_accepting": 1}
	elif party_data["party_type"] == "Supplier":
		filters = {"enable_sending": 1}

	all_settings = frappe.get_all("Electronic Payment Settings", filters)
	if not all_settings:
		return {"error_message": _("You cannot add a new Payment Method.")}
	error_messages = []

	for setting_name in all_settings:
		settings = frappe.get_doc("Electronic Payment Settings", setting_name)
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
		provider_field = "sending_provider" if doc.get("supplier") else "provider"
		provider = settings.get(provider_field)

		if provider == "Stripe" and data.mode_of_payment == "ACH":
			continue

		if provider not in ["Mercury", "Wise"]:
			# Authorize and Stripe use party profiles
			response = client.create_party_profile(doc)
			if response.get("error"):
				error_messages.append(response["error"])
				continue

			data["party_profile_id"] = response.get("transaction_id")
		response = client.create_party_payment_profile(doc, data)

		if response.get("error"):
			error_messages.append(response["error"])
			continue


	if error_messages:
		return {"error_message": " ".join(error_messages)}
	else:
		return {"success_message": _("Your Payment Method has been created successfully")}
