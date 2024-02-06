import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import get_contact_name

no_cache = 1


def get_context(context):
	context.add_breadcrumbs = 1
	context.portal_payment_methods = get_portal_payment_methods()


def get_portal_payment_methods():
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

	portal_payment_methods = []
	portal_payment_method_names = frappe.get_all(
		"Portal Payment Method", {"parent": party}, pluck="name"
	)

	if not portal_payment_method_names:
		return portal_payment_methods

	for ppm in portal_payment_method_names:
		portal_payment_method = frappe.get_doc("Portal Payment Method", ppm)
		electronic_payment_profile = frappe.get_doc(
			"Electronic Payment Profile", portal_payment_method.electronic_payment_profile
		)
		portal_payment_method.electronic_payment_profile_object = electronic_payment_profile
		portal_payment_methods.append(portal_payment_method)
	return portal_payment_methods


@frappe.whitelist()
def remove_portal_payment_method(payment_method):
	try:
		ppm = frappe.get_doc("Portal Payment Method", payment_method)
		ppm.delete(ignore_permissions=True)
		return {"success_message": "Your Payment Method has been removed successfully"}
	except Exception as e:
		return {"error_message": str(e)}
