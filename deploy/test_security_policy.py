import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContainerSecurityPolicyTest(unittest.TestCase):
    def test_coturn_container_has_uid_independent_hardening(self) -> None:
        deployment = (ROOT / "deploy/k8s/deployment.yaml").read_text(encoding="utf-8")
        coturn = deployment[deployment.index("        - name: coturn") : deployment.index("      volumes:")]

        self.assertIn("allowPrivilegeEscalation: false", coturn)
        self.assertRegex(coturn, r"capabilities:\s+drop:\s+- ALL")
        self.assertRegex(coturn, r"seccompProfile:\s+type: RuntimeDefault")

    def test_readme_records_the_pinned_image_uid_exception_and_operator_gate(self) -> None:
        readme = (ROOT / "deploy/README.md").read_text(encoding="utf-8")
        image = (ROOT / "deploy/coturn-image.txt").read_text(encoding="utf-8").strip()
        self.assertIn("容器執行身分例外", readme)
        self.assertIn(image, readme)
        self.assertIn("docker image inspect", readme)
        self.assertIn("runAsUser", readme)
        self.assertIn("runAsNonRoot", readme)

    def test_readme_first_template_sync_allows_unrelated_histories(self) -> None:
        readme = (ROOT / "deploy/README.md").read_text(encoding="utf-8")
        self.assertIn("git merge upstream/master --allow-unrelated-histories", readme)

    def test_ci_runs_the_security_policy_gate(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("Validate container security policy", workflow)
        self.assertIn("python3 -m unittest discover -s deploy -p 'test_*.py'", workflow)

    def test_rendered_conf_is_carried_by_a_secret_not_a_configmap(self) -> None:
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        deployment = (ROOT / "deploy/k8s/deployment.yaml").read_text(encoding="utf-8")
        active_deployment = "\n".join(
            line for line in deployment.splitlines() if not line.lstrip().startswith("#")
        )

        self.assertIn("kubectl create secret generic open4wd-turn-conf", workflow)
        self.assertIn("--from-file=turnserver.conf=turnserver.conf", workflow)
        self.assertNotIn("create configmap", workflow)
        self.assertNotIn("--from-literal", workflow)
        self.assertIn("secret: { secretName: open4wd-turn-conf }", active_deployment)
        self.assertNotIn("configMap", active_deployment)


if __name__ == "__main__":
    unittest.main()
