import importlib.util
import json
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "cloudflare/prepare.py"
spec = importlib.util.spec_from_file_location("cloudflare_prepare", MODULE)
assert spec and spec.loader
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)

API = "https://api.example.onrender.com"
SITE = "https://constitution.ng"


def configure(**overrides):
    options = {"public": False, "site_url": SITE, "api_origin": API} | overrides
    return prepare.configuration(**options)


class CloudflarePreparationTests(unittest.TestCase):
    def test_pending_launch_has_no_public_or_version_urls(self):
        config = configure()
        self.assertFalse(config["workers_dev"])
        self.assertFalse(config["preview_urls"])
        self.assertEqual(config["name"], "constitution-ng")
        self.assertEqual(config["main"], "cloudflare/worker.ts")
        self.assertEqual(config["assets"]["directory"], "../backend/app/frontend")

    def test_public_launch_keeps_version_urls_disabled(self):
        config = configure(public=True)
        self.assertTrue(config["workers_dev"])
        self.assertFalse(config["preview_urls"])

    def test_canonical_origin_and_document_routing_are_explicit(self):
        config = configure(public=True)
        self.assertEqual(config["vars"]["PUBLIC_SITE_URL"], SITE)
        self.assertTrue(config["assets"]["run_worker_first"])
        self.assertEqual(config["assets"]["not_found_handling"], "none")
        for site in (
            "http://constitution.ng",
            "https://constitution.ng/path",
            "https://user:password@constitution.ng",
            "https://constitution.ng?token=x",
        ):
            with self.subTest(site=site), self.assertRaises(ValueError):
                configure(public=True, site_url=site)

    def test_api_origin_is_taken_from_the_operator(self):
        self.assertEqual(configure()["vars"]["API_ORIGIN"], API)
        self.assertEqual(
            configure(api_origin=API + "/")["vars"]["API_ORIGIN"],
            API,
        )

    def test_unsafe_api_origins_are_rejected(self):
        for origin in (
            "",
            "http://api.example.onrender.com",
            "https://user:secret@api.example.onrender.com",
            "https://:secret@api.example.onrender.com",
            "https://api.example.onrender.com:8443",
            "https://api.example.onrender.com/api",
            "https://api.example.onrender.com?x=1",
            "https://api.example.onrender.com#frag",
            "https://api.example.com",
            "https://onrender.com.evil.example",
            "api.example.onrender.com",
        ):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                configure(api_origin=origin)

    def test_the_template_carries_no_deployment_identifiers(self):
        template = json.loads((MODULE.parent / "wrangler.json").read_text())
        self.assertNotIn("vars", template)

    def test_legacy_name_can_be_selected_for_existing_deployment(self):
        config = configure(public=True, worker_name="constitition-ng")
        self.assertEqual(config["name"], "constitition-ng")


if __name__ == "__main__":
    unittest.main()
