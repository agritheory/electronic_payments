import frappe
from frappe.utils.data import flt, fmt_money

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
				context.doc.grand_total + amount, frappe.get_precision(context.doc.doctype, "grand_total")
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
	print(dt, dn, payment_method)
	return {"success_message": "Your Payment has been processed successfully"}
