## Electronic Payments

An application with electronic payments utilities for ERPNext.

### Installation Guide

First, set up a new bench and substitute a path to the python version to use. Python should be 3.10 latest for `version-14`. These instructions use [pyenv](https://github.com/pyenv/pyenv) for managing environments.
```shell
bench init --frappe-branch version-14 {{ bench name }} --python ~/.pyenv/versions/3.10.13/bin/python3
```

Create a new site in that bench
```shell
cd {{ bench name }}
bench new-site {{ site name }} --force --db-name {{ site name }}
bench use {{ site name }}
```

Download apps
```shell
bench get-app payments
bench get-app erpnext --branch version-14
bench get-app electronic_payments --branch version-14 git@github.com:agritheory/electronic_payments.git 
```

Install the apps to your site
```shell
bench --site {{ site name }} install-app erpnext payments electronic_payments
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

Launch your bench (note you should be using Node.js v18)
```shell
bench start
```

Optional: install a [demo Company and its data](./exampledata.md) to test the Electronic Payments module's functionality
```shell
bench execute 'electronic_payments.tests.setup.before_test'
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