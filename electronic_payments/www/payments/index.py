import frappe
from frappe.utils.data import flt, fmt_money

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.electronic_payment_settings import (
	process,
)
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	exceeds_credit_limit,
	calculate_payment_method_fees,
)

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(frappe._("You need to be logged in to access this page"), frappe.PermissionError)

	context.doc = frappe.get_doc(frappe.request.args.get("dt"), frappe.request.args.get("dn"))
	party = context.doc.customer if context.doc.customer else context.doc.supplier
	payment_methods = []
	for pm in frappe.get_all("Portal Payment Method", {"parent": party}, order_by="`default` DESC"):
		payment_method = frappe.get_doc("Portal Payment Method", pm.name).as_dict()
		if payment_method.service_charge and payment_method.percentage_or_rate == "Percentage":
			amount = context.doc.grand_total * (payment_method.percentage / 100)
			payment_method.total = flt(
				context.doc.grand_total + amount,
				frappe.get_precision(context.doc.doctype, "grand_total"),
			)
			payment_method.service_charge = f""" - { fmt_money(
				amount,
				frappe.get_precision(context.doc.doctype, "grand_total"),
				context.doc.currency,
			) } ({fmt_money(
				context.doc.grand_total + amount,
				frappe.get_precision(context.doc.doctype, "grand_total"),
				context.doc.currency,
			) })"""
		elif payment_method.service_charge and payment_method.percentage_or_rate == "Rate":
			payment_method.total = flt(
				context.doc.grand_total + payment_method.rate,
				frappe.get_precision(context.doc.doctype, "grand_total"),
			)
			payment_method.service_charge = f""" - { fmt_money(
				payment_method.rate,
				frappe.get_precision(context.doc.doctype, "grand_total"),
				context.doc.currency,
			) } ({fmt_money(
				context.doc.grand_total + payment_method.rate,
				frappe.get_precision(context.doc.doctype, "grand_total"),
				context.doc.currency,
			) })"""
		else:
			payment_method.total = flt(
				context.doc.grand_total, frappe.get_precision(context.doc.doctype, "grand_total")
			)
			payment_method.service_charge = ""
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
	doc = frappe.get_doc(dt, dn)
	data = frappe._dict({})
	data.ppm_mop = ppm.mode_of_payment
	data.ppm_name = ppm.name

	# Check credit limit
	if ppm.subject_to_credit_limit and doc.get("customer") and exceeds_credit_limit(doc, data):
		return {"error_message": "Credit Limit exceeded for selected Mode of Payment"}

	# Calculate Portal Payment Method fees
	data.additional_charges = calculate_payment_method_fees(doc, data)

	# Process the payment
	if ppm.electronic_payment_profile:
		data.mode_of_payment = "Saved Payment Method"
		data.payment_profile_id, data.customer_profile_id = frappe.get_value(
			"Electronic Payment Profile",
			ppm.electronic_payment_profile,
			["payment_profile_id", "party_profile"],
		)
		response = process(doc, data)
		print(response)
		if response.get("message") == "Success":
			return {"success_message": "Your Payment has been processed successfully"}
		else:
			return {"error_message": response["error"]}
	else:
		return {"error_message": "No saved electronic payment profile found for selected payment method"}
