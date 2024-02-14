from . import __version__ as app_version  # noqa: F401

app_name = "electronic_payments"
app_title = "Electronic Payments"
app_publisher = "AgriTheory"
app_description = "Electronic Payments Utilities for ERPNext"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "support@agritheory.dev"
app_license = "MIT"
required_apps = ["frappe/erpnext", "frappe/payments"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/electronic_payments/css/electronic_payments.css"
app_include_js = ["electronic_payments.bundle.js"]

# include js, css files in header of web template
# web_include_css = "/assets/electronic_payments/css/electronic_payments.css"
# web_include_js = ["web.bundle.js"]

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "electronic_payments/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Sales Order": "public/js/sales_order_custom.js",
	"Sales Invoice": "public/js/sales_invoice_custom.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "electronic_payments.install.before_install"
# after_install = "electronic_payments.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "electronic_payments.uninstall.before_uninstall"
# after_uninstall = "electronic_payments.uninstall.after_uninstall"

# Migration
# ------------

# before_migrate = "electronic_payments.uninstall.before_uninstall"
after_migrate = "electronic_payments.customize.load_customizations"


# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "electronic_payments.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Journal Entry": "electronic_payments.overrides.journal_entry.CustomElectronicPaymentsJournalEntry"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Journal Entry": {
		"on_submit": "electronic_payments.overrides.payment_schedule.update_payment_schedule_for_electronic_payment",
		"on_cancel": "electronic_payments.overrides.payment_schedule.update_payment_schedule_for_electronic_payment",
	},
	"Payment Entry": {
		"on_submit": "electronic_payments.overrides.payment_schedule.update_payment_schedule_for_electronic_payment",
		"on_cancel": "electronic_payments.overrides.payment_schedule.update_payment_schedule_for_electronic_payment",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"electronic_payments.tasks.all"
# 	],
# 	"daily": [
# 		"electronic_payments.tasks.daily"
# 	],
# 	"hourly": [
# 		"electronic_payments.tasks.hourly"
# 	],
# 	"weekly": [
# 		"electronic_payments.tasks.weekly"
# 	]
# 	"monthly": [
# 		"electronic_payments.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "electronic_payments.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"pay": "electronic_payments.www.payments.index.pay",
	"erpnext.accounts.doctype.payment_request.payment_request.make_payment_request": "electronic_payments.www.payments.payment_options",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "electronic_payments.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{"doctype": "{doctype_4}"},
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"electronic_payments.auth.validate"
# ]
