import json
import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import get_contact_name
from erpnext import get_default_company
from electronic_payments.www.payment_methods.index import get_electronic_payment_settings

no_cache = 1


def get_context(context):
	context.add_breadcrumbs = 1
	name = frappe.local.request.args.get("name")
	user = frappe.session.user
	contact_name = get_contact_name(user)
	party = None

	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		for link in contact.links:
			if link.link_doctype == "Customer":
				party = link.link_name
				break

			if link.link_doctype == "Supplier":
				party = link.link_name
				break

	if not party:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

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
		response = client.get_customer_payment_profile(
			get_default_company(), electronic_payment_profile.name
		)
		if response["message"] == "Success":
			portal_payment_method.update(response["data"])

		context.portal_payment_method = portal_payment_method

	except frappe.exceptions.DoesNotExistError:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def edit_portal_payment_method(payment_method):
	data = json.loads(payment_method)
	portal_payment_method = frappe.get_doc("Portal Payment Method", data["name"])
	portal_payment_method.default = data.get("default")  # TODO: prevent multiple defaults?
	try:
		portal_payment_method.save(ignore_permissions=True)
		return {"success_message": "Your Payment Method has been updated successfully"}
	except Exception as e:
		return {"error_message": str(e)}
