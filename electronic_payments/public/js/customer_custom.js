// Copyright (c) 2026, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on('Customer', {
	refresh: frm => electronic_payments.portal_payment_method_refresh(frm),
})
