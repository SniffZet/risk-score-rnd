# python -m unittest discover -s backend/tests -t . -v

import json
import unittest
from pathlib import Path

from backend.models import Snapshot
from backend.risk.defaults import default_settings, merge_settings
from backend.risk.features import FEATURES
from backend.risk.scoring import evaluate, summarize

NOW = "2026-10-19T15:00:00.000Z"
DATA = Path(__file__).resolve().parents[2] / "data" / "data.json"

def account( id=1, balance=100_000, bonus=0, bonusState="locked" ):
    return { "id": id, "email": f"user-{id}@example.test", "balance": balance, "withdrawBalance": 0,
             "totalReplenished": balance, "bonusBalance": bonus, "bonusState": bonusState }

def service( id=1, owner=1, status="active", term="month", auto=True,
             expires="2026-12-19T15:00:00.000Z", price=500 ):
    return { "id": id, "name": f"service-{id}", "ownerId": owner, "paymentTerm": term, "autoProlong": auto,
             "createdAt": "2026-01-01T00:00:00.000Z", "expiresAt": expires, "status": status, "price": price }

def tx( id, serviceId, performed=True ):
    return { "id": id, "amount": 100, "type": "prolong", "serviceId": serviceId,
             "status": "performed" if performed else "not_performed",
             "createdAt": "2026-09-01T00:00:00.000Z",
             "performedAt": "2026-09-01T00:01:00.000Z" if performed else None }

def score_one( accounts, services, transactions=(), **settings ):
    snapshot = Snapshot.format_dict({ "accounts": accounts, "services": services, "transactions": list(transactions) })
    return evaluate(snapshot, { "referenceTime": NOW, **settings })[0]

def fired( customer ):
    return { r.feature for r in customer.reasons }


class Scenarios( unittest.TestCase ):
    def test_healthy_client_is_low( self ):
        c = score_one([account()], [service()], [tx(1, 1)])
        self.assertEqual(c.level, "low")
        self.assertEqual(c.score, 0)
        self.assertEqual(c.reasons, [])

    def test_prolong_wait_without_money_is_high( self ):
        c = score_one([account(balance=0)], [service(status="prolong_wait", expires="2026-10-17T15:00:00.000Z")])
        self.assertEqual(c.level, "high")
        self.assertEqual(fired(c), { "prolong_wait", "insufficient_funds" })

    def test_prolong_wait_gets_stronger_to_deletion( self ):
        fresh = score_one([account()], [service(status="prolong_wait", expires="2026-10-19T09:00:00.000Z")])
        late = score_one([account()], [service(status="prolong_wait", expires="2026-10-15T15:00:00.000Z")])
        self.assertLess(fresh.score, late.score)

    def test_expiring_without_autoprolong_is_medium( self ):
        c = score_one([account()], [service(auto=False, expires="2026-10-21T15:00:00.000Z")])
        self.assertEqual(c.level, "medium")
        self.assertEqual(fired(c), { "expiring_without_autoprolong" })

    def test_far_expiry_without_autoprolong_is_ignored( self ):
        c = score_one([account()], [service(auto=False, expires="2027-10-19T15:00:00.000Z")])
        self.assertNotIn("expiring_without_autoprolong", fired(c))

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

    def test_churn_history_reason_shown_once( self ):
        c = score_one([account()], [service(id=1), service(id=2), service(id=3, status="deleted")])
        self.assertEqual(sum(1 for r in c.reasons if r.feature == "churn_history"), 1)

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


class Settings( unittest.TestCase ):
    def test_defaults_cover_every_feature( self ):
        self.assertEqual(set(default_settings()["weights"]), set(FEATURES))

    def test_patch_merges_weights( self ):
        s = merge_settings({ "weights": { "suspended": 0.5 } })
        self.assertEqual(s["weights"]["suspended"], 0.5)
        self.assertEqual(s["weights"]["prolong_wait"], FEATURES["prolong_wait"].baseWeight)

    def test_rejects_bad_values( self ):
        for patch in ( { "weights": { "nope": 0.1 } }, { "weights": { "suspended": 2 } },
                       { "highThreshold": 10, "mediumThreshold": 50 }, { "unknown": 1 } ):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                merge_settings(patch)


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


if __name__ == "__main__":
    unittest.main()
