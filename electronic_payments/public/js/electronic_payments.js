frappe.provide('electronic_payments')

electronic_payments.electronic_payments = frm => {
	payment_options(frm)
	.then(mop_options => {
		let payment_profile_id = undefined
		if (mop_options[1] && mop_options[1].payment_profile_id){
			payment_profile_id = mop_options[1].payment_profile_id
		}
		let d = new frappe.ui.Dialog({
			title: __("Electronic Payments"),
			size: "extra-large",
			fields: [
				{ fieldname: 'ht', fieldtype: 'HTML', options: render_frm_data(frm) },
				{ fieldname: 'sec_1', fieldtype: 'Section Break' },
				{
					fieldname: 'mode_of_payment',
					fieldtype: 'Select',
					label: "Mode of Payment",
					options: mop_options[0],
					bold: 1,
					default: mop_options[0].split('\n')[0],
					change: () => { d.set_required_fields(mop_options) },
				},
				{
					fieldname: 'save_data', label: 'Charge Now?', fieldtype: 'Select', options: [
						'Charge now',
						'Save payment data for only this transaction',
						'Retain payment data for this party',
					],
				},
				{ fieldname: 'col_1', fieldtype: 'Column Break' },
				{
					fieldname: 'card_number',
					fieldtype: 'Data',
					label: "Card Number",
					change: () => { format_credit_card() },
					hidden: 1
				},
				{ fieldname: 'card_cvc', fieldtype: 'Int', label: "CVC", hidden: 1},
				{ fieldname: 'account_holders_name', fieldtype: 'Data', label: "Account Holder's Name", hidden: 1},
				{ fieldname: 'dl_state', fieldtype: 'Data', label: "Drivers License State", hidden: 1},
				{ fieldname: 'dl_number', fieldtype: 'Data', label: "Drivers License Number", hidden: 1},
				{ fieldname: 'col_2', fieldtype: 'Column Break', hidden: 1},
				{ fieldname: 'cardholder_name', fieldtype: 'Data', label: "Card Holder's Name", hidden: 1},
				{ fieldname: 'card_expiration_date', fieldtype: 'Data', label: "Card Expiration Date", description: "Enter as '2022-12' ", hidden: 1},
				{ fieldname: 'routing_number', fieldtype: 'Data', label: "Routing Number", hidden: 1},
				{ fieldname: 'account_number', fieldtype: 'Data', label: "Checking Account Number", hidden: 1},
				{ fieldname: 'check_number', fieldtype: 'Int', label: "Check Number", description: 'Optional', hidden: 1},
				{ fieldname: 'payment_profile_id', fieldtype: 'Data', hidden: 1, default: payment_profile_id, hidden: 1},
			],
			set_required_fields: (mop_options) => {
				if (d.fields_dict.mode_of_payment.value == 'New Card'){
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
				} else if (d.fields_dict.mode_of_payment.value == 'New ACH'){
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
				} else if (d.fields_dict.mode_of_payment.value == 'Saved Payment Method') {
					d.fields_dict.save_data.df.hidden = 1
					if (mop_options[1].payment_type == 'ACH') {
						d.fields_dict.account_number.df.hidden = 0
						d.fields_dict.card_number.df.hidden = 1
						d.fields_dict.account_number.df.read_only = 1
						d.fields_dict.account_number.set_value(mop_options[1].reference)

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
						d.fields_dict.card_number.set_value(mop_options[1].reference)

						d.fields_dict.account_holders_name.df.hidden = 1
						d.fields_dict.dl_state.df.hidden = 1
						d.fields_dict.dl_number.df.hidden = 1
						d.fields_dict.routing_number.df.hidden = 1
						d.fields_dict.check_number.df.hidden = 1
						d.fields_dict.card_number.df.hidden = 1
						d.fields_dict.card_cvc.df.hidden = 1
						d.fields_dict.cardholder_name.df.hidden = 1
						d.fields_dict.card_expiration_date.df.hidden = 1
					}
				}
				d.refresh()
			}
		})
		d.set_primary_action(__('Process Payment'), () => {
			process(frm, d)
		})
		d.set_required_fields(mop_options)
		d.show()
	})
}

function render_frm_data(frm){
	return '<table class="table table-borderless" style="margin-top: 0; margin-bottom: 0;">\
		<tbody><tr><td style="border: 1px solid transparent">Amount: ' + format_currency(cur_frm.doc.total) + '<br>' +
		'Tax Amount: ' + format_currency(frm.doc.total_taxes_and_charges) + '<br>' +
		'Order: ' + frm.doc.name + '<br>' + 'Purchase Order: ' + (frm.doc.po_no  || 'N/A') + '</td>' +
		'<td style="border: 1px solid transparent">' + frm.doc.customer_name + '<br>' + frm.doc.address_display + '</td>' +
		'<td style="border: 1px solid transparent">' + frm.doc.customer_name + '<br>' + frm.doc.shipping_address + '</td></tr></tbody></table>';
}

async function process(frm, dialog){
	let values = dialog.get_values()
	console.log('In JS process')
	console.log(values)
	await frappe.xcall("electronic_payments.electronic_payments.doctype.electronic_payment_settings.electronic_payment_settings.process", {doc: frm.doc, data: values})
	.then((r) => {
		console.log(r)
		if(r.message == 'Success'){
			dialog.fields_dict.ht.$wrapper.html('Success!')
		} else {
			dialog.fields_dict.ht.$wrapper.html(
				`<p style="color: red; font-weight: bold;">${r.error}</p>`
			)
		}
		frm.reload_doc()
	})
}

async function payment_options(frm){
	let payment_profile = ''
	await frappe.db.get_value('Electronic Payment Profile', {party: frm.doc.customer}, ['payment_profile_id', 'reference', 'payment_type'])
	.then(r => {payment_profile = r.message})
	console.log(frm.doc.pre_authorization_token, payment_profile)
	if (frm.doc.pre_authorization_token || payment_profile.hasOwnProperty('payment_profile_id')) {
		return ["Saved Payment Method\nNew Card\nNew ACH", payment_profile]
	} else {
		return ["New Card\nNew ACH"]
	}
}

function format_credit_card(){
	if(!cur_dialog){ return }
	const d = cur_dialog
	const credit_card_number = d.get_field("card_number").value
	if(credit_card_number.includes('*')){ return }
	const digits_only = credit_card_number.replace(/[^\d]/g, '')
	let formatted = digits_only.replace(/(.{4})/g, "$1 ")
	d.get_field("card_number").value = formatted
	d.get_field('card_number').refresh()
}
