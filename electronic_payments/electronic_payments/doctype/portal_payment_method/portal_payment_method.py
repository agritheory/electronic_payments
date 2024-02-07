# Copyright (c) 2023, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.data import flt
import json


class PortalPaymentMethod(Document):
	def calculate_payment_method_fees(self, doc):
		"""
		    Given a document (with a grand_total) and a data dict with payment method information,
		returns any fees associated with that payment method
		"""
		doc = frappe._dict(json.loads(doc)) if isinstance(doc, str) else doc
		fees = 0.0
		if not self.service_charge:
			return fees
		elif self.percentage_or_rate == "Percentage":
			if not doc.get("grand_total"):
				return fees
			fees = flt(
				doc.grand_total * (self.percentage / 100), frappe.get_precision(doc.doctype, "grand_total")
			)
		elif self.percentage_or_rate == "Rate":
			fees = flt(self.rate, frappe.get_precision(doc.doctype, "grand_total"))
		return fees
