# Copyright (c) 2022, AgriTheory and contributors
# For license information, please see license.txt


# import frappe
from frappe.model.document import Document


class ElectronicPaymentProfile(Document):
	def validate(self):
		if not len(self.reference) == 4:
			return
		if self.payment_type == "Card":
			self.reference = f"**** **** **** {self.reference}"
		if self.payment_type == "ACH":
			self.reference = f"*{self.reference}"
