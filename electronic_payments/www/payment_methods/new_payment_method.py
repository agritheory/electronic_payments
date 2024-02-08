import json
import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import get_contact_name
from erpnext import get_default_company
from electronic_payments.www.payment_methods.index import get_electronic_payment_settings

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
