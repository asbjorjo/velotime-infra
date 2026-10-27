import sys
from pathlib import Path
from urllib.error import URLError

from bootstrap import APIError, KeycloakAPI, REALM, authenticate, credentials


PROVIDERS = {
    "google": ("Google", "openid profile email"),
    "facebook": ("Facebook", "email"),
}
BASE_PATH = f"/admin/realms/{REALM}/identity-provider/instances"


def provider_credentials(directory):
    accounts = {
        alias: {
            field: (Path(directory) / f"{alias}-{field}").read_text().strip()
            for field in ("client-id", "client-secret")
        }
        for alias in PROVIDERS
    }
    if any(not value for account in accounts.values() for value in account.values()):
        raise RuntimeError("Social login credentials must not be empty")
    return accounts


def reconcile(api, operator, accounts):
    token = authenticate(api, operator)
    if token is None:
        raise RuntimeError("Permanent operator authentication failed")
    for alias, (display_name, scope) in PROVIDERS.items():
        path = f"{BASE_PATH}/{alias}"
        try:
            existing = api.request("GET", path, token)
        except APIError as error:
            if error.status != 404:
                raise
            existing = None
        if existing is not None and existing.get("providerId") != alias:
            raise RuntimeError("Social provider alias belongs to a different provider type")
        payload = dict(existing or {})
        payload.update({
            "alias": alias,
            "providerId": alias,
            "displayName": display_name,
            "enabled": True,
            "hideOnLogin": False,
            "trustEmail": False,
            "storeToken": False,
            "addReadTokenRoleOnCreate": False,
            "authenticateByDefault": False,
            "linkOnly": False,
            "firstBrokerLoginFlowAlias": "first broker login",
            "config": {
                **payload.get("config", {}),
                "clientId": accounts[alias]["client-id"],
                "clientSecret": accounts[alias]["client-secret"],
                "defaultScope": scope,
                "syncMode": "IMPORT",
            },
        })
        # Keycloak masks stored secrets on reads; always write the vault value for rotation.
        if existing is None:
            api.request("POST", BASE_PATH, token, payload=payload)
        else:
            api.request("PUT", path, token, payload=payload)
        actual = api.request("GET", path, token)
        if (
            any(actual.get(key) != value for key, value in payload.items() if key != "config")
            or any(
                actual.get("config", {}).get(key) != value
                for key, value in payload["config"].items()
                if key != "clientSecret"
            )
        ):
            raise RuntimeError("Social provider configuration verification failed")


def main():
    try:
        reconcile(
            KeycloakAPI(),
            credentials("/credentials/operator"),
            provider_credentials("/credentials/social"),
        )
    except APIError as error:
        print(f"Social login reconciliation failed (HTTP {error.status}); check operator permissions and provider configuration.", file=sys.stderr)
        return 1
    except (URLError, OSError, RuntimeError, ValueError, KeyError):
        print("Social login reconciliation failed; check connectivity, credentials and realm readiness.", file=sys.stderr)
        return 1
    print("Google and Facebook login providers reconciled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
