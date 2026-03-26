/**
 * Мульти-колоночные фильтры для таблиц.
 * Аналог dropdown checkbox фильтров из Flask plan.html.
 *
 * Использование:
 *   const filter = new ColumnFilter({
 *       container: '#filter-row',
 *       columns: ['task_type', 'dept', 'sector', 'executor'],
 *       data: allTasks,
 *       onChange: (filters) => { renderFilteredTable(filters); },
 *   });
 */

class ColumnFilter {
    constructor(options) {
        this.container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;
        this.columns = options.columns || [];
        this.onChange = options.onChange || (() => {});
        this.activeFilters = {};
        this._dropdowns = {};
        // Единый обработчик закрытия дропдаунов по клику вне (один раз)
        document.addEventListener('click', () => {
            Object.values(this._dropdowns).forEach(dd => dd.style.display = 'none');
        });
    }

    /**
     * Обновляет доступные значения фильтров на основе данных.
     * @param {Array} data — массив объектов (задач/строк)
     */
    updateValues(data) {
        this.columns.forEach(col => {
            const values = new Set();
            data.forEach(row => {
                const v = row[col];
                if (v !== null && v !== undefined && v !== '') {
                    values.add(String(v));
                }
            });
            const sorted = Array.from(values).sort();
            this._renderDropdown(col, sorted);
        });
    }

    /**
     * Проверяет, проходит ли строка через все активные фильтры.
     */
    matches(row) {
        for (const [col, selected] of Object.entries(this.activeFilters)) {
            if (selected.size === 0) continue;
            const val = String(row[col] || '');
            if (!selected.has(val)) return false;
        }
        return true;
    }

    /**
     * Сбросить все фильтры.
     */
    reset() {
        this.activeFilters = {};
        Object.values(this._dropdowns).forEach(dd => {
            dd.querySelectorAll('input[type=checkbox]').forEach(cb => {
                cb.checked = false;
            });
        });
        this.onChange(this.activeFilters);
    }

    /**
     * Возвращает текущее состояние фильтров (сериализуемое).
     */
    getState() {
        const state = {};
        for (const [col, selected] of Object.entries(this.activeFilters)) {
            if (selected.size > 0) {
                state[col] = Array.from(selected);
            }
        }
        return state;
    }

    /**
     * Восстанавливает состояние фильтров из объекта.
     */
    setState(state) {
        this.activeFilters = {};
        for (const [col, vals] of Object.entries(state)) {
            this.activeFilters[col] = new Set(vals);
        }
        // Обновить чекбоксы в UI
        Object.entries(this._dropdowns).forEach(([col, dd]) => {
            const selected = this.activeFilters[col] || new Set();
            dd.querySelectorAll('input[type=checkbox]').forEach(cb => {
                cb.checked = selected.has(cb.value);
            });
        });
        this.onChange(this.activeFilters);
    }

    _renderDropdown(col, values) {
        const th = this.container.querySelector(`[data-filter-col="${col}"]`);
        if (!th) return;

        th.innerHTML = '';
        th.style.position = 'relative';

        // Кнопка фильтра
        const btn = document.createElement('button');
        btn.className = 'filter-btn';
        btn.innerHTML = '<i class="fas fa-filter" style="font-size:10px;opacity:0.5;"></i>';
        btn.style.cssText = `
            background: none; border: 1px solid rgba(255,255,255,0.1);
            color: var(--muted, #64748b); padding: 2px 6px; border-radius: 4px;
            cursor: pointer; font-size: 11px; transition: all 0.15s;
        `;

        // Отметить активный фильтр
        if (this.activeFilters[col] && this.activeFilters[col].size > 0) {
            btn.style.borderColor = 'var(--accent, #3b82f6)';
            btn.style.color = 'var(--accent, #3b82f6)';
        }

        // Dropdown
        const dropdown = document.createElement('div');
        dropdown.className = 'filter-dropdown';
        dropdown.style.cssText = `
            display: none; position: absolute; top: 100%; left: 0;
            z-index: 5000; background: var(--surface, #161b27);
            border: 1px solid rgba(255,255,255,0.1); border-radius: 8px;
            padding: 8px; min-width: 180px; max-height: 300px;
            overflow-y: auto; box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        `;

        // Поиск в фильтре
        const search = document.createElement('input');
        search.type = 'text';
        search.placeholder = 'Поиск...';
        search.style.cssText = `
            width: 100%; padding: 4px 8px; font-size: 12px; margin-bottom: 6px;
            background: var(--surface2, #1e2536); color: var(--text, #e2e8f0);
            border: 1px solid rgba(255,255,255,0.1); border-radius: 4px;
            outline: none; box-sizing: border-box;
        `;
        dropdown.appendChild(search);

        // Чекбоксы
        const checkboxContainer = document.createElement('div');
        const selected = this.activeFilters[col] || new Set();

        values.forEach(val => {
            const label = document.createElement('label');
            label.style.cssText = `
                display: flex; align-items: center; gap: 6px;
                padding: 3px 4px; font-size: 12px; color: var(--text, #e2e8f0);
                cursor: pointer; border-radius: 3px; white-space: nowrap;
            `;
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = val;
            cb.checked = selected.has(val);
            cb.addEventListener('change', () => {
                if (!this.activeFilters[col]) {
                    this.activeFilters[col] = new Set();
                }
                if (cb.checked) {
                    this.activeFilters[col].add(val);
                } else {
                    this.activeFilters[col].delete(val);
                }
                // Обновить стиль кнопки
                if (this.activeFilters[col].size > 0) {
                    btn.style.borderColor = 'var(--accent, #3b82f6)';
                    btn.style.color = 'var(--accent, #3b82f6)';
                } else {
                    btn.style.borderColor = 'rgba(255,255,255,0.1)';
                    btn.style.color = 'var(--muted, #64748b)';
                }
                this.onChange(this.activeFilters);
            });
            label.appendChild(cb);
            label.appendChild(document.createTextNode(val));
            checkboxContainer.appendChild(label);
        });

        dropdown.appendChild(checkboxContainer);

        // Поиск
        search.addEventListener('input', () => {
            const q = search.value.toLowerCase();
            checkboxContainer.querySelectorAll('label').forEach(l => {
                l.style.display = l.textContent.toLowerCase().includes(q) ? '' : 'none';
            });
        });

        this._dropdowns[col] = dropdown;

        // Открытие/закрытие
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = dropdown.style.display !== 'none';
            // Закрыть все
            Object.values(this._dropdowns).forEach(dd => dd.style.display = 'none');
            if (!isOpen) {
                dropdown.style.display = 'block';
                search.focus();
            }
        });

        dropdown.addEventListener('click', (e) => e.stopPropagation());

        th.appendChild(btn);
        th.appendChild(dropdown);
    }
}


// ── Saved Filter Presets ──────────────────────────────────────────────────────
// Хранит именованные пресеты фильтров в localStorage, сгруппированные по pageKey.
// Каждая страница (plan, production_plan) передаёт свои getState/applyState колбэки.

const FILTER_PRESETS_KEY = 'filter_presets';

function _fpGetAll() {
  try { return JSON.parse(localStorage.getItem(FILTER_PRESETS_KEY) || '{}'); }
  catch(e) { return {}; }
}
function _fpSaveAll(all) {
  localStorage.setItem(FILTER_PRESETS_KEY, JSON.stringify(all));
}

function getFilterPresets(pageKey) {
  return _fpGetAll()[pageKey] || [];
}

function saveFilterPreset(pageKey, name, filterState) {
  const all = _fpGetAll();
  if (!all[pageKey]) all[pageKey] = [];
  all[pageKey].push({
    id: Date.now(),
    name: name,
    state: filterState,
    created: new Date().toISOString()
  });
  _fpSaveAll(all);
}

function deleteFilterPreset(pageKey, presetId) {
  const all = _fpGetAll();
  if (!all[pageKey]) return;
  all[pageKey] = all[pageKey].filter(p => p.id !== presetId);
  _fpSaveAll(all);
}

/**
 * Инициализирует UI пресетов: вставляет кнопку «Пресеты» в указанный контейнер.
 *
 * @param {string} pageKey        — ключ страницы ('plan', 'production_plan')
 * @param {string} containerId    — id элемента-обёртки для кнопки
 * @param {Function} getStateFn   — () => Object — возвращает текущее состояние фильтров
 * @param {Function} applyStateFn — (stateObj) => void — применяет пресет
 */
function initFilterPresets(pageKey, containerId, getStateFn, applyStateFn) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = '';
  container.classList.add('filter-presets-wrap');

  // Кнопка «Пресеты»
  const btn = document.createElement('button');
  btn.className = 'btn btn-outline btn-sm filter-presets-btn';
  btn.innerHTML = '<i class="fas fa-bookmark"></i> Пресеты';
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('open');
    if (dropdown.classList.contains('open')) _renderList();
  });

  // Dropdown
  const dropdown = document.createElement('div');
  dropdown.className = 'filter-presets-dropdown';
  dropdown.addEventListener('click', (e) => e.stopPropagation());

  // Закрытие по клику вне
  document.addEventListener('click', () => dropdown.classList.remove('open'));

  container.appendChild(btn);
  container.appendChild(dropdown);

  function _renderList() {
    const presets = getFilterPresets(pageKey);
    let html = '<div class="filter-presets-header">Сохранённые пресеты</div>';

    if (presets.length === 0) {
      html += '<div class="filter-presets-empty">Нет сохранённых пресетов</div>';
    } else {
      html += '<div class="filter-presets-list">';
      presets.forEach(p => {
        const date = new Date(p.created).toLocaleDateString('ru-RU', {day:'numeric', month:'short'});
        html += `<div class="filter-preset-item" data-id="${p.id}">
          <span class="filter-preset-name" title="${_fpEsc(p.name)}">${_fpEsc(p.name)}</span>
          <span class="filter-preset-date">${date}</span>
          <button class="filter-preset-delete" title="Удалить" data-id="${p.id}"><i class="fas fa-times"></i></button>
        </div>`;
      });
      html += '</div>';
    }

    html += `<div class="filter-presets-footer">
      <div class="filter-presets-save-row">
        <input class="filter-presets-input" type="text" placeholder="Название пресета..." maxlength="50">
        <button class="btn btn-primary btn-sm filter-presets-save-btn"><i class="fas fa-save"></i></button>
      </div>
    </div>`;

    dropdown.innerHTML = html;

    // Обработчик клика по пресету (применить)
    dropdown.querySelectorAll('.filter-preset-item').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.closest('.filter-preset-delete')) return;
        const id = parseInt(item.dataset.id);
        const preset = presets.find(p => p.id === id);
        if (preset) {
          applyStateFn(preset.state);
          dropdown.classList.remove('open');
        }
      });
    });

    // Обработчик удаления
    dropdown.querySelectorAll('.filter-preset-delete').forEach(del => {
      del.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = parseInt(del.dataset.id);
        deleteFilterPreset(pageKey, id);
        _renderList();
      });
    });

    // Обработчик сохранения
    const input = dropdown.querySelector('.filter-presets-input');
    const saveBtn = dropdown.querySelector('.filter-presets-save-btn');
    function doSave() {
      const name = input.value.trim();
      if (!name) { input.focus(); return; }
      const state = getStateFn();
      saveFilterPreset(pageKey, name, state);
      _renderList();
    }
    saveBtn.addEventListener('click', doSave);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') doSave();
    });
  }
}

function _fpEsc(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
