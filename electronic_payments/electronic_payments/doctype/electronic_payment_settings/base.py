# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt


from electronic_payments.electronic_payments.doctype.electronic_payment_settings.common import (
	exceeds_credit_limit,
	get_party_details,
	get_party_profile_id,
)


class BaseProvider:
	"""
	Base class for all payment providers. Code expects that the child provider-specific classes
	implement their own version for any method below that raises a `NotImplementedError`.

	For all methods:

	:param doc: may be a Sales Order, Sales Invoice, Purchase Order, or Purchase Invoice. When
	method is called from Customer or Supplier page, or from the portal (Customer or Supplier self
	-service), then it can be a frappe._dict with some/all of the following keys (depending on
	context):
	    {
	            "company": company in ERPNext (to collect the right Electronic Payment Settings),
	                "customer" or "supplier": the name of a Customer or Supplier doc in ERPNext,
	                "doctype": "Sales" or "Purchase" (determines the accepting or sending provider/keys),
	                "currency": currency code signifier in ERPNext,
	        }

	:param data: a dict object containing the necessary data to make an API call. This may be to
	create or update a payment method with the provider or to accept/send a payment against an
	existing payment method. The required data to create or update a payment method will depend on
	what the provider needs in their API calls. To accept or send a payment:
	    {
	            # Required:
	            "payment_profile_id": ID of a payment method with the provider,

	                # Optional:
	    "amount": amount to charge or pay (if not provided, looks for a payment term or the
	                doc's outstanding amount),
	                "payment_term": name of a Payment Term in ERPNext associated with the doc,
	                "ppm_name": name of a Portal Payment Method in ERPNext (to calculate configured fees),
	                "subject_to_credit_limit": 1/True or 0/False/not provided,
	        }
	"""

	def process_transaction(self, doc, data, bypass_je_pe_creation=False):
		"""
		Processes either accepting or sending a payment via the provider - override this method if
		the provider's payment workflow doesn't fit this pattern

		:param bypass_je_pe_creation: bool; default is False. If True, will not queue method that
		creates a Journal Entry or Payment Entry following a successful API response - used when
		method is called from a place such as Check Run, where that process is already creating a
		Payment Entry
		"""
		mop = data.mode_of_payment.replace("New ", "")
		party = get_party_details(doc)
		save_only = data.save_data == "Save payment data only"

		if mop == "Card" and data.get("save_data") == "Charge now":
			response = self.process_credit_card(doc, data)

		if not mop.startswith("Saved"):  # new payment method
			# find party profile (if used by provider)
			party_response = self.get_or_create_party_profile(doc)
			if party_response.get("message") == "Success":
				data.update({"party_profile_id": party_response.get("transaction_id")})

				# create payment method with provider, save ID to data
				pmt_profile_response = self.create_party_payment_profile(doc, data)
				if pmt_profile_response.get("message") == "Success":
					pp_doc = pmt_profile_response.get("payment_profile_doc")
					data.update({"payment_profile_id": pp_doc.payment_profile_id})
					if save_only:
						return pmt_profile_response
				else:  # error creating the payment profile
					return pmt_profile_response
			else:  # error getting / creating party profile
				return party_response
		elif (  # handle a saved method where amount exceeds credit limit
			mop.startswith("Saved")
			and data.get("subject_to_credit_limit")
			and exceeds_credit_limit(doc, data)
		):
			return {"error": "Credit Limit exceeded for selected Mode of Payment"}

		# charge or send transfer to the saved or newly created payment method
		if party.doctype == "Customer":
			response = self.charge_party_profile(doc, data)
		else:
			response = self.create_transfer_to_party_profile(
				doc, data, bypass_je_pe_creation=bypass_je_pe_creation
			)
		return response

	def get_or_create_party_profile(self, doc):
		"""
		Collects the party's profile ID with the provider
		"""
		party = get_party_details(doc)
		existing_party_id = get_party_profile_id(party.name, doc.company, self.provider)
		if existing_party_id:
			return {"message": "Success", "transaction_id": existing_party_id}
		else:
			party_profile_resp = self.create_party_profile(doc)
			return party_profile_resp

	def create_party_profile(self, doc):
		"""
		Implement in the provider class - creates a profile of the party with the provider

		If this functionality isn't supported or not required in provider's payment flow:
		- return {"message": "Success", "transaction_id": None}

		Successful API call:
		- return {"message": "Success", "transaction_id": str(party_profile_id)}

		Unsuccessful API call / Error:
		- return {"error": error_message}
		"""
		raise NotImplementedError

	def create_party_payment_profile(self, doc, data):
		"""
		Implement in the provider class - creates a payment method for the party with the provider

		If the provider doesn't support the "mode_of_payment" given in `data` dict:
		- return {"error": _("Mode of Payment not supported")}

		Successful API call:
		- create an Electronic Payment Profile (payment_profile in return statement) in ERPNext
		  and a Portal Payment Method, depending on that setting in Electronic Payment Settings
		- return {"message": "Success", "payment_profile_doc": payment_profile}

		Unsuccessful API call / Error:
		- return {"error": error_message}
		"""
		raise NotImplementedError

	def get_party_payment_profile(self, company, electronic_payment_profile_name):
		"""
		Implement in the provider class - gets payment details from provider for an Electronic
		Payment Profile (called from the Portal to edit a payment method)

		:param company: str; company in ERPNext (to get correct Electronic Payment Settings doc)
		:param electronic_payment_profile_name: str; name of the Electronic Payment Profile doc
		in ERPNext for a payment method

		Successful API call:
		- return {"message": "Success", "data": {payment method details}}

		Unsuccessful API call / Error:
		- the portal function calling this will raise a Permission Error
		"""
		return NotImplementedError

	def edit_payment_profile(self, company, electronic_payment_profile_name, data):
		"""
		Implement in the provider class - edits a payment method at the provider and in ERPNext

		:param company: str; company in ERPNext (to get correct Electronic Payment Settings doc)
		:param electronic_payment_profile_name: str; name of the Electronic Payment Profile doc
		in ERPNext for a payment method
		:param data: dict with details to update the payment method with the provider

		If this functionality isn't supported by the provider:
		- return {"error": reason why not support / recommended action}

		Successful API call:
		- edit the Electronic Payment Profile and Portal Payment Methods in ERPNext that are
		  attached to the payment method. For sending payment providers, this may include both
		  Wire and ACH methods
		- return {"message": "Success", "payment_profile_doc": payment_profile} where
		  payment_profile is the associated Electronic Payment Profile doc in ERPNext

		Unsuccessful API call / Error:
		- return {"error": error_message}
		"""
		return NotImplementedError

	def delete_payment_profile(self, company, payment_profile_id):
		"""
		Implement in the provider class - deletes a payment profile from the API and ERPNext

		If this functionality isn't supported by the provider:
		- return {"error": _("Not supported.")}

		Successful API call:
		- collect all Electronic Payment Profile docs associated with the payment_profile_id
		  (there may be both an ACH and Wire mode of payment with same ID for some providers)
		- delete the Electronic Payment Profile and Portal Payment Method docs from ERPNext
		- return {"message": "Success"}

		Unsuccessful API call / Error:
		- call frappe.log_error with details
		"""
		return NotImplementedError

	def delete_party_profile(self, company, party, party_profile_id):
		"""
		Implement in the provider class - deletes a party profile with the provider

		If this functionality isn't used or supported by the provider:
		- return {"message": "Success"}

		Successful API call:
		- return {"message": "Success"}

		Unsuccessful API call / Error:
		- call frappe.log_error with details
		"""
		return NotImplementedError

	def process_credit_card(self, doc, data):
		"""
		Implement in the provider class - for a one-time charge of a credit card (not saved / not
		associated with a party profile)

		If this functionality isn't supported by the provider:
		- return {"error": _("Not supported.")}

		Successful API call:
		- save the transaction ID to doc's electronic_payment_reference field
		- run common.py's process_electronic_payment via queue_method_as_admin
		- return {"message": "Success", "transaction_id": str(transaction_id)}

		Unsuccessful API call / Error:
		- return {"error": error_message}
		"""
		raise NotImplementedError

	def charge_party_profile(self, doc, data):
		"""
		Implement in the provider class - for accepting a payment from an existing party's profile

		If this functionality isn't supported by the provider:
		- return {"error": _("Not supported.")}

		Successful API call:
		- save the transaction ID to doc's electronic_payment_reference field
		- delete the payment profile from ERPNext if retain isn't checked in EPP doc
		- run common.py's process_electronic_payment via queue_method_as_admin
		- return {"message": "Success", "transaction_id": str(transaction_id)}

		Unsuccessful API call / Error:
		- return {"error": error_message}
		"""
		raise NotImplementedError

	def create_transfer_to_party_profile(self, doc, data, bypass_je_pe_creation=False):
		"""
		Implement in the provider class - for sending a payment to an existing party's profile

		If this functionality isn't supported by the provider:
		- return {"error": _("Not supported.")}

		Successful API call:
		- save the transaction ID to doc's electronic_payment_reference field
		- delete the payment profile from ERPNext if retain isn't checked in EPP doc
		- run common.py's process_electronic_payment via queue_method_as_admin if
		  bypass_je_pe_creation is False (flag is used when called from Check Run)
		- return {"message": "Success", "transaction_id": str(transaction_id)}

		Unsuccessful API call / Error:
		- return {"error": error_message}
		"""
		raise NotImplementedError

	def refund_transaction(self, doc, data):
		"""
		Implement in the provider class - refunds a transaction

		If this functionality isn't supported by the provider:
		- return {"error": _("Not supported.")}

		Successful API call:
		- handle the refund in ERPNext
		- return {"message": "Success", "transaction_id": str(transaction_id)}

		Unsuccessful API call / Error:
		- return {"error": error_message}
		"""
		raise NotImplementedError

	def void_transaction(self, doc, data):
		"""
		Implement in the provider class - voids an unsettled transaction

		If this functionality isn't supported by the provider:
		- return {"error": _("Not supported.")}

		Successful API call:
		- handle the voided transaction in ERPNext
		- return {"message": "Success", "transaction_id": str(transaction_id)}

		Unsuccessful API call / Error:
		- return {"error": error_message}
		"""
		return NotImplementedError

	def get_transaction_details(self, company, transaction_id):
		"""
		Implement in the provider class - gets the payment details for a given transaction ID.
		Supports refund_transaction for certain providers

		:param company: str; company in ERPNext (to get correct Electronic Payment Settings doc)
		:param transaction_id: str; provider's ID for the transaction

		If this functionality isn't supported by the provider:
		- return {"error": _("Not supported.")}

		Successful API call:
		- return {"message": "Success", "payment_details": payment_dict} where payment_dict has
		  select payment details for the given transaction

		Unsuccessful API call / Error:
		- return {"error": error_message}
		"""
		return NotImplementedError
