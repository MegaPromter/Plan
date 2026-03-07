/* ── Интерактивное обучение — Tour/Onboarding ──────────────────────────
 * Автоматически запускается при первом входе пользователя.
 * Может быть перезапущен вручную через кнопку «Обучение» на dashboard.
 * Прогресс сохраняется в localStorage (ключ 'tour_seen').
 * ──────────────────────────────────────────────────────────────────── */

(function() {
  'use strict';

  /* ── Tour steps ─────────────────────────────────────────────────────── */
  const TOUR_STEPS = [
    {
      selector: '.welcome-section',
      title: 'Добро пожаловать!',
      desc: 'Это ваша главная страница. Здесь вы видите приветствие и можете управлять пользователями (если вы админ).'
    },
    {
      selector: '.modules-grid',
      title: 'Модули системы',
      desc: 'Быстрый доступ ко всем разделам: план/отчёт, производственный план, отпуска, журнал извещений.'
    },
    {
      selector: '.sidebar',
      title: 'Навигация',
      desc: 'Боковое меню для перехода между разделами. Вы можете свернуть/развернуть его кнопкой в верхней панели.'
    },
    {
      selector: '.topbar',
      title: 'Панель управления',
      desc: 'Здесь находится хлебные крошки навигации и быстрые действия.'
    },
    {
      selector: '.kpi-grid',
      title: 'Сводная информация',
      desc: 'Карточки с основными показателями: количество задач, строк ПП, сотрудников и извещений.'
    }
  ];

  let currentStep = 0;
  let highlightEl = null;
  let tooltipEl = null;

  /* ── Welcome modal ─────────────────────────────────────────────────── */
  function showWelcomeModal() {
    const modal = document.createElement('div');
    modal.id = 'tourModal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.8);z-index:99999;display:flex;align-items:center;justify-content:center;cursor:pointer;';
    modal.innerHTML =
      '<div id="tourModalCard" style="background:#1e293b;border:2px solid #3b82f6;border-radius:16px;padding:40px;max-width:500px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,0.5);cursor:default;">' +
        '<div style="font-size:64px;margin-bottom:20px;">🎓</div>' +
        '<h2 style="color:#fff;margin:0 0 16px 0;font-size:24px;">Добро пожаловать в систему!</h2>' +
        '<p style="color:#94a3b8;margin:0 0 24px 0;line-height:1.6;">Пройдите короткое обучение, чтобы узнать все возможности системы планирования.</p>' +
        '<div style="display:flex;gap:12px;justify-content:center;">' +
          '<button id="tourStartBtn" style="background:#3b82f6;color:#fff;border:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;">Начать обучение</button>' +
          '<button id="tourSkipBtn" style="background:transparent;color:#64748b;border:1px solid #475569;padding:12px 24px;border-radius:8px;font-size:14px;cursor:pointer;">Пропустить</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(modal);

    function closeModal() {
      const m = document.getElementById('tourModal');
      if (m) m.remove();
      localStorage.setItem('tour_seen', '1');
    }

    modal.addEventListener('click', function(e) {
      if (!document.getElementById('tourModalCard').contains(e.target)) closeModal();
    });

    function escHandler(e) {
      if (e.key === 'Escape') { closeModal(); document.removeEventListener('keydown', escHandler); }
    }
    document.addEventListener('keydown', escHandler);

    document.getElementById('tourStartBtn').onclick = function() {
      closeModal();
      startSteps();
    };
    document.getElementById('tourSkipBtn').onclick = closeModal;
  }

  /* ── Step navigation ───────────────────────────────────────────────── */
  function startSteps() {
    currentStep = 0;
    // cleanup old
    cleanup();

    highlightEl = document.createElement('div');
    highlightEl.id = 'tourHighlight';
    highlightEl.style.cssText = 'position:absolute;border:3px solid #3b82f6;border-radius:8px;box-shadow:0 0 0 9999px rgba(0,0,0,0.7);z-index:99998;transition:all 0.3s;pointer-events:none;';
    document.body.appendChild(highlightEl);

    showStep(0);
  }

  function showStep(idx) {
    if (idx < 0) idx = 0;
    if (idx >= TOUR_STEPS.length) { endTour(); return; }
    currentStep = idx;

    const step = TOUR_STEPS[idx];
    const el = document.querySelector(step.selector);
    if (!el) { showStep(idx + 1); return; }

    const rect = el.getBoundingClientRect();
    const scrollY = window.scrollY || window.pageYOffset;
    const scrollX = window.scrollX || window.pageXOffset;

    highlightEl.style.top    = (rect.top  + scrollY - 10) + 'px';
    highlightEl.style.left   = (rect.left + scrollX - 10) + 'px';
    highlightEl.style.width  = (rect.width  + 20) + 'px';
    highlightEl.style.height = (rect.height + 20) + 'px';

    // Remove old tooltip
    removeTooltip();

    tooltipEl = document.createElement('div');
    tooltipEl.className = 'tour-nav';
    tooltipEl.style.cssText = 'position:fixed;bottom:40px;left:50%;transform:translateX(-50%);background:#1e293b;border:2px solid #3b82f6;border-radius:12px;padding:20px;max-width:420px;z-index:99999;box-shadow:0 10px 40px rgba(0,0,0,0.5);';
    tooltipEl.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">' +
        '<h3 style="color:#fff;margin:0;font-size:16px;">' + step.title + '</h3>' +
        '<span style="color:#64748b;font-size:12px;">' + (idx+1) + ' / ' + TOUR_STEPS.length + '</span>' +
      '</div>' +
      '<p style="color:#94a3b8;margin:0 0 16px 0;font-size:14px;line-height:1.5;">' + step.desc + '</p>' +
      '<div style="display:flex;justify-content:space-between;gap:10px;">' +
        '<button id="tourPrev" style="background:transparent;border:1px solid #475569;color:#94a3b8;padding:8px 16px;border-radius:6px;cursor:pointer;' + (idx === 0 ? 'visibility:hidden' : '') + '">← Назад</button>' +
        '<button id="tourEnd" style="background:#475569;border:none;color:#fff;padding:8px 16px;border-radius:6px;cursor:pointer;">Пропустить</button>' +
        '<button id="tourNext" style="background:#3b82f6;border:none;color:#fff;padding:8px 20px;border-radius:6px;cursor:pointer;font-weight:600;">' + (idx === TOUR_STEPS.length - 1 ? 'Готово ✓' : 'Далее →') + '</button>' +
      '</div>';
    document.body.appendChild(tooltipEl);

    document.getElementById('tourPrev').onclick = function() { showStep(currentStep - 1); };
    document.getElementById('tourNext').onclick = function() { showStep(currentStep + 1); };
    document.getElementById('tourEnd').onclick = function() { endTour(); };
  }

  function endTour() {
    cleanup();
    localStorage.setItem('tour_seen', '1');

    // Completion modal
    const modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.8);z-index:99999;display:flex;align-items:center;justify-content:center;';
    modal.innerHTML =
      '<div style="background:#1e293b;border:2px solid #3b82f6;border-radius:16px;padding:40px;max-width:450px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,0.5);">' +
        '<div style="font-size:48px;margin-bottom:20px;">🎉</div>' +
        '<h2 style="color:#fff;margin:0 0 12px 0;font-size:22px;">Обучение завершено!</h2>' +
        '<p style="color:#94a3b8;margin:0 0 24px 0;line-height:1.5;">Теперь вы знаете основы работы с системой. Удачной работы!</p>' +
        '<button id="tourDoneBtn" style="background:#3b82f6;color:#fff;border:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;">Начать работу</button>' +
      '</div>';
    document.body.appendChild(modal);
    document.getElementById('tourDoneBtn').onclick = function() { modal.remove(); };
    modal.addEventListener('click', function(e) {
      if (e.target === modal) modal.remove();
    });
  }

  function removeTooltip() {
    document.querySelectorAll('.tour-nav').forEach(function(el) { el.remove(); });
    tooltipEl = null;
  }

  function cleanup() {
    if (highlightEl) { highlightEl.remove(); highlightEl = null; }
    removeTooltip();
  }

  /* ── Public API ────────────────────────────────────────────────────── */
  window.startTourDemo = function() {
    showWelcomeModal();
  };

  window.restartTour = function() {
    localStorage.removeItem('tour_seen');
    showWelcomeModal();
  };

  /* ── Auto-init ─────────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function() {
    if (!localStorage.getItem('tour_seen')) {
      setTimeout(window.startTourDemo, 1500);
    }
  });

})();
