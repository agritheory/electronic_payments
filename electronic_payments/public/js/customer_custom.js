frappe.provide('electronic_payments')

frappe.ui.form.on('Customer', {
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
					? __('Do you want to remove the selected payment method through the API?')
					: __('Do you want to remove the selected payment methods through the API?')

			frappe.confirm(
				message,
				() => {
					selected.forEach(row => {
						frappe.call({
							method: 'electronic_payments.www.payment_methods.index.remove_portal_payment_method',
							args: { payment_method: row.name, party_type: frm.doc.doctype, party: frm.doc.name },
							callback: function () {
								remove_row_from_table(frm, row.name)
								$custom_delete_btn.addClass('hidden')
							},
						})
					})
				},
				() => {
					selected.forEach(row => {
						remove_row_from_table(frm, row.name)
						$custom_delete_btn.addClass('hidden')
					})
				}
			)
		})
	},
})

function remove_row_from_table(frm, row_name) {
	const grid = frm.get_field('portal_payment_method').grid
	const row = grid.grid_rows_by_docname[row_name]
	if (row) {
		row.remove()
		frm.refresh_field('portal_payment_method')
	}
}
