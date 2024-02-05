import json
import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import get_contact_name

no_cache = 1


def get_context(context):
	context.add_breadcrumbs = 1
	user = frappe.session.user
	contact_name = get_contact_name(user)
	party = None

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

	context.party = party
	context.party_type = party_type


@frappe.whitelist()
def new_portal_payment_method(payment_method):
	data = json.loads(payment_method)
	portal_payment_method = frappe.new_doc("Portal Payment Method")
	portal_payment_method.parent = data.get("party")
	portal_payment_method.parenttype = data.get("party_type")
	portal_payment_method.mode_of_payment = data.get("mode_of_payment")
	portal_payment_method.service_charge = data.get("service_charge")
	portal_payment_method.default = data.get("default") # TODO: prevent multiple defaults?
	portal_payment_method.percentage_or_rate = data.get("percentage_or_rate")
	portal_payment_method.percentage = data.get("percentage")
	portal_payment_method.rate = data.get("rate")
	portal_payment_method.label = data.get("label")
	try:
		portal_payment_method.insert(ignore_permissions=True)
		return {"success_message": "Your Payment Method has been created successfully"}
	except Exception as e:
		return {"error_message": str(e)}