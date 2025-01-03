# CHANGELOG


## v15.0.1 (2025-01-03)

### Bug Fixes

- Customizations load error
  ([`c76ab1e`](https://github.com/agritheory/electronic_payments/commit/c76ab1ed371ff25e91b4795628bdf7d47384c936))

### Chores

- Add yarn lock
  ([`fa72b89`](https://github.com/agritheory/electronic_payments/commit/fa72b8976dbd79002c7f0dc37472a3be9827fccb))

- Update installation instructions for version-15
  ([`55e7807`](https://github.com/agritheory/electronic_payments/commit/55e78075e9412078f277381fc861b39a4332ed72))

### Continuous Integration

- Conform release versions
  ([`933429c`](https://github.com/agritheory/electronic_payments/commit/933429c16a7fd1e1c6ddd8ab7320f9c4aeb13ecd))

- Update site_config
  ([`51b7a82`](https://github.com/agritheory/electronic_payments/commit/51b7a828b334734c68298238f26a509309f16638))

- Update versions, webshop to apps.txt
  ([`211c155`](https://github.com/agritheory/electronic_payments/commit/211c155d344b685ab31cc3c9dca5259ade01d243))

### Testing

- Fix rounding sequence
  ([`3c5267a`](https://github.com/agritheory/electronic_payments/commit/3c5267a19bbe564c601623719a4a1abc4c8da0f0))

- Update for v-14 float comparison issues
  ([`4d1c4ca`](https://github.com/agritheory/electronic_payments/commit/4d1c4cad0bcd3510bcba898748940582ece02f80))


## v14.4.0 (2024-05-20)

### Continuous Integration

- Update for version-15 and tests
  ([`bce8b1f`](https://github.com/agritheory/electronic_payments/commit/bce8b1ffb8d5085683753a123720bf2b102aba53))

### Features

- Update for max length limitation
  ([`c2e1998`](https://github.com/agritheory/electronic_payments/commit/c2e19986b2c4e4f30f06a30ebcd64daa9a584340))

- Update for version-15 and test issues
  ([`b28acc1`](https://github.com/agritheory/electronic_payments/commit/b28acc11462de9a7bcaadaa8e5caf6ede4536fb3))

- Update install for version-15
  ([`0761362`](https://github.com/agritheory/electronic_payments/commit/076136200936fef7b5c206f4caec1b5f6a293b4c))

- Update order pages for version-15
  ([`2e974f3`](https://github.com/agritheory/electronic_payments/commit/2e974f3d9a63955f3ff92ff1251b9aa8bb9d5bbf))

### Testing

- Add sending payment tests
  ([`339d259`](https://github.com/agritheory/electronic_payments/commit/339d259649c10ce04148813f7bed922ee8124ab4))

- Add test suite for common processing functions
  ([`75b9cf9`](https://github.com/agritheory/electronic_payments/commit/75b9cf9296cf680707486d4123a3660ca74eb2e4))


## v14.3.1 (2024-05-14)

### Bug Fixes

- Sets field even when no default method
  ([#33](https://github.com/agritheory/electronic_payments/pull/33),
  [`08b387b`](https://github.com/agritheory/electronic_payments/commit/08b387b1d1c9f5eef4bf7aecf61ced6857a49add))


## v14.3.0 (2024-03-29)

### Continuous Integration

- Add more linters to CI ([#25](https://github.com/agritheory/electronic_payments/pull/25),
  [`ae9f018`](https://github.com/agritheory/electronic_payments/commit/ae9f0186cb43ef14f70a2008610792d5dfdfba1f))

* ci: add more linters to CI

* ci: install mypy types

* chore: black

* ci: add --non-interactive flag


## v0.2.0 (2024-02-27)

### Chores

- Black
  ([`fa3b28c`](https://github.com/agritheory/electronic_payments/commit/fa3b28cb4ae84e2016299ced6fe8043231fc5f73))

- Fix install on version-14
  ([`9a3ed1d`](https://github.com/agritheory/electronic_payments/commit/9a3ed1d985ace6dba973a4fd6570ca28c65875fa))

- Fix install on version-14
  ([`7264926`](https://github.com/agritheory/electronic_payments/commit/7264926a8a74f41b3373157e68ac2cd5324d273d))

- Fix mypy instructions in readme
  ([`9d9e300`](https://github.com/agritheory/electronic_payments/commit/9d9e3001c973df9e1aaec1f46bd7eaefad52f6dd))

- Migrate to esbuild bundler
  ([`4e19e8a`](https://github.com/agritheory/electronic_payments/commit/4e19e8ac06981de4437635c637b47d5c396f1d40))

- Prettier
  ([`e0c7b67`](https://github.com/agritheory/electronic_payments/commit/e0c7b67716bd2369c621e3b4ed12f368b0a74d8b))

- Setup mypy dependency and instruction
  ([`6628edf`](https://github.com/agritheory/electronic_payments/commit/6628edf77d64f462a13120bbe5020110e5abb83c))

### Code Style

- Prettify code
  ([`650c55f`](https://github.com/agritheory/electronic_payments/commit/650c55ff5436e13d60205159eedcf16f3de76bd0))

- Prettify code
  ([`8b27675`](https://github.com/agritheory/electronic_payments/commit/8b276756941d015f0d7d8e2a61b7ae45cbe6b911))

### Continuous Integration

- Fix job requirement
  ([`25f4d3a`](https://github.com/agritheory/electronic_payments/commit/25f4d3aa3b09ab836be902114dc52f30891d3e85))

### Features

- Better styles in customer portal
  ([#24](https://github.com/agritheory/electronic_payments/pull/24),
  [`ed52c12`](https://github.com/agritheory/electronic_payments/commit/ed52c12872a07b649a22f6eac886977d3528bce1))

- Multiple payment methods ([#17](https://github.com/agritheory/electronic_payments/pull/17),
  [`c383888`](https://github.com/agritheory/electronic_payments/commit/c383888774134e1c712bcc7ff7c97b899340fc15))

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

Co-authored-by: Heather Kusmierz <heather.kusmierz@gmail.com>


## v0.1.1 (2023-11-02)


## v14.1.1 (2023-11-02)

### Bug Fixes

- Add requirements to pyproject.toml
  ([`65e8224`](https://github.com/agritheory/electronic_payments/commit/65e82243c7520e90a5cb04ad672681625bb60b48))


## v0.1.0 (2023-11-02)


## v14.1.0 (2023-11-02)

### Bug Fixes

- Update account names
  ([`8e4f061`](https://github.com/agritheory/electronic_payments/commit/8e4f06139beba300a8143e68747d2a569ef61baa))

### Continuous Integration

- Fix release version path
  ([`97ef993`](https://github.com/agritheory/electronic_payments/commit/97ef9931eaf7fcd981dea7a751731ea829be8b26))

### Features

- Add custom button to sales docs for electronic payments
  ([`5cea25e`](https://github.com/agritheory/electronic_payments/commit/5cea25ec85128ff0e048df6f3fccbd98b1f4cf0e))

- Add customer addresses
  ([`f720275`](https://github.com/agritheory/electronic_payments/commit/f720275bbf2221ba00b1e558af4de009d6f7da95))

- Add customers and sale items to test data
  ([`251e7ca`](https://github.com/agritheory/electronic_payments/commit/251e7ca734833f5ae1597be1e1ab2c7803f507a3))

- Add customization loader to hooks
  ([`39444e3`](https://github.com/agritheory/electronic_payments/commit/39444e360bbf9d0dd191094ea40152b3c3522572))

- Add fix for Authorize.net app to install properly
  ([`28b44e6`](https://github.com/agritheory/electronic_payments/commit/28b44e69e6188482c7c31339985327c0aa563a85))

- Add installation info and docs pages
  ([`2943f4b`](https://github.com/agritheory/electronic_payments/commit/2943f4b45ce196a2934ee09ac13a87ef24a3d468))

- Add JS functionality and authorize.net doctypes
  ([`1bebe85`](https://github.com/agritheory/electronic_payments/commit/1bebe85bb2ffc8e17433369ff90e2bc9a6ae2a00))

- Add MOP customizations and test data
  ([`bfbc373`](https://github.com/agritheory/electronic_payments/commit/bfbc373247173150682373fc0234ea26d12609bb))

- Initialize App
  ([`21dcdb0`](https://github.com/agritheory/electronic_payments/commit/21dcdb078c3c48cb46e6bd5f23a807e13f1bb09d))

### Testing

- Use updated check run test data
  ([`c7890bc`](https://github.com/agritheory/electronic_payments/commit/c7890bc61db96d517c8f881bed540531c5920ada))
