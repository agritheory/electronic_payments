# Electronic Payments Permissions and Workflows

## Permissions

The Electronic Payments app integrates with ERPNext's existing documents and workflows. The app doesn't introduce any new roles or permission changes, but leverages the existing setup.

- Users with the Role of System Manager may create and edit the Electronic Payments Settings for a company
- Users with access to Sales Orders and Sales Invoices (and soon Purchase Orders and Purchase Invoices) will see an "Electronic Payments" button on those documents, enabling them to make a payment on behalf of a customer or to a supplier
- Users with access to Customers or Suppliers are able to see that party's associated Portal Payment Methods on the Electronic Payments tab
- Users with the Role of Customer or Supplier are able to add credit cards (and ACH accounts for Authorize.net) as payment methods via their portal access, and apply those payment methods on outstanding orders or invoices

## Workflows

As noted in the [Configuration and Settings page](./configuration.md), there are two distinct methods for posting an electronic payment - using a Journal Entry with a Clearing Account, or using a Payment Entry. The major difference between the two options is when the electronic payment reflects against the deposit account (for accepting payments) or the withdrawal account (when sending payments). With a Journal Entry and clearing account, when the electronic payment successfully clears, the balance amount moves off the accounts receivable or accounts payable associated with the party and onto the clearing account. Only after transactions settle would the user make the entries to offset the cash transfers to/from the provider against the clearing account. With a Payment Entry, when the electronic payment successfully clears, the transaction immediately reflects against the deposit or withdrawal account - there is no intermediate step with a clearing account.

The following descriptions apply when accepting a payment from a customer, with differences noted when the transaction is for sending a payment to a supplier:

**Journal Entry with Clearing Account**
- When a payment successfully clears with the given provider, the system saves and submits a new Journal Entry for the individual transaction
    - Accepting payments: the balance moves off of the Accounts Receivable account associated with the party. The paid amount (balance net any discounts and fees) is debited against the clearing account. Any fees the customer pays are credited against the fee account and any discounts (per terms in the order or invoice's payment schedule) are debited against the payment discount account. The clearing account, fee account, and payment discount account are specified in the Electronic Payment Settings document
    - Sending payments: the balance moves off of the Accounts Payable account associated with the party. The paid amount (balance net any discounts and fees) is credited against the clearing account. Any fees the company pays are debited against the fee account and any discounts (per terms in the order or invoice's payment schedule) are credited against the payment discount account. The clearing account, fee account, and payment discount account are specified in the Electronic Payment Settings document
- The app automatically integrates with the payment schedule and updates it when a payment successfully clears

![Screen shot showing the debits and credits in a Journal Entry for an electronic payment of a sales invoice made by a customer. There is a credit to Accounts Receivable for the invoice total of $64.65, a debit to the clearing account for $64.94 (invoice total less a valid 2% discount for paying early of $1.29, plus fees of $1.58), a credit to the fee account for $1.58, and a debit to the payment discount account for $1.29.](./assets/ep_journal_entry_workflow.png)

- When the provider settles transactions and transfers cash into the deposit account (or out of the withdrawal account, both specified in the Electronic Payment Settings document), the user can reconcile them against the clearing account

**Payment Entry**
- When a payment successfully clears with the given provider, the system saves and submits a new Payment Entry for the individual transaction
    - Accepting payments: the References table logs the Order or Invoice with the balance amount. Any fees paid by the customer show in the Advance Taxes and Charges table and are associated with the fee account. If the reference document had a valid discount in its payment schedule, the discount amount shows in the Payment Deduction of Loss table and is associated with the payment discount account. The deposit account is used to receive the payment. The provider's transaction ID is stored in the Reference No. field. The deposit account, fee account, and payment discount account are specified in the Electronic Payment Settings document
    - Sending payments: the References table logs the Order or Invoice with the balance amount. Any fees paid by the company show in the Advance Taxes and Charges table and are associated with the fee account. If the reference document had a valid discount in its payment schedule, the discount amount shows in the Payment Deduction of Loss table and is associated with the payment discount account. The withdrawal account is used to clear the payment. The provider's transaction ID is stored in the Reference No. field. The withdrawal account, fee account, and payment discount account are specified in the Electronic Payment Settings document
- The app automatically integrates with the payment schedule and updates it when a payment successfully clears

![Screen shot showing the generated Payment Entry against a Sales Invoice for $81.96 when the customer applied an electronic payment method. The Advance Taxes and Charges table shows the card fees paid by the customer of $2.01 and the Payment Deductions or Loss table reflects a valid 2% discount of $1.64 for paying early.](./assets/ep_payment_entry.png)

![Screen shot showing the general ledger entries for an electronic payment made on a sales invoice. The invoice had payment terms of 2% discount if paid within 10 days, which the customer took advantage of. There's a credit to Accounts Receivable of $81.96 (total of the invoice), a debit to the deposit account of $82.33 (total less the discount amount plus fees), a debit to Sales (the payment discount account) of $1.64, and a credit to the fee account of $2.01](./assets/ep_payment_entry_gl_entries.png)
