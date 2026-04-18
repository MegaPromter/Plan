/**
 * Общий ресайзер колонок таблицы.
 *
 * Идея: на каждый <th>, в котором есть <div class="col-resize" data-col="КЛЮЧ">,
 * вешается drag-хэндлер. Во время перетаскивания меняется ширина колонки. По
 * mouseup ширина пишется в /api/col_settings/ под ключом `<префикс_таблицы>_<КЛЮЧ>`.
 *
 * Префикс таблицы берётся из `data-col-table` на самом <table> (plan, pp,
 * journal, ...). Благодаря префиксу одна и та же настройка `col_settings`
 * хранит ширины для всех таблиц программы, но без конфликтов между ними.
 *
 * ── Важно про <colgroup> ───────────────────────────────────────────────
 * В `table-layout: fixed` ширины колонок диктуются ЛИБО первой строкой
 * thead (и только ей!), ЛИБО элементами <col> в <colgroup>. Если в шапке
 * есть colspan-заголовки (например «Группа» накрывает две колонки), то
 * задавать ширины через <th> во второй строке thead бесполезно — браузер
 * их проигнорирует, и подколонки «плывут». Поэтому модуль работает так:
 *   — если у таблицы <colgroup> есть — пишем в <col>;
 *   — если нет — создаём его автоматически перед drag, собирая колонки
 *     по `data-col-idx` (или по последовательности первой строки с учётом
 *     colspan), и дальше всегда пишем ширины в <col>.
 *
 * На время drag форсим `table-layout: fixed`, чтобы ширины из <colgroup>
 * соблюдались буквально. Без фиксации текущих ширин соседних колонок
 * они расползаются (остаток делится пропорционально), поэтому перед
 * drag снимаем offsetWidth каждой колонки и записываем в <col>.
 *
 * API:
 *   attachColResize(table, { onResize }) — инициализирует drag на всех
 *     ручках внутри таблицы; возвращает функцию detach().
 *   applyColWidths(table, colSettings)  — применяет сохранённые ширины
 *     к заголовкам (читает те же ключи `<prefix>_<col>`).
 */
(function (global) {
  'use strict';

  // ── Единая точка доступа к CSRF и заголовкам ────────────────────────────
  function _headers() {
    if (typeof global.apiHeaders === 'function') return global.apiHeaders();
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    const h = { 'Content-Type': 'application/json' };
    if (m) h['X-CSRFToken'] = decodeURIComponent(m[1]);
    return h;
  }

  // ── Буфер отправки (дебаунс) ────────────────────────────────────────────
  let _pendingPatch = {};
  let _pendingTimer = null;

  function _queueSave(key, width) {
    _pendingPatch[key] = { width };
    if (_pendingTimer) clearTimeout(_pendingTimer);
    _pendingTimer = setTimeout(_flushSave, 400);
  }

  async function _flushSave() {
    _pendingTimer = null;
    const patch = _pendingPatch;
    _pendingPatch = {};
    if (!Object.keys(patch).length) return;
    try {
      await fetch('/api/col_settings/', {
        method: 'POST',
        headers: _headers(),
        body: JSON.stringify(patch),
      });
    } catch (e) {
      console.error('[col_resize] saveColSettings error:', e);
    }
  }

  // ── Утилиты ─────────────────────────────────────────────────────────────
  function _tablePrefix(table) {
    return table.dataset.colTable || '';
  }
  function _settingKey(prefix, col) {
    return prefix ? `${prefix}_${col}` : col;
  }
  function _minWidth(th) {
    const m = parseInt(th.dataset.colMin || '', 10);
    return Number.isFinite(m) && m > 0 ? m : 60;
  }

  /**
   * Посчитать суммарное число колонок в таблице по первой строке thead.
   * Учитывает colspan каждой ячейки.
   */
  function _totalCols(table) {
    const thead = table.tHead;
    if (!thead || !thead.rows[0]) return 0;
    let n = 0;
    for (const th of thead.rows[0].cells) {
      n += parseInt(th.getAttribute('colspan') || '1', 10) || 1;
    }
    return n;
  }

  /**
   * Убедиться, что у таблицы есть <colgroup> с нужным числом <col>.
   * Если нет — создаёт и вставляет первым элементом в таблицу.
   * Возвращает colgroup.
   */
  function _ensureColgroup(table) {
    let colgroup = table.querySelector(':scope > colgroup');
    const total = _totalCols(table);
    if (!colgroup) {
      colgroup = document.createElement('colgroup');
      for (let i = 0; i < total; i++) colgroup.appendChild(document.createElement('col'));
      // colgroup должен идти первым (до thead)
      table.insertBefore(colgroup, table.firstChild);
    } else {
      // Досоздаём недостающие <col>, если нужно
      while (colgroup.children.length < total) {
        colgroup.appendChild(document.createElement('col'));
      }
    }
    return colgroup;
  }

  /**
   * Индекс колонки (для <col> в colgroup) для данного <th>.
   * Приоритет: data-col-idx (в шаблоне СП задан явно) → позиция в своей
   * строке thead с учётом colspan предыдущих и «занятых» слотов из rowspan.
   */
  function _colIdxForTh(table, th) {
    if (th.dataset.colIdx !== undefined) {
      const i = parseInt(th.dataset.colIdx, 10);
      if (Number.isFinite(i) && i >= 0) return i;
    }
    // Фоллбэк: считаем «матрицу» thead и ищем позицию нашей th.
    const thead = table.tHead;
    if (!thead) return th.cellIndex;
    // grid[rowIdx][colIdx] = { th }
    const grid = [];
    for (let r = 0; r < thead.rows.length; r++) grid.push([]);
    for (let r = 0; r < thead.rows.length; r++) {
      const row = thead.rows[r];
      let c = 0;
      for (const cell of row.cells) {
        while (grid[r][c]) c++;
        const cs = parseInt(cell.getAttribute('colspan') || '1', 10) || 1;
        const rs = parseInt(cell.getAttribute('rowspan') || '1', 10) || 1;
        for (let dr = 0; dr < rs; dr++) {
          for (let dc = 0; dc < cs; dc++) {
            if (!grid[r + dr]) grid[r + dr] = [];
            grid[r + dr][c + dc] = { th: cell };
          }
        }
        if (cell === th) return c;
        c += cs;
      }
    }
    return th.cellIndex;
  }

  /**
   * Зафиксировать текущие ширины всех одинарных колонок thead в <colgroup>.
   *
   * В table-layout:fixed браузер распределяет ширину пропорционально между
   * колонками без явной width. Тянем одну — соседи сжимаются. Поэтому
   * перед drag снимаем offsetWidth у каждой th с colspan=1 (включая
   * субколонки второго ряда) и записываем в соответствующий <col>.
   */
  function _lockCurrentWidths(table, draggedTh) {
    const thead = table.tHead;
    if (!thead) return null;
    const colgroup = _ensureColgroup(table);
    for (const row of thead.rows) {
      for (const th of row.cells) {
        const span = parseInt(th.getAttribute('colspan') || '1', 10) || 1;
        if (span !== 1) continue; // colspan-шапки пропускаем
        if (th === draggedTh) continue;
        const w = th.offsetWidth;
        if (!w) continue;
        const idx = _colIdxForTh(table, th);
        const col = colgroup.children[idx];
        if (col && !col.style.width) col.style.width = w + 'px';
      }
    }
    return colgroup;
  }

  /**
   * Применить сохранённые ширины к колонкам таблицы (через <colgroup>).
   */
  function applyColWidths(table, colSettings) {
    if (!table || !colSettings) return;
    const prefix = _tablePrefix(table);
    const handles = table.querySelectorAll('th .col-resize[data-col]');
    if (!handles.length) return;
    const colgroup = _ensureColgroup(table);
    handles.forEach((handle) => {
      const th = handle.closest('th');
      if (!th) return;
      const col = handle.dataset.col;
      const key = _settingKey(prefix, col);
      const val = colSettings[key];
      if (val && val.width) {
        const w = Math.max(val.width, _minWidth(th));
        const idx = _colIdxForTh(table, th);
        const colEl = colgroup.children[idx];
        if (colEl) colEl.style.width = w + 'px';
      }
    });
  }

  /**
   * Навесить drag-хэндлеры ресайза на все ручки внутри таблицы.
   *
   * @param {HTMLTableElement} table
   * @param {Object} [opts]
   * @param {(col: string, widthPx: number) => void} [opts.onResize]
   * @returns {() => void} функция отвязки всех обработчиков
   */
  function attachColResize(table, opts) {
    opts = opts || {};
    const prefix = _tablePrefix(table);
    const cleanups = [];

    table.querySelectorAll('th .col-resize[data-col]').forEach((handle) => {
      const th = handle.closest('th');
      if (!th) return;
      const col = handle.dataset.col;

      function onDown(e) {
        e.preventDefault();
        const startX = e.clientX;
        const startW = th.offsetWidth;
        let raf = null;
        let pending = startW;

        // Форсим table-layout:fixed — в auto-layout заданная ширина
        // уважается лишь как подсказка, таблица подгоняется под контейнер.
        // В fixed ширины соблюдаются буквально через <colgroup>.
        if (getComputedStyle(table).tableLayout !== 'fixed') {
          table.style.tableLayout = 'fixed';
        }
        // Замораживаем соседей — чтобы они не расползались.
        const colgroup = _lockCurrentWidths(table, th);

        // Цель записи — <col> нужной колонки.
        const colIdx = _colIdxForTh(table, th);
        const colEl = colgroup ? colgroup.children[colIdx] : null;

        function applyWidth(w) {
          if (colEl) colEl.style.width = w + 'px';
          if (typeof opts.onResize === 'function') {
            try {
              opts.onResize(col, w);
            } catch (err) {
              console.error(err);
            }
          }
        }

        function onMove(ev) {
          const delta = ev.clientX - startX;
          pending = Math.max(_minWidth(th), startW + delta);
          if (raf) return;
          raf = requestAnimationFrame(() => {
            raf = null;
            applyWidth(pending);
          });
        }

        function onUp() {
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          _queueSave(_settingKey(prefix, col), pending);
        }

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
      }

      handle.addEventListener('mousedown', onDown);
      cleanups.push(() => handle.removeEventListener('mousedown', onDown));
    });

    return function detach() {
      cleanups.forEach((fn) => fn());
    };
  }

  // Экспорт — глобально, чтобы все SPA-файлы могли дёрнуть без модулей.
  global.ColResize = {
    attach: attachColResize,
    apply: applyColWidths,
    _flush: _flushSave, // для тестов
  };
})(window);
