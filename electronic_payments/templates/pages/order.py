# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils.data import fmt_money, getdate

from erpnext.templates.pages.order import get_context as get_erpnext_order_context

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	get_discount_amount,
)


def get_context(context):
	# Set flag so jinga loader finds electronic_payments app changes first
	local_web_pages_app_list = frappe.local.flags.web_pages_apps
	if not local_web_pages_app_list or local_web_pages_app_list[0] != "electronic_payments":
		installed_apps = frappe.get_installed_apps()
		frappe.local.flags.web_pages_apps = list(reversed(installed_apps))
		frappe.db.commit()

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

	# Adjust Payment Term Schedule amounts and due dates to include discount amounts
	payment_terms = []
	for pt in context.doc.payment_schedule:
		due_date_key = "due_date"
		discount_amount = 0
		if pt.outstanding and pt.discount and getdate() <= pt.discount_date:
			data = frappe._dict(
				{
					"payment_term": pt.name,
				}
			)
			discount_amount = get_discount_amount(context.doc, data)
			due_date_key = "discount_date"
		term_dict = frappe._dict(
			{
				"payment_term": pt.payment_term or "Due on Demand",
				"due_date": pt.get_formatted(due_date_key),
				"payment_amount": pt.payment_amount - discount_amount,
				"outstanding": pt.outstanding,
				"name": pt.name,
				"doctype": pt.doctype,
			}
		)
		payment_terms.append(term_dict)
	context.payment_terms = payment_terms
