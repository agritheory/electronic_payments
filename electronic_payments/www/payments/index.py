import frappe
from frappe.utils.data import flt, fmt_money

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.electronic_payment_settings import (
	process,
)
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	exceeds_credit_limit,
	get_payment_amount,
	get_discount_amount,
)

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(frappe._("You need to be logged in to access this page"), frappe.PermissionError)

	dt = frappe.request.args.get("dt")
	dn = frappe.request.args.get("dn")
	data = frappe._dict({})
	if dt == "Payment Schedule":
		payment_schedule_pmt_term = frappe.get_doc(dt, dn)
		context.doc = frappe.get_doc(
			payment_schedule_pmt_term.parenttype, payment_schedule_pmt_term.parent
		)
		data.payment_term = dn
	else:
		context.doc = frappe.get_doc(dt, dn)
	payment_amount = get_payment_amount(context.doc, data)
	discount_amount = get_discount_amount(context.doc, data)
	party = context.doc.customer if context.doc.customer else context.doc.supplier
	payment_methods = []
	for pm in frappe.get_all("Portal Payment Method", {"parent": party}, order_by="`default` DESC"):
		payment_method = frappe.get_doc("Portal Payment Method", pm.name)
		fees = payment_method.calculate_payment_method_fees(
			context.doc, amount=(payment_amount - discount_amount)
		)
		payment_method = payment_method.as_dict()
		payment_method.total = flt(
			payment_amount - discount_amount + fees,
			frappe.get_precision(context.doc.doctype, "grand_total"),
		)
		payment_method.service_charge = (
			f""" - { fmt_money(
			fees,
			frappe.get_precision(context.doc.doctype, "grand_total"),
			context.doc.currency,
		) } ({fmt_money(
			payment_amount - discount_amount + fees,
			frappe.get_precision(context.doc.doctype, "grand_total"),
			context.doc.currency,
		) })"""
			if fees
			else ""
		)
		if payment_method.default:
			context.doc.grand_total_with_service_charge = fmt_money(
				payment_method.total, frappe.get_precision(context.doc.doctype, "grand_total")
			)
		payment_methods.append(payment_method)
	context.payment_methods = payment_methods

	# get customer configured payment methods
	# - credit limit not exceeded
	# - gateway enabled
	# - insert saved payment methods (Card, ACH, account, etc) at beginning of list
	# - if saved payments exist, append ('new' to card and ACH payment)

	context.show_sidebar = True


@frappe.whitelist()
def pay(dt, dn, payment_method):
	"""
	Processes payment for given document
	:param dt: str; document doctype
	:param dn: str; document name
	:param payment method: str; Portal Payment Method name
	:return: dict[str: str] of form {"success_message": ...} or {"error_message": ...}
	"""
	ppm = frappe.get_doc("Portal Payment Method", payment_method)
	data = frappe._dict({})
	if dt == "Payment Schedule":
		payment_schedule_pmt_term = frappe.get_doc(dt, dn)
		doc = frappe.get_doc(payment_schedule_pmt_term.parenttype, payment_schedule_pmt_term.parent)
		data.payment_term = dn
	else:
		doc = frappe.get_doc(dt, dn)
	data.ppm_mop = ppm.mode_of_payment
	data.ppm_name = ppm.name
	payment_amount = get_payment_amount(doc, data)
	discount_amount = get_discount_amount(doc, data)

	# Check credit limit
	if ppm.subject_to_credit_limit and doc.get("customer") and exceeds_credit_limit(doc, data):
		return {"error_message": "Credit Limit exceeded for selected Mode of Payment"}

	# Calculate Portal Payment Method fees
	data.additional_charges = ppm.calculate_payment_method_fees(
		doc, amount=(payment_amount - discount_amount)
	)

	# Process the payment
	if ppm.electronic_payment_profile:
		data.mode_of_payment = "Saved Payment Method"
		data.payment_profile_id, data.customer_profile_id = frappe.get_value(
			"Electronic Payment Profile",
			ppm.electronic_payment_profile,
			["payment_profile_id", "party_profile"],
		)
		response = process(doc, data)
		if response.get("message") == "Success":
			return {"success_message": "Your Payment has been processed successfully"}
		else:
			return {"error_message": response["error"]}
	else:
		return {"error_message": "No saved electronic payment profile found for selected payment method"}
