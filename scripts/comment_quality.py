"""手動檢查 TURN 第一方設定與部署檔中的註解品質。"""

from __future__ import annotations

import re
import tokenize
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TODO_PATTERN = re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
DATED_HISTORY_PATTERN = re.compile(r"\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b")
DOC_REFERENCE_PATTERN = re.compile(r"(?<![\w:/.-])([\w./-]+\.md)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Comment:
    """單一來源檔中的註解文字與行號。"""

    line: int
    text: str


@dataclass(frozen=True)
class Violation:
    """可供終端輸出的註解品質違規。"""

    path: Path
    line: int
    rule: str
    detail: str


def python_comments_text(text: str) -> list[Comment]:
    """以 Python tokenizer 從文字取出真正的註解。"""

    return [
        Comment(token.start[0], token.string[1:].strip())
        for token in tokenize.tokenize(BytesIO(text.encode("utf-8")).readline)
        if token.type == tokenize.COMMENT
    ]


def unquoted_comment_index(line: str) -> int | None:
    """找出設定檔行中不在單、雙引號內的第一個井字號。"""

    quote: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote == '"':
            escaped = True
            continue
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            continue
        if character == "#" and quote is None:
            return index
    return None


def hash_comments_text(text: str) -> list[Comment]:
    """從文字取出 YAML、env 與 coturn template 中未被引號包住的註解。"""

    comments: list[Comment] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        index = unquoted_comment_index(line)
        if index is not None:
            comments.append(Comment(line_number, line[index + 1 :].strip()))
    return comments


def comments_for_text(text: str, path: Path) -> list[Comment]:
    """依來源格式選用不會把字串誤認成註解的解析方式。"""

    if path.suffix == ".py":
        return python_comments_text(text)
    return hash_comments_text(text)


def reference_exists(reference: str, source: Path, root: Path) -> bool:
    """確認相對文件指向可由 repo 根或來源檔目錄解析。"""

    normalized = reference.replace("\\", "/")
    candidates = (root / normalized, source.parent / normalized)
    return any(candidate.resolve().is_relative_to(root.resolve()) and candidate.is_file() for candidate in candidates)


def scan_text(text: str, path: Path, root: Path = ROOT) -> list[Violation]:
    """直接檢查來源文字，供工作樹檔案與 Git index blob 共用。"""

    violations: list[Violation] = []
    for comment in comments_for_text(text, path):
        if TODO_PATTERN.search(comment.text):
            violations.append(Violation(path, comment.line, "todo-marker", "移除待辦式註解或建立正式追蹤項目"))
        if DATED_HISTORY_PATTERN.search(comment.text):
            violations.append(Violation(path, comment.line, "dated-history", "將日期式變更紀錄移至版本歷史"))
        for match in DOC_REFERENCE_PATTERN.finditer(comment.text):
            reference = match.group(1)
            if not reference_exists(reference, path, root):
                violations.append(
                    Violation(path, comment.line, "stale-doc-reference", f"找不到註解引用的文件 {reference}")
                )
    return violations


def scan_file(path: Path, root: Path = ROOT) -> list[Violation]:
    """檢查單一實體來源檔，並委派給文字層掃描器。"""

    return scan_text(path.read_text(encoding="utf-8"), path, root)


def source_files(root: Path = ROOT) -> list[Path]:
    """列出本檢核納管的第一方設定、部署與 Python 檔案。"""

    candidates = [root / "config/turnserver.conf.tmpl", root / "deploy/.env.example"]
    candidates.extend((root / "deploy").rglob("*.yml"))
    candidates.extend((root / "deploy").rglob("*.yaml"))
    candidates.extend((root / "deploy").rglob("*.py"))
    candidates.extend((root / ".github/workflows").glob("*.yml"))
    candidates.extend((root / ".github/workflows").glob("*.yaml"))
    return sorted({path for path in candidates if path.is_file()})


def main() -> int:
    """執行實庫掃描，發現任何違規時以非零狀態結束。"""

    files = source_files()
    violations = [violation for path in files for violation in scan_file(path)]
    for violation in violations:
        relative = violation.path.relative_to(ROOT)
        print(f"{relative}:{violation.line}: {violation.rule}: {violation.detail}")
    print(f"comment-quality: scanned {len(files)} file(s), {len(violations)} finding(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
