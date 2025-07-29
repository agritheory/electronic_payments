frappe.provide('electronic_payments')

frappe.ui.form.on('Supplier', {
	refresh: frm => {
		const grid = frm.fields_dict['portal_payment_method'].grid
		grid.wrapper.find('.grid-add-row').hide()
		if (!frm.custom_child_button_added) {
			frm.custom_child_button_added = true
			const $add_payment_method_btn = $(
				`<button type="button" class="btn btn-xs btn-secondary">Add Payment Method</button>`
			)
			$add_payment_method_btn.on('click', () => electronic_payments.add_payment_method_dialog(frm))
			grid.wrapper.append($add_payment_method_btn)
		}
	},
})
