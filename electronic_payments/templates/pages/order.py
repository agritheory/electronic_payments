# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils.data import fmt_money

from erpnext.templates.pages.order import get_context as get_erpnext_order_context


def get_context(context):
	get_erpnext_order_context(context)
	context.show_payment_terms = (
		context.doc.doctype in ["Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice"]
		and len(context.doc.payment_schedule) > 0
	)
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
