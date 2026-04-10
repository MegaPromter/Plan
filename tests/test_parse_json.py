"""
Тесты parse_json_body — парсинг JSON из тела запроса.
"""

import pytest
from django.test import RequestFactory

from apps.api.mixins import parse_json_body


@pytest.fixture
def rf():
    """Фабрика фиктивных HTTP-запросов."""
    return RequestFactory()


def _make_request(rf, body: bytes):
    """Создаёт POST-запрос с заданным телом."""
    request = rf.post(
        "/api/fake/",
        data=body,
        content_type="application/json",
    )
    # RequestFactory не заполняет body из data при content_type json,
    # поэтому принудительно перезаписываем
    request._body = body
    return request


class TestParseJsonBodyValidDict:
    """Валидный JSON-объект — возвращает dict."""

    def test_simple_dict(self, rf):
        body = b'{"name": "Test", "value": 42}'
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result == {"name": "Test", "value": 42}

    def test_dict_with_cyrillic(self, rf):
        import json

        body = json.dumps({"name": "Тестовая работа"}).encode("utf-8")
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result == {"name": "Тестовая работа"}

    def test_nested_dict(self, rf):
        body = b'{"data": {"inner": true}}'
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result == {"data": {"inner": True}}

    def test_empty_dict(self, rf):
        body = b"{}"
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result == {}


class TestParseJsonBodyEmptyBody:
    """Пустое тело — возвращает пустой dict."""

    def test_empty_bytes(self, rf):
        request = _make_request(rf, b"")
        result = parse_json_body(request)
        assert result == {}


class TestParseJsonBodyMalformed:
    """Невалидный JSON — возвращает None."""

    def test_broken_json(self, rf):
        body = b"{invalid json}"
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result is None

    def test_truncated_json(self, rf):
        body = b'{"key": "value'
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result is None

    def test_just_comma(self, rf):
        body = b","
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result is None


class TestParseJsonBodyNonDict:
    """Валидный JSON, но не dict — возвращает None."""

    def test_array(self, rf):
        body = b"[1, 2, 3]"
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result is None

    def test_string(self, rf):
        body = b'"just a string"'
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result is None

    def test_number(self, rf):
        body = b"42"
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result is None

    def test_boolean(self, rf):
        body = b"true"
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result is None

    def test_null(self, rf):
        body = b"null"
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result is None


class TestParseJsonBodyBinaryGarbage:
    """Бинарный мусор — возвращает None."""

    def test_random_bytes(self, rf):
        body = b"\x00\x01\x02\xff\xfe\xfd"
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result is None

    def test_utf8_garbage(self, rf):
        body = "Это не JSON, а просто текст кириллицей".encode()
        request = _make_request(rf, body)
        result = parse_json_body(request)
        assert result is None
