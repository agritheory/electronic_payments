import frappe
import frappe.defaults
from frappe.utils import flt
import pytest
from random import randint

from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	exceeds_credit_limit,
	get_payment_amount,
	get_discount_amount,
	get_party_details,
	calculate_payment_method_fees,
	process_electronic_payment,
)


def create_electronic_payment_settings(
	provider, clearing_acct="Use Journal Entry and Clearing Account"
):
	"""
	Helper function to create Electronic Payment Settings for default company with dummy API keys
	"""
	company = frappe.defaults.get_defaults().company
	frappe.delete_doc_if_exists(
		"Electronic Payment Settings",
		frappe.get_value("Electronic Payment Settings", {"company": company}),
	)
	eps = frappe.new_doc("Electronic Payment Settings")
	eps.company = company
	eps.provider = provider
	eps.api_key = "123456789"
	eps.transaction_key = "" if provider == "Stripe" else "987654321"
	eps.create_ppm = 1
	eps.use_clearing_account = clearing_acct
	eps.deposit_account = "1201 - Primary Checking - CFC"
	eps.accepting_fee_account = "5223 - Electronic Payments Provider Fees - CFC"
	eps.accepting_clearing_account = "1320 - Electronic Payments Receivable - CFC"
	eps.accepting_payment_discount_account = frappe.get_value(
		"Account", {"name": ["like", "%Sales - CFC%"]}, "name"
	)
	eps.enable_sending = 1
	eps.withdrawal_account = "1201 - Primary Checking - CFC"
	eps.sending_fee_account = eps.accepting_fee_account
	eps.sending_clearing_account = "2130 - Electronic Payments Payable - CFC"
	eps.sending_payment_discount_account = frappe.get_value(
		"Account", {"name": ["like", "%Miscellaneous Expenses%"]}, "name"
	)
	eps.save()
	return eps


def create_party_payment_method(party, party_type, service_charge=False):
	"""
	Helper function to create dummy Portal Payment Method for given party

	:param party: str; name of party Document
	:param party_type: str; Customer or Supplier
	:param service_charge: bool; whether to include a $2 service charge for new payment method
	:return: str; docname of the Portal Payment Method
	"""
	settings = frappe.get_doc(
		"Electronic Payment Settings", {"company": frappe.defaults.get_defaults().company}
	)
	party_profile = frappe.get_value(party_type, party, "electronic_payment_profile")
	last4 = randint(1000, 9999)  # Random 4 digit number

	payment_profile = frappe.new_doc("Electronic Payment Profile")
	payment_profile.party_type = party_type
	payment_profile.party = party
	payment_profile.payment_type = "Card"
	payment_profile.payment_gateway = (
		"Authorize" if settings.provider == "Authorize.net" else "Stripe"
	)
	payment_profile.reference = f"**** **** **** {last4}"
	payment_profile.payment_profile_id = str(randint(100000000, 999999999))  # Random 9-digit number
	payment_profile.party_profile = (
		party_profile if party_profile else str(randint(100000000, 999999999))
	)  # Random 9-digit number
	payment_profile.retain = 1
	payment_profile.save()

	ppm = frappe.new_doc("Portal Payment Method")
	ppm.mode_of_payment = frappe.get_value(
		"Electronic Payment Settings",
		{"company": frappe.defaults.get_defaults().company},
		"mode_of_payment",
	)
	ppm.label = f"Card-{last4}"
	ppm.default = 0
	ppm.electronic_payment_profile = payment_profile.name
	ppm.service_charge = int(service_charge)
	if service_charge:
		ppm.percentage_or_rate = "Rate"
		ppm.rate = 2
	ppm.parent = payment_profile.party
	ppm.parenttype = payment_profile.party_type
	ppm.save()

	party_obj = frappe.get_doc(party_type, party)
	party_obj.append("portal_payment_method", ppm)
	party_obj.save()

	return ppm.name


@pytest.mark.order(10)
def test_exceeds_credit_limit():
	doc = frappe.get_doc(
		"Sales Order", {"customer": "Cassiopeia Restaurant Group", "grand_total": [">", 300]}
	)
	pt = frappe.get_value("Payment Schedule", {"parent": doc.name})
	data = frappe._dict(
		{
			"payment_term": pt,
		}
	)
	assert exceeds_credit_limit(doc, data)


@pytest.mark.order(11)
def test_multiple_payment_term_amounts():
	doc = frappe.get_doc(
		"Sales Invoice",
		{"customer": "Andromeda Fruit Market", "payment_terms_template": "20 in 14 80 in 30"},
	)
	precision = frappe.get_precision(doc.doctype, "grand_total")
	epsilson = 1 / pow(10, precision + 1)
	data = frappe._dict({})

	# No payment term passed along
	payment = get_payment_amount(doc, data)
	assert abs(payment - doc.grand_total) < epsilson

	# 20% of Invoice payment term
	pt_20_percent = frappe.get_doc(
		"Payment Schedule", {"parent": doc.name, "payment_term": "20 Percent in 14 Days"}
	)
	assert pt_20_percent.invoice_portion == 20
	data.payment_term = pt_20_percent.name
	calculated_payment = flt(doc.grand_total * pt_20_percent.invoice_portion / 100, precision)
	payment = get_payment_amount(doc, data)
	discount = get_discount_amount(doc, data)
	assert abs(payment - calculated_payment) < epsilson
	assert discount == 0

	# 80% of Invoice payment term
	pt_80_percent = frappe.get_doc(
		"Payment Schedule", {"parent": doc.name, "payment_term": "80 Percent in 30 Days"}
	)
	assert pt_80_percent.invoice_portion == 80
	data.payment_term = pt_80_percent.name
	calculated_payment = flt(doc.grand_total * pt_80_percent.invoice_portion / 100, precision)
	payment = get_payment_amount(doc, data)
	discount = get_discount_amount(doc, data)
	assert abs(payment - calculated_payment) < epsilson
	assert discount == 0


@pytest.mark.order(12)
def test_discount_payment_term_amounts():
	doc = frappe.get_doc(
		"Sales Invoice", {"customer": "Andromeda Fruit Market", "payment_terms_template": "2% 10 Net 30"}
	)
	precision = frappe.get_precision(doc.doctype, "grand_total")
	epsilson = 1 / pow(10, precision + 1)
	data = frappe._dict({})

	pt_discount = frappe.get_doc(
		"Payment Schedule", {"parent": doc.name, "payment_term": "2% 10 Net 30"}
	)
	assert pt_discount.discount == 2

	data.payment_term = pt_discount.name
	calculated_discount = flt(doc.grand_total * pt_discount.discount / 100, precision)
	payment = get_payment_amount(doc, data)
	assert (
		abs(payment - doc.grand_total) < epsilson and abs(payment - pt_discount.outstanding) < epsilson
	)

	discount = get_discount_amount(doc, data)
	assert abs(discount - calculated_discount) < epsilson


@pytest.mark.order(13)
def test_get_party_details():
	party = "Andromeda Fruit Market"
	doc = frappe.get_doc("Sales Invoice", {"customer": party})
	party_details = get_party_details(doc)
	assert party_details.doctype == "Customer"
	assert party_details.name == party

	party = "HIJ Telecom, Inc"
	doc = frappe.get_doc("Purchase Invoice", {"supplier": party})
	party_details = get_party_details(doc)
	assert party_details.doctype == "Supplier"
	assert party_details.name == party


@pytest.mark.order(20)
def test_receiving_payment_create_payment_entry_basic():
	"""
	The Payment Entry should have the following logic:

	- Paid amount = doc's grand total
	- References table linked to relevant Sales Invoice and allocated amount is the amount of the
	payment term, links to correct payment term
	- Electronic Payment fees accounted for in the taxes table with account head same as account
	specified in Electronic Payment Settings

	Payment Entry accounting:
	- Grand total of $100
	- $2 of provider fees

	| Account                                        | Debit   |  Credit |
	| ---------------------------------------------- | -------:| -------:|
	| 1310 - Accounts Receivable - CFC               |         | $100.00 |
	| 1201 - Primary Checking - CFC                  | $102.00 |         |
	| 5223 - Electronic Payments Provider Fees - CFC |         |   $2.00 |
	"""
	settings = create_electronic_payment_settings("Authorize.net", "Use Payment Entry")
	party = "Andromeda Fruit Market"
	party_type = "Customer"
	template = "Net 14"

	# Add dummy Portal Payment Method with $2.00 service charge
	ppm_name = create_party_payment_method(party, party_type, True)

	# Test single payment term, no discounts, with provider fees
	doc = frappe.get_doc("Sales Invoice", {"customer": party, "payment_terms_template": template})
	data = frappe._dict(
		{
			"ppm_name": ppm_name,
		}
	)
	data.payment_term = frappe.get_value("Payment Schedule", {"parent": doc.name})
	data.additional_charges = calculate_payment_method_fees(doc, data)
	assert data.additional_charges == 2
	transaction_id = str(randint(100000000, 999999999))
	process_electronic_payment(doc, data, transaction_id)
	pe = frappe.get_doc("Payment Entry", {"reference_no": transaction_id})
	pt = frappe.get_doc("Payment Schedule", {"parent": doc.name})
	precision = frappe.get_precision(doc.doctype, "grand_total")

	assert pe.paid_amount == doc.grand_total == pt.paid_amount
	assert pt.outstanding == 0 and frappe.get_value(doc.doctype, doc.name, "outstanding_amount") == 0
	assert pe.references[0].reference_name == doc.name
	assert pe.references[0].payment_term == pt.payment_term
	assert pe.references[0].allocated_amount == pt.payment_amount
	assert pe.taxes and pe.taxes[0].account_head == settings.accepting_fee_account
	assert pe.taxes[0].tax_amount == 2

	gl1 = frappe.get_doc(
		"GL Entry", {"voucher_no": pe.name, "account": "1310 - Accounts Receivable - CFC"}
	)
	assert flt(gl1.credit, precision) == doc.grand_total

	gl2 = frappe.get_doc(
		"GL Entry", {"voucher_no": pe.name, "account": settings.accepting_fee_account}
	)
	assert flt(gl2.credit, precision) == data.additional_charges

	gl3 = frappe.get_doc("GL Entry", {"voucher_no": pe.name, "account": settings.deposit_account})
	assert flt(gl3.debit, precision) == doc.grand_total + data.additional_charges


@pytest.mark.order(21)
def test_receiving_payment_create_payment_entry_multiple_payment_terms():
	"""
	The Payment Entry should have the following logic:

	- Paid amount = payment term payment amount, doc still has outstanding amount
	- References table linked to relevant Sales Invoice and allocated amount is the
	amount of the payment term, links to correct payment term

	Payment Entry accounting:
	- Grand total of $100, first payment term due is for 20% ($20)

	| Account                                        | Debit   |  Credit |
	| ---------------------------------------------- | -------:| -------:|
	| 1310 - Accounts Receivable - CFC               |         |  $20.00 |
	| 1201 - Primary Checking - CFC                  |  $20.00 |         |
	"""
	settings = create_electronic_payment_settings("Authorize.net", "Use Payment Entry")
	party = "Andromeda Fruit Market"
	party_type = "Customer"
	template = "20 in 14 80 in 30"
	term_1 = "20 Percent in 14 Days"
	term_2 = "80 Percent in 30 Days"

	# Add dummy Portal Payment Method with no service charge
	ppm_name = create_party_payment_method(party, party_type, False)

	# Test payment of one of multiple payment terms, no discounts, no provider fees
	doc = frappe.get_doc("Sales Invoice", {"customer": party, "payment_terms_template": template})
	data = frappe._dict(
		{
			"ppm_name": ppm_name,
		}
	)
	data.payment_term = frappe.get_value(
		"Payment Schedule", {"parent": doc.name, "payment_term": term_1}
	)
	data.additional_charges = calculate_payment_method_fees(doc, data)
	assert data.additional_charges == 0
	transaction_id = str(randint(100000000, 999999999))
	process_electronic_payment(doc, data, transaction_id)
	pe = frappe.get_doc("Payment Entry", {"reference_no": transaction_id})
	pt = frappe.get_doc("Payment Schedule", {"parent": doc.name, "payment_term": term_1})
	unpaid_pt = frappe.get_doc("Payment Schedule", {"parent": doc.name, "payment_term": term_2})
	precision = frappe.get_precision(doc.doctype, "grand_total")
	epsilon = 1 / pow(10, precision + 1)

	assert (
		pe.paid_amount == pt.paid_amount
		and abs(pe.paid_amount - flt(pt.invoice_portion / 100 * doc.grand_total, precision)) < epsilon
	)
	assert pt.outstanding == 0 and frappe.get_value(doc.doctype, doc.name, "outstanding_amount") > 0
	assert frappe.get_value(doc.doctype, doc.name, "outstanding_amount") == unpaid_pt.payment_amount
	assert pe.references[0].reference_name == doc.name
	assert pe.references[0].payment_term == pt.payment_term
	assert pe.references[0].allocated_amount == pt.payment_amount

	gl1 = frappe.get_doc(
		"GL Entry", {"voucher_no": pe.name, "account": "1310 - Accounts Receivable - CFC"}
	)
	assert flt(gl1.credit, precision) == flt(pt.invoice_portion / 100 * doc.grand_total, precision)

	gl2 = frappe.get_doc("GL Entry", {"voucher_no": pe.name, "account": settings.deposit_account})
	assert flt(gl2.debit, precision) == flt(gl1.credit, precision)


@pytest.mark.order(22)
def test_receiving_payment_create_payment_entry_discount():
	"""
	The Payment Entry should have the following logic:

	- Paid amount = Discounted payment amount
	- References table linked to relevant Sales Invoice and allocated amount is the non-
	discounted amount of the payment term, links to correct payment term
	- Electronic Payment fees accounted for in the taxes table with account head same as account
	specified in Electronic Payment Settings
	- Discounts accounted for in the deductions table (entries are positive for debits, negative
	for credits to given account head)

	Payment Entry accounting, assuming no discount allocation goes to taxes):
	- Grand total of $115
	- Item total of $100
	- 2% discount of $2.30, all allocated to items
	- Taxes of $10 for Freight and Forwarding, $5 to Sales Expenses
	- $2 of provider fees

	| Account                                        | Debit   |  Credit |
	| ---------------------------------------------- | -------:| -------:|
	| 1310 - Accounts Receivable - CFC               |         | $115.00 |
	| 1201 - Primary Checking - CFC                  | $114.70 |         |
	| 4110 - Sales - CFC                             |   $2.30 |         |
	| 5205 - Freight and Forwarding Charges - CFC    |         |         |
	| 5214 - Sales Expenses - CFC                    |         |         |
	| 5223 - Electronic Payments Provider Fees - CFC |         |   $2.00 |


	Payment Entry accounting, assuming discount gets allocated to taxes:
	- Grand total of $115
	- Item total of $100
	- 2% discount of $2.30, $2.00 allocated to items, remaining $0.30 split to taxes by relative amount
	- Taxes of $10 for Freight and Forwarding ($0.20 of discount), $5 to Sales Expenses ($0.10 of discount)
	- $2 of provider fees

	| Account                                        | Debit   |  Credit |
	| ---------------------------------------------- | -------:| -------:|
	| 1310 - Accounts Receivable - CFC               |         | $115.00 |
	| 1201 - Primary Checking - CFC                  | $114.70 |         |
	| 4110 - Sales - CFC                             |   $2.00 |         |
	| 5205 - Freight and Forwarding Charges - CFC    |   $0.20 |         |
	| 5214 - Sales Expenses - CFC                    |   $0.10 |         |
	| 5223 - Electronic Payments Provider Fees - CFC |         |   $2.00 |
	"""
	settings = create_electronic_payment_settings("Authorize.net", "Use Payment Entry")
	party = "Andromeda Fruit Market"
	party_type = "Customer"
	template = "2% 10 Net 30"

	# Add dummy Portal Payment Method with $2.00 service charge
	ppm_name = create_party_payment_method(party, party_type, True)

	# Test Discount Payment Term with provider fees
	doc = frappe.get_doc("Sales Invoice", {"customer": party, "payment_terms_template": template})
	data = frappe._dict(
		{
			"ppm_name": ppm_name,
		}
	)
	data.payment_term = frappe.get_value("Payment Schedule", {"parent": doc.name})
	data.additional_charges = calculate_payment_method_fees(doc, data)
	assert data.additional_charges == 2
	transaction_id = str(randint(100000000, 999999999))
	process_electronic_payment(doc, data, transaction_id)
	pe = frappe.get_doc("Payment Entry", {"reference_no": transaction_id})
	pt = frappe.get_doc("Payment Schedule", {"parent": doc.name})
	precision = frappe.get_precision(doc.doctype, "grand_total")
	epsilon = 1 / pow(10, precision + 1)

	assert abs(pe.paid_amount - flt(doc.grand_total - pt.discounted_amount, precision)) < epsilon
	assert pt.outstanding == 0 and frappe.get_value(doc.doctype, doc.name, "outstanding_amount") == 0
	assert pe.references[0].reference_name == doc.name
	assert pe.references[0].payment_term == pt.payment_term
	assert pe.references[0].allocated_amount == pt.payment_amount == doc.grand_total
	assert pe.deductions and pe.deductions[0].account == settings.accepting_payment_discount_account
	assert (
		abs(flt(pt.discounted_amount, precision) - flt(pe.deductions[0].amount, precision)) < epsilon
	)
	assert pe.taxes and pe.taxes[0].account_head == settings.accepting_fee_account
	assert pe.taxes[0].tax_amount == 2

	gl1 = frappe.get_doc(
		"GL Entry", {"voucher_no": pe.name, "account": "1310 - Accounts Receivable - CFC"}
	)
	assert flt(gl1.credit, precision) == doc.grand_total

	gl2 = frappe.get_doc(
		"GL Entry", {"voucher_no": pe.name, "account": settings.accepting_fee_account}
	)
	assert flt(gl2.credit, precision) == data.additional_charges

	gl3 = frappe.get_doc(
		"GL Entry", {"voucher_no": pe.name, "account": settings.accepting_payment_discount_account}
	)
	assert flt(gl3.debit, precision) == flt(pt.discounted_amount, precision)

	gl4 = frappe.get_doc("GL Entry", {"voucher_no": pe.name, "account": settings.deposit_account})
	assert flt(gl4.debit, precision) == doc.grand_total + data.additional_charges - flt(
		pt.discounted_amount, precision
	)

	# Cancel the Payment Entry
	pe.cancel()
	assert (
		frappe.get_value(doc.doctype, doc.name, "outstanding_amount") > 0
		and frappe.get_value("Payment Schedule", {"parent": doc.name}, "outstanding") > 0
	)

	# Update Accounts Settings to allocate discount to taxes
	frappe.db.set_single_value("Accounts Settings", "book_tax_discount_loss", 1)
	process_electronic_payment(doc, data, transaction_id)
	pe = frappe.get_doc("Payment Entry", {"reference_no": transaction_id, "docstatus": 1})
	pt = frappe.get_doc("Payment Schedule", {"parent": doc.name})

	assert pe.deductions and len(pe.deductions) == 3
	discount_percent = pt.discount / 100
	discount_dict = {discount.account: discount.amount for discount in pe.deductions}
	tax_amount_dict = {
		tax.account_head: tax.base_tax_amount_after_discount_amount for tax in doc.taxes
	}

	assert (
		abs(
			sum(discount.amount for discount in pe.deductions)
			- flt(discount_percent * doc.grand_total, precision)
		)
		< epsilon
	)
	for tax_acct, tax_amount in tax_amount_dict.items():
		assert abs(flt(discount_percent * tax_amount, precision) - discount_dict[tax_acct]) < epsilon
	assert (
		abs(
			discount_dict[settings.accepting_payment_discount_account]
			- flt(discount_percent * doc.base_net_total, precision)
		)
		< epsilon
	)

	gl1 = frappe.get_doc(
		"GL Entry", {"voucher_no": pe.name, "account": "1310 - Accounts Receivable - CFC"}
	)
	assert flt(gl1.credit, precision) == doc.grand_total

	gl2 = frappe.get_doc(
		"GL Entry", {"voucher_no": pe.name, "account": settings.accepting_fee_account}
	)
	assert flt(gl2.credit, precision) == data.additional_charges

	gl3 = frappe.get_doc("GL Entry", {"voucher_no": pe.name, "account": settings.deposit_account})
	assert flt(gl3.debit, precision) == doc.grand_total + data.additional_charges - flt(
		pt.discounted_amount, precision
	)

	for row in pe.deductions:
		gl_tax = frappe.get_doc("GL Entry", {"voucher_no": pe.name, "account": row.account})
		assert flt(gl_tax.debit, precision) == row.amount

	# Revert Accounts Settings change
	frappe.db.set_single_value("Accounts Settings", "book_tax_discount_loss", 0)


@pytest.mark.order(23)
def test_receiving_payment_create_journal_entry_basic():
	"""
	Journal Entry accounting:
	- Grand total of $100
	- $2 of provider fees

	| Account                                        | Debit   |  Credit |
	| ---------------------------------------------- | -------:| -------:|
	| 1310 - Accounts Receivable - CFC               |         | $100.00 |
	| 1320 - Electronic Payments Receivable - CFC    | $102.00 |         |
	| 5223 - Electronic Payments Provider Fees - CFC |         |   $2.00 |
	"""
	settings = create_electronic_payment_settings("Authorize.net")
	party = "Betelgeuse Bakery Suppliers"
	party_type = "Customer"
	template = "Net 14"

	# Add dummy Portal Payment Method with $2.00 service charge
	ppm_name = create_party_payment_method(party, party_type, True)

	# Test single payment term, no discounts, with provider fees
	doc = frappe.get_doc("Sales Invoice", {"customer": party, "payment_terms_template": template})
	data = frappe._dict(
		{
			"ppm_name": ppm_name,
		}
	)
	data.payment_term = frappe.get_value("Payment Schedule", {"parent": doc.name})
	data.additional_charges = calculate_payment_method_fees(doc, data)
	assert data.additional_charges == 2
	transaction_id = str(randint(100000000, 999999999))
	process_electronic_payment(doc, data, transaction_id)
	je = frappe.get_last_doc("Journal Entry")
	pt = frappe.get_doc("Payment Schedule", {"parent": doc.name})
	precision = frappe.get_precision(doc.doctype, "grand_total")

	assert doc.grand_total == pt.paid_amount
	assert pt.outstanding == 0 and frappe.get_value(doc.doctype, doc.name, "outstanding_amount") == 0
	assert je.accounts[0].reference_name == doc.name
	assert je.accounts[0].electronic_payments_payment_term == pt.name

	gl1 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": "1310 - Accounts Receivable - CFC"}
	)
	assert flt(gl1.credit, precision) == doc.grand_total

	gl2 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": settings.accepting_fee_account}
	)
	assert flt(gl2.credit, precision) == data.additional_charges

	gl3 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": settings.accepting_clearing_account}
	)
	assert flt(gl3.debit, precision) == doc.grand_total + data.additional_charges


@pytest.mark.order(24)
def test_receiving_payment_create_journal_entry_multiple_payment_terms():
	"""
	Journal Entry accounting:
	- Grand total of $100, first payment term due is for 20% ($20)

	| Account                                        | Debit   |  Credit |
	| ---------------------------------------------- | -------:| -------:|
	| 1310 - Accounts Receivable - CFC               |         |  $20.00 |
	| 1320 - Electronic Payments Receivable - CFC    |  $20.00 |         |
	"""
	settings = create_electronic_payment_settings("Authorize.net")
	party = "Betelgeuse Bakery Suppliers"
	party_type = "Customer"
	template = "20 in 14 80 in 30"
	term_1 = "20 Percent in 14 Days"
	term_2 = "80 Percent in 30 Days"

	# Add dummy Portal Payment Method with no service charge
	ppm_name = create_party_payment_method(party, party_type, False)

	# Test payment of one of multiple payment terms, no discounts, no provider fees
	doc = frappe.get_doc("Sales Invoice", {"customer": party, "payment_terms_template": template})
	data = frappe._dict(
		{
			"ppm_name": ppm_name,
		}
	)
	data.payment_term = frappe.get_value(
		"Payment Schedule", {"parent": doc.name, "payment_term": term_1}
	)
	data.additional_charges = calculate_payment_method_fees(doc, data)
	assert data.additional_charges == 0
	transaction_id = str(randint(100000000, 999999999))
	process_electronic_payment(doc, data, transaction_id)
	je = frappe.get_last_doc("Journal Entry")
	pt = frappe.get_doc("Payment Schedule", {"parent": doc.name, "payment_term": term_1})
	unpaid_pt = frappe.get_doc("Payment Schedule", {"parent": doc.name, "payment_term": term_2})
	precision = frappe.get_precision(doc.doctype, "grand_total")
	epsilon = 1 / pow(10, precision + 1)

	assert abs(pt.paid_amount - flt(pt.invoice_portion / 100 * doc.grand_total, precision)) < epsilon
	assert pt.outstanding == 0 and frappe.get_value(doc.doctype, doc.name, "outstanding_amount") > 0
	assert frappe.get_value(doc.doctype, doc.name, "outstanding_amount") == unpaid_pt.payment_amount
	assert je.accounts[0].reference_name == doc.name
	assert je.accounts[0].electronic_payments_payment_term == pt.name

	gl1 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": "1310 - Accounts Receivable - CFC"}
	)
	assert flt(gl1.credit, precision) == flt(pt.invoice_portion / 100 * doc.grand_total, precision)

	gl2 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": settings.accepting_clearing_account}
	)
	assert flt(gl2.debit, precision) == flt(gl1.credit, precision)


@pytest.mark.order(25)
def test_receiving_payment_create_journal_entry_discount():
	"""
	Journal Entry accounting, assuming no discount allocation goes to taxes):
	- Grand total of $115
	- Item total of $100
	- 2% discount of $2.30, all allocated to items
	- Taxes of $10 for Freight and Forwarding, $5 to Sales Expenses
	- $2 of provider fees

	| Account                                        | Debit   |  Credit |
	| ---------------------------------------------- | -------:| -------:|
	| 1310 - Accounts Receivable - CFC               |         | $115.00 |
	| 1320 - Electronic Payments Receivable - CFC    | $114.70 |         |
	| 4110 - Sales - CFC                             |   $2.30 |         |
	| 5205 - Freight and Forwarding Charges - CFC    |         |         |
	| 5214 - Sales Expenses - CFC                    |         |         |
	| 5223 - Electronic Payments Provider Fees - CFC |         |   $2.00 |


	Journal Entry accounting, assuming discount gets allocated to taxes:
	- Grand total of $115
	- Item total of $100
	- 2% discount of $2.30, $2.00 allocated to items, remaining $0.30 split to taxes by relative amount
	- Taxes of $10 for Freight and Forwarding ($0.20 of discount), $5 to Sales Expenses ($0.10 of discount)
	- $2 of provider fees

	| Account                                        | Debit   |  Credit |
	| ---------------------------------------------- | -------:| -------:|
	| 1310 - Accounts Receivable - CFC               |         | $115.00 |
	| 1320 - Electronic Payments Receivable - CFC    | $114.70 |         |
	| 4110 - Sales - CFC                             |   $2.00 |         |
	| 5205 - Freight and Forwarding Charges - CFC    |   $0.20 |         |
	| 5214 - Sales Expenses - CFC                    |   $0.10 |         |
	| 5223 - Electronic Payments Provider Fees - CFC |         |   $2.00 |
	"""
	settings = create_electronic_payment_settings("Authorize.net")
	party = "Betelgeuse Bakery Suppliers"
	party_type = "Customer"
	template = "2% 10 Net 30"

	# Add dummy Portal Payment Method with $2.00 service charge
	ppm_name = create_party_payment_method(party, party_type, True)

	# Test Discount Payment Term with provider fees
	doc = frappe.get_doc("Sales Invoice", {"customer": party, "payment_terms_template": template})
	data = frappe._dict(
		{
			"ppm_name": ppm_name,
		}
	)
	data.payment_term = frappe.get_value("Payment Schedule", {"parent": doc.name})
	data.additional_charges = calculate_payment_method_fees(doc, data)
	assert data.additional_charges == 2
	transaction_id = str(randint(100000000, 999999999))
	process_electronic_payment(doc, data, transaction_id)
	je = frappe.get_last_doc("Journal Entry")
	pt = frappe.get_doc("Payment Schedule", {"parent": doc.name})
	precision = frappe.get_precision(doc.doctype, "grand_total")
	epsilon = 1 / pow(10, precision + 1)

	assert pt.outstanding == 0 and frappe.get_value(doc.doctype, doc.name, "outstanding_amount") == 0
	assert je.accounts[0].reference_name == doc.name
	assert je.accounts[0].electronic_payments_payment_term == pt.name
	assert len(je.accounts) == 4

	gl1 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": "1310 - Accounts Receivable - CFC"}
	)
	assert flt(gl1.credit, precision) == doc.grand_total

	gl2 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": settings.accepting_fee_account}
	)
	assert flt(gl2.credit, precision) == data.additional_charges

	gl3 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": settings.accepting_payment_discount_account}
	)
	assert flt(gl3.debit, precision) == flt(pt.discounted_amount, precision)

	gl4 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": settings.accepting_clearing_account}
	)
	assert flt(gl4.debit, precision) == doc.grand_total + data.additional_charges - flt(
		pt.discounted_amount, precision
	)

	# Cancel the Payment Entry
	je.cancel()
	assert (
		frappe.get_value(doc.doctype, doc.name, "outstanding_amount") > 0
		and frappe.get_value("Payment Schedule", {"parent": doc.name}, "outstanding") > 0
	)

	# Update Accounts Settings to allocate discount to taxes
	frappe.db.set_single_value("Accounts Settings", "book_tax_discount_loss", 1)
	process_electronic_payment(doc, data, transaction_id)
	je = frappe.get_last_doc("Journal Entry")
	pt = frappe.get_doc("Payment Schedule", {"parent": doc.name})

	assert len(je.accounts) == 6
	discount_percent = pt.discount / 100
	tax_amount_dict = {
		tax.account_head: tax.base_tax_amount_after_discount_amount for tax in doc.taxes
	}
	tax_amount_dict.update({settings.accepting_payment_discount_account: doc.base_net_total})

	gl1 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": "1310 - Accounts Receivable - CFC"}
	)
	assert flt(gl1.credit, precision) == doc.grand_total

	gl2 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": settings.accepting_fee_account}
	)
	assert flt(gl2.credit, precision) == data.additional_charges

	gl3 = frappe.get_doc(
		"GL Entry", {"voucher_no": je.name, "account": settings.accepting_clearing_account}
	)
	assert flt(gl3.debit, precision) == doc.grand_total + data.additional_charges - flt(
		pt.discounted_amount, precision
	)

	for tax_acct, tax_amount in tax_amount_dict.items():
		gl_tax = frappe.get_doc("GL Entry", {"voucher_no": je.name, "account": tax_acct})
		assert (
			abs(flt(gl_tax.debit, precision) - flt(discount_percent * tax_amount, precision)) < epsilon
		)

	# Revert Accounts Settings change
	frappe.db.set_single_value("Accounts Settings", "book_tax_discount_loss", 0)


@pytest.mark.order(30)
def test_sending_payment_create_payment_entry_multiple_payment_terms():
	pass


@pytest.mark.order(31)
def test_sending_payment_create_payment_entry_discount():
	pass


@pytest.mark.order(32)
def test_sending_payment_create_journal_entry_multiple_payment_terms():
	pass


@pytest.mark.order(31)
def test_sending_payment_create_journal_entry_discount():
	pass
