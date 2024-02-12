import json
import frappe
from frappe import _
from erpnext import get_default_company
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
	data = frappe._dict(json.loads(payment_method))

	settings = get_electronic_payment_settings()

	if not settings:
		return {"error_message": _("You cannot add a new Payment Method.")}

	client = settings.client()
	doc = frappe._dict({"company": get_default_company(), "customer": data.party})
	data.mode_of_payment = data.payment_type
	data.save_data = "Retain payment data for this party"

	try:
		response = client.create_customer_payment_profile(doc, data)

		if response.get("error"):
			return {"error_message": response["error"]}
		return {"success_message": _("Your Payment Method has been created successfully")}
	except Exception as e:
		return {"error_message": str(e)}
