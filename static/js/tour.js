/* ── Интерактивное обучение — Tour/Onboarding (12 шагов) ──────────────────
 * Межстраничный тур: автоматический переход на нужную страницу,
 * подсветка элементов с пульсацией на каждом шаге.
 * Прогресс: localStorage + сервер (/api/col_settings/).
 * ──────────────────────────────────────────────────────────────────────── */

(function() {
  'use strict';

  /* ═══════════════════════════════════════════════════════════════════════
     1. TOUR_STEPS — 12 шагов (у каждого есть selector для spotlight)
     ═══════════════════════════════════════════════════════════════════════ */
  var STEPS = [
    {
      id: 'create_project', stepNum: 1,
      page: '/works/projects/',
      selector: '.btn-primary',
      title: 'Создание проекта (УП)',
      icon: 'fa-folder-plus',
      desc: 'Здесь администратор создаёт новый проект. Проект объединяет все работы, производственные планы и задачи.',
      descNonAdmin: 'Администратор создаёт проекты на этой странице. Проект объединяет все работы, планы и задачи.',
      adminOnly: true
    },
    {
      id: 'create_pp', stepNum: 2,
      page: '/works/production-plan/',
      selector: '#landingActions .btn-primary',
      title: 'Создание производственного плана',
      icon: 'fa-file-circle-plus',
      desc: 'Кнопка создания нового производственного плана (ПП). ПП содержит список работ с трудоёмкостью, сроками и исполнителями.',
      descNonAdmin: 'Администратор создаёт производственные планы здесь. ПП содержит список работ с трудоёмкостью и сроками.',
      adminOnly: true
    },
    {
      id: 'add_pp_row', stepNum: 3,
      page: '/works/production-plan/',
      selector: '#projectActions .btn-primary',
      title: 'Добавление строк в ПП',
      icon: 'fa-table-rows',
      desc: 'Внутри открытого ПП кнопка «Добавить строку» создаёт новую работу. Каждая строка — это работа с этапом, вехой, шифром и трудоёмкостью.'
    },
    {
      id: 'dependencies', stepNum: 4,
      page: '/works/plan/',
      selector: 'tr[data-id] .btn-deps',
      title: 'Зависимости между работами',
      icon: 'fa-link',
      desc: 'Кнопка \uD83D\uDD17 показывает зависимости между работами (FS/SS/FF/SF). Зависимости позволяют выстраивать последовательность и автоматически выравнивать сроки.'
    },
    {
      id: 'sync_to_sp', stepNum: 5,
      page: '/works/production-plan/',
      selector: '#projectActions .btn-secondary',
      title: 'Синхронизация ПП \u2192 СП',
      icon: 'fa-arrows-rotate',
      desc: 'Кнопка «Синхронизировать с СП» переносит работы из производственного плана в сводный план (план/отчёт). После синхронизации задачи появляются в СП с пометкой «из ПП».'
    },
    {
      id: 'edit_task', stepNum: 6,
      page: '/works/plan/',
      selector: 'tr[data-id] .btn-edit-row',
      title: 'Редактирование задачи в СП',
      icon: 'fa-pen-to-square',
      desc: 'Кнопка \u270F\uFE0F открывает модальное окно редактирования задачи. Здесь можно изменить сроки, исполнителей, плановые часы по месяцам и другие параметры.'
    },
    {
      id: 'report', stepNum: 7,
      page: '/works/plan/',
      selector: 'tr[data-id] .btn-report',
      title: 'Отчёт по задаче',
      icon: 'fa-chart-bar',
      desc: 'Кнопка отчёта позволяет внести фактические данные о выполнении работы: процент готовности, фактические часы, примечания.'
    },
    {
      id: 'errors_btn', stepNum: 8,
      page: '/works/plan/',
      selector: '#errorsBtn',
      title: 'Ошибки планирования',
      icon: 'fa-triangle-exclamation',
      desc: 'Кнопка «Ошибки планирования» показывает несоответствия: задачи без исполнителей, пересечение сроков с отпусками, превышение норм часов и другие проблемы.'
    },
    {
      id: 'work_calendar', stepNum: 9,
      page: '/works/work-calendar/',
      selector: '.cal-summary-table, table',
      title: 'Производственный календарь',
      icon: 'fa-calendar-days',
      desc: 'Производственный календарь задаёт норму рабочих часов по месяцам. Используется для расчёта загрузки и проверки планов.',
      adminOnly: true,
      descNonAdmin: 'Производственный календарь задаёт норму рабочих часов по месяцам. Доступен администраторам.'
    },
    {
      id: 'notices', stepNum: 10,
      page: '/works/notices/',
      selector: '.ji-table, table',
      title: 'Журнал извещений (ЖИ)',
      icon: 'fa-bell',
      desc: 'Журнал извещений фиксирует изменения в документации. Извещения создаются автоматически при корректировке или вручную. Здесь отслеживается статус и погашение.'
    },
    {
      id: 'roles', stepNum: 11,
      page: null,
      selector: null,
      title: 'Роли и права доступа',
      icon: 'fa-users-gear',
      desc: 'В системе 7 ролей: <b>Администратор</b>, <b>Нач. НТЦ</b>, <b>Зам. НТЦ</b>, <b>Нач. отдела</b>, <b>Зам. отдела</b>, <b>Нач. сектора</b>, <b>Пользователь</b>. Каждая роль определяет видимость данных и доступные действия.',
      infoOnly: true
    },
    {
      id: 'export', stepNum: 12,
      page: '/works/plan/',
      selector: '#exportBtnContainer',
      title: 'Экспорт данных',
      icon: 'fa-file-export',
      desc: 'Кнопка экспорта позволяет выгрузить данные таблицы в Excel. Экспортируются только видимые (отфильтрованные) строки с учётом текущих фильтров.'
    }
  ];

  var TOTAL = STEPS.length;
  var LS_KEY = 'tour_state';
  var currentIdx = -1;

  /* ═══════════════════════════════════════════════════════════════════════
     2. Определение роли
     ═══════════════════════════════════════════════════════════════════════ */
  function isAdmin() {
    return document.body.getAttribute('data-is-admin') === '1';
  }

  /* ═══════════════════════════════════════════════════════════════════════
     3. Состояние тура (localStorage + сервер)
     ═══════════════════════════════════════════════════════════════════════ */
  function getState() {
    try {
      var raw = localStorage.getItem(LS_KEY);
      if (raw) return JSON.parse(raw);
    } catch(e) {}
    return null;
  }

  function setState(obj) {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(obj));
    } catch(e) {}
  }

  function syncToServer(state) {
    try {
      var csrfVal = '';
      var csrfEl = document.querySelector('[name=csrfmiddlewaretoken]');
      if (csrfEl) {
        csrfVal = csrfEl.value;
      } else {
        var cookieMatch = document.cookie.match(/csrftoken=([^;]+)/);
        if (cookieMatch) csrfVal = cookieMatch[1];
      }
      var xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/col_settings/', true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.setRequestHeader('X-CSRFToken', csrfVal);
      xhr.send(JSON.stringify({
        _tour_step: state.step,
        _tour_completed: state.completed ? 1 : 0
      }));
    } catch(e) {}
  }

  function migrateOldState() {
    // Старый tour_seen → удалить, показать новый тур заново
    if (localStorage.getItem('tour_seen')) {
      localStorage.removeItem('tour_seen');
      localStorage.removeItem(LS_KEY);
      return null;
    }
    return null;
  }

  /* ═══════════════════════════════════════════════════════════════════════
     4. DOM-утилиты
     ═══════════════════════════════════════════════════════════════════════ */
  function clearTourUI() {
    var ids = ['tourSpotlight', 'tourTooltip', 'tourInfoBackdrop', 'tourModalBackdrop'];
    ids.forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.remove();
    });
    document.removeEventListener('keydown', keyHandler);
  }

  function currentPage() {
    return window.location.pathname;
  }

  function matchPage(stepPage) {
    if (!stepPage) return true;
    var cur = currentPage().replace(/\/+$/, '');
    var sp = stepPage.replace(/\/+$/, '');
    return cur === sp;
  }

  function findEl(step) {
    if (!step.selector) return null;
    var sels = step.selector.split(',');
    for (var i = 0; i < sels.length; i++) {
      var el = document.querySelector(sels[i].trim());
      if (el) return el;
    }
    return null;
  }

  /* ═══════════════════════════════════════════════════════════════════════
     5. Навигация между шагами — с авто-переходом на нужную страницу
     ═══════════════════════════════════════════════════════════════════════ */
  function goStep(idx) {
    if (idx < 0) idx = 0;
    if (idx >= TOTAL) { completeTour(); return; }
    currentIdx = idx;
    var step = STEPS[idx];
    setState({ step: idx, completed: false, version: 2 });
    clearTourUI();

    // Если шаг привязан к странице и мы на другой — делаем переход
    if (step.page && !matchPage(step.page)) {
      window.location.href = step.page;
      return; // после загрузки auto-init подхватит
    }

    showStep(idx);
  }

  function goNext() { goStep(currentIdx + 1); }
  function goPrev() { goStep(currentIdx - 1); }

  function skipTour() {
    var s = { step: currentIdx, completed: true, skipped: true, version: 2 };
    setState(s);
    syncToServer(s);
    clearTourUI();
  }

  function completeTour() {
    var s = { step: TOTAL, completed: true, version: 2 };
    setState(s);
    syncToServer(s);
    clearTourUI();
    showCompletionModal();
  }

  /* ═══════════════════════════════════════════════════════════════════════
     6. Клавиатура
     ═══════════════════════════════════════════════════════════════════════ */
  function keyHandler(e) {
    if (e.key === 'Escape') { skipTour(); }
    else if (e.key === 'ArrowRight') { goNext(); }
    else if (e.key === 'ArrowLeft') { goPrev(); }
  }

  /* ═══════════════════════════════════════════════════════════════════════
     7. Построение UI — кнопки навигации
     ═══════════════════════════════════════════════════════════════════════ */
  function buildNavButtons(idx) {
    var prevBtn = idx > 0
      ? '<button class="tour-btn tour-btn-prev" id="tourPrev">\u2190 \u041D\u0430\u0437\u0430\u0434</button>'
      : '<span></span>';
    var skipBtn = '<button class="tour-btn tour-btn-skip" id="tourSkip">\u041F\u0440\u043E\u043F\u0443\u0441\u0442\u0438\u0442\u044C</button>';
    var nextLabel = idx === TOTAL - 1 ? '\u0413\u043E\u0442\u043E\u0432\u043E \u2713' : '\u0414\u0430\u043B\u0435\u0435 \u2192';
    var nextBtn = '<button class="tour-btn tour-btn-next" id="tourNext">' + nextLabel + '</button>';
    return prevBtn + skipBtn + nextBtn;
  }

  function buildProgress(idx) {
    var pct = ((idx + 1) / TOTAL * 100).toFixed(0);
    return '<div class="tour-progress"><div class="tour-progress-bar" style="width:' + pct + '%"></div></div>';
  }

  function bindNavEvents() {
    var prev = document.getElementById('tourPrev');
    var next = document.getElementById('tourNext');
    var skip = document.getElementById('tourSkip');
    if (prev) prev.onclick = goPrev;
    if (next) next.onclick = goNext;
    if (skip) skip.onclick = skipTour;
    document.addEventListener('keydown', keyHandler);
  }

  /* ═══════════════════════════════════════════════════════════════════════
     8. showStep — главная функция отображения шага
     ═══════════════════════════════════════════════════════════════════════ */
  function showStep(idx) {
    var step = STEPS[idx];

    // Определяем текст описания
    var desc = step.desc;
    var adminNote = '';
    if (step.adminOnly && !isAdmin()) {
      desc = step.descNonAdmin || step.desc;
      adminNote = '<div class="tour-admin-note"><i class="fas fa-lock"></i> Этот шаг выполняет администратор</div>';
    }

    // Шаг без привязки к странице и без селектора → info-card
    if (step.infoOnly && !step.selector) {
      showInfoCard(step, idx, desc, adminNote);
      return;
    }

    // Пытаемся найти элемент для spotlight
    var el = findEl(step);
    if (el) {
      showSpotlight(el, step, idx, desc, adminNote);
    } else {
      // Элемент не найден — показываем info-card
      showInfoCard(step, idx, desc, adminNote);
    }
  }

  /* ═══════════════════════════════════════════════════════════════════════
     9. Spotlight — подсветка элемента + tooltip
     ═══════════════════════════════════════════════════════════════════════ */
  function showSpotlight(el, step, idx, desc, adminNote) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });

    setTimeout(function() {
      var rect = el.getBoundingClientRect();
      var pad = 10;

      // Spotlight overlay
      var spot = document.createElement('div');
      spot.id = 'tourSpotlight';
      spot.className = 'tour-spotlight';
      spot.style.top = (rect.top - pad + window.scrollY) + 'px';
      spot.style.left = (rect.left - pad) + 'px';
      spot.style.width = (rect.width + pad * 2) + 'px';
      spot.style.height = (rect.height + pad * 2) + 'px';
      document.body.appendChild(spot);

      // Tooltip
      var tip = document.createElement('div');
      tip.id = 'tourTooltip';
      tip.className = 'tour-tooltip';
      tip.innerHTML =
        buildProgress(idx) +
        '<div class="tour-tooltip-header">' +
          '<div class="tour-tooltip-icon"><i class="fas ' + step.icon + '"></i></div>' +
          '<div class="tour-tooltip-title">' + step.title + '</div>' +
          '<div class="tour-tooltip-counter">Шаг ' + (idx + 1) + ' из ' + TOTAL + '</div>' +
        '</div>' +
        '<div class="tour-tooltip-body">' + adminNote + desc + '</div>' +
        '<div class="tour-tooltip-nav">' + buildNavButtons(idx) + '</div>';
      document.body.appendChild(tip);

      positionTooltip(tip, rect);
      bindNavEvents();
    }, 400);
  }

  function positionTooltip(tip, targetRect) {
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var tipRect = tip.getBoundingClientRect();
    var gap = 16;

    var top = targetRect.bottom + gap + 10;
    var left = targetRect.left + targetRect.width / 2 - tipRect.width / 2;

    if (top + tipRect.height > vh - 20) {
      top = targetRect.top - tipRect.height - gap - 10;
    }
    if (top < 20) {
      top = Math.max(20, (vh - tipRect.height) / 2);
    }
    if (left < 16) left = 16;
    if (left + tipRect.width > vw - 16) left = vw - tipRect.width - 16;

    tip.style.top = top + 'px';
    tip.style.left = left + 'px';
  }

  /* ═══════════════════════════════════════════════════════════════════════
     10. Info-card — центрированная карточка (fallback если элемент не найден)
     ═══════════════════════════════════════════════════════════════════════ */
  function showInfoCard(step, idx, desc, adminNote) {
    var backdrop = document.createElement('div');
    backdrop.id = 'tourInfoBackdrop';
    backdrop.className = 'tour-info-backdrop';
    backdrop.innerHTML =
      '<div class="tour-info-card">' +
        buildProgress(idx) +
        '<div class="tour-info-icon"><i class="fas ' + step.icon + '"></i></div>' +
        '<div class="tour-info-title">' + step.title + '</div>' +
        '<div class="tour-info-counter">Шаг ' + (idx + 1) + ' из ' + TOTAL + '</div>' +
        '<div class="tour-info-body">' + adminNote + desc + '</div>' +
        '<div class="tour-info-nav">' + buildNavButtons(idx) + '</div>' +
      '</div>';
    document.body.appendChild(backdrop);

    backdrop.addEventListener('click', function(e) {
      if (e.target === backdrop) skipTour();
    });

    bindNavEvents();
  }

  /* ═══════════════════════════════════════════════════════════════════════
     11. Welcome / Completion модалы
     ═══════════════════════════════════════════════════════════════════════ */
  function showWelcomeModal() {
    var backdrop = document.createElement('div');
    backdrop.id = 'tourModalBackdrop';
    backdrop.className = 'tour-modal-backdrop';
    backdrop.innerHTML =
      '<div class="tour-modal-card">' +
        '<div class="tour-modal-emoji">\uD83C\uDF93</div>' +
        '<div class="tour-modal-title">Добро пожаловать!</div>' +
        '<div class="tour-modal-text">' +
          'Пройдите короткое обучение из 12 шагов, чтобы узнать все возможности системы планирования.' +
        '</div>' +
        '<div class="tour-modal-actions">' +
          '<button class="tour-btn tour-btn-next" id="tourWelcomeStart">Начать обучение</button>' +
          '<button class="tour-btn tour-btn-skip" id="tourWelcomeSkip">Пропустить</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(backdrop);

    document.getElementById('tourWelcomeStart').onclick = function() {
      clearTourUI();
      goStep(0);
    };
    document.getElementById('tourWelcomeSkip').onclick = function() {
      var s = { step: 0, completed: true, skipped: true, version: 2 };
      setState(s);
      syncToServer(s);
      clearTourUI();
    };
    backdrop.addEventListener('click', function(e) {
      if (e.target === backdrop) {
        var s = { step: 0, completed: true, skipped: true, version: 2 };
        setState(s);
        syncToServer(s);
        clearTourUI();
      }
    });

    function escHandler(e) {
      if (e.key === 'Escape') {
        var s = { step: 0, completed: true, skipped: true, version: 2 };
        setState(s);
        syncToServer(s);
        clearTourUI();
        document.removeEventListener('keydown', escHandler);
      }
    }
    document.addEventListener('keydown', escHandler);
  }

  function showCompletionModal() {
    var backdrop = document.createElement('div');
    backdrop.id = 'tourModalBackdrop';
    backdrop.className = 'tour-modal-backdrop';
    backdrop.innerHTML =
      '<div class="tour-modal-card">' +
        '<div class="tour-modal-emoji">\uD83C\uDF89</div>' +
        '<div class="tour-modal-title">Обучение завершено!</div>' +
        '<div class="tour-modal-text">' +
          'Теперь вы знаете основы работы с системой. Перезапустить обучение можно в профиле.' +
        '</div>' +
        '<div class="tour-modal-actions">' +
          '<button class="tour-btn tour-btn-next" id="tourDoneBtn">Начать работу</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(backdrop);

    document.getElementById('tourDoneBtn').onclick = function() {
      clearTourUI();
    };
    backdrop.addEventListener('click', function(e) {
      if (e.target === backdrop) clearTourUI();
    });
  }

  /* ═══════════════════════════════════════════════════════════════════════
     12. Public API
     ═══════════════════════════════════════════════════════════════════════ */
  window.startTour = function() {
    showWelcomeModal();
  };
  window.startTourDemo = window.startTour;

  window.restartTour = function() {
    localStorage.removeItem(LS_KEY);
    localStorage.removeItem('tour_seen');
    clearTourUI();
    showWelcomeModal();
  };

  /* ═══════════════════════════════════════════════════════════════════════
     13. Auto-init — подхватывает шаг после перехода между страницами
     ═══════════════════════════════════════════════════════════════════════ */
  document.addEventListener('DOMContentLoaded', function() {
    migrateOldState();
    var state = getState();

    // Первый вход — welcome только на дашборде (после логина)
    if (!state) {
      if (currentPage().indexOf('/accounts/dashboard') === 0 || currentPage() === '/') {
        setTimeout(showWelcomeModal, 1200);
      }
      return;
    }

    // Тур в процессе — продолжить текущий шаг
    if (!state.completed && typeof state.step === 'number' && state.step < TOTAL) {
      setTimeout(function() {
        currentIdx = state.step;
        showStep(state.step);
      }, 600);
      return;
    }
  });

})();
