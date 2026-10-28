import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import social_logins
from bootstrap import APIError


class SocialLoginTests(unittest.TestCase):
    def setUp(self):
        self.providers = {}
        self.writes = []
        self.accounts = {
            alias: {"client-id": f"{alias}-id", "client-secret": f"{alias}-secret"}
            for alias in social_logins.PROVIDERS
        }
        self.api = Mock()
        self.api.request.side_effect = self.request
        self.authentication = patch("social_logins.authenticate", return_value="operator-token")
        self.authentication.start()
        self.addCleanup(self.authentication.stop)

    def request(self, method, path, token=None, payload=None):
        alias = path.rsplit("/", 1)[-1]
        if method == "GET":
            if alias not in self.providers:
                raise APIError(404)
            result = copy.deepcopy(self.providers[alias])
            result["config"]["clientSecret"] = "**********"
            return result
        self.writes.append((method, path, copy.deepcopy(payload)))
        self.providers[payload["alias"]] = copy.deepcopy(payload)

    def reconcile(self):
        social_logins.reconcile(self.api, {"client-id": "operator"}, self.accounts)

    def test_creates_only_google_and_facebook_with_safe_defaults(self):
        self.reconcile()
        self.assertEqual(set(self.providers), {"google", "facebook"})
        self.assertEqual([method for method, _, _ in self.writes], ["POST", "POST"])
        for alias, provider in self.providers.items():
            self.assertEqual(provider["providerId"], alias)
            self.assertTrue(provider["enabled"])
            self.assertFalse(provider["hideOnLogin"])
            self.assertFalse(provider["trustEmail"])
            self.assertFalse(provider["storeToken"])
            self.assertFalse(provider["linkOnly"])
            self.assertEqual(provider["firstBrokerLoginFlowAlias"], "first broker login")
            self.assertEqual(provider["config"]["clientId"], self.accounts[alias]["client-id"])
            self.assertEqual(provider["config"]["clientSecret"], self.accounts[alias]["client-secret"])

    def test_repeat_runs_update_same_aliases_preserve_settings_and_rotate_secrets(self):
        self.reconcile()
        self.providers["google"]["config"]["hostedDomain"] = "example.invalid"
        self.providers["google"]["internalId"] = "original-id"
        self.providers["unrelated"] = {"config": {"clientSecret": "unmanaged"}}
        self.writes.clear()
        self.accounts["google"]["client-secret"] = "rotated-secret"
        self.reconcile()
        self.assertEqual([method for method, _, _ in self.writes], ["PUT", "PUT"])
        self.assertEqual(self.providers["google"]["internalId"], "original-id")
        self.assertEqual(self.providers["google"]["config"]["hostedDomain"], "example.invalid")
        self.assertEqual(self.providers["google"]["config"]["clientSecret"], "rotated-secret")
        self.assertEqual(self.providers["unrelated"], {"config": {"clientSecret": "unmanaged"}})

    def test_non_404_errors_do_not_create_providers(self):
        for status in (401, 403, 429, 500, 503):
            with self.subTest(status=status):
                self.api.request.side_effect = APIError(status)
                with self.assertRaises(APIError):
                    self.reconcile()
        self.assertEqual(self.writes, [])

    def test_alias_collision_fails_without_overwriting(self):
        self.providers["google"] = {"providerId": "oidc", "config": {}}
        with self.assertRaises(RuntimeError):
            self.reconcile()
        self.assertEqual(self.writes, [])

    @patch("social_logins.authenticate", return_value=None)
    def test_authentication_failure_does_not_modify_providers(self, authenticate):
        with self.assertRaises(RuntimeError):
            self.reconcile()
        self.api.request.assert_not_called()

    def test_readback_mismatch_is_reported(self):
        original = self.request

        def incorrect(method, path, token=None, payload=None):
            result = original(method, path, token, payload)
            if method == "GET":
                result["enabled"] = False
            return result

        self.api.request.side_effect = incorrect
        with self.assertRaises(RuntimeError):
            self.reconcile()

    def test_empty_or_missing_credentials_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for alias in social_logins.PROVIDERS:
                for field in ("client-id", "client-secret"):
                    (Path(directory) / f"{alias}-{field}").write_text("value")
            (Path(directory) / "facebook-client-secret").write_text("  \n")
            with self.assertRaises(RuntimeError):
                social_logins.provider_credentials(directory)
            (Path(directory) / "facebook-client-secret").unlink()
            with self.assertRaises(OSError):
                social_logins.provider_credentials(directory)

    @patch("social_logins.credentials", side_effect=RuntimeError("sensitive-value"))
    @patch("builtins.print")
    def test_errors_do_not_log_sensitive_details(self, output, credentials):
        self.assertEqual(social_logins.main(), 1)
        self.assertNotIn("sensitive-value", str(output.call_args_list))


if __name__ == "__main__":
    unittest.main()
