frappe.provide('electronic_payments')

frappe.ui.form.on('Purchase Order', {
	refresh: frm => {
		if (!frm.is_new() && !frm.is_dirty() && frm.company) {
			frappe.db.get_value('Electronic Payment Settings', { company: frm.company }, 'enable_sending').then(r => {
				if (r && r.message && r.message.enable_sending) {
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
