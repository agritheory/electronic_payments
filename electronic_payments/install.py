import frappe
import json


def after_install():
	move_app_to_beginning_of_installed_app_global_list()
	create_default_payment_term_template()


def move_app_to_beginning_of_installed_app_global_list():
	"""
	Moving electronic_payments before erpnext and setting frappe.local.flags.web_pages_apps flag
	in hooks.py ensures that the website reflects this app's changes to the orders template
	override and frappe finds all files associated with it (.html/.md, .js, and .py).
	Frappe traversed the installed app list in opposite directions when looking for jinga template
	pages (reversed order, but checks for the flag) vs when looking for the path to get_context
	(regular order). Setting the flag to the apps list in reversed order (which is then reversed
	back to original
	state)
	"""
	installed_apps = frappe.get_installed_apps()
	app_name = "electronic_payments"
	if app_name in installed_apps:
		installed_apps.remove(app_name)

	installed_apps.insert(0, app_name)
	frappe.db.set_global("installed_apps", json.dumps(installed_apps))
	frappe.db.commit()


def create_default_payment_term_template():
	# Check for a default payment terms template for All Customer Groups and All Supplier Groups
	if not frappe.db.exists("Customer Group", "All Customer Groups") or not frappe.db.exists(
		"Supplier Group", "All Supplier Groups"
	):
		print("Returning")
		return
	cg_has_pmt_term_template = bool(
		frappe.get_value("Customer Group", "All Customer Groups", "payment_terms")
	)
	sg_has_pmt_term_template = bool(
		frappe.get_value("Supplier Group", "All Supplier Groups", "payment_terms")
	)

	if cg_has_pmt_term_template and sg_has_pmt_term_template:
		return

	# One or both groups lack a default payment terms template - create one and link to it
	template_name = "Default Due on Demand"
	term_name = "Due on Demand"

	# find unique names for the template and payment term
	count = 2
	while frappe.db.exists("Payment Terms Template", template_name):
		template_name = template_name[:21] + f" {count}"
		count += 1
	count = 2
	while frappe.db.exists("Payment Term", term_name):
		term_name = term_name[:13] + f" {count}"
		count += 1

	doc = frappe.new_doc("Payment Terms Template")
	doc.template_name = template_name
	pt = frappe.new_doc("Payment Term")
	pt.payment_term_name = term_name
	pt.invoice_portion = 100
	pt.due_date_based_on = "Day(s) after invoice date"
	pt.credit_days = 0
	pt.save()
	doc.append(
		"terms",
		{"payment_term": pt.name},
	)
	doc.save()

	if not cg_has_pmt_term_template:
		frappe.db.set_value("Customer Group", "All Customer Groups", "payment_terms", doc.name)

	if not sg_has_pmt_term_template:
		frappe.db.set_value("Supplier Group", "All Supplier Groups", "payment_terms", doc.name)

	frappe.db.commit()
