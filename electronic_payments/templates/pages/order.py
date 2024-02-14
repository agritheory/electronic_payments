# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils.data import fmt_money

from erpnext.templates.pages.order import get_context as get_erpnext_order_context


def get_context(context):
	"""
	Method is never found - in frappe/website/page_renderers/template_page.py, the TemplatePage
	class method set_method_path collects all apps, then loops over them looking for the first
	one with an order.html/order.md file. Once it's found, it saves the path into the class.
	Unfortunately, because ERPNext comes first in the results of the frappe.get_installed_apps
	call, the code finds the ERPNext version first. When the code looks for the get_context
	method (in set_pymodule), it uses the ERPNext path to order.py, so it never finds this file.
	"""
	get_erpnext_order_context(context)

	show_payment_terms = (
		context.doc.doctype in ["Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice"]
		and len(context.doc.payment_schedule) > 0  # has a payment schedule
	)
	context.show_payment_terms = show_payment_terms
	outstanding_amount = (
		context.doc.outstanding_amount
		if "Invoice" in context.doc.doctype
		else context.doc.grand_total - context.doc.advance_paid
	)
	context.outstanding_amount = outstanding_amount
	context.formatted_outstanding_amount = fmt_money(
		outstanding_amount,
		frappe.get_precision(context.doc.doctype, "grand_total"),
		context.doc.currency,
	)
