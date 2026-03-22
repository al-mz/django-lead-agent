from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from leads.models import RoutingRule


class ApplyRoutingRulesTests(TestCase):
    def setUp(self):
        RoutingRule.objects.create(name="hot",  score_min=0.75, score_max=1.0,  queue_name="senior-sales", response_sla_minutes=15,   is_active=True)
        RoutingRule.objects.create(name="warm", score_min=0.40, score_max=0.74, queue_name="sales-team",   response_sla_minutes=120,  is_active=True)
        RoutingRule.objects.create(name="cold", score_min=0.00, score_max=0.39, queue_name="nurture",      response_sla_minutes=1440, is_active=True)

    def test_hot_score_routes_to_senior_sales(self):
        from leads.tasks import _apply_routing_rules
        queue, deadline = _apply_routing_rules({"icp_score": 0.85})
        self.assertEqual(queue, "senior-sales")
        self.assertAlmostEqual((deadline - timezone.now()).seconds, 15 * 60, delta=5)

    def test_warm_score_routes_to_sales_team(self):
        from leads.tasks import _apply_routing_rules
        queue, deadline = _apply_routing_rules({"icp_score": 0.55})
        self.assertEqual(queue, "sales-team")

    def test_no_matching_rule_falls_back(self):
        RoutingRule.objects.all().update(is_active=False)
        from leads.tasks import _apply_routing_rules
        queue, deadline = _apply_routing_rules({"icp_score": 0.5, "routing_queue": "fallback-queue"})
        self.assertEqual(queue, "fallback-queue")
        self.assertAlmostEqual((deadline - timezone.now()).seconds, 24 * 3600, delta=10)
