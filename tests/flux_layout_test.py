import fnmatch
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import celpy
import yaml
from celpy.adapter import json_to_cel


ROOT = Path(__file__).resolve().parents[1]
LAYERS = ("infrastructure", "services", "applications")
FLUX_API = "kustomize.toolkit.fluxcd.io/v1"


def build(path):
    result = subprocess.run(
        ["kubectl", "kustomize", str(path)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    return list(yaml.safe_load_all(result.stdout))


def identity(resource):
    metadata = resource["metadata"]
    return (
        resource["apiVersion"], resource["kind"],
        metadata.get("namespace", ""), metadata["name"],
    )


def log_record_is_excluded(expressions, resource_attributes):
    for expression in expressions:
        match = re.fullmatch(
            r'resource\.attributes\["([^"]+)"\] == "([^"]+)"',
            expression,
        )
        if match is None:
            raise AssertionError(f"Unsupported log exclusion expression: {expression}")
        if resource_attributes.get(match.group(1)) == match.group(2):
            return True
    return False


class FluxLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = build(ROOT / "clusters/development")
        cls.gates = {
            resource["metadata"]["name"]: resource
            for resource in cls.root if resource["apiVersion"] == FLUX_API
        }
        cls.layers = {
            layer: build(ROOT / cls.gates[layer]["spec"]["path"])
            for layer in LAYERS
        }
        cls.components = {
            resource["metadata"]["name"]: (layer, resource)
            for layer, resources in cls.layers.items()
            for resource in resources if resource["apiVersion"] == FLUX_API
        }
        cls.workloads = {
            name: build(ROOT / resource["spec"]["path"])
            for name, (_, resource) in cls.components.items()
            if resource["spec"]["sourceRef"]["name"] == "flux-system"
        }
        cls.database_resources = build(
            ROOT / cls.gates["database-opentelemetry-collector"]["spec"]["path"],
        )
        cls.node_resources = build(
            ROOT / cls.gates["node-telemetry-collector"]["spec"]["path"],
        )
        cls.cluster_resources = build(
            ROOT / cls.gates["cluster-telemetry-collector"]["spec"]["path"],
        )

    def test_root_manages_instance_layer_gates_and_standalone_collectors(self):
        self.assertEqual(set(self.gates), {
            *LAYERS,
            "database-opentelemetry-collector",
            "node-telemetry-collector",
            "cluster-telemetry-collector",
        })
        self.assertEqual(len(self.root), 7)
        self.assertEqual(
            [resource["kind"] for resource in self.root].count("FluxInstance"), 1,
        )

    def test_layer_dependency_chain(self):
        for layer, expected in zip(LAYERS, ([], ["infrastructure"], ["services"])):
            with self.subTest(layer=layer):
                spec = self.gates[layer]["spec"]
                self.assertEqual(
                    [dependency["name"] for dependency in spec.get("dependsOn", [])],
                    expected,
                )
                self.assertTrue(spec["wait"])
                self.assertTrue(spec["prune"])
                self.assertEqual(spec["sourceRef"]["name"], "flux-system")

    def test_layer_health_rejects_missing_stale_or_unready_children(self):
        cases = [
            ({}, False),
            ({"observedGeneration": 2}, False),
            ({"observedGeneration": 2, "conditions": []}, False),
            ({"observedGeneration": 1, "conditions": [
                {"type": "Ready", "status": "True"},
            ]}, False),
            ({"observedGeneration": 2, "conditions": [
                {"type": "Ready", "status": "False"},
            ]}, False),
            ({"observedGeneration": 2, "conditions": [
                {"type": "Ready", "status": "Unknown"},
            ]}, False),
            ({"observedGeneration": 2, "conditions": [
                {"type": "Ready", "status": "True"},
                {"type": "Reconciling", "status": "True"},
            ]}, False),
            ({"observedGeneration": 2, "conditions": [
                {"type": "Ready", "status": "True"},
                {"type": "Stalled", "status": "True"},
            ]}, False),
            ({"observedGeneration": 2, "conditions": [
                {"type": "Ready", "status": "True"},
                {"type": "Reconciling", "status": "False"},
                {"type": "Stalled", "status": "False"},
            ]}, True),
        ]
        for layer in LAYERS:
            checks = self.gates[layer]["spec"]["healthCheckExprs"]
            self.assertEqual(len(checks), 1)
            self.assertEqual(checks[0]["apiVersion"], FLUX_API)
            self.assertEqual(checks[0]["kind"], "Kustomization")
            environment = celpy.Environment()
            program = environment.program(environment.compile(checks[0]["current"]))
            resources = [
                ({"metadata": {"generation": 2}}, False),
                *[
                    ({"metadata": {"generation": 2}, "status": status}, expected)
                    for status, expected in cases
                ],
            ]
            for resource, expected in resources:
                with self.subTest(layer=layer, resource=resource):
                    try:
                        ready = bool(program.evaluate(dict(json_to_cel(resource))))
                    except celpy.CELEvalError:
                        ready = False
                    self.assertEqual(ready, expected)

    def test_components_have_unique_owners_and_local_dependencies(self):
        names = [
            resource["metadata"]["name"]
            for resources in self.layers.values()
            for resource in resources if resource["apiVersion"] == FLUX_API
        ]
        self.assertEqual(len(names), len(set(names)))
        for name, (layer, resource) in self.components.items():
            spec = resource["spec"]
            with self.subTest(component=name):
                self.assertTrue(spec.get("wait") or spec.get("healthChecks"))
                for dependency in spec.get("dependsOn", []):
                    self.assertIn(dependency["name"], self.components)
                    self.assertEqual(self.components[dependency["name"]][0], layer)
                if spec["sourceRef"]["name"] == "flux-system":
                    path = (ROOT / spec["path"]).resolve()
                    self.assertTrue(path.is_relative_to(ROOT))
                    self.assertTrue((path / "kustomization.yaml").is_file())
                    self.assertTrue(
                        path.is_relative_to(ROOT / layer)
                        or path.is_relative_to(ROOT / "clusters/development" / layer),
                    )

    def test_component_dependencies_are_acyclic(self):
        visited = set()

        def visit(name, ancestors):
            self.assertNotIn(name, ancestors, f"Dependency cycle at {name}")
            if name in visited:
                return
            for dependency in self.components[name][1]["spec"].get("dependsOn", []):
                visit(dependency["name"], ancestors | {name})
            visited.add(name)

        for name in self.components:
            visit(name, set())

    def test_workloads_are_not_duplicated_or_self_reconciling(self):
        owners = {}
        workloads = {
            **self.workloads,
            "database-opentelemetry-collector": self.database_resources,
            "node-telemetry-collector": self.node_resources,
            "cluster-telemetry-collector": self.cluster_resources,
        }
        for component, resources in workloads.items():
            for resource in resources:
                key = identity(resource)
                with self.subTest(component=component, resource=key):
                    self.assertNotEqual(resource["apiVersion"], FLUX_API)
                    self.assertNotIn(key, owners, f"Already managed by {owners.get(key)}")
                    owners[key] = component

    def test_secret_and_operator_layer_boundaries(self):
        expected = {
            ("ClusterSecretStore", "azure-keyvault"): "infrastructure",
            ("ExternalSecret", "external-dns-azure-config"): "infrastructure",
            ("ExternalSecret", "keycloak-bootstrap-admin"): "services",
            ("Keycloak", "keycloak"): "services",
            ("ExternalSecret", "keycloak-admin"): "applications",
            ("ExternalSecret", "keycloak-realm-client-secrets"): "applications",
            ("KeycloakRealmImport", "velotime"): "applications",
        }
        actual = {
            (resource["kind"], resource["metadata"]["name"]): self.components[name][0]
            for name, resources in self.workloads.items() for resource in resources
        }
        for key, layer in expected.items():
            with self.subTest(resource=key):
                self.assertEqual(actual[key], layer)
        self.assertEqual(self.components["keycloak-operator"][0], "infrastructure")
        self.assertEqual(self.components["keycloak-namespace"][0], "infrastructure")
        self.assertEqual(
            self.components["external-secrets-crs"][1]["spec"]["dependsOn"],
            [{"name": "external-secrets-operator"}],
        )
        self.assertIn(
            {"name": "keycloak-bootstrap-secrets"},
            self.components["keycloak"][1]["spec"]["dependsOn"],
        )

    def test_facilities_uses_existing_vault_messagebus_connection_string(self):
        self.assert_uses_existing_vault_messagebus_connection_string("module-facilities-api")

    def test_velotime_webui_fixed_replicas(self):
        resources = self.workloads["velotime"]
        release = next(resource for resource in resources if resource["kind"] == "HelmRelease")
        self.assertEqual(
            release["spec"]["values"]["webui"]["resources"]["requests"]["memory"], "256Mi",
        )
        self.assertFalse(any(
            resource["kind"] == "HorizontalPodAutoscaler" for resource in resources
        ))
        patches = release["spec"]["postRenderers"][0]["kustomize"]["patches"]
        deployments = [
            {
                "apiVersion": "apps/v1", "kind": "Deployment",
                "metadata": {"name": name},
                "spec": {"replicas": 1},
            }
            for name in ("velotime-webui", "velotime-module-timing-api")
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "deployments.yaml").write_text(yaml.safe_dump_all(deployments))
            (path / "kustomization.yaml").write_text(yaml.safe_dump({
                "apiVersion": "kustomize.config.k8s.io/v1beta1",
                "kind": "Kustomization",
                "resources": ["deployments.yaml"],
                "patches": patches,
            }))
            rendered = {resource["metadata"]["name"]: resource for resource in build(path)}
        self.assertEqual(rendered["velotime-webui"]["spec"]["replicas"], 2)
        self.assertEqual(rendered["velotime-module-timing-api"]["spec"]["replicas"], 1)

    def test_statistics_api_uses_existing_vault_messagebus_connection_string(self):
        self.assert_uses_existing_vault_messagebus_connection_string("module-statistics-api")

    def assert_uses_existing_vault_messagebus_connection_string(self, module):
        release = next(
            resource for resource in self.workloads["velotime"]
            if resource["kind"] == "HelmRelease"
        )
        secret_name = release["spec"]["values"][module]["existingSecret"]
        self.assertEqual(secret_name, module)
        secret = next(
            resource for resource in self.workloads["velotime-secrets"]
            if resource["kind"] == "ExternalSecret"
            and resource["metadata"]["name"] == secret_name
        )
        self.assertEqual(secret["metadata"]["namespace"], release["spec"]["targetNamespace"])
        spec = secret["spec"]
        self.assertEqual(spec["secretStoreRef"], {
            "kind": "ClusterSecretStore", "name": "azure-keyvault",
        })
        self.assertEqual(spec["target"]["name"], secret_name)
        self.assertEqual(spec["target"]["creationPolicy"], "Owner")
        self.assertEqual(spec["target"]["template"]["engineVersion"], "v2")
        self.assertEqual(
            spec["target"]["template"]["data"]["ConnectionStrings__MessageBus"],
            "{{ .ConnectionStrings__MessageBus }}",
        )
        self.assertEqual(
            [
                entry for entry in spec["data"]
                if entry["secretKey"] == "ConnectionStrings__MessageBus"
            ],
            [{
                "secretKey": "ConnectionStrings__MessageBus",
                "remoteRef": {"key": "velotime-messagebus"},
            }],
        )
        self.assertIn(
            {"name": "velotime-secrets"},
            self.components["velotime"][1]["spec"]["dependsOn"],
        )

    def test_profiles_uses_existing_vault_database_and_cache_credentials(self):
        release = next(
            resource for resource in self.workloads["velotime"]
            if resource["kind"] == "HelmRelease"
        )
        secret_name = release["spec"]["values"]["module-profiles-api"]["existingSecret"]
        self.assertEqual(secret_name, "module-profiles-api")
        secret = next(
            resource for resource in self.workloads["velotime-secrets"]
            if resource["kind"] == "ExternalSecret"
            and resource["metadata"]["name"] == secret_name
        )
        self.assertEqual(secret["metadata"]["namespace"], release["spec"]["targetNamespace"])
        spec = secret["spec"]
        self.assertEqual(spec["secretStoreRef"], {
            "kind": "ClusterSecretStore", "name": "azure-keyvault",
        })
        self.assertEqual(spec["target"]["name"], secret_name)
        self.assertEqual(spec["target"]["creationPolicy"], "Owner")
        remote_keys = {
            entry["secretKey"]: entry["remoteRef"]["key"] for entry in spec["data"]
        }
        self.assertEqual(remote_keys, {
            "CACHE_HOST": "velotime-cache-host",
            "CACHE_PORT": "velotime-cache-port",
            "CACHE_USER": "velotime-cache-username",
            "CACHE_PASSWORD": "velotime-cache-password",
            "VELOTIMEDB_HOST": "velotime-database-host",
            "VELOTIMEDB_PORT": "velotime-database-port",
            "VELOTIMEDB_USER": "velotime-database-user",
            "VELOTIMEDB_PASSWORD": "velotime-database-password",
        })
        vault = (ROOT / "terraform/keyvault/main.tf").read_text()
        for key in remote_keys.values():
            with self.subTest(vault_secret=key):
                self.assertIn(f'name         = "{key}"', vault)
        self.assertEqual(spec["target"]["template"]["engineVersion"], "v2")
        self.assertEqual(spec["target"]["template"]["data"], {
            "CACHE_HOST": "{{ .CACHE_HOST }}",
            "CACHE_PORT": "{{ .CACHE_PORT }}",
            "CACHE_USER": "{{ .CACHE_USER }}",
            "CACHE_PASSWORD": "{{ .CACHE_PASSWORD }}",
            "CACHE_URI": (
                "rediss://{{ .CACHE_USER }}:{{ .CACHE_PASSWORD }}"
                "@{{ .CACHE_HOST }}:{{ .CACHE_PORT }}"
            ),
            "ConnectionStrings__cache": (
                "{{ .CACHE_HOST }}:{{ .CACHE_PORT }},user={{ .CACHE_USER }},"
                "password={{ .CACHE_PASSWORD }},ssl=true"
            ),
            "VELOTIMEDB_PASSWORD": "{{ .VELOTIMEDB_PASSWORD }}",
            "VELOTIMEDB_URI": (
                "postgresql://{{ .VELOTIMEDB_USER }}:{{ .VELOTIMEDB_PASSWORD }}"
                "@{{ .VELOTIMEDB_HOST }}:{{ .VELOTIMEDB_PORT }}/velotimedb"
            ),
            "ConnectionStrings__velotimedb": (
                "Host={{ .VELOTIMEDB_HOST }};port={{ .VELOTIMEDB_PORT }};"
                "Username={{ .VELOTIMEDB_USER }};Password={{ .VELOTIMEDB_PASSWORD }};"
                "Database=velotimedb"
            ),
        })
        dependencies = self.components["velotime"][1]["spec"]["dependsOn"]
        self.assertIn({"name": "velotime-secrets"}, dependencies)
        self.assertIn({"name": "velotime-db-grant"}, dependencies)

    def test_notifications_use_existing_vault_database_and_cache_credentials(self):
        release = next(
            resource for resource in self.workloads["velotime"]
            if resource["kind"] == "HelmRelease"
        )
        remote_keys = {
            "CACHE_HOST": "velotime-cache-host",
            "CACHE_PORT": "velotime-cache-port",
            "CACHE_USER": "velotime-cache-username",
            "CACHE_PASSWORD": "velotime-cache-password",
            "VELOTIMEDB_HOST": "velotime-database-host",
            "VELOTIMEDB_PORT": "velotime-database-port",
            "VELOTIMEDB_USER": "velotime-database-user",
            "VELOTIMEDB_PASSWORD": "velotime-database-password",
        }
        template = {
            "CACHE_PASSWORD": "{{ .CACHE_PASSWORD }}",
            "CACHE_URI": (
                "rediss://{{ .CACHE_USER }}:{{ .CACHE_PASSWORD }}"
                "@{{ .CACHE_HOST }}:{{ .CACHE_PORT }}"
            ),
            "ConnectionStrings__cache": (
                "{{ .CACHE_HOST }}:{{ .CACHE_PORT }},user={{ .CACHE_USER }},"
                "password={{ .CACHE_PASSWORD }},ssl=true"
            ),
            "VELOTIMEDB_PASSWORD": "{{ .VELOTIMEDB_PASSWORD }}",
            "VELOTIMEDB_URI": (
                "postgresql://{{ .VELOTIMEDB_USER }}:{{ .VELOTIMEDB_PASSWORD }}"
                "@{{ .VELOTIMEDB_HOST }}:{{ .VELOTIMEDB_PORT }}/velotimedb"
            ),
            "ConnectionStrings__velotimedb": (
                "Host={{ .VELOTIMEDB_HOST }};port={{ .VELOTIMEDB_PORT }};"
                "Username={{ .VELOTIMEDB_USER }};Password={{ .VELOTIMEDB_PASSWORD }};"
                "Database=velotimedb"
            ),
        }
        for name in ("module-notifications-api", "module-notifications-processor"):
            with self.subTest(component=name):
                self.assertEqual(release["spec"]["values"][name]["existingSecret"], name)
                secret = next(
                    resource for resource in self.workloads["velotime-secrets"]
                    if resource["kind"] == "ExternalSecret"
                    and resource["metadata"]["name"] == name
                )
                self.assertEqual(
                    secret["metadata"]["namespace"], release["spec"]["targetNamespace"],
                )
                spec = secret["spec"]
                self.assertEqual(spec["secretStoreRef"], {
                    "kind": "ClusterSecretStore", "name": "azure-keyvault",
                })
                self.assertEqual(spec["target"]["name"], name)
                self.assertEqual(spec["target"]["creationPolicy"], "Owner")
                expected_keys = dict(remote_keys)
                expected_template = dict(template)
                if name == "module-notifications-processor":
                    expected_keys["ConnectionStrings__MessageBus"] = "velotime-messagebus"
                    expected_template["ConnectionStrings__MessageBus"] = (
                        "{{ .ConnectionStrings__MessageBus }}"
                    )
                self.assertEqual({
                    entry["secretKey"]: entry["remoteRef"]["key"]
                    for entry in spec["data"]
                }, expected_keys)
                self.assertEqual(spec["target"]["template"]["engineVersion"], "v2")
                self.assertEqual(spec["target"]["template"]["data"], expected_template)
        dependencies = self.components["velotime"][1]["spec"]["dependsOn"]
        self.assertIn({"name": "velotime-secrets"}, dependencies)
        self.assertIn({"name": "velotime-db-grant"}, dependencies)

    def test_webui_has_runtime_messagebus_for_notification_refresh(self):
        release = next(
            resource for resource in self.workloads["velotime"]
            if resource["kind"] == "HelmRelease"
        )
        secret_name = release["spec"]["values"]["webui"]["existingSecret"]
        secret = next(
            resource for resource in self.workloads["velotime-secrets"]
            if resource["kind"] == "ExternalSecret"
            and resource["metadata"]["name"] == secret_name
        )
        data = secret["spec"]["target"]["template"]["data"]
        self.assertEqual(
            data["ConnectionStrings__MessageBus"], "{{ .ConnectionStrings__MessageBus }}",
        )
        self.assertIn("ConnectionStrings__cache", data)
        self.assertIn({
            "secretKey": "ConnectionStrings__MessageBus",
            "remoteRef": {"key": "velotime-messagebus"},
        }, secret["spec"]["data"])
        values = release["spec"]["values"]
        self.assertEqual(
            values["global"]["oidcAudience"], "https://development.veloti.me",
        )
        self.assertEqual(
            values["global"]["oidcAuthority"], "https://auth.development.veloti.me/",
        )
        topic = next(
            topic for topic in values["messageBusTopology"]["topics"]
            if topic["name"] == "velotime-notifications"
        )
        self.assertEqual(topic["subscriptions"], [{
            "name": "webui-notifications",
            "requiresSession": False,
            "rules": [{
                "name": "NotificationsRefreshRequestedV1",
                "sqlFilter": "MessageName = 'NotificationsRefreshRequestedV1'",
            }],
        }])

    def test_development_agent_topology_matches_chart_control_plane(self):
        release = next(
            resource for resource in self.workloads["velotime"]
            if resource["kind"] == "HelmRelease"
        )
        topics = {
            topic["name"]: topic
            for topic in release["spec"]["values"]["messageBusTopology"]["topics"]
        }
        agent = {sub["name"]: sub for sub in topics["velotime-agent"]["subscriptions"]}
        self.assertEqual(set(agent), {"timing", "infrastructure"})
        self.assertEqual(
            [rule["name"] for rule in agent["infrastructure"]["rules"]],
            [
                "InstallationLayoutEvent", "LoopStatusV1",
                "AgentCapabilitiesV1", "PassingReplayStatusV1",
            ],
        )
        # Agents provision their own per-agent subscriptions on the control topic.
        self.assertEqual(topics["velotime-agent-control"]["subscriptions"], [])

    def test_keycloak_database_secrets_are_owned_by_grant(self):
        for name in ("keycloak-db-secret", "keycloak-db-admin-secret"):
            owners = [
                component
                for component, resources in self.workloads.items()
                for resource in resources
                if resource["kind"] == "ExternalSecret"
                and resource["metadata"]["namespace"] == "keycloak"
                and resource["spec"]["target"]["name"] == name
            ]
            with self.subTest(secret=name):
                self.assertEqual(owners, ["keycloak-db-grant"])

    def test_keycloak_and_velotime_database_connections_require_ssl(self):
        keycloak = next(
            resource for resource in self.workloads["keycloak"]
            if resource["kind"] == "Keycloak"
        )
        keycloak_options = {
            option["name"]: option
            for option in keycloak["spec"]["additionalOptions"]
        }
        self.assertEqual(
            keycloak_options["db-url-properties"]["value"], "?sslmode=require",
        )

        database_templates = []
        for component in ("velotime-bootstrap-secrets", "velotime-secrets"):
            database_templates.extend(
                resource["spec"]["target"]["template"]["data"]
                for resource in self.workloads[component]
                if resource["kind"] == "ExternalSecret"
                and (
                    "VELOTIMEDB_URI"
                    in resource["spec"]["target"]["template"].get("data", {})
                    or "ConnectionStrings__velotimedb"
                    in resource["spec"]["target"]["template"].get("data", {})
                )
            )
        self.assertTrue(database_templates)
        for data in database_templates:
            with self.subTest(data=data):
                if "VELOTIMEDB_URI" in data:
                    self.assertTrue(data["VELOTIMEDB_URI"].endswith("?sslmode=require"))
                if "ConnectionStrings__velotimedb" in data:
                    self.assertIn("SSL Mode=Require", data["ConnectionStrings__velotimedb"])

    def test_development_keycloak_tracing_and_metrics_preserve_base_configuration(self):
        keycloak = next(
            resource for resource in self.workloads["keycloak"]
            if resource["kind"] == "Keycloak"
        )
        base_resources = build(ROOT / "services/keycloak")
        base = next(resource for resource in base_resources if resource["kind"] == "Keycloak")
        self.assertNotIn("tracing", base["spec"])
        self.assertEqual(keycloak["spec"]["tracing"], {
            "enabled": True,
            "endpoint": "http://telemetry-collector.velotime-instrumentation.svc.cluster.local:4317",
            "samplerType": "traceidratio",
            "samplerRatio": 1.0,
        })
        self.assertEqual(
            keycloak["spec"]["additionalOptions"],
            base["spec"]["additionalOptions"] + [{"name": "metrics-enabled", "value": "true"}],
        )
        route = next(
            resource for resource in self.workloads["keycloak"]
            if resource["kind"] == "HTTPRoute"
        )
        base_route = next(resource for resource in base_resources if resource["kind"] == "HTTPRoute")
        self.assertEqual(route["spec"]["rules"], base_route["spec"]["rules"])

    def test_development_gateway_scrapes_keycloak_and_preserves_otlp_pipelines(self):
        collector = next(
            resource for resource in self.workloads["opentelemetry-collector"]
            if resource["kind"] == "OpenTelemetryCollector"
        )
        config = collector["spec"]["config"]
        self.assertEqual(config["receivers"]["prometheus"]["config"]["scrape_configs"], [{
            "job_name": "keycloak",
            "scrape_interval": "30s",
            "metrics_path": "/metrics",
            "dns_sd_configs": [{
                "names": ["keycloak-discovery.keycloak.svc.cluster.local"],
                "type": "A",
                "port": 9000,
            }],
        }])
        base = next(
            resource for resource in build(ROOT / "services/opentelemetry-collector")
            if resource["kind"] == "OpenTelemetryCollector"
        )["spec"]["config"]
        self.assertEqual(config["receivers"]["otlp"], base["receivers"]["otlp"])
        for signal in ("logs", "traces"):
            self.assertEqual(config["service"]["pipelines"][signal], base["service"]["pipelines"][signal])
        self.assertEqual(config["service"]["pipelines"]["metrics"], {
            **base["service"]["pipelines"]["metrics"],
            "receivers": ["otlp", "prometheus"],
        })
        self.assertEqual(config["exporters"]["otlp"]["tls"], base["exporters"]["otlp"]["tls"])

    def test_keycloak_grant_secret_keys_are_available_in_its_component(self):
        resources = self.workloads["keycloak-db-grant"]
        secrets = {
            (resource["metadata"]["namespace"], resource["spec"]["target"]["name"]):
                resource["spec"]["target"]["template"]["data"]
            for resource in resources if resource["kind"] == "ExternalSecret"
        }
        jobs = [resource for resource in resources if resource["kind"] == "Job"]
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        references = [
            variable["valueFrom"]["secretKeyRef"]
            for container in job["spec"]["template"]["spec"]["containers"]
            for variable in container["env"]
            if "secretKeyRef" in variable.get("valueFrom", {})
        ]
        self.assertTrue(references)
        for reference in references:
            target = (job["metadata"]["namespace"], reference["name"])
            with self.subTest(secret=target, key=reference["key"]):
                self.assertIn(target, secrets)
                self.assertIn(reference["key"], secrets[target])

    def test_velotime_grant_uses_separate_admin_port_secret(self):
        resources = self.workloads["velotime-db-grant"]
        port_secret = next(
            resource for resource in resources
            if resource["kind"] == "ExternalSecret"
            and resource["spec"]["target"]["name"] == "velotime-db-admin-port-secret"
        )
        self.assertEqual(
            port_secret["spec"]["target"]["template"]["data"],
            {"port": "{{ .port }}"},
        )
        self.assertIn({
            "secretKey": "port",
            "remoteRef": {"key": "velotime-database-admin-port"},
        }, port_secret["spec"]["data"])

        job = next(resource for resource in resources if resource["kind"] == "Job")
        pgport = next(
            variable for variable in job["spec"]["template"]["spec"]["containers"][0]["env"]
            if variable["name"] == "PGPORT"
        )
        self.assertEqual(
            pgport["valueFrom"]["secretKeyRef"],
            {"name": "velotime-db-admin-port-secret", "key": "port"},
        )

    def test_keycloak_waits_for_grant_completion_and_bootstrap_secret(self):
        self.assertTrue(self.components["keycloak-db-grant"][1]["spec"]["wait"])
        dependencies = self.components["keycloak"][1]["spec"]["dependsOn"]
        self.assertIn({"name": "keycloak-db-grant"}, dependencies)
        self.assertIn({"name": "keycloak-bootstrap-secrets"}, dependencies)

    def test_collector_checks_generated_deployment(self):
        spec = self.components["opentelemetry-collector"][1]["spec"]
        self.assertFalse(spec.get("wait", False))
        self.assertEqual(spec["healthChecks"], [{
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "name": "telemetry-collector",
            "namespace": "velotime-instrumentation",
        }])

    def test_database_collector_is_standalone_and_has_no_dependants(self):
        name = "database-opentelemetry-collector"
        kustomizations = list(self.gates.values()) + [
            resource for _, resource in self.components.values()
        ]
        for resource in kustomizations:
            with self.subTest(kustomization=resource["metadata"]["name"]):
                self.assertNotIn(
                    name,
                    [dependency["name"] for dependency in resource["spec"].get("dependsOn", [])],
                )
        services = self.gates["services"]["spec"]
        self.assertTrue(services["wait"])
        self.assertNotIn(name, self.components)
        spec = self.gates[name]["spec"]
        self.assertEqual(spec["dependsOn"], [{"name": "services"}])
        self.assertEqual(spec["path"], "./clusters/development/database-opentelemetry-collector")
        self.assertEqual(spec["sourceRef"], {"kind": "GitRepository", "name": "flux-system"})
        self.assertEqual(spec["healthChecks"], [{
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "name": "database-telemetry-collector",
            "namespace": "velotime-instrumentation",
        }])

    def test_node_and_cluster_collectors_are_standalone_and_check_generated_workloads(self):
        expected = {
            "node-telemetry-collector": (
                "DaemonSet", "node-telemetry-collector", self.node_resources,
            ),
            "cluster-telemetry-collector": (
                "Deployment", "cluster-telemetry-collector", self.cluster_resources,
            ),
        }
        root_kustomizations = [
            resource for resource in self.root if resource["apiVersion"] == FLUX_API
        ]
        all_kustomizations = root_kustomizations + [
            resource for _, resource in self.components.values()
        ]
        for name, (kind, workload, resources) in expected.items():
            spec = self.gates[name]["spec"]
            with self.subTest(component=name):
                self.assertTrue(spec["suspend"])
                self.assertEqual(spec["dependsOn"], [{"name": "services"}])
                self.assertEqual(
                    spec["path"], f"./clusters/development/{name}",
                )
                self.assertEqual(
                    spec["sourceRef"], {"kind": "GitRepository", "name": "flux-system"},
                )
                self.assertEqual(spec["healthChecks"], [{
                    "apiVersion": "apps/v1",
                    "kind": kind,
                    "name": workload,
                    "namespace": "velotime-instrumentation",
                }])
                self.assertFalse(any(
                    resource["apiVersion"] == FLUX_API
                    for resource in resources
                ))
                for other in all_kustomizations:
                    if other["metadata"]["name"] == name:
                        continue
                    self.assertNotIn(
                        name,
                        [
                            dependency["name"]
                            for dependency in other["spec"].get("dependsOn", [])
                        ],
                    )

    def test_node_collector_has_bounded_node_collection_and_explicit_log_selectors(self):
        resources = self.node_resources
        collector = next(
            resource for resource in resources
            if resource["kind"] == "OpenTelemetryCollector"
        )
        config = collector["spec"]["config"]
        self.assertEqual(collector["spec"]["mode"], "daemonset")
        self.assertEqual(collector["spec"]["image"], next(
            resource["spec"]["image"]
            for resource in self.cluster_resources
            if resource["kind"] == "OpenTelemetryCollector"
        ))
        self.assertEqual(collector["spec"]["serviceAccount"], "node-telemetry")
        filelog = config["receivers"]["filelog"]
        self.assertEqual(filelog["start_at"], "end")
        self.assertNotIn("storage", filelog)
        self.assertNotIn("file_storage", config.get("extensions", {}))
        self.assertEqual(filelog["include"], ["/var/log/pods/*/*/*.log"])
        self.assertEqual(len(filelog["exclude"]), 3)
        for pod_name in (
            "node-telemetry-collector-abc123",
            "cluster-telemetry-collector-abc123",
        ):
            path = f"/var/log/pods/velotime-instrumentation_{pod_name}_uid/collector/0.log"
            self.assertTrue(any(
                fnmatch.fnmatch(path, pattern) for pattern in filelog["exclude"]
            ))
        for namespace, excluded in (("velotime", True), ("default", False)):
            path = f"/var/log/pods/{namespace}_example-abc123_uid/app/0.log"
            with self.subTest(namespace=namespace):
                self.assertEqual(any(
                    fnmatch.fnmatch(path, pattern) for pattern in filelog["exclude"]
                ), excluded)

        selectors = config["processors"]["filter/logs"]["logs"]["log_record"]
        expected = (
            ({"k8s.pod.annotation.telemetry.velotime.io/collector": "node-agent"}, True),
            ({"k8s.pod.annotation.telemetry.velotime.io/collector": "cluster-state"}, True),
            ({"k8s.pod.annotation.telemetry.velotime.io/otlp-logs": "true"}, True),
            ({"k8s.namespace.name": "default"}, False),
            ({}, False),
        )
        for attributes, excluded in expected:
            with self.subTest(attributes=attributes):
                self.assertEqual(
                    log_record_is_excluded(selectors, attributes), excluded,
                )

        annotation_keys = {
            entry["key"]
            for entry in config["processors"]["k8sattributes"]["extract"]["annotations"]
        }
        self.assertEqual(annotation_keys, {
            "telemetry.velotime.io/collector",
            "telemetry.velotime.io/otlp-logs",
        })
        missing_metadata_statements = config["processors"]["transform/log-metadata"][
            "log_statements"
        ][0]["statements"]
        self.assertTrue(any(
            "telemetry.velotime.io/k8s-metadata-missing" in statement
            and 'resource.attributes["k8s.pod.name"] == nil' in statement
            for statement in missing_metadata_statements
        ))

    def test_node_collector_mounts_host_data_read_only_and_uses_minimal_rbac(self):
        collector = next(
            resource for resource in self.node_resources
            if resource["kind"] == "OpenTelemetryCollector"
        )
        self.assertEqual(collector["spec"]["mode"], "daemonset")
        volumes = {
            volume["name"]: volume["hostPath"]["path"]
            for volume in collector["spec"]["volumes"]
        }
        self.assertEqual(volumes, {"pod-logs": "/var/log/pods", "host-root": "/"})
        mounts = {
            mount["name"]: mount
            for mount in collector["spec"]["volumeMounts"]
        }
        self.assertTrue(all(mount["readOnly"] for mount in mounts.values()))
        config = collector["spec"]["config"]
        self.assertEqual(
            config["receivers"]["hostmetrics"]["root_path"],
            "/hostfs",
        )
        cluster_role = next(
            resource for resource in self.node_resources
            if resource["kind"] == "ClusterRole"
        )
        self.assertEqual({
            (resource, tuple(rule["verbs"]))
            for rule in cluster_role["rules"]
            for resource in rule["resources"]
        }, {
            ("nodes", ("get",)),
            ("nodes/stats", ("get",)),
            ("pods", ("get", "list", "watch")),
        })

    def test_node_and_cluster_collectors_use_distinct_read_only_service_accounts(self):
        expected = {
            "node-telemetry": self.node_resources,
            "cluster-telemetry": self.cluster_resources,
        }
        for account, resources in expected.items():
            service_accounts = [
                resource for resource in resources
                if resource["kind"] == "ServiceAccount"
            ]
            roles = [
                resource for resource in resources
                if resource["kind"] == "ClusterRole"
            ]
            bindings = [
                resource for resource in resources
                if resource["kind"] == "ClusterRoleBinding"
            ]
            with self.subTest(service_account=account):
                self.assertEqual(len(service_accounts), 1)
                self.assertEqual(service_accounts[0]["metadata"]["name"], account)
                self.assertEqual(len(roles), 1)
                self.assertEqual(len(bindings), 1)
                self.assertEqual(bindings[0]["roleRef"]["name"], roles[0]["metadata"]["name"])
                self.assertEqual(bindings[0]["subjects"], [{
                    "kind": "ServiceAccount",
                    "name": account,
                    "namespace": "velotime-instrumentation",
                }])
                self.assertEqual(
                    next(
                        resource["spec"]["serviceAccount"]
                        for resource in resources
                        if resource["kind"] == "OpenTelemetryCollector"
                    ),
                    account,
                )
                self.assertTrue(all(
                    set(rule["verbs"]) <= {"get", "list", "watch"}
                    and "*" not in rule["resources"]
                    for rule in roles[0]["rules"]
                ))

    def test_node_and_cluster_collectors_export_metrics_to_existing_gateway(self):
        expected_receivers = {
            "node-telemetry-collector": {
                "logs": ["filelog"],
                "metrics": ["kubeletstats", "hostmetrics"],
            },
            "cluster-telemetry-collector": {
                "metrics": ["k8s_cluster"],
            },
        }
        resources_by_name = {
            "node-telemetry-collector": self.node_resources,
            "cluster-telemetry-collector": self.cluster_resources,
        }
        endpoint = (
            "telemetry-collector.velotime-instrumentation.svc.cluster.local:4317"
        )
        for name, resources in resources_by_name.items():
            collector = next(
                resource for resource in resources
                if resource["kind"] == "OpenTelemetryCollector"
            )
            config = collector["spec"]["config"]
            with self.subTest(component=name):
                self.assertEqual(
                    config["exporters"]["otlp"]["endpoint"], endpoint,
                )
                self.assertEqual(
                    config["exporters"]["otlp"]["tls"], {"insecure": True},
                )
                self.assertEqual(
                    set(config["service"]["pipelines"]),
                    set(expected_receivers[name]),
                )
                for signal, receivers in expected_receivers[name].items():
                    self.assertEqual(
                        config["service"]["pipelines"][signal]["receivers"],
                        receivers,
                    )
                self.assertIn("memory_limiter", config["processors"])
                self.assertIn("batch", config["processors"])
                self.assertTrue(
                    config["exporters"]["otlp"]["sending_queue"]["enabled"],
                )
                self.assertTrue(
                    config["exporters"]["otlp"]["retry_on_failure"]["enabled"],
                )

        node_config = next(
            resource for resource in self.node_resources
            if resource["kind"] == "OpenTelemetryCollector"
        )["spec"]["config"]
        self.assertTrue(
            node_config["receivers"]["kubeletstats"]["insecure_skip_verify"],
        )
        cluster = next(
            resource for resource in self.cluster_resources
            if resource["kind"] == "OpenTelemetryCollector"
        )
        self.assertEqual(cluster["spec"]["mode"], "deployment")
        self.assertEqual(cluster["spec"]["replicas"], 1)

    def test_database_collector_scrapes_with_separate_vault_credentials(self):
        resources = self.database_resources
        collectors = {
            resource["metadata"]["name"]: resource
            for resource in resources if resource["kind"] == "OpenTelemetryCollector"
        }
        self.assertEqual(set(collectors), {"database-telemetry"})
        collector = collectors["database-telemetry"]
        secret = next(
            resource for resource in resources
            if resource["kind"] == "ExternalSecret"
            and resource["metadata"]["name"] == "database-metrics"
        )
        self.assertEqual(collector["metadata"]["namespace"], secret["metadata"]["namespace"])
        self.assertEqual(collector["spec"]["envFrom"], [
            {"secretRef": {"name": secret["spec"]["target"]["name"]}},
        ])
        self.assertEqual(secret["spec"]["secretStoreRef"], {
            "kind": "ClusterSecretStore", "name": "azure-keyvault",
        })
        self.assertEqual({
            entry["secretKey"]: entry["remoteRef"]["key"]
            for entry in secret["spec"]["data"]
        }, {
            "DATABASE_HOST": "velotime-database-host",
            "CACHE_HOST": "velotime-cache-host",
            "DATABASE_METRICS_USER": "database-metrics-user",
            "DATABASE_METRICS_PASSWORD": "database-metrics-password",
            "CACHE_METRICS_USER": "cache-metrics-user",
            "CACHE_METRICS_PASSWORD": "cache-metrics-password",
        })
        config = collector["spec"]["config"]
        jobs = config["receivers"]["prometheus"]["config"]["scrape_configs"]
        self.assertEqual(len(jobs), 2)
        for job, component in zip(jobs, ("DATABASE", "CACHE")):
            with self.subTest(component=component):
                self.assertEqual(job["job_name"], f"velotime-{component.lower()}")
                self.assertEqual(job["scheme"], "http")
                self.assertEqual(job["metrics_path"], "/metrics")
                self.assertEqual(job["static_configs"], [
                    {"targets": [f"${{env:{component}_HOST}}:9273"]},
                ])
                self.assertEqual(job["basic_auth"], {
                    "username": f"${{env:{component}_METRICS_USER}}",
                    "password": f"${{env:{component}_METRICS_PASSWORD}}",
                })
        self.assertEqual(config["service"]["pipelines"], {
            "metrics": {"receivers": ["prometheus"], "exporters": ["otlp"]},
        })
        self.assertEqual(
            config["exporters"],
            {"otlp": {
                "endpoint": "telemetry-collector.velotime-instrumentation.svc.cluster.local:4317",
                "tls": {"insecure": True},
            }},
        )
        telemetry = next(
            resource for resource in self.workloads["opentelemetry-collector"]
            if resource["kind"] == "OpenTelemetryCollector"
        )
        self.assertEqual(
            telemetry["spec"]["config"]["receivers"]["otlp"]["protocols"]["grpc"]["endpoint"],
            "0.0.0.0:4317",
        )
        self.assertEqual(
            set(telemetry["spec"]["config"]["service"]["pipelines"]),
            {"logs", "metrics", "traces"},
        )

    def test_gateway_checks_current_accepted_and_programmed_conditions(self):
        checks = self.components["gateway"][1]["spec"]["healthCheckExprs"]
        gateway_check = next(check for check in checks if check["kind"] == "Gateway")
        environment = celpy.Environment()
        program = environment.program(environment.compile(gateway_check["current"]))
        for generation in (1, 2):
            for accepted in ("True", "False", "Unknown"):
                for programmed in ("True", "False", "Unknown"):
                    resource = {
                        "metadata": {"generation": 2},
                        "status": {"conditions": [
                            {
                                "type": "Accepted", "status": accepted,
                                "observedGeneration": generation,
                            },
                            {
                                "type": "Programmed", "status": programmed,
                                "observedGeneration": generation,
                            },
                        ]},
                    }
                    with self.subTest(
                        generation=generation, accepted=accepted, programmed=programmed,
                    ):
                        self.assertEqual(
                            bool(program.evaluate(dict(json_to_cel(resource)))),
                            generation == 2 and accepted == programmed == "True",
                        )

    def test_every_component_source_exists_in_its_layer(self):
        for layer, resources in self.layers.items():
            sources = {
                identity(resource)
                for resource in resources if resource["kind"] == "GitRepository"
            }
            sources.update(
                identity(resource)
                for name, workload in self.workloads.items()
                if self.components[name][0] == layer
                for resource in workload if resource["kind"] == "GitRepository"
            )
            for name, (owner, resource) in self.components.items():
                if owner != layer:
                    continue
                source = resource["spec"]["sourceRef"]
                if source["name"] == "flux-system":
                    continue
                with self.subTest(component=name):
                    self.assertIn((
                        "source.toolkit.fluxcd.io/v1", "GitRepository",
                        source.get("namespace", resource["metadata"]["namespace"]),
                        source["name"],
                    ), sources)

    def test_shared_bases_have_no_development_settings_and_all_build(self):
        for layer in LAYERS:
            for path in (ROOT / layer).rglob("*.yaml"):
                with self.subTest(path=path):
                    self.assertNotIn("development", path.read_text())
            for path in (ROOT / layer).rglob("kustomization.yaml"):
                with self.subTest(path=path.parent):
                    build(path.parent)


if __name__ == "__main__":
    unittest.main()
