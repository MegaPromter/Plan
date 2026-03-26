/**
 * Command palette (Ctrl+K / Cmd+K) — глобальный поиск и навигация.
 * Группы: Страницы, Действия. Fuzzy-matching, клавиатурная навигация.
 */
(function() {
    /* ── Навигационные команды (Страницы) ──────────────────────────────── */
    var PAGES = [
        {title:'Стартовая страница',       icon:'fas fa-th-large',        url:'/accounts/dashboard/',        keywords:'главная дашборд home'},
        {title:'Управление проектами',     icon:'fas fa-project-diagram',  url:'/works/projects/',            keywords:'проекты projects'},
        {title:'Производственный план',    icon:'fas fa-industry',         url:'/works/production-plan/',     keywords:'производство production'},
        {title:'Сводное планирование',     icon:'fas fa-tasks',            url:'/works/plan/',                keywords:'план отчёт plan report'},
        {title:'Журнал извещений',         icon:'fas fa-envelope',         url:'/works/notices/',             keywords:'извещения notices'},
        {title:'Аналитика',                icon:'fas fa-chart-bar',        url:'/works/analytics/',           keywords:'аналитика analytics графики'},
        {title:'Производственный календарь', icon:'fas fa-calendar-check', url:'/works/work-calendar/',       keywords:'календарь calendar'},
        {title:'Список сотрудников',       icon:'fas fa-users',            url:'/employees/',                 keywords:'сотрудники employees люди'},
        {title:'План отпусков',            icon:'fas fa-calendar-alt',     url:'/employees/vacation-plan/',   keywords:'отпуск vacation'},
        {title:'План командировок',        icon:'fas fa-plane',            url:'/works/business-trips/',      keywords:'командировки trips'},
        {title:'Замечания и предложения',  icon:'fas fa-lightbulb',        url:'/works/feedback/',            keywords:'обратная связь feedback'},
        {title:'Журнал аудита',            icon:'fas fa-shield-alt',       url:'/works/audit-log/',           keywords:'аудит audit лог'},
        {title:'Профиль',                  icon:'fas fa-cog',              url:'/accounts/profile/',          keywords:'настройки profile settings'},
    ];

    /* ── Действия ──────────────────────────────────────────────────────── */
    function getActions() {
        var actions = [
            {
                title: 'Сменить тему',
                icon: 'fas fa-adjust',
                keywords: 'тема theme dark light переключить',
                action: function() {
                    var themes = ['light', 'dark', 'system'];
                    var current = localStorage.getItem('theme') || 'light';
                    var next = themes[(themes.indexOf(current) + 1) % themes.length];
                    localStorage.setItem('theme', next);
                    var effective = next;
                    if (next === 'system') {
                        try { effective = window.matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light'; } catch(e) { effective = 'light'; }
                    }
                    document.documentElement.setAttribute('data-theme', effective);
                    var btns = document.querySelectorAll('#themeToggle button');
                    btns.forEach(function(b) { b.classList.toggle('active', b.dataset.theme === next); });
                    if (typeof showToast === 'function') showToast('Тема: ' + next, 'success');
                }
            },
        ];

        // Контекстные действия
        var path = window.location.pathname;
        if (path.indexOf('/works/plan') >= 0) {
            actions.push({
                title: 'Новая задача',
                icon: 'fas fa-plus',
                keywords: 'создать добавить задача new task',
                action: function() {
                    var btn = document.querySelector('[data-action="add-task"], .btn-add-task, #addTaskBtn');
                    if (btn) btn.click();
                    else if (typeof showToast === 'function') showToast('Кнопка создания задачи не найдена', 'warning');
                }
            });
        }

        if (document.querySelector('.table-wrap, table, .data-table')) {
            actions.push({
                title: 'Экспорт',
                icon: 'fas fa-file-export',
                keywords: 'export скачать excel xlsx',
                action: function() {
                    var btn = document.querySelector('[data-action="export"], .btn-export, #exportBtn, .export-btn');
                    if (btn) btn.click();
                    else if (typeof showToast === 'function') showToast('Кнопка экспорта не найдена', 'warning');
                }
            });
        }

        return actions;
    }

    /* ── Fuzzy match ───────────────────────────────────────────────────── */
    function fuzzyMatch(text, query) {
        text = text.toLowerCase();
        query = query.toLowerCase();
        // Exact substring — highest priority
        if (text.indexOf(query) >= 0) return 2;
        // Fuzzy: all query chars appear in order
        var ti = 0;
        for (var qi = 0; qi < query.length; qi++) {
            var found = false;
            while (ti < text.length) {
                if (text[ti] === query[qi]) { ti++; found = true; break; }
                ti++;
            }
            if (!found) return 0;
        }
        return 1;
    }

    function scoreItem(item, query) {
        var s = fuzzyMatch(item.title, query);
        if (s) return s + 1; // title match bonus
        if (item.keywords) {
            var ks = fuzzyMatch(item.keywords, query);
            if (ks) return ks;
        }
        return 0;
    }

    /* ── UI state ──────────────────────────────────────────────────────── */
    var overlay = null;
    var selectedIdx = 0;
    var flatItems = [];   // flattened filtered items for keyboard nav

    function open() {
        if (overlay) return;
        overlay = document.createElement('div');
        overlay.className = 'cmd-palette-overlay';
        overlay.innerHTML =
            '<div class="cmd-palette">' +
              '<div class="cmd-palette-input-wrap">' +
                '<i class="fas fa-search cmd-palette-icon"></i>' +
                '<input class="cmd-palette-input" type="text" placeholder="Поиск по системе... (Ctrl+K)" autofocus>' +
                '<kbd class="cmd-palette-esc">Esc</kbd>' +
              '</div>' +
              '<div class="cmd-palette-list"></div>' +
              '<div class="cmd-palette-footer"><span>↑↓ навигация</span><span>↵ перейти</span><span>esc закрыть</span></div>' +
            '</div>';
        document.body.appendChild(overlay);

        var input = overlay.querySelector('.cmd-palette-input');
        var list = overlay.querySelector('.cmd-palette-list');

        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) close();
        });

        input.addEventListener('input', function() {
            render(input.value.trim());
        });

        input.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowDown') {
                selectedIdx = Math.min(selectedIdx + 1, flatItems.length - 1);
                renderHighlight(list);
                e.preventDefault();
            } else if (e.key === 'ArrowUp') {
                selectedIdx = Math.max(selectedIdx - 1, 0);
                renderHighlight(list);
                e.preventDefault();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                var item = flatItems[selectedIdx];
                if (item) {
                    close();
                    if (item.action) {
                        item.action();
                    } else if (item.url) {
                        window.location.href = item.url;
                    }
                }
            } else if (e.key === 'Escape') {
                close();
            }
        });

        function render(q) {
            var actions = getActions();
            var filteredPages, filteredActions;

            if (!q) {
                filteredPages = PAGES.slice();
                filteredActions = actions.slice();
            } else {
                filteredPages = PAGES.filter(function(p) { return scoreItem(p, q) > 0; })
                    .sort(function(a, b) { return scoreItem(b, q) - scoreItem(a, q); });
                filteredActions = actions.filter(function(a) { return scoreItem(a, q) > 0; })
                    .sort(function(a, b) { return scoreItem(b, q) - scoreItem(a, q); });
            }

            flatItems = [];
            var html = '';

            if (filteredPages.length) {
                html += '<div class="cmd-palette-group">Страницы</div>';
                filteredPages.forEach(function(item) {
                    var idx = flatItems.length;
                    flatItems.push(item);
                    var isActive = window.location.pathname === item.url;
                    html += '<a class="cmd-palette-item' + (idx === 0 ? ' active' : '') + (isActive ? ' current-page' : '') + '" href="' + item.url + '" data-idx="' + idx + '">' +
                        '<i class="' + item.icon + '"></i><span>' + highlightMatch(item.title, q) + '</span>' +
                        (isActive ? '<span class="cmd-palette-current-badge">текущая</span>' : '') +
                        '</a>';
                });
            }

            if (filteredActions.length) {
                html += '<div class="cmd-palette-group">Действия</div>';
                filteredActions.forEach(function(item) {
                    var idx = flatItems.length;
                    flatItems.push(item);
                    html += '<div class="cmd-palette-item' + (idx === 0 && !filteredPages.length ? ' active' : '') + '" data-idx="' + idx + '">' +
                        '<i class="' + item.icon + '"></i><span>' + highlightMatch(item.title, q) + '</span>' +
                        '<span class="cmd-palette-action-badge">действие</span>' +
                        '</div>';
                });
            }

            if (!flatItems.length) {
                html = '<div class="cmd-palette-empty">Ничего не найдено</div>';
            }

            selectedIdx = 0;
            list.innerHTML = html;

            // Click handlers for action items
            list.querySelectorAll('.cmd-palette-item').forEach(function(el) {
                el.addEventListener('click', function(e) {
                    var idx = parseInt(el.getAttribute('data-idx'), 10);
                    var item = flatItems[idx];
                    if (item && item.action) {
                        e.preventDefault();
                        close();
                        item.action();
                    }
                    // page links use native <a> navigation
                });
            });
        }

        function highlightMatch(title, q) {
            if (!q) return title;
            var lower = title.toLowerCase();
            var ql = q.toLowerCase();
            var idx = lower.indexOf(ql);
            if (idx >= 0) {
                return title.substring(0, idx) +
                    '<mark class="cmd-palette-match">' + title.substring(idx, idx + q.length) + '</mark>' +
                    title.substring(idx + q.length);
            }
            return title;
        }

        function renderHighlight(listEl) {
            var items = listEl.querySelectorAll('.cmd-palette-item');
            items.forEach(function(el) {
                var idx = parseInt(el.getAttribute('data-idx'), 10);
                el.classList.toggle('active', idx === selectedIdx);
                if (idx === selectedIdx) el.scrollIntoView({block:'nearest'});
            });
        }

        render('');
        setTimeout(function() { input.focus(); }, 50);
    }

    function close() {
        if (overlay) { overlay.remove(); overlay = null; }
    }

    /* ── Global keyboard shortcut ──────────────────────────────────────── */
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            if (overlay) close(); else open();
        }
    });

    /* ── Public API for the topbar hint button ─────────────────────────── */
    window.toggleCommandPalette = function() {
        if (overlay) close(); else open();
    };
})();
