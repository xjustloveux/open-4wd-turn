"""註解品質檢核器的獨立自我測試。"""

from pathlib import Path
from tempfile import TemporaryDirectory

from comment_quality import scan_file, scan_text


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def rule_names(path: Path, root: Path) -> set[str]:
    return {violation.rule for violation in scan_file(path, root)}


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "README.md").write_text("# fixture\n", encoding="utf-8")

        accepted = write(
            root,
            "deploy/accepted.py",
            '# 繁體中文註解可通過。\n# English comments are also accepted.\nVALUE = "# TODO is data"\n',
        )
        assert not scan_file(accepted, root)

        todo = write(root, "deploy/todo.yaml", "key: value # TODO: replace later\n")
        assert "todo-marker" in rule_names(todo, root)

        history = write(root, "config/history.conf.tmpl", "# 2026-08-13 changed default\n")
        assert "dated-history" in rule_names(history, root)

        stale = write(root, "deploy/stale.yml", "# See docs/missing.md before editing.\n")
        assert "stale-doc-reference" in rule_names(stale, root)

        current = write(root, "deploy/current.yml", "# See README.md before editing.\n")
        assert not scan_file(current, root)

        staged_path = root / "deploy/staged.yml"
        assert {violation.rule for violation in scan_text("key: value # TODO: fix\n", staged_path, root)} == {
            "todo-marker"
        }

    print("comment-quality self-test: pass")


if __name__ == "__main__":
    main()
