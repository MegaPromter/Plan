/**
 * Универсальная система модальных окон.
 * Аналог модалок из Flask plan.html.
 * Стили — в components.css (секция «JS-модалки»).
 */

/* ── Создание модалки ────────────────────────────────────────────────────── */

function openModal(options = {}) {
    const {
        title = '',
        body = '',
        width = '600px',
        onClose = null,
        id = 'modal-' + Date.now(),
        footer = '',
        bodyElement = null,
    } = options;

    // Backdrop
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.id = id;

    // Dialog
    const dialog = document.createElement('div');
    dialog.className = 'modal-dialog';
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    if (title) dialog.setAttribute('aria-label', title);
    dialog.style.width = width;

    // Header
    const header = document.createElement('div');
    header.className = 'modal-header';
    header.innerHTML = `
        <h3 class="modal-title"></h3>
        <button class="modal-close-btn" title="Закрыть">&times;</button>
    `;
    header.querySelector('h3').textContent = title;

    // Body
    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'modal-body';
    if (bodyElement) {
        bodyDiv.appendChild(bodyElement);
    } else {
        bodyDiv.innerHTML = body;
    }

    dialog.appendChild(header);
    dialog.appendChild(bodyDiv);

    // Footer
    if (footer) {
        const footerDiv = document.createElement('div');
        footerDiv.className = 'modal-footer';
        footerDiv.innerHTML = footer;
        dialog.appendChild(footerDiv);
    }

    // A11y: dialog role
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    if (title) {
        const titleEl = header.querySelector('h3');
        const titleId = id + '-title';
        titleEl.id = titleId;
        dialog.setAttribute('aria-labelledby', titleId);
    }

    backdrop.appendChild(dialog);
    document.body.appendChild(backdrop);

    // Блокируем прокрутку страницы за модалкой
    document.body.style.overflow = 'hidden';

    // A11y: сохраняем элемент, с которого открыли, для восстановления фокуса
    const previousFocus = document.activeElement;

    // A11y: focus trap — фокус циклически внутри модалки
    function trapFocus(e) {
        if (e.key !== 'Tab') return;
        const focusable = dialog.querySelectorAll(
            'button, [href], input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (!focusable.length) return;
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault(); last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault(); first.focus();
        }
    }
    dialog.addEventListener('keydown', trapFocus);

    // A11y: авто-фокус на первый input или на кнопку закрытия
    requestAnimationFrame(() => {
        const firstInput = dialog.querySelector('input:not([type="hidden"]), select, textarea');
        if (firstInput) { firstInput.focus(); } else {
            const closeBtn = header.querySelector('.modal-close-btn');
            if (closeBtn) closeBtn.focus();
        }
    });

    // Закрытие
    let closed = false;
    const close = () => {
        if (closed) return;
        closed = true;
        document.removeEventListener('keydown', onKey);
        dialog.removeEventListener('keydown', trapFocus);
        backdrop.style.animation = 'modalFadeOut 0.15s ease-in forwards';
        setTimeout(() => {
            backdrop.remove();
            // Восстанавливаем прокрутку если все модалки закрыты
            if (!document.querySelector('.modal-backdrop')) {
                document.body.style.overflow = '';
            }
            // A11y: возвращаем фокус на элемент-инициатор
            if (previousFocus && previousFocus.focus) {
                previousFocus.focus();
            }
            if (onClose) onClose();
        }, 150);
    };

    header.querySelector('.modal-close-btn').addEventListener('click', close);
    let _backdropDownTarget = null;
    backdrop.addEventListener('mousedown', (e) => { _backdropDownTarget = e.target; });
    backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop && _backdropDownTarget === backdrop) close();
    });
    // Кнопки с классом modal-cancel тоже закрывают модалку
    dialog.querySelectorAll('.modal-cancel').forEach(btn => {
        btn.addEventListener('click', close);
    });

    // ESC закрывает; Enter кликает первую .btn-primary в футере
    function onKey(e) {
        if (e.key === 'Escape' && !options.noEsc) {
            e.preventDefault();
            close();
        } else if (e.key === 'Enter' && !options.noEnter) {
            // Не срабатываем если фокус на textarea или select
            const tag = document.activeElement ? document.activeElement.tagName : '';
            if (tag === 'TEXTAREA' || tag === 'SELECT') return;
            const primaryBtn = dialog.querySelector('.modal-footer .btn-primary');
            if (primaryBtn && !primaryBtn.disabled) {
                e.preventDefault();
                primaryBtn.click();
            }
        }
    }
    document.addEventListener('keydown', onKey);

    return { backdrop, dialog, bodyDiv, close, id };
}

function closeModal(idOrEl) {
    let el;
    if (typeof idOrEl === 'string') {
        el = document.getElementById(idOrEl);
    } else {
        el = idOrEl;
    }
    if (!el) return;

    // Шаблонные модалы (.modal-overlay) — убираем класс .open
    if (el.classList.contains('modal-overlay')) {
        el.classList.remove('open');
        return;
    }

    // JS-модалы (.modal-backdrop из openModal) — удаляем с анимацией
    el.style.animation = 'modalFadeOut 0.15s ease-in forwards';
    setTimeout(() => {
        el.remove();
        if (!document.querySelector('.modal-backdrop')) {
            document.body.style.overflow = '';
        }
    }, 150);
}

function closeAllModals() {
    document.querySelectorAll('.modal-backdrop').forEach(el => {
        el.style.animation = 'modalFadeOut 0.15s ease-in forwards';
        setTimeout(() => el.remove(), 150);
    });
    setTimeout(() => { document.body.style.overflow = ''; }, 150);
}

/* ── Шаблонные модалы (.modal-overlay): единый ESC и клик по фону ────────── */

// Клик по фону — закрываем если клик именно на оверлей, не на содержимое (.modal)
// Защита от закрытия при выделении текста (mousedown внутри → drag → mouseup снаружи)
var _tplModalDownTarget = null;
document.addEventListener('mousedown', function(e) { _tplModalDownTarget = e.target; });
document.addEventListener('click', function(e) {
    if (!e.target.classList.contains('modal-overlay')) return;
    if (!e.target.classList.contains('open')) return;
    if (_tplModalDownTarget !== e.target) return;
    // Используем реестр кастомных close-функций (если зарегистрирована)
    if (typeof _callModalClose === 'function') _callModalClose(e.target);
    else e.target.classList.remove('open');
});

/* ── Confirm-диалог ──────────────────────────────────────────────────────── */

function confirmDialog(message, title = 'Подтверждение') {
    return new Promise((resolve) => {
        let resolved = false;

        function onKey(e) {
            if (e.key === 'Enter')  { e.preventDefault(); done(true);  }
            if (e.key === 'Escape') { e.preventDefault(); done(false); }
        }

        function done(result) {
            if (resolved) return;
            resolved = true;
            document.removeEventListener('keydown', onKey);
            modal.close();
            resolve(result);
        }

        const msgEl = document.createElement('p');
        msgEl.className = 'confirm-message';
        msgEl.textContent = message;

        const modal = openModal({
            title,
            bodyElement: msgEl,
            width: '400px',
            footer: `
                <button class="btn btn-outline modal-cancel">Отмена</button>
                <button class="btn btn-primary modal-confirm">Подтвердить</button>
            `,
            onClose: () => done(false),
            noEsc: true,   // Escape обрабатываем сами через onKey
            noEnter: true, // Enter обрабатываем сами через onKey
        });

        modal.dialog.querySelector('.modal-cancel').addEventListener('click', () => done(false));
        modal.dialog.querySelector('.modal-confirm').addEventListener('click', () => done(true));

        // Enter → подтвердить, Escape → отмена
        document.addEventListener('keydown', onKey);
        // Фокус на кнопку "Подтвердить" чтобы Enter сработал сразу
        modal.dialog.querySelector('.modal-confirm').focus();
    });
}
