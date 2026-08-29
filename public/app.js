const $ = s => document.querySelector(s);

let state;
let lastAlertIds = new Set();

const time = t =>
    new Date(t).toLocaleTimeString([], {
        hour: 'numeric',
        minute: '2-digit'
    });

async function api(url, options = {}) {
    const r = await fetch(url, {
        headers: {
            'Content-Type': 'application/json'
        },
        ...options
    });

    const j = await r.json();

    if (!r.ok) {
        throw Error(j.error);
    }

    return j;
}

function showBrowserAlerts(alerts, settings) {
    if (
        !settings?.browser ||
        !('Notification' in window) ||
        Notification.permission !== 'granted'
    ) {
        return;
    }

    alerts
        .filter(
            a =>
                !a.resolved &&
                !lastAlertIds.has(a.id)
        )
        .forEach(
            a =>
                new Notification(
                    'PillPath clinical alert',
                    {
                        body: a.message
                    }
                )
        );

    lastAlertIds = new Set(
        alerts.map(a => a.id)
    );
}

function render(d) {
    state = d;

    const device = d.devices[0];

    const pending = d.doses.filter(
        x => x.status === 'pending'
    ).length;

    const dispensed = d.doses.filter(
        x => x.status === 'dispensed'
    ).length;

    const active = d.alerts.filter(
        x => !x.resolved
    ).length;

    const total = d.doses.length;

    $('#patient-name').textContent =
        device.patient;

    $('#device').innerHTML = `
        <p class="label">Dispenser status</p>
        <strong>
            <span class="online-dot"></span>
            ${device.online ? 'Connected' : 'Not connected'}
        </strong>
        <div class="small">
            ${device.id} · last check-in ${time(device.lastSeen)}
        </div>
    `;

    $('#adherence').textContent =
        total
            ? `${Math.round(dispensed / total * 100)}%`
            : '—';

    $('#pending-total').textContent =
        pending;

    $('#alert-total').textContent =
        active;

    $('#alert-total').className =
        active ? 'needs-review' : '';

    $('#connection').textContent =
        device.online ? 'Online' : 'Offline';

    $('#nav-alert-count').textContent =
        active || '';

    $('#doses').innerHTML =
        d.doses
            .slice()
            .sort(
                (a, b) =>
                    a.dueAt - b.dueAt
            )
            .map(x => {

                const m =
                    d.medications.find(
                        z =>
                            z.id === x.medicationId
                    );

                const event =
                    x.dispensedAt
                        ? `Device recorded ${time(x.dispensedAt)}`
                        : x.status === 'pending'
                            ? 'Awaiting button press'
                            : 'Care team follow-up';

                return `
                    <div class="dose-row">

                        <div>
                            <div class="med-name">
                                ${m?.name || 'Unknown medication'}
                            </div>

                            <div class="subline">
                                ${m?.strength || ''}
                            </div>
                        </div>

                        <div>
                            ${time(x.dueAt)}
                        </div>

                        <span class="status ${x.status}">
                            ${x.status}
                        </span>

                        <div class="event">
                            ${event}
                        </div>

                    </div>
                `;
            })
            .join('') ||
        '<div class="no-alerts">No doses scheduled.</div>';

    $('#alerts-list').innerHTML =
        d.alerts
            .filter(x => !x.resolved)
            .map(
                a => `
                    <div class="clinical-alert">

                        <div class="alert-head ${
                            a.type === 'missed-dose'
                                ? 'critical'
                                : ''
                        }">
                            ● ${a.type.replace('-', ' ')}
                        </div>

                        <p>${a.message}</p>

                        <button
                            class="review"
                            onclick="resolveAlert('${a.id}')"
                        >
                            Mark as reviewed
                        </button>

                    </div>
                `
            )
            .join('') ||
        '<div class="no-alerts">No active clinical alerts.</div>';

    $('#medications').innerHTML =
        d.medications
            .map(
                m => `
                    <div class="stock-row">

                        <div>
                            <div class="med-name">
                                ${m.name}
                            </div>

                            <div class="subline">
                                ${m.strength} · ${m.deviceId}
                            </div>
                        </div>

                        <div class="stock-number ${
                            m.stock <= m.lowAt
                                ? 'low'
                                : ''
                        }">
                            ${m.stock} doses
                        </div>

                        <div class="subline">
                            Refill at ${m.lowAt}
                        </div>

                        <button
                            class="update"
                            onclick="updateStock('${m.id}', ${m.stock})"
                        >
                            Update
                        </button>

                    </div>
                `
            )
            .join('');

    renderSettings(d.alertSettings);

    showBrowserAlerts(
        d.alerts,
        d.alertSettings
    );
}

function renderSettings(s = {}) {
    $('#browser-enabled').checked =
        !!s.browser;

    $('#email-enabled').checked =
        !!s.email;

    $('#sms-enabled').checked =
        !!s.sms;

    $('#email-address').value =
        s.emailAddress || '';

    $('#phone-number').value =
        s.phoneNumber || '';
}

async function refresh() {
    try {
        render(
            await api('/api/dashboard')
        );
    } catch (e) {
        console.error(e);
    }
}

function changeView(view) {
    $('#overview').dataset.view =
        view;

    document
        .querySelectorAll('.nav[data-view]')
        .forEach(a =>
            a.classList.toggle(
                'active',
                a.dataset.view === view
            )
        );
}

window.resolveAlert = async id => {
    await api(
        `/api/alerts/${id}/resolve`,
        {
            method: 'POST'
        }
    );

    refresh();
};

window.updateStock = async (
    id,
    current
) => {
    const stock = prompt(
        'Available doses currently loaded:',
        current
    );

    if (
        stock !== null &&
        Number.isInteger(+stock)
    ) {
        await api(
            `/api/medications/${id}`,
            {
                method: 'PATCH',
                body: JSON.stringify({
                    stock: +stock
                })
            }
        );

        refresh();
    }
};

document
    .querySelectorAll('.nav[data-view]')
    .forEach(a =>
        a.addEventListener(
            'click',
            e => {
                e.preventDefault();

                changeView(
                    a.dataset.view
                );

                history.replaceState(
                    null,
                    '',
                    a.getAttribute('href')
                );
            }
        )
    );

$('#reset').onclick = async () => {
    await api(
        '/api/demo/reset',
        {
            method: 'POST'
        }
    );

    lastAlertIds.clear();

    refresh();
};

$('#add-dose').onclick = () => {
    const sel =
        $('#medication');

    sel.innerHTML =
        state.medications
            .map(
                m =>
                    `<option value="${m.id}">
                        ${m.name} (${m.strength})
                    </option>`
            )
            .join('');

    let t = new Date();

    t.setMinutes(
        t.getMinutes() -
        t.getTimezoneOffset()
    );

    $('#due').value =
        t.toISOString().slice(0, 16);

    $('#dialog').showModal();
};

/*
 * CANCEL BUTTON
 *
 * Because the button is type="button",
 * it does NOT submit the form.
 */
$('#cancel-dose').onclick = () => {
    $('#dialog').close();
};

/*
 * SAVE DOSE
 *
 * This is the only place where a new
 * dose is sent to the server.
 */
$('#dose-form').addEventListener(
    'submit',
    async e => {
        e.preventDefault();

        await api(
            '/api/doses',
            {
                method: 'POST',
                body: JSON.stringify({
                    medicationId:
                        $('#medication').value,

                    dueAt:
                        new Date(
                            $('#due').value
                        ).getTime()
                })
            }
        );

        $('#dialog').close();

        refresh();
    }
);

$('#save-alert-settings').onclick =
    async () => {

        const settings = {
            browser:
                $('#browser-enabled').checked,

            email:
                $('#email-enabled').checked,

            sms:
                $('#sms-enabled').checked,

            emailAddress:
                $('#email-address')
                    .value
                    .trim(),

            phoneNumber:
                $('#phone-number')
                    .value
                    .trim()
        };

        if (
            settings.browser &&
            'Notification' in window &&
            Notification.permission === 'default'
        ) {
            await Notification.requestPermission();
        }

        await api(
            '/api/alert-settings',
            {
                method: 'PATCH',
                body: JSON.stringify(settings)
            }
        );

        $('#delivery-status').textContent =
            'Notification settings saved.';

        refresh();
    };

$('#test-alert').onclick =
    async () => {

        await api(
            '/api/alerts/test',
            {
                method: 'POST',
                body: '{}'
            }
        );

        $('#delivery-status').textContent =
            'Test alert added. Enabled demo deliveries are recorded.';

        refresh();
    };

refresh();

setInterval(
    refresh,
    30000
);
