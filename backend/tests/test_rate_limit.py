import asyncio
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import create_app
from backend.rate_limit import RateLimiter
from backend.repository import MemoryRepository, set_repository


class SlidingWindowTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.limiter = RateLimiter(
            window=60, api_limit=3, login_limit=2, max_clients=2,
            clock=lambda: self.now,
        )

    def test_sliding_window_and_retry_do_not_extend_block(self):
        self.assertEqual(self.limiter.check("a").retry_after, 0)
        self.now += 10
        self.limiter.check("a")
        self.limiter.check("a")
        self.assertEqual(self.limiter.check("a").retry_after, 50)
        self.now = 159.5
        self.assertEqual(self.limiter.check("a").retry_after, 1)
        self.now = 160
        self.assertEqual(self.limiter.check("a").retry_after, 0)
        self.assertEqual(self.limiter.check("a").retry_after, 10)

    def test_login_budget_does_not_block_other_api_or_other_ip(self):
        for _ in range(2):
            self.assertEqual(self.limiter.check("a", login=True).retry_after, 0)
        self.assertEqual(self.limiter.check("a", login=True).scope, "login")
        self.assertEqual(self.limiter.check("a").retry_after, 0)
        self.assertEqual(self.limiter.check("b", login=True).retry_after, 0)

    def test_bounded_memory_keeps_active_limits_and_reclaims_expired_clients(self):
        for _ in range(3):
            self.limiter.check("a")
        self.limiter.check("b")
        self.assertEqual(self.limiter.check("c").scope, "capacity")
        self.assertGreater(self.limiter.check("a").retry_after, 0)
        self.now += 60
        self.assertEqual(self.limiter.check("c").retry_after, 0)
        self.assertEqual(len(self.limiter._clients), 1)

    def test_concurrent_requests_share_budget(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            decisions = list(pool.map(lambda _: self.limiter.check("a"), range(20)))
        self.assertEqual(sum(d.retry_after == 0 for d in decisions), 3)


class RateLimitApiTests(unittest.TestCase):
    def setUp(self):
        repository = MemoryRepository()
        asyncio.run(repository.create_user("admin", "unused-in-mocked-verifier"))
        set_repository(repository)
        with patch.object(settings, "RATE_LIMIT_API_REQUESTS", 20), \
             patch.object(settings, "RATE_LIMIT_LOGIN_REQUESTS", 2), \
             patch.object(settings, "RATE_LIMIT_ENABLED", True):
            self.app = create_app()
        self.now = 100.0
        self.app.state.rate_limiter.clock = lambda: self.now
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        set_repository(None)

    def test_password_checks_are_blocked_before_auth_and_expire(self):
        with patch("backend.routers.auth.verify_password", return_value=False) as verify:
            for _ in range(2):
                self.assertEqual(self.client.post(
                    "/api/v1/auth/login", json={"username": "admin", "password": "wrong"},
                ).status_code, 401)
            blocked = self.client.post(
                "/api/v1/auth/login", json={"username": "admin", "password": "anything"},
                headers={"Origin": "http://localhost:5173"},
            )
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(blocked.headers["Retry-After"], "60")
            self.assertEqual(blocked.json()["retryAfter"], 60)
            self.assertEqual(blocked.headers["Access-Control-Allow-Origin"], "http://localhost:5173")
            self.assertEqual(verify.call_count, 2)
            self.now += 60
            self.assertEqual(self.client.post(
                "/api/v1/auth/login", json={"username": "admin", "password": "wrong"},
            ).status_code, 401)
            self.assertEqual(verify.call_count, 3)

    def test_invalid_login_body_and_trailing_slash_cannot_bypass_limit(self):
        for _ in range(2):
            self.assertEqual(self.client.post("/api/v1/auth/login", json={}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/auth/login/", json={}).status_code, 429)

    def test_successful_logins_also_consume_budget(self):
        with patch("backend.routers.auth.verify_password", return_value=True):
            for _ in range(2):
                self.assertEqual(self.client.post(
                    "/api/v1/auth/login", json={"username": "admin", "password": "correct"},
                ).status_code, 200)
            self.assertEqual(self.client.post(
                "/api/v1/auth/login", json={"username": "admin", "password": "correct"},
            ).status_code, 429)

    def test_api_budget_covers_paths_queries_and_unauthorized_requests(self):
        for i in range(20):
            path = "/api/v1/customers" if i % 2 else "/api/v1/analytics/summary"
            self.assertEqual(self.client.get(path, params={"search": str(i)}).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/auth/providers").status_code, 429)
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/metrics").status_code, 200)
        preflight = self.client.options("/api/v1/customers", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
        })
        self.assertEqual(preflight.status_code, 200)

    def test_untrusted_forwarded_headers_do_not_reset_ip_budget(self):
        for i in range(2):
            self.assertEqual(self.client.post(
                "/api/v1/auth/login", json={}, headers={"X-Forwarded-For": f"198.51.100.{i}"},
            ).status_code, 422)
        self.assertEqual(self.client.post(
            "/api/v1/auth/login", json={}, headers={"X-Forwarded-For": "203.0.113.99"},
        ).status_code, 429)

    def test_different_clients_have_separate_budgets(self):
        for _ in range(2):
            self.client.post("/api/v1/auth/login", json={})
        self.assertEqual(self.client.post("/api/v1/auth/login", json={}).status_code, 429)
        other = TestClient(self.app, client=("198.51.100.8", 1234))
        try:
            self.assertEqual(other.post("/api/v1/auth/login", json={}).status_code, 422)
        finally:
            other.close()

    def test_rate_limit_response_is_documented(self):
        schema = self.app.openapi()
        for path, operations in schema["paths"].items():
            if path.startswith("/api/v1/"):
                for operation in operations.values():
                    self.assertIn("429", operation["responses"])

    def test_can_disable_limits_for_an_isolated_environment(self):
        with patch.object(settings, "RATE_LIMIT_ENABLED", False):
            app = create_app()
        client = TestClient(app)
        try:
            for _ in range(7):
                self.assertEqual(client.post("/api/v1/auth/login", json={}).status_code, 422)
        finally:
            client.close()
