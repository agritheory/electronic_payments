import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password

import stripe
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import create_payment_entry

"""
# Information assumed to be in data object:

- Currency (for charges) - code currently uses the global default

Credit cards
- card number
- expiration date month (M) able to convert to int
- expiration date year (YYYY) able to convert to int
- CVC code (Stripe will attempt to verify validity)

Bank Accounts
- Country in which bank account is (two-letter ISO code, ex: 'US') -> convert from
  Country in address?
- Currency the bank account is in (three-letter ISO code in lowercase, ex: 'usd')
  (code currently uses global default)
- Account holder type: 'individual' or 'company'. Considered optional except when
  bank account is attached to a Customer
- Account holder name
- Account number
- Routing number

Notes:
- Tokens: one-time use object to be used in a Charge or attached to a Customer
  (https://stripe.com/docs/api/tokens)
- Currency: amounts in charges and refunds are in the smallest currency unit (for USD,
  it's in cents so a $1.00 charge would use amount=100). There are a handful of zero-
  decimal currencies detailed in docs (https://stripe.com/docs/currencies). The use of
  int in amount drops any remaining amount in case of three-decimal currencies (Stripe
  requires the least-significant digit of the decimal to be zero)
- Charges: if credit card or bank account PaymentMethod used as source, needs to link
  to a Customer (i.e. must pass customer ID as parameter as well)
- Adding payment to Customer:
    - Create card: https://stripe.com/docs/api/cards/create
    - Create bank account: https://stripe.com/docs/api/customer_bank_accounts/create
    - PaymentIntents / JS integration saving info during payment: https://stripe.com/docs/payments/save-during-payment
- There's only one Refund object in stripe, which works for CCs/banks. There is no void transaction option
- If billing address provided, Stripe will validate line_1 and zip code
- Use idempotency_key in Charge (docs recommend UUID4 to generate)? Allows for safe POST retries if errors
"""


class Stripe():
	def get_password(self, company):
		settings = frappe.get_doc('Electronic Payment Settings', {'company': company})
		if not settings:
			frappe.msgprint(_(f'No Electronic Payment Settings found for {company}-Stripe'))
		else:
			stripe.api_key = get_decrypted_password(settings.doctype, settings.name, 'api_key')
	
	def currency_multiplier(self, currency):
		zero_decimal = (
			'bif', 'clp', 'djf', 'gnf',
			'jpy', 'kmf', 'krw', 'mga',
			'pyg', 'rwf', 'ugx', 'vnd',
			'vuv', 'xaf', 'xof', 'xpf'
		)
		return 100 if currency not in zero_decimal else 1

	def generate_token(self, doc, data):
		self.get_password(doc.company)
		try:
			if data.mode_of_payment.replace('New ', '') == 'Card':
				card_number = data.get('card_number')
				card_number = card_number.replace(' ', '')
				response = stripe.Token.create(
					card={
						'number': card_number,
						'exp_month': int(data.get('expiration_date').split('-')[1]),
						'exp_year': int(data.get('expiration_date').split('-')[0]),
						'cvc': data.get('card_cvc'),
					},
				)
			elif data.mode_of_payment.replace('New ', '') == 'ACH':
				response = stripe.Token.create(
					bank_account={
						'country': data.get('country'),
						'currency': frappe.defaults.get_global_default('currency').lower(),  # TODO: this should be currency of bank account, not company default in system
						'account_holder_name': data.get('account_holders_name'),
						'account_holder_type': data.get('account_holder_type'),  # 'individual' or 'company', generally optional but required if attached to a Customer in request
						'routing_number': str(data.get('routing_number')),
						'account_number': str(data.get('account_number')),
					},
				)
			return response.id
		except Exception as e:
			try:
				frappe.log_error(frappe.get_traceback(), f'{e.code}: {e.type}. {e.message}')
				return {'error': f'{e.code}: {e.type}. {e.message}'}  # e.code has status code, e.type is one of 4 error types, e.message is a human-readable message providing more details about the error
			except:  # non-Stripe error, something else went wrong
				frappe.log_error(frappe.get_traceback(), f'{e}')
				return {'error': f'{e}'}

	def process_credit_card(self, doc, data):
		self.get_password(doc.company)
		try:
			currency = frappe.defaults.get_global_default('currency').lower()
			response = stripe.Charge.create(
				amount=int(doc.grand_total * self.currency_multiplier(currency)),
				currency=currency,
				source=self.generate_token(doc, data),
				description=doc.name  # optional
			)
			if response.status == 'succeeded':
				create_payment_entry(doc, data, response.id)
				return {'message': 'Success', 'transaction_id': response.id}
			elif response.status == 'pending':
				# TODO: is there confirmation if it eventually goes through? How to handle?
				return {'error': 'Payment pending'}
			else:  # 'failed'
				return {'error': 'Payment failed'}
		except Exception as e:
			try:
				frappe.log_error(frappe.get_traceback(), f'{e.code}: {e.type}. {e.message}')
				return {'error': f'{e.code}: {e.type}. {e.message}'}  # e.code has status code, e.type is one of 4 error types, e.message is a human-readable message providing more details about the error
			except:  # non-Stripe error, something else went wrong
				frappe.log_error(frappe.get_traceback(), f'{e}')
				return {'error': f'{e}'}

	def create_customer_profile(self, doc, data):
		self.get_password(doc.company)
		try:
			response = stripe.Customer.create(
				name=doc.customer
			)
			frappe.db.set_value('Customer', doc.customer, 'electronic_payment_profile', response.id)
			return response.id
		except Exception as e:
			try:
				frappe.log_error(frappe.get_traceback(), f'{e.code}: {e.type}. {e.message}')
				return {'error': f'{e.code}: {e.type}. {e.message}'}
			except:  # non-Stripe error, something else went wrong
				frappe.log_error(frappe.get_traceback(), f'{e}')
				return {'error': f'{e}'}

	def create_customer_payment_profile(self, doc, data):
		self.get_password(doc.company)
		if not data.get('customer_profile'):
			customer_profile_id = frappe.get_value('Customer', doc.customer, 'electronic_payment_profile')
		else:
			customer_profile_id = data.get('customer_profile')

		try:
			# if data.get('save_data') # TODO: check if customer wants payment method saved
			response = stripe.Customer.create_source(
				customer_profile_id,
				source=self.generate_token(doc, data),
			)
			
			payment_profile = frappe.new_doc('Electronic Payment Profile')
			payment_profile.party_type = 'Customer'
			payment_profile.party = doc.customer
			payment_profile.payment_type = data.mode_of_payment.replace('New ', '')
			payment_profile.reference = f"**** **** **** {response.last4}" if response.object == 'card' else f"*{response.last4}"
			payment_profile.payment_profile_id = str(response.id)
			payment_profile.party_profile = str(customer_profile_id)
			payment_profile.retain = 1 if data.save_data == 'Save payment data for this customer' else 0
			payment_profile.save()
			return payment_profile
		except Exception as e:
			try:
				frappe.log_error(frappe.get_traceback(), f'{e.code}: {e.type}. {e.message}')
				return {'error': f'{e.code}: {e.type}. {e.message}'}
			except:  # non-Stripe error, something else went wrong
				frappe.log_error(frappe.get_traceback(), f'{e}')
				return {'error': f'{e}'}

	def charge_customer_profile(self, doc, data):
		self.get_password(doc.company)
		if not data.get('customer_profile'):
			customer_profile_id = frappe.get_value('Customer', doc.customer, 'electronic_payment_profile')
		else: 
			customer_profile_id = data.get('customer_profile')
		if not customer_profile_id:
			customer_profile_id = frappe.get_value(
				'Electronic Payment Profile',
				{'customer': doc.customer},
				'party_profile'
			)	
		payment_profile_id = frappe.get_value(
			'Electronic Payment Profile',
			{'customer': doc.customer},
			'payment_profile_id'
		)

		try:
			currency = frappe.defaults.get_global_default('currency').lower()
			response = stripe.Charge.create(
				amount=int(doc.grand_total * self.currency_multiplier(currency)),
				currency=currency,
				customer=customer_profile_id,
				source=payment_profile_id,
				description=doc.name,  # optional
			)
			if response.status == 'succeeded':
				if not frappe.get_value('Electronic Payment Profile', {'customer': doc.customer, 'payment_profile_id': payment_profile_id}, 'retain'):
					frappe.get_doc('Electronic Payment Profile', {'customer': doc.customer, 'payment_profile_id': payment_profile_id}).delete()
				create_payment_entry(doc, data, response.id)
				return {'message': 'Success', 'transaction_id': response.id}
			elif response.status == 'pending':
				# TODO: is there confirmation if it eventually goes through? How to handle?
				return {'error': 'Payment pending'}
			else:  # 'failed'
				return {'error': 'Payment failed'}
		except Exception as e:
			try:
				frappe.log_error(frappe.get_traceback(), f'{e.code}: {e.type}. {e.message}')
				return {'error': f'{e.code}: {e.type}. {e.message}'}
			except:  # non-Stripe error, something else went wrong
				frappe.log_error(frappe.get_traceback(), f'{e}')
				return {'error': f'{e}'}

	def refund_credit_card(self, doc, data):
		"""
		TODO: clarify where this function is called and what data can be passed
		Function needs: transaction ID of original charge and amount to refund
		    (amount technically only needed if it's a partial refund, will default to entire charge)
		"""
		self.get_password(doc.company)
		try:
			currency = frappe.defaults.get_global_default('currency').lower()
			response = stripe.Refund.create(
				charge=data.get('transaction_id'),
				amount=int(data.get('amount') * self.currency_multiplier(currency))
			)
			if response.status == 'succeeded':
				# TODO: reverse/cancel payment entry
				return {'message': 'Success', 'transaction_id': response.id}
			elif response.status == 'pending':
				# TODO: is there confirmation if it eventually goes through? How to handle?
				return {'error': 'Refund pending'}
			else:  # 'failed' for credit/debit cards. Can be 'requires_action' or 'canceled' for other methods
				return {'error': f'Refund {response.status}'}
		except Exception as e:
			try:
				frappe.log_error(frappe.get_traceback(), f'{e.code}: {e.type}. {e.message}')
				return {'error': f'{e.code}: {e.type}. {e.message}'}
			except:  # non-Stripe error, something else went wrong
				frappe.log_error(frappe.get_traceback(), f'{e}')
				return {'error': f'{e}'}

	def void_transaction(self, doc, data):
		# No separate workflow for this in Stripe
		self.refund_credit_card(doc, data)
