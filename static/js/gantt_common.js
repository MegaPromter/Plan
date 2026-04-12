/* ── Общие настройки dhtmlxGantt ────────────────────────────────────────────
 *  Подключается перед модулями plan.js, production_plan.js, enterprise.js.
 *  Предоставляет: загрузку библиотеки, русскую локаль, масштабы,
 *  авто-высоту строк, кастомный resize колонок, сохранение в localStorage.
 * ──────────────────────────────────────────────────────────────────────────── */
'use strict';

// ── Lazy-load библиотеки ──────────────────────────────────────────────────

/**
 * Загружает dhtmlxGantt (CSS + JS), если ещё не загружен.
 * @param {Function} onReady — вызывается когда gantt доступен
 * @param {string} [errorContainerId] — id контейнера для ошибки
 */
function ganttLoad(onReady, errorContainerId) {
  if (typeof gantt !== 'undefined') {
    onReady();
    return;
  }
  // CSS
  if (!document.querySelector('link[href*="dhtmlxgantt.css"]')) {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = '/static/lib/dhtmlxgantt/dhtmlxgantt.css';
    document.head.appendChild(css);
  }
  // JS
  const script = document.createElement('script');
  script.src = '/static/lib/dhtmlxgantt/dhtmlxgantt.js';
  script.onload = onReady;
  script.onerror = () => {
    const el = errorContainerId && document.getElementById(errorContainerId);
    if (el)
      el.innerHTML =
        '<div style="padding:40px;text-align:center;color:var(--muted);">' +
        '⚠ Библиотека dhtmlxGantt не загружена.</div>';
  };
  document.head.appendChild(script);
}

// ── Русская локаль ────────────────────────────────────────────────────────

function ganttApplyLocaleRu() {
  if (typeof gantt === 'undefined') return;
  gantt.locale = {
    date: {
      month_full: [
        'Январь',
        'Февраль',
        'Март',
        'Апрель',
        'Май',
        'Июнь',
        'Июль',
        'Август',
        'Сентябрь',
        'Октябрь',
        'Ноябрь',
        'Декабрь',
      ],
      month_short: [
        'Янв',
        'Фев',
        'Мар',
        'Апр',
        'Май',
        'Июн',
        'Июл',
        'Авг',
        'Сен',
        'Окт',
        'Ноя',
        'Дек',
      ],
      day_full: ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'],
      day_short: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'],
    },
    labels: {
      new_task: 'Новая задача',
      icon_save: 'Сохранить',
      icon_cancel: 'Отмена',
      icon_details: 'Детали',
      icon_edit: 'Редактировать',
      icon_delete: 'Удалить',
      confirm_closing: '',
      confirm_deleting: 'Удалить запись?',
      section_description: 'Описание',
      section_time: 'Период',
      section_type: 'Тип',
      column_text: 'Задача',
      column_start_date: 'Начало',
      column_duration: 'Длительность',
      column_add: '',
      link: 'Связь',
      confirm_link_deleting: 'Удалить связь?',
      link_start: '(начало)',
      link_end: '(конец)',
      type_task: 'Задача',
      type_project: 'Проект',
      type_milestone: 'Веха',
      minutes: 'мин',
      hours: 'ч',
      days: 'дн',
      weeks: 'нед',
      months: 'мес',
      years: 'лет',
    },
  };
}

// ── Масштабы (scales API v9) ──────────────────────────────────────────────

/**
 * Применяет масштаб к gantt и сохраняет в localStorage.
 * @param {string} scale — day|week|month|year
 * @param {string} [storageKey] — ключ localStorage (по умолчанию 'gantt_scale')
 * @param {string} [btnContainerSel] — CSS-селектор контейнера кнопок масштаба
 */
function ganttSetScale(scale, storageKey, btnContainerSel) {
  if (typeof gantt === 'undefined') return;
  if (storageKey) localStorage.setItem(storageKey, scale);

  // Подсветка кнопок
  if (btnContainerSel) {
    document
      .querySelectorAll(btnContainerSel + ' [data-scale]')
      .forEach((b) => b.classList.toggle('active', b.dataset.scale === scale));
    // Fallback для onclick-кнопок без data-scale
    document.querySelectorAll(btnContainerSel + ' .btn').forEach((b) => {
      const m = b.getAttribute('onclick')?.match(/Scale\('(\w+)'/);
      if (m) b.classList.toggle('active', m[1] === scale);
    });
  }

  switch (scale) {
    case 'day':
      gantt.config.scales = [
        { unit: 'month', step: 1, format: '%M %Y' },
        { unit: 'day', step: 1, format: '%d' },
      ];
      gantt.config.min_column_width = 28;
      break;
    case 'week':
      gantt.config.scales = [
        { unit: 'month', step: 1, format: '%M %Y' },
        { unit: 'week', step: 1, format: '%d' },
      ];
      gantt.config.min_column_width = 60;
      break;
    case 'month':
      gantt.config.scales = [
        { unit: 'year', step: 1, format: '%Y' },
        { unit: 'month', step: 1, format: '%M' },
      ];
      gantt.config.min_column_width = 50;
      break;
    case 'year':
      gantt.config.scales = [{ unit: 'year', step: 1, format: '%Y' }];
      gantt.config.min_column_width = 80;
      break;
  }

  gantt.render();
}

/** Восстановить масштаб из localStorage (без render — вызывать до init/parse). */
function ganttRestoreScale(storageKey) {
  const scale = localStorage.getItem(storageKey || 'gantt_scale') || 'year';
  switch (scale) {
    case 'day':
      gantt.config.scales = [
        { unit: 'month', step: 1, format: '%M %Y' },
        { unit: 'day', step: 1, format: '%d' },
      ];
      gantt.config.min_column_width = 28;
      break;
    case 'week':
      gantt.config.scales = [
        { unit: 'month', step: 1, format: '%M %Y' },
        { unit: 'week', step: 1, format: '%d' },
      ];
      gantt.config.min_column_width = 60;
      break;
    case 'month':
      gantt.config.scales = [
        { unit: 'year', step: 1, format: '%Y' },
        { unit: 'month', step: 1, format: '%M' },
      ];
      gantt.config.min_column_width = 50;
      break;
    default: // year
      gantt.config.scales = [{ unit: 'year', step: 1, format: '%Y' }];
      gantt.config.min_column_width = 80;
  }
  return scale;
}

// ── Общие настройки (readonly) ────────────────────────────────────────────

/**
 * Базовая настройка gantt (локаль, формат дат, smart rendering off).
 * Вызывать ПЕРЕД gantt.init().
 */
function ganttSetupBase() {
  if (typeof gantt === 'undefined') return;
  ganttApplyLocaleRu();
  gantt.config.date_format = '%Y-%m-%d';
  gantt.config.smart_rendering = false;
  gantt.config.fit_tasks = true;
  gantt.config.open_tree_initially = true;
  // Tooltip
  gantt.config.tooltip_offset_x = 10;
  gantt.config.tooltip_offset_y = 20;
  gantt.templates.tooltip_text = function (start, end, task) {
    return (
      '<b>' +
      task.text +
      '</b><br/>' +
      gantt.templates.tooltip_date_format(start) +
      ' — ' +
      gantt.templates.tooltip_date_format(end)
    );
  };
}

// ── Авто-высота строк (перенос текста) ────────────────────────────────────

/**
 * Подсчитывает высоту каждой строки по длине текста и задаёт task.row_height.
 * Вызывать ПОСЛЕ gantt.parse(), ПЕРЕД gantt.render().
 * @param {number} [colWidth] — ширина текстовой колонки (по умолчанию берёт из config)
 */
function ganttAutoFitRowHeights() {
  if (typeof gantt === 'undefined') return;
  const _skipCols = new Set(['add', 'start_date', 'end_date', 'duration']);
  const cols = gantt.config.columns.filter((c) => !_skipCols.has(c.name));
  const measure = document.createElement('div');
  measure.style.cssText =
    'position:absolute;visibility:hidden;white-space:normal;word-break:break-word;' +
    'line-height:1.4;font:inherit;padding:4px 0;box-sizing:border-box;';
  document.body.appendChild(measure);

  gantt.eachTask((task) => {
    let maxH = 36;
    cols.forEach((col) => {
      const val = col.name === 'text' ? task.text : task[col.name] || '';
      if (!val) return;
      measure.style.width = col.width - 28 + 'px';
      measure.textContent = val;
      maxH = Math.max(maxH, measure.offsetHeight + 16);
    });
    task.row_height = maxH;
  });
  document.body.removeChild(measure);
}

// ── Сохранение/загрузка ширин колонок ─────────────────────────────────────

function ganttLoadColWidths(storageKey, defaults) {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    if (saved) return { ...defaults, ...saved };
  } catch (e) {
    /* ignore */
  }
  return { ...defaults };
}

function ganttSaveColWidths(storageKey) {
  if (typeof gantt === 'undefined') return;
  const data = { grid: gantt.config.grid_width };
  gantt.config.columns.forEach((c) => {
    data[c.name] = c.width;
  });
  localStorage.setItem(storageKey, JSON.stringify(data));
}

// ── Кастомный resize колонок (GPL не поддерживает встроенный) ──────────────

let _ganttResizing = false;

function ganttInjectResizers(containerId, colStorageKey) {
  if (_ganttResizing) return;
  const container = document.getElementById(containerId);
  if (!container) return;
  container.querySelectorAll('.gantt-col-resizer, .gantt-grid-resizer').forEach((r) => r.remove());

  // Resize колонок
  const headerRow = container.querySelector('.gantt_grid_scale');
  if (headerRow) {
    const cells = headerRow.querySelectorAll('.gantt_grid_head_cell');
    cells.forEach((cell, idx) => {
      if (idx >= cells.length - 1) return;
      const handle = document.createElement('div');
      handle.className = 'gantt-col-resizer';
      cell.style.position = 'relative';
      cell.appendChild(handle);
      _ganttAttachColResize(handle, idx, containerId, colStorageKey);
    });
  }

  // Resize grid ↔ timeline
  const grid = container.querySelector('.gantt_grid');
  if (grid) {
    const splitter = document.createElement('div');
    splitter.className = 'gantt-grid-resizer';
    grid.style.position = 'relative';
    grid.appendChild(splitter);
    _ganttAttachGridSplitter(splitter, grid, containerId, colStorageKey);
  }
}

function _ganttAttachColResize(handle, colIdx, containerId, storageKey) {
  let startX, startW;
  handle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    startX = e.clientX;
    startW = gantt.config.columns[colIdx].width;
    _ganttResizing = true;
    const onMove = (ev) => {
      const delta = ev.clientX - startX;
      const newW = Math.max(40, startW + delta);
      gantt.config.columns[colIdx].width = newW;
      gantt.config.grid_width = gantt.config.columns.reduce((s, c) => s + c.width, 0);
      gantt.render();
    };
    const onUp = () => {
      _ganttResizing = false;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (storageKey) ganttSaveColWidths(storageKey);
      ganttInjectResizers(containerId, storageKey);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

function _ganttAttachGridSplitter(splitter, grid, containerId, storageKey) {
  let startX, startColW;
  splitter.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    startX = e.clientX;
    const lastCol = gantt.config.columns[gantt.config.columns.length - 1];
    startColW = lastCol.width;
    const startGridW = grid.offsetWidth;
    _ganttResizing = true;
    const onMove = (ev) => {
      const delta = ev.clientX - startX;
      const newColW = Math.max(40, startColW + delta);
      lastCol.width = newColW;
      gantt.config.grid_width = startGridW - startColW + newColW;
      gantt.render();
    };
    const onUp = () => {
      _ganttResizing = false;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (storageKey) ganttSaveColWidths(storageKey);
      ganttInjectResizers(containerId, storageKey);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

// ── Утилита: Date → "YYYY-MM-DD" ─────────────────────────────────────────

function ganttFormatDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
}
