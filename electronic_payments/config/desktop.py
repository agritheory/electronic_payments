# Copyright (c) 2026, AgriTheory and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	return [
		{
			"module_name": "Electronic Payments",
			"color": "grey",
			"icon": "octicon octicon-file-directory",
			"type": "module",
			"label": _("Electronic Payments"),
		}
	]
