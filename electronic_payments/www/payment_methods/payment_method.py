import json
import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import get_contact_name

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
		context.ppm = frappe.get_doc("Portal Payment Method", {"name": name, "parent": party})
	except frappe.exceptions.DoesNotExistError:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def edit_portal_payment_method(payment_method):
	data = json.loads(payment_method)
	portal_payment_method = frappe.get_doc("Portal Payment Method", data["name"])
	portal_payment_method.service_charge = True if data.get("service_charge") == "on" else False
	portal_payment_method.default = (
		True if data.get("default") == "on" else False
	)  # TODO: prevent multiple defaults?
	portal_payment_method.percentage_or_rate = data.get("percentage_or_rate")
	portal_payment_method.percentage = data.get("percentage")
	portal_payment_method.rate = data.get("rate")

	try:
		portal_payment_method.save(ignore_permissions=True)
		return {"success_message": "Your Payment Method has been updated successfully"}
	except Exception as e:
		return {"error_message": str(e)}
