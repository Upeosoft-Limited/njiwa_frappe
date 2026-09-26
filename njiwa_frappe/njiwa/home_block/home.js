// The Njiwa page. Frappe runs this inside the block's shadow root and hands it
// `root_element`; everything below reads through it, never through document.
const $ = (sel) => root_element.querySelector(sel);
const slot = (name) => $(`[data-slot="${name}"]`);
const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
const SUMMARY = "njiwa_frappe.home.summary";
const SET_EVENT = "njiwa_frappe.home.set_event";

const STATUS = {
	live: { tone: "live", text: __("Live · sending for real") },
	test: { tone: "test", text: __("Test mode · nothing reaches a phone") },
	off: { tone: "off", text: __("Connected · sending is off") },
	none: { tone: "none", text: __("Not connected yet") },
};

let data = null;
let busy = false;

function render() {
	if (data.logo) {
		const img = slot("logo");
		img.src = data.logo;
		img.alt = "";
		img.classList.add("nj-logo");
	}
	const s = data.key === "none" ? STATUS.none : !data.enabled ? STATUS.off : STATUS[data.key];
	const pill = slot("status");
	pill.dataset.tone = s.tone;
	pill.innerHTML = `<span class="nj-dot"></span><span>${esc(s.text)}</span>`;

	const banner = slot("banner");
	const anyOn = data.events.some((e) => e.on) || data.owner_event.on;
	if (data.key !== "none" && !data.enabled && anyOn) {
		banner.hidden = false;
		banner.textContent = __("Some messages are switched on, but sending is off in the settings, so nothing goes out yet.");
	} else {
		banner.hidden = true;
	}

	slot("sent").textContent = data.counts.sent;
	slot("failed").textContent = data.counts.failed;
	slot("failed").classList.toggle("nj-has", data.counts.failed > 0);
	slot("queued").textContent = data.counts.queued;

	const done = data.steps.filter((x) => x.done).length;
	slot("setup").hidden = done === data.steps.length;
	slot("setup-count").textContent = __("{0} of {1} done", [done, data.steps.length]);
	slot("setup-bar").style.width = `${Math.round((done / data.steps.length) * 100)}%`;
	slot("steps").innerHTML = data.steps
		.map((x, i) => `<li class="nj-step ${x.done ? "done" : ""}">
			<span class="nj-step-mark">${x.done ? "✓" : i + 1}</span>
			<div><b>${esc(x.title)}</b><span>${esc(x.hint)}</span></div></li>`)
		.join("");

	const groups = {};
	data.events.forEach((e) => (groups[e.group] = groups[e.group] || []).push(e));
	slot("events").innerHTML = Object.entries(groups)
		.map(([group, rows]) => `<div class="nj-group"><div class="nj-group-name">${esc(__(group))}</div>
			${rows.map((e) => eventRow(e, e.on && !e.worded ? __("The wording is empty, so nothing is sent.") : "")).join("")}</div>`)
		.join("");

	const o = data.owner_event;
	const hint = o.on && !o.numbers
		? `<span class="nj-event-warn">${esc(__("Add your WhatsApp number in the settings."))}</span>`
		: `<span class="nj-event-hint">${esc(o.numbers ? __("Goes to {0} number(s) of yours", [o.numbers]) : __("A message to your own phone for each new order"))}</span>`;
	slot("owner").innerHTML = `<div class="nj-event"><div><span class="nj-event-name">${esc(o.label)}</span>${hint}</div>${toggle(o)}</div>`;

	slot("recent").innerHTML = data.recent.length
		? data.recent.map((r) => `<li data-open="${esc(r.name)}">
			<span class="nj-r-dot" data-s="${esc(r.status)}"></span>
			<div class="nj-r-body">
				<div class="nj-r-what">${esc(r.event || __("Message"))}</div>
				<div class="nj-r-meta">${esc(r.status)} · ${esc(r.to)}${r.docname ? ` · ${esc(r.docname)}` : ""} · ${esc(frappe.datetime.prettyDate(r.at))}</div>
				${r.why ? `<div class="nj-r-why">${esc(r.why)}</div>` : ""}
			</div></li>`).join("")
		: `<li class="nj-empty">${esc(__("Nothing has been sent yet."))}</li>`;
}

function toggle(e) {
	return `<button class="nj-switch" role="switch" aria-checked="${e.on}" aria-label="${esc(e.label)}" data-event="${esc(e.key)}"></button>`;
}

function eventRow(e, warn) {
	return `<div class="nj-event"><div><span class="nj-event-name">${esc(e.label)}</span>${warn ? `<span class="nj-event-warn">${esc(warn)}</span>` : ""}</div>${toggle(e)}</div>`;
}

async function load() {
	try {
		data = await frappe.xcall(SUMMARY);
		root_element.querySelector(".nj").dataset.state = "ready";
		render();
	} catch (e) {
		slot("events").innerHTML = `<p class="nj-error">${esc(__("The Njiwa page could not load. Refresh to try again."))}</p>`;
	}
}

async function flip(button) {
	if (busy) return;
	busy = true;
	const on = button.getAttribute("aria-checked") !== "true";
	button.setAttribute("aria-checked", String(on));
	button.disabled = true;
	try {
		data = await frappe.xcall(SET_EVENT, { event: button.dataset.event, on: on ? 1 : 0 });
		render();
		frappe.show_alert({ message: on ? __("Switched on") : __("Switched off"), indicator: "green" });
	} catch (e) {
		button.setAttribute("aria-checked", String(!on));
	} finally {
		button.disabled = false;
		busy = false;
	}
}

function sendTest() {
	frappe.prompt(
		{ fieldname: "to", fieldtype: "Data", label: __("Send it to"), reqd: 1, description: __("Your own WhatsApp number, e.g. 0712345678") },
		(values) => frappe.call({
			method: "njiwa_frappe.api.send_test_message",
			args: { to: values.to },
			freeze: true,
			freeze_message: __("Sending…"),
			callback: () => load(),
		}),
		__("Send a test message"),
		__("Send"),
	);
}

root_element.addEventListener("click", (ev) => {
	const sw = ev.target.closest(".nj-switch");
	if (sw) return flip(sw);
	const open = ev.target.closest("[data-open]");
	if (open) return frappe.set_route("Form", "Njiwa Sent Message", open.dataset.open);
	const action = ev.target.closest("[data-action]")?.dataset.action;
	if (action === "settings" || action === "wording") return frappe.set_route("Form", "Njiwa Settings");
	if (action === "all") return frappe.set_route("List", "Njiwa Sent Message");
	if (action === "send") return sendTest();
	if (action === "test") {
		frappe.call({ method: "njiwa_frappe.api.test_connection", freeze: true, freeze_message: __("Asking Njiwa…") });
	}
});

slot("events").innerHTML = '<span class="nj-skel"></span><span class="nj-skel"></span><span class="nj-skel"></span>';
load();
