let clockInterval = null;
let examInterval = null;
let examEndTime = null;
let examStartTime = null;

/* ── CLOCK (with seconds) ─────────────────────────────────────────── */

function tickClock() {
    const now = new Date();
    let h = now.getHours();
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    const ap = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;
    document.getElementById('time-hm').textContent = `${h}:${m}`;
    document.getElementById('time-sec').textContent = `:${s}`;
    document.getElementById('ampm').textContent = ap;
}

function startClock() { tickClock(); clockInterval = setInterval(tickClock, 1000); }

/* ── UTILITIES ────────────────────────────────────────────────────── */

function formatDate(d) {
    return d.toLocaleDateString('en-CA', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
}

function formatEndTime(d) {
    let h = d.getHours();
    const m = String(d.getMinutes()).padStart(2, '0');
    const ap = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;
    return `${h}:${m} ${ap}`;
}

/* ── MARKDOWN via marked.js ───────────────────────────────────────── */

function parseMarkdown(src) {
    return marked.parse(src, { breaks: true });
}

/* ── LAUNCH ───────────────────────────────────────────────────────── */

function launchTimer() {
    const course = document.getElementById('course').value.trim();
    const prof = document.getElementById('professor').value.trim();
    const dur = parseInt(document.getElementById('duration').value, 10);
    const startInstrText = document.getElementById('instructions').value.trim();
    const endInstrText = document.getElementById('end-instructions').value.trim();

    if (!dur || dur < 1) { alert('Please enter a valid exam length in minutes.'); return; }

    // Store duration as ms on the start button for later
    document.getElementById('start-btn').dataset.ms = dur * 60 * 1000;

    document.getElementById('meta-date').textContent = formatDate(new Date());
    document.getElementById('meta-course').textContent = course;
    document.getElementById('meta-prof').textContent = prof;

    const startInstr = document.getElementById('instructions-block');
    if (startInstrText) {
        startInstr.innerHTML = `<div class="instructions-title">Instructions</div>
                    <div class="md-body">${parseMarkdown(startInstrText)}</div>`;
    } else {
        startInstr.innerHTML = '';
    }

    const endInstr = document.getElementById('expired-msg');
    if (endInstrText) {
        endInstr.innerHTML = `<p class="times-up">Time's up.</p><div class="md-body">${parseMarkdown(endInstrText)}</div>`;
    } else {
        endInstr.innerHTML = `<p class="times-up">Time's up.</p>`;
    }

    document.getElementById('setup').style.display = 'none';
    document.getElementById('timer-screen').classList.add('active');
    startClock();
}

/* ── START EXAM ───────────────────────────────────────────────────── */

function startExam() {
    const durationMs = parseInt(document.getElementById('start-btn').dataset.ms, 10);
    document.getElementById('start-btn').style.display = 'none';

    const display = document.getElementById('timer-display');
    display.classList.add('active');

    const badge = document.getElementById('status-badge');
    badge.textContent = 'Exam in progress';
    badge.classList.add('running');

    examStartTime = Date.now();
    examEndTime = new Date(examStartTime + durationMs);
    updateEndTimeDisplay();

    tickExam();
    examInterval = setInterval(tickExam, 1000);
}

/* ── GEAR POPOVER ────────────────────────────────────────────────── */

function toggleGear() {
    const btn = document.getElementById('gear-btn');
    const popover = document.getElementById('end-time-popover');
    const isOpen = popover.classList.toggle('open');
    btn.classList.toggle('open', isOpen);
    if (isOpen) {
        // Pre-fill input with current end time in HH:MM
        const h = String(examEndTime.getHours()).padStart(2, '0');
        const m = String(examEndTime.getMinutes()).padStart(2, '0');
        const s = String(examEndTime.getSeconds()).padStart(2, '0');
        const input = document.getElementById('end-time-input');
        input.value = `${h}:${m}:${s}`;
        setTimeout(() => input.focus(), 50);
    }
}

function applyEndTime() {
    const val = document.getElementById('end-time-input').value;
    if (!val) return;
    const [hh, mm, ss] = val.split(':').map(Number);
    const candidate = new Date();
    candidate.setHours(hh, mm, ss, 0);
    // If the chosen time is in the past, assume they mean tomorrow
    if (candidate <= Date.now()) candidate.setDate(candidate.getDate() + 1);
    examEndTime = candidate;
    updateEndTimeDisplay();
    tickExam();
    closeGear();
}

function closeGear() {
    document.getElementById('gear-btn').classList.remove('open');
    document.getElementById('end-time-popover').classList.remove('open');
}

function updateEndTimeDisplay() {
    document.getElementById('end-time-val').textContent = formatEndTime(examEndTime);
}

// Close popover on outside click
document.addEventListener('click', function (e) {
    const row = document.getElementById('end-time-row');
    if (row && !row.contains(e.target)) closeGear();
});

// Close on Enter key in the time input
document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && document.getElementById('end-time-popover').classList.contains('open')) {
        applyEndTime();
    }
    if (e.key === 'Escape') closeGear();
});

/* ── TICK EXAM ────────────────────────────────────────────────────── */

function tickExam() {
    const now = Date.now();
    const remaining = Math.max(0, examEndTime - now);
    const remSeconds = Math.ceil(remaining / 1000);
    const remMinutes = Math.ceil(remSeconds / 60);

    // Progress uses original span from start to end; stretches/shrinks with adjustments
    const totalSpan = examEndTime - examStartTime;
    const elapsed = now - examStartTime;
    const pct = totalSpan > 0 ? Math.min(100, Math.max(0, (elapsed / totalSpan) * 100)) : 100;

    const remEl = document.getElementById('remaining');
    const barEl = document.getElementById('progress-bar');
    const badge = document.getElementById('status-badge');
    const isWarn = remSeconds <= 300 && remSeconds > 0;

    remEl.textContent = remSeconds > 0 ? remMinutes : '0';
    remEl.classList.toggle('warn', isWarn || remSeconds === 0);
    barEl.style.width = pct + '%';
    barEl.classList.toggle('warn', isWarn || remSeconds === 0);

    if (remSeconds <= 60) {
        document.getElementById("remaining-label").textContent = "minute remaining"
    } else {
        document.getElementById("remaining-label").textContent = "minutes remaining"
    }
    if (remSeconds <= 0) {
        clearInterval(examInterval);
        document.getElementById('timer-display').style.display = 'none';
        document.getElementById('expired-msg').classList.add('active');
        badge.textContent = 'Expired';
        badge.classList.remove('running');
        badge.classList.add('expired');
    }
}

/* ── RESET ────────────────────────────────────────────────────────── */

function resetTimer() {
    clearInterval(clockInterval);
    clearInterval(examInterval);
    clockInterval = examInterval = examEndTime = examStartTime = null;

    document.getElementById('start-btn').style.display = '';
    const td = document.getElementById('timer-display');
    td.classList.remove('active');
    td.style.display = '';
    document.getElementById('expired-msg').classList.remove('active');
    document.getElementById('remaining').textContent = '—';
    document.getElementById('remaining').classList.remove('warn');
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-bar').classList.remove('warn');
    document.getElementById('end-time-val').textContent = '—';
    closeGear();

    const badge = document.getElementById('status-badge');
    badge.textContent = 'Ready';
    badge.classList.remove('running', 'expired');

    document.getElementById('timer-screen').classList.remove('active');
    document.getElementById('setup').style.display = '';
}