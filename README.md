<!-- Copyright (c) 2025, AgriTheory and contributors
For license information, please see license.txt-->

## Electronic Payments

An application with electronic payments utilities for ERPNext.

### Installation Guide

First, set up a new bench and substitute a path to the python version to use. Python should be 3.10 latest for `version-15`. These instructions use [pyenv](https://github.com/pyenv/pyenv) for managing environments.
```shell
bench init --frappe-branch version-15 {{ bench name }} --python ~/.pyenv/versions/3.10.13/bin/python3
```

Create a new site in that bench
```shell
cd {{ bench name }}
bench new-site {{ site name }} --force --db-name {{ site name }}
bench use {{ site name }}
```

Download apps
```shell
bench get-app erpnext --branch version-15
bench get-app payments --branch version-15
bench get-app webshop --branch version-15
bench get-app electronic_payments --branch version-15 git@github.com:agritheory/electronic_payments.git 
```

Install the apps to your site
```shell
bench --site {{ site name }} install-app erpnext payments webshop electronic_payments
```

Set developer mode in `site_config.json`
```shell
nano sites/{{ site name }}/site_config.json
# Add this line:
  "developer_mode": 1,

```
Install pre-commit:
```shell
# ~/frappe-bench/apps/electronic_payments/
pre-commit install
```

Add the site to your computer's hosts file to be able to access it via: `http://{{ site name }}:[8000]`. You'll need to enter your root password to allow your command line application to make edits to this file.
```shell
bench --site {{site name}} add-to-hosts
```

Launch your bench (note you should be using Node.js v20)
```shell
bench start
```

## Optional: Set up Developer API Keys and Install a Demo Company to Test App Functionality
Electronic Payments comes packaged with a script to optionally install a [demo Company and its data](./exampledata.md) to test the application's functionality. If there are certain environment variables present for a provider's test API keys (see below) when the script runs, it will automatically create an Electronic Payments Settings document for the preferred provider.

1. Create an account with the preferred provider and get test API keys. This process is different for each provider:

**Authorize.net**
- [Create a sandbox account](https://developer.authorize.net/hello_world/sandbox.html) - this is completely separate from a production account
- Log into the account and turn the Sandbox account to "Live Mode" (somewhat confusing, but in the Sandbox account, "Test Mode" is only to check if your credential work, the "Live Mode" allows you to run and "process" test transactions)
- Collect the API Login ID from Account -> API Credentials and Keys page and generate a new transaction key (the one sent over email may lead to invalid value errors)
- Use Authorize.net's [Testing Guide](https://developer.authorize.net/hello_world/testing_guide.html) for test card and account numbers

**Stripe**
- [Create a Stripe account](www.stripe.com)
- Flip the account to "Test Mode", and collect the Secret key from the Dashboard
- Use Stripe's [Testing Guide](https://docs.stripe.com/testing) for test card and account numbers

**Mercury**
- Refer to the [API sandbox documentation](https://docs.mercury.com/reference/using-the-mercury-sandbox-for-api-testing) for full instructions to [create a Mercury sandbox account](https://sandbox.mercury.com/signup)
- Set up an API key by clicking on the Company logo in the upper-left corner then navigate to Settings -> API Tokens. Add a new token with read/write access. This also requires a whitelisted IP address - make sure to use a static IP address when specifying this, if the IP address making the API call doesn't match, the API response will return a 401 unauthorized error. Running a VPN, such as Tailscale, to set the IP address and make API calls can help
- Mercury API calls require the sending account's ID. You need an API call to get this info

Option 1 (UI): The first time finding it can be done by leaving the Sending Provider info blank in Settings, then manually entering your Mercury credentials. Leave the Merchant ID field blank and click "Save" - the validate function will show the account ID options associated with your sandbox credentials. Copy one of the checking account options with an available balance into the Merchant ID field and then save it in your environment variables.

Option 2 (command line): Alternatively, you can run the following code from `bench console`, assuming the API key is saved as an environment variable, then copy the appropriate account's ID into the `MERCURY_ACCOUNT_ID` environment variable:

```py
import requests
key = os.environ.get("MERCURY_API_KEY")
url = "https://api-sandbox.mercury.com/api/v1/accounts"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
resp = requests.get(url, headers=headers)
resp.raise_for_status()
rj = resp.json()

for acc in rj["accounts"]:
    print(f'ID (copy this): {acc["id"]}\n{acc["name"]} - Avail Balance: {acc["availableBalance"]}\n')
```

2. Save your preferred provider's test API keys as shell environment variables. If you're testing multiple providers, you can have keys saved for each of them. The next step explains how to specify which provider(s) to use in an automatically-generated Electronic Payments Settings doc.
```shell
# Authorize.net
export AUTHORIZE_API_KEY='your_sandbox_api_login_id'
export AUTHORIZE_TRANSACTION_KEY='your_sandbox_transaction_key'

# Mercury
export MERCURY_API_KEY='secret-token:mercury_sandbox_wma_...'
export MERCURY_ACCOUNT_ID="your_sandbox_checking_account_profile_id"

# Stripe
export STRIPE_API_KEY='sk_test_...'
```

3. Run the script to install the demo data. If you have API keys set as environment variables, the script will look for them to automatically create an Electronic Payments Settings document (necessary to test payment functionality). It will first check for any present, if it finds multiple keys, then it will create using alphabetical ordering and the following logic:

- If Authorize.net keys are present, then it uses that provider for both accepting and sending payments. If there are no Authorize.net keys, it then checks for Stripe keys
- If Stripe keys are present, it uses Stripe as the accepting provider. If Mercury keys are also present, it enables sending payments and uses Mercury as the sending provider (if not, the script won't enable sending payments)
- If Stripe keys are not present the script won't create an Electronic Payments Settings doc (this may be done manually in the test site later). This is because Mercury is not set up to accept payments

If you have API keys for more than one provider, you can pass `a_provider` and `s_provider` arguments when executing the test script to specify which one to use for accepting and sending payments, respectively. The argument is the lowercase letter of the first initial of the provider's name. If the specified provider's keys aren't present, the script won't create the Electronic Payments Settings document.
```shell
# No provider specified - if Authorize.net keys present, use this to set it as both accepting and sending providers
bench execute 'electronic_payments.tests.setup.before_test'

# Create Electronic Payments Settings for Authorize.net to accept and Mercury to send payments (provider keys must be present)
bench execute --kwargs "{'a_provider': 'a', 's_provider': 'm'}" 'electronic_payments.tests.setup.before_test'

# Create Electronic Payments Settings for Stripe to accept and Authorize.net to send payments (provider keys must be present)
bench execute --kwargs "{'a_provider': 's', 's_provider': 'a'}" 'electronic_payments.tests.setup.before_test'

# Create Electronic Payments Settings for Stripe to accept and Mercury to send payments (provider keys must be present)
bench execute --kwargs "{'a_provider': 's', 's_provider': 'm'}" 'electronic_payments.tests.setup.before_test'
```

To run the Stripe mock, start the docker container:
```shell
docker run --rm -it -p 12111-12112:12111-12112 stripe/stripe-mock:latest
```
The endpoint should be configured in the Electronic Payments Settings with the following values:
```json
# values here / TBD
```

To run `mypy` locally:
```shell
source env/bin/activate
mypy ./apps/electronic_payments --ignore-missing-imports
```

To run tests locally on the test data:
```shell
source env/bin/activate
pytest ./apps/electronic_payments/electronic_payments/tests/ -s --disable-warnings
```
