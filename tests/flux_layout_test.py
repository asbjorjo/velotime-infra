import subprocess
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

    def test_root_manages_only_instance_and_layer_gates(self):
        self.assertEqual(set(self.gates), set(LAYERS))
        self.assertEqual(len(self.root), 4)
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
        for component, resources in self.workloads.items():
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
