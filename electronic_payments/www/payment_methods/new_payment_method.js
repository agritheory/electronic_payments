frappe.ready(async () => {
	function fields_display() {
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
	}

	function set_required_fields() {
		const payment_type = document.getElementById('ppm_payment_type')
		if (payment_type.value == 'Card') {
			document.getElementById('ppm_card_number').required = true
			document.getElementById('ppm_card_cvc').required = true
			document.getElementById('ppm_cardholder_name').required = true
			document.getElementById('ppm_card_expiration_date').required = true

			document.getElementById('ppm_account_holders_name').required = false
			document.getElementById('ppm_dl_state').required = false
			document.getElementById('ppm_dl_number').required = false
			document.getElementById('ppm_routing_number').required = false
			document.getElementById('ppm_account_number').required = false
		} else {
			document.getElementById('ppm_card_number').required = false
			document.getElementById('ppm_card_cvc').required = false
			document.getElementById('ppm_cardholder_name').required = false
			document.getElementById('ppm_card_expiration_date').required = false

			document.getElementById('ppm_account_holders_name').required = true
			document.getElementById('ppm_dl_state').required = true
			document.getElementById('ppm_dl_number').required = true
			document.getElementById('ppm_routing_number').required = true
			document.getElementById('ppm_account_number').required = true
		}
	}

	fields_display()
	set_required_fields()

	$('#ppm_payment_type').change(function () {
		fields_display()
		set_required_fields()
	})

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
		let ppm = get_form_data()
		frappe.call({
			method: 'electronic_payments.www.payment_methods.new_payment_method.new_portal_payment_method',
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

	function get_form_data() {
		ppm = {}
		let inputs = [
			'party',
			'payment_type',
			'card_number',
			'card_cvc',
			'cardholder_name',
			'card_expiration_date',
			'account_holders_name',
			'dl_state',
			'dl_number',
			'routing_number',
			'account_number',
		]
		inputs.forEach(id => (ppm[id] = document.getElementById(`ppm_${id}`).value))

		let checkboxs = ['default']
		checkboxs.forEach(id => (ppm[id] = document.getElementById(`ppm_${id}`).checked))
		return ppm
	}
})
