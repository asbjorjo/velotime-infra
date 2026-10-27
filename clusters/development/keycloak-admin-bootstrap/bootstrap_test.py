import unittest
from unittest.mock import Mock, patch

import bootstrap


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.temporary = {"client-id": "bootstrap", "client-secret": "temporary-value"}
        self.permanent = {"client-id": "operator", "client-secret": "permanent-value"}

    @patch("bootstrap.authenticate", return_value=None)
    @patch("bootstrap.verify_operator", return_value=True)
    def test_completed_bootstrap_is_idempotent(self, verify, authenticate):
        bootstrap.bootstrap(self.api, self.temporary, self.permanent)
        self.api.request.assert_not_called()

    @patch("bootstrap.authenticate", return_value=None)
    @patch("bootstrap.verify_operator", return_value=False)
    def test_missing_both_accounts_fails_closed(self, verify, authenticate):
        with self.assertRaises(RuntimeError):
            bootstrap.bootstrap(self.api, self.temporary, self.permanent)
        self.api.request.assert_not_called()

    def test_identical_accounts_are_rejected(self):
        with self.assertRaises(RuntimeError):
            bootstrap.bootstrap(self.api, self.permanent, self.permanent)
        self.api.request.assert_not_called()

    @patch("bootstrap.find_client", return_value={"id": "temporary-id"})
    @patch("bootstrap.authenticate", return_value="temporary-token")
    @patch("bootstrap.verify_operator", return_value=True)
    def test_partial_cleanup_is_retried_after_verification(self, verify, authenticate, find):
        bootstrap.bootstrap(self.api, self.temporary, self.permanent)
        self.assertEqual(verify.call_count, 2)
        self.api.request.assert_called_once_with(
            "DELETE", "/admin/realms/master/clients/temporary-id", "temporary-token",
        )

    @patch("bootstrap.find_client", side_effect=[None, {"id": "operator-id"}, {"id": "realm-id"}, {"id": "temporary-id"}])
    @patch("bootstrap.authenticate", return_value="temporary-token")
    @patch("bootstrap.verify_operator", side_effect=[False, True])
    def test_new_operator_is_created_verified_and_bootstrap_removed(self, verify, authenticate, find):
        self.api.request.return_value = {"id": "account-id"}
        bootstrap.bootstrap(self.api, self.temporary, self.permanent)
        calls = self.api.request.call_args_list
        self.assertEqual(calls[0].args, ("POST", "/admin/realms/master/clients", "temporary-token"))
        self.assertEqual(calls[0].kwargs["payload"]["clientId"], "operator")
        self.assertFalse(calls[0].kwargs["payload"]["standardFlowEnabled"])
        self.assertEqual(calls[-1].args, ("DELETE", "/admin/realms/master/clients/temporary-id", "temporary-token"))
        grants = [call for call in calls if "/role-mappings/" in call.args[1]]
        self.assertEqual(len(grants), 1)
        self.assertIn("/clients/realm-id", grants[0].args[1])

    @patch("bootstrap.find_client", side_effect=[{"id": "operator-id"}, {"id": "realm-id"}])
    @patch("bootstrap.authenticate", return_value="temporary-token")
    @patch("bootstrap.verify_operator", side_effect=[False, False])
    def test_failed_permanent_verification_retains_bootstrap_access(self, verify, authenticate, find):
        self.api.request.return_value = {"id": "account-id"}
        with self.assertRaises(RuntimeError):
            bootstrap.bootstrap(self.api, self.temporary, self.permanent)
        self.assertFalse(any(call.args[0] == "DELETE" for call in self.api.request.call_args_list))
        self.assertTrue(any(call.args[0] == "PUT" for call in self.api.request.call_args_list))

    def test_authentication_rejection_allows_bootstrap_fallback(self):
        self.api.request.side_effect = bootstrap.APIError(401)
        self.assertIsNone(bootstrap.authenticate(self.api, self.permanent))

    @patch("bootstrap.authenticate", return_value="operator-token")
    def test_verification_uses_the_versioned_client_endpoint(self, authenticate):
        self.assertTrue(bootstrap.verify_operator(self.api, self.permanent))
        self.api.request.assert_any_call(
            "GET", "/admin/api/velotime/clients/v2", "operator-token",
        )
        self.api.request.assert_any_call(
            "GET", "/admin/realms/velotime/identity-provider/instances", "operator-token",
        )
        self.assertIn("manage-identity-providers", bootstrap.OPERATOR_ROLES)

    def test_transient_authentication_failure_is_not_treated_as_missing_account(self):
        self.api.request.side_effect = bootstrap.APIError(503)
        with self.assertRaises(bootstrap.APIError):
            bootstrap.authenticate(self.api, self.permanent)

    @patch("bootstrap.credentials", side_effect=RuntimeError("sensitive-value"))
    @patch("builtins.print")
    def test_errors_do_not_log_sensitive_details(self, output, credentials):
        self.assertEqual(bootstrap.main(), 1)
        self.assertNotIn("sensitive-value", str(output.call_args_list))


if __name__ == "__main__":
    unittest.main()