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

        // Закрыть по клику вне
        document.addEventListener('click', () => {
            dropdown.style.display = 'none';
        });
        dropdown.addEventListener('click', (e) => e.stopPropagation());

        th.appendChild(btn);
        th.appendChild(dropdown);
    }
}
