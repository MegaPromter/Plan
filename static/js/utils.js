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
        warning: { bg: 'rgba(245,158,11,0.92)', border: 'rgba(245,158,11,1)', text: '#ffffff' },
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
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    toast.setAttribute('aria-atomic', 'true');
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

/* ── Синхронизация фильтров с URL (для расшаренных ссылок) ──────────────── */

/**
 * Записывает объект фильтров в URL query-параметры (без перезагрузки).
 * Пустые / null / undefined значения удаляются из URL.
 * @param {Object} params — например {year: 2026, month: 3, dept: '021', status: 'overdue'}
 */
function syncFiltersToUrl(params) {
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

/**
 * Считывает фильтры из текущих URL query-параметров.
 * Возвращает объект только с ключами из переданного списка.
 * @param {string[]} keys — список ожидаемых ключей (фильтрация мусора)
 * @returns {Object} — например {year: '2026', month: '3', dept: '021'}
 */
function readFiltersFromUrl(keys) {
    const sp = new URLSearchParams(window.location.search);
    const result = {};
    (keys || []).forEach(k => {
        if (sp.has(k)) result[k] = sp.get(k);
    });
    if (!keys) return Object.fromEntries(sp);
    return result;
}

/* ── Avatar helper ───────────────────────────────────────────────────────── */

function avatarHtml(fullName, size) {
    var parts = (fullName || '').trim().split(/\s+/);
    var initials = parts.length >= 2
        ? (parts[0][0] + parts[1][0]).toUpperCase()
        : (parts[0] || '?').substring(0, 2).toUpperCase();
    var colors = ['#e53e3e','#dd6b20','#d69e2e','#38a169','#319795','#3182ce','#5a67d8','#805ad5','#d53f8c'];
    var hash = 0;
    for (var i = 0; i < fullName.length; i++) hash = fullName.charCodeAt(i) + ((hash << 5) - hash);
    var color = colors[Math.abs(hash) % colors.length];
    var cls = 'avatar-circle' + (size ? ' ' + size : '');
    return '<span class="' + cls + '" style="background:' + color + '" title="' + escapeHtml(fullName) + '">' + initials + '</span>';
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

/* ── Единый бейдж типа задачи ──────────────────────────────────────────── */

/**
 * Возвращает HTML-строку бейджа типа задачи.
 * @param {string} taskType — полное название ("Выпуск нового документа", "Корректировка документа", ...)
 * @param {object} [opts] — опции: short=true — сокращённый текст ("нов","корр","разр","ОКАН")
 * @returns {string} HTML <span class="badge-sm ...">...</span>
 */
function taskTypeBadgeHtml(taskType, opts) {
    if (!taskType) return '';
    var map = {
        'Выпуск нового документа': {cls: 'tt-выпуск', short: 'нов'},
        'Корректировка документа': {cls: 'tt-корректировка', short: 'корр'},
        'Разработка':              {cls: 'tt-разработка', short: 'разр'},
        'Сопровождение (ОКАН)':    {cls: 'tt-сопровождение', short: 'ОКАН'},
    };
    var info = map[taskType];
    if (!info) return '<span class="badge-sm">' + escapeHtml(taskType) + '</span>';
    var text = (opts && opts.short) ? info.short : taskType;
    return '<span class="badge-sm ' + info.cls + '" data-full="' + escapeHtml(taskType) + '">' + escapeHtml(text) + '</span>';
}

/* Тултип для всех badge-sm (event delegation, position:fixed, справа) */
(function() {
    var tip = null;
    function getText(badge) {
        return badge.getAttribute('data-full') || badge.getAttribute('title') || '';
    }
    function show(badge) {
        var text = getText(badge);
        if (!text) return;
        if (!tip) {
            tip = document.createElement('div');
            tip.className = 'tt-tip';
            document.body.appendChild(tip);
        }
        // Убираем нативный title на время показа
        if (badge.hasAttribute('title')) {
            badge.setAttribute('data-title-bak', badge.getAttribute('title'));
            badge.removeAttribute('title');
        }
        tip.textContent = text;
        tip.style.background = getComputedStyle(badge).color;
        var r = badge.getBoundingClientRect();
        tip.style.left = (r.right + 6) + 'px';
        tip.style.top = (r.top + r.height / 2) + 'px';
        tip.style.transform = 'translateY(-50%)';
        tip.classList.add('visible');
    }
    function hide(badge) {
        if (tip) tip.classList.remove('visible');
        // Восстанавливаем title
        if (badge && badge.hasAttribute('data-title-bak')) {
            badge.setAttribute('title', badge.getAttribute('data-title-bak'));
            badge.removeAttribute('data-title-bak');
        }
    }
    var currentBadge = null;
    document.addEventListener('mouseover', function(e) {
        var b = e.target.closest && e.target.closest('.badge-sm');
        if (b && b !== currentBadge && (b.hasAttribute('data-full') || b.hasAttribute('title'))) {
            currentBadge = b;
            show(b);
        } else if (!b && currentBadge) {
            hide(currentBadge);
            currentBadge = null;
        }
    });
    document.addEventListener('mouseout', function(e) {
        if (!currentBadge) return;
        var related = e.relatedTarget;
        if (!related || !currentBadge.contains(related)) {
            hide(currentBadge);
            currentBadge = null;
        }
    });
})();

/* ══════════════════════════════════════════════════════════════════════════
   Sticky Horizontal Scrollbar + Drag-to-Scroll
   Автоматически находит обёртки таблиц и добавляет:
   1) Приклеенный к низу viewport горизонтальный скроллбар
   2) Drag-scroll через среднюю (колесо) и правую кнопку мыши
   ══════════════════════════════════════════════════════════════════════════ */

(function() {
    // Селекторы обёрток таблиц, в которых может понадобиться горизонтальный скролл
    const WRAP_SELECTORS = '.table-wrap, .pp-table-wrap, .ji-wrap, .data-table-wrap';

    // Порог перемещения мыши (px) — если меньше, считаем кликом, а не drag
    const DRAG_THRESHOLD = 3;

    /* ── Sticky Scrollbar ──────────────────────────────────────────────── */

    function initStickyScrollbar(wrap) {
        // Не создаём повторно
        if (wrap._stickyScrollbar) return;

        // Создаём sticky-div внизу обёртки
        const bar = document.createElement('div');
        bar.className = 'sticky-hscroll';
        const inner = document.createElement('div');
        inner.className = 'sticky-hscroll-inner';
        bar.appendChild(inner);

        // Вставляем сразу после обёртки (внутри родителя)
        wrap.parentNode.insertBefore(bar, wrap.nextSibling);
        wrap._stickyScrollbar = bar;

        // Флаг для предотвращения рекурсивного scroll-события
        let syncing = false;

        // Обёртка → sticky: при скролле таблицы обновляем sticky-bar
        wrap.addEventListener('scroll', function() {
            if (syncing) return;
            syncing = true;
            bar.scrollLeft = wrap.scrollLeft;
            syncing = false;
        }, { passive: true });

        // Sticky → обёртка: при скролле sticky-bar обновляем таблицу
        bar.addEventListener('scroll', function() {
            if (syncing) return;
            syncing = true;
            wrap.scrollLeft = bar.scrollLeft;
            syncing = false;
        }, { passive: true });

        // Обновляем ширину inner (= scrollWidth таблицы) и видимость
        function updateSize() {
            const sw = wrap.scrollWidth;
            const cw = wrap.clientWidth;
            inner.style.width = sw + 'px';
            // Скрываем если скролл не нужен (таблица влезает)
            bar.classList.toggle('hidden', sw <= cw + 1);
        }

        // Наблюдаем за изменением размера таблицы
        if (typeof ResizeObserver !== 'undefined') {
            const ro = new ResizeObserver(updateSize);
            ro.observe(wrap);
            // Если внутри есть table — наблюдаем и за ней
            const table = wrap.querySelector('table');
            if (table) ro.observe(table);
        }

        // Начальная синхронизация
        updateSize();
    }

    /* ── Drag-to-Scroll ────────────────────────────────────────────────── */

    function initDragScroll(wrap) {
        if (wrap._dragScrollInit) return;
        wrap._dragScrollInit = true;

        let dragging = false;   // идёт ли перетаскивание прямо сейчас
        let startX = 0;        // координата X мыши в момент нажатия
        let startScrollLeft = 0;// scrollLeft обёртки в момент нажатия
        let totalDx = 0;       // суммарное смещение (для отличия клика от drag)
        let suppressContext = false; // блокировать ли контекстное меню после drag

        function onDown(e) {
            // Реагируем только на колесо (button=1) и правую кнопку (button=2)
            if (e.button !== 1 && e.button !== 2) return;

            // Не начинаем drag если контент не шире контейнера
            if (wrap.scrollWidth <= wrap.clientWidth + 1) return;

            dragging = true;
            startX = e.clientX;
            startScrollLeft = wrap.scrollLeft;
            totalDx = 0;
            suppressContext = false;

            wrap.classList.add('drag-scroll-active');
            e.preventDefault(); // предотвращаем авто-скролл (колесо) и контекстное меню (ПКМ)
        }

        function onMove(e) {
            if (!dragging) return;
            var dx = e.clientX - startX;
            totalDx += Math.abs(dx);
            startX = e.clientX;
            wrap.scrollLeft = wrap.scrollLeft - dx;

            // Синхронизируем sticky-scrollbar
            if (wrap._stickyScrollbar) {
                wrap._stickyScrollbar.scrollLeft = wrap.scrollLeft;
            }
        }

        function onUp(e) {
            if (!dragging) return;
            dragging = false;
            wrap.classList.remove('drag-scroll-active');

            // Если сместились больше порога — блокируем context menu для ПКМ
            if (totalDx > DRAG_THRESHOLD && e.button === 2) {
                suppressContext = true;
            }
        }

        // Блокируем контекстное меню только после drag правой кнопкой
        function onContext(e) {
            if (suppressContext) {
                e.preventDefault();
                suppressContext = false;
            }
        }

        wrap.addEventListener('mousedown', onDown);
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
        wrap.addEventListener('contextmenu', onContext);

        // Отменяем drag если мышь ушла за пределы окна
        document.addEventListener('mouseleave', function() {
            if (dragging) {
                dragging = false;
                wrap.classList.remove('drag-scroll-active');
            }
        });
    }

    /* ── Инициализация ─────────────────────────────────────────────────── */

    function initAll() {
        document.querySelectorAll(WRAP_SELECTORS).forEach(function(wrap) {
            initStickyScrollbar(wrap);
            initDragScroll(wrap);
        });
    }

    // При загрузке DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }

    // Повторная инициализация через 1с (SPA может добавить таблицы позже)
    setTimeout(initAll, 1000);

    // MutationObserver: ловим динамически добавленные таблицы
    if (typeof MutationObserver !== 'undefined') {
        var observer = new MutationObserver(function(mutations) {
            for (var i = 0; i < mutations.length; i++) {
                if (mutations[i].addedNodes.length) {
                    initAll();
                    return;
                }
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }
})();

/* ── LazyRender — ленивая отрисовка таблицы с infinite scroll ─────────── */
/**
 * Создаёт контроллер ленивой отрисовки.
 * @param {Object} opts
 * @param {string} opts.tbodyId       — id tbody
 * @param {string} opts.scrollWrap    — CSS-селектор контейнера с прокруткой
 * @param {string} opts.spinnerId     — id элемента спиннера
 * @param {number} opts.chunkSize     — размер порции (default 50)
 * @param {number} opts.colSpan       — colspan для спиннера
 * @param {Function} opts.makeRow     — function(item, idx) → HTMLElement | string
 * @param {Function} [opts.onBatch]   — callback после каждой порции
 * @returns {Object} controller с методами reset(filtered), appendBatch(), dispose()
 */
function createLazyRender(opts) {
    var chunkSize = opts.chunkSize || 50;
    var filtered = [];
    var renderedCount = 0;
    var scrollDispose = null;

    function appendBatch(count) {
        var tbody = document.getElementById(opts.tbodyId);
        if (!tbody) return;
        var end = Math.min(renderedCount + (count || chunkSize), filtered.length);
        var spinner = document.getElementById(opts.spinnerId);
        if (spinner) spinner.remove();

        var frag = document.createDocumentFragment();
        for (var i = renderedCount; i < end; i++) {
            var row = opts.makeRow(filtered[i], i + 1);
            if (typeof row === 'string') {
                var tmp = document.createElement('tbody');
                tmp.innerHTML = row;
                while (tmp.firstChild) frag.appendChild(tmp.firstChild);
            } else if (row) {
                frag.appendChild(row);
            }
        }
        tbody.appendChild(frag);
        renderedCount = end;

        if (opts.onBatch) opts.onBatch(renderedCount, filtered.length);

        // Спиннер если ещё есть строки
        if (renderedCount < filtered.length) {
            var spinnerTr = document.createElement('tr');
            spinnerTr.id = opts.spinnerId;
            spinnerTr.innerHTML = '<td colspan="' + (opts.colSpan || 15) + '" class="scroll-spinner"><i class="fas fa-spinner"></i> Загрузка...</td>';
            tbody.appendChild(spinnerTr);
        }
    }

    function attachScroll() {
        if (scrollDispose) { scrollDispose(); scrollDispose = null; }
        if (renderedCount >= filtered.length) return;
        var wrap = document.querySelector(opts.scrollWrap);
        if (!wrap) return;
        scrollDispose = createScrollLoader(wrap, function() {
            if (renderedCount < filtered.length) {
                appendBatch(chunkSize);
                if (renderedCount >= filtered.length && scrollDispose) {
                    scrollDispose(); scrollDispose = null;
                }
            }
        }, 200);
    }

    function dispose() {
        if (scrollDispose) { scrollDispose(); scrollDispose = null; }
    }

    return {
        reset: function(data) {
            dispose();
            filtered = data || [];
            renderedCount = 0;
            var tbody = document.getElementById(opts.tbodyId);
            if (tbody) tbody.innerHTML = '';
        },
        render: function(data) {
            this.reset(data);
            if (filtered.length > 0) {
                appendBatch(chunkSize);
                attachScroll();
            }
        },
        appendBatch: appendBatch,
        attachScroll: attachScroll,
        dispose: dispose,
        getRenderedCount: function() { return renderedCount; },
        getFiltered: function() { return filtered; }
    };
}

/* ── Общие форматтеры ────────────────────────────────────────────────── */

/** Алиас escapeHtml для краткости */
var esc = escapeHtml;

/** Форматирование процентов: 85.3% */
function fmtPct(v) { return v > 0 ? v.toFixed(1) + '%' : '0%'; }

/** Форматирование часов: 123.5 */
function fmtHrs(v) { return v > 0 ? v.toFixed(1) : '0'; }

/** Дата ISO → DD.MM.YYYY */
function fmtDate(iso) {
    if (!iso) return '—';
    return iso.slice(8,10) + '.' + iso.slice(5,7) + '.' + iso.slice(0,4);
}

/** Дата+время ISO → DD.MM.YYYY HH:MM */
function fmtDateTime(iso) {
    if (!iso) return '';
    return iso.slice(8,10) + '.' + iso.slice(5,7) + '.' + iso.slice(0,4) +
        ' ' + iso.slice(11,16);
}

/** CSS-класс бейджа загрузки по проценту */
function loadBadgeCls(pct) {
    if (pct <= 85) return 'ok';
    if (pct <= 100) return 'warn';
    return 'over';
}

/* ── Права доступа (общие) ───────────────────────────────────────────── */

/** Может ли пользователь модифицировать строку (dept/sector) */
function canModifyRow(isWriter, isAdmin, userRole, userDept, userSector, rowDept, rowSector) {
    if (!isWriter) return false;
    if (isAdmin || userRole === 'ntc_head' || userRole === 'ntc_deputy') return true;
    if (userRole === 'sector_head') return !!rowSector && rowSector === userSector;
    return !!rowDept && rowDept === userDept;
}

/** Полный доступ (admin/ntc_head/ntc_deputy) */
function isFullAccess(isAdmin, userRole) {
    return isAdmin || userRole === 'ntc_head' || userRole === 'ntc_deputy';
}

/* ── Переключатель плотности (общий) ─────────────────────────────────── */

function initDensityToggle(wrapSelector, savedDensity) {
    var wrap = document.querySelector(wrapSelector);
    if (!wrap) return;
    var saved = savedDensity || 'comfortable';
    if (saved !== 'comfortable') wrap.classList.add('density-' + saved);
    var toggle = document.getElementById('densityToggle');
    if (!toggle) return;
    toggle.querySelectorAll('button').forEach(function(btn) {
        btn.classList.toggle('active', btn.dataset.density === saved);
        btn.addEventListener('click', function() {
            var d = this.dataset.density;
            wrap.classList.remove('density-compact', 'density-comfortable', 'density-spacious');
            if (d !== 'comfortable') wrap.classList.add('density-' + d);
            toggle.querySelectorAll('button').forEach(function(b) {
                b.classList.toggle('active', b.dataset.density === d);
            });
            fetch('/api/col_settings/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken()},
                body: JSON.stringify({density: d})
            }).catch(function() {});
        });
    });
}

/* ── Skeleton rows (общая заглушка загрузки таблицы) ──────────────────── */

function skeletonRows(count, cols) {
    var html = '';
    for (var i = 0; i < count; i++) {
        html += '<tr>';
        for (var c = 0; c < cols; c++) {
            var w = c === 0 ? 'sk-id' : (c < 3 ? 'sk-text' : (c % 3 === 0 ? 'sk-text-sm' : 'sk-text-md'));
            html += '<td><span class="skeleton ' + w + '" style="animation-delay:' + (i * 0.08) + 's"></span></td>';
        }
        html += '</tr>';
    }
    return html;
}

/* ── escapeJs (экранирование строки для JS-литерала) ─────────────────── */

function escapeJs(s) {
    if (!s) return '';
    return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"')
                     .replace(/\n/g, '\\n').replace(/\r/g, '\\r');
}

/* ── Универсальная сортировка массива данных по столбцу ────────────────── */
/**
 * Состояние сортировки: {col: string, dir: 'asc'|'desc'}
 * Использование:
 *   1. Вызвать toggleSort(state, colKey) при клике на заголовок
 *   2. Вызвать applySortToArray(array, state, getVal) для сортировки
 *   3. Вызвать renderSortIndicators(thElements, state) для отрисовки стрелок
 */

function toggleSort(state, colKey) {
    if (state.col === colKey) {
        state.dir = state.dir === 'asc' ? 'desc' : 'asc';
    } else {
        state.col = colKey;
        state.dir = 'asc';
    }
}

function applySortToArray(arr, state, getVal) {
    if (!state.col) return arr;
    var col = state.col;
    var dir = state.dir === 'desc' ? -1 : 1;
    return arr.slice().sort(function(a, b) {
        var va = getVal(a, col);
        var vb = getVal(b, col);
        if (va == null) va = '';
        if (vb == null) vb = '';
        // Числа
        if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
        // Даты (YYYY-MM-DD)
        if (typeof va === 'string' && /^\d{4}-\d{2}/.test(va)) {
            return va.localeCompare(vb) * dir;
        }
        // Строки
        va = String(va).toLowerCase();
        vb = String(vb).toLowerCase();
        return va.localeCompare(vb, 'ru') * dir;
    });
}

function renderSortIndicators(container, state) {
    var ths = container.querySelectorAll('th[data-sort]');
    ths.forEach(function(th) {
        var key = th.getAttribute('data-sort');
        // Удаляем старые индикаторы
        var old = th.querySelector('.sort-ind');
        if (old) old.remove();
        // Добавляем новый
        var span = document.createElement('span');
        span.className = 'sort-ind';
        span.style.cssText = 'margin-left:4px;font-size:10px;opacity:0.5;';
        if (state.col === key) {
            span.style.opacity = '1';
            span.textContent = state.dir === 'asc' ? '▲' : '▼';
        } else {
            span.textContent = '⇅';
        }
        th.appendChild(span);
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
    });
}

/* ── StatusPanel — универсальная панель статусов ──────────────────────── */
/**
 * Обновляет панель статусов (progress bar + счётчики).
 * @param {Object} opts
 * @param {string} opts.panelId    — id панели (e.g. 'spStatusPanel')
 * @param {string} opts.prefix     — префикс id элементов (e.g. 'sp' → spCountAll, spBarDone)
 * @param {Array}  opts.data       — массив данных
 * @param {Function} opts.getStatus — function(item) → 'done'|'overdue'|'inwork'
 * @param {string} opts.activeFilter — текущий фильтр статуса
 */
function updateStatusPanel(opts) {
    var panel = document.getElementById(opts.panelId);
    if (!panel || !opts.data || opts.data.length === 0) {
        if (panel) panel.style.display = 'none';
        return;
    }
    panel.style.display = '';

    var done = 0, overdue = 0, inwork = 0;
    opts.data.forEach(function(item) {
        var s = opts.getStatus(item);
        if (s === 'done') done++;
        else if (s === 'overdue') overdue++;
        else inwork++;
    });
    var total = opts.data.length;
    var p = opts.prefix;

    var el;
    el = document.getElementById(p + 'CountAll'); if (el) el.textContent = total;
    el = document.getElementById(p + 'CountDone'); if (el) el.textContent = done;
    el = document.getElementById(p + 'CountOverdue'); if (el) el.textContent = overdue;
    el = document.getElementById(p + 'CountInWork'); if (el) el.textContent = inwork;

    el = document.getElementById(p + 'BarDone'); if (el) el.style.width = (done / total * 100) + '%';
    el = document.getElementById(p + 'BarOverdue'); if (el) el.style.width = (overdue / total * 100) + '%';
    el = document.getElementById(p + 'BarInWork'); if (el) el.style.width = (inwork / total * 100) + '%';

    panel.querySelectorAll('.status-chip').forEach(function(c) {
        c.classList.toggle('active', c.dataset.status === opts.activeFilter);
    });
}

/* ── initColumnResize — ресайз столбцов таблицы ──────────────────────── */
/**
 * @param {string} tableSelector — CSS-селектор таблицы
 * @param {string} handleSelector — CSS-селектор resize-ручек (default '.col-resize')
 */
function initColumnResize(tableSelector, handleSelector) {
    var table = document.querySelector(tableSelector);
    if (!table) return;
    var handles = table.querySelectorAll(handleSelector || '.col-resize');
    handles.forEach(function(handle) {
        handle.addEventListener('mousedown', function(e) {
            e.preventDefault();
            e.stopPropagation();
            var th = handle.closest('th');
            if (!th) return;
            var startX = e.clientX;
            var startW = th.offsetWidth;
            var ticking = false;

            function onMove(ev) {
                if (ticking) return;
                ticking = true;
                requestAnimationFrame(function() {
                    var newW = Math.max(40, startW + ev.clientX - startX);
                    th.style.width = newW + 'px';
                    th.style.minWidth = newW + 'px';
                    ticking = false;
                });
            }
            function onUp() {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
            }
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    });
}

/* ── Универсальный empty-state HTML ─────────────────────────────────────── */

/**
 * Генерирует HTML пустого состояния.
 * @param {Object} opts
 * @param {string} [opts.icon='fas fa-inbox'] — класс FA-иконки
 * @param {string} [opts.title='Нет данных'] — заголовок
 * @param {string} [opts.desc=''] — описание / подсказка
 * @param {number} [opts.colspan] — если внутри таблицы, сколько колонок
 * @returns {string} HTML
 */
function emptyStateHtml(opts) {
    opts = opts || {};
    var icon  = opts.icon  || 'fas fa-inbox';
    var title = opts.title || 'Нет данных';
    var desc  = opts.desc  || '';
    var action = opts.action || '';   // HTML кнопки-действия
    var inner =
        '<div class="empty-state">' +
          '<div class="empty-state-icon"><i class="' + icon + '"></i></div>' +
          '<div class="empty-state-title">' + title + '</div>' +
          (desc ? '<div class="empty-state-desc">' + desc + '</div>' : '') +
          (action ? '<div class="empty-state-action">' + action + '</div>' : '') +
        '</div>';
    if (opts.colspan) {
        return '<tr><td colspan="' + opts.colspan + '">' + inner + '</td></tr>';
    }
    return inner;
}

/* ── Staggered fade-in ──────────────────────────────────────────────────── */
function initFadeUp(selector) {
    var els = document.querySelectorAll(selector || '.page-content > .section, .page-content > .page-header, .page-content > .filter-bar, .page-content > .data-table-wrap, .page-content > h1, .page-content > .ji-wrap');
    els.forEach(function(el) { el.classList.add('fade-up'); });
}
document.addEventListener('DOMContentLoaded', function() { initFadeUp(); });

/* ── URL filter state persistence ───────────────────────────────────────── */

/**
 * Записывает фильтры в URL query string (без перезагрузки страницы).
 * @param {Object} filters — ключ-значение фильтров (пустые значения удаляются)
 */
function saveFiltersToUrl(filters) {
    var params = new URLSearchParams(window.location.search);
    Object.keys(filters).forEach(function(key) {
        var val = filters[key];
        if (val === '' || val === null || val === undefined || (Array.isArray(val) && val.length === 0)) {
            params.delete(key);
        } else if (Array.isArray(val)) {
            params.set(key, val.join(','));
        } else {
            params.set(key, val);
        }
    });
    var qs = params.toString();
    var newUrl = window.location.pathname + (qs ? '?' + qs : '');
    window.history.replaceState(null, '', newUrl);
}

/**
 * Читает фильтры из URL query string.
 * @param {string[]} keys — список ключей для чтения
 * @returns {Object} — ключ-значение (отсутствующие ключи = '')
 */
function loadFiltersFromUrl(keys) {
    var params = new URLSearchParams(window.location.search);
    var result = {};
    keys.forEach(function(key) {
        result[key] = params.get(key) || '';
    });
    return result;
}

/* ── Employee avatar helper ─────────────────────────────────────────────── */
var _avatarColors = ['#2563eb','#7c3aed','#db2777','#059669','#d97706','#dc2626','#0891b2','#4f46e5','#be123c','#15803d'];
function empAvatarHtml(fullName) {
    if (!fullName) return '';
    var parts = fullName.trim().split(/\s+/);
    var initials = parts.length >= 2 ? (parts[0][0] + parts[1][0]) : parts[0].substring(0,2);
    var hash = 0;
    for (var i = 0; i < fullName.length; i++) hash = ((hash << 5) - hash) + fullName.charCodeAt(i);
    var color = _avatarColors[Math.abs(hash) % _avatarColors.length];
    return '<span class="emp-avatar">' +
           '<span class="emp-avatar-circle" style="background:' + color + '">' + escapeHtml(initials.toUpperCase()) + '</span>' +
           '<span>' + escapeHtml(fullName) + '</span></span>';
}

/* ── Inline field validation ────────────────────────────────────────────── */

/**
 * Инициализирует inline-валидацию для формы.
 * @param {HTMLElement} form — DOM-элемент формы или контейнера
 * @param {Object} rules — {fieldId: {required: bool, minLength: N, pattern: RegExp, message: string}}
 * @returns {Function} validate() — вызвать для проверки всех полей, возвращает true если всё ок
 */
function initInlineValidation(form, rules) {
    Object.keys(rules).forEach(function(fieldId) {
        var input = form.querySelector('#' + fieldId);
        if (!input) return;
        input.addEventListener('blur', function() { _validateField(input, rules[fieldId]); });
        input.addEventListener('input', function() {
            if (input.classList.contains('invalid')) _validateField(input, rules[fieldId]);
        });
    });
    function _validateField(input, rule) {
        var val = input.value.trim();
        var msg = '';
        if (rule.required && !val) msg = rule.message || 'Обязательное поле';
        else if (rule.minLength && val.length < rule.minLength) msg = 'Минимум ' + rule.minLength + ' символов';
        else if (rule.pattern && !rule.pattern.test(val)) msg = rule.message || 'Некорректный формат';
        // Remove old message
        var existing = input.parentElement.querySelector('.field-msg');
        if (existing) existing.remove();
        if (msg) {
            input.classList.add('invalid');
            input.classList.remove('valid');
            var span = document.createElement('span');
            span.className = 'field-msg error';
            span.textContent = msg;
            input.parentElement.appendChild(span);
            return false;
        } else if (val) {
            input.classList.remove('invalid');
            input.classList.add('valid');
        } else {
            input.classList.remove('invalid', 'valid');
        }
        return true;
    }
    return function validate() {
        var allOk = true;
        Object.keys(rules).forEach(function(fieldId) {
            var input = form.querySelector('#' + fieldId);
            if (input && !_validateField(input, rules[fieldId])) allOk = false;
        });
        return allOk;
    };
}

/* ── Keyboard Shortcuts Manager ─────────────────────────────────────────── */

/**
 * Глобальный менеджер горячих клавиш.
 * Позволяет регистрировать/отменять шорткаты из любых страниц.
 *
 * Использование:
 *   registerShortcut('n', 'Добавить запись', function(e) { ... });
 *   registerShortcut('ctrl+k', 'Поиск / Командная палитра', function(e) { ... });
 *   unregisterShortcut('n');
 */

var _shortcuts = {};

function registerShortcut(key, desc, handler) {
    _shortcuts[key.toLowerCase()] = { desc: desc, handler: handler };
}

function unregisterShortcut(key) {
    delete _shortcuts[key.toLowerCase()];
}

function showShortcutsHelp() {
    // Если уже открыт — закрываем
    var existing = document.querySelector('.kb-help-overlay');
    if (existing) { existing.remove(); return; }

    var overlay = document.createElement('div');
    overlay.className = 'kb-help-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:10001;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);';

    var card = document.createElement('div');
    card.style.cssText = 'background:var(--surface);border-radius:16px;padding:32px;max-width:480px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.3);max-height:80vh;overflow-y:auto;';

    // Заголовок
    var header = document.createElement('div');
    header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;';
    header.innerHTML = '<h3 style="font-size:18px;font-weight:700;color:var(--text);margin:0;">Горячие клавиши</h3>';
    var closeBtn = document.createElement('button');
    closeBtn.innerHTML = '&times;';
    closeBtn.style.cssText = 'background:none;border:none;font-size:20px;cursor:pointer;color:var(--muted);';
    closeBtn.onclick = function() { overlay.remove(); };
    header.appendChild(closeBtn);
    card.appendChild(header);

    // Таблица шорткатов
    var table = document.createElement('table');
    table.style.cssText = 'width:100%;border-collapse:collapse;';
    var kbdStyle = 'background:var(--surface2);padding:3px 8px;border-radius:4px;font-size:12px;border:1px solid var(--border);font-family:monospace;';

    // Собираем записи; ? и Esc обрабатываются отдельно — добавляем вручную
    var entries = [{ key: '?', desc: 'Показать эту справку' }];
    var keys = Object.keys(_shortcuts);
    for (var i = 0; i < keys.length; i++) {
        entries.push({ key: keys[i], desc: _shortcuts[keys[i]].desc });
    }
    entries.push({ key: 'Esc', desc: 'Закрыть окно / справку' });

    for (var j = 0; j < entries.length; j++) {
        var item = entries[j];
        var tr = document.createElement('tr');
        var tdKey = document.createElement('td');
        tdKey.style.cssText = 'padding:8px 12px;white-space:nowrap;';
        // Форматируем клавишу: ctrl+k → Ctrl + K
        var keyLabel = item.key.replace(/ctrl\+/i, 'Ctrl + ').replace(/shift\+/i, 'Shift + ');
        keyLabel = keyLabel.charAt(0).toUpperCase() + keyLabel.slice(1);
        var parts = keyLabel.split(' + ');
        var kbdHtml = '';
        for (var p = 0; p < parts.length; p++) {
            if (p > 0) kbdHtml += ' + ';
            kbdHtml += '<kbd style="' + kbdStyle + '">' + parts[p].trim() + '</kbd>';
        }
        tdKey.innerHTML = kbdHtml;

        var tdDesc = document.createElement('td');
        tdDesc.style.cssText = 'padding:8px 12px;color:var(--text);font-size:14px;';
        tdDesc.textContent = item.desc;

        tr.appendChild(tdKey);
        tr.appendChild(tdDesc);
        table.appendChild(tr);
    }

    card.appendChild(table);
    overlay.appendChild(card);

    // Клик по оверлею (фону) закрывает
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) overlay.remove();
    });

    document.body.appendChild(overlay);
}

// ── Глобальный keydown-обработчик ──────────────────────────────────────
document.addEventListener('keydown', function(e) {
    // Esc — закрываем справку, модальные окна, слайдауты
    if (e.key === 'Escape') {
        var help = document.querySelector('.kb-help-overlay');
        if (help) { help.remove(); return; }
        // Командная палитра (command-palette.js закрывает себя сам)
        var palette = document.querySelector('.cmd-palette-overlay');
        if (palette) return;
        // modal-backdrop (modal.js обрабатывает сам)
        var backdrops = document.querySelectorAll('.modal-backdrop');
        if (backdrops.length) return;
        // .modal-overlay.open — закрываем верхнее
        var openModals = document.querySelectorAll('.modal-overlay.open');
        if (openModals.length) {
            openModals[openModals.length - 1].classList.remove('open');
            e.preventDefault();
            return;
        }
        // Слайдауты и другие панели
        var slideout = document.querySelector('.slideout.open, .panel-overlay.open');
        if (slideout) { slideout.classList.remove('open'); e.preventDefault(); return; }
        return;
    }

    // Не срабатываем в полях ввода
    if (['INPUT', 'TEXTAREA', 'SELECT'].indexOf(e.target.tagName) >= 0) return;
    if (e.target.isContentEditable) return;

    // ? — показ справки (обрабатываем до lookup в _shortcuts)
    if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        showShortcutsHelp();
        e.preventDefault();
        return;
    }

    // Строим строку-ключ шортката
    var key = '';
    if (e.ctrlKey || e.metaKey) key += 'ctrl+';
    if (e.shiftKey && e.key !== '?') key += 'shift+';
    key += e.key.toLowerCase();

    var shortcut = _shortcuts[key];
    if (shortcut) {
        e.preventDefault();
        shortcut.handler(e);
    }
});

// ── Стандартные шорткаты ──────────────────────────────────────────────

registerShortcut('ctrl+k', 'Поиск / Командная палитра', function() {
    // command-palette.js уже слушает Ctrl+K — дублирующий вызов безвреден
});

registerShortcut('/', 'Фокус на поиск', function() {
    var search = document.querySelector('.search-input, .searchbar input, input[type="search"], #searchInput, .filter-bar input[type="text"]');
    if (search) search.focus();
});

registerShortcut('n', 'Добавить запись', function() {
    var addBtn = document.querySelector('.topbar .btn-primary, .page-header .btn-primary');
    if (addBtn) addBtn.click();
});

registerShortcut('d', 'Удалить выбранное', function() {
    var delBtn = document.querySelector('.btn-delete.active, .toolbar .btn-danger, button[data-action="delete"]');
    if (delBtn) delBtn.click();
});

registerShortcut('e', 'Редактировать выбранное', function() {
    var editBtn = document.querySelector('.btn-edit.active, .toolbar .btn-edit, button[data-action="edit"]');
    if (editBtn) editBtn.click();
});

/* ── Breadcrumbs — динамическое обновление хлебных крошек ──────────────────── */

/**
 * updateBreadcrumbs(items)
 * Перестраивает навигационные хлебные крошки.
 * @param {Array<{label:string, url?:string, icon?:string}>} items
 *   Первый элемент — обычно «Главная» с url:'/'.
 *   Последний элемент без url — текущая страница (не ссылка).
 *   icon (необяз.) — класс Font Awesome, например 'fas fa-home'.
 *
 * Пример:
 *   updateBreadcrumbs([
 *     {label:'Главная', url:'/', icon:'fas fa-home'},
 *     {label:'Производственный план', url:'/works/production-plan/'},
 *     {label:'Проект Альфа'}
 *   ]);
 */
function updateBreadcrumbs(items) {
    var nav = document.querySelector('.breadcrumb[aria-label="Хлебные крошки"]');
    if (!nav) return;

    // Сохраняем кнопки sidebar-toggle / mobile-toggle — они вне nav
    // Очищаем только содержимое <nav class="breadcrumb">
    nav.innerHTML = '';

    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var isLast = (i === items.length - 1);

        // Разделитель «/» между элементами (кроме первого)
        if (i > 0) {
            var sep = document.createElement('span');
            sep.className = 'breadcrumb-sep';
            sep.setAttribute('aria-hidden', 'true');
            sep.textContent = '/';
            nav.appendChild(sep);
        }

        if (isLast || !item.url) {
            // Текущая страница — не ссылка
            var span = document.createElement('span');
            span.className = 'breadcrumb-current';
            span.id = 'breadcrumbTitle';
            if (item.icon) {
                var ic = document.createElement('i');
                ic.className = item.icon;
                ic.setAttribute('aria-hidden', 'true');
                ic.style.marginRight = '5px';
                span.appendChild(ic);
            }
            span.appendChild(document.createTextNode(item.label));
            nav.appendChild(span);
        } else {
            // Промежуточная ссылка
            var a = document.createElement('a');
            a.href = item.url;
            if (item.icon) {
                var ic2 = document.createElement('i');
                ic2.className = item.icon;
                ic2.setAttribute('aria-hidden', 'true');
                ic2.style.marginRight = '4px';
                a.appendChild(ic2);
            }
            a.appendChild(document.createTextNode(item.label));
            // Для SPA-переходов: если есть onclick, не перезагружаем страницу
            if (item.onclick) {
                a.href = '#';
                a.addEventListener('click', (function(fn) {
                    return function(e) { e.preventDefault(); fn(); };
                })(item.onclick));
            }
            nav.appendChild(a);
        }
    }
}

/**
 * resetBreadcrumbs(pageLabel)
 * Сбрасывает хлебные крошки к начальному состоянию «Главная / pageLabel».
 */
function resetBreadcrumbs(pageLabel) {
    updateBreadcrumbs([
        {label: 'Главная', url: '/'},
        {label: pageLabel}
    ]);
}

(function() {
    var NAV_URLS = [
        '/works/projects/',
        '/works/production-plan/',
        '/works/plan/',
        '/works/notices/',
        '/works/analytics/',
        '/works/work-calendar/',
        '/employees/'
    ];
    for (var i = 0; i < NAV_URLS.length; i++) {
        (function(idx) {
            registerShortcut(String(idx + 1), 'Перейти к разделу ' + (idx + 1), function() {
                window.location.href = NAV_URLS[idx];
            });
        })(i);
    }
})();
