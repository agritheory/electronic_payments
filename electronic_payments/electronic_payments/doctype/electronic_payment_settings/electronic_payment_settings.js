// Copyright (c) 2022, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on('Electronic Payment Settings', {
	refresh: frm => {
		if (!frm.doc.mode_of_payment) {
			frm.set_df_property('mode_of_payment', 'read_only', 1)
		}
	},
})
