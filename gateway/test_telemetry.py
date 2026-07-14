#!/usr/bin/env python3
"""Focused regression tests for Honeycomb's accounted-usage dimensions."""

import importlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        config_path = Path(self.tempdir.name) / "config.json"
        config_path.write_text(json.dumps({"backends": {}, "api_tokens": {}}))
        os.environ["HONEYCOMB_GATEWAY_CONFIG"] = str(config_path)
        gateway_dir = str(Path(__file__).resolve().parent)
        sys.path.insert(0, gateway_dir)
        sys.modules.pop("server", None)
        self.server = importlib.import_module("server")
        self.server.STATS_PATH = Path(self.tempdir.name) / "stats.json"
        self.server._stats_last_write = time.time()
        self.server._stats = {
            "by_agent": {},
            "by_alias": {},
            "by_model": {},
            "by_device": {},
            "by_agent_model_device": {},
        }

    def tearDown(self):
        sys.modules.pop("server", None)
        self.tempdir.cleanup()

    def test_records_combined_agent_model_device_usage(self):
        self.server.record_request(
            "deepseek-reasoning",
            "deepseek-studio",
            "deepseek-v4-flash",
            False,
            200,
            25.0,
            120,
            30,
            "rory",
            "Mac Studio",
        )

        snapshot = self.server.stats_snapshot()
        route = snapshot["by_agent_model_device"]["rory | deepseek-v4-flash | Mac Studio"]
        self.assertEqual(route["requests"], 1)
        self.assertEqual(route["prompt_tokens"], 120)
        self.assertEqual(route["completion_tokens"], 30)
        self.assertEqual(snapshot["by_agent"]["rory"]["prompt_tokens"], 120)


if __name__ == "__main__":
    unittest.main()
