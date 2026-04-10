"""
Template tag для подключения Vite-собранных Vue-модулей в Django-шаблонах.

Использование:
  {% load vite %}
  {% vite_asset 'notices' %}

В dev-режиме (DEBUG=True) подключает Vite dev-сервер с HMR.
В prod-режиме читает manifest.json и подставляет хешированные пути.
"""

import json
import os

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()

_manifest_cache = None


def _load_manifest():
    """Загружает Vite manifest.json (кэшируется в prod)."""
    global _manifest_cache
    if _manifest_cache is not None and not settings.DEBUG:
        return _manifest_cache
    manifest_path = os.path.join(settings.BASE_DIR, "static", "vue", "manifest.json")
    try:
        with open(manifest_path, encoding="utf-8") as f:
            _manifest_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _manifest_cache = {}
    return _manifest_cache


@register.simple_tag
def vite_asset(entry_name):
    """Подключает JS+CSS для указанного entry point.

    В DEBUG: если есть manifest.json (собранный билд) — использует его,
    иначе подключает Vite dev-сервер (localhost:5173) с HMR.
    В PROD: всегда читает manifest.json.
    """
    manifest = _load_manifest()
    entry_key = f"src/{entry_name}.js"
    entry = manifest.get(entry_key, {})

    # Если есть собранный билд — используем его (и в DEBUG, и в PROD)
    if entry:
        tags = []
        # CSS-файлы (если Vite выделил стили в отдельный файл)
        for css in entry.get("css", []):
            tags.append(f'<link rel="stylesheet" href="/static/vue/{css}">')
        # JS-файл
        js_file = entry.get("file", "")
        if js_file:
            tags.append(f'<script type="module" src="/static/vue/{js_file}"></script>')
        return mark_safe("\n".join(tags))

    # Fallback в DEBUG: Vite dev-сервер с горячей перезагрузкой
    if settings.DEBUG:
        return mark_safe(
            '<script type="module" src="http://localhost:5173/@vite/client"></script>'
            f'<script type="module" src="http://localhost:5173/src/{entry_name}.js"></script>'
        )

    # PROD без manifest — пустая строка (ошибка сборки)
    return mark_safe("")
