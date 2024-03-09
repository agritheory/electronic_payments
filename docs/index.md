# Electronic Payments Documentation

The Electronic Payments application extends ERPNext[^1] with the capability to receive electronic payments via several vendors directly in the system. The current supported vendors are [Authorize.net](www.authorize.net) and [Stripe](stripe.com).

Electronic payments is set up to allow portal users to log in and add credit card (Stripe and Authorize.net) and ACH (Authorize.net only) payment methods associated with their account. Note that the payment method details are not saved on your system at any point. The app immediately passes the data to the provider API and, if the API successfully creates a payment method, it only saves the provider's token and last few account or card digits to identify that payment method. The Electronic Payments tab on the Customer page for that party shows a table with any stored payment methods.

<!-- TODO: add screen shot to add a portal payment method -->

When the customer is logged into the portal and has one or more payment methods set up, they can make a payment on an Order or Invoice directly from the portal. The app automatically integrates with the payment schedule defined on the Terms tab of the document, and will display payments spit out by payment term and showing any valid discounted amounts and due dates as necessary. If the provide accepts the payment and it successfully goes through, the app updates the payment schedule.

![Screen shot of the portal view of an invoice showing two payment terms, one is already paid and the other has a button to make a payment for that term's amount.](./assets/ep_portal_payment_terms.png)

The app also allows a desk user to make an advance payment on a Sales Order or a payment on a Sales Invoice on a customer's behalf. The document's page will show an Electronic Payment button which launches a dialog box to put the payment through.

![Screen shot showing the Electronic Payment button at the top of a Sales Invoice page in the desk view.](./assets/ep_desk_ep_button.png)

![Screen shot showing the dialog box to make a payment using a saved payment method. The Mode of Payment is Saved Payment Method: Card 0002 and the Card Number is **** **** **** 0002.](./assets/ep_desk_dialog.png)

## Installation, Configuration, Settings, and Permissions

There is some required prerequisite setup to get the Electronic Payments application up and running on your ERPNext site. See the following pages for details on installation, configuration, settings, and permissions:

- [Installation Guide](../README.md)
- [Configuration and Settings](./configuration.md)
- [Default Permissions and Workflows](./permissions.md)
- Refer to the [Example Data page](./exampledata.md) for instructions around installing fictitious demo data to experiment with using the Electronic Payments app

[^1]: [ERPNext](https://erpnext.com/) is an open-sourced Enterprise Resource Planning (ERP) software that provides a wide range of business management functionality. Its core features include support for accounting, inventory, manufacturing, customer relationship management (CRM), distribution, and retail.
