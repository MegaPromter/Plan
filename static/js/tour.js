/* ── Интерактивное обучение — Tour/Onboarding (11 шагов, без зависимостей) ──────────────────
 * Межстраничный тур: автоматический переход на нужную страницу,
 * подсветка элементов с пульсацией на каждом шаге.
 * Прогресс: localStorage + сервер (/api/col_settings/).
 * ──────────────────────────────────────────────────────────────────────── */

(function() {
  'use strict';

  /* ═══════════════════════════════════════════════════════════════════════
     1. TOUR_STEPS — 11 шагов
     ═══════════════════════════════════════════════════════════════════════ */
  var STEPS = [
    {
      id: 'create_project', stepNum: 1,
      page: '/works/projects/',
      selector: '.btn-primary',
      sidebarHighlight: 'a[href="/works/projects/"]',
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
      sidebarHighlight: 'a[href="/works/production-plan/"]',
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
      secondarySelector: 'tr[data-id]',
      needProject: true,
      title: 'Добавление строк в ПП',
      icon: 'fa-table-rows',
      desc: 'Внутри открытого ПП кнопка «Добавить строку» создаёт новую работу. Каждая строка — это работа с этапом, вехой, шифром и трудоёмкостью.'
    },
    {
      id: 'sync_to_sp', stepNum: 4,
      page: '/works/production-plan/',
      selector: '#projectActions .btn-secondary',
      needProject: true,
      title: 'Синхронизация ПП \u2192 СП',
      icon: 'fa-arrows-rotate',
      desc: 'Кнопка «Синхронизировать с СП» переносит работы из производственного плана в сводный план (план/отчёт). После синхронизации задачи появляются в СП с пометкой «из ПП».'
    },
    {
      id: 'sp_overview', stepNum: 5,
      page: '/works/plan/',
      selector: null,
      sidebarHighlight: 'a[href="/works/plan/"]',
      title: 'Сводное планирование',
      icon: 'fa-table-list',
      desc: 'По завершении работы в Производственном плане и выполнения синхронизации данные отображаются в модуле «Сводное планирование».',
      infoOnly: true
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
      autoAction: 'openErrorsPanel',
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
      desc: 'Производственный календарь задаёт норму рабочих часов по месяцам (фонд рабочего времени). Задаёт данные для расчёта загрузки, поиска ошибок загрузки/перегрузки подразделений и исполнителей. Доступен для управления администраторам.',
      adminOnly: true,
      descNonAdmin: 'Производственный календарь задаёт норму рабочих часов по месяцам (фонд рабочего времени). Доступен для управления администраторам.'
    },
    {
      id: 'notices', stepNum: 10,
      page: '/works/notices/',
      selector: '.ji-table, table',
      noArrow: true,
      title: 'Журнал извещений (ЖИ)',
      icon: 'fa-bell',
      desc: 'Журнал извещений фиксирует изменения в документации. Пункты ЖИ создаются автоматически при корректировке или вручную. Здесь отслеживается статус (сроки действия, просрочка, погашение и проч.).'
    },
    {
      id: 'roles', stepNum: 11,
      page: null,
      selector: null,
      title: 'Роли и права доступа',
      icon: 'fa-users-gear',
      desc: 'Роли пользователей чётко соответствуют должностям сотрудников. Должность определяет правила, права и видимость данных.',
      infoOnly: true
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
    var ids = ['tourSpotlight', 'tourSpotlight2', 'tourTooltip', 'tourArrow', 'tourInfoBackdrop', 'tourModalBackdrop'];
    ids.forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.remove();
    });
    // Убираем пульсацию sidebar
    var pulsing = document.querySelectorAll('.tour-sidebar-pulse');
    pulsing.forEach(function(el) { el.classList.remove('tour-sidebar-pulse'); });
    // Закрываем открытые модалы (зависимости, ошибки и т.д.)
    var openModals = document.querySelectorAll('.modal-overlay.open');
    openModals.forEach(function(m) { m.classList.remove('open'); });
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
      if (el && el.offsetParent !== null) return el;
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

    if (step.page && !matchPage(step.page)) {
      window.location.href = step.page;
      return;
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
      ? '<button class="tour-btn tour-btn-prev" id="tourPrev">\u2190 Назад</button>'
      : '<span></span>';
    var skipBtn = '<button class="tour-btn tour-btn-skip" id="tourSkip">Пропустить</button>';
    var nextLabel = idx === TOTAL - 1 ? 'Готово \u2713' : 'Далее \u2192';
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

    var desc = step.desc;
    var adminNote = '';
    if (step.adminOnly && !isAdmin()) {
      desc = step.descNonAdmin || step.desc;
      adminNote = '<div class="tour-admin-note"><i class="fas fa-lock"></i> Этот шаг выполняет администратор</div>';
    }

    // Пульсация sidebar-ссылки
    if (step.sidebarHighlight) {
      var sbEl = document.querySelector(step.sidebarHighlight);
      if (sbEl) sbEl.classList.add('tour-sidebar-pulse');
    }

    // Info-only шаг
    if (step.infoOnly && !step.selector) {
      showInfoCard(step, idx, desc, adminNote);
      return;
    }

    var el = findEl(step);
    if (el) {
      // Авто-действие перед показом spotlight
      if (step.autoAction) runAutoAction(step, el);
      showSpotlight(el, step, idx, desc, adminNote);
    } else if (step.needProject && matchPage(step.page)) {
      tryOpenFirstProject(step, idx, desc, adminNote);
    } else {
      showInfoCard(step, idx, desc, adminNote);
    }
  }

  /* ═══════════════════════════════════════════════════════════════════════
     8b. Авто-действия (открытие модалов и панелей)
     ═══════════════════════════════════════════════════════════════════════ */
  function runAutoAction(step, el) {
    if (step.autoAction === 'openDepsModal') {
      // Кликаем по кнопке зависимостей чтобы открыть модал
      try { el.click(); } catch(e) {}
    } else if (step.autoAction === 'openErrorsPanel') {
      // Кликаем по кнопке ошибок чтобы открыть панель
      try { el.click(); } catch(e) {}
    }
  }

  /* ═══════════════════════════════════════════════════════════════════════
     9. Spotlight — подсветка элемента + tooltip
     ═══════════════════════════════════════════════════════════════════════ */
  function showSpotlight(el, step, idx, desc, adminNote) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });

    setTimeout(function() {
      var rect = el.getBoundingClientRect();
      // Больше padding для мелких элементов
      var pad = (rect.width < 60 || rect.height < 40) ? 16 : 10;

      // Spotlight overlay
      var spot = document.createElement('div');
      spot.id = 'tourSpotlight';
      spot.className = 'tour-spotlight';
      spot.style.top = (rect.top - pad + window.scrollY) + 'px';
      spot.style.left = (rect.left - pad) + 'px';
      spot.style.width = (rect.width + pad * 2) + 'px';
      spot.style.height = (rect.height + pad * 2) + 'px';
      document.body.appendChild(spot);

      // Второй spotlight для secondarySelector (шаг 3 — строка таблицы)
      var secondaryRect = null;
      if (step.secondarySelector) {
        var el2 = document.querySelector(step.secondarySelector);
        if (el2 && el2.offsetParent !== null) {
          secondaryRect = el2.getBoundingClientRect();
          var spot2 = document.createElement('div');
          spot2.id = 'tourSpotlight2';
          spot2.className = 'tour-spotlight';
          spot2.style.top = (secondaryRect.top - pad + window.scrollY) + 'px';
          spot2.style.left = (secondaryRect.left - pad) + 'px';
          spot2.style.width = (secondaryRect.width + pad * 2) + 'px';
          spot2.style.height = (secondaryRect.height + pad * 2) + 'px';
          document.body.appendChild(spot2);
        }
      }

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
      if (!step.noArrow) drawArrows(tip, rect, secondaryRect);
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
     9b. Стрелки-указатели от tooltip к целевым элементам (SVG)
     ═══════════════════════════════════════════════════════════════════════ */
  function drawArrows(tipEl, targetRect, secondaryRect) {
    var old = document.getElementById('tourArrow');
    if (old) old.remove();

    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.id = 'tourArrow';
    svg.setAttribute('class', 'tour-arrow');
    svg.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99993;pointer-events:none';

    addArrowLine(svg, tipEl, targetRect);
    if (secondaryRect) {
      addArrowLine(svg, tipEl, secondaryRect);
    }

    document.body.appendChild(svg);
  }

  function addArrowLine(svg, tipEl, targetRect) {
    var ns = 'http://www.w3.org/2000/svg';
    var tipRect = tipEl.getBoundingClientRect();
    var tipBelow = tipRect.top > targetRect.bottom;
    var tipRight = tipRect.left > targetRect.right;
    var tipLeft  = tipRect.right < targetRect.left;

    var x1, y1, x2, y2;
    if (tipBelow) {
      x1 = tipRect.left + tipRect.width / 2;
      y1 = tipRect.top;
      x2 = targetRect.left + targetRect.width / 2;
      y2 = targetRect.bottom;
    } else if (tipRight) {
      x1 = tipRect.left;
      y1 = tipRect.top + tipRect.height / 2;
      x2 = targetRect.right;
      y2 = targetRect.top + targetRect.height / 2;
    } else if (tipLeft) {
      x1 = tipRect.right;
      y1 = tipRect.top + tipRect.height / 2;
      x2 = targetRect.left;
      y2 = targetRect.top + targetRect.height / 2;
    } else {
      x1 = tipRect.left + tipRect.width / 2;
      y1 = tipRect.bottom;
      x2 = targetRect.left + targetRect.width / 2;
      y2 = targetRect.top;
    }

    var line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', x1); line.setAttribute('y1', y1);
    line.setAttribute('x2', x2); line.setAttribute('y2', y2);
    svg.appendChild(line);

    var angle = Math.atan2(y2 - y1, x2 - x1);
    var sz = 10;
    var p1x = x2 - sz * Math.cos(angle - 0.4);
    var p1y = y2 - sz * Math.sin(angle - 0.4);
    var p2x = x2 - sz * Math.cos(angle + 0.4);
    var p2y = y2 - sz * Math.sin(angle + 0.4);
    var poly = document.createElementNS(ns, 'polygon');
    poly.setAttribute('points', x2+','+y2+' '+p1x+','+p1y+' '+p2x+','+p2y);
    svg.appendChild(poly);
  }

  /* ═══════════════════════════════════════════════════════════════════════
     9c. Авто-открытие первого ПП-проекта (для шагов, требующих открытый проект)
     ═══════════════════════════════════════════════════════════════════════ */
  function tryOpenFirstProject(step, idx, desc, adminNote) {
    var card = document.querySelector('.pp-project-card');
    if (card) {
      card.click();
      var attempts = 0;
      var poll = setInterval(function() {
        var el = findEl(step);
        attempts++;
        if (el) {
          clearInterval(poll);
          setTimeout(function() {
            if (step.autoAction) runAutoAction(step, el);
            showSpotlight(el, step, idx, desc, adminNote);
          }, 500);
        } else if (attempts > 30) {
          clearInterval(poll);
          showInfoCard(step, idx, desc, adminNote);
        }
      }, 200);
    } else {
      showInfoCard(step, idx, desc, adminNote);
    }
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
          'Пройдите короткое обучение из ' + TOTAL + ' шагов, чтобы узнать все возможности системы планирования.' +
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

    if (!state) {
      setTimeout(showWelcomeModal, 1200);
      return;
    }

    if (!state.completed && typeof state.step === 'number' && state.step < TOTAL) {
      setTimeout(function() {
        goStep(state.step);
      }, 600);
      return;
    }
  });

})();
