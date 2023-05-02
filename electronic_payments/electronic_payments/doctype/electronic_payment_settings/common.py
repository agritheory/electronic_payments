import frappe
from frappe.utils.data import today


def create_payment_entry(doc, data, transaction_id):
	settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
	payment_type = "Pay" if doc.doctype == "Purchase Invoice" else "Receive"
	party_type = "Supplier" if doc.doctype == "Purchase Invoice" else "Customer"
	party = doc.supplier if doc.doctype == "Purchase Invoice" else doc.customer
	account = doc.credit_to if doc.doctype == "Purchase Invoice" else doc.debit_to
	if settings.clearing_account:
		je = frappe.new_doc("Journal Entry")
		je.posting_date = today()
		je.append(
			"accounts",
			{
				"account": account,
				"party_type": party_type,
				"party": party,
				"debit": doc.grand_total,
				"debit_in_account_currency": doc.grand_total,
				"reference_type": doc.doctype,
				"reference_name": doc.name,
				"user_remarks": str(transaction_id),
				# need a general purpose function to move all accounting dimensions
				"cost_center": doc.cost_center,
				"project": doc.project,
			},
		)
		je.append(
			"accounts",
			{
				"account": settings.clearing_account,
				"party_type": party_type,
				"party": party,
				"debit": doc.grand_total,
				"debit_in_account_currency": doc.grand_total,
				"user_remarks": str(transaction_id),
				# need a general purpose function to move all accounting dimensions
				"cost_center": doc.cost_center,
				"project": doc.project,
			},
		)
		je.save()
		je.submit()
	else:
		pe = frappe.new_doc("Payment Entry")
		pe.mode_of_payment = settings.mode_of_payment
		pe.payment_type = payment_type
		pe.posting_date = today()
		pe.party_type = party_type
		pe.party = party
		# pe.paid_to =
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
		# frappe.db.set_value(doc.doctype, doc.name, "remarks", str(transaction_id)) # TODO switch to custom field - remarks doesn't exist on SO
