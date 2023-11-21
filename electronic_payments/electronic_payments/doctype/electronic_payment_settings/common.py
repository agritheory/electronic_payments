import frappe
from frappe.utils.data import today, flt
from erpnext.accounts.party import get_party_account
from erpnext.selling.doctype.customer.customer import get_credit_limit


def exceeds_credit_limit(doc, data):
	credit_limit = get_credit_limit(doc.customer, doc.company)
	return credit_limit > 0 and doc.grand_total > credit_limit


def calculate_payment_method_fees(doc, data):
	"""
	Given a document (with a grand_total) and a data dict with payment method information,
	        returns any fees associated with that payment method
	"""
	fees = 0.0
	if not data.get("ppm_name"):
		return fees
	ppm = frappe.get_doc("Portal Payment Method", data.get("ppm_name"))
	if ppm.service_charge and ppm.percentage_or_rate == "Percentage":
		fees = flt(
			doc.grand_total * (ppm.percentage / 100), frappe.get_precision(doc.doctype, "grand_total")
		)
	elif ppm.service_charge and ppm.percentage_or_rate == "Rate":
		fees = flt(ppm.rate, frappe.get_precision(doc.doctype, "grand_total"))
	return fees


def process_electronic_payment(doc, data, transaction_id):
	settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})

	if "Journal Entry" in settings.use_clearing_account:
		create_journal_entry(doc, data, transaction_id)
	else:
		create_payment_entry(doc, data, transaction_id)


def create_payment_entry(doc, data, transaction_id):
	settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
	payment_type = "Pay" if "Purchase" in doc.doctype else "Receive"
	party_type = "Supplier" if "Purchase" in doc.doctype else "Customer"
	party = doc.supplier if "Purchase" in doc.doctype else doc.customer
	if doc.doctype in ["Purchase Order", "Sales Order"]:
		account = get_party_account(party_type, party, doc.company)
	else:
		account = doc.credit_to if doc.doctype == "Purchase Invoice" else doc.debit_to
	bank_account = (
		settings.withdrawal_account if "Purchase" in doc.doctype else settings.deposit_account
	)
	fee_account = (
		settings.sending_fee_account if "Purchase" in doc.doctype else settings.accepting_fee_account
	)
	fees = data.get("additional_charges") or 0

	pe = frappe.new_doc("Payment Entry")
	ppm_mop = (
		frappe.get_value("Portal Payment Method", data.get("ppm_name"), "mode_of_payment")
		if data.get("ppm_name")
		else None
	)
	pe.mode_of_payment = ppm_mop or settings.mode_of_payment
	pe.payment_type = payment_type
	pe.posting_date = today()
	pe.party_type = party_type
	pe.party = party
	pe.paid_to = (
		account if doc.doctype == "Purchase Invoice" else bank_account
	)  # Accounts Payable for PO/PI (doc.credit_to field), Deposit Account for SO/SI
	pe.paid_from = (
		bank_account if doc.doctype == "Purchase Invoice" else account
	)  # Withdrawal Account for PO/PI, Accounts Receivable for SO/SI (doc.debit_to field)
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
	if fees:
		pe.append(
			"taxes",
			{
				"add_deduct_tax": "Add",
				"charge_type": "Actual",
				"account_head": fee_account,
				"description": "Electronic Payments Provider Fees",
				"tax_amount": fees,
			},
		)
	# need a general purpose function to move all accounting dimensions
	pe.cost_center = doc.cost_center
	pe.project = doc.project

	pe.save()
	pe.submit()


def create_journal_entry(doc, data, transaction_id):
	settings = frappe.get_doc("Electronic Payment Settings", {"company": doc.company})
	party_type = "Supplier" if "Purchase" in doc.doctype else "Customer"
	party = doc.supplier if "Purchase" in doc.doctype else doc.customer
	if doc.doctype in ["Purchase Order", "Sales Order"]:
		account = get_party_account(party_type, party, doc.company)
	else:
		account = doc.credit_to if doc.doctype == "Purchase Invoice" else doc.debit_to
	clearing_account = (
		settings.sending_clearing_account
		if "Purchase" in doc.doctype
		else settings.accepting_clearing_account
	)
	account_key = (
		"debit" if doc.doctype == "Purchase Invoice" else "credit"
	)  # Accounting term for reducing the account. A/R account for SO/SI -> "credit" or A/P account for PO/PI -> "debit"
	account_currency_key = account_key + "_in_account_currency"
	contra_account_key = "credit" if account_key == "debit" else "debit"
	contra_account_currency_key = contra_account_key + "_in_account_currency"
	is_advance = doc.doctype in ["Sales Order", "Purchase Order"]

	fee_account = (
		settings.sending_fee_account if "Purchase" in doc.doctype else settings.accepting_fee_account
	)
	fees = data.get("additional_charges") or 0

	je = frappe.new_doc("Journal Entry")
	je.posting_date = today()
	ppm_mop = (
		frappe.get_value("Portal Payment Method", data.get("ppm_name"), "mode_of_payment")
		if data.get("ppm_name")
		else None
	)
	je.mode_of_payment = ppm_mop or settings.mode_of_payment
	je.append(
		"accounts",
		{  # Reduce the account: either debit A/P for PO/PI or credit A/R for SO/SI
			"account": account,
			"party_type": party_type,
			"party": party,
			account_key: doc.grand_total,
			account_currency_key: doc.grand_total,
			"reference_type": doc.doctype,
			"reference_name": doc.name,
			"is_advance": "Yes" if is_advance else "No",
			"user_remarks": str(transaction_id),
			# need a general purpose function to move all accounting dimensions
			"cost_center": doc.cost_center,
			"project": doc.project,
		},
	)
	je.append(
		"accounts",
		{  # Increase the clearing account: either credit EP A/P for PO/PI, or debit EP A/R for SO/SI
			"account": clearing_account,
			"party_type": party_type,
			"party": party,
			contra_account_key: doc.grand_total + fees,
			contra_account_currency_key: doc.grand_total + fees,
			"user_remarks": str(transaction_id),
			# need a general purpose function to move all accounting dimensions
			"cost_center": doc.cost_center,
			"project": doc.project,
		},
	)
	if fees:
		je.append(
			"accounts",
			{
				"account": fee_account,
				account_key: fees,
				account_currency_key: fees,
				"user_remarks": str(transaction_id),
				"cost_center": doc.cost_center,
				"project": doc.project,
			},
		)
	je.save()
	je.submit()
