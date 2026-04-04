/* ══════════════════════════════════════════════════════════════════════
   custom-dropdown.js — Кастомный dropdown взамен нативного <select>
   Автоматически заменяет все select.cell-edit и select.cell-select
   внутри таблиц на красивый стилизованный dropdown.

   API:
     initCustomDropdowns(root)  — инициализировать все select внутри root
     destroyCustomDropdown(sel) — убрать обёртку, вернуть нативный select
     refreshCustomDropdown(sel) — перерисовать опции (после программного изменения)

   Совместимость:
     - Нативный <select> остаётся в DOM (скрыт), хранит value
     - При выборе: обновляет select.value + dispatch "change" event
     - Существующие event listeners на select продолжают работать
   ══════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  // ── Порог для показа поля поиска ──
  const SEARCH_THRESHOLD = 6;

  // ── Текущий открытый dropdown (только один одновременно) ──
  let _openWrap = null;

  // ── Утилиты ──────────────────────────────────────────────────────
  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  // ── Создание обёртки вокруг нативного select ─────────────────────
  function wrapSelect(sel) {
    // Уже обёрнут?
    if (sel._cdWrap) return sel._cdWrap;
    // Disabled select — не оборачиваем
    if (sel.disabled) return null;

    const wrap = document.createElement('div');
    wrap.className = 'cd-wrap';

    // Вставляем обёртку на место select
    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(sel);

    // Скрываем нативный select
    sel.style.position = 'absolute';
    sel.style.opacity = '0';
    sel.style.pointerEvents = 'none';
    sel.style.width = '0';
    sel.style.height = '0';
    sel.style.overflow = 'hidden';
    sel.tabIndex = -1;

    // Создаём триггер
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'cd-trigger';
    trigger.tabIndex = 0;
    updateTriggerText(trigger, sel);
    wrap.insertBefore(trigger, sel);

    // Создаём меню (пока не заполняем — лениво)
    const menu = document.createElement('div');
    menu.className = 'cd-menu';
    wrap.appendChild(menu);

    // Связи
    sel._cdWrap = wrap;
    sel._cdTrigger = trigger;
    sel._cdMenu = menu;
    wrap._cdSelect = sel;

    // ── События ──
    trigger.addEventListener('mousedown', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (wrap.classList.contains('open')) {
        closeDropdown(wrap);
      } else {
        openDropdown(wrap);
      }
    });

    // Keyboard на триггере
    trigger.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        if (!wrap.classList.contains('open')) openDropdown(wrap);
      } else if (e.key === 'Escape') {
        closeDropdown(wrap);
      }
    });

    // Следим за программным изменением select.value
    const origDescriptor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
    Object.defineProperty(sel, 'value', {
      get() { return origDescriptor.get.call(this); },
      set(v) {
        origDescriptor.set.call(this, v);
        updateTriggerText(trigger, sel);
      },
      configurable: true
    });

    // Если select меняется программно через selectedIndex
    const origIdxDescriptor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');
    Object.defineProperty(sel, 'selectedIndex', {
      get() { return origIdxDescriptor.get.call(this); },
      set(v) {
        origIdxDescriptor.set.call(this, v);
        updateTriggerText(trigger, sel);
      },
      configurable: true
    });

    return wrap;
  }

  // ── Текст триггера ──
  function updateTriggerText(trigger, sel) {
    const opt = sel.options[sel.selectedIndex];
    const text = opt ? opt.textContent : '';
    trigger.textContent = text || '—';
    // Стиль placeholder
    if (!sel.value || sel.value === '--' || sel.value === '') {
      trigger.classList.add('placeholder');
    } else {
      trigger.classList.remove('placeholder');
    }
  }

  // ── Позиционирование меню ──
  function positionMenu(wrap) {
    var menu = wrap.querySelector('.cd-menu');
    var trigger = wrap.querySelector('.cd-trigger');
    var rect = trigger.getBoundingClientRect();

    // Ширина: auto по контенту, но не уже триггера и не уже 180px
    menu.style.width = 'auto';
    menu.style.minWidth = Math.max(rect.width, 180) + 'px';
    menu.style.maxWidth = Math.min(window.innerWidth - 16, 400) + 'px';

    // Даём браузеру рассчитать реальную ширину
    var menuW = menu.offsetWidth;

    // По умолчанию — вниз
    var top = rect.bottom + 4;
    var left = rect.left;

    // Если не помещается внизу — открываем вверх
    var menuH = Math.min(menu.scrollHeight, 260);
    if (top + menuH > window.innerHeight - 8) {
      top = rect.top - menuH - 4;
    }
    // Если не помещается справа
    if (left + menuW > window.innerWidth - 8) {
      left = window.innerWidth - menuW - 8;
    }
    if (left < 4) left = 4;

    menu.style.top = top + 'px';
    menu.style.left = left + 'px';
  }

  // ── Построить список опций ──
  function buildMenuItems(wrap) {
    const sel = wrap._cdSelect;
    const menu = wrap.querySelector('.cd-menu');
    menu.innerHTML = '';

    const options = Array.from(sel.options);
    const hasSearch = options.length >= SEARCH_THRESHOLD;

    // Поле поиска
    let searchInput = null;
    if (hasSearch) {
      searchInput = document.createElement('input');
      searchInput.type = 'text';
      searchInput.className = 'cd-search';
      searchInput.placeholder = 'Поиск…';
      searchInput.autocomplete = 'off';
      menu.appendChild(searchInput);
    }

    // Контейнер для пунктов
    const listEl = document.createElement('div');
    listEl.className = 'cd-list';
    menu.appendChild(listEl);

    let highlighted = -1;
    let items = [];

    function render(filter) {
      listEl.innerHTML = '';
      items = [];
      highlighted = -1;
      const q = (filter || '').toLowerCase().trim();

      options.forEach(function (opt, idx) {
        const text = opt.textContent;
        if (q && !text.toLowerCase().includes(q)) return;

        const item = document.createElement('div');
        item.className = 'cd-item';
        item.textContent = text;
        item.dataset.value = opt.value;
        item.dataset.idx = idx;

        // Placeholder стиль для "--"
        if (opt.value === '' || opt.value === '--' || text === '--') {
          item.classList.add('placeholder');
        }
        // Текущий выбранный
        if (idx === sel.selectedIndex) {
          item.classList.add('selected');
        }

        item.addEventListener('mousedown', function (e) {
          e.preventDefault();
          e.stopPropagation();
          selectItem(wrap, opt.value, idx);
        });

        item.addEventListener('mouseenter', function () {
          setHighlight(items, items.indexOf(item));
          highlighted = items.indexOf(item);
        });

        listEl.appendChild(item);
        items.push(item);
      });

      if (items.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'cd-empty';
        empty.textContent = 'Ничего не найдено';
        listEl.appendChild(empty);
      }

      // Подсветить текущий
      const selItem = listEl.querySelector('.cd-item.selected');
      if (selItem) {
        highlighted = items.indexOf(selItem);
        selItem.classList.add('highlighted');
        // Scroll к выбранному
        requestAnimationFrame(function () {
          selItem.scrollIntoView({ block: 'nearest' });
        });
      }
    }

    render('');

    // Обработчики поиска
    if (searchInput) {
      searchInput.addEventListener('input', function () {
        render(searchInput.value);
      });
      searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          highlighted = Math.min(highlighted + 1, items.length - 1);
          setHighlight(items, highlighted);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          highlighted = Math.max(highlighted - 1, 0);
          setHighlight(items, highlighted);
        } else if (e.key === 'Enter') {
          e.preventDefault();
          if (highlighted >= 0 && items[highlighted]) {
            const it = items[highlighted];
            selectItem(wrap, it.dataset.value, +it.dataset.idx);
          }
        } else if (e.key === 'Escape') {
          closeDropdown(wrap);
        }
      });
    }
  }

  function setHighlight(items, idx) {
    items.forEach(function (it, i) {
      it.classList.toggle('highlighted', i === idx);
    });
    if (idx >= 0 && items[idx]) {
      items[idx].scrollIntoView({ block: 'nearest' });
    }
  }

  // ── Выбор пункта ──
  function selectItem(wrap, value, optIdx) {
    const sel = wrap._cdSelect;
    const prev = sel.value;
    sel.selectedIndex = optIdx;
    updateTriggerText(wrap.querySelector('.cd-trigger'), sel);
    closeDropdown(wrap);

    // Dispatch change только если значение реально изменилось
    if (prev !== value) {
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  // ── Находим ближайший скроллируемый контейнер ──
  function _findScrollParent(el) {
    var node = el.parentElement;
    while (node && node !== document.body) {
      var ov = getComputedStyle(node).overflow;
      if (ov === 'auto' || ov === 'scroll' || ov === 'overlay') return node;
      var ovY = getComputedStyle(node).overflowY;
      if (ovY === 'auto' || ovY === 'scroll' || ovY === 'overlay') return node;
      node = node.parentElement;
    }
    return window;
  }

  var _scrollParent = null;
  var _scrollHandler = null;

  // ── Открыть dropdown ──
  function openDropdown(wrap) {
    // Закрыть предыдущий
    if (_openWrap && _openWrap !== wrap) {
      closeDropdown(_openWrap);
    }
    wrap.classList.add('open');
    _openWrap = wrap;

    buildMenuItems(wrap);
    positionMenu(wrap);

    // Слушаем скролл на ближайшем scrollable parent — закрываем при прокрутке таблицы
    _scrollParent = _findScrollParent(wrap);
    _scrollHandler = function () { closeDropdown(wrap); };
    _scrollParent.addEventListener('scroll', _scrollHandler, { passive: true });

    // Фокус на поиск если есть
    var search = wrap.querySelector('.cd-search');
    if (search) {
      requestAnimationFrame(function () { search.focus(); });
    }
  }

  // ── Закрыть dropdown ──
  function closeDropdown(wrap) {
    if (!wrap) return;
    wrap.classList.remove('open');
    if (_openWrap === wrap) _openWrap = null;
    // Убираем scroll listener
    if (_scrollParent && _scrollHandler) {
      _scrollParent.removeEventListener('scroll', _scrollHandler);
      _scrollParent = null;
      _scrollHandler = null;
    }
    // Вернуть фокус на триггер
    var trigger = wrap.querySelector('.cd-trigger');
    if (trigger) trigger.focus();
  }

  // ── Глобальное закрытие по клику вне ──
  document.addEventListener('mousedown', function (e) {
    if (_openWrap && !_openWrap.contains(e.target)) {
      closeDropdown(_openWrap);
    }
  });

  // Скролл таблицы закрывает dropdown через _scrollParent listener (см. openDropdown)

  // ── Закрытие по Escape (глобально) ──
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && _openWrap) {
      closeDropdown(_openWrap);
    }
  });

  // ── Репозиционирование при resize ──
  window.addEventListener('resize', function () {
    if (_openWrap) positionMenu(_openWrap);
  });

  // ── Публичный API ────────────────────────────────────────────────

  /** Инициализировать все select внутри root */
  function initCustomDropdowns(root) {
    if (!root) root = document;
    const selects = root.querySelectorAll(
      'td select.cell-edit, td select.cell-select'
    );
    selects.forEach(function (sel) {
      if (!sel.disabled) wrapSelect(sel);
    });
  }

  /** Убрать обёртку, вернуть нативный select */
  function destroyCustomDropdown(sel) {
    if (!sel._cdWrap) return;
    const wrap = sel._cdWrap;
    const parent = wrap.parentNode;
    // Вернуть select на место
    sel.style.position = '';
    sel.style.opacity = '';
    sel.style.pointerEvents = '';
    sel.style.width = '';
    sel.style.height = '';
    sel.style.overflow = '';
    sel.tabIndex = 0;
    parent.insertBefore(sel, wrap);
    wrap.remove();
    delete sel._cdWrap;
    delete sel._cdTrigger;
    delete sel._cdMenu;
  }

  /** Перерисовать триггер и опции (после программного изменения options) */
  function refreshCustomDropdown(sel) {
    if (!sel._cdWrap) return;
    updateTriggerText(sel._cdTrigger, sel);
  }

  // Экспорт
  window.initCustomDropdowns = initCustomDropdowns;
  window.destroyCustomDropdown = destroyCustomDropdown;
  window.refreshCustomDropdown = refreshCustomDropdown;

})();
