// Copyright (c) 2019, Youssef Restom and contributors
// For license information, please see license.txt
// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt


frappe.notification = {
	setup_fieldname_select: function(frm) {
		// get the doctype to update fields
		if(!frm.doc.document_type) {
			return;
		}

		frappe.model.with_doctype(frm.doc.document_type, function() {
			let get_select_options = function(df) {
				return {value: df.fieldname, label: df.fieldname + " (" + __(df.label) + ")"};
			}

			let get_date_change_options = function() {
				let date_options = $.map(fields, function(d) {
					return (d.fieldtype=="Date" || d.fieldtype=="Datetime")?
						get_select_options(d) : null;
				});
				// append creation and modified date to Date Change field
				return date_options.concat([
					{ value: "creation", label: `creation (${__('Created On')})` },
					{ value: "modified", label: `modified (${__('Last Modified Date')})` }
				]);
			}

			let fields = frappe.get_doc("DocType", frm.doc.document_type).fields;
			let options = $.map(fields,
				function(d) { return in_list(frappe.model.no_value_type, d.fieldtype) ?
					null : get_select_options(d); });

			// set value changed options
			frm.set_df_property("value_changed", "options", [""].concat(options));
			frm.set_df_property("set_property_after_alert", "options", [""].concat(options));

			// set date changed options
			frm.set_df_property("date_changed", "options", get_date_change_options());

		});
	}
}

function update_telegram_user_required(frm) {
	var needs_static = !frm.doc.dynamic_recipients && !frm.doc.dynamic_recipients_from_child;
	frm.toggle_reqd("telegram_user", needs_static ? 1 : 0);
}

function update_child_table_field_options(frm) {
	if (!frm.doc.document_type || !frm.doc.dynamic_recipients_from_child) return;
	frappe.call({
		method: "erpnext_telegram_integration.erpnext_telegram_integration.doctype.telegram_notification.telegram_notification.get_valid_child_table_fieldnames",
		args: { document_type: frm.doc.document_type },
		callback: function(r) {
			if (r.message && r.message.length) {
				var opts = [""].concat(r.message);
				if (frm.fields_dict.recipient_child_tables && frm.fields_dict.recipient_child_tables.grid) {
					frm.fields_dict.recipient_child_tables.grid.update_docfield_property("child_table_fieldname", "options", opts.join("\n"));
				}
			}
		}
	});
}

frappe.ui.form.on('Telegram Notification', {
	onload: function(frm) {
		frm.set_query("document_type", function() {
			return {
				"filters": {
					"istable": 0
				}
			}
		});
		frm.set_query("print_format", function() {
			return { "filters": { "doc_type": frm.doc.document_type } };
		});
		frm.set_query("recipient_doctype", "recipient_doctypes", function() {
			if (!frm.doc.document_type) return { "filters": [["name", "in", []]] };
			return {
				query: "erpnext_telegram_integration.erpnext_telegram_integration.doctype.telegram_notification.telegram_notification.get_recipient_doctype_query",
				filters: { document_type: frm.doc.document_type, from_child: 0 }
			};
		});
		frm.set_query("recipient_doctype", "recipient_doctypes_from_child", function() {
			if (!frm.doc.document_type) return { "filters": [["name", "in", []]] };
			return {
				query: "erpnext_telegram_integration.erpnext_telegram_integration.doctype.telegram_notification.telegram_notification.get_recipient_doctype_query",
				filters: { document_type: frm.doc.document_type, from_child: 1 }
			};
		});
		update_telegram_user_required(frm);
	},
	refresh: function(frm) {
		frappe.notification.setup_fieldname_select(frm);
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);
		frm.trigger('event');
		update_telegram_user_required(frm);
		update_child_table_field_options(frm);

		if (frm.doc.document_type && frm.doc.channel === 'Telegram') {
			if (frm.doc.dynamic_recipients) {
				frm.add_custom_button(__('Fetch Recipient DocTypes'), function() {
					frappe.call({
						method: 'erpnext_telegram_integration.erpnext_telegram_integration.doctype.telegram_notification.telegram_notification.get_recipient_options',
						args: { document_type: frm.doc.document_type },
						callback: function(r) {
							if (r.message && r.message.recipient_doctypes && r.message.recipient_doctypes.length) {
								frm.clear_table("recipient_doctypes");
								r.message.recipient_doctypes.forEach(function(d) {
									var row = frm.add_child("recipient_doctypes");
									row.recipient_doctype = d.doctype;
								});
								frm.refresh_field("recipient_doctypes");
								frappe.show_alert({ message: __('Fetched {0} DocTypes', [r.message.recipient_doctypes.length]), indicator: 'green' });
							} else {
								frappe.msgprint(__('No Link fields found in Document Type'));
							}
						}
					});
				});
			}
			if (frm.doc.dynamic_recipients_from_child) {
				frm.add_custom_button(__('Fetch Child Tables'), function() {
					frappe.call({
						method: 'erpnext_telegram_integration.erpnext_telegram_integration.doctype.telegram_notification.telegram_notification.get_recipient_options',
						args: { document_type: frm.doc.document_type },
						callback: function(r) {
							if (r.message && r.message.child_table_fieldnames && r.message.child_table_fieldnames.length) {
								frm.clear_table("recipient_child_tables");
								r.message.child_table_fieldnames.forEach(function(d) {
									var row = frm.add_child("recipient_child_tables");
									row.child_table_fieldname = d.fieldname;
								});
								frm.refresh_field("recipient_child_tables");
								frappe.show_alert({ message: __('Fetched {0} child tables', [r.message.child_table_fieldnames.length]), indicator: 'green' });
							} else {
								frappe.msgprint(__('No child tables found in Document Type'));
							}
						}
					});
				});
				frm.add_custom_button(__('Fetch Recipient DocTypes (Child)'), function() {
					frappe.call({
						method: 'erpnext_telegram_integration.erpnext_telegram_integration.doctype.telegram_notification.telegram_notification.get_recipient_options',
						args: { document_type: frm.doc.document_type },
						callback: function(r) {
							if (r.message && r.message.recipient_doctypes && r.message.recipient_doctypes.length) {
								frm.clear_table("recipient_doctypes_from_child");
								r.message.recipient_doctypes.forEach(function(d) {
									var row = frm.add_child("recipient_doctypes_from_child");
									row.recipient_doctype = d.doctype;
								});
								frm.refresh_field("recipient_doctypes_from_child");
								frappe.show_alert({ message: __('Fetched {0} DocTypes', [r.message.recipient_doctypes.length]), indicator: 'green' });
							} else {
								frappe.msgprint(__('No Link fields found in Document Type or child tables'));
							}
						}
					});
				});
			}
		}
	},

	document_type: function(frm) {
		frappe.notification.setup_fieldname_select(frm);
		update_child_table_field_options(frm);
	},
	view_properties: function(frm) {
		frappe.route_options = {doc_type:frm.doc.document_type};
		frappe.set_route("Form", "Customize Form");
	},
	event: function(frm) {
		if(in_list(['Days Before', 'Days After'], frm.doc.event)) {
			frm.add_custom_button(__('Get Alerts for Today'), function() {
				frappe.call({
					method: 'erpnext_telegram_integration.erpnext_telegram_integration.doctype.telegram_notification.telegram_notification.get_documents_for_today',
					args: {
						notification: frm.doc.name
					},
					callback: function(r) {
						if(r.message) {
							frappe.msgprint(r.message);
						} else {
							frappe.msgprint(__('No alerts for today'));
						}
					}
				});
			});
		}
	},
	dynamic_recipients: function(frm) {
		update_telegram_user_required(frm);
	},
	dynamic_recipients_from_child: function(frm) {
		update_telegram_user_required(frm);
		update_child_table_field_options(frm);
	}
	
});
