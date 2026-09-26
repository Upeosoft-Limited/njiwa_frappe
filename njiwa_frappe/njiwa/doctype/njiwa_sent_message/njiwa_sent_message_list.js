// The list of messages this site asked Njiwa to send: coloured by how each one went.
const NJIWA_EVENTS = {
	order_placed: 'Order confirmed', order_cancelled: 'Order cancelled',
	invoice_issued: 'Invoice issued', invoice_cancelled: 'Invoice cancelled', credit_note: 'Credit note issued',
	payment_received: 'Payment received', payment_cancelled: 'Payment cancelled',
	delivery_sent: 'Goods on their way', delivery_cancelled: 'Delivery cancelled', new_order: 'New order alert',
};

(() => {
frappe.listview_settings['Njiwa Sent Message'] = {
	add_fields: ['status', 'failure_reason'],
	hide_name_column: true,
	formatters: {
		event: (value) => frappe.utils.escape_html(__(NJIWA_EVENTS[value] || value || '')),
	},
	get_indicator(doc) {
		const colours = { Sent: 'green', Failed: 'red', Queued: 'orange' };
		return [__(doc.status), colours[doc.status] || 'gray', `status,=,${doc.status}`];
	},
	onload(listview) {
		njiwa_width(listview.page.wrapper);
		listview.page.add_inner_button(__('Njiwa home'), () => frappe.set_route('njiwa'));
		listview.page.add_inner_button(__('Settings'), () => frappe.set_route('Form', 'Njiwa Settings'));
	},
};

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
