<!-- Copyright (c) 2025, AgriTheory and contributors
For license information, please see license.txt-->

# Electronic Payments Configuration and Settings

One Electronic Payment Settings document may be created for each Company in ERPNext. This document stores the Provider information (including API keys) and account information that's used in the chosen accounting workflow. Authorize.net requires both an API Key and a Transaction Key, whereas Stripe requires only the API Key. The keys should be the **testing/sandbox** values when testing the functionality of the application, and only updated to live keys when using the application in production.

![Screen shot showing the fields in the Electronic Payment Settings document.](./assets/electronic_payment_settings.png)

See below for information and default values for each field:

- **Company:** (required) the company in ERPNext to apply all settings to - only one Electronic Payment Settings document may exist per company
- **Provider:** Authorize.net or Stripe
- **Merchant ID:** (optional) the company's ID associated with the provider
- **Endpoint:** (required for Authorize.net, defaults to the Sandbox testing environment endpoint) Authorize.net has two distinct API endpoints
    - In testing: use the sandbox API endpoint `https://apitest.authorize.net/xml/v1/request.api`
    - Production mode: use the production API endpoint `https://api.authorize.net/xml/v1/request.api`
    - Note that for Authorize.net, sandbox keys only work with the sandbox endpoint, and production keys only work with the production endpoint. The user will see an error if the keys don't match with the appropriate endpoint
- **API Key:** the company's API key with the given provider
    - In testing: this should be the sandbox key for Authorize.net or the test keys for Stripe (the Stripe account should also be in test mode) when testing the application
    - In production: this should be the live production keys when being used in a production environment
- **Transaction Key:** (Authorize.net only) the company's transaction key with Authorize.net
    - In testing: this should be the sandbox transaction key
    - In production: this should be the live transaction key
- **Automatically Create a Portal Payment Method when Electronic Payment Profile is Saved:** (default checked) when checked, if a desk user clicks the Electronic Payment button for an Order or Invoice, then enters payment information via the dialog box and selects to save the payment method, this automatically creates a Portal Payment Method for the party. In ERPNext, Portal Payment Methods are viewable and editable in the Electronic Payments tab of the respective party's page

**Accounts: Accepting Payments**
- **Deposit Account:** the account that receives deposits from the provider after customer payments settle
- **Provider Fee Account:** the account to hold any provider fees associated with transactions
- **Payment Discount Account:** the account to net any payment discounts given to a customer (this field fetches the default payment discount account specified in Company Settings but is editable)
- **Use Clearing Account:** (default Use Journal Entry and Clearing Account) whether to account for a successful electronic payment via a Journal Entry and Clearing account, or a Payment Entry. The differences between the two workflows is detailed on the [Electronic Payments Permissions and Workflows page](./permissions.md)
- **Clearing Account:** account to use when the Use Journal Entry and Clearing Account option is selected. The accounting entries for an example transaction using a clearing account can be found on the [Electronic Payments Permissions and Workflows page](./permissions.md)

**Accounts: Sending Payments**
- **Enable Sending Electronic Payments:** (default unchecked) activate the ability for the given company to make electronic payments
- **Withdrawal Account:** the account that sends payments to the provider after supplier payment transactions settle
- **Payment Discount Account:** the account to net any payment discounts given to the company (this field fetches the default payment discount account specified in Company Settings but is editable)
- **Provider Fee Account:** the account to hold any provider fees associated with transactions
- **Clearing Account:** account to use when the Use Journal Entry and Clearing Account option is selected. The accounting entries for an example transaction using a clearing account can be found on the [Electronic Payments Permissions and Workflows page](./permissions.md)
