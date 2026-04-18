/**
 * Inline-редактирование ячеек таблицы (одиночный клик на td → поле ввода).
 *
 * Использование:
 *   <td data-field="work_name" data-id="123" data-editable="true">Текст</td>
 *
 *   InlineEditor.init({
 *       table: '#my-table',
 *       saveUrl: (id) => `/api/tasks/${id}/`,
 *       method: 'PUT',
 *       onSave: (id, field, value, resp) => { ... },
 *       fieldTypes: { dept: 'select', date_start: 'date', executor: 'autocomplete' },
 *       fieldOptions: { dept: [{value:'021', label:'021'}, ...] },
 *   });
 */

const InlineEditor = {
  _active: null, // текущий редактируемый элемент

  init(options) {
    const {
      table,
      saveUrl,
      method = 'PUT',
      onSave = null,
      onError = null,
      fieldTypes = {},
      fieldOptions = {},
    } = options;

    const tableEl = typeof table === 'string' ? document.querySelector(table) : table;
    if (!tableEl) return;

    this._options = options;

    tableEl.addEventListener('click', (e) => {
      const td = e.target.closest('[data-editable="true"]');
      if (!td || this._active === td) return;

      // Закрыть предыдущий
      if (this._active) this._finishEdit(this._active, false);

      this._startEdit(td);
    });
  },

  _startEdit(td) {
    const field = td.dataset.field;
    const id = td.dataset.id;
    const currentValue = td.dataset.value || td.textContent.trim();
    const fieldType = this._options.fieldTypes[field] || 'text';

    this._active = td;
    td.dataset.originalValue = currentValue;
    td.dataset.originalHtml = td.innerHTML;

    let input;
    if (fieldType === 'select') {
      input = document.createElement('select');
      const opts = this._options.fieldOptions[field] || [];
      input.innerHTML =
        '<option value="">—</option>' +
        opts
          .map(
            (o) =>
              `<option value="${o.value}" ${o.value === currentValue ? 'selected' : ''}>${o.label || o.value}</option>`,
          )
          .join('');
    } else if (fieldType === 'date') {
      input = document.createElement('input');
      input.type = 'date';
      input.value = currentValue || '';
      if (field === 'date_issued' || field === 'date_accepted') {
        input.max = new Date().toISOString().slice(0, 10);
      }
    } else if (fieldType === 'number') {
      input = document.createElement('input');
      input.type = 'number';
      input.step = 'any';
      input.value = currentValue || '';
    } else if (fieldType === 'textarea') {
      input = document.createElement('textarea');
      input.rows = 3;
      input.value = currentValue || '';
    } else {
      input = document.createElement('input');
      input.type = 'text';
      input.value = currentValue === '—' ? '' : currentValue || '';
    }

    input.className = 'inline-edit-input';
    input.style.cssText = `
            width: 100%; padding: 4px 6px; font-size: 13px;
            background: var(--surface2, #1e2536); color: var(--text, #e2e8f0);
            border: 1px solid var(--accent, #3b82f6); border-radius: 4px;
            outline: none; box-sizing: border-box;
        `;

    td.innerHTML = '';
    td.appendChild(input);
    input.focus();
    if (input.select) input.select();

    // Blur — сохранить
    input.addEventListener('blur', () => {
      this._finishEdit(td, true);
    });

    // Enter — сохранить, Escape — отменить
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && fieldType !== 'textarea') {
        e.preventDefault();
        input.blur();
      } else if (e.key === 'Escape') {
        this._finishEdit(td, false);
      }
    });
  },

  async _finishEdit(td, save) {
    if (this._active !== td) return;
    this._active = null;

    const input = td.querySelector('input, select, textarea');
    if (!input) return;

    const newValue = input.value;
    const originalValue = td.dataset.originalValue;
    const originalHtml = td.dataset.originalHtml;

    if (!save || newValue === originalValue) {
      // Отмена — вернуть оригинал
      td.innerHTML = originalHtml;
      return;
    }

    // Показать новое значение
    td.textContent = newValue || '—';
    td.dataset.value = newValue;

    // Сохранить через API
    const field = td.dataset.field;
    const id = td.dataset.id;
    const url = this._options.saveUrl(id);
    const body = { [field]: newValue };

    // Добавить updated_at для optimistic locking
    const row = td.closest('tr');
    if (row && row.dataset.updatedAt) {
      body.updated_at = row.dataset.updatedAt;
    }

    const resp = await fetchJson(url, {
      method: this._options.method || 'PUT',
      body: JSON.stringify(body),
    });

    if (resp._error || resp._conflict) {
      // Ошибка — вернуть оригинал
      td.innerHTML = originalHtml;
      if (this._options.onError) {
        this._options.onError(id, field, newValue, resp);
      }
    } else {
      // Обновить updated_at в строке
      if (resp.updated_at && row) {
        row.dataset.updatedAt = resp.updated_at;
      }
      // Зелёный flash — визуальное подтверждение сохранения
      if (td) {
        td.style.transition = 'background 0.15s';
        td.style.background = 'rgba(34,197,94,0.15)';
        setTimeout(function () {
          td.style.background = '';
        }, 600);
      }
      if (this._options.onSave) {
        this._options.onSave(id, field, newValue, resp);
      }
    }
  },
};
