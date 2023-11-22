import datetime
import random
import types
import os

import frappe
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
from erpnext.setup.utils import enable_all_roles_and_domains, set_defaults_for_tests  # noqa: F401
from erpnext.accounts.doctype.account.account import update_account_number

from electronic_payments.tests.fixtures import suppliers, tax_authority, employees, customers


def before_test():
	frappe.clear_cache()
	today = frappe.utils.getdate()
	setup_complete(
		{
			"currency": "USD",
			"full_name": "Administrator",
			"company_name": "Chelsea Fruit Co",
			"timezone": "America/New_York",
			"company_abbr": "CFC",
			"domains": ["Distribution"],
			"country": "United States",
			"fy_start_date": today.replace(month=1, day=1).isoformat(),
			"fy_end_date": today.replace(month=12, day=31).isoformat(),
			"language": "english",
			"company_tagline": "Chelsea Fruit Co",
			"email": "support@agritheory.dev",
			"password": "admin",
			"chart_of_accounts": "Standard with Numbers",
			"bank_account": "Primary Checking",
		}
	)
	# enable_all_roles_and_domains()
	set_defaults_for_tests()
	frappe.db.commit()
	create_test_data()
	for modu in frappe.get_all("Module Onboarding"):
		frappe.db.set_value("Module Onboarding", modu, "is_complete", 1)
	frappe.set_value("Website Settings", "Website Settings", "home_page", "login")
	frappe.db.commit()


def create_test_data():
	today = frappe.utils.getdate()
	setup_accounts()
	settings = frappe._dict(
		{
			"day": today.replace(month=1, day=1),
			"company": frappe.defaults.get_defaults().get("company"),
			"company_account": frappe.get_value(
				"Account",
				{
					"account_type": "Bank",
					"company": frappe.defaults.get_defaults().get("company"),
					"is_group": 0,
				},
			),
			"warehouse": frappe.get_value(
				"Warehouse",
				{
					"warehouse_name": "Finished Goods",
					"company": frappe.defaults.get_defaults().get("company"),
				},
			),
		}
	)
	create_bank_and_bank_account(settings)
	create_electronic_payment_settings(settings)
	create_payment_terms_templates(settings)
	create_suppliers(settings)
	create_customers(settings)
	create_items(settings)
	create_invoices(settings)
	config_expense_claim(settings)
	create_sales_invoices(settings)
	create_employees(settings)
	curate_portal_and_ecommerce_settings(settings)
	for month in range(1, 13):
		create_payroll_journal_entry(settings)
		settings.day = settings.day.replace(month=month)


def create_bank_and_bank_account(settings):
	if not frappe.db.exists("Mode of Payment", "ACH/EFT"):
		mop = frappe.new_doc("Mode of Payment")
		mop.mode_of_payment = "ACH/EFT"
		mop.enabled = 1
		mop.type = "Electronic"
		mop.append(
			"accounts",
			{"company": settings.company, "default_account": settings.company_account},
		)
		mop.save()

	wire_transfer = frappe.get_doc("Mode of Payment", "Wire Transfer")
	wire_transfer.type = "General"
	wire_transfer.append(
		"accounts", {"company": settings.company, "default_account": settings.company_account}
	)
	wire_transfer.save()

	credit_card = frappe.get_doc("Mode of Payment", "Credit Card")
	credit_card.type = "General"
	credit_card.append(
		"accounts", {"company": settings.company, "default_account": settings.company_account}
	)
	credit_card.save()

	bank_draft = frappe.get_doc("Mode of Payment", "Bank Draft")
	bank_draft.type = "General"
	bank_draft.append(
		"accounts", {"company": settings.company, "default_account": settings.company_account}
	)
	bank_draft.save()

	check_mop = frappe.get_doc("Mode of Payment", "Check")
	check_mop.type = "Bank"
	check_mop.append(
		"accounts", {"company": settings.company, "default_account": settings.company_account}
	)
	check_mop.save()

	if not frappe.db.exists("Bank", "Local Bank"):
		bank = frappe.new_doc("Bank")
		bank.bank_name = "Local Bank"
		bank.aba_number = "07200091"
		bank.save()

	if not frappe.db.exists("Bank Account", "Primary Checking - Local Bank"):
		bank_account = frappe.new_doc("Bank Account")
		bank_account.account_name = "Primary Checking"
		bank_account.bank = bank.name
		bank_account.is_default = 1
		bank_account.is_company_account = 1
		bank_account.company = settings.company
		bank_account.account = settings.company_account
		bank_account.check_number = 2500
		bank_account.company_ach_id = "1381655417"
		bank_account.bank_account_no = "072000915"
		bank_account.branch_code = "07200091"
		bank_account.save()

	doc = frappe.new_doc("Journal Entry")
	doc.posting_date = settings.day
	doc.voucher_type = "Opening Entry"
	doc.company = settings.company
	opening_balance = 50000.00
	doc.append(
		"accounts",
		{"account": settings.company_account, "debit_in_account_currency": opening_balance},
	)
	retained_earnings = frappe.get_value(
		"Account", {"account_name": "Retained Earnings", "company": settings.company}
	)
	doc.append(
		"accounts",
		{"account": retained_earnings, "credit_in_account_currency": opening_balance},
	)
	doc.save()
	doc.submit()


def setup_accounts():
	frappe.rename_doc(
		"Account",
		"1000 - Application of Funds (Assets) - CFC",
		"1000 - Assets - CFC",
		force=True,
	)
	frappe.rename_doc(
		"Account",
		"2000 - Source of Funds (Liabilities) - CFC",
		"2000 - Liabilities - CFC",
		force=True,
	)
	frappe.rename_doc(
		"Account", "1310 - Debtors - CFC", "1310 - Accounts Receivable - CFC", force=True
	)
	frappe.rename_doc(
		"Account", "2110 - Creditors - CFC", "2110 - Accounts Payable - CFC", force=True
	)
	update_account_number("1110 - Cash - CFC", "Petty Cash", account_number="1110")
	update_account_number("Primary Checking - CFC", "Primary Checking", account_number="1201")

	rca = frappe.new_doc("Account")  # receivable clearing account
	rca.account_name = "Electronic Payments Receivable"
	rca.account_number = "1320"
	rca.account_type = "Receivable"
	rca.parent_account = "1300 - Accounts Receivable - CFC"
	rca.currency = "USD"
	rca.company = frappe.defaults.get_defaults().get("company")
	rca.save()

	pca = frappe.new_doc("Account")  # payable clearing account
	pca.account_name = "Electronic Payments Payable"
	pca.account_number = "2130"
	pca.account_type = "Payable"
	pca.parent_account = "2100 - Accounts Payable - CFC"
	pca.currency = "USD"
	pca.company = frappe.defaults.get_defaults().get("company")
	pca.save()

	fee = frappe.new_doc("Account")  # provider fee expense account
	fee.account_name = "Electronic Payments Provider Fees"
	fee.account_number = "5223"
	# fee.account_type = ""
	fee.parent_account = "5200 - Indirect Expenses - CFC"
	fee.currency = "USD"
	fee.company = frappe.defaults.get_defaults().get("company")
	fee.save()


def create_payment_terms_templates(settings):
	if not frappe.db.exists("Payment Terms Template", "Net 30"):
		doc = frappe.new_doc("Payment Terms Template")
		doc.template_name = "Net 30"
		doc.append(
			"terms",
			{
				"payment_term": "Net 30",
				"invoice_portion": 100,
				"due_date_based_on": "Day(s) after invoice date",
				"credit_days": 30,
			},
		)
		doc.save()
	if not frappe.db.exists("Payment Terms Template", "Due on Receipt"):
		doc = frappe.new_doc("Payment Terms Template")
		doc.template_name = "Due on Receipt"
		doc.append(
			"terms",
			{
				"payment_term": "Due on Receipt",
				"invoice_portion": 100,
				"due_date_based_on": "Day(s) after invoice date",
				"credit_days": 0,
			},
		)
		doc.save()
	if not frappe.db.exists("Payment Terms Template", "Net 14"):
		doc = frappe.new_doc("Payment Terms Template")
		doc.template_name = "Net 14"
		doc.append(
			"terms",
			{
				"payment_term": "Net 14",
				"invoice_portion": 100,
				"due_date_based_on": "Day(s) after invoice date",
				"credit_days": 14,
			},
		)
		doc.save()


def create_suppliers(settings):
	addresses = frappe._dict({})
	for supplier in suppliers + tax_authority:
		biz = frappe.new_doc("Supplier")
		biz.supplier_name = supplier[0]
		biz.supplier_group = "Services"
		biz.country = "United States"
		biz.supplier_default_mode_of_payment = supplier[2]
		if biz.supplier_default_mode_of_payment == "ACH/EFT":
			biz.bank = "Local Bank"
			biz.bank_account = "123456789"
		biz.currency = "USD"
		biz.default_price_list = "Standard Buying"
		biz.payment_terms = supplier[4]
		biz.save()

		addr = frappe.new_doc("Address")
		addr.address_title = f"{supplier[0]} - {supplier[5]['city']}"
		addr.address_type = "Billing"
		addr.address_line1 = supplier[5]["address_line1"]
		addr.city = supplier[5]["city"]
		addr.state = supplier[5]["state"]
		addr.country = supplier[5]["country"]
		addr.pincode = supplier[5]["pincode"]
		addr.append("links", {"link_doctype": "Supplier", "link_name": supplier[0]})
		addr.save()

	addr = frappe.new_doc("Address")
	addr.address_type = "Billing"
	addr.address_title = "HIJ Telecom - Burlingame"
	addr.address_line1 = "167 Auto Terrace"
	addr.city = "Burlingame"
	addr.state = "ME"
	addr.country = "United States"
	addr.pincode = "79749"
	addr.append("links", {"link_doctype": "Supplier", "link_name": "HIJ Telecom, Inc"})
	addr.save()


def create_customers(settings):
	for customer in customers:
		cust = frappe.new_doc("Customer")
		cust.customer_name = customer[0]
		cust.customer_type = "Company"
		cust.customer_group = "Commercial"
		cust.territory = "All Territories"
		cust.tax_id = "04-" + f"{random.randint(100,99999):05d}"  # Tax ID number
		if customer[0] == "Cassiopeia Restaurant Group":
			# Set a credit limit and add a Portal Payment Method subject to the credit limit
			cust.append(
				"credit_limits",
				{"company": settings.company, "credit_limit": 300, "bypass_credit_limit_check": 1},
			)
		cust.save()

		addr = frappe.new_doc("Address")
		addr.address_title = f"{customer[0]} - {customer[1]['city']}"
		addr.address_type = "Shipping"
		addr.address_line1 = customer[1]["address_line1"]
		addr.city = customer[1]["city"]
		addr.state = customer[1]["state"]
		addr.country = customer[1]["country"]
		addr.pincode = customer[1]["pincode"]
		addr.append("links", {"link_doctype": "Customer", "link_name": cust.name})
		addr.save()

		user = frappe.new_doc("User")
		user.first_name = customer[2].split(" ")[0]
		user.last_name = customer[2].split(" ")[1]
		user.username = customer[3]
		user.time_zone = "America/New_York"
		user.email = customer[3]
		user.user_type = "System User"
		user.send_welcome_email = 0
		user.append("roles", {"role": "Customer"})
		user.save()

		contact = frappe.new_doc("Contact")
		contact.first_name = user.first_name
		contact.last_name = user.last_name
		contact.user = user.name
		contact.address = addr.name
		contact.append("email_ids", {"email_id": user.name, "is_primary": 1})
		contact.append("links", {"link_doctype": "Customer", "link_name": cust.name})
		contact.save()


def create_items(settings):
	for supplier in suppliers + tax_authority:
		item = frappe.new_doc("Item")
		item.item_code = item.item_name = supplier[1]
		item.item_group = "Services"
		item.stock_uom = "Nos"
		item.maintain_stock = 0
		(
			item.is_sales_item,
			item.is_sub_contracted_item,
			item.include_item_in_manufacturing,
		) = (0, 0, 0)
		item.grant_commission = 0
		item.is_purchase_item = 1
		item.append("supplier_items", {"supplier": supplier[0]})
		item.append(
			"item_defaults",
			{
				"company": settings.company,
				"default_warehouse": "",
				"default_supplier": supplier[0],
			},
		)
		item.save()

	fruits = [
		"Cloudberry",
		"Gooseberry",
		"Damson plum",
		"Tayberry",
		"Hairless rambutan",
		"Kaduka lime",
		"Hackberry",
	]

	for fruit in fruits:
		item = frappe.new_doc("Item")
		item.item_code, item.item_name = fruit.title(), fruit.title()
		item.item_group = "Products"
		item.stock_uom = "Box"
		item.maintain_stock = 1
		item.include_item_in_manufacturing = 0
		item.valuation_rate = round(random.uniform(5, 15), 2)
		item.default_warehouse = settings["warehouse"]
		item.description = fruit + " - Box"  # Description
		item.default_material_request_type = "Purchase"
		item.valuation_method = "FIFO"
		item.is_purchase_item = 1
		# item.append("supplier_items", {"supplier": random.choice(suppliers)})
		item.save()
		buying_item_price = frappe.new_doc("Item Price")
		buying_item_price.item_code = item.item_code
		buying_item_price.uom = item.stock_uom
		buying_item_price.price_list = "Standard Buying"
		buying_item_price.buying = 1
		buying_item_price.valid_from = "2018-1-1"
		buying_item_price.price_list_rate = round(random.uniform(5, 15), 2)
		buying_item_price.save()
		selling_item_price = frappe.new_doc("Item Price")
		selling_item_price.item_code = item.item_code
		selling_item_price.uom = item.stock_uom
		selling_item_price.price_list = "Standard Selling"
		selling_item_price.selling = 1
		selling_item_price.valid_from = "2018-1-1"
		selling_item_price.price_list_rate = round(buying_item_price.price_list_rate * 1.5, 2)
		selling_item_price.save()


def create_invoices(settings):
	# first month - already paid
	for supplier in suppliers:
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = settings.company
		pi.set_posting_time = 1
		pi.posting_date = settings.day
		pi.supplier = supplier[0]
		pi.append(
			"items",
			{
				"item_code": supplier[1],
				"rate": supplier[3],
				"qty": 1,
			},
		)
		pi.save()
		pi.submit()
	# two electric meters / test invoice aggregation
	pi = frappe.new_doc("Purchase Invoice")
	pi.company = settings.company
	pi.set_posting_time = 1
	pi.posting_date = settings.day
	pi.supplier = suppliers[0][0]
	pi.append(
		"items",
		{
			"item_code": suppliers[0][1],
			"rate": 75.00,
			"qty": 1,
		},
	)
	pi.save()
	pi.submit()

	# two phone bills / test address splitting
	pi = frappe.new_doc("Purchase Invoice")
	pi.company = settings.company
	pi.set_posting_time = 1
	pi.posting_date = settings.day
	pi.supplier = suppliers[4][0]
	pi.append(
		"items",
		{
			"item_code": suppliers[4][1],
			"rate": 122.50,
			"qty": 1,
		},
	)
	pi.supplier_address = "HIJ Telecom - Burlingame-Billing"
	pi.save()
	pi.submit()

	# second month - unpaid
	next_day = settings.day + datetime.timedelta(days=31)

	for supplier in suppliers:
		pi = frappe.new_doc("Purchase Invoice")
		pi.company = settings.company
		pi.set_posting_time = 1
		pi.posting_date = next_day
		pi.supplier = supplier[0]
		pi.append(
			"items",
			{
				"item_code": supplier[1],
				"rate": supplier[3],
				"qty": 1,
			},
		)
		pi.save()
		pi.submit()
	# two electric meters / test invoice aggregation
	pi = frappe.new_doc("Purchase Invoice")
	pi.company = settings.company
	pi.set_posting_time = 1
	pi.posting_date = next_day
	pi.supplier = suppliers[0][0]
	pi.append(
		"items",
		{
			"item_code": suppliers[0][1],
			"rate": 75.00,
			"qty": 1,
		},
	)
	pi.save()
	pi.submit()

	# two phone bills / test address splitting
	pi = frappe.new_doc("Purchase Invoice")
	pi.company = settings.company
	pi.set_posting_time = 1
	pi.posting_date = settings.day
	pi.supplier = suppliers[4][0]
	pi.append(
		"items",
		{
			"item_code": suppliers[4][1],
			"rate": 122.50,
			"qty": 1,
		},
	)
	pi.supplier_address = "HIJ Telecom - Burlingame-Billing"
	pi.save()
	pi.submit()

	# test on-hold invoice
	pi = frappe.new_doc("Purchase Invoice")
	pi.company = settings.company
	pi.set_posting_time = 1
	pi.posting_date = settings.day
	pi.supplier = suppliers[1][0]
	pi.append(
		"items",
		{
			"item_code": suppliers[1][1],
			"rate": 4000.00,
			"qty": 1,
		},
	)
	pi.on_hold = 1
	pi.release_date = settings.day + datetime.timedelta(days=60)
	pi.hold_comment = "Testing for on hold invoices"
	pi.validate_release_date = types.MethodType(
		validate_release_date, pi
	)  # allow date to be backdated for testing
	pi.save()
	pi.submit()


def validate_release_date(self):
	pass


def config_expense_claim(settings):
	try:
		travel_expense_account = frappe.get_value(
			"Account", {"account_name": "Travel Expenses", "company": settings.company}
		)
		travel = frappe.get_doc("Expense Claim Type", "Travel")
		travel.append(
			"accounts", {"company": settings.company, "default_account": travel_expense_account}
		)
		travel.save()
	except:  # noqa E722
		pass

	payroll_payable = frappe.db.get_value(
		"Account", {"account_name": "Payroll Payable", "company": settings.company}
	)
	if payroll_payable:
		frappe.db.set_value("Account", payroll_payable, "account_type", "Payable")

	if frappe.db.exists("Account", {"account_name": "Payroll Taxes", "company": settings.company}):
		return
	pta = frappe.new_doc("Account")
	pta.account_name = "Payroll Taxes"
	pta.account_number = (
		max(
			int(a.account_number or 1)
			for a in frappe.get_all("Account", {"is_group": 0}, ["account_number"])
		)
		+ 1
	)
	pta.account_type = "Expense Account"
	pta.company = settings.company
	pta.parent_account = frappe.get_value(
		"Account", {"account_name": "Indirect Expenses", "company": settings.company}
	)
	pta.save()


def create_employees(settings):
	for employee_number, employee in enumerate(employees, start=10):
		emp = frappe.new_doc("Employee")
		emp.first_name = employee[0].split(" ")[0]
		emp.last_name = employee[0].split(" ")[1]
		emp.employment_type = "Full-time"
		emp.company = settings.company
		emp.status = "Active"
		emp.gender = employee[1]
		emp.date_of_birth = employee[2]
		emp.date_of_joining = employee[3]
		emp.mode_of_payment = "Check" if employee_number % 3 == 0 else "ACH/EFT"
		emp.mode_of_payment = "Cash" if employee_number == 10 else emp.mode_of_payment
		emp.expense_approver = "Administrator"
		if emp.mode_of_payment == "ACH/EFT":
			emp.bank = "Local Bank"
			emp.bank_account = f"{employee_number}12345"
		emp.save()


def create_expense_claim(settings):
	cost_center = frappe.get_value("Company", settings.company, "cost_center")
	payable_acct = frappe.get_value("Company", settings.company, "default_payable_account")
	# first month - paid
	ec = frappe.new_doc("Expense Claim")
	ec.employee = "HR-EMP-00002"
	ec.expense_approver = "Administrator"
	ec.approval_status = "Approved"
	ec.append(
		"expenses",
		{
			"expense_date": settings.day,
			"expense_type": "Travel",
			"amount": 50.0,
			"sanctioned_amount": 50.0,
			"cost_center": cost_center,
		},
	)
	ec.posting_date = settings.day
	ec.company = settings.company
	ec.payable_account = payable_acct
	ec.save()
	ec.submit()
	# second month - open
	next_day = settings.day + datetime.timedelta(days=31)

	ec = frappe.new_doc("Expense Claim")
	ec.employee = "HR-EMP-00002"
	ec.expense_approver = "Administrator"
	ec.approval_status = "Approved"
	ec.append(
		"expenses",
		{
			"expense_date": next_day,
			"expense_type": "Travel",
			"amount": 50.0,
			"sanctioned_amount": 50.0,
			"cost_center": cost_center,
		},
	)
	ec.posting_date = next_day
	ec.company = settings.company
	ec.payable_account = payable_acct
	ec.save()
	ec.submit()
	# two expense claims to test aggregation
	ec = frappe.new_doc("Expense Claim")
	ec.employee = "HR-EMP-00002"
	ec.expense_approver = "Administrator"
	ec.approval_status = "Approved"
	ec.append(
		"expenses",
		{
			"expense_date": next_day,
			"expense_type": "Travel",
			"amount": 50.0,
			"sanctioned_amount": 50.0,
			"cost_center": cost_center,
		},
	)
	ec.posting_date = next_day
	ec.company = settings.company
	ec.payable_account = payable_acct
	ec.save()
	ec.submit()


def create_payroll_journal_entry(settings):
	emps = frappe.get_list("Employee", {"company": settings.company})
	cost_center = frappe.get_value("Company", settings.company, "cost_center")
	payroll_account = frappe.get_value(
		"Account",
		{"company": settings.company, "account_name": "Payroll Payable", "is_group": 0},
	)
	salary_account = frappe.get_value(
		"Account", {"company": settings.company, "account_name": "Salary", "is_group": 0}
	)
	payroll_expense = frappe.get_value(
		"Account",
		{"company": settings.company, "account_name": "Payroll Taxes", "is_group": 0},
	)
	payable_account = frappe.get_value("Company", settings.company, "default_payable_account")
	je = frappe.new_doc("Journal Entry")
	je.entry_type = "Journal Entry"
	je.company = settings.company
	je.posting_date = settings.day
	je.due_date = settings.day
	total_payroll = 0.0
	for idx, emp in enumerate(emps):
		employee_name = frappe.get_value(
			"Employee", {"company": settings.company, "name": emp.name}, "employee_name"
		)
		je.append(
			"accounts",
			{
				"account": payroll_account,
				"bank_account": frappe.get_value("Bank Account", {"account": settings.company_account}),
				"party_type": "Employee",
				"party": emp.name,
				"cost_center": cost_center,
				"account_currency": "USD",
				"credit": 1000.00,
				"credit_in_account_currency": 1000.00,
				"debit": 0.00,
				"debit_in_account_currency": 0.00,
				"user_remark": employee_name + " Paycheck",
				"idx": idx + 2,
			},
		)
		total_payroll += 1000.00
	je.append(
		"accounts",
		{
			"account": salary_account,
			"cost_center": cost_center,
			"account_currency": "USD",
			"credit": 0.00,
			"credit_in_account_currency": 0.00,
			"debit": total_payroll,
			"debit_in_account_currency": total_payroll,
			"idx": 1,
		},
	)
	je.append(
		"accounts",
		{
			"account": payroll_expense,
			"cost_center": cost_center,
			"account_currency": "USD",
			"credit": 0.00,
			"credit_in_account_currency": 0.00,
			"debit": total_payroll * 0.15,
			"debit_in_account_currency": total_payroll * 0.15,
		},
	)
	je.append(
		"accounts",
		{
			"account": payable_account,
			"cost_center": cost_center,
			"party_type": "Supplier",
			"party": tax_authority[0][0],
			"account_currency": "USD",
			"credit": total_payroll * 0.15,
			"credit_in_account_currency": total_payroll * 0.15,
			"debit": 0.00,
			"debit_in_account_currency": 0.0,
		},
	)
	je.save()
	je.submit()


def create_sales_invoices(settings):
	for customer in customers:
		so = frappe.new_doc("Sales Order")
		so.company = settings.company
		so.transaction_date = so.delivery_date = settings.day
		so.customer = customer[0]
		so.append(
			"items",
			{
				"item_code": "Cloudberry",
				"qty": 3,
			},
		)
		so.save()
		so.submit()


def create_electronic_payment_settings(settings):
	if not frappe.db.exists("Account", "1320 - Electronic Payments Receivable - CFC"):
		epr = frappe.new_doc("Account")
		epr.account_number = "1320"
		epr.account_name = "Electronic Payments Receivable"
		epr.company = settings.company
		epr.root_type = "Asset"
		epr.report_type = "Balance Sheet"
		epr.parent_account = "1300 - Accounts Receivable - CFC"
		epr.save()

	if os.environ.get("STRIPE_API_KEY"):
		eps = frappe.new_doc("Electronic Payment Settings")
		eps.company = settings.company
		eps.provider = "Stripe"
		eps.api_key = os.environ.get("STRIPE_API_KEY")
		eps.create_ppm = 1
		eps.deposit_account = "1201 - Primary Checking - CFC"
		eps.accepting_fee_account = "5223 - Electronic Payments Provider Fees - CFC"
		eps.accepting_clearing_account = "1320 - Electronic Payments Receivable - CFC"
		eps.save()
	if (
		os.environ.get("AUTHORIZE_API_KEY")
		and os.environ.get("AUTHORIZE_TRANSACTION_KEY")
		and not os.environ.get("STRIPE_API_KEY")
	):
		eps = frappe.new_doc("Electronic Payment Settings")
		eps.company = settings.company
		eps.provider = "Authorize.net"
		eps.api_key = os.environ.get("AUTHORIZE_API_KEY")
		eps.transaction_key = os.environ.get("AUTHORIZE_TRANSACTION_KEY")
		eps.create_ppm = 1
		eps.deposit_account = "1201 - Primary Checking - CFC"
		eps.accepting_fee_account = "5223 - Electronic Payments Provider Fees - CFC"
		eps.accepting_clearing_account = "1320 - Electronic Payments Receivable - CFC"
		eps.save()


def curate_portal_and_ecommerce_settings(settings=None):
	ecom = frappe.get_doc("E Commerce Settings", "E Commerce Settings")
	ecom.enabled = 1
	ecom.save()

	portal = frappe.get_doc("Portal Settings", "Portal Settings")
	portal.hide_standard_menu = 1
	portal.append(
		"custom_menu",
		{
			"title": "Orders",
			"enabled": 1,
			"route": "/orders",
			"reference_doctype": "Sales Invoice",
			"role": "Customer",
		},
	)
	portal.append(
		"custom_menu",
		{
			"title": "Orders",
			"enabled": 1,
			"route": "/orders",
			"reference_doctype": "Purchase Invoice",
			"role": "Supplier",
		},
	)
	portal.save()


# config portal
# add read permissions for each doctype with hook on Portal Settings
#
