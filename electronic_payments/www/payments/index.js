frappe.ready(() => {
	$('#payment-method').on('change', event => {
		let total = event.target.selectedOptions[0].dataset.total
		let currency = $('#doc-currency')[0].dataset.currency
		let currency_symbol = $('#doc-currency')[0].dataset.symbol
		let formatted_currency = format_currency(total, currency, 2).replace(currency, currency_symbol)

		let order_button = $('#pay-for-order')[0]
		order_button.innerHTML = `${__('Pay')} ${formatted_currency}`
	})
	$('#pay-for-order').on('click', () => {
		$('#pay-for-order').addClass('disabled')
		let order_url = new URL(window.location)
		let dt = order_url.searchParams.get('dt')
		let dn = order_url.searchParams.get('dn')
		let payment_method = $('#payment-method')[0].value
		frappe.call('pay', {dt: dt, dn: dn, payment_method: payment_method})
		.then(r => {
			if ('success_message' in r.message){
				$('#payments-messages')[0].innerHTML = r.message.success_message
				setTimeout(() => {
					window.location = '/invoices'
				}, 3000)
			}
			if ('error_message' in r.message) {
				$('#payments-messages')[0].innerHTML = r.message.error_message
			}
		})
	})

})

