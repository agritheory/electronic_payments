// Copyright (c) 2025, AgriTheory and contributors
// For license information, please see license.txt

window.payment_method_utils = {
	fields_display() {
		const payment_type = document.getElementById('ppm_payment_type')
		const card_section = document.getElementById('card')
		const ach_section = document.getElementById('ach')

		if (payment_type.value == 'Card') {
			card_section.style.display = 'block'
			ach_section.style.display = 'none'
		} else {
			card_section.style.display = 'none'
			ach_section.style.display = 'block'
		}
	},

	set_required_fields() {
		const payment_type = document.getElementById('ppm_payment_type')
		if (payment_type.value == 'Card') {
			document.getElementById('ppm_card_number').required = true
			document.getElementById('ppm_card_cvc').required = true
			document.getElementById('ppm_cardholder_name').required = true
			document.getElementById('ppm_card_expiration_date').required = true

			document.getElementById('ppm_account_holders_name').required = false
			document.getElementById('ppm_email').required = false
			document.getElementById('ppm_routing_number').required = false
			document.getElementById('ppm_account_number').required = false
			document.getElementById('ppm_accept_wire').required = false
			document.getElementById('ppm_account_currency').required = false
			document.getElementById('ppm_address_firstline').required = false
			document.getElementById('ppm_address_secondline').required = false
			document.getElementById('ppm_city').required = false
			document.getElementById('ppm_state').required = false
			document.getElementById('ppm_postcode').required = false
			document.getElementById('ppm_country').required = false
		} else {
			document.getElementById('ppm_card_number').required = false
			document.getElementById('ppm_card_cvc').required = false
			document.getElementById('ppm_cardholder_name').required = false
			document.getElementById('ppm_card_expiration_date').required = false

			document.getElementById('ppm_account_holders_name').required = true
			document.getElementById('ppm_email').required = true
			document.getElementById('ppm_routing_number').required = true
			document.getElementById('ppm_account_number').required = true
			document.getElementById('ppm_accept_wire').required = false
			document.getElementById('ppm_account_currency').required = true
			document.getElementById('ppm_address_firstline').required = true
			document.getElementById('ppm_address_secondline').required = false
			document.getElementById('ppm_city').required = true
			document.getElementById('ppm_state').required = true
			document.getElementById('ppm_postcode').required = true
			document.getElementById('ppm_country').required = true
		}
	},

	get_form_data(inputs) {
		let ppm = {}
		inputs.forEach(id => (ppm[id] = document.getElementById(`ppm_${id}`).value))
		let checkboxes = ['default', 'accept_wire']
		checkboxes.forEach(id => (ppm[id] = document.getElementById(`ppm_${id}`).checked))
		return ppm
	},

	init() {
		this.fields_display()
		this.set_required_fields()
		$('#ppm_payment_type').change(() => {
			this.fields_display()
			this.set_required_fields()
		})
	},
}
