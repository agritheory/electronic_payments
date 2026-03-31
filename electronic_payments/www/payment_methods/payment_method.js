// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

frappe.ready(async () => {
	payment_method_utils.init()

	$('#submit-button').on('click', event => {
		event.preventDefault()
		let button = document.getElementById('submit-button')
		button.disabled = true
		let form = document.querySelector('#ppm-form')
		if (!form.checkValidity()) {
			form.reportValidity()
			button.disabled = false
			return
		}
		let ppm = payment_method_utils.get_form_data([
			'name',
			'payment_type',
			'card_number',
			'card_cvc',
			'cardholder_name',
			'card_expiration_date',
			'account_holders_name',
			'email',
			'routing_number',
			'account_number',
			'accept_wire',
			'address_firstline',
			'address_secondline',
			'city',
			'state',
			'postcode',
			'country',
			'account_currency',
		])
		frappe.call({
			method: 'electronic_payments.www.payment_methods.payment_method.edit_portal_payment_method',
			args: {
				payment_method: ppm,
			},
			callback: r => {
				if ('success_message' in r.message) {
					$('#payments-messages')[0].innerHTML = r.message.success_message
					setTimeout(() => {
						window.location = '/payment_methods'
					}, 3000)
				}
				if ('error_message' in r.message) {
					$('#payments-messages')[0].innerHTML = r.message.error_message
				}
				button.disabled = false
			},
			error: err => {
				frappe.show_alert('Something went wrong please try again')
				button.disabled = false
			},
		})
	})
})
