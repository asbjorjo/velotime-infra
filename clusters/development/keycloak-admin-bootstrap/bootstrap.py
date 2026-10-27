import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SERVER = "http://keycloak-service.keycloak.svc:8080"
REALM = "velotime"
OPERATOR_ROLES = (
    "manage-clients",
    "view-clients",
    "manage-users",
    "view-users",
    "manage-realm",
    "manage-identity-providers",
)


class APIError(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Keycloak request failed (HTTP {status})")


class KeycloakAPI:
    def request(self, method, path, token=None, payload=None, form=None):
        headers = {}
        data = None
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode()
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = urlencode(form).encode()
        request = Request(SERVER + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read()
                return json.loads(body) if body else None
        except HTTPError as error:
            raise APIError(error.code) from None


def credentials(directory):
    return {
        name: (Path(directory) / name).read_text()
        for name in ("client-id", "client-secret")
    }


def authenticate(api, account):
    try:
        response = api.request(
            "POST",
            "/realms/master/protocol/openid-connect/token",
            form={
                "grant_type": "client_credentials",
                "client_id": account["client-id"],
                "client_secret": account["client-secret"],
            },
        )
        return response["access_token"]
    except APIError as error:
        if error.status in (400, 401):
            return None
        raise


def find_client(api, token, client_id):
    query = urlencode({"clientId": client_id})
    matches = api.request("GET", f"/admin/realms/master/clients?{query}", token)
    exact = [client for client in matches if client["clientId"] == client_id]
    if len(exact) > 1:
        raise RuntimeError("Multiple clients matched the expected ID")
    return exact[0] if exact else None


def verify_operator(api, account):
    print("Authenticating permanent operator.", flush=True)
    token = authenticate(api, account)
    if token is None:
        print("Permanent operator authentication was rejected.", file=sys.stderr, flush=True)
        return False
    for path in (
        f"/admin/api/{REALM}/clients/v2",
        f"/admin/realms/{REALM}/roles",
        f"/admin/realms/{REALM}/users?max=1",
        f"/admin/realms/{REALM}/identity-provider/instances",
    ):
        print(f"Verifying operator access: GET {path}", flush=True)
        try:
            api.request("GET", path, token)
        except APIError as error:
            print(f"Operator access check failed (HTTP {error.status}).", file=sys.stderr, flush=True)
            if error.status in (401, 403):
                return False
            raise
    return True


def bootstrap(api, temporary, permanent):
    if temporary["client-id"] == permanent["client-id"]:
        raise RuntimeError("Bootstrap and permanent client IDs must differ")
    permanent_ready = verify_operator(api, permanent)
    print("Checking temporary bootstrap access.", flush=True)
    token = authenticate(api, temporary)
    if token is None:
        if permanent_ready:
            return
        print("Neither temporary bootstrap nor permanent operator access is available.", file=sys.stderr, flush=True)
        raise RuntimeError("Neither bootstrap nor permanent operator access is available")

    if not permanent_ready:
        print("Provisioning permanent operator and realm management roles.", flush=True)
        client = find_client(api, token, permanent["client-id"])
        payload = {
            "clientId": permanent["client-id"],
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "clientAuthenticatorType": "client-secret",
            "secret": permanent["client-secret"],
            "serviceAccountsEnabled": True,
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "implicitFlowEnabled": False,
            "fullScopeAllowed": True,
        }
        if client is None:
            api.request("POST", "/admin/realms/master/clients", token, payload=payload)
            client = find_client(api, token, permanent["client-id"])
        else:
            api.request(
                "PUT", f"/admin/realms/master/clients/{client['id']}", token,
                payload=payload,
            )
        if client is None:
            raise RuntimeError("Permanent operator client was not created")
        account = api.request(
            "GET", f"/admin/realms/master/clients/{client['id']}/service-account-user", token,
        )
        management = find_client(api, token, f"{REALM}-realm")
        if management is None:
            raise RuntimeError("Realm management client is missing; import the realm first")
        roles = [
            api.request(
                "GET", f"/admin/realms/master/clients/{management['id']}/roles/{name}", token,
            )
            for name in OPERATOR_ROLES
        ]
        api.request(
            "POST",
            f"/admin/realms/master/users/{account['id']}/role-mappings/clients/{management['id']}",
            token, payload=roles,
        )

    if not verify_operator(api, permanent):
        raise RuntimeError("Permanent operator verification failed; bootstrap access retained")
    client = find_client(api, token, temporary["client-id"])
    if client is not None:
        print("Removing temporary bootstrap account after successful verification.", flush=True)
        api.request("DELETE", f"/admin/realms/master/clients/{client['id']}", token)


def main():
    print("Starting Keycloak operator bootstrap.", flush=True)
    try:
        bootstrap(
            KeycloakAPI(),
            credentials("/credentials/bootstrap"),
            credentials("/credentials/operator"),
        )
    except APIError as error:
        print(f"Operator bootstrap failed (HTTP {error.status}); check the preceding access check, realm existence and permissions.", file=sys.stderr)
        return 1
    except (URLError, OSError, RuntimeError, ValueError, KeyError):
        print("Operator bootstrap failed; check connectivity, credentials and realm readiness.", file=sys.stderr)
        return 1
    print("Permanent operator access verified; temporary bootstrap account removed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())