import frappe
import json


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
		payment_amount = (
			ref.allocated_amount
			if is_pe
			else (ref.get("debit_in_account_currency") or ref.get("credit_in_account_currency"))
		)

		if method == "on_submit":
			frappe.db.sql(
				"""
				UPDATE `tabPayment Schedule`
				SET
					paid_amount = `paid_amount` + %s,
					outstanding = `outstanding` - %s
				WHERE name = %s""",
				(payment_amount, payment_amount, ref.electronic_payments_payment_term),
			)
		elif method == "on_cancel":
			frappe.db.sql(
				"""
				UPDATE `tabPayment Schedule`
				SET
					paid_amount = `paid_amount` - %s,
					outstanding = `outstanding` + %s
				WHERE name = %s""",
				(payment_amount, payment_amount, ref.electronic_payments_payment_term),
			)
