
import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from backend.models import Snapshot
from backend.risk.defaults import default_settings, merge_settings
from backend.risk.features import FEATURES
from backend.risk.scoring import evaluate, summarize, timeline

NOW = "2026-10-19T15:00:00.000Z"
DATA = Path(__file__).resolve().parents[2] / "data" / "data.json"

def account( id=1, balance=100_000, bonus=0, bonusState="locked", replenished=None ):
    return { "id": id, "email": f"user-{id}@example.test", "balance": balance, "withdrawBalance": 0,
             "totalReplenished": balance + 50_000 if replenished is None else replenished,
             "bonusBalance": bonus, "bonusState": bonusState }

def service( id=1, owner=1, status="active", term="month", auto=True,
             expires="2026-12-19T15:00:00.000Z", price=500, created="2026-01-01T00:00:00.000Z" ):
    return { "id": id, "name": f"service-{id}", "ownerId": owner, "paymentTerm": term, "autoProlong": auto,
             "createdAt": created, "expiresAt": expires, "status": status, "price": price }

def tx( id, serviceId, performed=True, created="2026-09-01T00:00:00.000Z" ):
    return { "id": id, "amount": 100, "type": "prolong", "serviceId": serviceId,
             "status": "performed" if performed else "not_performed",
             "createdAt": created,
             "performedAt": created.replace("00:00:00", "00:01:00") if performed else None }

def snapshot_of( accounts, services, transactions=() ):
    return Snapshot.format_dict({ "accounts": accounts, "services": services, "transactions": list(transactions) })

def score_one( accounts, services, transactions=(), **settings ):
    return evaluate(snapshot_of(accounts, services, transactions), { "referenceTime": NOW, **settings })[0]

def fired( customer ):
    return { r.feature for r in customer.reasons }


class Scenarios( unittest.TestCase ):
    def test_healthy_client_is_low( self ):
        c = score_one([account()], [service()], [tx(1, 1)])
        self.assertEqual(c.level, "low")
        self.assertEqual(c.score, 0)
        self.assertEqual(c.reasons, [])
        self.assertIsNone(c.action)

    def test_prolong_wait_without_money_is_high( self ):
        c = score_one([account(balance=0)], [service(status="prolong_wait", expires="2026-10-17T15:00:00.000Z")])
        self.assertEqual(c.level, "high")
        self.assertEqual(fired(c), { "prolong_wait", "insufficient_funds" })

    def test_prolong_wait_gets_stronger_to_deletion( self ):
        fresh = score_one([account()], [service(status="prolong_wait", expires="2026-10-19T09:00:00.000Z")])
        late = score_one([account()], [service(status="prolong_wait", expires="2026-10-15T15:00:00.000Z")])
        self.assertLess(fresh.score, late.score)

    def test_zero_grace_does_not_crash( self ):
        c = score_one([account()], [service(status="prolong_wait", expires="2026-10-19T09:00:00.000Z")],
                      prolongWaitGraceDays=0)
        self.assertIn("prolong_wait", fired(c))

    def test_expiring_without_autoprolong_is_medium( self ):
        c = score_one([account()], [service(auto=False, expires="2026-10-21T15:00:00.000Z")])
        self.assertEqual(c.level, "medium")
        self.assertIn("expiring_without_autoprolong", fired(c))

    def test_overdue_service_says_expired( self ):
        c = score_one([account()], [service(auto=False, expires="2026-10-10T15:00:00.000Z")])
        reason = next(r for r in c.reasons if r.feature == "expiring_without_autoprolong")
        self.assertIn("истёк", reason.text)
        self.assertEqual(reason.strength, 1.0)

    def test_far_expiry_without_autoprolong_is_ignored( self ):
        c = score_one([account()], [service(auto=False, expires="2027-10-19T15:00:00.000Z")])
        self.assertNotIn("expiring_without_autoprolong", fired(c))

    def test_hourly_and_weekly_expiry_window( self ):
        hourly = service(term="hour", auto=False, expires="2026-10-19T15:30:00.000Z")
        self.assertNotIn("expiring_without_autoprolong", fired(score_one([account()], [hourly])))
        weekly = lambda expires: score_one([account()], [service(term="week", auto=False, expires=expires)])
        self.assertNotIn("expiring_without_autoprolong", fired(weekly("2026-10-24T15:00:00.000Z")))
        self.assertIn("expiring_without_autoprolong", fired(weekly("2026-10-20T15:00:00.000Z")))

    def test_far_shortfall_is_weaker( self ):
        near = score_one([account(balance=0)], [service(expires="2026-10-22T15:00:00.000Z")])
        far = score_one([account(balance=0)], [service(expires="2026-11-15T15:00:00.000Z")])
        strength = lambda c: next(r.strength for r in c.reasons if r.feature == "insufficient_funds")
        self.assertEqual(strength(near), 1.0)
        self.assertLess(strength(far), 0.5)
        self.assertGreaterEqual(strength(far), 0.25)
        self.assertLess(far.score, near.score)

    def test_big_spender_gets_vip_action( self ):
        drained = [service(expires="2026-10-22T15:00:00.000Z", price=500)]
        vip = score_one([account(balance=100, replenished=200_000)], drained)
        self.assertEqual(vip.action.code, "vip_topup")
        plain = score_one([account(balance=100, replenished=50_000)], drained)
        self.assertEqual(plain.action.code, "topup_nudge")
        self.assertEqual(vip.score, plain.score)

    def test_unlocked_bonus_covers_renewal( self ):
        services = [service(expires="2026-10-25T15:00:00.000Z", price=500)]
        locked = score_one([account(balance=0, bonus=1000)], services)
        unlocked = score_one([account(balance=0, bonus=1000, bonusState="unlocked")], services)
        self.assertIn("insufficient_funds", fired(locked))
        self.assertNotIn("insufficient_funds", fired(unlocked))

    def test_money_goes_to_earliest_renewal_first( self ):
        c = score_one([account(balance=500)], [
            service(id=1, expires="2026-10-20T15:00:00.000Z", price=500),
            service(id=2, expires="2026-10-22T15:00:00.000Z", price=500),
        ])
        byId = { s.serviceId: { r.feature for r in s.reasons } for s in c.services }
        self.assertNotIn("insufficient_funds", byId[1])
        self.assertIn("insufficient_funds", byId[2])

    def test_failed_payments_share( self ):
        c = score_one([account()], [service()], [tx(1, 1), tx(2, 1, performed=False)])
        reason = next(r for r in c.reasons if r.feature == "failed_payments")
        self.assertEqual(reason.strength, 0.5)

    def test_failed_payments_skips_attempt_behind_prolong_wait( self ):
        waiting = [service(status="prolong_wait", expires="2026-10-18T15:00:00.000Z")]
        last = tx(2, 1, performed=False, created="2026-10-18T15:00:00.000Z")
        self.assertNotIn("failed_payments", fired(score_one([account()], waiting, [tx(1, 1), last])))
        earlier = tx(3, 1, performed=False, created="2026-09-18T15:00:00.000Z")
        c = score_one([account()], waiting, [tx(1, 1), earlier, last])
        reason = next(r for r in c.reasons if r.feature == "failed_payments")
        self.assertEqual(reason.strength, 0.5)

    def test_failed_payments_ignores_old_attempts( self ):
        old = "2025-01-01T00:00:00.000Z"
        c = score_one([account()], [service()], [tx(1, 1, created=old), tx(2, 1, performed=False, created=old)])
        self.assertNotIn("failed_payments", fired(c))
        c = score_one([account()], [service()], [tx(1, 1, created=old), tx(2, 1, performed=False, created=old)],
                      paymentLookbackDays=1000)
        self.assertIn("failed_payments", fired(c))

    def test_deleted_services_reason_shown_once( self ):
        c = score_one([account()], [service(id=1), service(id=2), service(id=3, status="deleted")])
        self.assertEqual(sum(1 for r in c.reasons if r.feature == "deleted_services"), 1)

    def test_deleted_hourly_servers_are_not_churn( self ):
        hourly = [service(id=1), service(id=2, term="hour", status="deleted"), service(id=3, term="hour", status="deleted")]
        self.assertNotIn("deleted_services", fired(score_one([account()], hourly)))
        c = score_one([account()], [service(id=1), service(id=2, term="hour"), service(id=3, status="deleted")])
        reason = next(r for r in c.reasons if r.feature == "deleted_services")
        self.assertEqual(reason.strength, 0.5)

    def test_only_churned_services_means_no_data( self ):
        c = score_one([account()], [service(status="deleted"), service(id=2, status="blocked")])
        self.assertIsNone(c.score)
        self.assertEqual(c.level, "no_data")
        self.assertEqual(c.expectedLoss, 0)

    def test_zero_weight_disables_feature( self ):
        c = score_one([account(balance=0)], [service(status="prolong_wait", expires="2026-10-17T15:00:00.000Z")],
                      weights={ "prolong_wait": 0 })
        self.assertNotIn("prolong_wait", fired(c))

    def test_expected_loss_is_risk_times_revenue( self ):
        c = score_one([account(balance=0)], [service(status="prolong_wait", expires="2026-10-17T15:00:00.000Z")])
        s = c.services[0]
        self.assertEqual(c.expectedLoss, round(s.risk * s.revenue))
        self.assertGreater(c.expectedLoss, 0)

    def test_client_who_never_paid_has_nothing_to_lose( self ):
        c = score_one([account(balance=0, replenished=0)], [service(status="prolong_wait", expires="2026-10-17T15:00:00.000Z")])
        self.assertEqual(c.level, "high")
        self.assertEqual(c.capacity, 0)
        self.assertEqual(c.expectedLoss, 0)

    def test_capacity_caps_hourly_revenue( self ):
        services = [service(term="hour", price=500, expires="2026-10-19T16:00:00.000Z")]
        capped = score_one([account(balance=100_000)], services)
        self.assertEqual(capped.revenueFull, 500 * 30 * 24)
        self.assertLess(capped.revenue, capped.revenueFull)
        self.assertEqual(capped.revenue, capped.capacity)
        raw = score_one([account(balance=100_000)], services, capRevenueByCapacity=False)
        self.assertEqual(raw.revenue, raw.revenueFull)

    def test_tie_in_score_is_broken_by_money( self ):
        snapshot = snapshot_of(
            [account(id=1, balance=0), account(id=2, balance=0)],
            [service(id=1, owner=1, status="prolong_wait", expires="2026-09-01T00:00:00.000Z", price=100),
             service(id=2, owner=2, status="prolong_wait", expires="2026-09-01T00:00:00.000Z", price=900)],
        )
        customers = evaluate(snapshot, { "referenceTime": NOW })
        self.assertEqual(customers[0].score, customers[1].score)
        self.assertEqual(customers[0].accountId, 2)

    def test_action_follows_main_reason( self ):
        remind = score_one([account()], [service(status="prolong_wait", expires="2026-10-18T15:00:00.000Z")])
        self.assertEqual(remind.action.code, "remind_payment")
        bonus = score_one([account(balance=0, bonus=5000)],
                          [service(status="prolong_wait", expires="2026-10-18T15:00:00.000Z")])
        self.assertEqual(bonus.action.code, "topup_nudge")
        auto = score_one([account()], [service(auto=False, expires="2026-10-21T15:00:00.000Z")])
        self.assertEqual(auto.action.code, "enable_autoprolong")


class NewFeatures( unittest.TestCase ):
    def test_new_customer_fades_and_ignores_future_dates( self ):
        c = score_one([account()], [service(created="2026-10-10T15:00:00.000Z")])
        reason = next(r for r in c.reasons if r.feature == "new_customer")
        self.assertAlmostEqual(reason.strength, 0.7)
        self.assertNotIn("new_customer", fired(score_one([account()], [service()])))
        future = service(created="2027-01-01T00:00:00.000Z", expires="2027-02-01T00:00:00.000Z")
        self.assertNotIn("new_customer", fired(score_one([account()], [future])))

    def test_first_renewal_only_in_first_period( self ):
        first = service(created="2026-09-21T15:00:00.000Z", expires="2026-10-21T15:00:00.000Z")
        c = score_one([account()], [first])
        reason = next(r for r in c.reasons if r.feature == "first_renewal")
        self.assertAlmostEqual(reason.strength, 1 - 2 / 7, places=2)
        self.assertEqual(c.action.code, "first_renewal_check")
        renewed = service(created="2026-08-21T15:00:00.000Z", expires="2026-10-21T15:00:00.000Z")
        self.assertNotIn("first_renewal", fired(score_one([account()], [renewed])))
        far = service(created="2026-09-01T15:00:00.000Z", expires="2026-10-01T15:00:00.000Z", status="prolong_wait")
        self.assertNotIn("first_renewal", fired(score_one([account()], [far])))
        hourly = service(term="hour", created="2026-10-19T14:30:00.000Z", expires="2026-10-19T15:30:00.000Z")
        self.assertNotIn("first_renewal", fired(score_one([account()], [hourly])))

    def test_recent_expansion_softens_old_client( self ):
        old = service(id=1)
        fresh = service(id=2, created="2026-10-10T15:00:00.000Z", expires="2026-11-10T15:00:00.000Z")
        risky = [tx(1, 1), tx(2, 1, performed=False)]
        off = { "recent_expansion": 0, "long_tenure_autoprolong": 0 }
        plain = score_one([account()], [old, fresh], risky, weights=off)
        soft = score_one([account()], [old, fresh], risky, weights={ "long_tenure_autoprolong": 0 })
        reason = next(r for r in soft.reasons if r.feature == "recent_expansion")
        self.assertEqual(reason.kind, "protective")
        self.assertIn("service-2", reason.text)
        self.assertAlmostEqual(soft.score, round(plain.score * 0.7, 1), delta=0.1)
        young = service(id=1, created="2026-10-01T15:00:00.000Z")
        self.assertNotIn("recent_expansion", fired(score_one([account()], [young, fresh], risky)))
        hourly = service(id=2, term="hour", created="2026-10-10T15:00:00.000Z", expires="2026-10-19T16:00:00.000Z")
        self.assertNotIn("recent_expansion", fired(score_one([account()], [old, hourly], risky)))
        dropped = service(id=2, status="deleted", created="2026-10-10T15:00:00.000Z", expires="2026-11-10T15:00:00.000Z")
        self.assertNotIn("recent_expansion", fired(score_one([account()], [old, dropped], risky)))

    def test_new_server_next_to_waiting_one_is_migration( self ):
        waiting = service(id=1, status="prolong_wait", expires="2026-10-18T15:00:00.000Z")
        fresh = service(id=2, created="2026-10-10T15:00:00.000Z", expires="2026-11-10T15:00:00.000Z")
        c = score_one([account()], [waiting, fresh])
        byId = { s.serviceId: { r.feature for r in s.reasons } for s in c.services }
        self.assertNotIn("recent_expansion", byId[1])

    def test_protective_lowers_risk_only_for_active( self ):
        risky = [tx(1, 1), tx(2, 1, performed=False)]
        plain = score_one([account()], [service()], risky, weights={ "long_tenure_autoprolong": 0 })
        guarded = score_one([account()], [service()], risky)
        self.assertLess(guarded.score, plain.score)
        self.assertAlmostEqual(guarded.score, round(plain.score * 0.7, 1), delta=0.1)
        reason = next(r for r in guarded.reasons if r.feature == "long_tenure_autoprolong")
        self.assertEqual(reason.kind, "protective")
        self.assertEqual(guarded.action.code, "check_payment")
        waiting = score_one([account()], [service(status="prolong_wait", expires="2026-10-18T15:00:00.000Z")])
        self.assertNotIn("long_tenure_autoprolong", fired(waiting))
        poor = score_one([account(balance=600)], [service()], risky)
        self.assertNotIn("long_tenure_autoprolong", fired(poor))

    def test_late_payer_habit_softens_waiting( self ):
        waiting = [service(status="prolong_wait", expires="2026-10-17T15:00:00.000Z")]
        late = [tx(1, 1, created="2026-07-03T00:00:00.000Z"), tx(2, 1, created="2026-08-03T00:00:00.000Z"),
                tx(3, 1, created="2026-09-02T12:00:00.000Z")]
        plain = score_one([account()], waiting, late, weights={ "pays_late_but_pays": 0 })
        soft = score_one([account()], waiting, late)
        reason = next(r for r in soft.reasons if r.feature == "pays_late_but_pays")
        self.assertEqual(reason.kind, "protective")
        self.assertEqual(reason.strength, 1.0)
        self.assertAlmostEqual(soft.score, round(plain.score * 0.7, 1), delta=0.1)
        self.assertEqual(soft.action.code, "remind_payment")

    def test_late_payer_habit_ignores_early_and_auto_payments( self ):
        waiting = [service(status="prolong_wait", expires="2026-10-17T15:00:00.000Z")]
        early = [tx(1, 1, created="2026-06-20T00:00:00.000Z"), tx(2, 1, created="2026-07-20T00:00:00.000Z")]
        self.assertNotIn("pays_late_but_pays", fired(score_one([account()], waiting, early)))
        auto = [tx(1, 1, created="2026-07-01T00:00:00.000Z"), tx(2, 1, created="2026-08-01T00:00:00.000Z")]
        self.assertNotIn("pays_late_but_pays", fired(score_one([account()], waiting, auto)))
        single = [tx(1, 1, created="2026-07-03T00:00:00.000Z")]
        self.assertNotIn("pays_late_but_pays", fired(score_one([account()], waiting, single)))
        calm = score_one([account()], [service()], [tx(1, 1, created="2026-07-03T00:00:00.000Z"), tx(2, 1, created="2026-08-03T00:00:00.000Z")])
        self.assertNotIn("pays_late_but_pays", fired(calm))

    def test_lateness_for_hourly_and_weekly_terms( self ):
        from datetime import timedelta
        from backend.models import parsetime
        from backend.risk.features import lateness
        hourly = Snapshot.format_dict({ "accounts": [account()], "services": [service(term="hour")], "transactions": [] }).services[0]
        self.assertEqual(lateness(parsetime("2026-01-01T05:10:00Z"), hourly), timedelta(minutes=10))
        self.assertEqual(lateness(parsetime("2026-01-01T04:50:00Z"), hourly), -timedelta(minutes=10))
        weekly = Snapshot.format_dict({ "accounts": [account()], "services": [service(term="week")], "transactions": [] }).services[0]
        self.assertEqual(lateness(parsetime("2026-01-10T00:00:00Z"), weekly), timedelta(days=2))

    def test_reliable_manual_renewer_softens_expiry( self ):
        expiring = [service(auto=False, expires="2026-10-21T15:00:00.000Z")]
        onTime = [tx(1, 1, created="2026-07-01T00:00:00.000Z"), tx(2, 1, created="2026-08-01T00:00:00.000Z"),
                  tx(3, 1, created="2026-09-01T00:00:00.000Z")]
        plain = score_one([account()], expiring, onTime, weights={ "reliable_manual_renewer": 0 })
        soft = score_one([account()], expiring, onTime)
        reason = next(r for r in soft.reasons if r.feature == "reliable_manual_renewer")
        self.assertEqual(reason.kind, "protective")
        self.assertEqual(reason.strength, 0.5)
        self.assertAlmostEqual(soft.score, plain.score * 0.85, delta=0.15)
        self.assertEqual(soft.action.code, "enable_autoprolong")
        failed = onTime + [tx(4, 1, performed=False, created="2026-10-01T00:00:00.000Z")]
        self.assertNotIn("reliable_manual_renewer", fired(score_one([account()], expiring, failed)))
        self.assertNotIn("reliable_manual_renewer", fired(score_one([account()], expiring, onTime[:2])))
        late = [tx(1, 1, created="2026-07-03T00:00:00.000Z"), tx(2, 1, created="2026-08-03T00:00:00.000Z"),
                tx(3, 1, created="2026-09-03T00:00:00.000Z")]
        self.assertNotIn("reliable_manual_renewer", fired(score_one([account()], expiring, late)))
        calm = [service(auto=False, expires="2027-10-19T15:00:00.000Z")]
        self.assertNotIn("reliable_manual_renewer", fired(score_one([account()], calm, onTime)))

    def test_protective_hidden_without_risk( self ):
        c = score_one([account()], [service()], [tx(1, 1)])
        self.assertEqual(c.score, 0)
        self.assertEqual(c.reasons, [])


class Chart( unittest.TestCase ):
    def test_forecast_never_lands_in_the_past( self ):
        snapshot = snapshot_of([account(balance=0)], [
            service(id=1, status="prolong_wait", expires="2025-09-14T16:00:00.000Z", created="2025-09-14T15:00:00.000Z"),
            service(id=2, status="deleted", expires="2025-10-14T16:00:00.000Z", created="2025-09-14T15:00:00.000Z"),
        ])
        settings = { "referenceTime": NOW }
        chart = timeline(evaluate(snapshot, settings), snapshot, settings)
        self.assertEqual(chart.referenceDate, "2026-10-19")
        self.assertEqual(chart.bucket, "week")
        ref = date.fromisoformat(chart.referenceDate)
        ref_bucket = ref - timedelta(days=ref.weekday())
        for p in chart.points:
            if p.expectedNonrenewals > 0 or p.servicesAtRisk > 0:
                self.assertGreaterEqual(date.fromisoformat(p.date), ref_bucket)
        self.assertEqual(sum(p.deleted for p in chart.points), 1)
        self.assertEqual(sum(p.servicesAtRisk for p in chart.points), 1)

    def test_observed_deletion_date_wins( self ):
        snapshot = snapshot_of([account()], [service(id=2, status="deleted", expires="2025-10-14T16:00:00.000Z",
                                                     created="2025-09-14T15:00:00.000Z")])
        settings = { "referenceTime": NOW }
        from backend.models import parsetime
        observed = { 2: parsetime("2026-10-10T12:00:00.000Z") }
        chart = timeline(evaluate(snapshot, settings), snapshot, settings, observed)
        point = next(p for p in chart.points if p.deleted)
        self.assertEqual(point.deletedObserved, 1)
        self.assertEqual(chart.bucket, "day")
        self.assertEqual(point.date, "2026-10-10")

    def test_chart_depends_on_weights( self ):
        snapshot = snapshot_of([account(balance=0)],
                               [service(status="prolong_wait", expires="2026-10-18T15:00:00.000Z")])
        base = { "referenceTime": NOW }
        off = { "referenceTime": NOW, "weights": { "prolong_wait": 0, "insufficient_funds": 0 } }
        with_risk = timeline(evaluate(snapshot, base), snapshot, base)
        without = timeline(evaluate(snapshot, off), snapshot, off)
        self.assertGreater(sum(p.expectedNonrenewals for p in with_risk.points), 0)
        self.assertEqual(sum(p.expectedNonrenewals for p in without.points), 0)


class Settings( unittest.TestCase ):
    def test_defaults_cover_every_feature( self ):
        self.assertEqual(set(default_settings()["weights"]), set(FEATURES))

    def test_patch_merges_weights( self ):
        s = merge_settings({ "weights": { "suspended": 0.5 } })
        self.assertEqual(s["weights"]["suspended"], 0.5)
        self.assertEqual(s["weights"]["prolong_wait"], FEATURES["prolong_wait"].baseWeight)

    def test_rejects_bad_values( self ):
        for patch in ( { "weights": { "nope": 0.1 } }, { "weights": { "suspended": 2 } },
                       { "highThreshold": 10, "mediumThreshold": 50 }, { "unknown": 1 },
                       { "referenceTime": "garbage" }, { "referenceTime": 42 },
                       { "paymentLookbackDays": 0 }, { "capRevenueByCapacity": "yes" },
                       { "newCustomerDays": 0 }, { "bigSpenderThreshold": -1 } ):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                merge_settings(patch)

    def test_reference_time_formats( self ):
        for value in ( None, "now", "2026-10-19T15:00:00Z", "2026-10-19T15:00:00+03:00", "2026-10-19" ):
            with self.subTest(value=value):
                self.assertEqual(merge_settings({ "referenceTime": value })["referenceTime"], value)


class Dataset( unittest.TestCase ):
    def test_scores_whole_dataset( self ):
        snapshot = Snapshot.format_dict(json.loads(DATA.read_text(encoding="utf-8")))
        customers = evaluate(snapshot)
        summary = summarize(customers, snapshot)
        self.assertEqual(summary.customersTotal, len(snapshot.accounts))
        self.assertEqual(sum(summary.customersByLevel.values()), len(snapshot.accounts))
        for c in customers:
            if c.score is not None:
                self.assertTrue(0 <= c.score <= 100)
        attributed = sum(f.expectedLoss for f in summary.features)
        self.assertAlmostEqual(attributed, summary.expectedLossTotal, delta=len(snapshot.services))
        self.assertEqual(sum(summary.expectedLossByTerm.values()), summary.expectedLossTotal)
        self.assertLessEqual(summary.revenueTotal, summary.revenueFullTotal)
        chart = timeline(customers, snapshot)
        self.assertTrue(chart.points)


if __name__ == "__main__":
    unittest.main()
