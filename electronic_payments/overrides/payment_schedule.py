import frappe
import json

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	get_discount_amount,
)


def update_payment_schedule_for_electronic_payment(doc, method=None):
	"""
	Updates the Payment Schedule for Journal Entries and Payment Entries in the case where the
	auto-generated schedule lack the Payment Term name and thus the ability to link to it

	Custom field `electronic_payments_payment_term` on both Payment Entry Reference and Journal
	Entry Account stores the docname of a payment term within the Payment Schedule the payment
	applies to. Journal Entries don't have a way to track payment terms, Payment Entries have
	a field in references that stores the Payment Schedule's payment term name and will update
	the schedule if that's provided. However, when ERPNext auto-generates payment schedules for
	a SO/SI/PO/PI (when there's no template and user leaves section empty), it doesn't give
	a name of a payment term, which is the field needed in the Payment Entry to link to.
	"""
	doc = json.loads(doc) if isinstance(doc, str) else doc
	if doc.doctype not in ["Payment Entry", "Journal Entry"]:
		return
	is_pe = doc.doctype == "Payment Entry"
	refs = doc.get("references") if is_pe else doc.get("accounts")
	for ref in refs:
		if not ref.get("electronic_payments_payment_term"):
			continue
		if is_pe and ref.get("payment_term"):  # already updates via Payment Entry mechanism
			continue

		# Replicate code flow in erpnext.accounts.doctype.payment_entry.payment_entry update_payment_schedule
		payment_term_doc = frappe.get_doc(
			"Payment Schedule", ref.get("electronic_payments_payment_term")
		)
		pre_discount_payment_amount = (
			ref.allocated_amount
			if is_pe
			else (ref.get("debit_in_account_currency") or ref.get("credit_in_account_currency"))
		)
		if payment_term_doc.discount and method == "on_submit":
			orig_doc = frappe.get_doc(payment_term_doc.parenttype, payment_term_doc.parent)
			data = frappe._dict(
				{
					"reference_date": doc.posting_date,
					"payment_term": ref.get("electronic_payments_payment_term"),
				}
			)
			discount_amount = get_discount_amount(orig_doc, data)
		elif payment_term_doc.discount and method == "on_cancel":
			discount_amount = payment_term_doc.discounted_amount
		else:
			discount_amount = 0

		ps = frappe.qb.DocType("Payment Schedule").as_("ps")
		if method == "on_submit":
			frappe.qb.update(ps).set(
				ps.paid_amount, ps.paid_amount + (pre_discount_payment_amount - discount_amount)
			).where(ps.name == ref.electronic_payments_payment_term).run()
			frappe.qb.update(ps).set(ps.discounted_amount, ps.discounted_amount + discount_amount).where(
				ps.name == ref.electronic_payments_payment_term
			).run()
			frappe.qb.update(ps).set(ps.outstanding, ps.outstanding - pre_discount_payment_amount).where(
				ps.name == ref.electronic_payments_payment_term
			).run()
		elif method == "on_cancel":
			frappe.qb.update(ps).set(
				ps.paid_amount, ps.paid_amount - (pre_discount_payment_amount - discount_amount)
			).where(ps.name == ref.electronic_payments_payment_term).run()
			frappe.qb.update(ps).set(ps.discounted_amount, ps.discounted_amount - discount_amount).where(
				ps.name == ref.electronic_payments_payment_term
			).run()
			frappe.qb.update(ps).set(ps.outstanding, ps.outstanding + pre_discount_payment_amount).where(
				ps.name == ref.electronic_payments_payment_term
			).run()
