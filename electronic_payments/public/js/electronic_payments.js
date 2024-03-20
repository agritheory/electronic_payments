frappe.provide('electronic_payments')

electronic_payments.electronic_payments = frm => {
	payment_options(frm).then(mop_options => {
		let payment_profile_id = undefined
		let customer_profile_id = undefined
		let ppm_name = undefined
		let subject_to_credit_limit = 0
		let d = new frappe.ui.Dialog({
			title: __('Electronic Payments'),
			size: 'extra-large',
			fields: [
				{ fieldname: 'ht', fieldtype: 'HTML', options: render_frm_data(frm) },
				{ fieldname: 'sec_1', fieldtype: 'Section Break' },
				{
					fieldname: 'mode_of_payment',
					fieldtype: 'Select',
					label: 'Mode of Payment',
					options: mop_options[0],
					bold: 1,
					default: mop_options[0].split('\n')[0],
					change: () => {
						d.set_required_fields(mop_options)
					},
				},
				{
					fieldname: 'save_data',
					label: 'Charge Now?',
					fieldtype: 'Select',
					options: ['Charge now', 'Save payment data for only this transaction', 'Retain payment data for this party'],
				},
				{ fieldname: 'col_1', fieldtype: 'Column Break' },
				{
					fieldname: 'card_number',
					fieldtype: 'Data',
					label: 'Card Number',
					change: () => {
						format_credit_card()
					},
					hidden: 1,
				},
				{ fieldname: 'card_cvc', fieldtype: 'Int', label: 'CVC', hidden: 1 },
				{ fieldname: 'account_holders_name', fieldtype: 'Data', label: "Account Holder's Name", hidden: 1 },
				{ fieldname: 'dl_state', fieldtype: 'Data', label: 'Drivers License State', hidden: 1 },
				{ fieldname: 'dl_number', fieldtype: 'Data', label: 'Drivers License Number', hidden: 1 },
				{ fieldname: 'col_2', fieldtype: 'Column Break', hidden: 1 },
				{ fieldname: 'cardholder_name', fieldtype: 'Data', label: "Card Holder's Name", hidden: 1 },
				{
					fieldname: 'card_expiration_date',
					fieldtype: 'Data',
					label: 'Card Expiration Date',
					description: "Enter as '2022-12' ",
					hidden: 1,
				},
				{ fieldname: 'routing_number', fieldtype: 'Data', label: 'Routing Number', hidden: 1 },
				{ fieldname: 'account_number', fieldtype: 'Data', label: 'Checking Account Number', hidden: 1 },
				{ fieldname: 'check_number', fieldtype: 'Int', label: 'Check Number', description: 'Optional', hidden: 1 },
				{ fieldname: 'customer_profile_id', fieldtype: 'Data', default: customer_profile_id, hidden: 1 },
				{ fieldname: 'payment_profile_id', fieldtype: 'Data', default: payment_profile_id, hidden: 1 },
				{ fieldname: 'ppm_name', fieldtype: 'Data', default: ppm_name, hidden: 1 },
				{ fieldname: 'subject_to_credit_limit', fieldtype: 'Int', default: subject_to_credit_limit, hidden: 1 },
			],
			set_required_fields: mop_options => {
				if (d.fields_dict.mode_of_payment.value == 'New Card') {
					d.fields_dict.save_data.df.hidden = 0
					d.fields_dict.card_number.df.hidden = 0
					d.fields_dict.card_cvc.df.hidden = 0
					d.fields_dict.cardholder_name.df.hidden = 0
					d.fields_dict.card_expiration_date.df.hidden = 0

					d.fields_dict.account_holders_name.df.hidden = 1
					d.fields_dict.dl_state.df.hidden = 1
					d.fields_dict.dl_number.df.hidden = 1
					d.fields_dict.routing_number.df.hidden = 1
					d.fields_dict.account_number.df.hidden = 1
					d.fields_dict.check_number.df.hidden = 1
					d.fields_dict.card_number.df.read_only = 0
					d.fields_dict.card_number.set_value('')
				} else if (d.fields_dict.mode_of_payment.value == 'New ACH') {
					d.fields_dict.save_data.df.hidden = 0
					d.fields_dict.card_number.df.hidden = 1
					d.fields_dict.card_cvc.df.hidden = 1
					d.fields_dict.cardholder_name.df.hidden = 1
					d.fields_dict.card_expiration_date.df.hidden = 1

					d.fields_dict.account_holders_name.df.hidden = 0
					d.fields_dict.dl_state.df.hidden = 0
					d.fields_dict.dl_number.df.hidden = 0
					d.fields_dict.routing_number.df.hidden = 0
					d.fields_dict.account_number.df.hidden = 0
					d.fields_dict.check_number.df.hidden = 0
					d.fields_dict.account_number.df.read_only = 0
					d.fields_dict.account_number.set_value('')
				} else if (d.fields_dict.mode_of_payment.value.slice(0, 5) == 'Saved') {
					let ref_last4 = d.fields_dict.mode_of_payment.value.slice(d.fields_dict.mode_of_payment.value.length - 4)
					let selected = mop_options[1].filter(item => item.reference.slice(item.reference.length - 4) == ref_last4)
					d.fields_dict.save_data.df.hidden = 1
					d.fields_dict.customer_profile_id.set_value(selected[0].party_profile)
					d.fields_dict.payment_profile_id.set_value(selected[0].payment_profile_id)
					d.fields_dict.ppm_name.set_value(selected[0].ppm_name)
					d.fields_dict.subject_to_credit_limit.set_value(selected[0].subject_to_credit_limit)
					if (selected[0].payment_type == 'ACH') {
						d.fields_dict.account_number.df.hidden = 0
						d.fields_dict.card_number.df.hidden = 1
						d.fields_dict.account_number.df.read_only = 1
						d.fields_dict.account_number.set_value(selected[0].reference)

						d.fields_dict.account_holders_name.df.hidden = 1
						d.fields_dict.dl_state.df.hidden = 1
						d.fields_dict.dl_number.df.hidden = 1
						d.fields_dict.routing_number.df.hidden = 1
						d.fields_dict.check_number.df.hidden = 1
						d.fields_dict.card_number.df.hidden = 1
						d.fields_dict.card_cvc.df.hidden = 1
						d.fields_dict.cardholder_name.df.hidden = 1
						d.fields_dict.card_expiration_date.df.hidden = 1
					} else {
						d.fields_dict.card_number.df.hidden = 0
						d.fields_dict.account_number.df.hidden = 1
						d.fields_dict.card_number.df.read_only = 1
						d.fields_dict.card_number.set_value(selected[0].reference)

						d.fields_dict.account_holders_name.df.hidden = 1
						d.fields_dict.dl_state.df.hidden = 1
						d.fields_dict.dl_number.df.hidden = 1
						d.fields_dict.routing_number.df.hidden = 1
						d.fields_dict.check_number.df.hidden = 1
						d.fields_dict.card_cvc.df.hidden = 1
						d.fields_dict.cardholder_name.df.hidden = 1
						d.fields_dict.card_expiration_date.df.hidden = 1
					}
				}
				d.refresh()
			},
		})
		d.set_primary_action(__('Process Payment'), () => {
			process(frm, d)
		})
		d.set_required_fields(mop_options)
		d.show()
	})
}

function render_frm_data(frm) {
	if (frm.doc.doctype.indexOf('Sales') >= 0) {
		return (
			'<table class="table table-borderless" style="margin-top: 0; margin-bottom: 0;">\
			<tbody><tr><td style="border: 1px solid transparent">Amount: ' +
			format_currency(cur_frm.doc.total) +
			'<br>' +
			'Tax Amount: ' +
			format_currency(frm.doc.total_taxes_and_charges) +
			'<br>' +
			'Order: ' +
			frm.doc.name +
			'<br>' +
			'Purchase Order: ' +
			(frm.doc.po_no || 'N/A') +
			'</td>' +
			'<td style="border: 1px solid transparent">' +
			frm.doc.customer_name +
			'<br>' +
			frm.doc.address_display +
			'</td>' +
			'<td style="border: 1px solid transparent">' +
			frm.doc.customer_name +
			'<br>' +
			frm.doc.shipping_address +
			'</td></tr></tbody></table>'
		)
	} else {
		return (
			'<table class="table table-borderless" style="margin-top: 0; margin-bottom: 0;">\
			<tbody><tr><td style="border: 1px solid transparent">Amount: ' +
			format_currency(frm.doc.total) +
			'<br>' +
			'Tax Amount: ' +
			format_currency(frm.doc.total_taxes_and_charges) +
			'<br>' +
			'Order: ' +
			frm.doc.name +
			'</td>' +
			'<td style="border: 1px solid transparent">' +
			frm.doc.supplier_name +
			'<br>' +
			frm.doc.address_display +
			'</td>' +
			'<td style="border: 1px solid transparent">' +
			frm.doc.supplier_name +
			'<br>' +
			frm.doc.shipping_address +
			'</td></tr></tbody></table>'
		)
	}
}

async function process(frm, dialog) {
	let values = dialog.get_values()
	await frappe
		.xcall(
			'electronic_payments.electronic_payments.doctype.electronic_payment_settings.electronic_payment_settings.process',
			{ doc: frm.doc, data: values }
		)
		.then(r => {
			if (r.message == 'Success') {
				dialog.fields_dict.ht.$wrapper.html(`<p style="color: green; font-weight: bold;">Success!</p>`)
				// TODO: hide/remove Process Payment button
			} else {
				dialog.fields_dict.ht.$wrapper.html(`<p style="color: red; font-weight: bold;">${r.error}</p>`)
			}
			frm.reload_doc()
		})
}

async function payment_options(frm) {
	let payment_profiles = []
	let saved_methods = []
	let is_sales = frm.doc.doctype.indexOf('Sales') >= 0 ? true : false
	await frappe
		.xcall(
			'electronic_payments.electronic_payments.doctype.electronic_payment_settings.electronic_payment_settings.get_payment_profiles',
			{ doc: frm.doc }
		)
		.then(r => {
			payment_profiles = r
			for (let i = 0; i < r.length; ++i) {
				saved_methods.push(
					'Saved Payment Method: ' + r[i].payment_type + ' ' + r[i].reference.slice(r[i].reference.length - 4)
				)
			}
		})
	if (frm.doc.pre_authorization_token || payment_profiles.length > 0) {
		let options = []
		if (is_sales) {
			options = saved_methods.concat(['New Card', 'New ACH']).join('\n')
		} else {
			options = saved_methods.concat(['New ACH']).join('\n')
		}
		return [options, payment_profiles]
	} else {
		if (is_sales) {
			return ['New Card\nNew ACH']
		} else {
			return ['New ACH']
		}
	}
}

function format_credit_card() {
	if (!cur_dialog) {
		return
	}
	const d = cur_dialog
	const credit_card_number = d.get_field('card_number').value
	if (credit_card_number.includes('*')) {
		return
	}
	const digits_only = credit_card_number.replace(/[^\d]/g, '')
	let formatted = digits_only.replace(/(.{4})/g, '$1 ')
	d.get_field('card_number').value = formatted
	d.get_field('card_number').refresh()
}
