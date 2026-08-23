"""TURN 註解 hook 與 local-only setup 的獨立自我測試。"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from comment_hook_runner import run_staged_gate
from setup_comment_hooks import HOOK_NAMES, OWNERSHIP_MARKER, configure_comment_hooks


ROOT = Path(__file__).resolve().parents[1]


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=check, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout


def hook_template(name: str) -> str:
    return (ROOT / ".githooks" / name).read_text(encoding="utf-8")


def installed_hook(root: Path, name: str) -> Path:
    return root / ".git" / "hooks" / name


def config_missing(root: Path, key: str) -> bool:
    probe = subprocess.run(["git", "config", "--local", "--get", key], cwd=root, capture_output=True)
    return probe.returncode != 0


def repository() -> tuple[TemporaryDirectory[str], Path]:
    directory = TemporaryDirectory()
    root = Path(directory.name)
    git(root, "init", "--quiet")
    (root / "deploy").mkdir()
    (root / ".githooks").mkdir()
    for name in HOOK_NAMES:
        (root / ".githooks" / name).write_text(hook_template(name), encoding="utf-8", newline="\n")
    return directory, root


def expect_error(
    action: Callable[[], object], error_type: type[Exception], fragment: str, message: str
) -> None:
    try:
        action()
    except error_type as error:
        assert fragment in str(error), message
    else:
        raise AssertionError(message)


def main() -> None:
    directory, root = repository()
    with directory:
        source = root / "deploy" / "config.yml"
        source.write_text("key: value # TODO: fix\n", encoding="utf-8")
        git(root, "add", "deploy/config.yml")
        source.write_text("key: value # Valid explanation.\n", encoding="utf-8")
        assert run_staged_gate(root, "maintainer", write=lambda _line: None) == 1

        git(root, "add", "deploy/config.yml")
        source.write_text("key: value # TODO: unstaged\n", encoding="utf-8")
        assert run_staged_gate(root, "contributor", write=lambda _line: None) == 0

        expect_error(
            lambda: run_staged_gate(root, None, write=lambda _line: None),
            ValueError,
            "profile",
            "missing profile must fail closed",
        )

        # setup 在 .git/hooks 產生可執行 wrapper、不設 core.hooksPath，且可重複執行。
        configure_comment_hooks(root, "setup", "maintainer")
        configure_comment_hooks(root, "setup", "maintainer")
        assert config_missing(root, "core.hooksPath")
        assert git(root, "config", "--local", "--get", "open4wd.commentProfile").strip() == "maintainer"
        for name in HOOK_NAMES:
            hook = installed_hook(root, name)
            assert hook.read_text(encoding="utf-8") == hook_template(name)
            if os.name != "nt":
                assert hook.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # disable 只移除自有 wrapper 並清 profile。
        configure_comment_hooks(root, "disable", None)
        assert all(not installed_hook(root, name).exists() for name in HOOK_NAMES)
        assert config_missing(root, "open4wd.commentProfile")

        # disable 拒絕移除被改成非 Open4WD 內容的 hook，且不動其他 hook。
        configure_comment_hooks(root, "setup", "maintainer")
        modified = installed_hook(root, "pre-commit")
        modified.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
        expect_error(
            lambda: configure_comment_hooks(root, "disable", None),
            RuntimeError,
            "pre-commit",
            "modified hook must not be removed",
        )
        assert modified.read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"
        assert installed_hook(root, "pre-push").exists()

    legacy_directory, legacy = repository()
    with legacy_directory:
        git(legacy, "config", "--local", "core.hooksPath", ".githooks")
        configure_comment_hooks(legacy, "setup", "contributor")
        assert config_missing(legacy, "core.hooksPath")
        assert all(installed_hook(legacy, name).exists() for name in HOOK_NAMES)

    marked_directory, marked = repository()
    with marked_directory:
        hook = installed_hook(marked, "pre-commit")
        hook.write_text(f"#!/bin/sh\n{OWNERSHIP_MARKER}\nexit 0\n", encoding="utf-8", newline="\n")
        configure_comment_hooks(marked, "setup", "maintainer")
        assert hook.read_text(encoding="utf-8") == hook_template("pre-commit")

    custom_directory, custom = repository()
    with custom_directory:
        git(custom, "config", "--local", "core.hooksPath", "custom-hooks")
        expect_error(
            lambda: configure_comment_hooks(custom, "setup", "contributor"),
            RuntimeError,
            "custom-hooks",
            "custom hooksPath must not be replaced",
        )

    occupied_directory, occupied = repository()
    with occupied_directory:
        hook = installed_hook(occupied, "pre-commit")
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
        expect_error(
            lambda: configure_comment_hooks(occupied, "setup", "maintainer"),
            RuntimeError,
            "pre-commit",
            "existing hooks must not be hidden",
        )

    print("comment hook runner self-test: pass")


if __name__ == "__main__":
    main()
