import frappe
import json


def after_install():
	move_app_after_erpnext_and_webshop_in_installed_app_global_list
	create_default_payment_term_template()


def move_app_after_erpnext_and_webshop_in_installed_app_global_list():
	"""
	For the app's template Order page changes to render, it must come after both ERPNext and
	Webshop in Installed Applications, which should happen since they're required in hooks.py.
	This function ensures the proper ordering for the Order page to render.
	"""
	installed_apps = frappe.get_installed_apps()
	app_name = "electronic_payments"
	erpnext_idx = installed_apps.index("erpnext") if "erpnext" in installed_apps else 100
	webshop_idx = installed_apps.index("webshop") if "webshop" in installed_apps else 100
	elec_pmts_idx = installed_apps.index(app_name)

	if elec_pmts_idx > erpnext_idx and elec_pmts_idx > webshop_idx:
		return
	else:  # Move to end of installed apps
		installed_apps.remove(app_name)
		installed_apps.append(app_name)
		frappe.db.set_global("installed_apps", json.dumps(installed_apps))


def create_default_payment_term_template():
	"""
	If not specified in Company Settings, creates and adds a default Payment Term Template that's
	used in Orders/Invoices when there isn't one tied to the party or set by the user. This avoids
	the default ERPNext behavior, which creates a payment schedule term without a name. The name
	field is how to link to the term in a Payment Entry, so there would be no way to keep the
	Payment Schedule up-to-date for payments in that situation.
	"""
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
