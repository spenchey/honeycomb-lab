#!/usr/bin/env python3
"""Regression tests for Honeycomb's safe routing and control-plane primitives."""

import importlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tempdir.name) / "config.json"
        self.config_path.write_text(json.dumps({"backends": {}, "api_tokens": {}}))
        os.environ["HONEYCOMB_GATEWAY_CONFIG"] = str(self.config_path)
        gateway_dir = str(Path(__file__).resolve().parent)
        sys.path.insert(0, gateway_dir)
        sys.modules.pop("server", None)
        self.server = importlib.import_module("server")
        self.server.EVENTS_PATH = Path(self.tempdir.name) / "events.jsonl"
        self.server.AUDIT_PATH = Path(self.tempdir.name) / "audit.jsonl"
        self.server.STATS_PATH = Path(self.tempdir.name) / "stats.json"
        self.server._stats_last_write = time.time()

    def tearDown(self):
        os.environ.pop("HONEYCOMB_TEST_PROVIDER_TOKEN", None)
        sys.modules.pop("server", None)
        self.tempdir.cleanup()

    def test_upstream_headers_only_accept_environment_references(self):
        os.environ["HONEYCOMB_TEST_PROVIDER_TOKEN"] = "provider-secret"
        self.assertEqual(
            self.server.upstream_headers({"headers": {"Authorization": "env:HONEYCOMB_TEST_PROVIDER_TOKEN"}}),
            {"Authorization": "provider-secret"},
        )
        self.assertEqual(self.server.upstream_headers({"headers": {"Authorization": "literal-secret"}}), {})
        self.assertFalse(self.server.backend_auth_ready({"headers": {"Authorization": "env:MISSING_TOKEN"}}))

    def test_health_probe_uses_the_configured_environment_header(self):
        os.environ["HONEYCOMB_TEST_PROVIDER_TOKEN"] = "provider-secret"
        with mock.patch.object(
            self.server, "http_json", return_value=(200, {}, b'{"data":[{"id":"cloud-model"}]}')
        ) as http:
            healthy, models, _ = self.server.backend_healthy({
                "base_url": "https://provider.invalid/v1",
                "headers": {"Authorization": "env:HONEYCOMB_TEST_PROVIDER_TOKEN"},
            })
        self.assertTrue(healthy)
        self.assertEqual(models, ["cloud-model"])
        self.assertEqual(http.call_args.kwargs["headers"], {"Authorization": "provider-secret"})

    def test_backend_alert_requires_repeated_failures_over_grace_period(self):
        with mock.patch.object(self.server.time, "time", side_effect=[100.0, 115.0, 131.0]):
            self.server._store_probe_result("cloud", (False, [], None))
            self.server._store_probe_result("cloud", (False, [], None))
            self.assertFalse(self.server._backend_probe_alert_ready("cloud", 130.0))
            self.server._store_probe_result("cloud", (False, [], None))
        self.assertTrue(self.server._backend_probe_alert_ready("cloud", 131.0))

    def test_backend_recovery_notifies_once_and_resets_incident(self):
        self.server._backend_probe_state["cloud"] = {
            "consecutive_failures": 3,
            "first_failure_at": 100.0,
            "alerted": True,
        }
        self.server._alert_state["backend-down:cloud"] = 130.0
        with mock.patch.object(self.server, "_dispatch_alert") as dispatch:
            self.server._store_probe_result("cloud", (True, ["cloud-model"], 25.0))
            self.server._store_probe_result("cloud", (True, ["cloud-model"], 20.0))
        dispatch.assert_called_once()
        self.assertEqual(dispatch.call_args.args[0]["severity"], "recovered")
        self.assertNotIn("backend-down:cloud", self.server._alert_state)
        self.assertFalse(self.server._backend_probe_alert_ready("cloud", 200.0))

    def test_history_keeps_request_metadata_not_prompt_content(self):
        self.server.record_request("dev-local", "spark", "qwen", False, 200, 12.0, 10, 2, "dev", "Spark")
        history = self.server.history_snapshot(since=time.time() - 10)
        self.assertEqual(len(history["events"]), 1)
        self.assertEqual(history["events"][0]["agent"], "dev")
        self.assertNotIn("messages", history["events"][0])
        self.assertEqual(history["summary"]["dev | qwen | Spark"]["completion_tokens"], 2)

    def test_profile_requires_configured_command_and_smoke_test(self):
        nodes = self.server.fleet_nodes
        with nodes._lock:
            nodes._fleet = {"title": "test", "links": [], "nodes": [{
                "id": "spark", "sshHost": "test-host", "modelProfiles": {
                    "safe": {"activateCommand": "activate", "verifyCommand": "verify", "rollbackCommand": "rollback", "autoRollback": True}
                }
            }]}
        with mock.patch.object(nodes, "_run", side_effect=[(0, "started"), (1, "not ready"), (0, "rolled back")]) as run:
            result = nodes.action_profile("spark", "safe")
        self.assertFalse(result["ok"])
        self.assertTrue(result["rolledBack"])
        self.assertEqual(run.call_count, 3)


if __name__ == "__main__":
    unittest.main()
