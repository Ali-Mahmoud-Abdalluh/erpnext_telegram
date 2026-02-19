// Copyright (c) 2019, Youssef Restom and contributors
// For license information, please see license.txt

frappe.ui.form.on('Telegram Settings', {
	refresh: function (frm) {
		if (!frappe.boot.versions.hrms) {
			frm.set_value('enable_interactive_bot', 0);
			frm.set_df_property('enable_interactive_bot', 'read_only', 1);
			frm.set_df_property('enable_interactive_bot', 'description',
				__("Requires <b>HRMS</b> app to be installed."));
		}
	}
});
