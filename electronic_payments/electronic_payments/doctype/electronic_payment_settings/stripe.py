import json
import datetime
from dateutil.relativedelta import relativedelta

import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password
from frappe.utils.data import flt

import stripe
from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	exceeds_credit_limit,
	calculate_payment_method_fees,
	process_electronic_payment,
)

"""
Credit cards
- card number
- expiration date month (M) able to convert to int
- expiration date year (YYYY) able to convert to int
- CVC code (Stripe will attempt to verify validity)
- Currency. Code uses the global default

Bank Accounts
- Code handles ACH transactions for type 'us_bank_account' (API requests require
  different payment method type and related data for non-US options)
- Requires customer accepting a mandate and a verification process - either instant
  (through Plaid service) or 2-4 days if done manually. (Stripe makes 2 microdeposits
  to the account, the account holder must relay the amounts to the company, which must
  be sent back to Stripe to verify).
- Account holder type: 'individual' or 'company'. Code pulls `customer_type` from
  Customer doctype
- Account holder name
- Account type ('checking' or 'savings', defaults to 'checking')
- Account number
- Routing number

General Notes:
- Currency: amounts in charges and refunds are in the smallest currency unit (for USD,
  it's in cents so a $1.00 charge would use amount=100). There are a handful of zero-
  decimal currencies detailed in docs (https://stripe.com/docs/currencies). The use of
  int in amount drops any remaining amount in case of three-decimal currencies (Stripe
  requires the least-significant digit of the decimal to be zero)
- There's only one Refund object in stripe, which works for CCs/banks. There is no void
  transaction option
- Stripe validations:
  - CVC code for cards
  - If billing address provided, line_1 and zip code
"""


class Stripe:
	def get_password(self, company):
		settings = frappe.get_doc("Electronic Payment Settings", {"company": company})
		if not settings:
			frappe.msgprint(_(f"No Electronic Payment Settings found for {company}-Stripe"))
		else:
			stripe.api_key = get_decrypted_password(
				settings.doctype, settings.name, "api_key", raise_exception=False
			)

	def process_transaction(self, doc, data):
		mop = data.mode_of_payment.replace("New ", "")
		if mop.startswith("Saved"):
			if data.get("subject_to_credit_limit") and exceeds_credit_limit(doc, data):
				return {"error": "Credit Limit exceeded for selected Mode of Payment"}
			if data.get("ppm_name"):
				data.update({"additional_charges": calculate_payment_method_fees(doc, data)})
			response = self.charge_customer_profile(doc, data)
		elif mop == "ACH":
			# TODO: update UI to handle response, handle save_data option
			response = self.create_payment_intent(doc, data)
		else:  # New Card
			if data.get("save_data") == "Charge now":
				response = self.process_credit_card(doc, data)
			else:  # saves payment data (will delete payment profile doc after charging if for txn only)
				customer_response = self.create_customer_profile(doc, data)
				if customer_response.get("message") == "Success":
					data.update({"customer_profile_id": customer_response.get("transaction_id")})
					pmt_profile_response = self.create_customer_payment_profile(doc, data)
					if pmt_profile_response.get("message") == "Success":
						pp_doc = pmt_profile_response.get("payment_profile_doc")
						data.update({"payment_profile_id": pp_doc.payment_profile_id})
						response = self.charge_customer_profile(doc, data)
					else:  # error creating the customer payment profile
						return pmt_profile_response
				else:  # error creating customer profile
					return customer_response
		return response

	def currency_multiplier(self, currency):
		zero_decimal = (
			"bif",
			"clp",
			"djf",
			"gnf",
			"jpy",
			"kmf",
			"krw",
			"mga",
			"pyg",
			"rwf",
			"ugx",
			"vnd",
			"vuv",
			"xaf",
			"xof",
			"xpf",
		)
		return 100 if currency not in zero_decimal else 1

	def create_payment_method(self, doc, data):
		self.get_password(doc.company)
		try:
			if data.mode_of_payment.replace("New ", "") == "Card":
				card_number = data.get("card_number")
				card_number = card_number.replace(" ", "")
				# TODO: replace with UI data collection
				response = stripe.PaymentMethod.create(
					type="card",
					card={
						"number": card_number,
						"exp_month": int(data.get("card_expiration_date").split("-")[1]),
						"exp_year": int(data.get("card_expiration_date").split("-")[0]),
						"cvc": data.get("card_cvc"),
					},
				)
			elif (
				data.mode_of_payment.replace("New ", "") == "ACH"
			):  # TODO: replace with UI data collection / mandate / verification process
				response = stripe.PaymentMethod.create(
					type="us_bank_account",
					us_bank_account={
						"account_holder_type": frappe.get_value(
							"Customer", doc.customer, "customer_type"
						).lower(),  # 'individual' or 'company'
						"routing_number": str(data.get("routing_number")),
						"account_number": str(data.get("account_number")),
					},
					billing_details={"name": data.get("account_holders_name"), "email": ""},
				)
			else:
				frappe.throw(_("Unsupported payment method provided."))

			return {"message": "Success", "transaction_id": response.id}
		except Exception as e:
			try:
				frappe.log_error(message=frappe.get_traceback(), title=f"{e.code}: {e.type}. {e.message}")
				return {
					"error": f"{e.code}: {e.type}. {e.message}"
				}  # e.code has status code, e.type is one of 4 error types, e.message is a human-readable message providing more details about the error
			except Exception as _e:  # non-Stripe error, something else went wrong
				frappe.log_error(message=frappe.get_traceback(), title=f"{e}")
				return {"error": f"{e}"}

	def create_payment_intent(self, doc, data):
		# For New ACH transactions, creates an un-confirmed PaymentIntent and returns the client secret
		self.get_password(doc.company)
		try:
			total_to_charge = flt(
				doc.grand_total + (data.get("additional_charges") or 0),
				frappe.get_precision(doc.doctype, "grand_total"),
			)
			customer_id = self.create_customer_profile(doc, data)
			if customer_id.get("message") == "Success":
				currency = frappe.defaults.get_global_default("currency").lower()
				response = stripe.PaymentIntent.create(
					amount=int(total_to_charge * self.currency_multiplier(currency)),
					currency=currency,
					customer=customer_id,
					description=doc.name,
					setup_future_usage="off_session",  # Indicates this payment method will be used in future PaymentIntents and saves to Customer. off_session = can charge customer at later time, on_session = can only charge in live session
					payment_method_types=["us_bank_account"],
					# payment_method_options={
					# 	"us_bank_account": {
					# 	"financial_connections": {"permissions": ["payment_method", "balances"]},
					# 	},
					# },
				)
				return {
					"message": "Success",
					"transaction_id": response.id,
					"client_secret": response.client_secret,
				}
			else:  # error creating customer profile
				return customer_id
		except Exception as e:
			try:
				frappe.log_error(message=frappe.get_traceback(), title=f"{e.code}: {e.type}. {e.message}")
				return {
					"error": f"{e.code}: {e.type}. {e.message}"
				}  # e.code has status code, e.type is one of 4 error types, e.message is a human-readable message providing more details about the error
			except Exception as _e:  # non-Stripe error, something else went wrong
				frappe.log_error(message=frappe.get_traceback(), title=f"{e}")
				return {"error": f"{e}"}

	def process_credit_card(self, doc, data):
		self.get_password(doc.company)
		try:
			pm_response = self.create_payment_method(doc, data)
			if pm_response.get("message") == "Success":
				currency = frappe.defaults.get_global_default("currency").lower()
				card_number = data.get("card_number")
				card_number = card_number.replace(" ", "")
				total_to_charge = flt(
					doc.grand_total + (data.get("additional_charges") or 0),
					frappe.get_precision(doc.doctype, "grand_total"),
				)
				response = stripe.PaymentIntent.create(
					amount=int(total_to_charge * self.currency_multiplier(currency)),
					currency=currency,
					confirm=True,
					description=doc.name,
					payment_method=pm_response.get("transaction_id"),
					# automatic_payment_methods={"enabled": True},  # Company would need to set up payment methods in their Stripe dashboard
					# off_session=False if data.get('save_date') != 'Charge now' else True,  # Use with confirm=True and collecting payment data to charge later
					# customer=None,  # Stripe customer ID. If provided and setup_future_usage is present, will save payment method to that customer for future use
					# setup_future_usage='off_session',  # Indicates this payment method will be used in future PaymentIntents. Saves to Customer if present (if not, can be attached to a customer after transaction completes). off_session = can charge customer at later time, on_session = can only charge in live session
				)

				if response.status == "succeeded":
					frappe.db.set_value(doc.doctype, doc.name, "electronic_payment_reference", str(response.id))
					frappe.enqueue(
						process_electronic_payment,
						queue="short",
						timeout=3600,
						is_async=True,
						now=False,
						doc=doc,
						data=data,
						transaction_id=str(response.id),
					)
					return {"message": "Success", "transaction_id": response.id}
				elif response.status == "processing":
					# TODO: handle follow up in UI
					return {"error": "Transaction processing"}
				elif response.status in [
					"requires_action",
					"requires_confirmation",
					"requires_capture",
				]:
					# TODO: requires_action needs customer authentication (handle on client-side), parameter values should bypass other statuses
					return {"error": f'Further action required: {response.status.split("_")[-1]}'}
				else:  # 'requires_payment_method' aka the payment attempt failed
					return {"error": "Payment failed"}
			else:  # error creating the payment method
				return pm_response
		except Exception as e:
			try:
				frappe.log_error(message=frappe.get_traceback(), title=f"{e.code}: {e.type}. {e.message}")
				return {
					"error": f"{e.code}: {e.type}. {e.message}"
				}  # e.code has status code, e.type is one of 4 error types, e.message is a human-readable message providing more details about the error
			except Exception as _e:  # non-Stripe error, something else went wrong
				frappe.log_error(message=frappe.get_traceback(), title=f"{e}")
				return {"error": f"{e}"}

	def create_customer_profile(self, doc, data):
		self.get_password(doc.company)
		try:
			existing_customer_id = frappe.get_value("Customer", doc.customer, "electronic_payment_profile")
			if existing_customer_id:
				return {"message": "Success", "transaction_id": existing_customer_id}
			else:
				response = stripe.Customer.create(name=doc.customer)
				frappe.db.set_value("Customer", doc.customer, "electronic_payment_profile", response.id)
				return {"message": "Success", "transaction_id": response.id}
		except Exception as e:
			try:
				frappe.log_error(message=frappe.get_traceback(), title=f"{e.code}: {e.type}. {e.message}")
				return {"error": f"{e.code}: {e.type}. {e.message}"}
			except Exception as _e:  # non-Stripe error, something else went wrong
				frappe.log_error(message=frappe.get_traceback(), title=f"{e}")
				return {"error": f"{e}"}

	def create_customer_payment_profile(self, doc, data):
		self.get_password(doc.company)
		if not data.get("customer_profile_id"):
			customer_profile_id = frappe.get_value("Customer", doc.customer, "electronic_payment_profile")
		else:
			customer_profile_id = data.get("customer_profile_id")

		try:
			pm_response = self.create_payment_method(doc, data)
			if pm_response.get("message") == "Success":
				response = stripe.PaymentMethod.attach(
					pm_response.get("transaction_id"),
					customer=customer_profile_id,
				)
				mop = data.mode_of_payment.replace("New ", "")
				if mop == "Card":
					card_number = data.get("card_number")
					card_number = card_number.replace(" ", "")
					last4 = card_number[-4:]
				else:
					account_number = data.get("account_number")
					account_number = account_number.replace(" ", "")
					last4 = account_number[-4:]

				payment_profile = frappe.new_doc("Electronic Payment Profile")
				payment_profile.party_type = "Customer"
				payment_profile.party = doc.customer
				payment_profile.payment_type = mop
				payment_profile.reference = f"**** **** **** {last4}" if mop == "Card" else f"*{last4}"
				payment_profile.payment_profile_id = str(response.id)
				payment_profile.party_profile = str(customer_profile_id)
				payment_profile.retain = 1 if data.save_data == "Retain payment data for this party" else 0
				payment_profile.save()

				if payment_profile.retain and frappe.get_value(
					"Electronic Payment Settings", {"company": doc.company}, "create_ppm"
				):
					ppm = frappe.new_doc("Portal Payment Method")
					ppm.mode_of_payment = frappe.get_value(
						"Electronic Payment Settings", {"company": doc.company}, "mode_of_payment"
					)
					ppm.label = f"{mop}-{last4}"
					ppm.default = 0
					ppm.electronic_payment_profile = payment_profile.name
					ppm.service_charge = 0
					ppm.parent = payment_profile.party
					ppm.parenttype = payment_profile.party_type
					ppm.save()
					cust = frappe.get_doc("Customer", doc.customer)
					cust.append("portal_payment_method", ppm)
					cust.save()

				return {"message": "Success", "payment_profile_doc": payment_profile}
			else:  # error creating the payment method
				return pm_response
		except Exception as e:
			try:
				frappe.log_error(message=frappe.get_traceback(), title=f"{e.code}: {e.type}. {e.message}")
				return {"error": f"{e.code}: {e.type}. {e.message}"}
			except Exception as _e:  # non-Stripe error, something else went wrong
				frappe.log_error(message=frappe.get_traceback(), title=f"{e}")
				return {"error": f"{e}"}

	def charge_customer_profile(self, doc, data):
		self.get_password(doc.company)
		if not data.get("customer_profile_id"):
			customer_profile_id = frappe.get_value("Customer", doc.customer, "electronic_payment_profile")
		else:
			customer_profile_id = data.get("customer_profile_id")

		payment_profile_id = data.get("payment_profile_id")

		try:
			currency = frappe.defaults.get_global_default("currency").lower()
			total_to_charge = flt(
				doc.grand_total + (data.get("additional_charges") or 0),
				frappe.get_precision(doc.doctype, "grand_total"),
			)
			response = stripe.PaymentIntent.create(
				amount=int(total_to_charge * self.currency_multiplier(currency)),
				currency=currency,
				confirm=True,
				customer=customer_profile_id,
				payment_method_types=["card", "us_bank_account"],
				payment_method=payment_profile_id,
				description=doc.name,
			)
			if response.status == "succeeded":
				if not frappe.get_value(
					"Electronic Payment Profile",
					{"party": doc.customer, "payment_profile_id": payment_profile_id},
					"retain",
				):
					frappe.get_doc(
						"Electronic Payment Profile",
						{"party": doc.customer, "payment_profile_id": payment_profile_id},
					).delete()
					stripe.PaymentMethod.detach(payment_profile_id)
				frappe.db.set_value(doc.doctype, doc.name, "electronic_payment_reference", str(response.id))
				frappe.enqueue(
					process_electronic_payment,
					queue="short",
					timeout=3600,
					is_async=True,
					now=False,
					doc=doc,
					data=data,
					transaction_id=str(response.id),
				)
				return {"message": "Success", "transaction_id": response.id}
			elif response.status == "processing":
				# TODO: handle follow up in UI
				return {"error": "Payment processing"}
			elif response.status in [
				"requires_action",
				"requires_confirmation",
				"requires_capture",
			]:
				# TODO: requires_action needs customer authentication (handle on client-side), parameter values should bypass other statuses
				return {"error": f'Further action required: {response.status.split("_")[-1]}'}
			else:  # 'requires_payment_method' aka the payment attempt failed
				return {"error": "Payment failed"}
		except Exception as e:
			try:
				frappe.log_error(message=frappe.get_traceback(), title=f"{e.code}: {e.type}. {e.message}")
				return {"error": f"{e.code}: {e.type}. {e.message}"}
			except Exception as _e:  # non-Stripe error, something else went wrong
				frappe.log_error(message=frappe.get_traceback(), title=f"{e}")
				return {"error": f"{e}"}

	def refund_transaction(self, doc, data):
		"""
		TODO: clarify where this function is called and what data can be passed
		Function needs: transaction ID of original charge and amount to refund
		        (amount technically only needed if partial refund, will default to entire charge)
		"""
		self.get_password(doc.company)
		orig_transaction_id = doc.electronic_payment_reference

		try:
			currency = frappe.defaults.get_global_default("currency").lower()
			response = stripe.Refund.create(
				payment_intent=orig_transaction_id,
				amount=int(data.get("amount") * self.currency_multiplier(currency)),
			)
			if response.status == "succeeded":
				# TODO: reverse/cancel payment/journal entry
				return {"message": "Success", "transaction_id": response.id}
			elif response.status == "pending":
				# TODO: handle follow up in UI
				return {"error": "Refund pending"}
			else:  # 'failed' for credit/debit cards. Can be 'requires_action' or 'canceled' for other methods
				return {"error": f"Refund {response.status}"}
		except Exception as e:
			try:
				frappe.log_error(message=frappe.get_traceback(), title=f"{e.code}: {e.type}. {e.message}")
				return {"error": f"{e.code}: {e.type}. {e.message}"}
			except Exception as _e:  # non-Stripe error, something else went wrong
				frappe.log_error(message=frappe.get_traceback(), title=f"{e}")
				return {"error": f"{e}"}

	def void_transaction(self, doc, data):
		# No separate workflow for this in Stripe
		self.refund_transaction(doc, data)

	def delete_payment_profile(self, company, payment_profile_id):
		# Delete from ERPNext
		epp_name = frappe.get_value(
			"Electronic Payment Profile",
			{"payment_profile_id": payment_profile_id},
		)
		pmm_name = frappe.get_value("Portal Payment Method", {"electronic_payment_profile": epp_name})

		frappe.delete_doc("Portal Payment Method", pmm_name)
		frappe.delete_doc("Electronic Payment Profile", epp_name)

		# Delete from API
		self.get_password(company)
		try:
			response = stripe.PaymentMethod.detach(payment_profile_id)
			return {"message": "Success"}
		except Exception as e:
			try:
				frappe.log_error(message=frappe.get_traceback(), title=f"{e.code}: {e.type}. {e.message}")
				return {"error": f"{e.code}: {e.type}. {e.message}"}
			except Exception as _e:  # non-Stripe error, something else went wrong
				frappe.log_error(message=frappe.get_traceback(), title=f"{e}")
				return {"error": f"{e}"}

	def delete_customer_profile(self, company, customer):
		# Delete from ERPNext
		customer_profile_id = frappe.get_value(
			"Customer",
			customer,
			"electronic_payment_profile",
		)
		frappe.set_value("Customer", customer, "electronic_payment_profile", "")

		# Delete from API
		self.get_password(company)
		try:
			response = stripe.Customer.delete(customer_profile_id)
			if response.deleted:
				return {"message": "Success"}
			else:
				frappe.log_error(
					message=frappe.get_traceback(),
					title=f"Error deleting profile for {customer}",
				)
		except Exception as e:
			try:
				frappe.log_error(message=frappe.get_traceback(), title=f"{e.code}: {e.type}. {e.message}")
				return {"error": f"{e.code}: {e.type}. {e.message}"}
			except Exception as _e:  # non-Stripe error, something else went wrong
				frappe.log_error(message=frappe.get_traceback(), title=f"{e}")
				return {"error": f"{e}"}


def fetch_stripe_transactions(settings):
	"""
	API call to collect all charge or payment transactions since midnight the day prior
	to when called. Returns the API response of transaction data.

	Assumptions:
	- Scheduler called at midnight local time and retrieves transactions as of midnight
	  one day prior

	:param settings: Electronic Payment Settings document
	:return: list of frappe._dict objects including transactional data for each transaction
	"""
	settings = frappe._dict(json.loads(settings)) if isinstance(settings, str) else settings
	# utc_one_day_ago = datetime.datetime.now(datetime.timezone.utc) + relativedelta(days=-1)
	from_datetime = (
		datetime.datetime.combine(datetime.date.today(), datetime.time(0))
	) + relativedelta(
		days=-1
	)  # Midnight one day ago
	from_timestamp = int(
		from_datetime.timestamp()
	)  # TODO: more precision using timezones? A timestamp from naive datetime assumes local time based on the machine calling this function
	transactions = []

	try:
		response = stripe.BalanceTransaction.list(
			limit=100, created={"gte": from_timestamp}  # requires Unix timestamp as integer
		)
		if hasattr(response, "data"):
			batch_txns = [frappe._dict(txn) for txn in response["data"]]
			transactions.extend(batch_txns)
		# Collect remaining transactions if more than 100
		while response["has_more"]:
			last_id = response["data"][-1]["id"]
			response = stripe.BalanceTransaction.list(
				limit=100, created={"gte": from_timestamp}, starting_after=last_id
			)
			if hasattr(response, "data"):
				batch_txns = [frappe._dict(txn) for txn in response["data"]]
				transactions.extend(batch_txns)
		return {"message": "Success", "transactions": transactions}
	except Exception as e:
		try:
			frappe.log_error(message=frappe.get_traceback(), title=f"{e.code}: {e.type}. {e.message}")
			return {"error": f"{e.code}: {e.type}. {e.message}"}
		except Exception as _e:  # non-Stripe error, something else went wrong
			frappe.log_error(message=frappe.get_traceback(), title=f"{e}")
			return {"error": f"{e}"}
