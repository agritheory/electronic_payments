// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

frappe.provide('electronic_payments')

frappe.ui.form.on('Sales Invoice', {
	refresh: frm => {
		if (!frm.is_new() && !frm.is_dirty() && frm.doc.company) {
			frappe.db.get_value('Electronic Payment Settings', { company: frm.doc.company }, 'enable_accepting').then(r => {
				if (r && r.message && r.message.enable_accepting) {
					frm.add_custom_button(__('Electronic Payments'), () => {
						electronic_payments.electronic_payments(frm)
					})
				}
			})
		}
	},
	onload_post_render: frm => {
		$(frm.wrapper).on('dirty', () => {
			frm.remove_custom_button(__('Electronic Payments'))
		})
	},
})
