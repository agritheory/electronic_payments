# Copyright (c) 2023, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.data import flt
import json


class PortalPaymentMethod(Document):
	def calculate_payment_method_fees(self, doc, amount=None):
		"""
		Returns fees associated with a payment method for a payment being made on doc. If the
		`amount` parameter is provided, percentage fees are calculated off it (e.g. for payment
		terms), if not, percentage fees are calculated off the doc's outstanding amount
		(`outstanding_amount` for Invoices, `grand_total` - `advance_paid` for Orders).
		"""
		doc = frappe._dict(json.loads(doc)) if isinstance(doc, str) else doc
		precision = frappe.get_precision(doc.doctype, "grand_total")
		fees = 0.0
		if not self.service_charge:
			return fees
		elif self.percentage_or_rate == "Percentage":
			if not doc.get("grand_total") and not amount:
				return fees
			outstanding_amount = (
				doc.outstanding_amount if "Invoice" in doc.doctype else doc.grand_total - doc.advance_paid
			)
			fees = flt(
				(amount if amount else outstanding_amount) * (self.percentage / 100),
				precision,
			)
		elif self.percentage_or_rate == "Rate":
			fees = flt(self.rate, precision)
		return fees
