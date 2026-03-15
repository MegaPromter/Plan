/**
 * Универсальная система модальных окон.
 * Аналог модалок из Flask plan.html.
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
    backdrop.style.cssText = `
        position: fixed; inset: 0; z-index: 9000;
        background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
        display: flex; align-items: center; justify-content: center;
        animation: modalFadeIn 0.2s ease-out;
        overflow-y: auto;
    `;

    // Dialog
    const dialog = document.createElement('div');
    dialog.className = 'modal-dialog';
    dialog.style.cssText = `
        background: var(--surface, #ffffff); border: 1px solid var(--border, #e2e6ed);
        border-radius: 12px; width: ${width}; max-width: 95vw;
        box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        animation: modalSlideIn 0.2s ease-out;
        margin-bottom: 40px;
    `;

    // Header
    const header = document.createElement('div');
    header.style.cssText = `
        display: flex; align-items: center; justify-content: space-between;
        padding: 16px 20px; border-bottom: 1px solid var(--border, #e2e6ed);
    `;
    header.innerHTML = `
        <h3 style="margin:0;font-size:16px;font-weight:600;color:var(--text,#1e293b);"></h3>
        <button class="modal-close-btn" style="
            background:none;border:none;color:var(--muted,#64748b);
            font-size:20px;cursor:pointer;padding:4px 8px;
            border-radius:4px;transition:all 0.15s;
        " title="Закрыть">&times;</button>
    `;
    header.querySelector('h3').textContent = title;

    // Body
    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'modal-body';
    bodyDiv.style.cssText = 'padding: 20px; max-height: 70vh; overflow-y: auto;';
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
        footerDiv.style.cssText = `
            padding: 12px 20px; border-top: 1px solid var(--border, #e2e6ed);
            display: flex; justify-content: flex-end; gap: 8px;
        `;
        footerDiv.innerHTML = footer;
        dialog.appendChild(footerDiv);
    }

    backdrop.appendChild(dialog);
    document.body.appendChild(backdrop);

    // Блокируем прокрутку страницы за модалкой
    document.body.style.overflow = 'hidden';

    // Закрытие
    let closed = false;
    const close = () => {
        if (closed) return;
        closed = true;
        document.removeEventListener('keydown', onKey);
        backdrop.style.animation = 'modalFadeOut 0.15s ease-in forwards';
        setTimeout(() => {
            backdrop.remove();
            // Восстанавливаем прокрутку если все модалки закрыты
            if (!document.querySelector('.modal-backdrop')) {
                document.body.style.overflow = '';
            }
            if (onClose) onClose();
        }, 150);
    };

    header.querySelector('.modal-close-btn').addEventListener('click', close);
    backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) close();
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
    if (el) {
        el.style.animation = 'modalFadeOut 0.15s ease-in forwards';
        setTimeout(() => {
            el.remove();
            if (!document.querySelector('.modal-backdrop')) {
                document.body.style.overflow = '';
            }
        }, 150);
    }
}

function closeAllModals() {
    document.querySelectorAll('.modal-backdrop').forEach(el => {
        el.style.animation = 'modalFadeOut 0.15s ease-in forwards';
        setTimeout(() => el.remove(), 150);
    });
    setTimeout(() => { document.body.style.overflow = ''; }, 150);
}

/* ── CSS-анимации для модалок ──────────────────────────────────────────── */

(function() {
    if (document.getElementById('modal-animations')) return;
    const style = document.createElement('style');
    style.id = 'modal-animations';
    style.textContent = `
        @keyframes modalFadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes modalFadeOut { from { opacity: 1; } to { opacity: 0; } }
        @keyframes modalSlideIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        .modal-close-btn:hover { background: var(--surface2, #f8f9fb) !important; color: var(--text, #1e293b) !important; }
    `;
    document.head.appendChild(style);
})();

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
        msgEl.style.cssText = 'color:var(--text,#1e293b);margin:0;';
        msgEl.textContent = message;

        const modal = openModal({
            title,
            bodyElement: msgEl,
            width: '400px',
            footer: `
                <button class="btn btn-outline modal-cancel" style="
                    padding:7px 16px;border-radius:6px;font-size:14px;cursor:pointer;
                    background:transparent;color:var(--text,#1e293b);
                    border:1px solid var(--border2,#c8d0dc);font-family:inherit;
                    transition:all 0.15s;
                ">Отмена</button>
                <button class="btn btn-primary modal-confirm" style="
                    padding:7px 16px;border-radius:6px;font-size:14px;cursor:pointer;
                    background:var(--accent,#3b82f6);color:#fff;border:none;
                    font-family:inherit;font-weight:500;transition:all 0.15s;
                ">Подтвердить</button>
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
