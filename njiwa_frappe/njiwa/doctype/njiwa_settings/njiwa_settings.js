/**
 * The desk side of Njiwa Settings.
 *
 * A header in the same look as the Njiwa page (/desk/njiwa): the Njiwa logo,
 * whether sending is on and whether the saved key is live or test, and the
 * buttons that ask Njiwa a question. The live-or-test answer is read from the
 * saved key's prefix through njiwa_frappe.home.summary, which never calls
 * Njiwa, so opening this page still does not depend on Njiwa being up.
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
			add_style();
			$(frm.wrapper).addClass('njiwa-form');
			njiwa_width(frm.page.wrapper);
			show_state(frm);
			// What the saved key is. Read from this site
			// only; nothing here reaches Njiwa.
			frappe
				.xcall('njiwa_frappe.home.summary')
				.then((summary) => {
					frm.njiwa_summary = summary;
					if (frm.njiwa_key_is === null && summary.key !== 'none') {
						frm.njiwa_key_is = summary.key;
					}
					show_state(frm);
				})
				.catch(() => {});
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

	/** The header: the Njiwa logo, on or off, live or test, and the buttons. */
	function show_state(frm) {
		const on = Boolean(frm.doc.enabled);
		const summary = frm.njiwa_summary || {};
		const saved_key = frm.njiwa_key_is || (summary.key && summary.key !== 'none' ? summary.key : null);
		let tone = 'none';
		let status = __('No key saved yet');
		if (!on) {
			tone = 'off';
			status = __('Sending is off');
		} else if (saved_key === 'live') {
			tone = 'live';
			status = __('Live · messages reach real phones');
		} else if (saved_key === 'test') {
			tone = 'test';
			status = __('Test key · nothing reaches a phone');
		}

		const dirty = frm.is_dirty()
			? `<p class="njiwa-hero-note">${__('You have unsaved changes. Save before testing.')}</p>`
			: '';
		const $hero = $(`
			<section class="njiwa-hero" role="status">
				<div class="njiwa-hero-brand">
					<img class="njiwa-hero-logo is-wide" src="/assets/njiwa_frappe/images/njiwa-logo.svg" alt="Njiwa">
					<div>
						<h2>${__('WhatsApp settings')}</h2>
						<p>${__('How this site sends WhatsApp messages through Njiwa, and which moments your customers hear about.')}</p>
						${dirty}
					</div>
				</div>
				<div class="njiwa-hero-side">
					<span class="njiwa-pill" data-tone="${tone}"><span class="njiwa-dot"></span>${status}</span>
					<div class="njiwa-hero-actions">
						<button class="njiwa-btn" data-njiwa="back">${__('Njiwa home')}</button>
						<button class="njiwa-btn" data-njiwa="test">${__('Test connection')}</button>
						<button class="njiwa-btn njiwa-btn-primary" data-njiwa="send">${__('Send a test message')}</button>
					</div>
				</div>
			</section>`);
		$hero.on('click', '[data-njiwa]', (event) => {
			const action = event.currentTarget.dataset.njiwa;
			if (action === 'back') frappe.set_route('njiwa');
			if (action === 'test') test_connection(frm);
			if (action === 'send') open_test_message_dialog(frm);
		});

		// Drawn again on every refresh; only ours is taken out.
		const $layout = $(frm.layout.wrapper);
		$layout.find('> .njiwa-hero').remove();
		$layout.prepend($hero);
	}

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

	/** The header's look, added once per page load. Scoped to this form. */
	function add_style() {
		if (document.getElementById('njiwa-form-style')) {
			return;
		}
		const style = document.createElement('style');
		style.id = 'njiwa-form-style';
		style.textContent = `
			.njiwa-form .njiwa-hero { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; justify-content: space-between;
				margin: 12px 0 4px; padding: 20px 22px; border-radius: 16px; color: #fff;
				background: radial-gradient(120% 140% at 100% 0%, rgba(15,163,160,.55), rgba(15,163,160,0) 60%), #0c1a2b; }
			.njiwa-form .njiwa-hero-brand { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; flex: 1 1 320px; min-width: 0; }
			.njiwa-form .njiwa-hero-brand > div { flex: 1; min-width: 200px; }
			.njiwa-form .njiwa-hero h2 { margin: 0; font-size: 20px; font-weight: 700; color: #fff; }
			.njiwa-form .njiwa-hero p { margin: 4px 0 0; font-size: 13px; color: rgba(255,255,255,.78); max-width: 520px; }
			.njiwa-form .njiwa-hero p.njiwa-hero-note { color: #fdd89a; font-weight: 600; }
			.njiwa-form .njiwa-hero-logo { width: 48px; height: 48px; border-radius: 12px; background: #fff; padding: 6px; object-fit: contain; flex: none; }
			.njiwa-form .njiwa-hero-logo.is-wide { width: auto; max-width: 190px; padding: 9px 13px; }
			.njiwa-form .njiwa-hero-side { display: grid; gap: 10px; justify-items: end; }
			.njiwa-form .njiwa-hero-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
			.njiwa-form .njiwa-btn { min-height: 32px; padding: 0 13px; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer;
				border: 1px solid rgba(255,255,255,.28); background: rgba(255,255,255,.08); color: #fff; }
			.njiwa-form .njiwa-btn:hover { background: rgba(255,255,255,.16); }
			.njiwa-form .njiwa-btn-primary { background: ${TEAL}; border-color: ${TEAL}; }
			.njiwa-form .njiwa-pill { display: inline-flex; align-items: center; gap: 7px; padding: 5px 12px; border-radius: 999px; font-size: 12.5px; font-weight: 700; }
			.njiwa-form .njiwa-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
			.njiwa-form .njiwa-pill[data-tone="live"] { background: #d7f5f4; color: #06625f; }
			.njiwa-form .njiwa-pill[data-tone="test"] { background: #fdf0d5; color: #8a5a00; }
			.njiwa-form .njiwa-pill[data-tone="off"], .njiwa-form .njiwa-pill[data-tone="none"] { background: #fde4dc; color: #9a3412; }
			.njiwa-form .form-section .section-head { font-weight: 700; }
			.njiwa-form .frappe-control[data-fieldname^="event_"] .label-area { font-weight: 600; }
			.njiwa-form .frappe-control[data-fieldname^="event_"] { margin-top: 10px; }
			.njiwa-form .frappe-control[data-fieldname^="message_"] textarea { min-height: 72px; border-left: 3px solid ${TEAL}; }
			.njiwa-form .frappe-control .help-box { font-size: 12px; }
			@media (max-width: 600px) {
				.njiwa-form .njiwa-hero { margin: 8px 8px 4px; padding: 16px; }
				.njiwa-form .njiwa-hero-side { justify-items: start; }
				.njiwa-form .njiwa-hero-actions { justify-content: flex-start; }
			}`;
		document.head.appendChild(style);
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
