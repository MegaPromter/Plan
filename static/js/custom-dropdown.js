/* ══════════════════════════════════════════════════════════════════════
   custom-dropdown.js — Кастомный dropdown взамен нативного <select>
   Автоматически заменяет все select.cell-edit и select.cell-select
   внутри таблиц на красивый стилизованный dropdown.

   API:
     initCustomDropdowns(root)  — инициализировать все select внутри root
     destroyCustomDropdown(sel) — убрать обёртку, вернуть нативный select
     refreshCustomDropdown(sel) — перерисовать триггер (после программного изменения)
     closeOpenDropdown()        — закрыть текущий открытый dropdown (если есть)

   Совместимость:
     - Нативный <select> остаётся в DOM (скрыт), хранит value
     - При выборе: обновляет select.value + dispatch "change" event
     - Существующие event listeners на select продолжают работать
   ══════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  var SEARCH_THRESHOLD = 6;
  var _openWrap = null;

  function updateTriggerText(trigger, sel) {
    var opt = sel.options[sel.selectedIndex];
    var text = opt ? opt.textContent : '';
    trigger.textContent = text || '—';
    if (!sel.value || sel.value === '--' || sel.value === '') {
      trigger.classList.add('placeholder');
    } else {
      trigger.classList.remove('placeholder');
    }
  }

  function wrapSelect(sel) {
    if (sel._cdWrap) return sel._cdWrap;
    if (sel.disabled) return null;

    var wrap = document.createElement('div');
    wrap.className = 'cd-wrap';
    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(sel);

    sel.style.cssText = 'position:absolute;opacity:0;pointer-events:none;width:0;height:0;overflow:hidden;';
    sel.tabIndex = -1;

    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'cd-trigger';
    trigger.setAttribute('role', 'combobox');
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.tabIndex = 0;
    updateTriggerText(trigger, sel);
    wrap.insertBefore(trigger, sel);

    var menu = document.createElement('div');
    menu.className = 'cd-menu';
    menu.setAttribute('role', 'listbox');
    wrap.appendChild(menu);

    sel._cdWrap = wrap;
    sel._cdTrigger = trigger;
    sel._cdMenu = menu;
    wrap._cdSelect = sel;

    trigger.addEventListener('mousedown', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (wrap.classList.contains('open')) closeDropdown(wrap);
      else openDropdown(wrap);
    });

    trigger.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        if (!wrap.classList.contains('open')) openDropdown(wrap);
      } else if (e.key === 'Escape') {
        closeDropdown(wrap);
      }
    });

    var valDesc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
    var idxDesc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');
    Object.defineProperty(sel, 'value', {
      get: function () { return valDesc.get.call(this); },
      set: function (v) { valDesc.set.call(this, v); updateTriggerText(trigger, sel); },
      configurable: true
    });
    Object.defineProperty(sel, 'selectedIndex', {
      get: function () { return idxDesc.get.call(this); },
      set: function (v) { idxDesc.set.call(this, v); updateTriggerText(trigger, sel); },
      configurable: true
    });

    return wrap;
  }

  function positionMenu(wrap) {
    var menu = wrap._cdSelect._cdMenu;
    var trigger = wrap._cdSelect._cdTrigger;
    var rect = trigger.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) return; // элемент скрыт

    menu.style.width = 'auto';
    menu.style.minWidth = Math.max(rect.width, 180) + 'px';
    menu.style.maxWidth = Math.min(window.innerWidth - 16, 400) + 'px';

    var menuW = menu.offsetWidth;
    var menuH = Math.min(menu.scrollHeight, 260);
    var top = rect.bottom + 4;
    var left = rect.left;

    if (top + menuH > window.innerHeight - 8) top = rect.top - menuH - 4;
    if (left + menuW > window.innerWidth - 8) left = window.innerWidth - menuW - 8;
    if (left < 4) left = 4;

    menu.style.top = top + 'px';
    menu.style.left = left + 'px';
  }

  function buildMenuItems(wrap) {
    var sel = wrap._cdSelect;
    var menu = sel._cdMenu;
    var trigger = sel._cdTrigger;
    menu.innerHTML = '';

    // Снимаем предыдущий keydown listener (защита от повторного buildMenuItems)
    if (wrap._cdKeyNavBound) {
      trigger.removeEventListener('keydown', wrap._cdKeyNavBound);
      wrap._cdKeyNavBound = null;
    }

    var options = Array.from(sel.options);
    var hasSearch = options.length >= SEARCH_THRESHOLD;

    var searchInput = null;
    if (hasSearch) {
      searchInput = document.createElement('input');
      searchInput.type = 'text';
      searchInput.className = 'cd-search';
      searchInput.placeholder = 'Поиск…';
      searchInput.setAttribute('aria-label', 'Поиск в списке');
      searchInput.autocomplete = 'off';
      menu.appendChild(searchInput);
    }

    var listEl = document.createElement('div');
    listEl.className = 'cd-list';
    menu.appendChild(listEl);

    var highlighted = -1;
    var items = [];

    function render(filter) {
      listEl.innerHTML = '';
      items = [];
      highlighted = -1;
      var q = (filter || '').toLowerCase().trim();

      options.forEach(function (opt, idx) {
        if (opt.disabled) return;
        var text = opt.textContent;
        if (q && !text.toLowerCase().includes(q)) return;

        var item = document.createElement('div');
        item.className = 'cd-item';
        item.setAttribute('role', 'option');
        item.textContent = text;
        item.dataset.value = opt.value;
        item.dataset.idx = idx;

        if (opt.value === '' || opt.value === '--' || text === '--') {
          item.classList.add('placeholder');
        }
        if (idx === sel.selectedIndex) {
          item.classList.add('selected');
          item.setAttribute('aria-selected', 'true');
        }

        item.addEventListener('mousedown', function (e) {
          e.preventDefault();
          e.stopPropagation();
          selectItem(wrap, opt.value, idx);
        });
        item.addEventListener('mouseenter', function () {
          highlighted = +this.dataset.hlIdx;
          setHighlight(items, highlighted);
        });

        item.dataset.hlIdx = items.length;
        listEl.appendChild(item);
        items.push(item);
      });

      if (items.length === 0) {
        var empty = document.createElement('div');
        empty.className = 'cd-empty';
        empty.textContent = 'Ничего не найдено';
        listEl.appendChild(empty);
      }

      var selItem = listEl.querySelector('.cd-item.selected');
      if (selItem) {
        highlighted = items.indexOf(selItem);
        selItem.classList.add('highlighted');
        requestAnimationFrame(function () {
          selItem.scrollIntoView({ block: 'nearest' });
        });
      }
    }

    render('');

    function handleKeyNav(e) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (items.length === 0) return;
        highlighted = highlighted < items.length - 1 ? highlighted + 1 : 0; // cycling
        setHighlight(items, highlighted);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (items.length === 0) return;
        highlighted = highlighted > 0 ? highlighted - 1 : items.length - 1; // cycling
        setHighlight(items, highlighted);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (highlighted >= 0 && items[highlighted]) {
          var it = items[highlighted];
          selectItem(wrap, it.dataset.value, +it.dataset.idx);
        }
      } else if (e.key === 'Escape') {
        closeDropdown(wrap);
      }
    }

    if (searchInput) {
      searchInput.addEventListener('input', function () { render(searchInput.value); });
      searchInput.addEventListener('keydown', handleKeyNav);
    }

    wrap._cdKeyNavBound = function (e) {
      if (wrap.classList.contains('open')) handleKeyNav(e);
    };
    trigger.addEventListener('keydown', wrap._cdKeyNavBound);
  }

  function setHighlight(items, idx) {
    items.forEach(function (it, i) {
      it.classList.toggle('highlighted', i === idx);
    });
    if (idx >= 0 && items[idx]) {
      items[idx].scrollIntoView({ block: 'nearest' });
    }
  }

  function selectItem(wrap, value, optIdx) {
    var sel = wrap._cdSelect;
    var prev = sel.value;
    sel.selectedIndex = optIdx;
    updateTriggerText(sel._cdTrigger, sel);
    closeDropdown(wrap);
    if (prev !== value) {
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  function _findScrollParent(el) {
    var node = el.parentElement;
    while (node && node !== document.body) {
      var style = getComputedStyle(node);
      if (/auto|scroll|overlay/.test(style.overflow + style.overflowY)) return node;
      node = node.parentElement;
    }
    return window;
  }

  function openDropdown(wrap) {
    if (_openWrap && _openWrap !== wrap) closeDropdown(_openWrap);

    wrap.classList.add('open');
    wrap._cdSelect._cdTrigger.setAttribute('aria-expanded', 'true');
    _openWrap = wrap;

    buildMenuItems(wrap);

    // Портал: переносим меню в body, чтобы overflow:auto предков не обрезал
    var menu = wrap._cdSelect._cdMenu;
    document.body.appendChild(menu);
    menu.style.display = 'block';

    positionMenu(wrap);

    // Scroll parent listener — привязан к wrap, а не к модулю
    wrap._scrollParent = _findScrollParent(wrap);
    wrap._scrollHandler = function () { closeDropdown(wrap); };
    wrap._scrollParent.addEventListener('scroll', wrap._scrollHandler, { passive: true });

    var search = menu.querySelector('.cd-search');
    if (search) {
      requestAnimationFrame(function () { search.focus(); });
    }
  }

  function closeDropdown(wrap) {
    if (!wrap) return;
    wrap.classList.remove('open');
    var trigger = wrap._cdSelect ? wrap._cdSelect._cdTrigger : wrap.querySelector('.cd-trigger');
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    if (_openWrap === wrap) _openWrap = null;

    // Возвращаем меню обратно в wrap
    var menu = wrap._cdSelect ? wrap._cdSelect._cdMenu : null;
    if (menu && menu.parentNode === document.body) {
      menu.style.display = '';
      wrap.appendChild(menu);
    }

    if (wrap._scrollParent && wrap._scrollHandler) {
      wrap._scrollParent.removeEventListener('scroll', wrap._scrollHandler);
      wrap._scrollParent = null;
      wrap._scrollHandler = null;
    }

    if (wrap._cdKeyNavBound && trigger) {
      trigger.removeEventListener('keydown', wrap._cdKeyNavBound);
      wrap._cdKeyNavBound = null;
    }

    if (trigger && trigger.offsetParent !== null) trigger.focus();
  }

  document.addEventListener('mousedown', function (e) {
    if (!_openWrap) return;
    // Не закрываем, если клик по wrap или по меню (портал в body)
    var menu = _openWrap._cdSelect ? _openWrap._cdSelect._cdMenu : null;
    if (_openWrap.contains(e.target)) return;
    if (menu && menu.contains(e.target)) return;
    closeDropdown(_openWrap);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && _openWrap) closeDropdown(_openWrap);
  });
  var _resizeRaf = 0;
  window.addEventListener('resize', function () {
    if (!_openWrap) return;
    cancelAnimationFrame(_resizeRaf);
    _resizeRaf = requestAnimationFrame(function () {
      if (_openWrap) positionMenu(_openWrap);
    });
  });

  function initCustomDropdowns(root) {
    if (!root) root = document;
    root.querySelectorAll('td select.cell-edit, td select.cell-select').forEach(function (sel) {
      if (!sel.disabled) wrapSelect(sel);
    });
  }

  function destroyCustomDropdown(sel) {
    if (!sel._cdWrap) return;
    var wrap = sel._cdWrap;
    if (_openWrap === wrap) closeDropdown(wrap);
    if (wrap._cdKeyNavBound && sel._cdTrigger) {
      sel._cdTrigger.removeEventListener('keydown', wrap._cdKeyNavBound);
    }
    sel.style.cssText = '';
    sel.tabIndex = 0;
    delete sel.value;
    delete sel.selectedIndex;
    wrap.parentNode.insertBefore(sel, wrap);
    wrap.remove();
    delete sel._cdWrap;
    delete sel._cdTrigger;
    delete sel._cdMenu;
  }

  function refreshCustomDropdown(sel) {
    if (!sel || !sel._cdWrap) return;
    updateTriggerText(sel._cdTrigger, sel);
  }

  function closeOpenDropdown() {
    if (_openWrap) closeDropdown(_openWrap);
  }

  window.initCustomDropdowns = initCustomDropdowns;
  window.destroyCustomDropdown = destroyCustomDropdown;
  window.refreshCustomDropdown = refreshCustomDropdown;
  window.closeOpenDropdown = closeOpenDropdown;

})();
