import frappe
import json


def after_install():
	move_app_to_beginning_of_installed_app_global_list()
	create_default_payment_term_template()


def move_app_to_beginning_of_installed_app_global_list():
	"""
	Moving electronic_payments before erpnext and setting frappe.local.flags.web_pages_apps flag
	ensures that the website reflects this app's changes to the orders template and frappe finds
	all files associated with it (.html/.md, .js, and .py).
	Frappe traverses the installed app list in opposite directions when looking for jinga template
	pages (reversed order) vs when looking for the path to get_context (regular order). Since the
	jinga code first checks the frappe.local.flags.web_pages_apps, it's possible to set the flag
	to the reversed order as get_installed_apps, to ensure frappe uses a consistent order to find/
	load override files.
	"""
	installed_apps = frappe.get_installed_apps()
	app_name = "electronic_payments"
	if app_name in installed_apps:
		installed_apps.remove(app_name)

	installed_apps.insert(0, app_name)
	frappe.db.set_global("installed_apps", json.dumps(installed_apps))

	# Set the web_pages_apps flag to the reverse order
	frappe.local.flags.web_pages_apps = list(reversed(installed_apps))
	frappe.db.commit()


def create_default_payment_term_template():
	# Check for a default payment terms template for all Companies
	companies = frappe.get_all("Company", ["name", "payment_terms"])

	if all(company.payment_terms for company in companies):
		return

	# At least one Company lacks a default payment terms template - create one and link to it
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

	for company in companies:
		if not company.payment_terms:
			print("Setting pt for ", company.name)
			frappe.db.set_value("Company", company.name, "payment_terms", doc.name)

	frappe.db.commit()
