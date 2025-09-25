frappe.provide('electronic_payments')

frappe.ui.form.on('Supplier', {
	refresh: frm => {
		frm.set_df_property('portal_payment_method', 'cannot_add_rows', true)
		frm.set_df_property('portal_payment_method', 'cannot_delete_rows', true)

		const grid = frm.fields_dict['portal_payment_method'].grid
		const $custom_buttons_wrapper = $('<div class="custom-grid-buttons" style="display: flex; gap: 8px;"></div>')
		const $add_payment_method_btn = $(
			`<button type="button" class="btn btn-xs btn-secondary">Add Payment Method</button>`
		)
		$add_payment_method_btn.on('click', () => electronic_payments.add_payment_method_dialog(frm))
		const $custom_delete_btn = $(`
			<button type="button" class="btn btn-xs btn-danger hidden">
				${__('Delete Payment Method')}
			</button>
		`)

		if (!frm.custom_buttons_added) {
			frm.custom_buttons_added = true
			$custom_buttons_wrapper.append($add_payment_method_btn)
			$custom_buttons_wrapper.append($custom_delete_btn)
			grid.wrapper.append($custom_buttons_wrapper)
		}

		grid.wrapper.on('click', '.grid-row-check', function () {
			const selected = grid.get_selected_children()
			if (selected.length === 0) {
				$custom_delete_btn.addClass('hidden')
			} else {
				$custom_delete_btn.removeClass('hidden')
			}
		})

		$custom_delete_btn.on('click', function () {
			const selected = grid.get_selected_children()

			if (!selected.length) {
				frappe.msgprint(__('Please select at least one row.'))
				return
			}

			const message =
				selected.length === 1
					? __(
							'Do you want to delete the selected payment method only in ERPNext, or also remove it from the external provider?'
						)
					: __(
							'Do you want to delete the selected payment methods only in ERPNext, or also remove them from the external provider?'
						)

			const d = new frappe.ui.Dialog({
				title: __('Delete Payment Method'),
				fields: [
					{
						fieldtype: 'HTML',
						options: `<div style="margin-bottom: 12px;">${message}</div>`,
					},
				],
				primary_action_label: __('Delete from ERPNext and Provider'),
				primary_action: () => {
					selected.forEach(row => {
						frappe.call({
							method: 'electronic_payments.www.payment_methods.index.remove_portal_payment_method',
							args: { payment_method: row.name, party_type: frm.doc.doctype, party: frm.doc.name },
							callback: function () {
								remove_row_from_table(frm, row.name, true)
							},
						})
					})
					d.hide()
					$custom_delete_btn.addClass('hidden')
				},
				secondary_action_label: __('Delete only from ERPNext'),
				secondary_action: () => {
					selected.forEach(row => {
						remove_row_from_table(frm, row.name, true)
					})
					d.hide()
					$custom_delete_btn.addClass('hidden')
				},
			})
			d.show()
		})
	},
})

function remove_row_from_table(frm, row_name) {
	const grid = frm.get_field('portal_payment_method').grid
	const row = grid.grid_rows_by_docname[row_name]
	if (row) {
		row.remove()
		frm.save()
	}
}
