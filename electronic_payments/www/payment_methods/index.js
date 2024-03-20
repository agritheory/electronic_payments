frappe.ready(() => {
	$('.remove-ppm').on('click', e => {
		let portal_payment_method_name = e.currentTarget.dataset.name
		let mop = e.currentTarget.dataset.mop
		let label = e.currentTarget.dataset.label
		frappe.confirm(
			__(`Are you sure to remove ${mop} ${label}?`),
			() => {
				frappe
					.call('electronic_payments.www.payment_methods.index.remove_portal_payment_method', {
						payment_method: portal_payment_method_name,
					})
					.then(r => {
						if ('success_message' in r.message) {
							$('#payments-messages')[0].innerHTML = r.message.success_message
							setTimeout(() => {
								window.location = '/payment_methods'
							}, 3000)
						}
						if ('error_message' in r.message) {
							$('#payments-messages')[0].innerHTML = r.message.error_message
						}
					})
			},
			() => {}
		)
	})
})
