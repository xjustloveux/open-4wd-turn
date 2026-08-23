"""執行 TURN staged 或全庫註解品質 gate。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

from comment_quality import ROOT, scan_file, scan_text, source_files


PROFILES = {"maintainer", "contributor"}


def git_text(root: Path, arguments: list[str]) -> str:
    """以參數陣列執行唯讀 Git 查詢，失敗時保留可診斷訊息。"""

    result = subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {arguments[0]} failed: {result.stderr.strip()}")
    return result.stdout


def is_source_path(path: str) -> bool:
    """判斷 repo-relative 路徑是否屬現行 TURN scanner inventory。"""

    normalized = path.replace("\\", "/")
    if normalized in {"config/turnserver.conf.tmpl", "deploy/.env.example"}:
        return True
    suffix = Path(normalized).suffix
    return (normalized.startswith("deploy/") and suffix in {".yml", ".yaml", ".py"}) or (
        normalized.startswith(".github/workflows/") and suffix in {".yml", ".yaml"}
    )


def validate_profile(profile: str | None) -> str:
    """確認本機 profile 完整且為受支援值。"""

    if profile not in PROFILES:
        raise ValueError("profile must be maintainer or contributor")
    return profile


def run_staged_gate(root: Path, profile: str | None, write: Callable[[str], None] = print) -> int:
    """只讀取 Git index blob；兩種 Template profile 均使用語言中立規則。"""

    validate_profile(profile)
    paths = git_text(root, ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]).split("\0")
    violations = []
    for relative in filter(None, paths):
        if not is_source_path(relative):
            continue
        text = git_text(root, ["show", f":{relative}"])
        violations.extend(scan_text(text, root / relative, root))
    for violation in violations:
        write(f"{violation.path.relative_to(root)}:{violation.line}: {violation.rule}: {violation.detail}")
    return 1 if violations else 0


def run_full_gate(root: Path, profile: str | None, write: Callable[[str], None] = print) -> int:
    """執行現行 11-file inventory 的完整語言中立掃描。"""

    validate_profile(profile)
    files = source_files(root)
    violations = [violation for path in files for violation in scan_file(path, root)]
    for violation in violations:
        write(f"{violation.path.relative_to(root)}:{violation.line}: {violation.rule}: {violation.detail}")
    write(f"comment-quality: scanned {len(files)} file(s), {len(violations)} finding(s)")
    return 1 if violations else 0


def main() -> int:
    """由 Git hook 讀取 repo-local profile 後執行 staged 或 full gate。"""

    action = sys.argv[1] if len(sys.argv) > 1 else ""
    profile = git_text(ROOT, ["config", "--local", "--get", "open4wd.commentProfile"]).strip()
    if action == "staged":
        return run_staged_gate(ROOT, profile)
    if action == "full":
        return run_full_gate(ROOT, profile)
    print("usage: comment_hook_runner.py staged|full", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
