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

	fields_display()

	$('#ppm_payment_type').change(function () {
		fields_display()
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
			'name',
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
