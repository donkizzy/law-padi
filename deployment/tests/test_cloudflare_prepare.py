import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "cloudflare/prepare.py"
spec = importlib.util.spec_from_file_location("cloudflare_prepare", MODULE)
assert spec and spec.loader
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class CloudflarePreparationTests(unittest.TestCase):
    def test_pending_launch_has_no_public_or_version_urls(self):
        config = prepare.configuration(prepare.API_ORIGIN, public=False)
        self.assertFalse(config["workers_dev"])
        self.assertFalse(config["preview_urls"])
        self.assertEqual(config["name"], "constitition-ng")
        self.assertEqual(config["vars"]["API_ORIGIN"], prepare.API_ORIGIN)
        self.assertEqual(config["main"], "cloudflare/worker.ts")
        self.assertEqual(config["assets"]["directory"], "../backend/app/frontend")

    def test_public_launch_keeps_version_urls_disabled(self):
        config = prepare.configuration(prepare.API_ORIGIN, public=True)
        self.assertTrue(config["workers_dev"])
        self.assertFalse(config["preview_urls"])

    def test_canonical_origin_and_document_routing_are_explicit(self):
        config = prepare.configuration(
            prepare.API_ORIGIN, public=True, site_url="https://constitution.ng"
        )
        self.assertEqual(config["vars"]["PUBLIC_SITE_URL"], "https://constitution.ng")
        self.assertTrue(config["assets"]["run_worker_first"])
        self.assertEqual(config["assets"]["not_found_handling"], "none")
        for site in (
            "http://constitution.ng",
            "https://constitution.ng/path",
            "https://user:password@constitution.ng",
            "https://constitution.ng?token=x",
        ):
            with self.subTest(site=site), self.assertRaises(ValueError):
                prepare.configuration(prepare.API_ORIGIN, public=True, site_url=site)

    def test_rejects_accidental_or_credential_bearing_origins(self):
        for origin in (
            "http://constitution-ng-api.onrender.com",
            "https://other-app.onrender.com",
            "https://constitution-ng-api.onrender.com.evil.example",
            "https://user:password@constitution-ng-api.onrender.com",
            "https://constitution-ng-api.onrender.com:443",
            "https://constitution-ng-api.onrender.com/api",
            "https://constitution-ng-api.onrender.com?token=secret",
        ):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                prepare.configuration(origin, public=False)


if __name__ == "__main__":
    unittest.main()
