/**
 * feedback.js — Замечания и предложения.
 */
(function() {
'use strict';

var cfg = JSON.parse(document.getElementById('fb-config').textContent);
var isAdmin = cfg.isAdmin;
var csrfToken = cfg.csrfToken;

var CATEGORIES = {
  functionality: 'Функционал',
  logic: 'Логика / Алгоритмы',
  design: 'Оформление',
  bug: 'Ошибка',
  other: 'Другое'
};

var STATUSES = {
  'new': 'Новое',
  accepted: 'Принято',
  implemented: 'Выполнено',
  rejected: 'Отклонено'
};

// esc() — в utils.js
// feedback.js fmtDate = fmtDateTime (дата + время)
var fmtDate = fmtDateTime;

var filterStatus = '';
var filterCategory = '';

/* ── Чипы-фильтры ─────────────────────────────────────────────────── */
function renderFilterChips() {
  var html = '<div class="fb-filter-group">';
  html += '<span class="fb-filter-label">Статус:</span>';
  html += '<button class="fb-chip' + (!filterStatus ? ' active' : '') + '" onclick="fbSetStatus(\'\')">Все</button>';
  Object.keys(STATUSES).forEach(function(k) {
    html += '<button class="fb-chip fb-chip-' + k + (filterStatus === k ? ' active' : '') + '" onclick="fbSetStatus(\'' + k + '\')">' + STATUSES[k] + '</button>';
  });
  html += '</div>';
  html += '<div class="fb-filter-sep"></div>';
  html += '<div class="fb-filter-group">';
  html += '<span class="fb-filter-label">Тип:</span>';
  html += '<button class="fb-chip' + (!filterCategory ? ' active' : '') + '" onclick="fbSetCategory(\'\')">Все</button>';
  Object.keys(CATEGORIES).forEach(function(k) {
    html += '<button class="fb-chip fb-chip-' + k + (filterCategory === k ? ' active' : '') + '" onclick="fbSetCategory(\'' + k + '\')">' + CATEGORIES[k] + '</button>';
  });
  html += '</div>';
  document.getElementById('fbFilters').innerHTML = html;
}

window.fbSetStatus = function(s) { filterStatus = s; renderFilterChips(); fbLoad(); };
window.fbSetCategory = function(c) { filterCategory = c; renderFilterChips(); fbLoad(); };

/* ── Загрузка ──────────────────────────────────────────────────────── */
function fbLoad() {
  var params = [];
  if (filterStatus) params.push('status=' + filterStatus);
  if (filterCategory) params.push('category=' + filterCategory);
  var url = '/api/feedback/' + (params.length ? '?' + params.join('&') : '');
  fetch(url).then(function(r) { return r.json(); }).then(function(items) {
    renderList(items);
  });
}
window.fbLoad = fbLoad;

function renderList(items) {
  var el = document.getElementById('fbList');
  if (!items.length) {
    el.innerHTML = '<div class="fb-empty"><i class="fas fa-clipboard-check"></i><br>Нет замечаний</div>';
    return;
  }
  var html = '';
  items.forEach(function(fb) {
    html += '<div class="fb-card">';
    html += '<div class="fb-card-header">';
    html += '<span class="fb-cat fb-cat-' + fb.category + '">' + esc(fb.category_display) + '</span>';
    html += '<span class="fb-meta">' + esc(fb.user_name) + ' · ' + fmtDate(fb.created_at) + '</span>';
    html += '<span class="fb-status fb-status-' + fb.status + '">' + esc(fb.status_display) + '</span>';
    html += '</div>';
    html += '<div class="fb-text">' + esc(fb.text) + '</div>';
    var allScreens = (fb.screenshots || []).map(function(s) { return s.url || s; });
    if (fb.screenshot) allScreens.unshift(fb.screenshot);
    if (allScreens.length > 0) {
      html += '<div class="fb-screenshot">';
      allScreens.forEach(function(url) {
        html += '<img src="' + esc(url) + '" onclick="window.open(this.src)" title="Увеличить"> ';
      });
      html += '</div>';
    }
    if (fb.admin_comment) {
      html += '<div class="fb-admin-comment"><strong>Ответ:</strong> ' + esc(fb.admin_comment) + '</div>';
    }
    var hasActions = isAdmin || fb.is_own;
    if (hasActions) {
      html += '<div class="fb-actions">';
      if (fb.is_own) {
        html += '<button class="btn btn-outline btn-xs" onclick=\'fbOpenEdit(' + JSON.stringify({id:fb.id, category:fb.category, text:fb.text, screenshots:fb.screenshots||[]}).replace(/'/g, "&#39;") + ')\'><i class="fas fa-pen"></i> Редактировать</button>';
      }
      if (isAdmin) {
        html += '<button class="btn btn-outline btn-xs" onclick="fbOpenStatus(' + fb.id + ',\'' + fb.status + '\',\'' + esc(fb.admin_comment).replace(/'/g, "\\'") + '\')"><i class="fas fa-edit"></i> Статус</button>';
        html += '<button class="btn btn-danger btn-xs" onclick="fbDelete(' + fb.id + ')"><i class="fas fa-trash"></i></button>';
      }
      html += '</div>';
    }
    html += '</div>';
  });
  el.innerHTML = html;
}

/* ── Создание ──────────────────────────────────────────────────────── */
window.fbOpenCreate = function() {
  var body = document.createElement('div');
  body.className = 'fb-form';
  body.innerHTML =
    '<label>Категория</label>' +
    '<select id="fbNewCat">' +
    '<option value="functionality">Функционал</option>' +
    '<option value="logic">Логика / Алгоритмы</option>' +
    '<option value="design">Оформление</option>' +
    '<option value="bug">Ошибка</option>' +
    '<option value="other">Другое</option>' +
    '</select>' +
    '<label>Описание</label>' +
    '<textarea id="fbNewText" placeholder="Опишите замечание или предложение..."></textarea>' +
    '<div class="fb-dropzone" id="fbNewDropzone">' +
    '<input type="file" id="fbNewFile" accept="image/*">' +
    '<i class="fas fa-image"></i>' +
    'Перетащите скриншот или кликните для выбора файла<br>' +
    '<button type="button" class="fb-paste-btn"><i class="fas fa-paste"></i> Вставить из буфера</button>' +
    '<div class="fb-dropzone-preview" id="fbNewPreview"></div>' +
    '</div>';

  openModal({
    title: 'Новое замечание',
    bodyElement: body,
    width: '500px',
    footer:
      '<button class="btn btn-outline" onclick="closeAllModals()">Отмена</button>' +
      '<button class="btn btn-primary" onclick="fbSubmitCreate()">Отправить</button>'
  });
  setupDropzone('fbNewDropzone', 'fbNewFile', 'fbNewPreview');
};

window.fbSubmitCreate = function() {
  var cat = document.getElementById('fbNewCat').value;
  var text = document.getElementById('fbNewText').value.trim();
  if (!text) { alert('Введите текст'); return; }

  var fd = new FormData();
  fd.append('category', cat);
  fd.append('text', text);
  var zone = document.getElementById('fbNewDropzone');
  var files = zone && zone._files ? zone._files : [];
  files.forEach(function(f) {
    fd.append('screenshots', f.file);
  });

  fetch('/api/feedback/', {
    method: 'POST',
    headers: {'X-CSRFToken': csrfToken},
    body: fd
  }).then(function(r) {
    if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || 'Ошибка'); });
    return r.json();
  }).then(function() {
    closeAllModals();
    fbLoad();
  }).catch(function(e) { alert(e.message); });
};

/* ── Редактирование (автор) ────────────────────────────────────────── */
window.fbOpenEdit = function(data) {
  var id = data.id, currentCat = data.category, currentText = data.text;
  var existingScreens = data.screenshots || [];

  var body = document.createElement('div');
  body.className = 'fb-form';
  var opts = '';
  Object.keys(CATEGORIES).forEach(function(k) {
    opts += '<option value="' + k + '"' + (k === currentCat ? ' selected' : '') + '>' + CATEGORIES[k] + '</option>';
  });

  var existingHtml = '';
  if (existingScreens.length > 0) {
    existingHtml = '<label>Текущие скриншоты</label><div class="fb-existing-screens" id="fbExistingScreens">';
    existingScreens.forEach(function(s) {
      existingHtml += '<span class="fb-preview-item" data-att-id="' + s.id + '">';
      existingHtml += '<img src="' + esc(s.url) + '">';
      existingHtml += '<span class="fb-dropzone-remove" onclick="event.stopPropagation(); fbDeleteAttachment(' + s.id + ',this)"><i class="fas fa-times"></i></span>';
      existingHtml += '</span>';
    });
    existingHtml += '</div>';
  }

  body.innerHTML =
    '<label>Категория</label><select id="fbEditCat">' + opts + '</select>' +
    '<label>Текст</label><textarea id="fbEditText">' + esc(currentText) + '</textarea>' +
    existingHtml +
    '<div class="fb-dropzone" id="fbEditDropzone">' +
    '<input type="file" id="fbEditFile" accept="image/*">' +
    '<i class="fas fa-image"></i>' +
    'Добавить скриншоты<br>' +
    '<button type="button" class="fb-paste-btn"><i class="fas fa-paste"></i> Вставить из буфера</button>' +
    '<div class="fb-dropzone-preview" id="fbEditPreview"></div>' +
    '</div>';

  openModal({
    title: 'Редактировать замечание',
    bodyElement: body,
    width: '500px',
    footer:
      '<button class="btn btn-outline" onclick="closeAllModals()">Отмена</button>' +
      '<button class="btn btn-primary" onclick="fbSubmitEdit(' + id + ')">Сохранить</button>'
  });
  setupDropzone('fbEditDropzone', 'fbEditFile', 'fbEditPreview');
};

window.fbDeleteAttachment = function(attId, el) {
  if (!confirm('Удалить скриншот?')) return;
  fetch('/api/feedback/attachment/' + attId + '/', {
    method: 'DELETE',
    headers: {'X-CSRFToken': csrfToken}
  }).then(function(r) {
    if (!r.ok) throw new Error('Ошибка');
    // Убираем из DOM
    var item = el.closest('.fb-preview-item');
    if (item) item.remove();
  }).catch(function(e) { alert(e.message); });
};

window.fbSubmitEdit = function(id) {
  var cat = document.getElementById('fbEditCat').value;
  var text = document.getElementById('fbEditText').value.trim();
  if (!text) { alert('Текст обязателен'); return; }

  var zone = document.getElementById('fbEditDropzone');
  var dzFiles = zone && zone._files ? zone._files : [];
  var hasFile = dzFiles.length > 0;

  if (hasFile) {
    var fd = new FormData();
    fd.append('category', cat);
    fd.append('text', text);
    dzFiles.forEach(function(f) { fd.append('screenshots', f.file); });
    fd.append('_method', 'PUT');
    fetch('/api/feedback/' + id + '/', {
      method: 'POST',
      headers: {'X-CSRFToken': csrfToken},
      body: fd
    }).then(function(r) {
      if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || 'Ошибка'); });
      return r.json();
    }).then(function() {
      closeAllModals();
      fbLoad();
    }).catch(function(e) { alert(e.message); });
  } else {
    fetch('/api/feedback/' + id + '/', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
      body: JSON.stringify({category: cat, text: text})
    }).then(function(r) {
      if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || 'Ошибка'); });
      return r.json();
    }).then(function() {
      closeAllModals();
      fbLoad();
    }).catch(function(e) { alert(e.message); });
  }
};

/* ── Статус (admin) ───────────────────────────────────────────────── */
window.fbOpenStatus = function(id, currentStatus, currentComment) {
  var body = document.createElement('div');
  body.className = 'fb-form';
  var opts = '';
  Object.keys(STATUSES).forEach(function(k) {
    opts += '<option value="' + k + '"' + (k === currentStatus ? ' selected' : '') + '>' + STATUSES[k] + '</option>';
  });
  body.innerHTML =
    '<label>Статус</label><select id="fbEditStatus">' + opts + '</select>' +
    '<label>Комментарий администратора</label>' +
    '<textarea id="fbEditComment">' + esc(currentComment) + '</textarea>';

  openModal({
    title: 'Изменить статус',
    bodyElement: body,
    width: '450px',
    footer:
      '<button class="btn btn-outline" onclick="closeAllModals()">Отмена</button>' +
      '<button class="btn btn-primary" onclick="fbSubmitStatus(' + id + ')">Сохранить</button>'
  });
};

window.fbSubmitStatus = function(id) {
  var status = document.getElementById('fbEditStatus').value;
  var comment = document.getElementById('fbEditComment').value;

  fetch('/api/feedback/' + id + '/', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
    body: JSON.stringify({status: status, admin_comment: comment})
  }).then(function(r) {
    if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || 'Ошибка'); });
    return r.json();
  }).then(function() {
    closeAllModals();
    fbLoad();
  }).catch(function(e) { alert(e.message); });
};

/* ── Удаление (admin) ─────────────────────────────────────────────── */
window.fbDelete = function(id) {
  if (!confirm('Удалить замечание?')) return;
  fetch('/api/feedback/' + id + '/', {
    method: 'DELETE',
    headers: {'X-CSRFToken': csrfToken}
  }).then(function(r) {
    if (!r.ok) throw new Error('Ошибка');
    fbLoad();
  });
};

/* ── Dropzone: drag & drop / paste / click (множественные файлы) ──── */
function setupDropzone(dropzoneId, fileInputId, previewId) {
  var zone = document.getElementById(dropzoneId);
  var fileInput = document.getElementById(fileInputId);
  var preview = document.getElementById(previewId);
  if (!zone || !fileInput) return;

  // Хранилище файлов
  var files = [];
  zone._files = files;

  function renderPreviews() {
    if (!preview) return;
    if (files.length === 0) {
      preview.innerHTML = '';
      fileInput.style.display = '';
      return;
    }
    var html = '';
    files.forEach(function(f, idx) {
      html += '<span class="fb-preview-item" data-idx="' + idx + '">';
      html += '<img src="' + f.dataUrl + '">';
      html += '<span class="fb-dropzone-remove" onclick="event.stopPropagation(); event.preventDefault(); fbRemoveFile(\'' + dropzoneId + '\',' + idx + ')"><i class="fas fa-times"></i></span>';
      html += '</span>';
    });
    preview.innerHTML = html;
    fileInput.style.display = 'none';
  }

  function addFile(file) {
    var reader = new FileReader();
    reader.onload = function(ev) {
      files.push({file: file, dataUrl: ev.target.result});
      renderPreviews();
    };
    reader.readAsDataURL(file);
  }

  // File input change
  fileInput.setAttribute('multiple', '');
  fileInput.addEventListener('change', function() {
    for (var i = 0; i < fileInput.files.length; i++) {
      addFile(fileInput.files[i]);
    }
  });

  // Drag events
  zone.addEventListener('dragover', function(e) { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', function() { zone.classList.remove('dragover'); });
  zone.addEventListener('drop', function(e) {
    e.preventDefault();
    zone.classList.remove('dragover');
    for (var i = 0; i < e.dataTransfer.files.length; i++) {
      addFile(e.dataTransfer.files[i]);
    }
  });

  // Paste — слушаем на document (пока модалка открыта)
  function pasteHandler(e) {
    // Только если модалка ещё видна
    if (!document.contains(zone)) {
      document.removeEventListener('paste', pasteHandler);
      return;
    }
    var items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (var i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        addFile(items[i].getAsFile());
        e.preventDefault();
        break;
      }
    }
  }
  document.addEventListener('paste', pasteHandler);

  // Кнопка «Вставить из буфера»
  var pasteBtn = zone.querySelector('.fb-paste-btn');
  if (pasteBtn) {
    pasteBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      if (!navigator.clipboard || !navigator.clipboard.read) {
        alert('Браузер не поддерживает чтение буфера. Используйте Ctrl+V.');
        return;
      }
      navigator.clipboard.read().then(function(clipItems) {
        for (var i = 0; i < clipItems.length; i++) {
          var types = clipItems[i].types;
          for (var j = 0; j < types.length; j++) {
            if (types[j].indexOf('image') !== -1) {
              clipItems[i].getType(types[j]).then(function(blob) {
                var file = new File([blob], 'screenshot.png', {type: blob.type});
                addFile(file);
              });
              return;
            }
          }
        }
        alert('В буфере нет изображения');
      }).catch(function() {
        alert('Не удалось прочитать буфер. Используйте Ctrl+V.');
      });
    });
  }
}

window.fbRemoveFile = function(dropzoneId, idx) {
  var zone = document.getElementById(dropzoneId);
  if (!zone || !zone._files) return;
  zone._files.splice(idx, 1);
  // Перерендерим
  var fileInput = zone.querySelector('input[type=file]');
  var preview = zone.querySelector('.fb-dropzone-preview');
  if (zone._files.length === 0) {
    if (preview) preview.innerHTML = '';
    if (fileInput) { fileInput.value = ''; fileInput.style.display = ''; }
    return;
  }
  var html = '';
  zone._files.forEach(function(f, i) {
    html += '<span class="fb-preview-item" data-idx="' + i + '">';
    html += '<img src="' + f.dataUrl + '">';
    html += '<span class="fb-dropzone-remove" onclick="event.stopPropagation(); event.preventDefault(); fbRemoveFile(\'' + dropzoneId + '\',' + i + ')"><i class="fas fa-times"></i></span>';
    html += '</span>';
  });
  if (preview) preview.innerHTML = html;
};

/* ── Init ──────────────────────────────────────────────────────────── */
renderFilterChips();
fbLoad();

})();
