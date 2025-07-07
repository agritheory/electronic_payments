// Copyright (c) 2022, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on('Electronic Payment Settings', {
	refresh: frm => {
		if (!frm.doc.mode_of_payment) {
			frm.set_df_property('mode_of_payment', 'read_only', 1)
		}

		frm.set_query('deposit_account', () => {
			return {
				filters: {
					company: frm.doc.company,
				},
			}
		})

		frm.set_query('accepting_fee_account', () => {
			return {
				filters: {
					company: frm.doc.company,
				},
			}
		})

		frm.set_query('accepting_payment_discount_account', () => {
			return {
				filters: {
					company: frm.doc.company,
				},
			}
		})

		frm.set_query('accepting_clearing_account', () => {
			return {
				filters: {
					company: frm.doc.company,
				},
			}
		})

		frm.set_query('withdrawal_account', () => {
			return {
				filters: {
					company: frm.doc.company,
				},
			}
		})

		frm.set_query('sending_fee_account', () => {
			return {
				filters: {
					company: frm.doc.company,
				},
			}
		})

		frm.set_query('sending_payment_discount_account', () => {
			return {
				filters: {
					company: frm.doc.company,
				},
			}
		})

		frm.set_query('sending_clearing_account', () => {
			return {
				filters: {
					company: frm.doc.company,
				},
			}
		})
	},
})
