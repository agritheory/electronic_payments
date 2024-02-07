import frappe
from frappe.utils import flt
from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry


class CustomElectronicPaymentsJournalEntry(JournalEntry):
	def check_credit_limit(self):
		customers = list(
			{
				d.party
				for d in self.get("accounts")
				if d.party_type == "Customer" and d.party and flt(d.debit) > 0
			}
		)
		if customers:
			from erpnext.selling.doctype.customer.customer import check_credit_limit

			for customer in customers:
				# CUSTOM CODE START
				bypass_cl_check_for_so = bool(
					frappe.db.get_value(
						"Customer Credit Limit",
						{"parent": customer, "parenttype": "Customer", "company": self.company},
						"bypass_credit_limit_check",
					)
				)  # if True, ignores Sales Order totals in customer_outstanding
				check_credit_limit(
					customer, self.company, ignore_outstanding_sales_order=bypass_cl_check_for_so
				)
				# CUSTOM CODE END
