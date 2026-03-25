/* ========================================================================
   Производственный план — SPA
   Логика: лендинг со списком ПП-проектов + таблица строк с инлайн-редактированием
   ======================================================================== */

// Калибровка sticky top для filter-row (после того как таблица стала видимой)
function _fixFilterRowTop() {
  var tbl = document.querySelector('.pp-table');
  if (!tbl) return;
  var headerRow = tbl.querySelector('thead tr:first-child');
  var filterRow = tbl.querySelector('thead tr.filter-row');
  if (!headerRow || !filterRow) return;
  var h = headerRow.getBoundingClientRect().height;
  if (h < 1) return; // таблица ещё скрыта
  var ths = filterRow.querySelectorAll('th');
  for (var i = 0; i < ths.length; i++) ths[i].style.top = h + 'px';
}

// escapeJs() — в utils.js

// Конфигурация страницы (подставляется Django-шаблоном через JSON-блок)
const _ppCfg = JSON.parse(document.getElementById('pp-config').textContent);
const IS_WRITER = _ppCfg.isWriter;
const IS_ADMIN  = _ppCfg.isAdmin;
const USER_ROLE     = _ppCfg.userRole;
const USER_DEPT     = _ppCfg.userDept;
const USER_SECTOR   = _ppCfg.userSector;
const USER_SECTOR_NAME = _ppCfg.userSectorName;
const USER_CENTER = _ppCfg.userCenter;

// Может ли текущий пользователь редактировать строку с данным dept/sector
function _canModify(rowDept, rowSector) {
  if (!IS_WRITER) return false;
  if (IS_ADMIN || USER_ROLE === 'ntc_head' || USER_ROLE === 'ntc_deputy') return true;
  if (USER_ROLE === 'sector_head') return !!rowSector && rowSector === USER_SECTOR;
  // dept_head, dept_deputy — только свой отдел
  return !!rowDept && rowDept === USER_DEPT;
}

/* ── Skeleton-загрузка — в utils.js ───────────────────────────────── */
var _ppSkeletonRows = skeletonRows;

/* ── Переключатель плотности — в utils.js ─────────────────────────── */
function _initPPDensity() {
  initDensityToggle('.pp-table-wrap', (_ppCfg.colSettings && _ppCfg.colSettings.density) || 'comfortable');
}

/** Формирует стандартное название ПП:
 *  "Производственный план подразделения НТЦ-XX по проекту/изделию ..."
 *  @param {object|null} upProj — объект проекта УП (с name_short/name_full)
 *  @param {object|null} prod   — объект изделия (с name, code)
 */
function buildPPName(upProj, prod) {
  // Формируем префикс с кодом НТЦ (если задан в профиле)
  const prefix = USER_CENTER
    ? 'Производственный план подразделения ' + USER_CENTER + ' '
    : 'Производственный план ';
  // Если выбрано изделие — добавляем его название и код
  if (prod) {
    const prodLabel = prod.name + (prod.code ? ' ' + prod.code : '');
    return prefix + 'по изделию ' + prodLabel;
  }
  // Если выбран проект УП — добавляем его краткое название
  if (upProj) {
    const projLabel = upProj.name_short || upProj.name_full;
    return prefix + 'по проекту ' + projLabel;
  }
  // Без привязки — только префикс
  return prefix.trimEnd();
}

/* ── Состояние модуля ─────────────────────────────────────────────────── */
// ID и название текущего открытого ПП-плана
let currentProjectId = null;
let currentProjectName = '';
// Список ПП-проектов (массив объектов)
let projects = [];
// Строки текущего ПП-плана (массив объектов)
let rows = [];
// Справочные данные (отделы, НТЦ, сотрудники, типы задач и т.д.)
let dirs = {};

// Список полей колонок ПП-таблицы (в порядке отображения)
const PP_COLUMNS = [
  'row_code', 'work_order', 'stage_num', 'milestone_num', 'work_num',
  'work_designation', 'work_name',
  'date_end', 'sheets_a4', 'norm', 'coeff', 'labor',
  'center', 'dept', 'sector_head', 'executor', 'task_type'
];

// Текущий фильтр статуса: 'all' | 'done' | 'overdue' | 'inwork'
let _ppStatusFilter = 'all';

/* ── Статус-панель (прогресс-бар + фильтры) ──────────────────────────── */
function _ppGetStatus(row) {
  if (row.has_reports) return 'done';
  if (row.is_overdue)  return 'overdue';
  return 'inwork';
}

function ppUpdateStatusPanel() {
  updateStatusPanel({
    panelId: 'ppStatusPanel',
    prefix: 'pp',
    data: rows,
    getStatus: _ppGetStatus,
    activeFilter: _ppStatusFilter
  });
}

function ppFilterStatus(status) {
  _ppStatusFilter = (_ppStatusFilter === status) ? 'all' : status;
  ppUpdateStatusPanel();
  renderPPTable();
}

/* ── Работа с URL (project_id в query string) ─────────────────────────── */
// Читает project_id из query string для поддержки прямых ссылок и навигации браузера
function readProjectFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get('project_id') || null;
}

// Обновляет URL без перезагрузки страницы (pushState)
function setProjectUrl(projectId) {
  const url = new URL(window.location);
  if (projectId) {
    url.searchParams.set('project_id', projectId);
  } else {
    url.searchParams.delete('project_id');
  }
  window.history.pushState({}, '', url);
}

/* ── API-запросы ──────────────────────────────────────────────────────── */
// Загружает справочники (отделы, НТЦ, сотрудники, типы задач и т.д.)
async function loadDirs() {
  // Cache-bust через timestamp чтобы не получать устаревшие данные
  const data = await fetchJson('/api/directories/?t=' + Date.now());
  if (!data._error) {
    // API возвращает секторы под ключом 'sector'; для колонки 'sector_head'
    // создаём алиас, чтобы buildSelectHtml мог читать dirs.sector_head
    if (data.sector && !data.sector_head) data.sector_head = data.sector;
    dirs = data;
  }
}

// Загружает список ПП-проектов текущего пользователя
async function loadProjects() {
  const data = await fetchJson('/api/pp_projects/');
  if (!data._error) projects = Array.isArray(data) ? data : (data.results || []);
}

// Загружает строки производственного плана для конкретного проекта
async function loadPPRows(projectId) {
  const data = await fetchJson('/api/production_plan/?project_id=' + projectId);
  if (!data._error) {
    rows = Array.isArray(data) ? data : (data.results || []);
    // Обратный порядок: новые строки отображаются вверху
    rows.reverse();
  }
}

/* ── Режим лендинга (список ПП-проектов) ────────────────────────────── */
// Переключает интерфейс на лендинг: скрывает таблицу, показывает сетку карточек
function showLanding() {
  currentProjectId = null;
  currentProjectName = '';
  // Убираем project_id из URL
  setProjectUrl(null);

  // Показываем лендинг, скрываем таблицу
  document.getElementById('landingView').style.display = '';
  document.getElementById('projectView').style.display = 'none';
  // Показываем кнопки лендинга, скрываем кнопки просмотра плана
  document.getElementById('landingActions').style.display = '';
  document.getElementById('projectActions').style.display = 'none';
  // Восстанавливаем заголовок хлебной крошки
  document.getElementById('breadcrumbTitle').textContent = 'Производственный план';

  // Сбрасываем счётчики строк
  const cp = document.getElementById('ppRowsCounterPlain');
  if (cp) { cp.textContent = ''; cp.style.display = 'none'; }

  // Скрываем панель периода
  ppSelectedMonth = null;
  ppSelectedYear = new Date().getFullYear();
  const periodBar = document.getElementById('ppPeriodBar');
  if (periodBar) periodBar.style.display = 'none';

  // Скрываем чипы отделов
  ppSelectedDept = null;
  const deptBar = document.getElementById('ppDeptBar');
  if (deptBar) deptBar.style.display = 'none';

  renderProjects();
}

// Отрисовывает сетку карточек ПП-проектов
function renderProjects() {
  const grid = document.getElementById('projectsGrid');

  // Пустое состояние: нет проектов
  if (projects.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1;">
        <div class="empty-state-icon"><i class="fas fa-industry"></i></div>
        <p>Проектов пока нет</p>
        ${IS_ADMIN ? '<button class="btn btn-primary" onclick="openCreateProjectModal()"><i class="fas fa-plus"></i> Создать новый производственный план</button>' : ''}
      </div>`;
    return;
  }

  // Генерируем карточки для каждого ПП-проекта
  grid.innerHTML = projects.map(p => `
    <div class="pp-project-card" onclick="openProject(${p.id}, '${escapeJs(p.name || '')}')">
      <!-- Привязанный проект УП (если есть) — синяя метка -->
      ${p.up_project_name ? `<div style="font-size:11px;color:var(--accent);font-weight:500;margin-bottom:2px;"><i class="fas fa-project-diagram" style="margin-right:3px;"></i>${escapeHtml(p.up_project_name)}</div>` : ''}
      <!-- Привязанное изделие УП (если есть) — зелёная метка -->
      ${p.up_product_name ? `<div style="font-size:11px;color:var(--success,#22c55e);font-weight:500;margin-bottom:4px;"><i class="fas fa-cog" style="margin-right:3px;"></i>${escapeHtml(p.up_product_name)}</div>` : ''}
      <!-- Название плана -->
      <div class="pp-project-card-name">${escapeHtml(p.name || 'Без названия')}</div>
      <!-- Количество строк в плане -->
      <div class="pp-project-card-count">
        <i class="fas fa-list" style="margin-right:4px;"></i>${p.row_count || 0} строк
      </div>
      <!-- Кнопки редактирования/удаления (только для администраторов) -->
      ${IS_ADMIN ? `
        <div class="pp-project-card-actions">
          <!-- Редактировать название и привязку к УП -->
          <button class="pp-card-btn" onclick="event.stopPropagation(); editProjectName(${p.id}, '${escapeJs(p.name || '')}', ${p.up_project_id || 'null'}, ${p.up_product_id || 'null'})" title="Переименовать">
            <i class="fas fa-pen"></i>
          </button>
          <!-- Удалить план со всеми его строками -->
          <button class="pp-card-btn danger" onclick="event.stopPropagation(); deleteProject(${p.id}, '${escapeJs(p.name || '')}')" title="Удалить">
            <i class="fas fa-trash"></i>
          </button>
        </div>` : ''}
    </div>
  `).join('');
}

/* ── Проекты УП (для диалога создания ПП-плана) ─────────────────────── */
// Кэш проектов из модуля УП (загружается один раз)
let upProjects = [];

// Загружает проекты УП (с изделиями) — только если кэш пуст
async function loadUpProjects() {
  if (upProjects.length) return;
  const data = await fetchJson('/api/projects/');
  if (!data._error) upProjects = Array.isArray(data) ? data : [];
}

/* ── CRUD ПП-проектов ────────────────────────────────────────────────── */
// Открывает модальное окно создания нового ПП-плана
async function openCreateProjectModal() {
  // Загружаем проекты УП для привязки
  await loadUpProjects();

  // Опции для привязки к проекту УП
  const upOptions = upProjects.length
    ? upProjects.map(p => `<option value="${p.id}">${escapeHtml(p.name_short || p.name_full)}</option>`).join('')
    : '';

  // Опции для открытия существующего ПП-плана из списка
  const existingOptions = projects.length
    ? projects.map(p => `<option value="${p.id}">${escapeHtml(p.name || 'Без названия')}</option>`).join('')
    : '';

  // Открываем модальное окно через modal.js
  const modal = openModal({
    title: 'Производственный план',
    width: '480px',
    body: `
      ${projects.length ? `
      <!-- Секция открытия существующего плана (если список не пуст) -->
      <div class="modal-form-group">
        <label>Открыть существующий план</label>
        <select id="existingProjectSel">
          <option value="">— выберите из списка —</option>
          ${existingOptions}
        </select>
      </div>
      <div style="text-align:center;color:var(--muted);font-size:13px;margin:12px 0;">— или —</div>
      ` : ''}
      <div style="font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px;">Создать новый план</div>
      ${upProjects.length ? `
      <!-- Привязка к проекту УП -->
      <div class="modal-form-group">
        <label>Проект (из модуля УП)</label>
        <select id="newPlanUpProject">
          <option value="">— не привязывать —</option>
          ${upOptions}
        </select>
      </div>
      <!-- Выбор конкретного изделия проекта (появляется, если у проекта есть изделия) -->
      <div class="modal-form-group" id="newPlanProductGroup" style="display:none;">
        <label>Изделие проекта</label>
        <select id="newPlanUpProduct">
          <option value="">— весь проект —</option>
        </select>
      </div>` : ''}
      <!-- Поле названия плана (авто-заполняется при выборе УП-проекта) -->
      <div class="modal-form-group">
        <label>Название плана</label>
        <input type="text" id="newProjectName" placeholder="Производственный план подразделения НТЦ-... по проекту ...">
      </div>`,
    footer: `
      <button class="btn btn-outline modal-cancel">Отмена</button>
      ${projects.length ? '<button class="btn btn-secondary" id="openExistingBtn">Открыть</button>' : ''}
      <button class="btn btn-primary" id="createProjectBtn">Создать</button>`,
  });

  // Ссылки на элементы модального окна
  const nameInput    = modal.dialog.querySelector('#newProjectName');
  const createBtn    = modal.dialog.querySelector('#createProjectBtn');
  const existingSel  = modal.dialog.querySelector('#existingProjectSel');
  const openBtn      = modal.dialog.querySelector('#openExistingBtn');
  const upSel        = modal.dialog.querySelector('#newPlanUpProject');
  const productGroup = modal.dialog.querySelector('#newPlanProductGroup');
  const productSel   = modal.dialog.querySelector('#newPlanUpProduct');

  // При выборе проекта УП: автозаполнить название и показать изделия (если есть)
  if (upSel) {
    upSel.addEventListener('change', () => {
      const upId = upSel.value;
      const upProj = upId ? upProjects.find(p => String(p.id) === String(upId)) : null;

      // Авто-название по проекту (без изделия)
      nameInput.value = buildPPName(upProj, null);

      // Показать/скрыть список изделий в зависимости от наличия у проекта
      if (productGroup && productSel) {
        const products = upProj && upProj.products ? upProj.products : [];
        if (products.length > 0) {
          // Заполнить список изделий
          productSel.innerHTML = '<option value="">— весь проект —</option>'
            + products.map(pr => `<option value="${pr.id}">${escapeHtml(pr.name)}${pr.code ? ' (' + escapeHtml(pr.code) + ')' : ''}</option>`).join('');
          productGroup.style.display = '';
        } else {
          // Скрыть список изделий если у проекта нет изделий
          productGroup.style.display = 'none';
          productSel.innerHTML = '<option value="">— весь проект —</option>';
        }
      }

      // При выборе конкретного изделия — обновить название плана
      if (productSel) {
        productSel.onchange = () => {
          const prodId = productSel.value;
          const prod = prodId && upProj ? (upProj.products || []).find(pr => String(pr.id) === String(prodId)) : null;
          nameInput.value = buildPPName(upProj, prod);
        };
      }
    });
  }

  // Открыть выбранный существующий план
  if (openBtn && existingSel) {
    openBtn.addEventListener('click', () => {
      const id = existingSel.value;
      // Обязательно выбрать из списка
      if (!id) { existingSel.style.borderColor = 'var(--danger)'; return; }
      const proj = projects.find(p => String(p.id) === String(id));
      if (proj) { modal.close(); openProject(proj.id, proj.name); }
    });
  }

  // Создать новый ПП-план
  async function doCreate() {
    const name = nameInput.value.trim();
    // Название обязательно
    if (!name) { nameInput.style.borderColor = 'var(--danger)'; return; }
    createBtn.disabled = true;
    // Опциональная привязка к УП-проекту и изделию
    const up_project_id = upSel ? (upSel.value || null) : null;
    const up_product_id = productSel ? (productSel.value || null) : null;
    // POST /api/pp_projects/create/
    const resp = await fetchJson('/api/pp_projects/create/', {
      method: 'POST',
      body: JSON.stringify({ name, up_project_id, up_product_id }),
    });
    if (!resp._error) {
      modal.close();
      // Перезагружаем список и перерисовываем карточки
      await loadProjects();
      renderProjects();
      showToast('Производственный план создан', 'success');
    }
    createBtn.disabled = false;
  }

  // Кнопка «Создать» и Enter в поле имени
  createBtn.addEventListener('click', doCreate);
  nameInput.addEventListener('keydown', e => { if (e.key === 'Enter') doCreate(); });
  // Кнопка «Отмена»
  modal.dialog.querySelector('.modal-cancel').addEventListener('click', () => modal.close());
}

// Открывает модальное окно редактирования названия и привязки ПП-плана
async function editProjectName(id, currentName, currentUpProjectId, currentUpProductId) {
  await loadUpProjects();
  // Строим список опций с предвыбором текущего УП-проекта
  const upOptions = upProjects.map(p =>
    `<option value="${p.id}"${String(p.id) === String(currentUpProjectId) ? ' selected' : ''}>${escapeHtml(p.name_short || p.name_full)}</option>`
  ).join('');

  // Получаем изделия текущего проекта УП для предзаполнения
  const curUpProj = currentUpProjectId ? upProjects.find(p => String(p.id) === String(currentUpProjectId)) : null;
  const curProducts = curUpProj && curUpProj.products ? curUpProj.products : [];
  const productOptions = curProducts.map(pr =>
    `<option value="${pr.id}"${String(pr.id) === String(currentUpProductId) ? ' selected' : ''}>${escapeHtml(pr.name)}${pr.code ? ' (' + escapeHtml(pr.code) + ')' : ''}</option>`
  ).join('');

  const modal = openModal({
    title: 'Редактировать производственный план',
    width: '440px',
    body: `
      <!-- Поле названия плана (предзаполнено текущим именем) -->
      <div class="modal-form-group">
        <label>Название плана</label>
        <input type="text" id="editProjectName" value="${escapeHtml(currentName)}" autofocus>
      </div>
      ${upProjects.length ? `
      <!-- Привязка к проекту УП -->
      <div class="modal-form-group">
        <label>Привязать к проекту (УП)</label>
        <select id="editUpProject">
          <option value="">— не привязывать —</option>
          ${upOptions}
        </select>
      </div>
      <!-- Список изделий (показывается если у выбранного УП-проекта есть изделия) -->
      <div class="modal-form-group" id="editProductGroup" style="display:${curProducts.length ? '' : 'none'};">
        <label>Изделие проекта</label>
        <select id="editUpProduct">
          <option value="">— весь проект —</option>
          ${productOptions}
        </select>
      </div>` : ''}`,
    footer: `
      <button class="btn btn-outline modal-cancel">Отмена</button>
      <button class="btn btn-primary" id="saveProjectBtn">Сохранить</button>`,
  });

  const nameInput    = modal.dialog.querySelector('#editProjectName');
  const upSel        = modal.dialog.querySelector('#editUpProject');
  const productGroup = modal.dialog.querySelector('#editProductGroup');
  const productSel   = modal.dialog.querySelector('#editUpProduct');
  const saveBtn      = modal.dialog.querySelector('#saveProjectBtn');

  // При смене УП-проекта: обновить список изделий
  if (upSel && productGroup && productSel) {
    upSel.addEventListener('change', () => {
      const upId = upSel.value;
      const upProj = upId ? upProjects.find(p => String(p.id) === String(upId)) : null;
      const products = upProj && upProj.products ? upProj.products : [];
      if (products.length > 0) {
        productSel.innerHTML = '<option value="">— весь проект —</option>'
          + products.map(pr => `<option value="${pr.id}">${escapeHtml(pr.name)}${pr.code ? ' (' + escapeHtml(pr.code) + ')' : ''}</option>`).join('');
        productGroup.style.display = '';
      } else {
        productGroup.style.display = 'none';
        productSel.innerHTML = '<option value="">— весь проект —</option>';
      }
    });
  }

  // Сохранить изменения через PUT /api/pp_projects/<id>/
  async function doSave() {
    const name = nameInput.value.trim();
    if (!name) { nameInput.style.borderColor = 'var(--danger)'; return; }
    saveBtn.disabled = true;
    // undefined означает «не изменять» (если поля нет в форме)
    const up_project_id = upSel ? (upSel.value || null) : undefined;
    const up_product_id = productSel ? (productSel.value || null) : undefined;
    const body = { name };
    if (up_project_id !== undefined) body.up_project_id = up_project_id;
    if (up_product_id !== undefined) body.up_product_id = up_product_id;
    const resp = await fetchJson(`/api/pp_projects/${id}/`, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
    if (!resp._error) {
      modal.close();
      await loadProjects();
      renderProjects();
      showToast('Производственный план обновлён', 'success');
    }
    saveBtn.disabled = false;
  }

  saveBtn.addEventListener('click', doSave);
  modal.dialog.querySelector('.modal-cancel').addEventListener('click', () => modal.close());
}

// Удаляет ПП-план со всеми его строками после подтверждения
async function deleteProject(id, name) {
  const ok = await confirmDialog(
    `Удалить проект "${name}" и все его строки?`,
    'Удаление проекта'
  );
  if (!ok) return;
  // DELETE /api/pp_projects/<id>/
  const resp = await fetchJson(`/api/pp_projects/${id}/`, { method: 'DELETE' });
  if (!resp._error) {
    await loadProjects();
    renderProjects();
    showToast('Проект удалён', 'success');
  }
}

/* ── Режим просмотра плана (таблица строк) ───────────────────────────── */
// Переключает интерфейс на таблицу конкретного ПП-плана
async function openProject(id, name) {
  currentProjectId = id;
  currentProjectName = name;
  // Обновляем URL для прямой ссылки и поддержки истории браузера
  setProjectUrl(id);

  // Переключаем видимость блоков
  document.getElementById('landingView').style.display = 'none';
  document.getElementById('projectView').style.display = '';
  document.getElementById('landingActions').style.display = 'none';
  document.getElementById('projectActions').style.display = '';
  // Обновляем хлебную крошку: если привязан УП-проект — показываем его название
  const projObj = projects.find(p => String(p.id) === String(id));
  let headerTitle = 'ПП: ' + name;
  if (projObj && projObj.up_project_name) {
    headerTitle = name + ' (проект: ' + projObj.up_project_name + ')';
  }
  document.getElementById('breadcrumbTitle').textContent = headerTitle;

  // Показываем skeleton-загрузку в таблице
  const _ppTbody = document.getElementById('ppTableBody');
  if (_ppTbody) _ppTbody.innerHTML = _ppSkeletonRows(10, 19);
  // Загружаем строки плана и рендерим таблицу
  await loadPPRows(id);

  // Устанавливаем дефолтный фильтр по отделу при первом открытии проекта
  // (не-admin с привязанным отделом видит по умолчанию только свой отдел)
  // Если пользователь уже сбрасывал фильтр вручную — не восстанавливаем
  const filterKey = 'pp_dept_filter_cleared_' + id;
  const wasCleared = sessionStorage.getItem(filterKey);
  if (!IS_ADMIN && USER_DEPT && !wasCleared && !colFilters['mf_dept']) {
    // Устанавливаем фильтр по своему отделу
    mfSelections['dept'] = new Set([USER_DEPT]);
    colFilters['mf_dept'] = new Set([USER_DEPT]);
    // Обновляем кнопку фильтра
    const deptBtn = document.querySelector('.mf-trigger[data-col="dept"]');
    if (deptBtn) { deptBtn.textContent = USER_DEPT; deptBtn.classList.add('active'); }
    document.getElementById('filtersActiveBadge').style.display = 'inline';
  }

  renderPPTable();
  requestAnimationFrame(_fixFilterRowTop);
  initPPPeriodBar();
  initPPDeptChips();
}

// Возврат на лендинг
function goToLanding() {
  showLanding();
}

/* ── Построение HTML-селекта для ячейки-выпадашки ────────────────────── */
// Строит <select> для столбцов dept, center, executor, sector_head, task_type
// с учётом роли пользователя (отдельные опции могут быть disabled)
function buildSelectHtml(col, row) {
  const val = row[col] || '';
  // Для task_type нет пустой опции (значение обязательно); для остальных — есть «--»
  let options = col === 'task_type' ? '' : '<option value="">--</option>';

  if (col === 'dept') {
    // В ПП все отделы доступны для просмотра и выбора
    (dirs.dept || []).forEach(d => {
      options += `<option value="${escapeHtml(d.value)}"${d.value === val ? ' selected' : ''}>${escapeHtml(d.value)}</option>`;
    });
  } else if (col === 'center') {
    // В ПП все НТЦ доступны для выбора
    const centerVal = val || USER_CENTER;
    (dirs.center || []).forEach(d => {
      options += `<option value="${escapeHtml(d.value)}"${d.value === centerVal ? ' selected' : ''}>${escapeHtml(d.value)}</option>`;
    });
  } else if (col === 'executor') {
    // Исполнитель: фильтрация по сектору (если выбран), иначе по отделу
    const deptFilter   = row['dept'] || '';
    const sectorFilter = row['sector_head'] || '';
    const allEmps = dirs.employees || [];
    let filtered;
    if (sectorFilter) {
      // Если выбран сектор — показываем только сотрудников этого сектора
      filtered = allEmps.filter(e => e.sector === sectorFilter);
    } else if (deptFilter) {
      // Иначе — все сотрудники отдела
      filtered = allEmps.filter(e => e.dept === deptFilter);
    } else {
      filtered = allEmps;
    }
    // Если текущее значение не в отфильтрованном списке — добавляем его как фантомную опцию
    if (val && !filtered.find(e => e.value === val)) {
      options += `<option value="${escapeHtml(val)}" selected>${escapeHtml(val)}</option>`;
    }
    filtered.forEach(e => {
      options += `<option value="${escapeHtml(e.value)}"${e.value === val ? ' selected' : ''}>${escapeHtml(e.value)}</option>`;
    });
  } else if (col === 'sector_head') {
    // Сектор: фильтрация по выбранному отделу
    const deptVal = row['dept'] || '';
    const deptEntry = (dirs.dept || []).find(d => d.value === deptVal);
    const allHeads = dirs.sector_head || [];
    const filtered = deptEntry ? allHeads.filter(h => h.parent_id === deptEntry.id) : allHeads;
    // Фантомная опция если текущее значение не найдено в отфильтрованном списке
    if (val && !filtered.find(h => h.value === val)) {
      // Ищем ФИО нач. сектора среди всех секторов
      const anyMatch = allHeads.find(h => h.value === val);
      options += `<option value="${escapeHtml(val)}" selected>${escapeHtml(val)}</option>`;
    }
    filtered.forEach(h => {
      // Начальник сектора видит все сектора своего отдела,
      // но чужой сектор — disabled (только для просмотра)
      const isOwnSector = IS_ADMIN || USER_ROLE === 'dept_head' || USER_ROLE === 'dept_deputy'
                          || !USER_SECTOR || h.value === USER_SECTOR;
      const disabledAttr = isOwnSector ? '' : ' disabled style="color:var(--muted)"';
      // Текст опции: только код сектора (ФИО выводится серым под select'ом)
      options += `<option value="${escapeHtml(h.value)}"${h.value === val ? ' selected' : ''}${disabledAttr}>${escapeHtml(h.value)}</option>`;
    });
  } else if (col === 'task_type') {
    // Тип задачи: значение по умолчанию «Выпуск нового документа»
    const taskVal = val || 'Выпуск нового документа';
    const taskTypes = dirs.task_type || [];
    taskTypes.forEach(d => {
      options += `<option value="${escapeHtml(d.value)}"${d.value === taskVal ? ' selected' : ''}>${escapeHtml(d.value)}</option>`;
    });
  }
  return `<select class="cell-edit" data-col="${col}" data-id="${row.id}">${options}</select>`;
}

/* ── Infinite scroll: состояние ленивой отрисовки ПП ──────────────────── */
const PP_CHUNK = 50;
let _ppFiltered = [];
let _ppRenderedCount = 0;
let _ppScrollDispose = null;

/* ── Отрисовка таблицы ПП ────────────────────────────────────────────── */
function renderPPTable() {
  const tbody = document.getElementById('ppTableBody');
  tbody.innerHTML = '';
  _ppRenderedCount = 0;
  if (_ppScrollDispose) { _ppScrollDispose(); _ppScrollDispose = null; }

  // Обновляем панель статусов
  ppUpdateStatusPanel();

  // Применяем сортировку и активные колоночные фильтры к массиву строк
  _ppFiltered = rows.filter(row => {
    // Фильтр по статусу (прогресс-панель)
    if (_ppStatusFilter !== 'all' && _ppGetStatus(row) !== _ppStatusFilter) return false;

    for (const [col, val] of Object.entries(colFilters)) {
      if (col.startsWith('mf_')) {
        // Мультифильтр: проверяем входит ли значение в выбранное множество
        const field = col.slice(3);
        if (val.size > 0) {
            // Для date_end сравниваем по году-месяцу (первые 7 символов)
            const cellVal = (field === 'date_end')
              ? (row[field] || '').slice(0, 7)
              : (row[field] || '');
            if (!val.has(cellVal)) return false;
        }
        continue;
      }
      // Текстовый фильтр (подстрока, нижний регистр)
      const cellVal = (row[col] || '').toString().toLowerCase();
      if (!cellVal.includes(val)) return false;
    }
    return true;
  });

  // Сортировка
  if (_ppSortState.col) {
    _ppFiltered = applySortToArray(_ppFiltered, _ppSortState, function(r, col) {
      return r[col] || '';
    });
  }

  // Обновляем счётчик строк
  const hasFiltersActive = Object.keys(colFilters).length > 0;
  const counter = document.getElementById('ppRowsCounter');
  const counterPlain = document.getElementById('ppRowsCounterPlain');
  if (hasFiltersActive) {
    if (counter) counter.textContent = `(${_ppFiltered.length} из ${rows.length})`;
    if (counterPlain) counterPlain.style.display = 'none';
  } else {
    if (counter) counter.textContent = '';
    if (counterPlain) {
      counterPlain.textContent = rows.length > 0 ? `${rows.length} строк` : '';
      counterPlain.style.display = rows.length > 0 ? 'inline' : 'none';
    }
  }

  // Пустое состояние: нет строк после фильтрации
  if (_ppFiltered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="20">
      <div class="empty-state">
        <div class="empty-state-icon"><i class="fas fa-inbox"></i></div>
        <div class="empty-state-title">Нет записей</div>
        <div class="empty-state-desc">Попробуйте изменить фильтры или добавьте новую строку</div>
      </div>
    </td></tr>`;
    return;
  }

  // Рендерим первую порцию строк
  _ppAppendBatch(PP_CHUNK);
  // Ставим слушатель прокрутки для подгрузки следующих порций
  _ppAttachScrollListener();
}

/* ── Добавление порции строк в таблицу ПП ─────────────────────────── */
function _ppAppendBatch(count) {
  const tbody = document.getElementById('ppTableBody');
  const end = Math.min(_ppRenderedCount + count, _ppFiltered.length);
  // Убираем спиннер, если есть
  const spinner = document.getElementById('ppScrollSpinner');
  if (spinner) spinner.remove();

  const startIdx = _ppRenderedCount;
  for (let idx = startIdx; idx < end; idx++) {
    const row = _ppFiltered[idx];
    const tr = document.createElement('tr');
    tr.dataset.id = row.id;
    // Подсветка строки по статусу
    const _st = _ppGetStatus(row);
    if (_st === 'done') tr.classList.add('row-done');
    else if (_st === 'overdue') tr.classList.add('row-overdue');
    else tr.classList.add('row-inwork');
    // Первый столбец — порядковый номер (1-based)
    let html = `<td>${idx + 1}</td>`;

    // Может ли текущий пользователь редактировать эту строку (свой отдел/сектор)
    const rowEditable = _canModify(row.dept, row.sector_head);

    // Для каждого поля колонки — определяем тип ячейки и строим HTML
    for (const col of PP_COLUMNS) {
      const val = row[col] || '';
      // Классификация типа ячейки
      const isSelectCol = ['dept', 'center', 'executor', 'task_type', 'sector_head'].includes(col);
      const isTextCol = ['work_name', 'work_order', 'work_designation'].includes(col);
      const isDateCol = col === 'date_end';

      if (!IS_WRITER || !rowEditable || col === 'row_code') {
        // Режим только для чтения: статичный текст (row_code всегда read-only — автогенерация)
        if (col === 'sector_head' && val) {
          const sh = (dirs.sector_head || []).find(h => h.value === val);
          const headName = sh ? (sh.head_name || '') : '';
          html += `<td style="font-size:12px;padding:4px 6px;">${escapeHtml(val)}${headName ? `<div style="font-size:11px;color:var(--muted);margin-top:2px;">${escapeHtml(headName)}</div>` : ''}</td>`;
        } else if (col === 'task_type' && val) {
          html += `<td style="padding:4px 6px;text-align:center;">${taskTypeBadgeHtml(val, {short: true})}</td>`;
        } else {
          html += `<td style="font-size:12px;padding:4px 6px;">${escapeHtml(val)}</td>`;
        }
      } else if (isSelectCol) {
        // Выпадающий список с учётом роли пользователя
        if (col === 'sector_head' && val) {
          const sh = (dirs.sector_head || []).find(h => h.value === val);
          const headName = sh ? (sh.head_name || '') : '';
          html += `<td>${buildSelectHtml(col, row)}${headName ? `<div style="font-size:11px;color:var(--muted);margin-top:2px;padding:0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(headName)}</div>` : ''}</td>`;
        } else {
          html += `<td>${buildSelectHtml(col, row)}</td>`;
        }
      } else if (isTextCol) {
        // Текстовое поле ввода
        html += `<td><input class="cell-edit" data-col="${col}" data-id="${row.id}" value="${escapeHtml(val)}"></td>`;
      } else if (isDateCol) {
        // Поле выбора даты
        html += `<td><input type="date" class="cell-edit" data-col="${col}" data-id="${row.id}" value="${escapeHtml(val)}"></td>`;
      } else {
        // Числовое поле (трудоёмкость, листы, коэффициент и т.д.)
        html += `<td><input class="cell-edit cell-num" data-col="${col}" data-id="${row.id}" value="${escapeHtml(val)}"></td>`;
      }
    }

    // Последний столбец: кнопки действий
    const pc = row.predecessors_count || 0;
    html += '<td style="text-align:center;white-space:nowrap;">';
    html += `<span class="dep-badge action-dep${pc === 0 ? ' zero' : ''}" style="cursor:pointer;margin-right:4px;" onclick="openPPDepsModal(${row.id})" title="Зависимости">🔗</span>`;
    if (rowEditable) {
      html += `<button class="btn-delete" data-id="${row.id}" title="Удалить"><i class="fas fa-times"></i></button>`;
    }
    html += '</td>';

    tr.innerHTML = html;
    tbody.appendChild(tr);
  }

  /* ── Навешиваем обработчики только на новые ячейки ────────────────── */
  const allRows = tbody.querySelectorAll('tr');
  for (let r = startIdx; r < end && r < allRows.length; r++) {
    allRows[r].querySelectorAll('.cell-edit').forEach(input => {
      input._ppLastSaved = input.value;
      input.addEventListener('change', handleCellChange);
      input.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
          e.preventDefault();
          handleCellChange({ target: this });
          const inputs = Array.from(tbody.querySelectorAll('.cell-edit'));
          const i = inputs.indexOf(this);
          const nextI = e.shiftKey ? i - 1 : i + 1;
          if (nextI >= 0 && nextI < inputs.length) {
            inputs[nextI].focus();
            if (inputs[nextI].tagName !== 'SELECT') inputs[nextI].select();
          }
        }
      });
    });
    allRows[r].querySelectorAll('.btn-delete').forEach(btn => {
      btn.addEventListener('click', async function() {
        const ok = await confirmDialog('Удалить эту строку?', 'Удаление');
        if (!ok) return;
        const id = this.getAttribute('data-id');
        const resp = await fetchJson('/api/production_plan/' + id + '/', { method: 'DELETE' });
        if (!resp._error) {
          rows = rows.filter(r => String(r.id) !== String(id));
          renderPPTable();
          showToast('Строка удалена', 'success');
        }
      });
    });
  }

  _ppRenderedCount = end;

  // Показываем спиннер, если ещё есть строки для отрисовки
  if (_ppRenderedCount < _ppFiltered.length) {
    const spinnerTr = document.createElement('tr');
    spinnerTr.id = 'ppScrollSpinner';
    spinnerTr.innerHTML = '<td colspan="19" class="scroll-spinner"><i class="fas fa-spinner"></i> Загрузка...</td>';
    tbody.appendChild(spinnerTr);
  }

}

/* ── Слушатель прокрутки для ленивой подгрузки строк ПП ───────────── */
function _ppAttachScrollListener() {
  if (_ppScrollDispose) { _ppScrollDispose(); _ppScrollDispose = null; }
  if (_ppRenderedCount >= _ppFiltered.length) return;

  _ppScrollDispose = createScrollLoader(
    document.getElementById('ppTableView'),
    () => {
      if (_ppRenderedCount < _ppFiltered.length) {
        _ppAppendBatch(PP_CHUNK);
        if (_ppRenderedCount >= _ppFiltered.length && _ppScrollDispose) {
          _ppScrollDispose(); _ppScrollDispose = null;
        }
      }
    },
    200
  );
}

/* ── Визуальная подсветка ячейки (успех/ошибка) ─────────────────────── */
// Устанавливает outline цвета color на td на ms миллисекунд
function cellOutline(td, color, ms) {
  if (!td) return;
  td.style.outline = '1px solid ' + color;
  setTimeout(() => { td.style.outline = ''; }, ms);
}

/* ── Обработчик изменения ячейки (отправка PUT на сервер) ────────────── */
async function handleCellChange(e) {
  const input = e.target;
  const id = input.getAttribute('data-id');
  const field = input.getAttribute('data-col');
  let value = input.value;
  const td = input.closest('td');

  // Защита от повторного PUT (change+Tab могут вызвать дважды)
  if (id !== '_new_' && input._ppLastSaved === value) return;
  input._ppLastSaved = value;

  // Для новой (ещё не сохранённой) строки — только авто-расчёт трудоёмкости, без PUT
  if (id === '_new_') {
    if (['sheets_a4', 'norm', 'coeff'].includes(field)) {
      const tr = input.closest('tr');
      let sheets = null, norm = null, coeff = null;
      tr.querySelectorAll('input').forEach(inp => {
        const col = inp.getAttribute('data-col');
        const v = parseFloat(inp.value.replace(',', '.'));
        if (col === 'sheets_a4' && !isNaN(v)) sheets = v;
        if (col === 'norm'      && !isNaN(v)) norm  = v;
        if (col === 'coeff'     && !isNaN(v)) coeff = v;
      });
      const laborInput = tr.querySelector('input[data-col="labor"]');
      if (laborInput) {
        // Рассчитываем трудоёмкость: листы × норматив × коэффициент (округлить до целого)
        laborInput.value = (sheets !== null && norm !== null && coeff !== null)
          ? +(sheets * norm * coeff).toFixed(2)
          : '';
      }
    }
    return;
  }

  // task_type обязателен: если очищен — сбросить к значению по умолчанию
  if (field === 'task_type' && !value.trim()) {
    const defaultType = (dirs.task_type && dirs.task_type.length) ? dirs.task_type[0].value : '';
    input.value = defaultType;
    value = defaultType;
  }

  // При смене отдела: пересобираем список нач. секторов И исполнителей
  if (field === 'dept') {
    const rowObj = rows.find(r => String(r.id) === String(id));
    if (rowObj) {
      rowObj.dept = value;
      rowObj.sector_head = '';  // Сброс сектора при смене отдела
      // Обновляем нач. секторов
      const headSel = input.closest('tr').querySelector('select[data-col="sector_head"]');
      if (headSel) {
        headSel.outerHTML = buildSelectHtml('sector_head', rowObj);
        const newHead = input.closest('tr').querySelector('select[data-col="sector_head"]');
        if (newHead) {
          newHead.addEventListener('change', handleCellChange);
          newHead._ppLastSaved = newHead.value;
        }
      }
      // Обновляем исполнителей по новому отделу (сектор сброшен — показываем весь отдел)
      const execSel = input.closest('tr').querySelector('select[data-col="executor"]');
      if (execSel) {
        execSel.outerHTML = buildSelectHtml('executor', rowObj);
        const newSel = input.closest('tr').querySelector('select[data-col="executor"]');
        if (newSel) {
          newSel.addEventListener('change', handleCellChange);
          newSel._ppLastSaved = newSel.value;
        }
      }
    }
  }

  // При смене сектора: обновляем ФИО под селектом и пересобираем список исполнителей
  if (field === 'sector_head') {
    const rowObj = rows.find(r => String(r.id) === String(id));
    if (rowObj) {
      rowObj.sector_head = value;
      // Обновляем div с ФИО начальника сектора
      const headDiv = input.closest('td').querySelector('div');
      const sh = (dirs.sector_head || []).find(h => h.value === value);
      const headName = sh ? (sh.head_name || '') : '';
      if (headDiv) {
        headDiv.textContent = headName;
        headDiv.style.display = headName ? '' : 'none';
      } else if (headName) {
        input.closest('td').insertAdjacentHTML('beforeend',
          `<div style="font-size:11px;color:var(--muted);margin-top:2px;padding:0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(headName)}</div>`);
      }
      // Пересобираем исполнителей
      const execSel = input.closest('tr').querySelector('select[data-col="executor"]');
      if (execSel) {
        execSel.outerHTML = buildSelectHtml('executor', rowObj);
        const newSel = input.closest('tr').querySelector('select[data-col="executor"]');
        if (newSel) {
          newSel.addEventListener('change', handleCellChange);
          newSel._ppLastSaved = newSel.value;
        }
      }
    }
  }

  // Синяя подсветка ячейки пока идёт запрос
  if (td) td.style.outline = '1px solid rgba(59,130,246,0.5)';

  // PUT /api/production_plan/<id>/?field=<field> — сохранить одно поле
  const resp = await fetchJson('/api/production_plan/' + id + '/?field=' + field, {
    method: 'PUT',
    body: JSON.stringify({ value: value }),
  });

  // Ошибка конфликта (например, попытка изменить заблокированное поле from_pp)
  if (resp._conflict) {
    cellOutline(td, 'rgba(239,68,68,0.7)', 3000);
    return;
  }
  // Другая ошибка сервера
  if (resp._error) {
    cellOutline(td, 'rgba(239,68,68,0.7)', 3000);
    return;
  }

  // Успех: зелёная подсветка на 700мс
  cellOutline(td, 'rgba(34,197,94,0.5)', 700);

  // Обновляем данные в локальном массиве
  const rowObj = rows.find(r => String(r.id) === String(id));
  if (rowObj) rowObj[field] = value;

  // Автоматический пересчёт трудоёмкости при изменении листов/норматива/коэффициента
  if (['sheets_a4', 'norm', 'coeff'].includes(field)) {
    try {
      const tr = input.closest('tr');
      let sheets = null, norm = null, coeff = null;
      // Читаем актуальные значения из DOM
      tr.querySelectorAll('input').forEach(inp => {
        const col = inp.getAttribute('data-col');
        const v = parseFloat(inp.value.replace(',', '.'));
        if (col === 'sheets_a4' && !isNaN(v)) sheets = v;
        if (col === 'norm' && !isNaN(v)) norm = v;
        if (col === 'coeff' && !isNaN(v)) coeff = v;
      });
      const laborInput = tr.querySelector('input[data-col="labor"]');
      const laborTd = laborInput ? laborInput.closest('td') : null;
      let laborVal = '';
      if (sheets !== null && norm !== null && coeff !== null) {
        // Трудоёмкость = Ф × Норматив × Коэффициент (до 2 знаков)
        laborVal = parseFloat((sheets * norm * coeff).toFixed(2));
        if (laborInput) laborInput.value = laborVal;
      } else {
        if (laborInput) laborInput.value = '';
      }
      // Синяя подсветка ячейки трудоёмкости
      if (laborTd) laborTd.style.outline = '1px solid rgba(59,130,246,0.5)';
      // Сохраняем вычисленную трудоёмкость на сервере
      const r2 = await fetchJson('/api/production_plan/' + id + '/?field=labor', {
        method: 'PUT',
        body: JSON.stringify({ value: laborVal }),
      });
      if (!r2._error && !r2._conflict) {
        cellOutline(laborTd, 'rgba(34,197,94,0.5)', 700);
        if (rowObj) rowObj.labor = laborVal;
      } else {
        cellOutline(laborTd, 'rgba(239,68,68,0.7)', 3000);
      }
    } catch (e) { console.error('Ошибка пересчёта трудоёмкости:', e); }
  }
}

/* ── Добавление строки прямо в таблицу ──────────────────────────────── */
// Флаг: предотвращает двойное добавление строки
let _addingRow = false;

// Добавляет временную редактируемую строку в конец таблицы
function openAddRowModal() {
  // Нельзя добавить строку без открытого проекта
  if (!currentProjectId) {
    showToast('Откройте проект для добавления строк', 'error');
    return;
  }
  if (_addingRow) {
    // Если строка уже добавлена — прокрутить к ней и поставить фокус
    const newTr = document.getElementById('ppNewRow');
    if (newTr) {
      newTr.scrollIntoView({ behavior: 'smooth', block: 'center' });
      const first = newTr.querySelector('input, select');
      if (first) first.focus();
    }
    return;
  }
  _addingRow = true;

  const tbody = document.getElementById('ppTableBody');

  // Определяем значение нач. сектора по умолчанию (для роли sector_head)
  let _defaultSectorHead = '';
  if (USER_ROLE === 'sector_head' && USER_SECTOR) {
    const _heads = dirs.sector_head || [];
    // Ищем совпадение по коду или имени сектора
    const _match = _heads.find(h => h.value === USER_SECTOR || h.value === USER_SECTOR_NAME);
    if (_match) _defaultSectorHead = _match.value;
    else if (USER_SECTOR_NAME) _defaultSectorHead = USER_SECTOR_NAME;
    else _defaultSectorHead = USER_SECTOR;
  }

  // Авто-заполнение НТЦ: для dept_head / dept_deputy / sector_head подставляем свой НТЦ
  // ntc_head / ntc_deputy / admin оставляем пустым (выбирают сами)
  const _defaultCenter = (['dept_head', 'dept_deputy', 'sector_head'].includes(USER_ROLE) && USER_CENTER)
    ? USER_CENTER : '';

  // Объект новой строки с дефолтными значениями из профиля пользователя
  const newRow = { id: '_new_', row_code: '', work_order: '', stage_num: '',
    milestone_num: '', work_num: '', work_designation: '', work_name: '',
    date_end: '', sheets_a4: '', norm: '', coeff: '', labor: '',
    center: _defaultCenter, dept: USER_DEPT || '', sector_head: _defaultSectorHead,
    executor: '', task_type: (dirs.task_type && dirs.task_type.length) ? dirs.task_type[0].value : 'Выпуск нового документа' };

  const tr = document.createElement('tr');
  tr.id = 'ppNewRow';
  // Синяя подсветка новой строки
  tr.style.cssText = 'background:rgba(59,130,246,0.07);outline:2px solid rgba(59,130,246,0.3);';

  // Первый столбец — знак «+» вместо номера
  let html = `<td style="color:var(--accent);font-weight:600;">+</td>`;

  // Строим ячейки для каждого поля (те же типы, что и в renderPPTable)
  for (const col of PP_COLUMNS) {
    const isSelectCol = ['dept', 'center', 'executor', 'task_type', 'sector_head'].includes(col);
    const isTextCol   = ['work_name', 'work_order', 'work_designation'].includes(col);
    const isDateCol   = col === 'date_end';

    if (col === 'row_code') {
      // row_code — автогенерация на сервере, read-only
      html += `<td style="font-size:11px;color:var(--muted);padding:4px 6px;">авто</td>`;
    } else if (isSelectCol) {
      html += `<td>${buildSelectHtml(col, newRow)}</td>`;
    } else if (isTextCol) {
      html += `<td><input class="cell-edit" data-col="${col}" data-id="_new_" value="" placeholder="${col === 'work_name' ? 'Наименование' : ''}"></td>`;
    } else if (isDateCol) {
      html += `<td><input type="date" class="cell-edit" data-col="${col}" data-id="_new_" value=""></td>`;
    } else {
      html += `<td><input class="cell-edit cell-num" data-col="${col}" data-id="_new_" value=""></td>`;
    }
  }

  // Последний столбец: кнопки «Сохранить» (✓) и «Отмена» (✕) — в колонке «Действия»
  html += `<td style="text-align:center;white-space:nowrap;">
    <button id="ppNewRowSave" title="Сохранить строку" style="background:var(--success);color:#fff;border:none;border-radius:4px;padding:4px 10px;cursor:pointer;font-size:13px;margin-right:2px;">✓</button>
    <button id="ppNewRowCancel" title="Отмена" style="background:transparent;color:var(--danger);border:1px solid var(--danger);border-radius:4px;padding:4px 8px;cursor:pointer;font-size:13px;">✕</button>
  </td>`;

  tr.innerHTML = html;
  tbody.prepend(tr);

  // Автофокус на первое редактируемое поле
  const firstInput = tr.querySelector('input, select');
  if (firstInput) {
    firstInput.focus();
    tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  // Зависимость: при смене отдела — обновить список нач. секторов И исполнителей
  tr.querySelector('select[data-col="dept"]')?.addEventListener('change', function() {
    newRow.dept = this.value;
    newRow.sector_head = '';  // Сброс сектора при смене отдела
    // Обновляем нач. секторов
    const tdSector = tr.querySelector('select[data-col="sector_head"]')?.closest('td');
    if (tdSector) {
      tdSector.innerHTML = buildSelectHtml('sector_head', newRow);
      tdSector.querySelector('select').addEventListener('change', function() { newRow.sector_head = this.value; });
    }
    // Обновляем список исполнителей по новому отделу
    const tdExec = tr.querySelector('select[data-col="executor"]')?.closest('td');
    if (tdExec) {
      tdExec.innerHTML = buildSelectHtml('executor', newRow);
      tdExec.querySelector('select').addEventListener('change', function() { newRow.executor = this.value; });
    }
  });

  // Зависимость: при смене сектора — обновить список исполнителей
  tr.querySelector('select[data-col="sector_head"]')?.addEventListener('change', function() {
    newRow.sector_head = this.value;
    const tdExec = tr.querySelector('select[data-col="executor"]')?.closest('td');
    if (tdExec) {
      tdExec.innerHTML = buildSelectHtml('executor', newRow);
      tdExec.querySelector('select').addEventListener('change', function() { newRow.executor = this.value; });
    }
  });

  // Зависимость: при смене НТЦ — ничего дополнительно (исполнители фильтруются по отделу/сектору)
  tr.querySelector('select[data-col="center"]')?.addEventListener('change', function() {
    newRow.center = this.value;
  });

  // Собирает данные из новой строки и отправляет POST /api/production_plan/create/
  async function doSaveNewRow() {
    const body = { project_id: currentProjectId };
    // Читаем значения всех полей новой строки
    tr.querySelectorAll('[data-id="_new_"]').forEach(inp => {
      body[inp.getAttribute('data-col')] = inp.value;
    });

    const saveBtn = document.getElementById('ppNewRowSave');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = '...'; }

    let resp;
    try {
    // POST /api/production_plan/create/
    resp = await fetchJson('/api/production_plan/create/', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    } catch (e) {
      console.error('Ошибка сохранения строки:', e);
      showToast('Ошибка сети', 'error');
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '✓'; }
      return;
    }

    if (!resp._error) {
      _addingRow = false;
      tr.remove();
      // Сбрасываем фильтры, чтобы новая запись была точно видна
      colFilters = {};
      mfSelections = {};
      document.querySelectorAll('.mf-trigger.active').forEach(b => {
        b.classList.remove('active');
        b.textContent = '▼';
      });
      document.getElementById('filtersActiveBadge').style.display = 'none';
      // Сбрасываем панель периода
      ppSelectedMonth = null;
      ppSelectedYear = new Date().getFullYear();
      document.getElementById('ppYearDisplay').textContent = ppSelectedYear;
      document.querySelectorAll('.pp-cal-month').forEach(el => el.classList.remove('active'));
      // Сбрасываем чипы отделов
      ppSelectedDept = null;
      document.querySelectorAll('.pp-dept-chip').forEach(c => {
        c.classList.toggle('active', !c.dataset.dept);
      });
      if (currentProjectId) sessionStorage.setItem('pp_dept_filter_cleared_' + currentProjectId, '1');
      // Вставляем новую запись в начало rows напрямую (не зависим от лимита пагинации)
      if (resp.work) {
        rows = rows.filter(r => r.id !== resp.work.id);
        rows.unshift(resp.work);
      } else {
        await loadPPRows(currentProjectId);
      }
      renderPPTable();
      initPPPeriodBar();
      initPPDeptChips();
      showToast('Строка добавлена', 'success');
      // Прокрутить к новой строке по id
      const newId = resp.id;
      const newTr = document.querySelector(`#ppTableBody tr[data-id="${newId}"]`);
      if (newTr) newTr.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      showToast(resp.error || 'Ошибка сохранения строки', 'error');
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '✓'; }
    }
  }

  // Кнопка «Сохранить» (✓)
  document.getElementById('ppNewRowSave').addEventListener('click', doSaveNewRow);

  // Кнопка «Отмена» (✕): убрать строку без сохранения
  document.getElementById('ppNewRowCancel').addEventListener('click', () => {
    _addingRow = false;
    tr.remove();
  });

  // Enter в любом поле — сохранить; Escape — отменить
  tr.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); doSaveNewRow(); }
      if (e.key === 'Escape') { _addingRow = false; tr.remove(); }
    });
  });

  // Авто-расчёт трудоёмкости при вводе sheets_a4 / norm / coeff в новой строке
  tr.querySelectorAll('input[data-col="sheets_a4"], input[data-col="norm"], input[data-col="coeff"]').forEach(inp => {
    inp.addEventListener('input', () => {
      let sheets = null, norm = null, coeff = null;
      tr.querySelectorAll('input').forEach(i => {
        const col = i.getAttribute('data-col');
        const v = parseFloat(i.value.replace(',', '.'));
        if (col === 'sheets_a4' && !isNaN(v)) sheets = v;
        if (col === 'norm'      && !isNaN(v)) norm   = v;
        if (col === 'coeff'     && !isNaN(v)) coeff  = v;
      });
      const laborInput = tr.querySelector('input[data-col="labor"]');
      if (laborInput) {
        laborInput.value = (sheets !== null && norm !== null && coeff !== null)
          ? +(sheets * norm * coeff).toFixed(2)
          : '';
      }
    });
  });
}

/* ── Статистика ПП ───────────────────────────────────────────────────── */

function togglePPStats() {
  const dd = document.getElementById('ppStatsDropdown');
  if (dd.classList.contains('open')) { dd.classList.remove('open'); return; }

  // Считаем по всем строкам проекта (не фильтрованным)
  const executors = new Set();
  let totalLabor = 0;
  let doneLabor = 0;

  rows.forEach(r => {
    if (r.executor) executors.add(r.executor);
    const lab = parseFloat(r.labor);
    if (!isNaN(lab)) {
      totalLabor += lab;
      if (r.has_reports) doneLabor += lab;
    }
  });

  const fmt = v => v % 1 === 0 ? v : v.toFixed(2);

  dd.innerHTML =
    '<div class="pp-stats-row">' +
      '<span class="pp-stats-label">Разработчиков</span>' +
      '<span class="pp-stats-val">' + executors.size + '</span>' +
    '</div>' +
    '<div class="pp-stats-row">' +
      '<span class="pp-stats-label">Трудоёмкость план / выполнено</span>' +
      '<span class="pp-stats-val">' + fmt(totalLabor) + ' / ' + fmt(doneLabor) + '</span>' +
    '</div>';

  dd.classList.add('open');
}

// Закрытие дропдауна статистики по клику вне
document.addEventListener('click', function(e) {
  const wrap = document.querySelector('.pp-stats-wrap');
  const dd = document.getElementById('ppStatsDropdown');
  if (wrap && dd && !wrap.contains(e.target)) dd.classList.remove('open');
});

/* ── Синхронизация ПП → модуль «План/отчёт» ────────────────────────── */
// Переносит строки ПП в задачи модуля ПО (если заполнены все обязательные поля)
async function syncToTasks() {
  // Синхронизация возможна только когда открыт конкретный проект
  if (!currentProjectId) {
    showToast('Откройте проект для синхронизации', 'error');
    return;
  }
  const ok = await confirmDialog(
    'Синхронизировать данные с модулем "План/отчёт"?',
    'Синхронизация'
  );
  if (!ok) return;

  // Необязательные поля (не требуются для синхронизации)
  // executor — исполнитель назначается позже
  // center, sector_head — не у всех записей есть подразделение/сектор
  // task_type — сервер ставит дефолт «Выпуск нового документа»
  const optionalCols = new Set(['executor', 'center', 'sector_head', 'task_type']);
  const requiredCols = PP_COLUMNS.filter(c => !optionalCols.has(c));

  // Проверка «значение заполнено»: 0 — допустимое значение, пустая строка — нет
  function isFilled(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'number') return true;
    return String(v).trim() !== '';
  }

  // Синхронизируем только отфильтрованные строки (видимые в таблице)
  const filteredRows = rows.filter(row => {
    for (const [col, val] of Object.entries(colFilters)) {
      if (col.startsWith('mf_')) {
        const field = col.slice(3);
        if (val.size > 0) {
          const cellVal = (field === 'date_end')
            ? (row[field] || '').slice(0, 7)
            : (row[field] || '');
          if (!val.has(cellVal)) return false;
        }
        continue;
      }
      const cellVal = (row[col] || '').toString().toLowerCase();
      if (!cellVal.includes(val)) return false;
    }
    return true;
  });

  // Сбрасываем предыдущие ошибки валидации
  document.querySelectorAll('.cell-error').forEach(el => el.classList.remove('cell-error'));

  let hasErrors = false;
  let errorCount = 0;

  // Проверяем каждую отфильтрованную строку на наличие обязательных полей
  for (const row of filteredRows) {
    // Пропускаем полностью пустые строки
    const allEmpty = PP_COLUMNS.every(c => !isFilled(row[c]));
    if (allEmpty) continue;

    const missingCols = requiredCols.filter(c => !isFilled(row[c]));
    if (missingCols.length > 0) {
      hasErrors = true;
      errorCount++;
      // Подсвечиваем незаполненные обязательные ячейки красным
      for (const col of missingCols) {
        const input = document.querySelector(
          `#ppTableBody [data-col="${col}"][data-id="${row.id}"]`
        );
        if (input) {
          input.classList.add('cell-error');
          // Первую ошибочную ячейку прокрутить в видимую область
          if (errorCount === 1 && col === missingCols[0]) {
            input.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }
      }
    }
  }

  // Если есть незаполненные обязательные поля — прерываем синхронизацию
  if (hasErrors) {
    showToast('Обнаружены строки с незаполненными ячейками (выделены красным). Обязательны все поля, кроме: Исполнитель, Подразделение, Сектор, Тип задачи.', 'error');
    return;
  }

  // Передаём серверу ids только отфильтрованных строк
  const filteredIds = filteredRows.map(r => r.id);

  // POST /api/production_plan/sync/ — запускаем перенос данных на сервере
  const resp = await fetchJson('/api/production_plan/sync/', {
    method: 'POST',
    body: JSON.stringify({ project_id: currentProjectId, ids: filteredIds }),
  });
  if (!resp._error) {
    // Показываем сколько задач перенесено/обновлено
    const n = resp.synced || 0;
    let msg = n > 0
      ? `Синхронизировано записей: ${n}`
      : 'Все записи уже синхронизированы';
    showToast(msg, 'success');
  }
}

/* ── Сортировка столбцов ─────────────────────────────────────────────── */
var _ppSortState = { col: null, dir: 'asc' };

function _ppInitSort() {
    var thead = document.querySelector('#ppTable thead');
    if (!thead) return;
    thead.querySelectorAll('th[data-sort]').forEach(function(th) {
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.addEventListener('click', function(e) {
            if (e.target.classList.contains('col-resize') || e.target.classList.contains('mf-trigger')) return;
            toggleSort(_ppSortState, th.getAttribute('data-sort'));
            renderSortIndicators(thead, _ppSortState);
            renderPPTable();
        });
    });
    renderSortIndicators(thead, _ppSortState);
}

/* ── Мультифильтры по столбцам ───────────────────────────────────────── */
// Активные фильтры: { 'mf_<col>': Set<значений> }
let colFilters = {};
// Текущие выборки в дропдаунах фильтров
let mfSelections = {};
// Ссылки на активный дропдаун и его кнопку-триггер
let activeMfBtn = null;
let activeMfDropdown = null;

// Дефолтный текст кнопок-триггеров (треугольник ▼)
const MF_DEFAULTS = {};
PP_COLUMNS.forEach(c => { MF_DEFAULTS[c] = '\u25BC'; });

// ── PERIOD FILTER (год + месяц, клиентская фильтрация по date_end) ────────
let ppSelectedYear = new Date().getFullYear();
let ppSelectedMonth = null; // null = все месяцы

function initPPPeriodBar() {
  const bar = document.getElementById('ppPeriodBar');
  // Показываем панель периода если есть строки с датой
  const hasDates = rows.some(r => r.date_end);
  bar.style.display = hasDates ? '' : 'none';
  document.getElementById('ppYearDisplay').textContent = ppSelectedYear;
  document.querySelectorAll('.pp-cal-month').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.m) === ppSelectedMonth);
  });
}

function ppChangeYear(d) {
  ppSelectedYear += d;
  document.getElementById('ppYearDisplay').textContent = ppSelectedYear;
  _applyPPPeriodFilter();
}

function ppSelectMonth(m) {
  ppSelectedMonth = (ppSelectedMonth === m) ? null : m;
  document.querySelectorAll('.pp-cal-month').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.m) === ppSelectedMonth);
  });
  _applyPPPeriodFilter();
}

function ppClearPeriod() {
  ppSelectedMonth = null;
  ppSelectedYear = new Date().getFullYear();
  document.getElementById('ppYearDisplay').textContent = ppSelectedYear;
  document.querySelectorAll('.pp-cal-month').forEach(el => el.classList.remove('active'));
  // Убираем date_end фильтр из colFilters
  delete colFilters['mf_date_end'];
  mfSelections['date_end'] = new Set();
  const btn = document.querySelector('.mf-trigger[data-col="date_end"]');
  if (btn) { btn.textContent = MF_DEFAULTS['date_end'] || '\u25BC'; btn.classList.remove('active'); }
  const hasFilters = Object.keys(colFilters).length > 0;
  document.getElementById('filtersActiveBadge').style.display = hasFilters ? 'inline' : 'none';
  renderPPTable();
}

function _applyPPPeriodFilter() {
  // Формируем фильтр по date_end через year-month ключи
  const yearStr = String(ppSelectedYear);
  if (ppSelectedMonth) {
    const key = yearStr + '-' + String(ppSelectedMonth).padStart(2, '0');
    mfSelections['date_end'] = new Set([key]);
    colFilters['mf_date_end'] = new Set([key]);
  } else {
    // Все месяцы выбранного года — собираем ключи из данных
    const keys = new Set();
    rows.forEach(r => {
      if (r.date_end && r.date_end.startsWith(yearStr)) keys.add(r.date_end.slice(0, 7));
    });
    if (keys.size > 0) {
      mfSelections['date_end'] = keys;
      colFilters['mf_date_end'] = keys;
    } else {
      // Нет данных за этот год — фильтр по невозможному значению
      mfSelections['date_end'] = new Set([yearStr + '-00']);
      colFilters['mf_date_end'] = new Set([yearStr + '-00']);
    }
  }
  // Обновляем кнопку mf-trigger для date_end
  const btn = document.querySelector('.mf-trigger[data-col="date_end"]');
  if (btn) {
    if (ppSelectedMonth) {
      btn.textContent = formatYearMonth(yearStr + '-' + String(ppSelectedMonth).padStart(2, '0'));
    } else {
      btn.textContent = yearStr;
    }
    btn.classList.add('active');
  }
  const hasFilters = Object.keys(colFilters).length > 0;
  document.getElementById('filtersActiveBadge').style.display = hasFilters ? 'inline' : 'none';
  renderPPTable();
}

// ── DEPT CHIPS (чипы отделов как в СП) ───────────────────────────────────
let ppSelectedDept = null;

function initPPDeptChips() {
  const depts = [...new Set(rows.map(r => r.dept).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru'));
  const bar = document.getElementById('ppDeptBar');
  const wrap = document.getElementById('ppDeptChips');
  if (depts.length < 2) { bar.style.display = 'none'; return; }
  // Восстанавливаем выбор из текущего фильтра
  const currentDeptFilter = colFilters['mf_dept'];
  if (currentDeptFilter && currentDeptFilter.size === 1) {
    ppSelectedDept = [...currentDeptFilter][0];
  }
  let html = `<span class="pp-dept-chip${!ppSelectedDept ? ' active' : ''}" onclick="selectPPDept(null)">Все</span>`;
  depts.forEach(d => {
    html += `<span class="pp-dept-chip${ppSelectedDept === d ? ' active' : ''}" data-dept="${escapeHtml(d)}" onclick="selectPPDept(this.dataset.dept)">${escapeHtml(d)}</span>`;
  });
  wrap.innerHTML = html;
  bar.style.display = '';
}

function selectPPDept(dept) {
  ppSelectedDept = dept;
  // Подсветка активного чипа
  document.querySelectorAll('.pp-dept-chip').forEach(c => {
    c.classList.toggle('active', dept ? c.dataset.dept === dept : !c.dataset.dept);
  });
  _syncPPDeptFilter(dept);
  renderPPTable();
}

function _syncPPDeptFilter(dept) {
  const btn = document.querySelector('.mf-trigger[data-col="dept"]');
  if (dept) {
    mfSelections['dept'] = new Set([dept]);
    colFilters['mf_dept'] = new Set([dept]);
    if (btn) { btn.textContent = dept; btn.classList.add('active'); }
  } else {
    delete colFilters['mf_dept'];
    mfSelections['dept'] = new Set();
    if (btn) { btn.textContent = MF_DEFAULTS['dept'] || '\u25BC'; btn.classList.remove('active'); }
  }
  const hasFilters = Object.keys(colFilters).length > 0;
  document.getElementById('filtersActiveBadge').style.display = hasFilters ? 'inline' : 'none';
  // Запоминаем сброс дефолтного фильтра
  if (currentProjectId && !dept) sessionStorage.setItem('pp_dept_filter_cleared_' + currentProjectId, '1');
}

// Названия месяцев для читабельного отображения дат в фильтре
const MONTH_NAMES_RU = [
  'Январь','Февраль','Март','Апрель','Май','Июнь',
  'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'
];

// Возвращает отсортированный массив уникальных значений столбца col из rows.
// Для date_end — группирует по году-месяцу (YYYY-MM), остальные — как есть.
function getMfValues(col) {
  const vals = new Set();
  // Для сектора: если выбран фильтр по отделу — показываем только секторы этих отделов
  let sourceRows = rows;
  if (col === 'sector_head') {
    const deptFilter = colFilters['mf_dept'];
    if (deptFilter && deptFilter.size > 0) {
      // Находим id выбранных отделов
      const deptIds = new Set();
      (dirs.dept || []).forEach(d => { if (deptFilter.has(d.value)) deptIds.add(d.id); });
      // Берём только секторы, входящие в эти отделы (из справочника)
      const validSectors = new Set();
      (dirs.sector_head || []).forEach(s => { if (deptIds.has(s.parent_id)) validSectors.add(s.value); });
      sourceRows = rows.filter(r => validSectors.has(r[col]));
    }
  }
  if (col === 'date_end') {
    // Срок выполнения: берём только год-месяц (первые 7 символов «YYYY-MM»)
    sourceRows.forEach(r => {
      if (r[col] && r[col].length >= 7) vals.add(r[col].slice(0, 7));
    });
  } else {
    sourceRows.forEach(r => { if (r[col]) vals.add(r[col]); });
  }
  return [...vals].sort((a, b) => String(a).localeCompare(String(b), 'ru'));
}

// Форматирует значение «YYYY-MM» в читабельный вид «Март 2026»
function formatYearMonth(ym) {
  const [y, m] = ym.split('-');
  const mi = parseInt(m, 10) - 1;
  return (MONTH_NAMES_RU[mi] || m) + ' ' + y;
}

// Строит и отображает дропдаун мультифильтра для кнопки btn и столбца col
function buildMfDropdown(btn, col) {
  // Убираем предыдущий дропдаун
  if (activeMfDropdown) activeMfDropdown.remove();
  const vals = getMfValues(col);
  const selected = mfSelections[col] || new Set();
  const drop = document.createElement('div');
  drop.className = 'mf-dropdown open';
  drop.dataset.col = col;

  // Поле поиска внутри дропдауна
  const searchWrap = document.createElement('div');
  searchWrap.className = 'mf-search';
  const searchInp = document.createElement('input');
  searchInp.placeholder = 'Поиск...';
  searchInp.autocomplete = 'off';
  // Фильтрация опций при наборе текста (ищем и по коду, и по отображаемому тексту)
  searchInp.oninput = () => {
    const q = searchInp.value.toLowerCase();
    drop.querySelectorAll('.mf-option').forEach(opt => {
      const rawVal = opt.dataset.val.toLowerCase();
      let displayVal = rawVal;
      if (col === 'date_end') displayVal = formatYearMonth(opt.dataset.val).toLowerCase();
      else if (col === 'sector_head') {
        const sh = (dirs.sector_head || []).find(h => h.value === opt.dataset.val);
        if (sh && sh.head_name) displayVal = (opt.dataset.val + ' ' + sh.head_name).toLowerCase();
      }
      opt.style.display = (rawVal.includes(q) || displayVal.includes(q)) ? '' : 'none';
    });
  };
  searchWrap.appendChild(searchInp);
  drop.appendChild(searchWrap);

  // Кнопки «Все» и «Сброс»
  const actions = document.createElement('div');
  actions.className = 'mf-actions';
  const selectAll = document.createElement('button');
  selectAll.className = 'mf-btn';
  selectAll.textContent = 'Все';
  // «Все»: выбрать все значения
  selectAll.onclick = (e) => {
    e.stopPropagation();
    mfSelections[col] = new Set(vals);
    drop.querySelectorAll('.mf-option input').forEach(cb => cb.checked = true);
    applyMfFilter(col, btn);
  };
  const clearMfBtn = document.createElement('button');
  clearMfBtn.className = 'mf-btn';
  clearMfBtn.textContent = 'Сброс';
  // «Сброс»: снять все галочки
  clearMfBtn.onclick = (e) => {
    e.stopPropagation();
    mfSelections[col] = new Set();
    drop.querySelectorAll('.mf-option input').forEach(cb => cb.checked = false);
    applyMfFilter(col, btn);
  };
  actions.appendChild(selectAll);
  actions.appendChild(clearMfBtn);
  drop.appendChild(actions);

  // Список опций с чекбоксами
  vals.forEach(val => {
    const opt = document.createElement('div');
    opt.className = 'mf-option';
    opt.dataset.val = val;
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = selected.has(val);
    // Переключение чекбокса при клике на строку
    const toggle = () => {
      cb.checked = !cb.checked;
      const sel = mfSelections[col] || new Set();
      if (cb.checked) sel.add(val); else sel.delete(val);
      mfSelections[col] = sel;
      applyMfFilter(col, btn);
    };
    cb.onchange = () => {
      const sel = mfSelections[col] || new Set();
      if (cb.checked) sel.add(val); else sel.delete(val);
      mfSelections[col] = sel;
      applyMfFilter(col, btn);
    };
    opt.onclick = (e) => { if (e.target !== cb) toggle(); };
    opt.appendChild(cb);
    // Для date_end отображаем «Март 2026»
    let displayText = val;
    if (col === 'date_end') {
      displayText = formatYearMonth(val);
    }
    opt.appendChild(document.createTextNode(displayText));
    drop.appendChild(opt);
  });

  // Позиционируем дропдаун под кнопкой-триггером
  document.body.appendChild(drop);
  const rect = btn.getBoundingClientRect();
  drop.style.top = (rect.bottom + 2) + 'px';
  drop.style.left = Math.min(rect.left, window.innerWidth - 250) + 'px';
  activeMfDropdown = drop;
  activeMfBtn = btn;
  // Автофокус на поле поиска
  setTimeout(() => searchInp.focus(), 50);
}

// Открывает/закрывает дропдаун мультифильтра при клике на триггер
function toggleMf(btn) {
  // Если этот же дропдаун уже открыт — закрыть
  if (activeMfDropdown && activeMfBtn === btn) {
    activeMfDropdown.remove();
    activeMfDropdown = null;
    activeMfBtn = null;
    return;
  }
  buildMfDropdown(btn, btn.dataset.col);
}

// Обновляет colFilters и перерисовывает таблицу при изменении выборки фильтра
function applyMfFilter(col, btn) {
  const sel = mfSelections[col] || new Set();
  const def = MF_DEFAULTS[col] || '\u25BC';
  if (sel.size === 0) {
    // Нет выбранных значений — убираем фильтр
    delete colFilters['mf_' + col];
    btn.textContent = def;
    btn.classList.remove('active');
  } else {
    // Обновляем активный фильтр
    colFilters['mf_' + col] = sel;
    // Текст кнопки: одно значение (для date_end — «Март 2026») или «N выбрано»
    if (sel.size === 1) {
      const singleVal = [...sel][0];
      btn.textContent = (col === 'date_end') ? formatYearMonth(singleVal) : singleVal;
    } else {
      btn.textContent = sel.size + ' выбрано';
    }
    btn.classList.add('active');
  }
  // Показываем/скрываем бейдж сброса всех фильтров
  const hasFilters = Object.keys(colFilters).length > 0;
  document.getElementById('filtersActiveBadge').style.display = hasFilters ? 'inline' : 'none';
  // Синхронизируем панель периода если изменён date_end-фильтр через дропдаун
  if (col === 'date_end') {
    ppSelectedMonth = null;
    document.querySelectorAll('.pp-cal-month').forEach(el => el.classList.remove('active'));
    // Если выбран один месяц — подсветить в панели периода
    if (sel.size === 1) {
      const val = [...sel][0];
      const parts = val.split('-');
      if (parts.length === 2) {
        ppSelectedYear = parseInt(parts[0]) || ppSelectedYear;
        ppSelectedMonth = parseInt(parts[1]) || null;
        document.getElementById('ppYearDisplay').textContent = ppSelectedYear;
        if (ppSelectedMonth) {
          const mEl = document.querySelector(`.pp-cal-month[data-m="${ppSelectedMonth}"]`);
          if (mEl) mEl.classList.add('active');
        }
      }
    }
  }
  // Синхронизируем чипы отделов если изменён dept-фильтр через дропдаун
  if (col === 'dept') {
    ppSelectedDept = (sel.size === 1) ? [...sel][0] : null;
    document.querySelectorAll('.pp-dept-chip').forEach(c => {
      c.classList.toggle('active', ppSelectedDept ? c.dataset.dept === ppSelectedDept : !c.dataset.dept);
    });
  }
  renderPPTable();
}

// Сбрасывает все активные фильтры и перерисовывает таблицу
function clearAllColFilters() {
  colFilters = {};
  Object.keys(mfSelections).forEach(k => mfSelections[k] = new Set());
  // Возвращаем все кнопки к дефолтному тексту и убираем active-класс
  document.querySelectorAll('.mf-trigger').forEach(btn => {
    btn.textContent = MF_DEFAULTS[btn.dataset.col] || '\u25BC';
    btn.classList.remove('active');
  });
  if (activeMfDropdown) { activeMfDropdown.remove(); activeMfDropdown = null; activeMfBtn = null; }
  document.getElementById('filtersActiveBadge').style.display = 'none';
  // Сбрасываем панель периода
  ppSelectedMonth = null;
  ppSelectedYear = new Date().getFullYear();
  document.getElementById('ppYearDisplay').textContent = ppSelectedYear;
  document.querySelectorAll('.pp-cal-month').forEach(el => el.classList.remove('active'));
  // Сбрасываем чипы отделов
  ppSelectedDept = null;
  document.querySelectorAll('.pp-dept-chip').forEach(c => {
    c.classList.toggle('active', !c.dataset.dept);
  });
  // Запоминаем что пользователь сбросил дефолтный фильтр вручную
  if (currentProjectId) sessionStorage.setItem('pp_dept_filter_cleared_' + currentProjectId, '1');
  renderPPTable();
}

// Закрываем дропдаун при клике вне его (capture-фаза чтобы перехватить раньше других)
document.addEventListener('click', (e) => {
  if (activeMfDropdown && !activeMfDropdown.contains(e.target) && e.target !== activeMfBtn) {
    activeMfDropdown.remove();
    activeMfDropdown = null;
    activeMfBtn = null;
  }
}, true);

/* ── Изменение ширины столбцов drag-handle ───────────────────────────── */
// Инициализирует drag-resize хэндлы на всех th таблицы
function initColumnResize() {
  document.querySelectorAll('.pp-table th').forEach(th => {
    // Не добавляем повторно если хэндл уже есть
    if (th.querySelector('.resize-handle')) return;
    const handle = document.createElement('div');
    handle.className = 'resize-handle';
    th.appendChild(handle);

    handle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      // Добавляем визуальный класс при начале перетаскивания
      th.classList.add('resizing');
      handle.classList.add('resizing');
      const startX = e.pageX;
      const startWidth = th.offsetWidth;
      const colIndex = th.cellIndex;
      const tblRows = th.closest('table').querySelectorAll('tbody tr');

      // Перемещение мыши: меняем ширину колонки (с rAF throttle)
      let _rafResize = null;
      const onMouseMove = (ev) => {
        if (_rafResize) return;
        _rafResize = requestAnimationFrame(() => {
          _rafResize = null;
          const width = startWidth + (ev.pageX - startX);
          if (width > 30) {
            th.style.width = width + 'px';
            th.style.minWidth = width + 'px';
            tblRows.forEach(row => {
              if (row.cells[colIndex]) {
                row.cells[colIndex].style.width = width + 'px';
                row.cells[colIndex].style.minWidth = width + 'px';
              }
            });
          }
        });
      };
      // Отпустили кнопку мыши: снимаем визуальные классы
      const onMouseUp = () => {
        th.classList.remove('resizing');
        handle.classList.remove('resizing');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
      };
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });
  });
}

/* ── Поддержка навигации браузера (кнопки назад/вперёд) ──────────────── */
// При popstate (кнопки Назад/Вперёд): открываем нужный план или возвращаемся на лендинг
window.addEventListener('popstate', async () => {
  const pid = readProjectFromUrl();
  if (pid) {
    const proj = projects.find(p => String(p.id) === String(pid));
    if (proj) {
      await openProject(proj.id, proj.name);
    }
  } else {
    showLanding();
  }
});

/* ── Инициализация ────────────────────────────────────────────────────── */
(async function init() {
  _initPPDensity();
  _ppInitSort();
  // Параллельно загружаем справочники и список ПП-проектов
  await Promise.all([loadDirs(), loadProjects()]);

  // Если в URL есть project_id — открываем план напрямую (прямая ссылка)
  const urlProjectId = readProjectFromUrl();
  if (urlProjectId) {
    const proj = projects.find(p => String(p.id) === String(urlProjectId));
    if (proj) {
      await openProject(proj.id, proj.name);
    } else {
      // ID не найден — переходим на лендинг
      showLanding();
    }
  } else {
    // Нет project_id в URL — показываем лендинг
    showLanding();
  }

  // Инициализируем drag-resize хэндлы для колонок
  initColumnResize();

  // Экспорт
  buildExportDropdown('exportBtnContainer', {
    pageName: 'ПП',
    columns: [
      { key: 'row_code',         header: 'Код строки',     width: 80,  forceText: true },
      { key: 'work_order',       header: 'Наряд-заказ',    width: 90,  forceText: true },
      { key: 'stage_num',        header: '№ этапа',        width: 60,  forceText: true },
      { key: 'milestone_num',    header: '№ вехи',         width: 60,  forceText: true },
      { key: 'work_num',         header: '№ работы',       width: 60,  forceText: true },
      { key: 'work_designation', header: 'Обозначение',    width: 140 },
      { key: 'work_name',        header: 'Наименование',   width: 240 },
      { key: 'date_end',         header: 'Срок выполнения',width: 100 },
      { key: 'sheets_a4',        header: 'Ф, А4',          width: 60 },
      { key: 'norm',             header: 'Норматив',       width: 70 },
      { key: 'coeff',            header: 'Коэфф',          width: 60 },
      { key: 'labor',            header: 'Трудоёмкость',   width: 90 },
      { key: 'task_type',        header: 'Тип задачи',     width: 160 },
      { key: 'center',           header: 'Подразделение',  width: 90,  forceText: true },
      { key: 'dept',             header: 'Отдел',          width: 80,  forceText: true },
      { key: 'sector_head',      header: 'Сектор',         width: 100, forceText: true },
      { key: 'executor',         header: 'Разработчик',    width: 140 },
    ],
    getAllData:      () => rows,
    getFilteredData: ppGetFilteredRows,
  });
})();

function ppGetFilteredRows() {
  return rows.filter(row => {
    for (const [col, val] of Object.entries(colFilters)) {
      if (col.startsWith('mf_')) {
        const field = col.slice(3);
        if (val.size > 0) {
            const cellVal = (field === 'date_end')
              ? (row[field] || '').slice(0, 7)
              : (row[field] || '');
            if (!val.has(cellVal)) return false;
        }
        continue;
      }
      const cellVal = (row[col] || '').toString().toLowerCase();
      if (!cellVal.includes(val)) return false;
    }
    return true;
  });
}


// ── PP DEPENDENCIES ────────────────────────────────────────────────────
let ppCurrentDepsTaskId = null;

/* ── Searchable predecessor dropdown (PP) ─────────────────────── */
let _ppDepsDropdownItems = [];
let _ppDepsDropdownHighlight = -1;

function _ppPopulateDepsSelect(excludeId) {
  const input = document.getElementById('ppDepsAddPredInput');
  const hidden = document.getElementById('ppDepsAddPredSelect');
  input.value = '';
  hidden.value = '';
  _ppDepsDropdownItems = [];
  rows.forEach(r => {
    if (r.id === excludeId) return;
    const name = r.work_name || r.work_num || '#' + r.id;
    const dept = r.dept ? ` [${r.dept}]` : '';
    _ppDepsDropdownItems.push({ id: r.id, label: name + dept });
  });
  _ppRenderDepsDropdownList('');
}

function _ppRenderDepsDropdownList(filter) {
  const list = document.getElementById('ppDepsAddPredList');
  const lc = filter.toLowerCase();
  const filtered = lc ? _ppDepsDropdownItems.filter(it => it.label.toLowerCase().includes(lc)) : _ppDepsDropdownItems;
  const selectedId = document.getElementById('ppDepsAddPredSelect').value;
  if (filtered.length === 0) {
    list.innerHTML = '<div class="search-dropdown-empty">Ничего не найдено</div>';
  } else {
    list.innerHTML = filtered.map(it =>
      `<div class="search-dropdown-item${it.id == selectedId ? ' selected' : ''}" data-value="${it.id}">${escapeHtml(it.label)}</div>`
    ).join('');
  }
  _ppDepsDropdownHighlight = -1;
}

function _ppHighlightDepsItem(items) {
  items.forEach((it, i) => it.classList.toggle('highlighted', i === _ppDepsDropdownHighlight));
  if (items[_ppDepsDropdownHighlight]) items[_ppDepsDropdownHighlight].scrollIntoView({ block: 'nearest' });
}

(function initPPDepsDropdown() {
  function _init() {
    const input = document.getElementById('ppDepsAddPredInput');
    const list = document.getElementById('ppDepsAddPredList');
    const hidden = document.getElementById('ppDepsAddPredSelect');
    if (!input) return;

    input.addEventListener('focus', () => { _ppRenderDepsDropdownList(input.value); list.classList.add('open'); });
    input.addEventListener('input', () => { _ppRenderDepsDropdownList(input.value); list.classList.add('open'); });

    input.addEventListener('keydown', e => {
      const items = list.querySelectorAll('.search-dropdown-item');
      if (e.key === 'ArrowDown') { e.preventDefault(); _ppDepsDropdownHighlight = Math.min(_ppDepsDropdownHighlight + 1, items.length - 1); _ppHighlightDepsItem(items); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); _ppDepsDropdownHighlight = Math.max(_ppDepsDropdownHighlight - 1, 0); _ppHighlightDepsItem(items); }
      else if (e.key === 'Enter') { e.preventDefault(); if (_ppDepsDropdownHighlight >= 0 && items[_ppDepsDropdownHighlight]) items[_ppDepsDropdownHighlight].click(); }
      else if (e.key === 'Escape') { list.classList.remove('open'); }
    });

    list.addEventListener('click', e => {
      const item = e.target.closest('.search-dropdown-item');
      if (!item) return;
      hidden.value = item.dataset.value;
      input.value = item.textContent;
      list.classList.remove('open');
    });

    document.addEventListener('click', e => {
      if (!e.target.closest('#ppDepsAddPredDropdown')) list.classList.remove('open');
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }
})();

/* ── Searchable successor dropdown (PP) ──────────────────── */
let _ppSuccDropdownItems = [];
let _ppSuccDropdownHighlight = -1;

function _ppPopulateSuccSelect(excludeId) {
  const input = document.getElementById('ppDepsAddSuccInput');
  const hidden = document.getElementById('ppDepsAddSuccSelect');
  input.value = '';
  hidden.value = '';
  _ppSuccDropdownItems = [];
  rows.forEach(r => {
    if (r.id === excludeId) return;
    const name = r.work_name || r.work_num || '#' + r.id;
    const dept = r.dept ? ` [${r.dept}]` : '';
    _ppSuccDropdownItems.push({ id: r.id, label: name + dept });
  });
  _ppRenderSuccDropdownList('');
}

function _ppRenderSuccDropdownList(filter) {
  const list = document.getElementById('ppDepsAddSuccList');
  const lc = filter.toLowerCase();
  const filtered = lc ? _ppSuccDropdownItems.filter(it => it.label.toLowerCase().includes(lc)) : _ppSuccDropdownItems;
  const selectedId = document.getElementById('ppDepsAddSuccSelect').value;
  if (filtered.length === 0) {
    list.innerHTML = '<div class="search-dropdown-empty">Ничего не найдено</div>';
  } else {
    list.innerHTML = filtered.map(it =>
      `<div class="search-dropdown-item${it.id == selectedId ? ' selected' : ''}" data-value="${it.id}">${escapeHtml(it.label)}</div>`
    ).join('');
  }
  _ppSuccDropdownHighlight = -1;
}

function _ppHighlightSuccItem(items) {
  items.forEach((it, i) => it.classList.toggle('highlighted', i === _ppSuccDropdownHighlight));
  if (items[_ppSuccDropdownHighlight]) items[_ppSuccDropdownHighlight].scrollIntoView({ block: 'nearest' });
}

(function initPPSuccDropdown() {
  function _init() {
    const input = document.getElementById('ppDepsAddSuccInput');
    const list = document.getElementById('ppDepsAddSuccList');
    const hidden = document.getElementById('ppDepsAddSuccSelect');
    if (!input) return;

    input.addEventListener('focus', () => { _ppRenderSuccDropdownList(input.value); list.classList.add('open'); });
    input.addEventListener('input', () => { _ppRenderSuccDropdownList(input.value); list.classList.add('open'); });

    input.addEventListener('keydown', e => {
      const items = list.querySelectorAll('.search-dropdown-item');
      if (e.key === 'ArrowDown') { e.preventDefault(); _ppSuccDropdownHighlight = Math.min(_ppSuccDropdownHighlight + 1, items.length - 1); _ppHighlightSuccItem(items); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); _ppSuccDropdownHighlight = Math.max(_ppSuccDropdownHighlight - 1, 0); _ppHighlightSuccItem(items); }
      else if (e.key === 'Enter') { e.preventDefault(); if (_ppSuccDropdownHighlight >= 0 && items[_ppSuccDropdownHighlight]) items[_ppSuccDropdownHighlight].click(); }
      else if (e.key === 'Escape') { list.classList.remove('open'); }
    });

    list.addEventListener('click', e => {
      const item = e.target.closest('.search-dropdown-item');
      if (!item) return;
      hidden.value = item.dataset.value;
      input.value = item.textContent;
      list.classList.remove('open');
    });

    document.addEventListener('click', e => {
      if (!e.target.closest('#ppDepsAddSuccDropdown')) list.classList.remove('open');
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }
})();

async function ppAddSuccessor() {
  const succId = document.getElementById('ppDepsAddSuccSelect').value;
  if (!succId) { showToast('Выберите задачу', 'warning'); return; }
  const depType = document.getElementById('ppDepsAddSuccType').value;
  const lagDays = parseInt(document.getElementById('ppDepsAddSuccLag').value) || 0;
  try {
    const res = await fetch(`/api/tasks/${parseInt(succId)}/dependencies/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ predecessor_id: ppCurrentDepsTaskId, dep_type: depType, lag_days: lagDays }),
    });
    if (!res.ok) {
      let data = {};
      try { data = await res.json(); } catch(_) {}
      showToast(data.error || 'Ошибка', 'error');
      return;
    }
    const data = await res.json();
    showToast('Зависимость добавлена', 'success');
    document.getElementById('ppDepsAddSuccInput').value = '';
    document.getElementById('ppDepsAddSuccSelect').value = '';
    await ppLoadDeps(ppCurrentDepsTaskId);
    const succRow = rows.find(r => r.id === parseInt(succId));
    if (succRow) {
      succRow.predecessors_count = (succRow.predecessors_count || 0) + 1;
      renderPPTable();
    }
  } catch (e) { showToast('Ошибка: ' + e.message, 'error'); }
}

function openPPDepsModal(taskId) {
  ppCurrentDepsTaskId = taskId;
  const row = rows.find(r => r.id === taskId);
  const modal = document.getElementById('ppDepsModal');
  document.getElementById('ppDepsModalTitle').textContent =
    `Зависимости: ${row ? (row.work_name || row.work_num || '#' + taskId) : '#' + taskId}`;
  const ds = row && row.date_start ? row.date_start.split('-').reverse().join('.') : '—';
  const de = row && row.date_end ? row.date_end.split('-').reverse().join('.') : '—';
  document.getElementById('ppDepsModalDates').textContent = `Сроки: ${ds} → ${de}`;
  if (IS_WRITER) {
    document.getElementById('ppDepsAddForm').style.display = '';
    document.getElementById('ppDepsAddSuccForm').style.display = '';
    _ppPopulateDepsSelect(taskId);
    _ppPopulateSuccSelect(taskId);
  } else {
    document.getElementById('ppDepsAddForm').style.display = 'none';
    document.getElementById('ppDepsAddSuccForm').style.display = 'none';
  }
  modal.classList.add('open');
  ppLoadDeps(taskId);
}

function closePPDepsModal() {
  document.getElementById('ppDepsModal').classList.remove('open');
  ppCurrentDepsTaskId = null;
}

async function ppLoadDeps(taskId) {
  try {
    const res = await fetch(`/api/tasks/${taskId}/dependencies/`, { headers: { 'X-CSRFToken': getCsrfToken() } });
    if (!res.ok) { showToast('Ошибка загрузки зависимостей', 'error'); return; }
    const data = await res.json();
    ppRenderPreds(data.predecessors || []);
    ppRenderSuccs(data.successors || []);
    const alignBar = document.getElementById('ppDepsAlignBar');
    const alignText = document.getElementById('ppDepsAlignText');
    const predBtn = document.getElementById('ppDepsAlignPredBtn');
    const succBtn = document.getElementById('ppDepsAlignSuccBtn');
    const hasDeps = (data.predecessors || []).length > 0 || (data.successors || []).length > 0;
    if (data.has_conflict && IS_WRITER) {
      alignBar.style.display = '';
      alignText.textContent = '⚠ Обнаружен конфликт сроков';
      alignText.style.color = 'var(--danger, #e53e3e)';
      predBtn.style.display = data.has_pred_conflict ? '' : 'none';
      succBtn.style.display = data.has_succ_conflict ? '' : 'none';
    } else if (hasDeps) {
      alignBar.style.display = '';
      alignText.textContent = '✓ Даты соответствуют зависимостям';
      alignText.style.color = 'var(--success, #38a169)';
      predBtn.style.display = 'none';
      succBtn.style.display = 'none';
    } else {
      alignBar.style.display = 'none';
    }
  } catch (e) {
    console.error('ppLoadDeps error:', e);
  }
}

function ppRenderPreds(preds) {
  const wrap = document.getElementById('ppDepsPredBody');
  document.getElementById('ppDepsPredCount').textContent = preds.length ? `(${preds.length})` : '';
  if (preds.length === 0) { wrap.innerHTML = '<div style="color:var(--muted);font-size:14px;padding:8px 0;">Нет предшественников</div>'; return; }
  let html = '<table class="deps-table"><thead><tr><th>Задача</th><th>Тип</th><th>Лаг</th><th>Даты</th>';
  if (IS_WRITER) html += '<th style="width:40px;"></th>';
  html += '</tr></thead><tbody>';
  preds.forEach(d => {
    const ds = d.date_start ? d.date_start.split('-').reverse().join('.') : '—';
    const de = d.date_end ? d.date_end.split('-').reverse().join('.') : '—';
    const rowStyle = d.conflict ? 'background:rgba(229,62,62,0.08);' : '';
    const dateColor = d.conflict ? 'color:var(--danger, #e53e3e);font-weight:600;' : 'color:var(--text2);';
    html += `<tr style="${rowStyle}"><td>${escapeHtml(d.work_name || d.work_num || '#' + d.work_id)}</td>`;
    html += `<td><span class="dep-type-badge">${d.dep_type}</span></td>`;
    html += `<td style="font-family:var(--mono);">${d.lag_days}д</td>`;
    html += `<td style="font-size:13px;${dateColor}">${ds} → ${de}${d.conflict ? ' ⚠' : ''}</td>`;
    if (IS_WRITER) html += `<td><button class="btn-delete" onclick="ppDeleteDep(${d.id})" title="Удалить">✕</button></td>`;
    html += '</tr>';
  });
  html += '</tbody></table>';
  wrap.innerHTML = html;
}

function ppRenderSuccs(succs) {
  const wrap = document.getElementById('ppDepsSuccBody');
  document.getElementById('ppDepsSuccCount').textContent = succs.length ? `(${succs.length})` : '';
  if (succs.length === 0) { wrap.innerHTML = '<div style="color:var(--muted);font-size:14px;padding:8px 0;">Нет последователей</div>'; return; }
  let html = '<table class="deps-table"><thead><tr><th>Задача</th><th>Тип</th><th>Лаг</th><th>Даты</th>';
  if (IS_WRITER) html += '<th style="width:40px;"></th>';
  html += '</tr></thead><tbody>';
  succs.forEach(d => {
    const ds = d.date_start ? d.date_start.split('-').reverse().join('.') : '—';
    const de = d.date_end ? d.date_end.split('-').reverse().join('.') : '—';
    const rowStyle = d.conflict ? 'background:rgba(229,62,62,0.08);' : '';
    const dateColor = d.conflict ? 'color:var(--danger, #e53e3e);font-weight:600;' : 'color:var(--text2);';
    html += `<tr style="${rowStyle}"><td>${escapeHtml(d.work_name || d.work_num || '#' + d.work_id)}</td>`;
    html += `<td><span class="dep-type-badge">${d.dep_type}</span></td>`;
    html += `<td style="font-family:var(--mono);">${d.lag_days}д</td>`;
    html += `<td style="font-size:13px;${dateColor}">${ds} → ${de}${d.conflict ? ' ⚠' : ''}</td>`;
    if (IS_WRITER) html += `<td><button class="btn-delete" onclick="ppDeleteDep(${d.id})" title="Удалить">✕</button></td>`;
    html += '</tr>';
  });
  html += '</tbody></table>';
  wrap.innerHTML = html;
}

async function ppAddPredecessor() {
  const predId = document.getElementById('ppDepsAddPredSelect').value;
  if (!predId) { showToast('Выберите задачу', 'warning'); return; }
  const depType = document.getElementById('ppDepsAddType').value;
  const lagDays = parseInt(document.getElementById('ppDepsAddLag').value) || 0;
  try {
    const res = await fetch(`/api/tasks/${ppCurrentDepsTaskId}/dependencies/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ predecessor_id: parseInt(predId), dep_type: depType, lag_days: lagDays }),
    });
    if (!res.ok) {
      let data = {};
      try { data = await res.json(); } catch(_) {}
      showToast(data.error || 'Ошибка', 'error');
      return;
    }
    const data = await res.json();
    showToast('Зависимость добавлена', 'success');
    document.getElementById('ppDepsAddPredInput').value = '';
    document.getElementById('ppDepsAddPredSelect').value = '';
    await ppLoadDeps(ppCurrentDepsTaskId);
    const row = rows.find(r => r.id === ppCurrentDepsTaskId);
    if (row) row.predecessors_count = (row.predecessors_count || 0) + 1;
    renderPPTable();
  } catch (e) { showToast('Ошибка: ' + e.message, 'error'); }
}

async function ppDeleteDep(depId) {
  const ok = await confirmDialog('Удалить эту зависимость?', 'Удаление');
  if (!ok) return;
  try {
    const res = await fetch(`/api/dependencies/${depId}/`, {
      method: 'DELETE', headers: { 'X-CSRFToken': getCsrfToken() },
    });
    if (res.ok) {
      showToast('Зависимость удалена', 'success');
      await ppLoadDeps(ppCurrentDepsTaskId);
      const row = rows.find(r => r.id === ppCurrentDepsTaskId);
      if (row) row.predecessors_count = Math.max(0, (row.predecessors_count || 0) - 1);
      renderPPTable();
    } else { showToast('Ошибка удаления', 'error'); }
  } catch (e) { showToast('Ошибка', 'error'); }
}

async function ppAlignDates(cascade) {
  const msg = cascade
    ? 'Выровнять даты всех последователей по зависимостям?'
    : 'Выровнять даты этой задачи по предшественникам?';
  if (!await confirmDialog(msg)) return;
  try {
    const res = await fetch(`/api/tasks/${ppCurrentDepsTaskId}/align_dates/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ cascade }),
    });
    const data = await res.json();
    if (res.ok) {
      showToast(`Даты выровнены (${data.aligned_count} задач)`, 'success');
      ppLoadDeps(ppCurrentDepsTaskId);
      await loadPPRows(currentProjectId);
      renderPPTable();
    } else { showToast(data.error || 'Ошибка', 'error'); }
  } catch (e) { showToast('Ошибка', 'error'); }
}

// Закрытие модала кликом по фону
document.getElementById('ppDepsModal').addEventListener('click', function(e) {
  if (e.target === this) closePPDepsModal();
});


// ── PP Gantt View ──────────────────────────────────────────────────────
let ppGanttLoaded = false;

function ppSwitchView(view) {
  document.querySelectorAll('.pp-view-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.view === view);
  });
  const tableEl = document.getElementById('ppTableView');
  const ganttEl = document.getElementById('ppGanttContainer');
  const scaleGroup = document.getElementById('ppGanttScaleGroup');
  if (view === 'table') {
    tableEl.style.display = '';
    ganttEl.style.display = 'none';
    if (scaleGroup) scaleGroup.style.display = 'none';
  } else {
    tableEl.style.display = 'none';
    ganttEl.style.display = 'block';
    if (scaleGroup) scaleGroup.style.display = '';
    if (!ppGanttLoaded) {
      ppLoadGantt();
      ppGanttLoaded = true;
    } else {
      ppRenderGantt();
    }
  }
}

function ppSetGanttScale(scale) {
  if (typeof gantt === 'undefined') return;
  document.querySelectorAll('#ppGanttScaleGroup .gantt-scale-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.scale === scale));
  if (scale === 'day') {
    gantt.config.scale_unit = 'month';
    gantt.config.date_scale = '%M %Y';
    gantt.config.subscales = [{ unit: 'day', step: 1, date: '%d' }];
    gantt.config.min_column_width = 28;
  } else if (scale === 'week') {
    gantt.config.scale_unit = 'month';
    gantt.config.date_scale = '%M %Y';
    gantt.config.subscales = [{ unit: 'week', step: 1, date: '%d — ' }];
    gantt.config.min_column_width = 60;
  } else if (scale === 'month') {
    gantt.config.scale_unit = 'year';
    gantt.config.date_scale = '%Y';
    gantt.config.subscales = [{ unit: 'month', step: 1, date: '%M' }];
    gantt.config.min_column_width = 50;
  } else if (scale === 'year') {
    gantt.config.scale_unit = 'year';
    gantt.config.date_scale = '%Y';
    gantt.config.subscales = [];
    gantt.config.min_column_width = 80;
  }
  gantt.render();
}

function ppLoadGantt() {
  // Проверить загружен ли уже gantt (может быть из СП)
  if (typeof gantt !== 'undefined') { ppSetupGantt(); ppRenderGantt(); return; }
  const cssLink = document.createElement('link');
  cssLink.rel = 'stylesheet';
  cssLink.href = '/static/lib/dhtmlxgantt/dhtmlxgantt.css';
  document.head.appendChild(cssLink);
  const script = document.createElement('script');
  script.src = '/static/lib/dhtmlxgantt/dhtmlxgantt.js';
  script.onload = () => { ppSetupGantt(); ppRenderGantt(); };
  script.onerror = () => {
    document.getElementById('ppGanttContainer').innerHTML =
      '<div style="padding:40px;text-align:center;color:var(--muted);font-size:16px;">' +
      '⚠ Библиотека dhtmlxGantt не загружена.</div>';
  };
  document.head.appendChild(script);
}

function _applyGanttLocaleRu() {
  if (typeof gantt === 'undefined') return;
  gantt.locale = {
    date: {
      month_full: ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"],
      month_short: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"],
      day_full: ["Воскресенье","Понедельник","Вторник","Среда","Четверг","Пятница","Суббота"],
      day_short: ["Вс","Пн","Вт","Ср","Чт","Пт","Сб"]
    },
    labels: {
      new_task: "Новая задача",
      icon_save: "Сохранить",
      icon_cancel: "Отмена",
      icon_details: "Детали",
      icon_edit: "Редактировать",
      icon_delete: "Удалить",
      confirm_closing: "",
      confirm_deleting: "Удалить запись?",
      section_description: "Описание",
      section_time: "Период",
      section_type: "Тип",
      column_text: "Задача",
      column_start_date: "Начало",
      column_duration: "Длительность",
      column_add: "",
      link: "Связь",
      confirm_link_deleting: "Удалить связь?",
      link_start: "(начало)",
      link_end: "(конец)",
      type_task: "Задача",
      type_project: "Проект",
      type_milestone: "Веха",
      minutes: "мин",
      hours: "ч",
      days: "дн",
      weeks: "нед",
      months: "мес",
      years: "лет"
    }
  };
}

function ppSetupGantt() {
  if (typeof gantt === 'undefined') return;
  _applyGanttLocaleRu();
  gantt.config.date_format = "%Y-%m-%d";
  gantt.config.scale_unit = "year";
  gantt.config.date_scale = "%Y";
  gantt.config.subscales = [{ unit: "month", step: 1, date: "%M" }];
  gantt.config.min_column_width = 50;
  gantt.config.columns = [
    { name: "text", label: "Задача", width: 200, tree: false },
    { name: "designation", label: "Обозначение", width: 140, align: "left" },
    { name: "work_name_full", label: "Наименование", width: 160, align: "left" },
    { name: "start_date", label: "Начало", align: "center", width: 90 },
    { name: "end_date", label: "Окончание", align: "center", width: 90 },
  ];
  gantt.config.readonly = true;
  gantt.config.show_links = false;
  gantt.config.drag_links = false;
  gantt.config.drag_move = false;
  gantt.config.drag_resize = false;
  gantt.init("ppGanttContainer");
}

async function ppRenderGantt() {
  if (typeof gantt === 'undefined' || !currentProjectId) return;
  try {
    const filteredRows = rows.filter(r => r.date_end);
    const ganttData = {
      data: filteredRows.map(r => ({
        id: r.id,
        text: r.work_name || r.work_num || '#' + r.id,
        designation: r.work_designation || '',
        work_name_full: r.work_name || '',
        start_date: r.date_start || r.date_end,
        end_date: r.date_end,
      })),
      links: [],
    };
    gantt.clearAll();
    gantt.parse(ganttData);
    gantt.render();
  } catch (e) { console.error('ppRenderGantt error:', e); }
}

