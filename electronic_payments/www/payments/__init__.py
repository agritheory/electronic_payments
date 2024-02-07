import frappe
from urllib.parse import urlencode


@frappe.whitelist()
def get_party_by_username():
	roles = frappe.get_roles(frappe.session.user)
	supplier_or_customer = None
	if "Customer" in roles:
		supplier_or_customer = ["Customer"]
	if "Supplier" in roles:
		supplier_or_customer = ["Supplier"]
	email_ids = frappe.get_all(
		"Contact Email", ["parent AS name"], {"email_id": frappe.session.user}, pluck="name"
	)
	if not email_ids:
		return
	doc = frappe.get_doc("Contact", email_ids[0])
	parties = [l.link_name for l in doc.links if l.link_doctype in supplier_or_customer]
	if not parties:
		return
	return {"party_type": supplier_or_customer[0], "party_name": parties[0]}


@frappe.whitelist()
def payment_options(*args, **kwargs):
	if "submit_doc" in kwargs:
		kwargs.pop("submit_doc")
	if "order_type" in kwargs:
		kwargs.pop("order_type")
	if "cmd" in kwargs:
		kwargs.pop("cmd")

	frappe.response["type"] = "redirect"
	frappe.response.location = f"/payments?dt={kwargs.get('dt')}&dn={kwargs.get('dn')}"
