/**
 * Общие JS-утилиты для SPA-страниц.
 * Аналог общих функций из Flask plan.html.
 */

/* ── CSRF-токен для fetch ─────────────────────────────────────────────────── */

function getCsrfToken() {
    const cookie = document.cookie.split(';')
        .find(c => c.trim().startsWith('csrftoken='));
    if (cookie) return cookie.split('=')[1];
    const meta = document.querySelector('[name=csrfmiddlewaretoken]');
    if (meta) return meta.value;
    const inp = document.querySelector('input[name=csrfmiddlewaretoken]');
    if (inp) return inp.value;
    return '';
}

/* ── Обёртка fetch для JSON API ──────────────────────────────────────────── */

async function fetchJson(url, options = {}) {
    const defaults = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'same-origin',
    };
    const merged = { ...defaults, ...options };
    if (options.headers) {
        merged.headers = { ...defaults.headers, ...options.headers };
    }

    try {
        const resp = await fetch(url, merged);
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
            const msg = data.error || data.message || `Ошибка ${resp.status}`;
            if (resp.status === 409) {
                showToast(msg, 'warning');
                return { _conflict: true, ...data };
            }
            showToast(msg, 'error');
            return { _error: true, status: resp.status, ...data };
        }
        return data;
    } catch (err) {
        showToast('Ошибка сети: ' + err.message, 'error');
        return { _error: true, message: err.message };
    }
}

/* ── Toast-уведомления ───────────────────────────────────────────────────── */

let _toastContainer = null;

function _ensureToastContainer() {
    if (_toastContainer) return _toastContainer;
    _toastContainer = document.createElement('div');
    _toastContainer.id = 'toast-container';
    _toastContainer.style.cssText = `
        position: fixed; top: 16px; right: 16px; z-index: 10000;
        display: flex; flex-direction: column; gap: 8px;
        pointer-events: none;
    `;
    document.body.appendChild(_toastContainer);
    return _toastContainer;
}

function showToast(message, type = 'info', duration = 4000) {
    const container = _ensureToastContainer();
    const toast = document.createElement('div');

    const colors = {
        info:    { bg: 'rgba(59,130,246,0.22)', border: 'rgba(59,130,246,0.6)', text: '#bfdbfe' },
        success: { bg: 'rgba(34,197,94,0.22)',  border: 'rgba(34,197,94,0.6)',  text: '#a7f3d0' },
        warning: { bg: 'rgba(245,158,11,0.25)', border: 'rgba(245,158,11,0.6)', text: '#fde68a' },
        error:   { bg: 'rgba(220,38,38,0.95)',   border: 'rgba(255,100,100,1)', text: '#ffffff' },
    };
    const c = colors[type] || colors.info;

    toast.style.cssText = `
        background: ${c.bg}; border: 1.5px solid ${c.border}; color: ${c.text};
        padding: 14px 22px; border-radius: 10px; font-size: 15px; font-weight: 500;
        backdrop-filter: blur(14px); pointer-events: auto;
        animation: toastIn 0.3s ease-out;
        max-width: 480px; min-width: 240px; word-wrap: break-word;
        box-shadow: 0 4px 16px rgba(0,0,0,0.25);
    `;
    toast.textContent = message;
    container.appendChild(toast);

    let remaining = duration;
    let startTime = Date.now();
    let timerId = setTimeout(dismissToast, remaining);

    function dismissToast() {
        toast.style.animation = 'toastOut 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
    }

    toast.addEventListener('mouseenter', () => {
        clearTimeout(timerId);
        remaining -= (Date.now() - startTime);
    });
    toast.addEventListener('mouseleave', () => {
        startTime = Date.now();
        timerId = setTimeout(dismissToast, remaining);
    });
}

// CSS-анимации для тостов
(function() {
    if (document.getElementById('toast-animations')) return;
    const style = document.createElement('style');
    style.id = 'toast-animations';
    style.textContent = `
        @keyframes toastIn { from { opacity: 0; transform: translateX(30px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes toastOut { from { opacity: 1; } to { opacity: 0; transform: translateY(-10px); } }
    `;
    document.head.appendChild(style);
})();


/* ── Кнопка-загрузка ────────────────────────────────────────────────────── */

function setButtonLoading(btn, loading) {
    if (loading) {
        btn._origHTML = btn.innerHTML;
        btn.disabled = true;
        btn.classList.add('btn-loading');
        const spinner = document.createElement('span');
        spinner.className = 'spinner';
        btn.prepend(spinner);
    } else {
        btn.disabled = false;
        btn.classList.remove('btn-loading');
        if (btn._origHTML !== undefined) btn.innerHTML = btn._origHTML;
    }
}

/* ── Debounce ────────────────────────────────────────────────────────────── */

function debounce(fn, delay = 300) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

/* ── Форматирование дат ──────────────────────────────────────────────────── */

function formatDate(dateStr) {
    if (!dateStr) return '—';
    const parts = dateStr.split('-');
    if (parts.length === 3) return `${parts[2]}.${parts[1]}.${parts[0]}`;
    return dateStr;
}

function formatDateISO(dateStr) {
    if (!dateStr) return '';
    // dd.mm.yyyy → yyyy-mm-dd
    const parts = dateStr.split('.');
    if (parts.length === 3) return `${parts[2]}-${parts[1]}-${parts[0]}`;
    return dateStr;
}

/* ── Утилиты для работы с URL-параметрами ─────────────────────────────── */

function getUrlParams() {
    return Object.fromEntries(new URLSearchParams(window.location.search));
}

function setUrlParams(params) {
    const url = new URL(window.location);
    Object.entries(params).forEach(([k, v]) => {
        if (v === null || v === undefined || v === '') {
            url.searchParams.delete(k);
        } else {
            url.searchParams.set(k, v);
        }
    });
    window.history.replaceState({}, '', url);
}

/* ── Escape HTML ─────────────────────────────────────────────────────────── */

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/* ── Месяц-навигация ─────────────────────────────────────────────────────── */

function monthAdd(dateStr, months) {
    // dateStr: "YYYY-MM"
    const [y, m] = dateStr.split('-').map(Number);
    let newM = m + months;
    let newY = y;
    while (newM > 12) { newM -= 12; newY++; }
    while (newM < 1) { newM += 12; newY--; }
    return `${newY}-${String(newM).padStart(2, '0')}`;
}

function monthLabel(dateStr) {
    const months = [
        'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ];
    const [y, m] = dateStr.split('-').map(Number);
    return `${months[m - 1]} ${y}`;
}

function currentMonth() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

/* ── Scroll-loader для infinite scroll ─────────────────────────────────── */

/**
 * Создаёт слушатель прокрутки, вызывающий callback при приближении к низу.
 * @param {HTMLElement|Window} container — элемент с overflow-y или window
 * @param {Function} onNearBottom — callback при достижении порога
 * @param {number} threshold — пикселей до низа для срабатывания (по умолчанию 200)
 * @returns {Function} dispose — удаляет слушатель
 */
function createScrollLoader(container, onNearBottom, threshold = 200) {
    let _ticking = false;
    const target = container === window ? window : container;

    function onScroll() {
        if (_ticking) return;
        _ticking = true;
        requestAnimationFrame(() => {
            _ticking = false;
            let distToBottom;
            if (container === window) {
                distToBottom = document.documentElement.scrollHeight
                    - window.scrollY - window.innerHeight;
            } else {
                distToBottom = container.scrollHeight
                    - container.scrollTop - container.clientHeight;
            }
            if (distToBottom < threshold) onNearBottom();
        });
    }

    target.addEventListener('scroll', onScroll, { passive: true });
    return function dispose() {
        target.removeEventListener('scroll', onScroll);
    };
}
