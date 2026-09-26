// One message this site asked Njiwa to send. Read only: the header says how it went.
(() => {
frappe.ui.form.on('Njiwa Sent Message', {
	refresh(frm) {
		njiwa_width(frm.page.wrapper);
		const status = frm.doc.status;
		const colour = { Sent: 'green', Failed: 'red', Queued: 'orange' }[status] || 'blue';
		const lines = {
			Sent: __('Sent to {0}.', [frm.doc.to_number || __('the customer')]),
			Failed: __('Not sent. {0}', [frm.doc.failure_reason || __('Njiwa gave no reason.')]),
			Queued: __('Waiting for a background worker. If it stays here, the workers are not running.'),
		};
		frm.dashboard.clear_headline();
		frm.dashboard.set_headline(frappe.utils.escape_html(lines[status] || status || ''), colour);

		if (frm.doc.reference_doctype && frm.doc.reference_name) {
			frm.add_custom_button(__('Open {0}', [__(frm.doc.reference_doctype)]), () =>
				frappe.set_route('Form', frm.doc.reference_doctype, frm.doc.reference_name)
			);
		}
		frm.add_custom_button(__('Njiwa home'), () => frappe.set_route('njiwa'));
	},
});

	/**
	 * The same 850px column the Njiwa page (/desk/njiwa) has, so every Njiwa
	 * screen lines up. The side panel (assign, attachments) is hidden here: none
	 * of it means anything on these screens. Scoped to pages marked njiwa-page.
	 */
	function njiwa_width(wrapper) {
		$(wrapper).addClass('njiwa-page');
		if (document.getElementById('njiwa-width-style')) {
			return;
		}
		const style = document.createElement('style');
		style.id = 'njiwa-width-style';
		style.textContent = `
			.njiwa-page .layout-main { max-width: 850px; margin-left: auto; margin-right: auto; }
			.njiwa-page .layout-side-section { display: none !important; }
			.njiwa-page .layout-main-section-wrapper, .njiwa-page .layout-main-section { flex: 1 1 auto; max-width: 100%; width: 100%; }`;
		document.head.appendChild(style);
	}
})();
