# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

import frappe


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(frappe._("You need to be logged in to access this page"), frappe.PermissionError)

	context.show_sidebar = True
