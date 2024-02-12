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
		settings = get_electronic_payment_settings()

		if not settings:
			return {"error_message": _("You cannot edit this Payment Method.")}

		portal_payment_method = frappe.get_doc("Portal Payment Method", {"name": name, "parent": party})
		electronic_payment_profile = frappe.get_doc(
			"Electronic Payment Profile", portal_payment_method.electronic_payment_profile
		)
		portal_payment_method.electronic_payment_profile_object = electronic_payment_profile

		client = settings.client()
		response = client.get_customer_payment_profile(settings.company, electronic_payment_profile.name)
		if response["message"] == "Success":
			portal_payment_method.update(response["data"])

		context.portal_payment_method = portal_payment_method

	except frappe.exceptions.DoesNotExistError:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def edit_portal_payment_method(payment_method):
	data = json.loads(payment_method)
	settings = get_electronic_payment_settings()

	if not settings:
		return {"error_message": _("You cannot edit this Payment Method.")}

	portal_payment_method = frappe.get_doc("Portal Payment Method", data["name"])
	try:
		client = settings.client()
		response = client.edit_customer_payment_profile(
			settings.company, portal_payment_method.electronic_payment_profile, data
		)
		print(response)
		if response.get("error"):
			return {"error_message": response["error"]}
		return {"success_message": _("Your Payment Method has been updated successfully")}
	except Exception as e:
		return {"error_message": str(e)}
