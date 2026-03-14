"""
Тесты health check эндпоинта.
GET /api/health/ — возвращает 200 с {"status": "ok"} без авторизации.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestHealthCheck:
    def test_returns_200(self):
        """Health check возвращает 200."""
        client = Client()
        resp = client.get('/api/health/')
        assert resp.status_code == 200

    def test_returns_status_ok(self):
        """Тело ответа содержит {"status": "ok"}."""
        client = Client()
        resp = client.get('/api/health/')
        data = resp.json()
        assert data['status'] == 'ok'

    def test_no_auth_required(self):
        """Эндпоинт доступен без авторизации."""
        client = Client()
        resp = client.get('/api/health/')
        # Не должен быть 401 или 403
        assert resp.status_code not in (401, 403)
        assert resp.status_code == 200
