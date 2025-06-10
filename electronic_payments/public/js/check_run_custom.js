// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on('Check Run', {
	refresh: frm => {
		if (frm.doc.docstatus === 1) {
			set_button_info(frm)
		}
	},
})

async function set_button_info(frm) {
	await frappe
		.xcall(
			'electronic_payments.electronic_payments.doctype.electronic_payment_settings.electronic_payment_settings.get_check_run_button_info',
			{ cr_doc: frm.doc }
		)
		.then(r => {
			if (r.include_button) {
				frm.add_custom_button(__(r.button_text), () => {
					process_check_run_electronic_payments(frm)
				})
			}
		})
}

async function process_check_run_electronic_payments(frm) {
	await frappe
		.xcall(
			'electronic_payments.electronic_payments.doctype.electronic_payment_settings.electronic_payment_settings.process_check_run_electronic_payments',
			{
				cr_doc: frm.doc,
			}
		)
		.then(r => {
			console.log('POST-SERVER PROCESS CALL', r)
			if (r && r.message && r.message === 'Success') {
				frm.set_intro(
					__(
						'<span style="color: var(--green)" id="check-run-error">Successfully processed electronic payment provider ACH payments.</span>'
					),
					'green'
				)
			} else if (r && r.message && r.message === 'Error')
				frm.set_intro(
					__(
						`<span style="color: var(--red)" id="check-run-error">Electronic Payment processing error: ${r.errors}</span>`
					),
					'red'
				)
		})
}
