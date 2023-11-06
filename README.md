## Electronic Payments

An application with electronic payments utilities for ERPNext.

[TODO: create version-14 branch]

### Installation Guide

First, set up a new bench and substitute a path to the python version to use. Python should be 3.8 latest for V13 and 3.10 latest for V14. These instructions use [pyenv](https://github.com/pyenv/pyenv) for managing environments.
```shell
# Version 13
bench init --frappe-branch version-13 {{ bench name }} --python ~/.pyenv/versions/3.8.12/bin/python3

# Version 14
bench init --frappe-branch version-14 {{ bench name }} --python ~/.pyenv/versions/3.10.3/bin/python3
```

Create a new site in that bench
```shell
cd {{ bench name }}
bench new-site {{ site name }} --force --db-name {{ site name }}
```

Download the ERPNext app
```shell
# Version 13
bench get-app erpnext --branch version-13

# Version 14
bench get-app payments
bench get-app erpnext --branch version-14
```
**Important note for benches installed with Python 3.10 or later:**

If you created a bench using Python 3.10 or later, you must make the following manual fix to the Authorize.net package. The current state of the package does NOT support Python 3.10 ([see GitHub issue](https://github.com/AuthorizeNet/sdk-python/issues/154)) and the timing for this to be resolved is unknown.
```
# Activate the bench environment:
source env/bin/activate

# Install authorizenet package
pip install authorizenet
```
Open the file `env/lib/python3.10/site-packages/pyxb/binding/content.py` and change line 799 from `import collections` to `import collections.abc as collections` and save your changes.

Download the Electronic Payments application
```shell
bench get-app electronic_payments git@github.com:agritheory/electronic_payments.git 
```

Install the apps to your site
```shell
bench --site {{ site name }} install-app erpnext electronic_payments

# Optional: Check that all apps installed on your site
bench --site {{ site name }} list-apps
```

Set developer mode in `site_config.json`
```shell
nano sites/{{ site name }}/site_config.json
# Add this line:
  "developer_mode": 1,

```
Install pre-commit:
```
# ~/frappe-bench/apps/electronic_payments/
pre-commit install
```

Add the site to your computer's hosts file to be able to access it via: `http://{{ site name }}:[8000]`. You'll need to enter your root password to allow your command line application to make edits to this file.
```shell
bench --site {{site name}} add-to-hosts
```

Launch your bench (note you should be using Node.js v14 for a Version 13 bench and Node.js v16 for a Version 14 bench)
```shell
bench start
```

Optional: install a [demo Company and its data](./exampledata.md) to test the Electronic Payments module's functionality
```shell
bench execute 'electronic_payments.test_setup.before_test'
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