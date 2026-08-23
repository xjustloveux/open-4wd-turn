"""安全設定或停用 TURN repo-local 註解 hooks。"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROFILES = {"maintainer", "contributor"}
HOOK_NAMES = ("pre-commit", "pre-push")
OWNERSHIP_MARKER = "# Open4WD 管理的本機註解品質 hook。"
ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class HookFile:
    """單一 hook 的版控 template 與目前 clone 的安裝位置。"""

    name: str
    source: Path
    target: Path


def git(root: Path, arguments: list[str], required: bool = True) -> str | None:
    """執行 local Git 操作；optional query 不存在時回傳 None。"""

    result = subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if result.returncode != 0:
        if required:
            raise RuntimeError(result.stderr.strip() or f"git {arguments[0]} failed")
        return None
    return result.stdout.strip()


def hook_files(root: Path) -> list[HookFile]:
    """以 git rev-parse 解析 hooks 目錄，一般 clone 與 worktree 皆適用。"""

    git_dir = Path(git(root, ["rev-parse", "--git-dir"]))
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    return [HookFile(name, root / ".githooks" / name, git_dir / "hooks" / name) for name in HOOK_NAMES]


def read_templates(files: list[HookFile]) -> dict[str, str]:
    """讀取版控中的 hook template；缺檔即失敗，不產生空 hook。"""

    return {file.name: file.source.read_text(encoding="utf-8") for file in files}


def assert_owned_or_absent(files: list[HookFile], templates: dict[str, str]) -> None:
    """只允許覆寫或移除缺席、與 template 相同或帶 Open4WD 標記的 hook。"""

    for file in files:
        if not file.target.exists():
            continue
        current = file.target.read_text(encoding="utf-8")
        if current != templates[file.name] and OWNERSHIP_MARKER not in current.splitlines():
            raise RuntimeError(f"refusing to replace or remove non-Open4WD Git hook: {file.name}")


def install_hook(target: Path, content: str) -> None:
    """寫入 hook 並設為可執行；版控 template 因此不需攜帶 executable mode。"""

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    os.chmod(target, 0o755)


def configure_comment_hooks(root: Path, action: str, profile: str | None) -> None:
    """設定或停用目前 clone 的 opt-in 註解 hooks，不觸碰全域 Git 設定。"""

    current = git(root, ["config", "--local", "--get", "core.hooksPath"], required=False)
    files = hook_files(root)
    templates = read_templates(files)
    if action == "disable":
        assert_owned_or_absent(files, templates)
        for file in files:
            if file.target.exists():
                file.target.unlink()
        if current == ".githooks":
            git(root, ["config", "--local", "--unset-all", "core.hooksPath"])
        git(root, ["config", "--local", "--unset-all", "open4wd.commentProfile"], required=False)
        return
    if action != "setup":
        raise ValueError("action must be setup or disable")
    if profile not in PROFILES:
        raise ValueError("profile must be maintainer or contributor")
    if current and current != ".githooks":
        raise RuntimeError(f"refusing to replace custom core.hooksPath: {current}")
    assert_owned_or_absent(files, templates)
    for file in files:
        install_hook(file.target, templates[file.name])
    if current == ".githooks":
        git(root, ["config", "--local", "--unset-all", "core.hooksPath"])
    git(root, ["config", "--local", "--replace-all", "open4wd.commentProfile", profile])


def main() -> int:
    """解析 setup／disable CLI 參數。"""

    action = sys.argv[1] if len(sys.argv) > 1 else ""
    profile = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        configure_comment_hooks(ROOT, action, profile)
    except (RuntimeError, ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"comment hooks enabled ({profile})" if action == "setup" else "comment hooks disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
