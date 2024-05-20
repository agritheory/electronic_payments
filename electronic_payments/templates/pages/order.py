# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils.data import fmt_money, getdate

from webshop.templates.pages.order import get_context as get_webshop_order_context

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	get_discount_amount,
)


def get_context(context):
	get_webshop_order_context(context)
	is_valid_doctype = context.doc.doctype in [
		"Sales Order",
		"Sales Invoice",
		"Purchase Order",
		"Purchase Invoice",
	]
	if is_valid_doctype:
		party = context.doc.customer if "Sales" in context.doc.doctype else context.doc.supplier
		context.has_portal_payment_method = (
			len(frappe.get_all("Portal Payment Method", {"parent": party})) > 0
		)
	else:
		context.has_portal_payment_method = False
	context.show_payment_terms = (
		is_valid_doctype and len(context.doc.payment_schedule) > 0 and context.has_portal_payment_method
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
	has_discount = False
	payment_terms = []
	for pt in context.doc.payment_schedule:
		due_date_key = "due_date"
		discount_amount = 0
		if pt.outstanding and pt.discount and getdate() <= pt.discount_date:
			has_discount = True
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
				"outstanding": min(pt.payment_amount - discount_amount, pt.outstanding, outstanding_amount),
				"name": pt.name,
				"doctype": pt.doctype,
			}
		)
		payment_terms.append(term_dict)
	context.payment_terms = payment_terms
	context.has_discount = has_discount
