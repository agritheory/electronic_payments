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
	context.add_breadcrumbs = 1
	name = frappe.local.request.args.get("name")
	party_data = get_party()
	party = party_data["party"]

	try:
		portal_payment_method = frappe.get_doc("Portal Payment Method", {"name": name, "parent": party})
		electronic_payment_profile = frappe.get_doc(
			"Electronic Payment Profile", portal_payment_method.electronic_payment_profile
		)
		portal_payment_method.electronic_payment_profile_object = electronic_payment_profile
		settings = get_electronic_payment_settings(company=electronic_payment_profile.company)
		if not settings:
			return {"error_message": _("You cannot edit this Payment Method.")}

		doc = frappe._dict({party_data["party_type"].lower(): party})
		client = settings.client(doc)
		response = client.get_party_payment_profile(settings.company, electronic_payment_profile.name)
		if response.get("message") and response["message"] == "Success":
			data = response["data"]
			for field in [
				"email",
				"address_firstline",
				"address_secondline",
				"city",
				"state",
				"state_label",
				"postcode",
				"country",
			]:
				if not data.get(field):
					data.update({field: ""})
			portal_payment_method.update(data)

		context.portal_payment_method = portal_payment_method

	except frappe.exceptions.DoesNotExistError:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def edit_portal_payment_method(payment_method):
	data = json.loads(payment_method)
	party_data = get_party()

	portal_payment_method = frappe.get_doc("Portal Payment Method", data["name"])
	company = frappe.db.get_value(
		"Electronic Payment Profile", portal_payment_method.electronic_payment_profile, "company"
	)
	settings = get_electronic_payment_settings(company=company)

	if not settings:
		return {"error_message": _("You cannot edit this Payment Method.")}

	try:
		doc = frappe._dict({party_data["party_type"].lower(): party_data["party"]})
		client = settings.client(doc)
		response = client.edit_customer_payment_profile(
			settings.company, portal_payment_method.electronic_payment_profile, data
		)
		if response.get("error"):
			return {"error_message": response["error"]}
		return {"success_message": _("Your Payment Method has been updated successfully")}
	except Exception as e:
		return {"error_message": str(e)}
