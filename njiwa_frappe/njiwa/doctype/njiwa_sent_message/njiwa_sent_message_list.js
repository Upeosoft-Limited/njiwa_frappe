// The list of messages this site asked Njiwa to send: coloured by how each one went.
const NJIWA_EVENTS = {
	order_placed: 'Order confirmed', order_cancelled: 'Order cancelled',
	invoice_issued: 'Invoice issued', invoice_cancelled: 'Invoice cancelled', credit_note: 'Credit note issued',
	payment_received: 'Payment received', payment_cancelled: 'Payment cancelled',
	delivery_sent: 'Goods on their way', delivery_cancelled: 'Delivery cancelled', new_order: 'New order alert',
};

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
		listview.page.add_inner_button(__('Njiwa home'), () => frappe.set_route('njiwa'));
		listview.page.add_inner_button(__('Settings'), () => frappe.set_route('Form', 'Njiwa Settings'));
	},
};
