/**
 * Клиентский экспорт данных таблиц в Excel (SpreadsheetML) и XML.
 * Используется на всех SPA-страницах с таблицами.
 *
 * Публичные функции:
 *   buildExportDropdown(containerId, config)
 *   exportToExcel(data, columns, pageName)
 *   exportToXml(data, columns, pageName)
 */

/* ── Вспомогательные ───────────────────────────────────────────────────── */

function _escXml(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _isNum(v) {
    if (typeof v === 'number' && isFinite(v)) return true;
    if (typeof v === 'string' && /^-?\d+([.,]\d+)?$/.test(v.trim())) return true;
    return false;
}

function _makeExportFilename(pageName, ext) {
    const now = new Date();
    const d = now.toISOString().slice(0, 10);
    const t = String(now.getHours()).padStart(2, '0')
            + String(now.getMinutes()).padStart(2, '0')
            + String(now.getSeconds()).padStart(2, '0');
    return `${pageName}_${d}_${t}.${ext}`;
}

function _triggerDownload(content, filename, mimeType) {
    const blob = new Blob(['\uFEFF' + content], { type: mimeType + ';charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 200);
}

/* ── Excel (SpreadsheetML XML) ─────────────────────────────────────────── */

function exportToExcel(data, columns, pageName) {
    if (!data || !data.length) {
        showToast('Нет данных для экспорта', 'warning');
        return;
    }

    let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
    xml += '<?mso-application progid="Excel.Sheet"?>\n';
    xml += '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"\n';
    xml += ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n';

    // Стили
    xml += '<Styles>\n';
    xml += '  <Style ss:ID="hdr">';
    xml += '<Font ss:Bold="1" ss:Size="11"/>';
    xml += '<Interior ss:Color="#D9E1F2" ss:Pattern="Solid"/>';
    xml += '<Alignment ss:Horizontal="Center" ss:WrapText="1"/>';
    xml += '</Style>\n';
    xml += '  <Style ss:ID="def"><Alignment ss:WrapText="1"/></Style>\n';
    xml += '</Styles>\n';

    // Лист
    xml += '<Worksheet ss:Name="Данные">\n<Table>\n';

    // Ширины колонок
    columns.forEach(c => {
        xml += `  <Column ss:Width="${c.width || 100}"/>\n`;
    });

    // Заголовки
    xml += '  <Row ss:StyleID="hdr">\n';
    columns.forEach(c => {
        xml += `    <Cell><Data ss:Type="String">${_escXml(c.header)}</Data></Cell>\n`;
    });
    xml += '  </Row>\n';

    // Данные
    data.forEach(row => {
        xml += '  <Row ss:StyleID="def">\n';
        columns.forEach(c => {
            const val = c.format ? c.format(row) : row[c.key];
            // forceText: true — всегда String (коды с вед. нулями: dept, sector и т.п.)
            const type = c.forceText ? 'String' : (_isNum(val) ? 'Number' : 'String');
            const display = val == null ? '' : val;
            xml += `    <Cell><Data ss:Type="${type}">${_escXml(display)}</Data></Cell>\n`;
        });
        xml += '  </Row>\n';
    });

    xml += '</Table>\n</Worksheet>\n</Workbook>';

    _triggerDownload(xml, _makeExportFilename(pageName, 'xls'), 'application/vnd.ms-excel');
    showToast(`Excel: ${data.length} записей`, 'success');
}

/* ── XML ───────────────────────────────────────────────────────────────── */

function exportToXml(data, columns, pageName) {
    if (!data || !data.length) {
        showToast('Нет данных для экспорта', 'warning');
        return;
    }

    const now = new Date().toISOString().slice(0, 19);
    let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
    xml += `<Export page="${_escXml(pageName)}" date="${now}" count="${data.length}">\n`;

    data.forEach(row => {
        xml += '  <Row>\n';
        columns.forEach(c => {
            const val = c.format ? c.format(row) : row[c.key];
            const tag = c.key.replace(/[^a-zA-Z0-9_]/g, '_');
            xml += `    <${tag}>${_escXml(val)}</${tag}>\n`;
        });
        xml += '  </Row>\n';
    });

    xml += '</Export>';

    _triggerDownload(xml, _makeExportFilename(pageName, 'xml'), 'application/xml');
    showToast(`XML: ${data.length} записей`, 'success');
}

/* ── Dropdown UI ───────────────────────────────────────────────────────── */

function _injectExportStyles() {
    if (document.getElementById('export-dropdown-styles')) return;
    const style = document.createElement('style');
    style.id = 'export-dropdown-styles';
    style.textContent = `
        .export-dropdown { position:relative; display:inline-block; }
        .export-menu {
            display:none; position:absolute; top:calc(100% + 4px); right:0;
            z-index:9999; min-width:240px; background:var(--surface);
            border:1px solid var(--border); border-radius:8px;
            box-shadow:0 4px 20px rgba(0,0,0,0.18); padding:4px 0;
        }
        .export-menu.open { display:block; }
        .export-menu-item {
            display:flex; align-items:center; gap:8px; padding:9px 14px;
            cursor:pointer; font-size:13px; color:var(--text);
            transition:background 0.12s; white-space:nowrap;
        }
        .export-menu-item:hover { background:var(--hover, rgba(255,255,255,0.06)); }
        .export-menu-sep { height:1px; background:var(--border); margin:4px 0; }
    `;
    document.head.appendChild(style);
}

/**
 * Создаёт кнопку «Экспорт» с выпадающим меню (4 пункта).
 * @param {string} containerId — id элемента-контейнера
 * @param {Object} config — { pageName, columns, getAllData, getFilteredData }
 */
function buildExportDropdown(containerId, config) {
    _injectExportStyles();
    const container = document.getElementById(containerId);
    if (!container) return;

    const wrap = document.createElement('div');
    wrap.className = 'export-dropdown';

    const btn = document.createElement('button');
    btn.className = 'btn btn-outline btn-sm';
    btn.innerHTML = '<i class="fas fa-download"></i> Экспорт';
    btn.onclick = (e) => {
        e.stopPropagation();
        menu.classList.toggle('open');
    };

    const menu = document.createElement('div');
    menu.className = 'export-menu';

    const items = [
        { icon: 'fa-file-excel', color: '#217346', label: 'Excel (фильтрованные)',
          fn: () => exportToExcel(config.getFilteredData(), config.columns, config.pageName) },
        { icon: 'fa-file-excel', color: '#217346', label: 'Excel (все данные)',
          fn: () => exportToExcel(config.getAllData(), config.columns, config.pageName) },
        '_sep_',
        { icon: 'fa-file-code', color: '#e37400', label: 'XML (фильтрованные)',
          fn: () => exportToXml(config.getFilteredData(), config.columns, config.pageName) },
        { icon: 'fa-file-code', color: '#e37400', label: 'XML (все данные)',
          fn: () => exportToXml(config.getAllData(), config.columns, config.pageName) },
    ];

    items.forEach(it => {
        if (it === '_sep_') {
            const sep = document.createElement('div');
            sep.className = 'export-menu-sep';
            menu.appendChild(sep);
            return;
        }
        const item = document.createElement('div');
        item.className = 'export-menu-item';
        item.innerHTML = `<i class="fas ${it.icon}" style="color:${it.color};width:16px;text-align:center;"></i> ${it.label}`;
        item.onclick = (e) => {
            e.stopPropagation();
            menu.classList.remove('open');
            it.fn();
        };
        menu.appendChild(item);
    });

    wrap.appendChild(btn);
    wrap.appendChild(menu);
    container.appendChild(wrap);

    // Закрытие по клику вне (используем capture для одного обработчика)
    document.addEventListener('click', (e) => {
        if (!wrap.contains(e.target)) menu.classList.remove('open');
    }, { once: false });
}
