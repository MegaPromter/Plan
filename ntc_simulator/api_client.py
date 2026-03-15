"""
HTTP-client for planapp_django API.
Sessions, CSRF, request logging, metrics.
"""
import logging
import time
from collections import defaultdict

import requests

logger = logging.getLogger('simulator')


class ApiMetrics:
    """Collects API request metrics."""

    def __init__(self):
        self.request_count = 0
        self.errors_4xx = defaultdict(list)
        self.errors_5xx = defaultdict(list)
        self.response_times = defaultdict(list)
        self.bugs = []

    def record(self, method, path, status, elapsed_ms):
        self.request_count += 1
        key = f"{method} {path}"
        self.response_times[key].append(elapsed_ms)
        if 400 <= status < 500:
            self.errors_4xx[key].append(status)
        elif status >= 500:
            self.errors_5xx[key].append(status)

    def report_bug(self, desc):
        self.bugs.append(desc)
        logger.warning("BUG: %s", desc)

    def summary(self):
        avg_times = {}
        for ep, times in self.response_times.items():
            avg_times[ep] = round(sum(times) / len(times), 1) if times else 0
        return {
            'total_requests': self.request_count,
            'errors_4xx': {k: len(v) for k, v in self.errors_4xx.items()},
            'errors_5xx': {k: len(v) for k, v in self.errors_5xx.items()},
            'avg_response_ms': avg_times,
            'bugs': self.bugs,
        }


class ApiClient:
    """HTTP client with Django session/CSRF support. One instance = one user."""

    def __init__(self, base_url, metrics: ApiMetrics):
        self.base_url = base_url.rstrip('/')
        self.metrics = metrics
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
        self.username = None

    def login(self, username, password):
        """Login via Django LoginView (session)."""
        self.username = username
        login_url = f"{self.base_url}/accounts/login/"
        self.session.get(login_url)
        csrf = self.session.cookies.get('csrftoken', '')
        resp = self.session.post(login_url, data={
            'username': username,
            'password': password,
            'csrfmiddlewaretoken': csrf,
        }, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': login_url,
        }, allow_redirects=False)
        if resp.status_code in (200, 301, 302):
            logger.info("Login OK: %s", username)
            return True
        logger.error("Login FAIL: %s -> %s", username, resp.status_code)
        return False

    def _get_csrf(self):
        return self.session.cookies.get('csrftoken', '')

    def _url(self, path):
        return f"{self.base_url}{path}"

    def _request(self, method, path, json_data=None, params=None,
                 max_retries=5):
        """Generic request with retry on 429."""
        url = self._url(path)
        headers = {'X-CSRFToken': self._get_csrf()} if method != 'GET' else {}
        resp = None

        for attempt in range(max_retries + 1):
            t0 = time.perf_counter()
            try:
                resp = self.session.request(
                    method, url, json=json_data, params=params,
                    headers=headers, timeout=30)
            except requests.RequestException as e:
                logger.error("%s %s -> network error: %s", method, path, e)
                return None
            elapsed = (time.perf_counter() - t0) * 1000
            self.metrics.record(method, path, resp.status_code, elapsed)

            if resp.status_code == 429 and attempt < max_retries:
                wait = 3 * (attempt + 1)
                logger.debug("429 on %s %s, retry in %ds (attempt %d)...",
                             method, path, wait, attempt + 1)
                time.sleep(wait)
                continue

            if resp.status_code >= 400:
                logger.warning("%s %s -> %s: %s", method, path,
                               resp.status_code, resp.text[:200])
            return resp
        return resp

    def get(self, path, params=None):
        return self._request('GET', path, params=params)

    def post(self, path, json_data=None):
        return self._request('POST', path, json_data=json_data)

    def put(self, path, json_data=None, params=None):
        return self._request('PUT', path, json_data=json_data, params=params)

    def delete(self, path):
        return self._request('DELETE', path)

    def json_ok(self, resp):
        """Returns JSON if response 2xx, else None."""
        if resp is None:
            return None
        if resp.status_code < 300:
            try:
                return resp.json()
            except Exception:
                return None
        return None
