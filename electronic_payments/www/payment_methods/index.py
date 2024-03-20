import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import get_contact_name
from erpnext import get_default_company

no_cache = 1


def get_context(context):
	context.add_breadcrumbs = 1
	context.portal_payment_methods = get_portal_payment_methods()


def get_portal_payment_methods():
	party_data = get_party()
	party = party_data["party"]
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
	settings = get_electronic_payment_settings()

	if not settings:
		return {"error_message": _("Your Payment Method cannot be deleted.")}

	try:
		electronic_payment_profile = frappe.db.get_value(
			"Portal Payment Method", payment_method, "electronic_payment_profile"
		)
		payment_profile_id = frappe.db.get_value(
			"Electronic Payment Profile", electronic_payment_profile, "payment_profile_id"
		)
		client = settings.client()
		response = client.delete_payment_profile(get_default_company(), payment_profile_id)

		if response.get("message") and response.get("message") == "Success":
			return {"success_message": _("Your Payment Method has been removed successfully.")}
		return {"error_message": _("Your Payment Method cannot be deleted.")}
	except Exception as e:
		return {"error_message": str(e)}


def get_electronic_payment_settings():
	company = get_default_company()

	if frappe.db.exists("Electronic Payment Settings", {"company": company}):
		return frappe.get_doc("Electronic Payment Settings", {"company": company})
	return None


def get_party():
	user = frappe.session.user
	contact_name = get_contact_name(user)
	party = None
	party_type = None

	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		for link in contact.links:
			if link.link_doctype == "Customer":
				party = link.link_name
				party_type = link.link_doctype
				break

			if link.link_doctype == "Supplier":
				party = link.link_name
				party_type = link.link_doctype
				break

	if not party:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	return {"party": party, "party_type": party_type}
