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

    def test_openai_llm_metrics_report_shared_cluster_role(self):
        response = {"data": [{"id": "deepseek-v4-flash"}]}
        with mock.patch.object(nodes, "_fetch_json", return_value=response):
            metrics = nodes._llm_workload_metrics("http://pair-a:8888", "openai", "worker")
        self.assertTrue(metrics["llmReady"])
        self.assertEqual(metrics["llmModels"], ["deepseek-v4-flash"])
        self.assertEqual(metrics["llmRole"], "worker")

    def test_ollama_llm_metrics_report_loaded_model_memory(self):
        response = {"models": [{"name": "qwen3.6:35b-a3b", "size_vram": 24 * 1024**3}]}
        with mock.patch.object(nodes, "_fetch_json", return_value=response):
            metrics = nodes._llm_workload_metrics("http://spark:11434", "ollama")
        self.assertTrue(metrics["llmReady"])
        self.assertEqual(metrics["llmModels"], ["qwen3.6:35b-a3b"])
        self.assertEqual(metrics["llmMemUsedMB"], 24 * 1024)

    def test_llm_probe_marks_pair_worker_as_serving_shared_model(self):
        node = {
            "id": "pair-b",
            "baseURL": "http://pair-b:8189",
            "sshHost": "pair-b",
            "llmURL": "http://pair-a:8888",
            "llmKind": "openai",
            "llmRole": "worker",
            "gpuUtilReliable": False,
        }
        with (
            mock.patch.object(nodes, "_run", return_value=(0, "ok")),
            mock.patch.object(nodes, "_http_models", return_value=(False, [], None)),
            mock.patch.object(nodes, "_ssh_metrics", return_value={"memUsedMB": 1000}),
            mock.patch.object(
                nodes,
                "_llm_workload_metrics",
                return_value={"llmReady": True, "llmModels": ["deepseek-v4-flash"], "llmRole": "worker"},
            ),
            mock.patch.object(nodes, "_vllm_metrics", return_value={}),
        ):
            result = nodes._probe_vllm_ssh(node)
        self.assertTrue(result["inferenceOK"])
        self.assertEqual(result["models"], ["deepseek-v4-flash"])


if __name__ == "__main__":
    unittest.main()
