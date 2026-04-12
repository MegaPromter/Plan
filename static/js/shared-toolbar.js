/* ══════════════════════════════════════════════════════════════════════
   shared-toolbar.js — Общие компоненты тулбара для СП и ПП
   Dept filter (чипы/dropdown), Period bar, Status pills
   ══════════════════════════════════════════════════════════════════════ */

// ── DEPT FILTER ──────────────────────────────────────────────────────────
// Конфиг: { barId, wrapId, idPrefix, multiSelect, chipLimit,
//            getSelection, setSelection, onApply }

var DEPT_CHIP_LIMIT = 5;

function initDeptFilter(cfg) {
  var barId = cfg.barId;
  var wrapId = cfg.wrapId;
  var prefix = cfg.idPrefix || '';
  var multi = cfg.multiSelect || false;
  var limit = cfg.chipLimit || DEPT_CHIP_LIMIT;
  var depts = cfg.depts;
  var getSel = cfg.getSelection; // () => Set
  var setSel = cfg.setSelection; // (Set) => void
  var onApply = cfg.onApply; // () => void

  var bar = document.getElementById(barId);
  var wrap = document.getElementById(wrapId);
  if (!bar || !wrap) return null;
  if (!depts || depts.length < 2) {
    return null;
  }
  bar.style.display = '';

  var mode = depts.length > limit ? 'dropdown' : 'chips';
  var sel = getSel();

  // ── Глобальные функции для onclick ──
  var fnPrefix = prefix || 'shared';

  if (mode === 'dropdown') {
    _deptRenderDropdown(wrap, prefix, depts, sel, multi);
    // Регистрируем глобальные функции
    window[fnPrefix + 'ToggleDeptMenu'] = function () {
      var menu = document.getElementById(prefix + 'DeptMenu');
      if (!menu) return;
      menu.classList.toggle('open');
      if (menu.classList.contains('open')) {
        // Синхронизируем чекбоксы с текущим выбором
        var curSel = getSel();
        document.querySelectorAll('#' + prefix + 'DeptMenuItems .dept-cb').forEach(function (cb) {
          cb.checked = curSel.has(cb.value);
        });
        var inp = document.getElementById(prefix + 'DeptSearch');
        if (inp) {
          inp.value = '';
          _deptFilterList(prefix, depts);
          inp.focus();
        }
      }
    };
    window[fnPrefix + 'FilterDeptList'] = function () {
      _deptFilterList(prefix, depts);
    };
    window[fnPrefix + 'ToggleDeptItem'] = function (cb) {
      // Мгновенное применение при клике на чекбокс
      var checked = document.querySelectorAll('#' + prefix + 'DeptMenuItems .dept-cb:checked');
      var newSel = new Set();
      checked.forEach(function (c) {
        newSel.add(c.value);
      });
      setSel(newSel);
      _deptUpdateUI(wrap, prefix, mode, multi, depts, newSel);
      onApply();
    };
    window[fnPrefix + 'ClearDeptFilter'] = function () {
      document.querySelectorAll('#' + prefix + 'DeptMenuItems .dept-cb').forEach(function (c) {
        c.checked = false;
      });
      setSel(new Set());
      _deptUpdateUI(wrap, prefix, mode, multi, depts, new Set());
      var menu = document.getElementById(prefix + 'DeptMenu');
      if (menu) menu.classList.remove('open');
      onApply();
    };
  } else {
    // Chips mode
    _deptRenderChips(wrap, prefix, depts, sel);
    window[fnPrefix + 'SelectDept'] = function (dept) {
      var newSel = dept ? new Set([dept]) : new Set();
      setSel(newSel);
      _deptUpdateChips(wrap, newSel);
      onApply();
    };
  }

  // Close outside для dropdown
  if (mode === 'dropdown') {
    document.addEventListener(
      'click',
      function (e) {
        var dd = document.getElementById(prefix + 'DeptDropdown');
        var menu = document.getElementById(prefix + 'DeptMenu');
        if (dd && menu && menu.classList.contains('open') && !dd.contains(e.target)) {
          menu.classList.remove('open');
        }
      },
      true,
    );
  }

  return {
    mode: mode,
    refresh: function () {
      var s = getSel();
      if (mode === 'dropdown') {
        _deptUpdateUI(wrap, prefix, mode, multi, depts, s);
      } else {
        _deptUpdateChips(wrap, s);
      }
    },
  };
}

function _deptRenderDropdown(wrap, prefix, depts, sel, multi) {
  var hasFilter = sel.size > 0;
  var label = hasFilter ? (sel.size === 1 ? [...sel][0] : sel.size + ' отд.') : 'Все отделы';
  var fnPfx = prefix || 'shared';
  var inputType = multi ? 'checkbox' : 'radio';
  var html =
    '<div class="dept-dropdown" id="' +
    prefix +
    'DeptDropdown">' +
    '<button class="dept-trigger' +
    (hasFilter ? ' has-filter' : '') +
    '" id="' +
    prefix +
    'DeptTrigger" onclick="' +
    fnPfx +
    'ToggleDeptMenu()">' +
    '<i class="fas fa-building" style="font-size:12px;opacity:0.6"></i> ' +
    '<span id="' +
    prefix +
    'DeptLabel">' +
    escapeHtml(label) +
    '</span> ' +
    (hasFilter && multi ? '<span class="badge-count">' + sel.size + '</span> ' : '') +
    '<i class="fas fa-chevron-down" style="font-size:10px;opacity:0.5;margin-left:2px"></i>' +
    '</button>' +
    '<div class="dept-menu" id="' +
    prefix +
    'DeptMenu">' +
    '<div class="dept-menu-search"><input type="text" placeholder="Поиск отдела..." id="' +
    prefix +
    'DeptSearch" oninput="' +
    fnPfx +
    'FilterDeptList()"></div>' +
    '<div class="dept-menu-items" id="' +
    prefix +
    'DeptMenuItems">';
  depts.forEach(function (d) {
    var checked = sel.has(d) ? ' checked' : '';
    html +=
      '<label class="dept-menu-item" data-dept="' +
      escapeHtml(d) +
      '">' +
      '<input type="' +
      inputType +
      '" name="' +
      prefix +
      'Dept" class="dept-cb" value="' +
      escapeHtml(d) +
      '"' +
      checked +
      ' onchange="' +
      fnPfx +
      'ToggleDeptItem(this)">' +
      '<span>' +
      escapeHtml(d) +
      '</span></label>';
  });
  html +=
    '</div>' +
    '<div class="dept-menu-footer">' +
    '<button class="dm-clear" onclick="' +
    fnPfx +
    'ClearDeptFilter()">Сбросить</button>' +
    '</div></div></div>';
  wrap.innerHTML = html;
}

function _deptRenderChips(wrap, prefix, depts, sel) {
  var fnPfx = prefix || 'shared';
  var html =
    '<span class="pp-dept-chip' +
    (sel.size === 0 ? ' active' : '') +
    '" onclick="' +
    fnPfx +
    'SelectDept(null)">Все</span>';
  depts.forEach(function (d) {
    html +=
      '<span class="pp-dept-chip' +
      (sel.has(d) ? ' active' : '') +
      '" data-dept="' +
      escapeHtml(d) +
      '" onclick="' +
      fnPfx +
      'SelectDept(this.dataset.dept)">' +
      escapeHtml(d) +
      '</span>';
  });
  wrap.innerHTML = html;
}

function _deptUpdateChips(wrap, sel) {
  if (!wrap) return;
  wrap.querySelectorAll('.pp-dept-chip').forEach(function (c) {
    var d = c.dataset.dept;
    if (!d)
      c.classList.toggle('active', sel.size === 0); // "Все"
    else c.classList.toggle('active', sel.has(d));
  });
}

function _deptUpdateUI(wrap, prefix, mode, multi, depts, sel) {
  if (mode === 'chips') {
    _deptUpdateChips(wrap, sel);
    return;
  }
  var trigger = document.getElementById(prefix + 'DeptTrigger');
  var labelEl = document.getElementById(prefix + 'DeptLabel');
  if (!trigger || !labelEl) return;
  var n = sel.size;
  if (n === 0) {
    labelEl.textContent = 'Все отделы';
    trigger.classList.remove('has-filter');
    var badge = trigger.querySelector('.badge-count');
    if (badge) badge.remove();
  } else {
    labelEl.textContent = n === 1 ? [...sel][0] : n + ' отд.';
    trigger.classList.add('has-filter');
    if (multi) {
      let badge = trigger.querySelector('.badge-count');
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'badge-count';
        trigger.insertBefore(badge, trigger.querySelector('.fa-chevron-down'));
      }
      badge.textContent = n;
    }
  }
}

function _deptFilterList(prefix, depts) {
  var q = (document.getElementById(prefix + 'DeptSearch')?.value || '').toLowerCase();
  document.querySelectorAll('#' + prefix + 'DeptMenuItems .dept-menu-item').forEach(function (el) {
    el.style.display = el.dataset.dept.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
  });
}
