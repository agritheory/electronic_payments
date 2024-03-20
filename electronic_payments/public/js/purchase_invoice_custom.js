frappe.provide('electronic_payments')

frappe.ui.form.on('Purchase Invoice', {
	refresh: frm => {
		if (!frm.is_new() && !frm.is_dirty()) {
			frm.add_custom_button(__('Electronic Payments'), () => {
				electronic_payments.electronic_payments(frm)
			})
		}
	},
	onload_post_render: frm => {
		$(frm.wrapper).on('dirty', () => {
			frm.remove_custom_button(__('Electronic Payments'))
		})
	},
})
