frappe.provide('electronic_payments')

frappe.ui.form.on("Customer", {
	refresh: frm => {
        const grid = frm.fields_dict["portal_payment_method"].grid
        const $add_payment_method_btn = $(
            `<button type="button" class="btn btn-xs btn-secondary">Add Payment Method</button>`
        );
        $add_payment_method_btn.on('click', () => electronic_payments.add_payment_method(frm))
        grid.wrapper.append($add_payment_method_btn)
        grid.wrapper.find('.grid-add-row').hide()
	},
})