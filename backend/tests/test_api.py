import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend import repository
from backend.config import settings
from backend.main import create_app
from backend.repository_file import FileRepository

DATA = Path(__file__).resolve().parents[2] / "data" / "data.json"


def start( data_dir ):
    repository.set_repository(FileRepository(data_dir))
    return TestClient(create_app())

def login( client ):
    r = client.post("/api/v1/auth/login", json={ "username": "admin", "password": "admin" })
    assert r.status_code == 200, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return client

def raw_data():
    return json.loads(DATA.read_text(encoding="utf-8"))


class Api( unittest.TestCase ):
    def setUp( self ):
        self.dir = tempfile.TemporaryDirectory()
        self.client = start(self.dir.name).__enter__()

    def tearDown( self ):
        self.client.__exit__(None, None, None)
        repository.set_repository(None)
        self.dir.cleanup()

    def restart( self ):
        self.client.__exit__(None, None, None)
        self.client = start(self.dir.name).__enter__()

    def test_no_access_without_login( self ):
        for path in ( "/api/v1/customers", "/api/v1/customers/1", "/api/v1/customers/export.csv",
                      "/api/v1/analytics/summary", "/api/v1/analytics/churn-chart", "/api/v1/analytics/journal",
                      "/api/v1/model/settings", "/api/v1/source/snapshot", "/api/v1/auth/me", "/api/v1/events" ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.put("/api/v1/source/snapshot", json={}).status_code, 401)
        self.assertEqual(self.client.patch("/api/v1/source/snapshot", json={}).status_code, 401)
        self.assertEqual(self.client.patch("/api/v1/model/settings", json={}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/model/settings/preview", json={}).status_code, 401)

    def test_providers_without_oidc( self ):
        r = self.client.get("/api/v1/auth/providers")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["oidc"], False)
        self.assertEqual(self.client.get("/api/v1/auth/oidc/login").status_code, 404)

    def test_wrong_password( self ):
        r = self.client.post("/api/v1/auth/login", json={ "username": "admin", "password": "nope" })
        self.assertEqual(r.status_code, 401)

    def test_logout_revokes_token( self ):
        login(self.client)
        self.assertEqual(self.client.post("/api/v1/auth/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_session_survives_restart( self ):
        login(self.client)
        token = self.client.headers["Authorization"]
        self.restart()
        self.client.headers["Authorization"] = token
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 200)

    def test_sorting_both_directions( self ):
        login(self.client)
        for field, key in ( ("accountId", "accountId"), ("email", "email"), ("balance", "balance"),
                            ("totalReplenished", "totalReplenished"), ("score", "score"),
                            ("expectedLoss", "expectedLoss") ):
            for order in ( "asc", "desc" ):
                with self.subTest(field=field, order=order):
                    r = self.client.get("/api/v1/customers", params={ "sort_by": field, "sort_order": order, "limit": 500 })
                    values = [c[key] for c in r.json()["items"] if c[key] is not None]
                    self.assertEqual(values, sorted(values, reverse=order == "desc"))

    def test_level_filter_accepts_risk_zone( self ):
        login(self.client)
        summary = self.client.get("/api/v1/analytics/summary").json()["customersByLevel"]
        r = self.client.get("/api/v1/customers", params={ "level": "high,medium", "limit": 500 })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total"], summary["high"] + summary["medium"])
        self.assertEqual({ c["level"] for c in r.json()["items"] }, { "high", "medium" })
        self.assertEqual(self.client.get("/api/v1/customers", params={ "level": "nope" }).status_code, 422)
        csv = self.client.get("/api/v1/customers/export.csv", params={ "level": "high,medium" })
        self.assertEqual(len(csv.text.splitlines()) - 1, summary["high"] + summary["medium"])

    def test_list_has_reasons_action_and_detail_has_services( self ):
        login(self.client)
        top = self.client.get("/api/v1/customers", params={ "sort_by": "score", "sort_order": "desc", "limit": 1 }).json()["items"][0]
        self.assertTrue(top["reasons"])
        self.assertTrue(top["action"]["title"])
        detail = self.client.get(f"/api/v1/customers/{top['accountId']}").json()
        self.assertTrue(detail["services"])
        self.assertIn("history", detail)
        self.assertIn("revenueFull", detail["services"][0])
        self.assertGreaterEqual(len(detail["reasons"]), len(top["reasons"]))

    def test_export_csv( self ):
        login(self.client)
        r = self.client.get("/api/v1/customers/export.csv", params={ "level": "high" })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("text/csv"))
        lines = r.text.lstrip("﻿").splitlines()
        self.assertTrue(lines[0].startswith("id;email;balance_eur"))
        high = self.client.get("/api/v1/analytics/summary").json()["customersByLevel"]["high"]
        self.assertEqual(len(lines) - 1, high)

    def test_patch_recalculates( self ):
        login(self.client)
        before = self.client.get("/api/v1/analytics/summary").json()["expectedLossTotal"]
        r = self.client.patch("/api/v1/model/settings", json={ "weights": { "prolong_wait": 0 } })
        self.assertEqual(r.status_code, 200)
        after = self.client.get("/api/v1/analytics/summary").json()["expectedLossTotal"]
        self.assertLess(after, before)

    def test_preview_does_not_persist( self ):
        login(self.client)
        before = self.client.get("/api/v1/analytics/summary").json()
        r = self.client.post("/api/v1/model/settings/preview", json={ "weights": { "prolong_wait": 0, "insufficient_funds": 0 } })
        self.assertEqual(r.status_code, 200)
        self.assertLess(r.json()["summary"]["expectedLossTotal"], before["expectedLossTotal"])
        self.assertEqual(r.json()["settings"]["weights"]["prolong_wait"], 0)
        self.assertEqual(self.client.get("/api/v1/analytics/summary").json(), before)
        self.assertEqual(self.client.get("/api/v1/model/settings").json()["weights"]["prolong_wait"], 0.9)
        self.assertEqual(self.client.post("/api/v1/model/settings/preview", json={ "referenceTime": "garbage" }).status_code, 422)

    def test_bad_settings_rejected( self ):
        login(self.client)
        for patch in ( { "weights": { "nope": 0.1 } }, { "weights": { "suspended": 2 } },
                       { "highThreshold": 10, "mediumThreshold": 50 }, { "unknown": 1 },
                       { "referenceTime": "garbage" } ):
            with self.subTest(patch=patch):
                self.assertEqual(self.client.patch("/api/v1/model/settings", json=patch).status_code, 422)

    def test_invalid_reference_time_is_not_persisted( self ):
        login(self.client)
        self.assertEqual(self.client.patch("/api/v1/model/settings", json={ "referenceTime": "garbage" }).status_code, 422)
        saved = json.loads((Path(self.dir.name) / "model_settings.json").read_text(encoding="utf-8")) \
            if (Path(self.dir.name) / "model_settings.json").is_file() else {}
        self.assertIsNone(saved.get("referenceTime"))
        self.assertEqual(self.client.patch("/api/v1/model/settings", json={ "weights": { "suspended": 0.1 } }).status_code, 200)
        self.restart()
        login(self.client)
        self.assertEqual(self.client.get("/api/v1/analytics/summary").status_code, 200)

    def test_settings_and_snapshot_survive_restart( self ):
        login(self.client)
        self.client.patch("/api/v1/model/settings", json={ "weights": { "suspended": 0.55 }, "horizonDays": 14 })
        raw = raw_data()
        accounts = raw["accounts"][:5]
        ids = { a["id"] for a in accounts }
        services = [s for s in raw["services"] if s["ownerId"] in ids]
        sids = { s["id"] for s in services }
        small = { "accounts": accounts, "services": services,
                  "transactions": [t for t in raw["transactions"] if t["serviceId"] in sids] }
        self.assertEqual(self.client.put("/api/v1/source/snapshot", json=small).status_code, 200)
        self.restart()
        login(self.client)
        settings_now = self.client.get("/api/v1/model/settings").json()
        self.assertEqual(settings_now["weights"]["suspended"], 0.55)
        self.assertEqual(settings_now["horizonDays"], 14)
        self.assertEqual(self.client.get("/api/v1/analytics/summary").json()["customersTotal"], 5)

    def test_free_form_names_and_big_amounts_accepted( self ):
        login(self.client)
        raw = raw_data()
        account = raw["accounts"][0]
        service = dict(raw["services"][0], name="Мой сервер #1 (prod)", ownerId=account["id"])
        transaction = dict(raw["transactions"][0], amount=250_000, serviceId=service["id"])
        r = self.client.put("/api/v1/source/snapshot", json={ "accounts": [account], "services": [service], "transactions": [transaction] })
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["counts"], { "accounts": 1, "services": 1, "transactions": 1 })

    def test_upsert_records_journal_and_history( self ):
        login(self.client)
        raw = raw_data()
        victim = next(s for s in raw["services"] if s["status"] == "active")
        changed = dict(victim, status="deleted", autoProlong=not victim["autoProlong"])
        r = self.client.patch("/api/v1/source/snapshot", json={ "services": [changed] })
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["applied"], { "accounts": 0, "services": 1, "transactions": 0 })
        self.assertEqual(body["transitions"], 2)
        self.assertEqual(body["counts"]["services"], len(raw["services"]))

        journal = self.client.get("/api/v1/analytics/journal", params={ "service_id": victim["id"] }).json()
        self.assertEqual({ e["field"] for e in journal }, { "status", "autoProlong" })
        self.assertEqual(next(e for e in journal if e["field"] == "status")["new"], "deleted")

        history = self.client.get(f"/api/v1/customers/{victim['ownerId']}").json()["history"]
        self.assertTrue(any(e["serviceId"] == victim["id"] for e in history))

        chart = self.client.get("/api/v1/analytics/churn-chart").json()
        self.assertEqual(sum(p["deletedObserved"] for p in chart["points"]), 1)

        bad = dict(victim, ownerId=10_000)
        self.assertEqual(self.client.patch("/api/v1/source/snapshot", json={ "services": [bad] }).status_code, 422)
        self.assertEqual(self.client.patch("/api/v1/source/snapshot", json={}).status_code, 422)

    def test_chart_forecast_is_not_in_the_past( self ):
        login(self.client)
        chart = self.client.get("/api/v1/analytics/churn-chart").json()
        ref = date.fromisoformat(chart["referenceDate"])
        ref_bucket = ref - timedelta(days=ref.weekday()) if chart["bucket"] == "week" else ref
        forecast = [p for p in chart["points"] if p["expectedNonrenewals"] > 0 or p["servicesAtRisk"] > 0]
        self.assertTrue(forecast)
        for p in forecast:
            self.assertGreaterEqual(date.fromisoformat(p["date"]), ref_bucket)
        self.assertGreater(sum(p["deleted"] for p in chart["points"]), 0)

    def test_metrics_match_summary( self ):
        login(self.client)
        summary = self.client.get("/api/v1/analytics/summary").json()
        r = self.client.get("/metrics", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        values = { line.rsplit(" ", 1)[0]: float(line.rsplit(" ", 1)[1])
                   for line in r.text.splitlines() if line.startswith("churn_") }
        for level, count in summary["customersByLevel"].items():
            self.assertEqual(values[f'churn_customers_by_risk_total{{level="{level}"}}'], count)
        self.assertEqual(values["churn_potential_loss_cents"], summary["expectedLossTotal"])
        self.assertEqual(values["churn_revenue_full_cents"], summary["revenueFullTotal"])
        for impact in summary["features"]:
            self.assertEqual(values[f'churn_feature_customers_total{{feature="{impact["feature"]}"}}'], impact["customers"])

    def test_metrics_token( self ):
        settings.METRICS_TOKEN = "secret-scraper-token"
        try:
            anonymous = self.client.get("/metrics", follow_redirects=False)
            self.assertEqual(anonymous.status_code, 401)
            ok = self.client.get("/metrics", headers={ "Authorization": "Bearer secret-scraper-token" }, follow_redirects=False)
            self.assertEqual(ok.status_code, 200)
        finally:
            settings.METRICS_TOKEN = ""

    def test_health_is_minimal( self ):
        body = self.client.get("/health").json()
        self.assertEqual(set(body), { "status", "last_updated" })
