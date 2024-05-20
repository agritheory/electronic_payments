import frappe
from frappe.utils.data import cstr, today, flt, getdate, get_datetime
from frappe.utils.background_jobs import (
	get_queue,
	execute_job,
	create_job_id,
	RQ_JOB_FAILURE_TTL,
	RQ_RESULTS_TTL,
)
from erpnext.accounts.party import get_party_account
from erpnext.selling.doctype.customer.customer import get_credit_limit
import datetime


def exceeds_credit_limit(doc, data):
	credit_limit = get_credit_limit(doc.customer, doc.company)
	payment_amount = get_payment_amount(doc, data)
	discount_amount = get_discount_amount(doc, data)
	return credit_limit > 0 and payment_amount - discount_amount > credit_limit


def get_payment_amount(doc, data):
	"""
	Given a `doc` (SO/SI/PO/PI) and `data` dict, returns the payment amount. If the `data` dict
	has a "payment_term" key with the docname of a Payment Schedule payment term, the payment
	amount is the minimum of the doc's outstanding amount or the payment term outstanding amount.
	If not, the payment amount is `outstanding_amount` for Invoices and `grand_total` -
	`advance_paid` for Orders.
	"""
	precision = frappe.get_precision(doc.doctype, "grand_total")
	outstanding_amount = (
		doc.outstanding_amount if "Invoice" in doc.doctype else doc.grand_total - doc.advance_paid
	)
	payment_amount = (
		frappe.get_value("Payment Schedule", data.payment_term, "outstanding")
		if data.get("payment_term")
		else doc.grand_total
	)
	return flt(min(payment_amount, outstanding_amount), precision)


def get_discount_amount(doc, data):
	"""
	Given a `doc` (SO/SI/PO/PI) and `data` dict, returns the discount amount tied to a payment term
	if any.
	"""
	precision = frappe.get_precision(doc.doctype, "grand_total")
	reference_date = data.get("reference_date") or getdate()
	reference_date = (
		get_datetime(reference_date).date() if isinstance(reference_date, str) else reference_date
	)
	discount_amount = 0.0
	if data.get("payment_term"):
		term = frappe.get_doc("Payment Schedule", data.payment_term)
		if not term.discounted_amount and term.discount and reference_date <= term.discount_date:
			if term.discount_type == "Percentage":
				discount_amount = doc.get("grand_total") * (term.discount / 100)
			else:
				discount_amount = term.discount

	return flt(discount_amount, precision)


def calculate_payment_method_fees(doc, data):
	"""
	Given a `doc` (SO/SI/PO/PI) and `data` dict with payment method information, returns any
	fees associated with that payment method. Percentage-based fees use the payment amount.
	"""
	if not data.get("ppm_name"):
		return 0.0
	ppm = frappe.get_doc("Portal Payment Method", data.get("ppm_name"))
	payment_amount = get_payment_amount(doc, data) - get_discount_amount(doc, data)
	return ppm.calculate_payment_method_fees(doc, amount=payment_amount)


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
	payment_amount = get_payment_amount(doc, data)
	discount_amount = get_discount_amount(doc, data)
	payment_term = (
		frappe.get_value("Payment Schedule", data.payment_term, "payment_term")
		if data.get("payment_term")
		else ""
	)

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
	pe.paid_amount = payment_amount - discount_amount
	pe.received_amount = payment_amount - discount_amount
	pe.reference_no = str(transaction_id)
	pe.reference_date = pe.posting_date
	# need a general purpose function to move all accounting dimensions
	pe.cost_center = doc.cost_center
	pe.project = doc.project

	pe.append(
		"references",
		{
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"allocated_amount": payment_amount,
			"payment_term": payment_term,
			"electronic_payments_payment_term": data.get("payment_term") or "",
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
	if discount_amount:
		positive_or_negative = (
			-1 if payment_type == "Pay" else 1
		)  # determines whether entry will be a debit or credit on account
		precision = frappe.get_precision(doc.doctype, "grand_total")
		book_tax_loss = frappe.db.get_single_value("Accounts Settings", "book_tax_discount_loss")
		account = (
			settings.sending_payment_discount_account
			if payment_type == "Pay"
			else settings.accepting_payment_discount_account
		)

		if book_tax_loss:
			pt_discount_type, pt_discount = frappe.get_value(
				"Payment Schedule", data.payment_term, ["discount_type", "discount"]
			)
			total_discount_percent = (
				pt_discount
				if pt_discount_type == "Percentage"
				else (pt_discount / doc.get("grand_total")) * 100
			)

			# Calculate the split amounts to items vs tax accounts, adjust for rounding differences
			tax_deductions = calculate_tax_discount_portion(doc, total_discount_percent)
			total_tax_deduction_amount = (
				sum(d.get("amount", 0) for d in tax_deductions) if tax_deductions else 0
			)
			discount_portion_on_items = flt(discount_amount - total_tax_deduction_amount, precision)

			# Change signs for taxes and append to PE
			for tax in tax_deductions:
				tax["amount"] *= positive_or_negative
				pe.append(
					"deductions",
					tax,
				)
		else:
			discount_portion_on_items = discount_amount

		pe.append(
			"deductions",
			{
				"account": account,
				"cost_center": doc.cost_center
				or frappe.get_cached_value("Company", doc.company, "cost_center"),
				"amount": positive_or_negative * discount_portion_on_items,
			},
		)

	pe.save(ignore_permissions=True)
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
		"debit" if "Purchase" in doc.doctype else "credit"
	)  # Accounting term for reducing the account. A/R account for SO/SI -> "credit" or A/P account for PO/PI -> "debit"
	account_currency_key = account_key + "_in_account_currency"
	contra_account_key = "credit" if account_key == "debit" else "debit"
	contra_account_currency_key = contra_account_key + "_in_account_currency"
	is_advance = doc.doctype in ["Sales Order", "Purchase Order"]

	fee_account = (
		settings.sending_fee_account if "Purchase" in doc.doctype else settings.accepting_fee_account
	)
	fees = data.get("additional_charges") or 0
	payment_amount = get_payment_amount(doc, data)
	discount_amount = get_discount_amount(doc, data)

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
			account_key: payment_amount,
			account_currency_key: payment_amount,
			"reference_type": doc.doctype,
			"reference_name": doc.name,
			"electronic_payments_payment_term": data.get("payment_term") or "",
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
			contra_account_key: payment_amount - discount_amount + fees,
			contra_account_currency_key: payment_amount - discount_amount + fees,
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
	if discount_amount:
		# Discounts fall under same account_key (debit/credit) as the clearing account
		precision = frappe.get_precision(doc.doctype, "grand_total")
		book_tax_loss = frappe.db.get_single_value("Accounts Settings", "book_tax_discount_loss")
		account = (
			settings.sending_payment_discount_account
			if "Purchase" in doc.doctype
			else settings.accepting_payment_discount_account
		)

		if book_tax_loss:
			pt_discount_type, pt_discount = frappe.get_value(
				"Payment Schedule", data.payment_term, ["discount_type", "discount"]
			)
			total_discount_percent = (
				pt_discount
				if pt_discount_type == "Percentage"
				else (pt_discount / doc.get("grand_total")) * 100
			)

			# Calculate the split amounts to items vs tax accounts, adjust for rounding differences
			tax_deductions = calculate_tax_discount_portion(doc, total_discount_percent)
			total_tax_deduction_amount = (
				sum(d.get("amount", 0) for d in tax_deductions) if tax_deductions else 0
			)
			discount_portion_on_items = flt(discount_amount - total_tax_deduction_amount, precision)

			# Change keys to match Journal Entry Account Item fields and append
			for tax in tax_deductions:
				tax[contra_account_key] = tax["amount"]
				tax[contra_account_currency_key] = tax["amount"]
				tax["user_remarks"] = str(transaction_id)
				tax["project"] = doc.project
				del tax["amount"]
				je.append(
					"accounts",
					tax,
				)
		else:
			discount_portion_on_items = discount_amount

		je.append(
			"accounts",
			{
				"account": account,
				contra_account_key: discount_portion_on_items,
				contra_account_currency_key: discount_portion_on_items,
				"user_remarks": str(transaction_id),
				"cost_center": doc.cost_center
				or frappe.get_cached_value("Company", doc.company, "cost_center"),
				"project": doc.project,
			},
		)

	je.save(ignore_permissions=True)
	je.submit()


def calculate_tax_discount_portion(doc, total_discount_percentage):
	"""
	Calculates portion of a discount split to taxes if Accounts Settings has Book Tax Discount
	Loss checked (which splits a discount amongst the doc's item total and the tax table)

	:param doc: Document (Sales Order, Sales Invoice, Purchase Order, Purchase Invoice)
	:param total_discount_percentage: flt | int; percent (vs doc's grand_total) the discount
	amount is for (not a decimal, so 2% would be 2.00)
	:return: list of dicts; information to append to PE or JE
	"""
	tax_discount_loss = {}
	precision = frappe.get_precision(doc.doctype, "grand_total")
	deductions = []

	# The same account head could be used more than once
	for tax in doc.get("taxes", []):
		base_tax_loss = tax.get("base_tax_amount_after_discount_amount") * (
			total_discount_percentage / 100
		)

		account = tax.get("account_head")
		if not tax_discount_loss.get(account):
			tax_discount_loss[account] = base_tax_loss
		else:
			tax_discount_loss[account] += base_tax_loss

	for account, loss in tax_discount_loss.items():
		if loss == 0.0:
			continue

		deductions.append(
			{
				"account": account,
				"cost_center": doc.cost_center
				or frappe.get_cached_value("Company", doc.company, "cost_center"),
				"amount": flt(loss, precision),
			},
		)

	return deductions


def queue_method_as_admin(method, **kwargs):
	"""
	Applies background job enqueue logic but sets the user as Administrator to execute method.

	:param method: function to call
	:param kwargs: arguments to pass to method
	:return: job
	"""
	# enqueue arguments passed to execute_job
	job_name_and_id_str = cstr(method) + str(datetime.datetime.now())
	queue = "short"
	timeout = 3600
	event = None
	is_async = True
	at_front = False
	job_id = create_job_id(job_name_and_id_str)
	try:
		q = get_queue(queue, is_async=is_async)
	except ConnectionError:
		if frappe.local.flags.in_migrate:
			# If redis is not available during migration, execute the job directly
			print(f"Redis queue is unreachable: Executing {method} synchronously")
			return frappe.call(method, **kwargs)
		raise

	queue_args = {
		"site": frappe.local.site,
		"user": "Administrator",  # frappe.session.user,
		"method": method,
		"event": event,
		"job_name": job_name_and_id_str,
		"is_async": is_async,
		"kwargs": kwargs,
	}

	return q.enqueue_call(
		execute_job,
		on_success=None,
		on_failure=None,
		timeout=timeout,
		kwargs=queue_args,
		at_front=at_front,
		failure_ttl=frappe.conf.get("rq_job_failure_ttl") or RQ_JOB_FAILURE_TTL,
		result_ttl=frappe.conf.get("rq_results_ttl") or RQ_RESULTS_TTL,
		job_id=job_id,
	)


def get_party_details(doc):
	if hasattr(doc, "customer"):
		return frappe._dict(
			{"doctype": "Customer", "name": doc.customer, "description": doc.customer_name}
		)
	elif hasattr(doc, "supplier"):
		return frappe._dict(
			{"doctype": "Supplier", "name": doc.supplier, "description": doc.supplier_name}
		)
