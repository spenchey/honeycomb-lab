#!/usr/bin/env python3
"""Regression tests for workload-aware Honeycomb node metrics."""

import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent))
import nodes  # noqa: E402


class NodeMetricsTests(unittest.TestCase):
    def test_unreliable_gpu_sample_can_be_suppressed(self):
        output = "MEM 12000 128000\nCPU 12.5\nGPU 0\n"
        with mock.patch.object(nodes, "_run", return_value=(0, output)):
            metrics = nodes._ssh_metrics("spark-test", include_gpu_util=False)
        self.assertEqual(metrics["memUsedMB"], 12000)
        self.assertEqual(metrics["cpuUtilPct"], 12.5)
        self.assertNotIn("gpuUtilPct", metrics)

    def test_comfy_metrics_report_running_jobs_and_unified_gpu_memory(self):
        responses = [
            {"queue_running": [[0, "job-1"]], "queue_pending": [[1, "job-2"]]},
            {"devices": [{"vram_total": 128 * 1024**3, "vram_free": 40 * 1024**3}]},
        ]
        with mock.patch.object(nodes, "_fetch_json", side_effect=responses):
            metrics = nodes._comfy_metrics("http://spark-test:8189")
        self.assertEqual(metrics["runningJobs"], 1)
        self.assertEqual(metrics["queuedJobs"], 1)
        self.assertEqual(metrics["gpuMemUsedMB"], 88 * 1024)
        self.assertEqual(metrics["gpuMemTotalMB"], 128 * 1024)


if __name__ == "__main__":
    unittest.main()
