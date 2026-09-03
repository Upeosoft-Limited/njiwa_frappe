frappe.ui.form.on('Njiwa Settings', {
	refresh(frm) {
		frm.add_custom_button(__('Test connection'), () => {
			// The test reads the saved key, not what is on screen. Sending an
			// unsaved key would tell you about a key nothing else will use.
			if (frm.is_dirty()) {
				frappe.msgprint({
					title: __('Save first'),
					message: __('The test uses the saved settings. Save your changes, then test.'),
					indicator: 'orange',
				});
				return;
			}

			frappe.call({
				method: 'njiwa_frappe.api.test_connection',
				freeze: true,
				freeze_message: __('Asking Njiwa...'),
			});
		});
	},
});
