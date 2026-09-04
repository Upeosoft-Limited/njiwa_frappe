/**
 * The desk side of Njiwa Settings.
 *
 * Two buttons that ask Njiwa a question, and a headline that says what the
 * saved settings will do. Nothing here calls Njiwa on its own: opening this
 * page must not depend on Njiwa being up, so the live-or-test answer waits
 * until somebody presses Test connection.
 *
 * The headline says what state the settings are in, and nothing else. What
 * the app is for, and that nothing here decides when a message goes out, is
 * said once by the doctype itself at the top of the form.
 *
 * Everything is inside one function because a bench is shared. Nothing in
 * here becomes a name another app could collide with.
 */

(() => {
	// The one place the brand colour appears on this form. The desk belongs to
	// the site, not to us.
	const TEAL = '#0fa3a0';

	frappe.ui.form.on('Njiwa Settings', {
		onload(frm) {
			// What Njiwa said about the saved key. Nothing is known about a key
			// until Test connection has asked.
			frm.njiwa_key_is = null;
		},

		refresh(frm) {
			// Test connection comes first because it is the one that costs
			// nothing: it proves the key, and the test message then proves the
			// rest of the way. Neither is btn-primary. Save is the blue button
			// on this form, and a second blue button beside it would argue with
			// it over which one you came here to press.
			frm.add_custom_button(__('Test connection'), () => test_connection(frm));
			frm.add_custom_button(__('Send test message'), () => open_test_message_dialog(frm));
			show_state(frm);
		},

		after_save(frm) {
			// The key on file may be a different key now, so what Njiwa said
			// about the last one no longer describes what is stored.
			frm.njiwa_key_is = null;
		},

		enabled(frm) {
			show_state(frm);
		},
	});

	/**
	 * Both buttons read what is saved, not what is on screen. Testing an
	 * unsaved key would tell you about a key nothing else will use.
	 */
	function saved_first(frm) {
		if (!frm.is_dirty()) {
			return true;
		}
		frappe.msgprint({
			title: __('Save first'),
			message: __('The test uses the saved settings. Save your changes, then test.'),
			indicator: 'orange',
		});
		return false;
	}

	function test_connection(frm) {
		if (!saved_first(frm)) {
			return;
		}

		frappe.call({
			method: 'njiwa_frappe.api.test_connection',
			freeze: true,
			freeze_message: __('Asking Njiwa...'),
			callback(response) {
				if (!response.message) {
					return;
				}
				// The numbers have already been shown by the call itself. All
				// that is kept here is whether the saved key sends for real, so
				// the headline can say so without asking a second time.
				frm.njiwa_key_is = response.message.live ? 'live' : 'test';
				show_state(frm);
			},
		});
	}

	/** The headline: on or off, and whatever is known about the saved key. */
	function show_state(frm) {
		const on = Boolean(frm.doc.enabled);
		const lines = [];

		if (on) {
			lines.push(`<b>${__('Njiwa is on.')}</b>`);
			lines.push(key_line(frm));
		} else {
			lines.push(`<b>${__('Njiwa is off.')}</b> ` + __('Nothing will send.'));
		}

		if (frm.is_dirty()) {
			lines.push(
				__('That is the form as it stands. It is true of the saved settings once you save.')
			);
		}

		// Two shapes as well as two colours, and the words say it either way.
		// The colour is the block's own text colour, whatever the theme has
		// made that: a colour picked to read against the light green block
		// disappears into the dark one, and the dot is meant to be a second
		// way of reading the state rather than a decoration.
		const dot = on
			? 'background: currentColor;'
			: 'background: transparent; box-shadow: inset 0 0 0 3px currentColor;';

		// A headline is appended, not replaced, so the one this drew last time
		// has to go or they stack up. Only ours is taken out: another message on
		// this form belongs to whoever put it there.
		if (frm.layout && frm.layout.message) {
			frm.layout.message.find('.njiwa-state').closest('.form-message').remove();
		}

		frm.dashboard.set_headline(
			`<div class="njiwa-state" role="status" style="display: flex; gap: 10px; align-items: flex-start;">
				<span aria-hidden="true" style="flex: 0 0 auto; width: 10px; height: 10px; margin-top: 5px; border-radius: 50%; ${dot}"></span>
				<div>${lines.join('<br>')}</div>
			</div>`,
			on ? 'green' : 'red'
		);
	}

	function key_line(frm) {
		if (frm.njiwa_key_is === 'live') {
			return __('Test connection says the saved key is a live key, so messages reach real phones.');
		}
		if (frm.njiwa_key_is === 'test') {
			return __(
				'Test connection says the saved key is a test key: every message is checked and stored, and nothing reaches WhatsApp.'
			);
		}
		return __(
			'Whether the saved key is live or test is what Test connection answers, and it has not been asked yet.'
		);
	}

	function open_test_message_dialog(frm) {
		// The send uses the saved key, exactly as Test connection does.
		if (!saved_first(frm)) {
			return;
		}

		const dialog = new frappe.ui.Dialog({
			title: __('Send a test message'),
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'preamble',
					options: preamble(frm),
				},
				{
					fieldtype: 'Data',
					fieldname: 'to',
					label: __('Send to'),
					reqd: 1,
					description: __('Full international form, digits only, like 254712345678.'),
				},
				{ fieldtype: 'HTML', fieldname: 'outcome' },
			],
			primary_action_label: __('Send'),
			primary_action: (values) => send_test_message(dialog, values),
		});

		dialog.show();
	}

	/**
	 * What is said above the number field. The last block is what pressing Send
	 * will actually do, and it sits against the field rather than in the small
	 * grey type at the top, because it is the part that costs money.
	 *
	 * The form is saved by the time this runs, so frm.doc and frm.njiwa_key_is
	 * both describe the settings the send will use.
	 */
	function preamble(frm) {
		const blocks = [
			`<p class="text-muted">${__(
				'This sends one short fixed message so you can watch a real send finish. You cannot choose the words, and it carries no idempotency key: pressing Send twice sends twice.'
			)}</p>`,
		];

		if (!frm.doc.enabled) {
			// Nothing leaves the site while it is switched off, so what the key
			// would have done is beside the point, and saying it here would
			// contradict the line above it.
			blocks.push(
				note(
					'orange',
					`<b>${__('Njiwa is switched off, so this send will be refused.')}</b> ` +
						__('That refusal is the off switch working.')
				)
			);
			return blocks.join('');
		}

		if (frm.njiwa_key_is === 'live') {
			blocks.push(
				note(
					'red',
					`<b>${__('The saved key is a live key, so this is a real message.')}</b> ` +
						__(
							'It reaches a WhatsApp handset, the person holding that phone will read it, and it costs whatever a message costs. Send it to your own number.'
						)
				)
			);
		} else if (frm.njiwa_key_is === 'test') {
			blocks.push(
				note(
					'teal',
					`<b>${__('The saved key is a test key.')}</b> ` +
						__(
							'The message is checked and stored, nothing reaches WhatsApp, and it costs nothing.'
						)
				)
			);
		} else {
			blocks.push(
				note(
					'orange',
					`<b>${__('Which key is saved has not been asked yet.')}</b> ` +
						__(
							'Test connection is what answers that. If the saved key starts sk_live_ this is a real message: it reaches a WhatsApp handset, the person holding that phone will read it, and it costs whatever a message costs. Send it to your own number.'
						)
				)
			);
		}

		return blocks.join('');
	}

	function send_test_message(dialog, values) {
		const $outcome = dialog.get_field('outcome').$wrapper;
		$outcome.empty();

		// The dialog will not call this with the field empty; it says so itself.
		// What is left to catch is a field holding nothing but spaces.
		const to = (values.to || '').trim();
		if (!to) {
			$outcome.html(note('orange', __('Type the number to send to first.')));
			return;
		}

		// The desk freezes, the button goes dead, and this flag catches anything
		// that gets past both. The send carries no idempotency key, so a second
		// click really would be a second message.
		if (dialog.njiwa_sending) {
			return;
		}
		dialog.njiwa_sending = true;

		const button = dialog.get_primary_btn();
		button.prop('disabled', true);

		frappe.call({
			method: 'njiwa_frappe.api.send_test_message',
			args: { to },
			freeze: true,
			freeze_message: __('Sending, and waiting for the outcome...'),
			callback(response) {
				render_outcome($outcome, response.message);
			},
			error(refusal) {
				render_refusal($outcome, refusal);
			},
			always() {
				dialog.njiwa_sending = false;
				button.prop('disabled', false);
			},
		});
	}

	/** Njiwa's answer to the send. Every value in it came off the network. */
	function render_outcome($wrapper, answer) {
		if (!answer) {
			$wrapper.html(note('grey', __('Njiwa answered, but said nothing about the message.')));
			return;
		}

		const status = String(pick(answer, 'status') || '').toLowerCase();
		const sandbox = Boolean(pick(answer, 'sandbox'));
		const rows = [
			[__('Message id'), value(pick(answer, 'id', 'message_id'))],
			[
				__('Status'),
				status
					? `<span class="indicator ${status_colour(status)}">${text(status)}</span>`
					: value(null),
			],
			[__('Sent to'), value(pick(answer, 'to', 'to_msisdn'))],
			[__('Sent from'), value(pick(answer, 'from', 'from_msisdn', 'from_number'))],
		];

		const notes = [];
		// A test key answers "sent" without anything having been sent, so this
		// goes first and the line about the status being a real outcome is left
		// out: on a test key it would not be true.
		if (sandbox) {
			notes.push(
				note(
					'orange',
					__(
						'The saved key is a test key, so the message was stored and nothing reached WhatsApp. Swap in a key starting sk_live_ to send for real.'
					)
				)
			);
		}
		if (!sandbox && ['sent', 'delivered', 'read'].includes(status)) {
			notes.push(
				note(
					'teal',
					__(
						'That status is the delivery outcome, not a receipt for a queued message: this test waits for Njiwa to finish before it answers.'
					)
				)
			);
		}
		if (status === 'failed') {
			notes.push(
				note(
					'red',
					[__('Njiwa took the message and then could not send it.'), reason(answer)]
						.filter(Boolean)
						.join(' ')
				)
			);
		}
		// api.send_test_message calls the flag timed_out. The older name is kept
		// beside it so an answer written either way is read.
		if (status === 'queued' || pick(answer, 'timed_out', 'wait_timed_out')) {
			notes.push(
				note(
					'orange',
					__(
						'This one is still queued: Njiwa did not finish within the wait. It will most likely still go out, and the message id above is how you look it up.'
					)
				)
			);
		}

		const body = rows
			.map(([label, cell]) => `<tr><td style="width: 38%;">${label}</td><td>${cell}</td></tr>`)
			.join('');
		$wrapper.html(
			`<table class="table table-bordered" style="margin-bottom: 0;"><tbody>${body}</tbody></table>${notes.join(
				''
			)}`
		);
	}

	function render_refusal($wrapper, refusal) {
		// The backend raises NjiwaError, and it reaches the browser with Njiwa's
		// own wording, the stable code to branch on, and the page explaining that
		// code. Frappe shows the wording in a dialog of its own; all three are
		// repeated here so they are still on screen once that dialog has been
		// dismissed.
		const failure = refusal_details(refusal);
		const lines = [
			`<b>${__('Nothing was sent.')}</b> ` +
				(failure.message
					? text(failure.message)
					: __('Njiwa gave no reason. The error log on this site will have the rest.')),
		];

		// The wording sometimes carries the code or the address itself. Adding
		// a line that says the same thing again helps nobody.
		if (failure.code && !says(failure.message, failure.code)) {
			lines.push(`${__('Code')}: <code>${text(failure.code)}</code>`);
		}
		if (failure.docs && !says(failure.message, failure.docs)) {
			lines.push(
				`<a href="${text(failure.docs)}" target="_blank" rel="noopener noreferrer">${__(
					'What this code means'
				)}</a>`
			);
		}

		$wrapper.html(note('red', lines.join('<br>')));
	}

	/**
	 * What the refusal is carrying. Frappe puts the wording in _server_messages
	 * and hands anything else the method added back beside it, so read the code
	 * and the docs address wherever they sit rather than from one fixed key.
	 */
	function refusal_details(refusal) {
		const payload = parsed(refusal);
		const holders = [payload.njiwa_error, payload.njiwa, payload.error, payload];
		const said = server_message(payload) || first(holders, ['message']);
		return {
			message: said ? plain(said) : null,
			code: first(holders, ['njiwa_code', 'code']),
			// A docs page named on its own is the one to link. Failing that,
			// the address written into the wording is the same page.
			docs: web_link(first(holders, ['njiwa_docs', 'docs', 'docs_url']) || address_in(said)),
		};
	}

	// A thrown error arrives here as the parsed response; anything Frappe could
	// not parse arrives as the request itself, or as nothing at all.
	function parsed(refusal) {
		try {
			if (refusal && refusal.responseText) {
				return JSON.parse(refusal.responseText) || {};
			}
		} catch {
			// Not JSON at all. Whatever was handed over is all there is.
		}
		return refusal && typeof refusal === 'object' ? refusal : {};
	}

	function server_message(payload) {
		try {
			const messages = JSON.parse(payload._server_messages || '[]')
				.map((entry) => (typeof entry === 'string' ? JSON.parse(entry) : entry))
				.map((entry) => entry && entry.message)
				.filter(Boolean);
			if (messages.length) {
				return messages.join(' ');
			}
		} catch {
			// Not a server message, or not JSON at all. The line that stands in
			// for it says as much.
		}
		return null;
	}

	function reason(answer) {
		const failure = pick(answer, 'error');
		if (!failure) {
			return '';
		}
		const said = typeof failure === 'object' ? failure.message || failure.code : failure;
		return said ? text(said) : '';
	}

	/**
	 * api.send_test_message hands back Njiwa's own answer to the send. Read each
	 * field wherever it sits, so a wrapper around that answer is not the
	 * difference between the operator seeing the outcome and seeing nothing.
	 */
	function pick(answer, ...names) {
		return first([answer, answer.result, answer.message, answer.data], names);
	}

	/** The first of these names that any of these holders has a value for. */
	function first(holders, names) {
		for (const holder of holders) {
			if (!holder || typeof holder !== 'object') {
				continue;
			}
			for (const name of names) {
				const found = holder[name];
				if (found !== undefined && found !== null && found !== '') {
					return found;
				}
			}
		}
		return null;
	}

	function status_colour(status) {
		if (['sent', 'delivered', 'read'].includes(status)) {
			return 'green';
		}
		if (status === 'failed') {
			return 'red';
		}
		if (['queued', 'pending', 'sending'].includes(status)) {
			return 'orange';
		}
		return 'grey';
	}

	/** A line under the table. The colour repeats what the words already say. */
	function note(colour, body) {
		const edges = {
			teal: TEAL,
			red: 'var(--red-500, #e24c4c)',
			orange: 'var(--orange-500, #e5a03d)',
			grey: 'var(--gray-400, #b8b8b8)',
		};
		return `<div style="margin-top: 12px; padding: 2px 0 2px 12px; border-left: 3px solid ${
			edges[colour] || edges.grey
		};">${body}</div>`;
	}

	function value(raw) {
		if (raw === null || raw === undefined || raw === '') {
			return `<span class="text-muted">${__('not given')}</span>`;
		}
		return `<code>${text(raw)}</code>`;
	}

	function text(raw) {
		return frappe.utils.escape_html(String(raw));
	}

	/**
	 * A message written for a dialog may carry a little HTML. Everything shown
	 * here is escaped, so the tags would arrive on screen as tags. Take them off
	 * and keep the sentence.
	 */
	function plain(raw) {
		return String(raw)
			.replace(/<[^>]*>/g, ' ')
			.replace(/\s+/g, ' ')
			.trim();
	}

	/** Only an ordinary web address becomes a link, whatever arrived. */
	function web_link(raw) {
		const address = String(raw || '').trim();
		return /^https?:\/\//i.test(address) ? address : null;
	}

	function address_in(raw) {
		const found = String(raw || '').match(/https?:\/\/[^\s"'<>)]+/i);
		return found ? found[0] : null;
	}

	function says(body, part) {
		return Boolean(body) && String(body).includes(String(part));
	}
})();
