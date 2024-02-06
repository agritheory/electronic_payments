frappe.ready(async () => {
	function fields_display() {
		const service_charge = document.getElementById('ppm_service_charge')
		const percentage_or_rate = document.getElementById('ppm_percentage_or_rate')
		const percentage = document.getElementById('ppm_percentage')
		const rate = document.getElementById('ppm_rate')

		if (service_charge.checked) {
			percentage_or_rate.style.display = 'block'
			percentage_or_rate.parentNode.style.display = 'block'
		} else {
			percentage_or_rate.style.display = 'none'
			percentage_or_rate.parentNode.style.display = 'none'
		}

		if (percentage_or_rate.style.display != 'none') {
			if (percentage_or_rate.value == 'Percentage') {
				percentage.style.display = 'block'
				percentage.parentNode.style.display = 'block'
				rate.style.display = 'none'
				rate.parentNode.style.display = 'none'
			} else {
				percentage.style.display = 'none'
				percentage.parentNode.style.display = 'none'
				rate.style.display = 'block'
				rate.parentNode.style.display = 'block'
			}
		} else {
			percentage.style.display = 'none'
			percentage.parentNode.style.display = 'none'
			rate.style.display = 'none'
			rate.parentNode.style.display = 'none'
		}
	}

	fields_display()

	$('#ppm_service_charge').change(function () {
		fields_display()
	})

	$('#ppm_percentage_or_rate').change(function () {
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
		let inputs = ['name', 'label', 'default', 'percentage_or_rate', 'percentage', 'rate']
		inputs.forEach(id => (ppm[id] = document.getElementById(`ppm_${id}`).value))

		let checkboxs = ['service_charge', 'default']
		checkboxs.forEach(id => (ppm[id] = document.getElementById(`ppm_${id}`).checked))
		return ppm
	}
})
