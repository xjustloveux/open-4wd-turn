import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_DEFAULTS = {
    "MIN_PORT": "49152",
    "MAX_PORT": "65535",
    "USER_QUOTA": "12",
    "TOTAL_QUOTA": "1200",
    "MAX_BPS": "0",
}


def env_keys(path: Path) -> set[str]:
    return {
        match.group(1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if (match := re.fullmatch(r"([A-Z][A-Z0-9_]*)=.*", line))
    }


class WorkflowContractTest(unittest.TestCase):
    def test_root_readme_relative_links_exist(self) -> None:
        readme_path = ROOT / "README.md"
        targets = [
            unquote(target.split("#", 1)[0].strip("<>"))
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", readme_path.read_text(encoding="utf-8"))
            if target and not re.match(r"^(?:https?:|mailto:|#)", target)
        ]
        self.assertTrue(targets)
        for target in targets:
            self.assertTrue((readme_path.parent / target).exists(), target)

    def test_root_readme_is_a_prelaunch_public_entrypoint(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "開發中",
            "主遊戲尚未正式公開",
            "[MIT](LICENSE)",
            "https://github.com/xjustloveux/open-4wd-specs/blob/master/%E8%B3%87%E5%AE%89%E8%A6%8F%E7%AF%84.md#101-reporting",
        ):
            self.assertIn(required, readme)
        self.assertNotIn("https://github.com/xjustloveux/open-4wd/security/policy", readme)
        self.assertNotRegex(readme, r"部署 repo|deployment repo")
        self.assertIn("營運者 fork", readme)

    def test_graphify_release_only_trusts_official_master_push(self) -> None:
        workflow = (ROOT / ".github/workflows/graphify-release.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.event == 'push'", workflow)
        self.assertIn(
            "github.event.workflow_run.head_repository.full_name == github.repository",
            workflow,
        )
        # 守門驗產出：讀 release 自身的 immutable 欄位；不得改回查 repository 設定，
        # administration 不在 GITHUB_TOKEN 可宣告的 permissions 之列。
        self.assertIn("--jq '.immutable'", workflow)
        self.assertIn('if [ "${immutable}" != "true" ]; then', workflow)
        self.assertNotIn("immutable-releases", workflow)

    def test_graphify_specs_token_uses_client_id_without_legacy_app_id(self) -> None:
        workflow = (ROOT / ".github/workflows/graphify-release.yml").read_text(encoding="utf-8")
        self.assertIn(
            "client-id: ${{ vars.OPEN4WD_GRAPH_APP_CLIENT_ID }}",
            workflow,
        )
        self.assertNotRegex(workflow, r"^\s+app-id:")
        self.assertNotIn("OPEN4WD_GRAPH_APP_ID", workflow)

    def test_graphify_release_replays_complete_semantic_cache_through_runner(self) -> None:
        workflow = (ROOT / ".github/workflows/graphify-release.yml").read_text(encoding="utf-8")
        self.assertIn("node scripts/run-graphify-release.mjs", workflow)
        self.assertNotRegex(workflow, r"graphify extract[^\n]*(?:--code-only|--no-cluster)")
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn(
            "node --test scripts/prepare-graphify-release.test.mjs scripts/run-graphify-release.test.mjs",
            ci,
        )

    def test_comment_quality_is_official_only_and_not_a_deploy_dependency(self) -> None:
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("if: github.repository == 'xjustloveux/open-4wd-turn'", ci)
        self.assertIn("python3 scripts/comment_quality_self_test.py", ci)
        self.assertIn("python3 scripts/comment_hook_runner_self_test.py", ci)
        self.assertIn("python3 scripts/comment_quality.py", ci)
        self.assertNotIn("needs: comment-quality", ci)

        deploy = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        self.assertNotIn("comment_quality", deploy)

    def test_deploy_defaults_are_declared_once_at_job_scope(self) -> None:
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        job_header = workflow[: workflow.index("    steps:")]

        for name, default in DEPLOY_DEFAULTS.items():
            expression = "${{ vars.%s || '%s' }}" % (name, default)
            self.assertEqual(workflow.count(expression), 1, name)
            self.assertIn(f"      {name}: {expression}", job_header)

    def test_example_keys_equal_template_keys_plus_signaling_only_turn_urls(self) -> None:
        example = env_keys(ROOT / "deploy/.env.example")
        template_text = "\n".join(
            line
            for line in (ROOT / "config/turnserver.conf.tmpl").read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        template = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)\}", template_text))
        self.assertEqual(example, template | {"TURN_URLS"})

        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("deploy/.env.example", ci[: ci.index("          envsubst <")])

    def test_live_smoke_punches_peer_holes_only_for_the_runner_not_the_template(self) -> None:
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        template = (ROOT / "config/turnserver.conf.tmpl").read_text(encoding="utf-8")
        smoke = ci[ci.index("Live smoke against rendered config") : ci.index("Cleanup smoke container")]

        self.assertIn("--allowed-peer-ip=127.0.0.1", smoke)
        self.assertIn("hostname -I", smoke)
        self.assertIn("turnutils_uclient -W ci-sample-secret -y 127.0.0.1", smoke)
        self.assertNotIn("allowed-peer-ip", template)

    def test_ci_inline_python_reads_files_as_utf8(self) -> None:
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        # runner 是 UTF-8 locale，但內嵌 python 不得依賴它：本機等價執行（cp950 等）也要能跑。
        self.assertNotIn("read_text()", ci)
        self.assertEqual(ci.count("read_text(encoding='utf-8')"), 3)

    def test_all_coturn_image_literals_match_the_authoritative_version(self) -> None:
        image = (ROOT / "deploy/coturn-image.txt").read_text(encoding="utf-8").strip()
        self.assertRegex(image, r"^coturn/coturn:[0-9]+\.[0-9]+\.[0-9]+$")

        targets = [
            ROOT / "deploy/README.md",
            ROOT / "deploy/docker-compose.yml",
            ROOT / "deploy/k8s/deployment.yaml",
            ROOT / ".github/workflows/ci.yml",
            ROOT / ".github/workflows/deploy.yml",
        ]
        literals: list[str] = []
        for target in targets:
            literals.extend(re.findall(r"coturn/coturn:[A-Za-z0-9._-]+", target.read_text("utf-8")))
        self.assertTrue(literals)
        self.assertEqual(set(literals), {image})

        for workflow in targets[-2:]:
            text = workflow.read_text(encoding="utf-8")
            self.assertIn("deploy/coturn-image.txt", text)
            self.assertIn("$COTURN_IMAGE", text)


if __name__ == "__main__":
    unittest.main()
