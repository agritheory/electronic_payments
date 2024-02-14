import frappe
import json


def execute(company=None):
	move_app_to_beginning_of_installed_app_global_list()


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
