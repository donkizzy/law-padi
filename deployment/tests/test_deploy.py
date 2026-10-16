import copy
import gzip
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "deploy.py"
spec = importlib.util.spec_from_file_location("deployment_script", MODULE)
assert spec and spec.loader
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((MODULE.parent / "project.example.json").read_text())

    def test_safe_runtime_limits_and_generation_flags(self):
        api = deploy.runtime_env(
            self.config, "api", handler_url="https://tasks.run.app"
        )
        worker = deploy.runtime_env(
            self.config, "tasks", handler_url="https://tasks.run.app"
        )
        self.assertEqual(api["DATABASE_POOL_SIZE"], "5")
        self.assertEqual(worker["DATABASE_POOL_SIZE"], "2")
        self.assertEqual(worker["AI_MONTHLY_BUDGET_USD"], "5")
        self.assertEqual(worker["CHAT_MONTHLY_BUDGET_USD"], "4")
        self.assertEqual(api["EMBEDDING_QUERY_ENABLED"], "false")
        self.assertEqual(api["CHAT_GENERATION_ENABLED"], "false")
        self.assertEqual(api["CHAT_GENERATION_KILL_SWITCH"], "true")
        self.assertNotIn("FASTAPI_ENV", api)
        self.assertNotIn("DATABASE_URL", api)

    def test_image_size_counts_classic_and_oci_layer_bytes(self):
        for name, payload in (
            ("layer-id/layer.tar", b"uncompressed layer contents" * 100),
            ("blobs/sha256/layer", gzip.compress(b"OCI layer contents" * 100)),
        ):
            with self.subTest(format=name):
                archive = io.BytesIO()
                with tarfile.open(fileobj=archive, mode="w") as saved:
                    metadata = tarfile.TarInfo("manifest.json")
                    metadata.size = 2
                    saved.addfile(metadata, io.BytesIO(b"[]"))
                    layer = tarfile.TarInfo(name)
                    layer.size = len(payload)
                    saved.addfile(layer, io.BytesIO(payload))
                archive.seek(0)
                expected = (
                    len(gzip.decompress(payload))
                    if name.startswith("blobs/")
                    else len(payload)
                )
                self.assertEqual(deploy.uncompressed_layers(archive), expected)

    def test_image_size_refuses_an_archive_without_layers(self):
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w"):
            pass
        archive.seek(0)
        with self.assertRaisesRegex(ValueError, "uncompressed image layers"):
            deploy.uncompressed_layers(archive)

    def test_cloud_mutation_stops_without_spending_confirmation(self):
        with patch.object(deploy, "run") as execute:
            with self.assertRaisesRegex(ValueError, "billing alerts"):
                deploy.provision(self.config)
            execute.assert_not_called()

    def test_deploy_is_iam_private_with_pinned_secret_and_instance_limits(self):
        with patch.object(
            deploy, "run", return_value="https://tasks.run.app"
        ) as execute:
            deploy.deploy_service(
                self.config, "tasks", "abc123", handler_url="https://tasks.run.app"
            )
        command = execute.call_args_list[0].args[0]
        self.assertIn("--no-allow-unauthenticated", command)
        self.assertIn("--invoker-iam-check", command)
        self.assertIn("--max=1", command)
        self.assertIn("--min=0", command)
        self.assertIn("--concurrency=1", command)
        self.assertIn("--cpu-throttling", command)
        self.assertIn(
            "--set-secrets=/run/secrets/runtime.env=law-padi-worker-runtime:1", command
        )
        self.assertFalse(
            any("cloudsql" in item or "vpc-connector=" in item for item in command)
        )

    def test_validates_region_secret_pin_and_browser_origin(self):
        deploy.validate_config(self.config)
        for key, value in (
            ("region", "europe-west1"),
            ("api_secret_version", "latest"),
            ("frontend_url", "http://example.com"),
            ("frontend_url", "https://example.com/path"),
            ("frontend_url", "https://example.com,CHAT_GENERATION_ENABLED=true"),
            ("project_id", "project;danger"),
            ("cloudflare_account_id", "wrong-account"),
        ):
            invalid = copy.deepcopy(self.config)
            invalid[key] = value
            with self.assertRaises(ValueError):
                deploy.validate_config(invalid)

    def test_rejects_a_stale_prompt_capture_before_public_mutation(self):
        self.config["spending_safeguards_confirmed"] = True
        dataset = deploy.ROOT / "docs/constitution-explanation-evaluation-v1.json"
        cases = json.loads(dataset.read_text())["cases"]
        with tempfile.TemporaryDirectory() as directory:
            captures = Path(directory) / "captures.jsonl"
            judgments = Path(directory) / "judgments.jsonl"
            captures.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "id": case["id"],
                            "turns": [{"answer": {"prompt_version": "old-prompt"}}],
                        }
                    )
                    for case in cases
                )
            )
            judgments.write_text("{}\n")
            with patch.object(deploy, "run") as execute:
                with self.assertRaisesRegex(ValueError, "current prompt"):
                    deploy.release(
                        self.config, "abc123", dataset, captures, judgments, True
                    )
                execute.assert_not_called()

    def test_rejects_unconfirmed_provider_spend_before_public_mutation(self):
        self.config["spending_safeguards_confirmed"] = True
        with patch.object(deploy, "run") as execute:
            with self.assertRaisesRegex(ValueError, "prepaid"):
                deploy.release(
                    self.config,
                    "abc123",
                    Path("missing"),
                    Path("missing"),
                    Path("missing"),
                    False,
                )
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
