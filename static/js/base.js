/* ══════════════════════════════════════════════════════════════════════
   base.js — Общая логика для всех страниц (сайдбар, тосты, уведомления,
   онбординг, тема, сессия)
   Вынесено из inline-скрипта в base.html
   ══════════════════════════════════════════════════════════════════════ */

// ── A11y: aria-current на хлебных крошках ────────────────────────────────
document.querySelectorAll('.breadcrumb-current').forEach(function(el) {
  el.setAttribute('aria-current', 'page');
});

// ── Сайдбар ─────────────────────────────────────────────────────────────
var sidebar = document.getElementById('sidebar');
var mainContent = document.getElementById('mainContent');
var sidebarOverlay = document.getElementById('sidebarOverlay');
var sidebarToggle = document.getElementById('sidebarToggle');
var mobileToggle = document.getElementById('mobileToggle');

if (sidebarToggle) {
  sidebarToggle.addEventListener('click', function() {
    sidebar.classList.toggle('collapsed');
    mainContent.classList.toggle('sidebar-collapsed');
    localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
  });
  if (localStorage.getItem('sidebarCollapsed') === 'true') {
    sidebar.classList.add('collapsed');
    mainContent.classList.add('sidebar-collapsed');
  }
}

if (mobileToggle) {
  mobileToggle.addEventListener('click', function() {
    sidebar.classList.toggle('open');
    sidebarOverlay.classList.toggle('open');
  });
  sidebarOverlay.addEventListener('click', function() {
    sidebar.classList.remove('open');
    sidebarOverlay.classList.remove('open');
  });
}

// ── Резервный showToast (до загрузки utils.js) ──────────────────────────
if (typeof showToast !== 'function') {
  window.showToast = function(message, type) {
    type = type || 'success';
    var container = document.getElementById('toastContainer');
    if (!container) return;
    var toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    toast.setAttribute('aria-atomic', 'true');
    var icons = {success: '✓', error: '✕', warning: '!'};
    toast.innerHTML = '<div class="toast-icon">' + (icons[type] || '!') + '</div><div class="toast-message"></div>';
    toast.querySelector('.toast-message').textContent = message;
    container.appendChild(toast);
    setTimeout(function() {
      toast.style.animation = 'slideIn 0.3s ease reverse';
      setTimeout(function() { toast.remove(); }, 300);
    }, 4000);
  };
}

// ── Навигация: дропдауны ────────────────────────────────────────────────
function toggleNavDropdown(btn) {
  btn.classList.toggle('open');
  btn.setAttribute('aria-expanded', btn.classList.contains('open'));
  var menu = btn.nextElementSibling;
  if (menu) menu.classList.toggle('open');
  _saveNavDropdownState();
}

function _saveNavDropdownState() {
  var open = [];
  document.querySelectorAll('.nav-dropdown-toggle.open').forEach(function(btn) {
    var span = btn.querySelector('span');
    if (span) open.push(span.textContent.trim());
  });
  localStorage.setItem('navDropdownOpen', JSON.stringify(open));
}

// ── DOMContentLoaded ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  // Django-messages → Toast
  document.querySelectorAll('.django-message').forEach(function(el) {
    var t = el.dataset.type;
    var type = t && t.indexOf('error') >= 0 ? 'error'
             : t && t.indexOf('warning') >= 0 ? 'warning' : 'success';
    showToast(el.textContent.trim(), type);
  });
  // Восстанавливаем открытые дропдауны
  var saved = [];
  try { saved = JSON.parse(localStorage.getItem('navDropdownOpen') || '[]'); } catch(e) {}
  document.querySelectorAll('.nav-dropdown-toggle').forEach(function(btn) {
    var span = btn.querySelector('span');
    if (span && saved.indexOf(span.textContent.trim()) >= 0) {
      btn.classList.add('open');
      btn.setAttribute('aria-expanded', 'true');
      var menu = btn.nextElementSibling;
      if (menu) menu.classList.add('open');
    }
  });
  // Авто-раскрытие дропдауна если активный подраздел
  document.querySelectorAll('.nav-dropdown-menu .nav-item.active').forEach(function(el) {
    var menu = el.closest('.nav-dropdown-menu');
    var toggle = menu && menu.previousElementSibling;
    if (menu) { menu.classList.add('open'); toggle.classList.add('open'); toggle.setAttribute('aria-expanded', 'true'); }
  });
});

// ── Onboarding Tips ─────────────────────────────────────────────────────
(function() {
  var TIPS = [
    {
      target: '.sidebar-nav',
      title: 'Навигация',
      text: 'Здесь находятся все разделы системы: планы, проекты, аналитика и справочники.',
      pos: 'right'
    },
    {
      target: '#themeToggle',
      title: 'Тема оформления',
      text: 'Нажмите, чтобы переключить между светлой и тёмной темой.',
      pos: 'bottom'
    },
  ];
  var seen = {};
  try { seen = JSON.parse(localStorage.getItem('onboardingSeen') || '{}'); } catch(e) {}

  function showNextTip() {
    for (var idx = 0; idx < TIPS.length; idx++) {
      if (seen[idx]) continue;
      var el = document.querySelector(TIPS[idx].target);
      if (!el) continue;
      var tip = document.createElement('div');
      tip.className = 'onboarding-tip';
      tip.setAttribute('data-pos', TIPS[idx].pos);
      tip.innerHTML =
        '<button class="onboarding-tip-close" aria-label="Закрыть">&times;</button>' +
        '<div class="onboarding-tip-title">' + TIPS[idx].title + '</div>' +
        '<div>' + TIPS[idx].text + '</div>' +
        '<div class="onboarding-tip-footer">' +
          '<span class="onboarding-tip-step">' + (idx + 1) + ' из ' + TIPS.length + '</span>' +
          '<button class="onboarding-tip-btn">Понятно</button>' +
        '</div>';
      var rect = el.getBoundingClientRect();
      if (TIPS[idx].pos === 'right') {
        tip.style.top = (rect.top + rect.height / 2 - 30) + 'px';
        tip.style.left = (rect.right + 14) + 'px';
      } else {
        tip.style.top = (rect.bottom + 14) + 'px';
        tip.style.left = (rect.left + rect.width / 2 - 120) + 'px';
      }
      (function(tipIdx, tipEl) {
        var dismiss = function() {
          seen[tipIdx] = true;
          localStorage.setItem('onboardingSeen', JSON.stringify(seen));
          tipEl.remove();
          setTimeout(showNextTip, 400);
        };
        tipEl.querySelector('.onboarding-tip-btn').addEventListener('click', dismiss);
        tipEl.querySelector('.onboarding-tip-close').addEventListener('click', dismiss);
      })(idx, tip);
      document.body.appendChild(tip);
      break;
    }
  }
  setTimeout(showNextTip, 1200);
})();

// ── Modal overlay click ─────────────────────────────────────────────────
document.addEventListener('click', function(e) {
  if (!e.target.classList.contains('modal-overlay')) return;
  if (!e.target.classList.contains('open')) return;
  e.target.classList.remove('open');
});

// ── User menu dropdown ──────────────────────────────────────────────────
function toggleBaseUserMenu() {
  var dd = document.getElementById('baseUserDropdown');
  var btn = document.getElementById('baseTopbarUser');
  dd.classList.toggle('open');
  btn.classList.toggle('menu-open');
}
document.addEventListener('click', function(e) {
  var wrap = document.getElementById('baseUserMenuWrap');
  if (wrap && !wrap.contains(e.target)) {
    var dd = document.getElementById('baseUserDropdown');
    var btn = document.getElementById('baseTopbarUser');
    if (dd) dd.classList.remove('open');
    if (btn) btn.classList.remove('menu-open');
  }
});

// ── Notification center ─────────────────────────────────────────────────
function toggleNotifPanel() {
  var panel = document.getElementById('notifPanel');
  if (!panel) return;
  var isOpen = panel.classList.toggle('open');
  if (isOpen) {
    loadNotifications();
    updateNotifBadge();
    // #15: авто-обновление при открытой панели
    if (!window._notifPollId) {
      window._notifPollId = setInterval(function() {
        var p = document.getElementById('notifPanel');
        if (p && p.classList.contains('open')) loadNotifications();
        else { clearInterval(window._notifPollId); window._notifPollId = null; }
      }, 60000);
    }
  }
}

function loadNotifications() {
  // Синхронизируем уведомления о сроках (POST), затем загружаем список (GET)
  fetch('/api/notifications/sync/', {method: 'POST', headers: {'X-CSRFToken': getCsrfToken()}, credentials: 'same-origin'})
    .catch(function() {})
    .then(function() { return fetch('/api/notifications/', {credentials: 'same-origin'}); })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var list = document.getElementById('notifList');
      if (!list) return;
      if (!data.items || !data.items.length) {
        list.innerHTML = '<div class="notif-empty"><i class="fas fa-bell-slash" aria-hidden="true"></i><br>Нет новых уведомлений</div>';
        return;
      }
      list.innerHTML = data.items.map(function(n) {
        return '<div class="notif-item' + (n.is_read ? '' : ' unread') + '" data-id="' + n.id + '" onclick="readNotif(' + n.id + ', \'' + (n.link || '') + '\')">' +
          '<div class="notif-item-icon"><i class="fas fa-' + notifIcon(n.type) + '" aria-hidden="true"></i></div>' +
          '<div class="notif-item-body">' +
          '<div class="notif-item-title">' + n.title + '</div>' +
          '<div class="notif-item-msg">' + n.message + '</div>' +
          '<div class="notif-item-time">' + timeAgo(n.created_at) + '</div>' +
          '</div></div>';
      }).join('');
    });
}

function notifIcon(type) {
  return {info: 'info-circle', warning: 'exclamation-triangle', success: 'check-circle', task: 'tasks', overdue: 'clock', sandbox: 'flask'}[type] || 'bell';
}

function timeAgo(isoStr) {
  var d = new Date(isoStr);
  var diff = Math.floor((Date.now() - d) / 1000);
  if (diff < 60) return 'только что';
  if (diff < 3600) return Math.floor(diff / 60) + ' мин. назад';
  if (diff < 86400) return Math.floor(diff / 3600) + ' ч. назад';
  return d.toLocaleDateString('ru-RU');
}

function readNotif(id, link) {
  fetch('/api/notifications/' + id + '/read/', {method: 'POST', headers: {'X-CSRFToken': getCsrfToken()}, credentials: 'same-origin'})
    .then(function() { updateNotifBadge(); });
  var el = document.querySelector('.notif-item[data-id="' + id + '"]');
  if (el) el.classList.remove('unread');
  if (link) window.location.href = link;
}

function markAllNotifRead() {
  fetch('/api/notifications/read_all/', {method: 'POST', headers: {'X-CSRFToken': getCsrfToken()}, credentials: 'same-origin'})
    .then(function() {
      document.querySelectorAll('.notif-item.unread').forEach(function(el) { el.classList.remove('unread'); });
      updateNotifBadge();
      loadNotifications();
    });
}

function updateNotifBadge() {
  fetch('/api/notifications/unread_count/', {credentials: 'same-origin'})
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var badge = document.getElementById('notifBadge');
      if (!badge) return;
      if (data.count > 0) {
        badge.textContent = data.count > 99 ? '99+' : data.count;
        badge.style.display = '';
      } else {
        badge.style.display = 'none';
      }
    });
}

// Initial load + polling every 5 min (с паузой при скрытой вкладке)
updateNotifBadge();
var _notifBadgePollId = setInterval(updateNotifBadge, 300000);

document.addEventListener('visibilitychange', function() {
  if (document.hidden) {
    // Вкладка скрыта — останавливаем polling
    if (_notifBadgePollId) { clearInterval(_notifBadgePollId); _notifBadgePollId = null; }
    if (window._notifPollId) { clearInterval(window._notifPollId); window._notifPollId = null; }
  } else {
    // Вкладка снова видима — возобновляем polling бейджа
    updateNotifBadge();
    if (!_notifBadgePollId) { _notifBadgePollId = setInterval(updateNotifBadge, 300000); }
    // Панельный polling возобновится при следующем toggleNotifPanel()
  }
});

// Close notification panel on outside click
document.addEventListener('click', function(e) {
  var wrap = document.getElementById('notifWrap');
  if (wrap && !wrap.contains(e.target)) {
    var panel = document.getElementById('notifPanel');
    if (panel) panel.classList.remove('open');
  }
});

// ── Тема ────────────────────────────────────────────────────────────────
(function() {
  var mql = window.matchMedia('(prefers-color-scheme: dark)');

  function resolveSystemTheme() {
    return mql.matches ? 'dark' : 'light';
  }

  function applyTheme(stored) {
    var effective = stored === 'system' ? resolveSystemTheme() : stored;
    document.documentElement.setAttribute('data-theme', effective);
    var btns = document.querySelectorAll('#themeToggle button');
    btns.forEach(function(b) { b.classList.toggle('active', b.dataset.theme === stored); });
    var sysBtn = document.querySelector('#themeToggle button[data-theme="system"]');
    if (sysBtn) {
      var label = stored === 'system'
        ? (effective === 'dark' ? 'Авто (тёмная)' : 'Авто (светлая)')
        : 'Авто';
      sysBtn.title = label;
    }
  }

  var saved = localStorage.getItem('theme') || 'light';
  applyTheme(saved);

  mql.addEventListener('change', function() {
    if (localStorage.getItem('theme') === 'system') {
      applyTheme('system');
    }
  });

  var toggle = document.getElementById('themeToggle');
  if (toggle) toggle.addEventListener('click', function(e) {
    var btn = e.target.closest('button');
    if (!btn) return;
    var t = btn.dataset.theme;
    localStorage.setItem('theme', t);
    applyTheme(t);
    // #16: toast при смене темы
    var names = {light: 'Светлая', dark: 'Тёмная', twilight: 'Сумерки', system: 'Авто'};
    if (typeof showToast === 'function') showToast('Тема: ' + (names[t] || t), 'info');
  });
})();

// ── Предупреждение о таймауте сессии ────────────────────────────────────
(function() {
  var SESSION_LIFETIME = 8 * 3600 * 1000;
  var WARN_BEFORE = 10 * 60 * 1000;
  var warned = false;
  var overlay = null;
  function showWarn() {
    if (warned) return;
    warned = true;
    overlay = document.createElement('div');
    overlay.className = 'session-warn-overlay';
    overlay.innerHTML = '<div class="session-warn-card">' +
      '<h3><i class="fas fa-clock" style="color:var(--warning);margin-right:8px;" aria-hidden="true"></i>Сессия истекает</h3>' +
      '<p>Ваша сессия скоро завершится. Сохраните изменения и обновите страницу.</p>' +
      '<button class="btn btn-primary" id="sessionRefreshBtn">Продлить сессию</button>' +
      '<button class="btn btn-outline" id="sessionDismissBtn">Закрыть</button></div>';
    document.body.appendChild(overlay);
    document.getElementById('sessionRefreshBtn').onclick = function() {
      fetch('/api/health/', {credentials: 'same-origin'}).then(function() {
        if (overlay) { overlay.remove(); overlay = null; }
        warned = false;
        startTimer();
      });
    };
    document.getElementById('sessionDismissBtn').onclick = function() {
      if (overlay) { overlay.remove(); overlay = null; }
    };
  }
  function startTimer() {
    setTimeout(showWarn, SESSION_LIFETIME - WARN_BEFORE);
  }
  startTimer();
})();
