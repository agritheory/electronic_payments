frappe.ready(async () => {
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
		let ppm_edited = frappe.call({
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
		let inputs = ['name', 'label', 'default', 'service_charge', 'percentage_or_rate', 'percentage', 'rate']
		inputs.forEach(id => (ppm[id] = document.getElementById(`ppm_${id}`).value))
		return ppm
	}
})
