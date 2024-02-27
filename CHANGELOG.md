# CHANGELOG



## v0.2.0 (2024-02-27)

### Chore

* chore: migrate to esbuild bundler ([`4e19e8a`](https://github.com/agritheory/electronic_payments/commit/4e19e8ac06981de4437635c637b47d5c396f1d40))

* chore: fix mypy instructions in readme ([`9d9e300`](https://github.com/agritheory/electronic_payments/commit/9d9e3001c973df9e1aaec1f46bd7eaefad52f6dd))

* chore: setup mypy dependency and instruction ([`6628edf`](https://github.com/agritheory/electronic_payments/commit/6628edf77d64f462a13120bbe5020110e5abb83c))

* chore: prettier ([`e0c7b67`](https://github.com/agritheory/electronic_payments/commit/e0c7b67716bd2369c621e3b4ed12f368b0a74d8b))

* chore: black ([`fa3b28c`](https://github.com/agritheory/electronic_payments/commit/fa3b28cb4ae84e2016299ced6fe8043231fc5f73))

* chore: fix install on version-14 ([`9a3ed1d`](https://github.com/agritheory/electronic_payments/commit/9a3ed1d985ace6dba973a4fd6570ca28c65875fa))

* chore: fix install on version-14 ([`7264926`](https://github.com/agritheory/electronic_payments/commit/7264926a8a74f41b3373157e68ac2cd5324d273d))

### Ci

* ci: fix job requirement ([`25f4d3a`](https://github.com/agritheory/electronic_payments/commit/25f4d3aa3b09ab836be902114dc52f30891d3e85))

### Feature

* feat: better styles in customer portal (#24) ([`ed52c12`](https://github.com/agritheory/electronic_payments/commit/ed52c12872a07b649a22f6eac886977d3528bce1))

* feat: multiple payment methods (#17)

* feat: multiple payment methods

wip: integration with Electronic Payment Profile, Payment Gateway and credit limit

* chore: prettier, black, validate customizations

* fix: remove doubly-defined function

* ci: install missing dateutil types

* fix: accommodate if local file path includes app name

* docs: update example data path

* feat: update custom fields for customer ID and PPM table

* test: move, add credit limit, update settings

* fix: remove non-rendering doc.title

* fix: include bypass config in JE credit_limit_check

* feat: pass portal payment method data through dialog

* feat: add multiple payment methods, fees, credit check

* fix: remove extraneous new_doc call

* feat: init file

* test: ignore payment method setup

* fix: delete method order of operations

* feat: add config to create PPM when EPP is saved

* refactor: use enqueue to process payment

* fix: permission error by running in queue as admin

* refactor: move fee calc to PPM, hide options as needed

* test: use Authorize keys if present

* chore: update to handle test data

---------

Co-authored-by: Heather Kusmierz &lt;heather.kusmierz@gmail.com&gt; ([`c383888`](https://github.com/agritheory/electronic_payments/commit/c383888774134e1c712bcc7ff7c97b899340fc15))

### Style

* style: prettify code ([`650c55f`](https://github.com/agritheory/electronic_payments/commit/650c55ff5436e13d60205159eedcf16f3de76bd0))

* style: prettify code ([`8b27675`](https://github.com/agritheory/electronic_payments/commit/8b276756941d015f0d7d8e2a61b7ae45cbe6b911))

### Unknown

* [v14] Stripe (#16)

* chore: update for field changes

* wip: add stripe api code

* wip: fix circular import issue

* wip: add void and refund functions, load keys from settings, fix circular import

* wip: add currency to calls

* wip: stripe card workflow with UI

* wip: update error log calls for v14 changes

* wip: authorize.net request fixes following testing

* wip: convert types for all response objects

* tests: add so + si creation to test data, also eps if env exists

* docs: add pre-commit instructions to readme

* chore: remove future imports, no longer needed

* chore: remove orphaned code

* chore: fix flake 8 errors

* chore: fix flake8 errors

* chore: prettier

* wip: clearing process

* wip: update test data for new accounts

* wip: update workflow for PE or JE with clearing account

* fix: error handling

* feat: do not show electronic payment on dirty/new documents

* fix: create_journal_entry

* fix: take all last name

* fix: remove print statements, add todo mark

* fix: validate customizations

---------

Co-authored-by: Heather Kusmierz &lt;heather.kusmierz@gmail.com&gt;
Co-authored-by: Tyler Matteson &lt;tyler@agritheory.com&gt; ([`12e1907`](https://github.com/agritheory/electronic_payments/commit/12e19076b5bc55d9eeccc172e83724a39e6e6418))


## v0.1.1 (2023-11-02)


## v14.1.1 (2023-11-02)

### Fix

* fix: add requirements to pyproject.toml ([`65e8224`](https://github.com/agritheory/electronic_payments/commit/65e82243c7520e90a5cb04ad672681625bb60b48))


## v0.1.0 (2023-11-02)


## v14.1.0 (2023-11-02)

### Ci

* ci: fix release version path ([`97ef993`](https://github.com/agritheory/electronic_payments/commit/97ef9931eaf7fcd981dea7a751731ea829be8b26))

### Feature

* feat: add customer addresses ([`f720275`](https://github.com/agritheory/electronic_payments/commit/f720275bbf2221ba00b1e558af4de009d6f7da95))

* feat: add customers and sale items to test data ([`251e7ca`](https://github.com/agritheory/electronic_payments/commit/251e7ca734833f5ae1597be1e1ab2c7803f507a3))

* feat: add customization loader to hooks ([`39444e3`](https://github.com/agritheory/electronic_payments/commit/39444e360bbf9d0dd191094ea40152b3c3522572))

* feat: add MOP customizations and test data ([`bfbc373`](https://github.com/agritheory/electronic_payments/commit/bfbc373247173150682373fc0234ea26d12609bb))

* feat: add fix for Authorize.net app to install properly ([`28b44e6`](https://github.com/agritheory/electronic_payments/commit/28b44e69e6188482c7c31339985327c0aa563a85))

* feat: add custom button to sales docs for electronic payments ([`5cea25e`](https://github.com/agritheory/electronic_payments/commit/5cea25ec85128ff0e048df6f3fccbd98b1f4cf0e))

* feat: add JS functionality and authorize.net doctypes ([`1bebe85`](https://github.com/agritheory/electronic_payments/commit/1bebe85bb2ffc8e17433369ff90e2bc9a6ae2a00))

* feat: add installation info and docs pages ([`2943f4b`](https://github.com/agritheory/electronic_payments/commit/2943f4b45ce196a2934ee09ac13a87ef24a3d468))

* feat: Initialize App ([`21dcdb0`](https://github.com/agritheory/electronic_payments/commit/21dcdb078c3c48cb46e6bd5f23a807e13f1bb09d))

### Fix

* fix: update account names ([`8e4f061`](https://github.com/agritheory/electronic_payments/commit/8e4f06139beba300a8143e68747d2a569ef61baa))

### Test

* test: use updated check run test data ([`c7890bc`](https://github.com/agritheory/electronic_payments/commit/c7890bc61db96d517c8f881bed540531c5920ada))

### Unknown

* wip: version-14 setup ([`b299e97`](https://github.com/agritheory/electronic_payments/commit/b299e97dc61cbeb9fa95c6d67e9bdbfbb300cc63))

* Merge pull request #8 from agritheory/ex_data_acct_fix

fix: update account names ([`ae49f16`](https://github.com/agritheory/electronic_payments/commit/ae49f16f7b08734ca0e601cacafe8211f3a8a40b))

* wip: refactor settings, organize code ([`9a5e0ff`](https://github.com/agritheory/electronic_payments/commit/9a5e0ff508cc65fc128c0cc46f634ba863f5e711))

* wip: refactor to generic Controller, add custom fields ([`97a80ee`](https://github.com/agritheory/electronic_payments/commit/97a80eeeb407a63f57139f7dc7618941e958428e))

* Merge pull request #5 from agritheory/update_test_data

test: use updated check run test data ([`5e1f8b5`](https://github.com/agritheory/electronic_payments/commit/5e1f8b5b60eec6f7dcc0b9d37e55ac2ec0a98fc3))

* Merge pull request #6 from agritheory/test_data

feat: add customers, addresses, and items to test data ([`c073f98`](https://github.com/agritheory/electronic_payments/commit/c073f9815173ea3c31b849018d7d4b12705c9a78))

* Merge branch &#39;update_test_data&#39; into test_data ([`3635787`](https://github.com/agritheory/electronic_payments/commit/36357875485ee08878112a0edb67825335b45b95))

* Merge pull request #4 from agritheory/mop_customizations

MOP customizations ([`fda38f1`](https://github.com/agritheory/electronic_payments/commit/fda38f1649564beaeb06b6d2412f7a5564985b12))
