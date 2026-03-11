<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Network Diagrams

<div class="byline">
  Heather Kusmierz 2026-02-25
</div>


The Electronic Payments app offers multiple ways to accomplish the same tasks in terms of adding, editing, or deleting payment methods, or applying one to pay an outstanding invoice. In general:

- **ERPNext User (via desk)** (with the appropriate permissions)
    - Add, edit, or delete payment methods from the Customer or Supplier record from the "Electronic Payments" tab. If there are multiple companies in ERPNext with Electronic Payments Settings configured, a new payment method will attach to all companies with "Accepting Payments" enabled (for Customers) or with "Sending Payments" enabled (for Suppliers)
    - Add and optionally apply a payment method or apply a saved payment method on a Sales Invoice or Purchase Invoice via the "Electronic Payments" button. The payment method will only attach to the company in the Invoice's "Company" field
- **Customer (self service via portal)**
    - Add, edit, or delete payment methods through the portal. If there are multiple companies in ERPNext with Electronic Payments Settings configured, a new payment method will attach to all companies with "Accepting Payments" enabled
    - Pay an outstanding Sales Invoice with a saved payment method
- **Supplier (self service via portal)**
    - Add, edit, or delete payment methods through the portal. If there are multiple companies in ERPNext with Electronic Payments Settings configured, a new payment method will attach to all companies with "Accepting Payments" enabled

Not all providers allow editing or deleting payment methods via their API - this is noted by provider.

Throughout all the following processes, ERPNext only stores the customer ID (if one is created), the payment method ID (the token the provider assigns to identify the payment method), and a payment method reference. This reference is a shorthand display (using the mode of payment and last four digits of the payment method, such as "Card-1234" or "ACH-6789") to help a user identify it.

For any unsuccessful interactions with the Provider API, ERPNext will display an error message and exit out of the process.

## Authorize.net

Authorize.net is available as a provider to both send or accept payments.

| Action | ERPNext Desk User | Customer Portal User | Supplier Portal User |
| :----: | :----------: | :------: | :------: |
| Add Pmt Method | ✅ | ✅ | ✅ |
| Edit Pmt Method | ✅ | ✅ | ✅ |
| Delete Pmt Method | ✅ | ✅ | ✅ |
| Pay Sales Invoice | ✅ | ✅ | ❌ |
| Pay Purchase Invoice | ✅ | ❌ | ❌ |


### Authorize.net: Adding a Portal Payment Method

The following diagram summarizes the interactions between a Customer or Supplier logged into the ERPNext portal and the provider's API when they add a new Portal Payment Method. These interactions with the API are identical to what an ERPNext desk user would experience if they added a payment method from the "Electronic Payments" tab in the Customer or Supplier record on behalf of the party.

Authorize.net generally saves payment methods to a customer profile. The diagram shows that this profile gets created first (if it's not already stored in ERPNext), then the new payment method gets linked to it.

In the loop below, the Electronic Payments Settings documents returned by the database are only those configured to accept payments (when a Customer is logged in) or to send payments (when a Supplier is logged in).

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Authorize.net API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Add Portal Payment Method
    ERPNext->>ERPNext DB: Get EP Settings
    activate ERPNext DB
    ERPNext DB->>ERPNext: All Configured EP Settings

    loop All Companies with Configured EP Settings
    ERPNext->>ERPNext DB: Get Customer ID

    alt No Stored Customer ID
        activate ERPNext DB
        ERPNext DB->>ERPNext: No ID
        deactivate ERPNext DB
        ERPNext->>Authorize.net API: New Customer Request
        activate Authorize.net API
        Authorize.net API->>ERPNext DB: Customer ID
        deactivate Authorize.net API
        activate ERPNext DB
        ERPNext DB ->>ERPNext:Customer ID
        deactivate ERPNext DB
    else Has Stored Customer ID
        activate ERPNext DB
        ERPNext DB ->>ERPNext:Customer ID
        deactivate ERPNext DB
    end

    ERPNext->>Authorize.net API: Create Pmt Method Request
    activate Authorize.net API
    Authorize.net API->>ERPNext DB: Pmt Method ID
    deactivate Authorize.net API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Pmt Method Reference
    deactivate ERPNext DB
    end
    ERPNext->>Portal User: Display Pmt Method Reference(s)
    deactivate ERPNext
```

### Authorize.net: Editing a Portal Payment Method

The following diagram summarizes the interactions between a Customer or Supplier logged into the ERPNext portal when they want to edit a saved payment method. The form expects the Customer or Supplier to re-enter all payment method data to update it.

These interactions with the API are identical to what an ERPNext desk user would experience if they edited a payment method from the "Electronic Payments" tab in the Customer or Supplier record on behalf of the party.

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Authorize.net API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Navigates to Portal Pmt Methods
    ERPNext->>ERPNext DB: Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext: Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>Portal User: Display Pmt Methods References
    Portal User->>ERPNext: Clicks Pencil Icon for Pmt Method to Edit
    ERPNext->>Authorize.net API: Get Pmt Profile Request
    activate Authorize.net API
    Authorize.net API->>ERPNext: Pmt Profile Data
    deactivate Authorize.net API
    ERPNext->>Portal User: Form to Collect Pmt Method Data
    Portal User->>ERPNext: Updated Pmt Method Data
    ERPNext->>Authorize.net API: Edit Pmt Method Request
    activate Authorize.net API
    Authorize.net API->>ERPNext DB: Edit Request Response
    deactivate Authorize.net API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Response and Updated Reference (if needed)
    deactivate ERPNext DB
    ERPNext->>Portal User: Success Message, Pmt Method Updated 
    deactivate ERPNext
```

### Authorize.net: Deleting a Portal Payment Method

The following diagram summarizes the interactions between a Customer or Supplier logged into the ERPNext portal when they want to delete a saved payment method.

These interactions with the API are identical to what an ERPNext desk user would experience if they deleted a payment method from the "Electronic Payments" tab in the Customer or Supplier record on behalf of the party.

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Authorize.net API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Navigates to Portal Pmt Methods
    ERPNext->>ERPNext DB: Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext: Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>Portal User: Display Pmt Methods References
    Portal User->>ERPNext: Clicks Trash Icon for Pmt Method to Delete
    ERPNext->>ERPNext DB:Delete Pmt Method Reference/ID from ERPNext
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Pmt Method Removed from ERPNext DB
    deactivate ERPNext DB
    ERPNext->>Authorize.net API: Delete Pmt Method Request
    activate Authorize.net API
    Authorize.net API->>ERPNext: Delete Request Response
    deactivate Authorize.net API
    ERPNext->>Portal User: Success Message, Pmt Method Removed
    deactivate ERPNext
```

### Authorize.net: Applying a Portal Payment Method to Pay a Sales Invoice from the Portal

The following diagram summarizes the interactions between a Customer logged into the ERPNext portal when they want to apply a saved payment method to pay an outstanding Sales Invoice.

```mermaid
sequenceDiagram
    actor Customer
    participant ERPNext
    participant ERPNext DB
    participant Authorize.net API

    Customer->>ERPNext: Logs into Portal
    activate ERPNext
    Customer->>ERPNext: Navigates to and Selects Invoice to Pay
    ERPNext->>ERPNext DB:Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>Customer: Display Pmt Method References
    Customer->>ERPNext: Pay via Pmt Method Reference
    ERPNext->>Authorize.net API: Process Payment via Pmt Method ID
    activate Authorize.net API
    Authorize.net API->>ERPNext DB: Transaction ID
    deactivate Authorize.net API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Transaction ID
    deactivate ERPNext DB
    ERPNext->>ERPNext DB: Create Payment Entry
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Invoice Fully/Partially Paid
    deactivate ERPNext DB
    ERPNext->>Customer: Success Message, Invoice Status Updated 
    deactivate ERPNext
```

### Authorize.net: Applying a Portal Payment Method to Satisfy a Sales Invoice or Purchase Invoice as an ERPNext Desk User

The following diagram summarizes the interactions between an ERPNext desk user logged into ERPNext when they want to apply a party's saved payment method to accept payment for an outstanding Sales Invoice or send payment on an outstanding Purchase Invoice.

From the Invoice, the desk user can also add a new payment method and choose to save only, save and process payment, or only temporarily save until the payment goes through, then remove it from ERPNext.

```mermaid
sequenceDiagram
    actor User
    participant ERPNext
    participant ERPNext DB
    participant Authorize.net API

    User->>ERPNext: Logs into ERPNext
    activate ERPNext
    User->>ERPNext: Navigates to Invoice
    User->>ERPNext: Clicks Electronic Payments Button
    ERPNext->>ERPNext DB:Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>User: Dialog Displays Saved or Add New Methods
    User->>ERPNext: Selects Saved Pmt Method Reference
    User->>ERPNext: Clicks Process Payment
    ERPNext->>Authorize.net API: Process Payment via Pmt Method ID
    activate Authorize.net API
    Authorize.net API->>ERPNext DB: Transaction ID
    deactivate Authorize.net API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Transaction ID
    deactivate ERPNext DB
    ERPNext->>ERPNext DB: Create Payment Entry
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Invoice Fully/Partially Paid
    deactivate ERPNext DB
    ERPNext->>User: Success Message, Invoice Status Updated 
    deactivate ERPNext
```

## Mercury

Mercury is available as a provider to send payments.

| Action | ERPNext Desk User | Customer Portal User | Supplier Portal User |
| :----: | :----------: | :------: | :------: |
| Add Pmt Method | ✅ | ❌ | ✅ |
| Edit Pmt Method | ✅ | ❌ | ✅ |
| Delete Pmt Method | 🟡 | ❌ | 🟡 |
| Pay Sales Invoice | ❌ | ❌ | ❌ |
| Pay Purchase Invoice | ✅ | ❌ | ❌ |

### Mercury: Adding a Portal Payment Method

The following diagram summarizes the interactions between a Supplier logged into the ERPNext portal and the Mercury API when they add a new Portal Payment Method. These interactions with the API are identical to what an ERPNext desk user would experience if they added a payment method from the "Electronic Payments" tab in the Supplier record on behalf of the party.

Mercury does not use profile IDs for a party. Instead, it creates independent "recipients" for each payment method. If a new payment method's bank account can accept both wire and ACH transfers, the user should select the "Routing number can accept wire transfers?" box. The app will automatically adjust the API call so the recipient has both modes of payment available. Note that wire transfers are only possible via the Mercury UI and not via the API yet.

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Mercury API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Add Portal Payment Method
    ERPNext->>ERPNext DB: Get EP Settings
    activate ERPNext DB
    ERPNext DB->>ERPNext: All EP Settings Configured to Send Payments

    loop All Companies with EP Settings to Send Payments

    ERPNext->>Mercury API: Create Recipient Request
    activate Mercury API
    Mercury API->>ERPNext DB: Pmt Method ID
    deactivate Mercury API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Pmt Method Reference
    deactivate ERPNext DB
    end
    ERPNext->>Portal User: Display Pmt Method Reference(s)
    deactivate ERPNext
```

### Mercury: Editing a Portal Payment Method

The following diagram summarizes the interactions between a Supplier logged into the ERPNext portal when they want to edit a saved payment method. The form expects the Supplier to re-enter all payment method data to update it.

These interactions with the API are identical to what an ERPNext desk user would experience if they edited a payment method from the "Electronic Payments" tab in the Supplier record on behalf of the party.

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Mercury API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Navigates to Portal Pmt Methods
    ERPNext->>ERPNext DB: Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext: Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>Portal User: Display Pmt Methods References
    Portal User->>ERPNext: Clicks Pencil Icon for Pmt Method to Edit
    ERPNext->>Mercury API: Get Pmt Profile Request
    activate Mercury API
    Mercury API->>ERPNext: Pmt Profile Data
    deactivate Mercury API
    ERPNext->>Portal User: Form to Collect Pmt Method Data
    Portal User->>ERPNext: Updated Pmt Method Data
    ERPNext->>Mercury API: Edit Pmt Method Request
    activate Mercury API
    Mercury API->>ERPNext DB: Edit Request Response
    deactivate Mercury API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Response and Updated Reference (if needed)
    deactivate ERPNext DB
    ERPNext->>Portal User: Success Message, Pmt Method Updated 
    deactivate ERPNext
```

### Mercury: Deleting a Portal Payment Method

The following diagram summarizes the interactions between a Supplier logged into the ERPNext portal when they want to delete a saved payment method. The Mercury API does not allow for payment methods to be removed via an API call, so this action deletes it from ERPNext, then logs an error to let ERPNext desk users know to manually delete it from the Mercury website.

These interactions with the API are identical to what an ERPNext desk user would experience if they deleted a payment method from the "Electronic Payments" tab in the Supplier record on behalf of the party.

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Mercury API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Navigates to Portal Pmt Methods
    ERPNext->>ERPNext DB: Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext: Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>Portal User: Display Pmt Methods References
    Portal User->>ERPNext: Clicks Trash Icon for Pmt Method to Delete
    ERPNext->>ERPNext DB:Delete Pmt Method Reference/ID from ERPNext
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Pmt Method Removed from ERPNext DB
    ERPNext->>ERPNext DB:Log Error to Delete Method on Mercury Website
    deactivate ERPNext DB
    ERPNext->>Portal User: Success Message, Pmt Method Removed
    deactivate ERPNext
```

### Mercury: Send Payment to a Portal Payment Method to Pay a Purchase Invoice as an ERPNext Desk User

The following diagram summarizes the interactions between an ERPNext desk user logged into ERPNext when they want to send payment to a Supplier's saved payment method to pay an outstanding Purchase Invoice.

```mermaid
sequenceDiagram
    actor User
    participant ERPNext
    participant ERPNext DB
    participant Mercury API

    User->>ERPNext: Logs into ERPNext
    activate ERPNext
    User->>ERPNext: Navigates to Purchase Invoice to Pay
    User->>ERPNext: Clicks Electronic Payments Button
    ERPNext->>ERPNext DB:Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>User: Dialog Displays Saved or Add New Methods
    User->>ERPNext: Selects Saved Pmt Method Reference
    User->>ERPNext: Clicks Process Payment
    ERPNext->>Mercury API: Process Payment via Pmt Method ID
    activate Mercury API
    Mercury API->>ERPNext DB: Transaction ID
    deactivate Mercury API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Transaction ID
    deactivate ERPNext DB
    ERPNext->>ERPNext DB: Create Payment Entry
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Invoice Fully/Partially Paid
    deactivate ERPNext DB
    ERPNext->>User: Success Message, Invoice Status Updated 
    deactivate ERPNext
```

## Stripe

Stripe is available as a provider to accept payments.

| Action | ERPNext Desk User | Customer Portal User | Supplier Portal User |
| :----: | :----------: | :------: | :------: |
| Add Pmt Method | ✅ | ✅ | ❌ |
| Edit Pmt Method | ✅ | ✅ | ❌ |
| Delete Pmt Method | ✅ | ✅ | ❌ |
| Pay Sales Invoice | ✅ | ✅ | ❌ |
| Pay Purchase Invoice | ❌ | ❌ | ❌ |


### Stripe: Adding a Portal Payment Method

The following diagram summarizes the interactions between a Customer logged into the ERPNext portal and Stripe's API when they add a new Portal Payment Method. These interactions with the API are identical to what an ERPNext desk user would experience if they added a payment method from the "Electronic Payments" tab in the Customer record on behalf of the party.

Stripe generally saves payment methods to a customer profile. The diagram shows that this profile gets created first (if it's not already stored in ERPNext), then the new payment method gets linked to it. 

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Stripe API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Add Portal Payment Method
    ERPNext->>ERPNext DB: Get EP Settings that Accept Payments
    activate ERPNext DB
    ERPNext DB->>ERPNext: All EP Settings that Accept Payments

    loop All Companies with EP Settings to Accept
    ERPNext->>ERPNext DB: Get Customer ID

    alt No Stored Customer ID
        activate ERPNext DB
        ERPNext DB->>ERPNext: No ID
        deactivate ERPNext DB
        ERPNext->>Stripe API: New Customer Request
        activate Stripe API
        Stripe API->>ERPNext DB: Customer ID
        deactivate Stripe API
        activate ERPNext DB
        ERPNext DB ->>ERPNext:Customer ID
        deactivate ERPNext DB
    else Has Stored Customer ID
        activate ERPNext DB
        ERPNext DB ->>ERPNext:Customer ID
        deactivate ERPNext DB
    end

    ERPNext->>Stripe API: Create Pmt Method Request
    activate Stripe API
    Stripe API->>ERPNext DB: Pmt Method ID
    deactivate Stripe API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Pmt Method Reference
    deactivate ERPNext DB
    end
    ERPNext->>Portal User: Display Pmt Method Reference(s)
    deactivate ERPNext
```

### Stripe: Editing a Portal Payment Method

The following diagram summarizes the interactions between a Customer logged into the ERPNext portal when they want to edit a saved payment method. The form expects the Customer to re-enter all payment method data to update it.

These interactions with the API are identical to what an ERPNext desk user would experience if they edited a payment method from the "Electronic Payments" tab in the Customer record on behalf of the party.

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Stripe API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Navigates to Portal Pmt Methods
    ERPNext->>ERPNext DB: Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext: Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>Portal User: Display Pmt Methods References
    Portal User->>ERPNext: Clicks Pencil Icon for Pmt Method to Edit
    ERPNext->>Stripe API: Get Pmt Profile Request
    activate Stripe API
    Stripe API->>ERPNext: Pmt Profile Data
    deactivate Stripe API
    ERPNext->>Portal User: Form to Collect Pmt Method Data
    Portal User->>ERPNext: Updated Pmt Method Data
    ERPNext->>Stripe API: Edit Pmt Method Request
    activate Stripe API
    Stripe API->>ERPNext DB: Edit Request Response
    deactivate Stripe API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Response and Updated Reference (if needed)
    deactivate ERPNext DB
    ERPNext->>Portal User: Success Message, Pmt Method Updated 
    deactivate ERPNext
```

### Stripe: Deleting a Portal Payment Method

The following diagram summarizes the interactions between a Customer logged into the ERPNext portal when they want to delete a saved payment method.

These interactions with the API are identical to what an ERPNext desk user would experience if they deleted a payment method from the "Electronic Payments" tab in the Customer record on behalf of the party.

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Stripe API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Navigates to Portal Pmt Methods
    ERPNext->>ERPNext DB: Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext: Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>Portal User: Display Pmt Methods References
    Portal User->>ERPNext: Clicks Trash Icon for Pmt Method to Delete
    ERPNext->>ERPNext DB:Delete Pmt Method Reference/ID from ERPNext
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Pmt Method Removed from ERPNext DB
    deactivate ERPNext DB
    ERPNext->>Stripe API: Delete Pmt Method Request
    activate Stripe API
    Stripe API->>ERPNext: Delete Request Response
    deactivate Stripe API
    ERPNext->>Portal User: Success Message, Pmt Method Removed
    deactivate ERPNext
```

### Stripe: Applying a Portal Payment Method to Pay a Sales Invoice from the Portal

The following diagram summarizes the interactions between a Customer logged into the ERPNext portal when they want to apply a saved payment method to pay an outstanding Sales Invoice.

```mermaid
sequenceDiagram
    actor Customer
    participant ERPNext
    participant ERPNext DB
    participant Stripe API

    Customer->>ERPNext: Logs into Portal
    activate ERPNext
    Customer->>ERPNext: Navigates to and Selects Invoice to Pay
    ERPNext->>ERPNext DB:Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>Customer: Display Pmt Method References
    Customer->>ERPNext: Pay via Pmt Method Reference
    ERPNext->>Stripe API: Process Payment via Pmt Method ID
    activate Stripe API
    Stripe API->>ERPNext DB: Transaction ID
    deactivate Stripe API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Transaction ID
    deactivate ERPNext DB
    ERPNext->>ERPNext DB: Create Payment Entry
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Invoice Fully/Partially Paid
    deactivate ERPNext DB
    ERPNext->>Customer: Success Message, Invoice Status Updated 
    deactivate ERPNext
```

### Stripe: Applying a Portal Payment Method to Satisfy a Sales Invoice as an ERPNext Desk User

The following diagram summarizes the interactions between an ERPNext desk user logged into ERPNext when they want to apply a party's saved payment method to satisfy an outstanding Sales Invoice.

From the Invoice, the desk user can also add a new payment method and choose to save only, save and process payment, or only temporarily save until the payment goes through, then remove it from ERPNext.

```mermaid
sequenceDiagram
    actor User
    participant ERPNext
    participant ERPNext DB
    participant Stripe API

    User->>ERPNext: Logs into ERPNext
    activate ERPNext
    User->>ERPNext: Navigates to Invoice
    User->>ERPNext: Clicks Electronic Payments Button
    ERPNext->>ERPNext DB:Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>User: Dialog Displays Saved or Add New Methods
    User->>ERPNext: Selects Saved Pmt Method Reference
    User->>ERPNext: Clicks Process Payment
    ERPNext->>Stripe API: Process Payment via Pmt Method ID
    activate Stripe API
    Stripe API->>ERPNext DB: Transaction ID
    deactivate Stripe API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Transaction ID
    deactivate ERPNext DB
    ERPNext->>ERPNext DB: Create Payment Entry
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Invoice Fully/Partially Paid
    deactivate ERPNext DB
    ERPNext->>User: Success Message, Invoice Status Updated 
    deactivate ERPNext
```

## Wise

Wise is available as a provider to send payments.

| Action | ERPNext Desk User | Customer Portal User | Supplier Portal User |
| :----: | :----------: | :------: | :------: |
| Add Pmt Method | ✅ | ❌ | ✅ |
| Edit Pmt Method | ❌ | ❌ | ❌ |
| Delete Pmt Method | ✅ | ❌ | ✅ |
| Pay Sales Invoice | ❌ | ❌ | ❌ |
| Pay Purchase Invoice | ✅ | ❌ | ❌ |

### Wise: Adding a Portal Payment Method

The following diagram summarizes the interactions between a Supplier logged into the ERPNext portal and the Wise API when they add a new Portal Payment Method. These interactions with the API are identical to what an ERPNext desk user would experience if they added a payment method from the "Electronic Payments" tab in the Supplier record on behalf of the party.

Wise does not use profile IDs for a party. Instead, it creates independent "recipients" for each payment method.

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Wise API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Add Portal Payment Method
    ERPNext->>ERPNext DB: Get EP Settings
    activate ERPNext DB
    ERPNext DB->>ERPNext: All EP Settings Configured to Send Payments

    loop All Companies with EP Settings to Send Payments

    ERPNext->>Wise API: Create Recipient Request
    activate Wise API
    Wise API->>ERPNext DB: Pmt Method ID
    deactivate Wise API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Pmt Method Reference
    deactivate ERPNext DB
    end
    ERPNext->>Portal User: Display Pmt Method Reference(s)
    deactivate ERPNext
```

### Wise: Editing a Portal Payment Method

Wise doesn't allow for editing a payment method. Instead, the user needs to delete it and add it as a new payment method with any changes.

### Wise: Deleting a Portal Payment Method

The following diagram summarizes the interactions between a Supplier logged into the ERPNext portal when they want to delete a saved payment method.

These interactions with the API are identical to what an ERPNext desk user would experience if they deleted a payment method from the "Electronic Payments" tab in the Supplier record on behalf of the party.

```mermaid
sequenceDiagram
    actor Portal User
    participant ERPNext
    participant ERPNext DB
    participant Wise API

    Portal User->>ERPNext: Logs into Portal
    activate ERPNext
    Portal User->>ERPNext: Navigates to Portal Pmt Methods
    ERPNext->>ERPNext DB: Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext: Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>Portal User: Display Pmt Methods References
    Portal User->>ERPNext: Clicks Trash Icon for Pmt Method to Delete
    ERPNext->>ERPNext DB:Delete Pmt Method Reference/ID from ERPNext
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Pmt Method Removed from ERPNext DB
    deactivate ERPNext DB
    ERPNext->>Wise API: Delete Pmt Method Request
    activate Wise API
    Wise API->>ERPNext: Delete Request Response
    deactivate Wise API
    ERPNext->>Portal User: Success Message, Pmt Method Removed
    deactivate ERPNext
```

### Wise: Send Payment to a Portal Payment Method to Pay a Purchase Invoice as an ERPNext Desk User

The following diagram summarizes the interactions between an ERPNext desk user logged into ERPNext when they want to send payment to a Supplier's saved payment method to pay an outstanding Purchase Invoice.

Wise has a slightly different process compared to the other providers - instead of a single payment request, there are separate requests to create a quote, then set up a transfer. Wise does not allow funding a transfer via the API, unless there's a direct debit account set up. If that's the case, the Electronic Payments app will attempt the final fund transfer step as a batch transfer with direct debit.

If the user doesn't want to set up or use direct debit to fund all transfers, then they will need to go to the Wise website and perform the final funding step there.

#### No Direct Debit Account is Configured in Wise or Electronic Payments Settings

```mermaid
sequenceDiagram
    actor User
    participant ERPNext
    participant ERPNext DB
    participant Wise API
    participant Wise Website

    User->>ERPNext: Logs into ERPNext
    activate ERPNext
    User->>ERPNext: Navigates to Purchase Invoice to Pay
    User->>ERPNext: Clicks Electronic Payments Button
    ERPNext->>ERPNext DB:Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>User: Dialog Displays Saved or Add New Methods
    User->>ERPNext: Selects Saved Pmt Method Reference
    User->>ERPNext: Clicks Process Payment

    ERPNext->>Wise API: Create Quote Request
    activate Wise API
    Wise API->>ERPNext: Quote ID
    deactivate Wise API
    ERPNext->>Wise API: Create Transfer with Pmt Method ID
    activate Wise API
    Wise API->>ERPNext DB: Transaction ID
    deactivate Wise API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Transaction ID
    deactivate ERPNext DB
    ERPNext->>ERPNext DB: Create Payment Entry
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Invoice Fully/Partially Paid
    deactivate ERPNext DB
    ERPNext->>User: Success Message, Invoice Status Updated 
    User->>Wise Website: Selects Funding Mechanism for Transfer
    activate Wise Website
    Wise Website->>User: Transfer Funded
    deactivate Wise Website
    deactivate ERPNext
```

#### Direct Debit Account is Configured in Wise and Electronic Payments Settings

```mermaid
sequenceDiagram
    actor User
    participant ERPNext
    participant ERPNext DB
    participant Wise API

    User->>ERPNext: Logs into ERPNext
    activate ERPNext
    User->>ERPNext: Navigates to Purchase Invoice to Pay
    User->>ERPNext: Clicks Electronic Payments Button
    ERPNext->>ERPNext DB:Get Pmt Method References/IDs
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Party's Pmt Method References/IDs
    deactivate ERPNext DB
    ERPNext->>User: Dialog Displays Saved or Add New Methods
    User->>ERPNext: Selects Saved Pmt Method Reference
    User->>ERPNext: Clicks Process Payment

    ERPNext->>Wise API: Create Quote Request
    activate Wise API
    Wise API->>ERPNext: Quote ID
    deactivate Wise API
    
    ERPNext->>Wise API: Create a Batch Group Request
    activate Wise API
    Wise API->>ERPNext: Create Batch Group Response
    deactivate Wise API
    
    ERPNext->>Wise API: Create a Batch Group Transfer Request
    activate Wise API
    Wise API->>ERPNext: Create Batch Group Transfer Response
    deactivate Wise API

    ERPNext->>Wise API: Fund Batch Group with Direct Debit Request
    activate Wise API
    Wise API->>ERPNext DB: Transaction ID
    deactivate Wise API
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Transaction ID
    deactivate ERPNext DB
    ERPNext->>ERPNext DB: Create Payment Entry
    activate ERPNext DB
    ERPNext DB ->>ERPNext:Invoice Fully/Partially Paid
    deactivate ERPNext DB
    ERPNext->>User: Success Message, Invoice Status Updated 
    deactivate ERPNext
```
