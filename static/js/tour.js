/* ── Интерактивное обучение — Tour/Onboarding (15 шагов, без зависимостей) ──────────────────
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
      id: 'sidebar_intro', stepNum: 1,
      page: '/accounts/dashboard/',
      spotlightSelector: '#sidebar',
      selector: null,
      title: 'Панель навигации',
      icon: 'fa-compass',
      desc: 'Панель навигации содержит ссылки на все основные модули и вспомогательные страницы.',
      infoOnly: true
    },
    {
      id: 'dashboard_intro', stepNum: 2,
      page: '/accounts/dashboard/',
      selector: null,
      sidebarHighlight: '.nav-item[href="/accounts/dashboard/"]',
      title: 'Стартовая страница',
      icon: 'fa-th-large',
      desc: 'Стартовая страница, которая перед Вами при входе. Содержит основные меню и будет дополнена статистикой и прочей информацией, ориентированной на пользователя (Вас). Можно будет настраивать под себя.',
      infoOnly: true
    },
    {
      id: 'projects_intro', stepNum: 3,
      page: '/works/projects/',
      selector: null,
      sidebarHighlight: '.nav-item[href="/works/projects/"]',
      title: 'Управление проектами',
      icon: 'fa-folder-open',
      desc: 'Меню управления проектами предоставляет основную и сводную информацию о проекте и имеющихся изделиях по данному проекту. Редактирование доступно только администратору.',
      infoOnly: true
    },
    {
      id: 'pp_intro', stepNum: 4,
      page: '/works/production-plan/',
      selector: null,
      sidebarHighlight: '.nav-item[href="/works/production-plan/"]',
      title: 'Производственный план',
      icon: 'fa-file-circle-plus',
      desc: 'Меню «Производственный план» содержит перечень производственных планов, в которых задействовано Ваше подразделение. Предназначено для совместной работы подразделений при планировании работ по конкретному проекту/изделию. Кликнув на иконку любого из них, попадаем в раздел редактирования.',
      infoOnly: true
    },
    {
      id: 'add_pp_row', stepNum: 5,
      page: '/works/production-plan/',
      selector: '#projectActions .btn-primary',
      secondarySelector: 'tr[data-id]',
      needProject: true,
      centerCard: true,
      title: 'Добавление строк в ПП',
      icon: 'fa-table-rows',
      desc: 'План формируется посредством добавления строк с задачами. Например, выпуск документа. Представители каждого отдела могут добавлять/редактировать работы только для своего отдела. На чтение - полный доступ. По умолчанию добавлять может только начальник отдела. Делегирование прав будет настроено позже.'
    },
    {
      id: 'pp_deps', stepNum: 6,
      page: '/works/production-plan/',
      selector: '.dep-badge.action-dep',
      needProject: true,
      centerCard: true,
      cardPosition: 'right',
      autoAction: 'openDepsModal',
      noBlur: true,
      title: 'Зависимости задач',
      icon: 'fa-link',
      desc: 'Функция управления зависимостями. Предназначена для увязки последовательностей работ. Например, типа СТАРТ-ФИНИШ.'
    },
    {
      id: 'sync_to_sp', stepNum: 7,
      page: '/works/production-plan/',
      selector: '#projectActions .btn-secondary',
      needProject: true,
      centerCard: true,
      title: 'Синхронизация ПП \u2192 СП',
      icon: 'fa-arrows-rotate',
      desc: 'Завершив работу по добавлению/редактированию работ в модуле производственного плана, можем перейти к автоматическому переносу данных в план подразделения (месячный/квартальный/годовой). Для этого нажимаем кнопку синхронизации с модулем «Сводное планирование (План/отчёт)». Таким образом работы появятся в плане вашего подразделения. Ручной ввод не требуется.'
    },
    {
      id: 'goto_sp', stepNum: 8,
      page: '/works/production-plan/',
      selector: null,
      sidebarHighlight: '.nav-item[href="/works/plan/"]',
      needProject: true,
      title: 'Переход в СП',
      icon: 'fa-arrow-right',
      desc: 'Готово. Пора переходить в модуль сводного планирования.',
      infoOnly: true
    },
    {
      id: 'sp_overview', stepNum: 9,
      page: '/works/plan/',
      selector: null,
      title: 'Сводное планирование',
      icon: 'fa-table-list',
      desc: 'Страница модуля «Сводное планирование». Он же — привычный «План/отчёт».\n\nЕсли модуль производственного плана предназначен для планирования работ по конкретному проекту/изделию, то модуль сводного планирования предназначен для составления плана подразделения на период.\n\nВ отличие от модуля производственного плана предназначен для планирования каждой работы с простановкой сотрудника (-ов) и часов, необходимых ему для выполнения работы (части работы) в определённый календарный период, а также для заполнения отчётов. В сводном плане могут содержаться работы, как перенесённые (синхронизированные) из производственных планов, так и введённые вновь непосредственно на представленной странице.\n\nРаботы по умолчанию могут вводить начальник отдела и начальник сектора. Начальник сектора может вносить работы только для своего сектора.',
      infoOnly: true
    },
    {
      id: 'edit_task', stepNum: 10,
      page: '/works/plan/',
      selector: 'tr[data-id] .btn-edit-row',
      centerCard: true,
      title: 'Редактирование задачи в СП',
      icon: 'fa-pen-to-square',
      desc: 'Кнопка \u270F\uFE0F открывает модальное окно редактирования задачи. Здесь можно изменить сроки, исполнителей, плановые часы по месяцам и другие параметры.'
    },
    {
      id: 'edit_task_modal', stepNum: 11,
      page: '/works/plan/',
      selector: null,
      infoOnly: true,
      autoAction: 'openEditTaskModal',
      noBlur: true,
      arrowToModal: true,
      title: 'Модальное окно редактирования',
      icon: 'fa-pen-to-square',
      desc: 'Модальное окно редактирования задачи.'
    },
    {
      id: 'report', stepNum: 12,
      page: '/works/plan/',
      selector: 'tr[data-id] .btn-report',
      centerCard: true,
      title: 'Отчёт по задаче',
      icon: 'fa-chart-bar',
      desc: 'Кнопка отчёта позволяет внести фактические данные о выполнении работы: процент готовности, фактические часы, примечания.'
    },
    {
      id: 'errors_btn', stepNum: 13,
      page: '/works/plan/',
      selector: '#errorsBtn',
      autoAction: 'openErrorsPanel',
      title: 'Ошибки планирования',
      icon: 'fa-triangle-exclamation',
      desc: 'Функция «Ошибки планирования» позволяет проверить несоответствия: пересечение сроков с отпусками, командировками, превышение норм часов и другие проблемы.'
    },
    {
      id: 'work_calendar', stepNum: 14,
      page: '/works/work-calendar/',
      selector: '.cal-summary-table, table',
      title: 'Производственный календарь',
      icon: 'fa-calendar-days',
      desc: 'Производственный календарь задаёт норму рабочих часов по месяцам (фонд рабочего времени). Задаёт данные для расчёта загрузки, поиска ошибок загрузки/перегрузки подразделений и исполнителей. Доступен для управления администраторам.',
      adminOnly: true,
      descNonAdmin: 'Производственный календарь задаёт норму рабочих часов по месяцам (фонд рабочего времени). Доступен для управления администраторам.'
    },
    {
      id: 'notices', stepNum: 15,
      page: '/works/notices/',
      selector: '.ji-table, table',
      noArrow: true,
      title: 'Журнал извещений (ЖИ)',
      icon: 'fa-bell',
      desc: 'Журнал извещений фиксирует изменения в документации. Пункты ЖИ создаются автоматически при корректировке или вручную. Здесь отслеживается статус (сроки действия, просрочка, погашение и проч.).'
    },
    {
      id: 'roles', stepNum: 14,
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
  var _activePoll = null; // ID активного setInterval (tryOpenFirstProject)

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
    var ids = ['tourSpotlight', 'tourSpotlight2', 'tourTooltip', 'tourArrow', 'tourArrow2', 'tourSidebarArrow', 'tourInfoBackdrop', 'tourModalBackdrop'];
    ids.forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.remove();
    });
    // Убираем пульсацию sidebar
    var pulsing = document.querySelectorAll('.tour-sidebar-pulse');
    pulsing.forEach(function(el) { el.classList.remove('tour-sidebar-pulse'); });
    // Закрываем открытые модалы и восстанавливаем blur
    var openModals = document.querySelectorAll('.modal-overlay.open');
    openModals.forEach(function(m) {
      m.classList.remove('open');
      m.style.backdropFilter = '';
      m.style.webkitBackdropFilter = '';
    });
    // Закрываем модалки, открытые autoAction-ами тура
    ['newTaskModal', 'peModal', 'typeModal'].forEach(function(id) {
      var m = document.getElementById(id);
      if (m && m.classList.contains('open')) {
        m.classList.remove('open');
        m.style.backdropFilter = '';
        m.style.webkitBackdropFilter = '';
      }
    });
    document.removeEventListener('keydown', keyHandler);
    // Очищаем polling (tryOpenFirstProject)
    if (_activePoll) { clearInterval(_activePoll); _activePoll = null; }
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
      // #sidebar может быть скрыт через transform — не проверяем offsetParent для него
      if (el && (el.id === 'sidebar' || el.offsetParent !== null)) return el;
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

  /* Стрелка-указатель от tooltip к подсвеченной sidebar-ссылке */
  function drawSidebarArrow(tipEl, step) {
    if (!step.sidebarHighlight) return;
    var sbEl = document.querySelector(step.sidebarHighlight);
    if (!sbEl) return;

    // Если sidebar свёрнут — раскрываем на время тура
    var sidebar = document.getElementById('sidebar');
    if (sidebar && sidebar.classList.contains('collapsed')) {
      sidebar.classList.remove('collapsed');
      var mc = document.getElementById('mainContent');
      if (mc) mc.classList.remove('sidebar-collapsed');
    }

    var sbRect = sbEl.getBoundingClientRect();
    var tipRect = tipEl.getBoundingClientRect();

    var old = document.getElementById('tourSidebarArrow');
    if (old) old.remove();

    // Если ссылка вертикально за viewport — не рисуем
    if (sbRect.top < -50 || sbRect.bottom > window.innerHeight + 50) return;

    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.id = 'tourSidebarArrow';
    svg.setAttribute('class', 'tour-sidebar-arrow');
    svg.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99993;pointer-events:none';

    // Начало: левый край tooltip → конец: правый край sidebar-ссылки
    // Если sidebar за пределами экрана (мобильный) — указываем на левый край
    var x1 = tipRect.left;
    var y1 = tipRect.top + tipRect.height / 2;
    var x2 = Math.max(sbRect.right, 4);
    var y2 = Math.max(Math.min(sbRect.top + sbRect.height / 2, window.innerHeight - 10), 10);

    var line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', x1); line.setAttribute('y1', y1);
    line.setAttribute('x2', x2); line.setAttribute('y2', y2);
    svg.appendChild(line);

    // Наконечник стрелки
    var angle = Math.atan2(y2 - y1, x2 - x1);
    var sz = 10;
    var p1x = x2 - sz * Math.cos(angle - 0.4);
    var p1y = y2 - sz * Math.sin(angle - 0.4);
    var p2x = x2 - sz * Math.cos(angle + 0.4);
    var p2y = y2 - sz * Math.sin(angle + 0.4);
    var poly = document.createElementNS(ns, 'polygon');
    poly.setAttribute('points', x2+','+y2+' '+p1x+','+p1y+' '+p2x+','+p2y);
    svg.appendChild(poly);

    document.body.appendChild(svg);
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

    // Раскрываем sidebar если он свёрнут (нужен для подсветки и поиска элементов)
    var sidebar = document.getElementById('sidebar');
    if (sidebar && sidebar.classList.contains('collapsed')) {
      sidebar.classList.remove('collapsed');
      var mc = document.getElementById('mainContent');
      if (mc) mc.classList.remove('sidebar-collapsed');
    }

    // Пульсация sidebar-ссылки
    if (step.sidebarHighlight) {
      var sbEl = document.querySelector(step.sidebarHighlight);
      if (sbEl) sbEl.classList.add('tour-sidebar-pulse');
    }

    // Info-only шаг (центрированная карточка)
    if (step.infoOnly && !step.selector) {
      // Если есть spotlightSelector — рисуем рамку вокруг элемента + стрелку
      if (step.spotlightSelector) {
        var spotEl = document.querySelector(step.spotlightSelector);
        if (spotEl) {
          showInfoCard(step, idx, desc, adminNote);
          // Spotlight рамка поверх info-card
          setTimeout(function() {
            var rect = spotEl.getBoundingClientRect();
            var pad = 6;
            // Для sidebar: рамка от верха до низа viewport, по ширине sidebar
            var spotTop = Math.max(rect.top - pad - 5, 0);
            var spotLeft = Math.max(rect.left - pad, 0);
            var spotHeight = Math.min(rect.bottom + pad + 5, window.innerHeight) - spotTop;
            var spotWidth = rect.width + pad * 2;

            var spot = document.createElement('div');
            spot.id = 'tourSpotlight';
            spot.className = 'tour-spotlight';
            spot.style.top = spotTop + 'px';
            spot.style.left = spotLeft + 'px';
            spot.style.width = spotWidth + 'px';
            spot.style.height = spotHeight + 'px';
            document.body.appendChild(spot);

            // Стрелка от info-card к spotlight рамке
            var card = document.querySelector('.tour-info-card');
            if (card) {
              var spotRect = {
                top: spotTop, left: spotLeft,
                bottom: spotTop + spotHeight, right: spotLeft + spotWidth,
                width: spotWidth, height: spotHeight
              };
              drawArrows(card, spotRect, null);
            }
          }, 100);
          return;
        }
      }
      // Авто-действие для info-only шага (например, открытие модалки)
      if (step.autoAction) {
        var triggerEl = null;
        if (step.autoAction === 'openEditTaskModal') {
          triggerEl = document.querySelector('tr[data-id] .btn-edit-row');
        }
        runAutoAction(step, triggerEl);
      }
      showInfoCard(step, idx, desc, adminNote);
      // Стрелка от info-card к модалу
      if (step.arrowToModal) {
        var card = document.querySelector('.tour-info-card');
        if (card) {
          setTimeout(function() {
            var modalOuter = document.getElementById('newTaskModal');
            var modal = modalOuter ? modalOuter.querySelector('.new-task-box') : null;
            if (modal && modalOuter.classList.contains('open') && card) {
              var mRect = modal.getBoundingClientRect();
              var cRect = card.getBoundingClientRect();
              var ns = 'http://www.w3.org/2000/svg';
              var svg = document.createElementNS(ns, 'svg');
              svg.id = 'tourArrow2';
              svg.setAttribute('class', 'tour-arrow');
              svg.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99993;pointer-events:none';
              var cy = cRect.top + cRect.height / 2;
              var x1 = cRect.right + 5;
              var x2 = mRect.left - 5;
              var line = document.createElementNS(ns, 'line');
              line.setAttribute('x1', x1); line.setAttribute('y1', cy);
              line.setAttribute('x2', x2); line.setAttribute('y2', cy);
              line.setAttribute('stroke', 'rgba(100,160,255,0.7)');
              line.setAttribute('stroke-width', '2');
              line.setAttribute('stroke-dasharray', '8,5');
              svg.appendChild(line);
              var a = 8;
              var arrow = document.createElementNS(ns, 'polygon');
              arrow.setAttribute('points', x2+','+cy+' '+(x2-a)+','+(cy-a/2)+' '+(x2-a)+','+(cy+a/2));
              arrow.setAttribute('fill', 'rgba(100,160,255,0.7)');
              svg.appendChild(arrow);
              document.body.appendChild(svg);
            }
          }, 400);
        }
      }
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
      // Убираем размытие фона если указано noBlur
      if (step.noBlur) {
        setTimeout(function() {
          var modal = document.getElementById('ppDepsModal');
          if (modal) modal.style.backdropFilter = 'none';
          if (modal) modal.style.webkitBackdropFilter = 'none';
        }, 100);
      }
    } else if (step.autoAction === 'openEditTaskModal') {
      // Открываем модал редактирования первой задачи в СП
      try {
        var firstEditBtn = document.querySelector('tr[data-id] .btn-edit-row');
        if (firstEditBtn) firstEditBtn.click();
      } catch(e) {}
      if (step.noBlur) {
        setTimeout(function() {
          var modal = document.getElementById('newTaskModal');
          if (modal) { modal.style.backdropFilter = 'none'; modal.style.webkitBackdropFilter = 'none'; }
        }, 100);
      }
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

      // centerCard: info-card по центру вместо tooltip (но со стрелками к spotlight)
      if (step.centerCard) {
        showInfoCard(step, idx, desc, adminNote);
        var card = document.querySelector('.tour-info-card');
        if (card && !step.noArrow) drawArrows(card, rect, secondaryRect);
        // Стрелка от info-card к модалу редактирования задачи
        if (card && step.arrowToModal) {
          setTimeout(function() {
            var modalOuter = document.getElementById('newTaskModal');
            var modal = modalOuter ? modalOuter.querySelector('.new-task-box') : null;
            if (modal && modalOuter.classList.contains('open') && card) {
              var mRect = modal.getBoundingClientRect();
              var cRect = card.getBoundingClientRect();
              var ns = 'http://www.w3.org/2000/svg';
              var svg = document.createElementNS(ns, 'svg');
              svg.id = 'tourArrow2';
              svg.setAttribute('class', 'tour-arrow');
              svg.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99993;pointer-events:none';
              // Горизонтально: от правого края card к левому краю модалки
              var cy = cRect.top + cRect.height / 2;
              var x1 = cRect.right + 5;
              var x2 = mRect.left - 5;
              var line = document.createElementNS(ns, 'line');
              line.setAttribute('x1', x1); line.setAttribute('y1', cy);
              line.setAttribute('x2', x2); line.setAttribute('y2', cy);
              line.setAttribute('stroke', 'rgba(100,160,255,0.7)');
              line.setAttribute('stroke-width', '2');
              line.setAttribute('stroke-dasharray', '8,5');
              svg.appendChild(line);
              var a = 8;
              var arrow = document.createElementNS(ns, 'polygon');
              arrow.setAttribute('points', x2+','+cy+' '+(x2-a)+','+(cy-a/2)+' '+(x2-a)+','+(cy+a/2));
              arrow.setAttribute('fill', 'rgba(100,160,255,0.7)');
              svg.appendChild(arrow);
              document.body.appendChild(svg);
            }
          }, 400);
        }
        // Стрелка к открытому модалу (например, окно зависимостей)
        if (card && step.autoAction === 'openDepsModal') {
          setTimeout(function() {
            var modalCard = document.querySelector('#ppDepsModal.open .modal');
            if (modalCard && card) {
              var mRect = modalCard.getBoundingClientRect();
              var cRect = card.getBoundingClientRect();
              var ns = 'http://www.w3.org/2000/svg';
              var svg = document.createElementNS(ns, 'svg');
              svg.id = 'tourArrow2';
              svg.setAttribute('class', 'tour-arrow');
              svg.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99993;pointer-events:none';
              addArrowLine(svg, card, mRect);
              document.body.appendChild(svg);
            }
          }, 300);
        }
        drawSidebarArrow(card || document.body, step);
        return;
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
      drawSidebarArrow(tip, step);
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
      _activePoll = setInterval(function() {
        var el = findEl(step);
        attempts++;
        if (el) {
          clearInterval(_activePoll); _activePoll = null;
          setTimeout(function() {
            if (step.autoAction) runAutoAction(step, el);
            showSpotlight(el, step, idx, desc, adminNote);
          }, 500);
        } else if (attempts > 30) {
          clearInterval(_activePoll); _activePoll = null;
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
        '<div class="tour-info-body">' + adminNote + desc.replace(/\n\n/g, '<br><br>') + '</div>' +
        '<div class="tour-info-nav">' + buildNavButtons(idx) + '</div>' +
      '</div>';
    document.body.appendChild(backdrop);

    // Позиционирование карточки (по умолчанию — центр)
    if (step.cardPosition === 'right') {
      backdrop.style.justifyContent = 'flex-end';
      backdrop.style.paddingRight = '40px';
    }

    // Клик в фон НЕ закрывает обучение — только кнопки навигации

    bindNavEvents();

    // Стрелка от info-card к sidebar-ссылке
    var card = backdrop.querySelector('.tour-info-card');
    if (card) drawSidebarArrow(card, step);
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

    if (!state.completed && typeof state.step === 'number' && state.step >= 0 && state.step < TOTAL) {
      setTimeout(function() {
        goStep(state.step);
      }, 600);
      return;
    }
  });

})();
