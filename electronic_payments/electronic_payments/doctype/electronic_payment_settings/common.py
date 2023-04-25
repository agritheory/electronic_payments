import frappe
from frappe.utils.data import today


def create_payment_entry(doc, data, transaction_id):
	settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
	pe = frappe.new_doc("Payment Entry")
	pe.mode_of_payment = settings.mode_of_payment
	pe.payment_type = "Receive"
	pe.posting_date = today()
	pe.party_type = "Customer"
	pe.party = doc.customer
	pe.paid_to = settings.clearing_account
	pe.paid_amount = doc.grand_total
	pe.received_amount = doc.grand_total
	pe.reference_no = str(transaction_id)
	pe.reference_date = pe.posting_date
	pe.append(
		"references",
		{
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"allocated_amount": doc.grand_total,
		},
	)
	pe.save()
	pe.submit()
	frappe.db.set_value(doc.doctype, doc.name, "remarks", str(transaction_id))
	return
