import frappe
from frappe.utils.data import today


def process_electronic_payment(doc, data, transaction_id):
	settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})

	if "Journal Entry" in settings.use_clearing_account:
		create_journal_entry(doc, data, transaction_id)
	else:
		create_payment_entry(doc, data, transaction_id)


def create_payment_entry(doc, data, transaction_id):
	settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
	payment_type = "Pay" if doc.doctype == "Purchase Invoice" else "Receive"
	party_type = "Supplier" if doc.doctype == "Purchase Invoice" else "Customer"
	party = doc.supplier if doc.doctype == "Purchase Invoice" else doc.customer
	account = doc.credit_to if doc.doctype == "Purchase Invoice" else doc.debit_to
	bank_account = (
		settings.withdrawal_account if doc.doctype == "Purchase Invoice" else settings.deposit_account
	)

	pe = frappe.new_doc("Payment Entry")
	pe.mode_of_payment = settings.mode_of_payment
	pe.payment_type = payment_type
	pe.posting_date = today()
	pe.party_type = party_type
	pe.party = party
	pe.paid_to = (
		account if doc.doctype == "Purchase Invoice" else bank_account
	)  # Accounts Payable for PI (doc.credit_to field), Deposit Account for SO/SI
	pe.paid_from = (
		bank_account if doc.doctype == "Purchase Invoice" else account
	)  # Withdrawal Account for PI, Accounts Receivable for SO/SI (doc.debit_to field)
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
	# need a general purpose function to move all accounting dimensions
	pe.cost_center = doc.cost_center
	pe.project = doc.project

	pe.save()
	pe.submit()


def create_journal_entry(doc, data, transaction_id):
	settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
	party_type = "Supplier" if doc.doctype == "Purchase Invoice" else "Customer"
	party = doc.supplier if doc.doctype == "Purchase Invoice" else doc.customer
	account = doc.credit_to if doc.doctype == "Purchase Invoice" else doc.debit_to
	clearing_account = (
		settings.sending_clearing_account
		if doc.doctype == "Purchase Invoice"
		else settings.accepting_clearing_account
	)
	account_key = (
		"debit" if doc.doctype == "Purchase Invoice" else "credit"
	)  # Accounting term for reducing the account. A/R account for SO/SI -> "credit" or reducing A/P account for PI -> "debit"
	account_currency_key = account_key + "_in_account_currency"
	contra_account_key = "credit" if account_key == "debit" else "debit"
	contra_account_currency_key = contra_account_key + "_in_account_currency"

	je = frappe.new_doc("Journal Entry")
	je.posting_date = today()
	je.append(
		"accounts",
		{  # Reduce the account: either debit A/P for PI or credit A/R for SI/SO
			"account": account,
			"party_type": party_type,
			"party": party,
			account_key: doc.grand_total,
			account_currency_key: doc.grand_total,
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
		{  # Increase the clearing account: either credit EP A/P for PI, or debit EP A/R for SI/SO
			"account": clearing_account,
			"party_type": party_type,
			"party": party,
			contra_account_key: doc.grand_total,
			contra_account_currency_key: doc.grand_total,
			"user_remarks": str(transaction_id),
			# need a general purpose function to move all accounting dimensions
			"cost_center": doc.cost_center,
			"project": doc.project,
		},
	)
	je.save()
	je.submit()
