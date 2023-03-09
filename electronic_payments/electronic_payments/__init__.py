import frappe
import json

@frappe.whitelist()
def process(doc, data):
	if isinstance(data, str):
		doc = json.loads(doc)
		doc = frappe.get_doc(doc['doctype'], doc['name'])
		data = frappe._dict(json.loads(data))
	# TODO: use mode of payment instead, design better selection logic
	eps_name = frappe.get_value('Electronic Payment Settings', {'company': doc.company})
	eps = frappe.get_doc('Electronic Payment Settings', eps_name)
	# TODO: Move this to a separate function and make it sensitive to both Authorize and Stripe
	if eps.provider == 'Authorize.Net':
		if data.mode_of_payment == 'New Card' and data.save_data == 'Charge now':
			return eps.process_credit_card(doc, data)
		elif data.mode_of_payment == 'New ACH' and data.save_data == 'Charge now':
			return eps.debit_bank_account(doc, data)
		elif data.mode_of_payment == 'Saved Payment Method':
			return eps.charge_customer_profile(doc, data)
		elif data.save_data != 'Charge now':
			data["customer_profile"] = eps.create_customer_profile(doc, data)
			payment_profile = eps.create_customer_payment_profile(doc, data)
			if payment_profile.get('error'):
				return payment_profile
			if payment_profile.retain == 0:
				frappe.db.set_value(doc.doctype, doc.name, 'pre_authorization_token', payment_profile.payment_profile_id)
			else:
				frappe.db.set_value('Customer', doc.customer, 'electronic_payment_profile', payment_profile.customer_profile)
			return payment_profile
		else:
			frappe.throw('Invalid options')
	if eps.provider == 'Stripe':
		... # do stripe stuff