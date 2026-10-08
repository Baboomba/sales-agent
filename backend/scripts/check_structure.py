"""서버 코드의 모양을 본다 — 린트 · 타입 · 계층 계약이 못 막는 규칙.

규칙과 장치의 표는 docs/convention/enforcement.md 다. 구조 규칙은 테스트로 지키지 않고
검사 장치에 둔다 (testing 9절). 어긴 곳을 모두 적고 실패한다.

    uv run python scripts/check_structure.py
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterator
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
CODE_DIRS = ("app", "tests", "scripts", "evaluation")
SUPPRESSION = re.compile(r"#\s*(noqa|type:\s*ignore)\b")
RULE_ID = re.compile(r"\b[A-Z]{3}-R\d{3}\b")
FAKE_PREFIXES = ("Fake", "Scripted", "Stub", "Spy")


def python_files(*dirs: str) -> Iterator[Path]:
    for name in dirs:
        yield from sorted((BACKEND / name).rglob("*.py"))


def rel(path: Path) -> str:
    return str(path.relative_to(BACKEND))


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def suppression_comments() -> Iterator[str]:
    """경고를 끄는 주석을 쓰지 않는다 (code-style 1.1). 끄려면 설정에서 이유와 함께 끈다."""
    for path in python_files(*CODE_DIRS):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if SUPPRESSION.search(line):
                yield f"{rel(path)}:{number} 경고를 끄는 주석 — 설정에서 이유와 함께 끈다"


def _is_frozen_dataclass(node: ast.ClassDef) -> bool:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or getattr(decorator.func, "id", "") != "dataclass":
            continue
        for keyword in decorator.keywords:
            if keyword.arg == "frozen" and getattr(keyword.value, "value", False) is True:
                return True
    return False


def _is_enum(node: ast.ClassDef) -> bool:
    return any(getattr(base, "id", "") == "Enum" for base in node.bases)


def model_shapes() -> Iterator[str]:
    """모델은 메서드 없는 @dataclass(frozen=True) 이거나 열거다 (code-architecture 2.1)."""
    for path in sorted(BACKEND.glob("app/*/model/*.py")):
        for node in parse(path).body:
            if not isinstance(node, ast.ClassDef):
                continue
            where = f"{rel(path)}:{node.lineno} {node.name}"
            if not (_is_frozen_dataclass(node) or _is_enum(node)):
                yield f"{where} 모델은 @dataclass(frozen=True) 이거나 열거여야 한다"
            if any(isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) for item in node.body):
                yield f"{where} 모델에 메서드를 두지 않는다 — 판단은 규칙에 둔다"


def rule_docstrings() -> Iterator[str]:
    """규칙의 공개 함수는 문서 문자열 첫 줄에 규칙 ID 를 적는다 (code-architecture 2.2)."""
    for path in sorted(BACKEND.glob("app/*/rules/*.py")):
        for node in parse(path).body:
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            first = (ast.get_docstring(node) or "").splitlines()[:1]
            if not first or not RULE_ID.search(first[0]):
                yield f"{rel(path)}:{node.lineno} {node.name} 문서 문자열 첫 줄에 규칙 ID 가 없다"


def _branches(node: ast.AST) -> Iterator[ast.stmt]:
    """테스트 흐름 안의 if · 반복. 테스트 안에 정의한 함수(기록 콜백 등)의 속은 보지 않는다."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        if isinstance(child, ast.If | ast.For | ast.AsyncFor | ast.While):
            yield child
        yield from _branches(child)


def test_branches() -> Iterator[str]:
    """테스트 함수에 if · 반복을 넣지 않는다 — 여러 경우는 매개변수로 나눈다 (testing 5)."""
    for path in sorted((BACKEND / "tests").rglob("test_*.py")):
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "test_"
            ):
                for branch in _branches(node):
                    kind = type(branch).__name__
                    yield f"{rel(path)}:{branch.lineno} {node.name} 테스트 안의 {kind}"


def integration_marks() -> Iterator[str]:
    """통합 테스트는 pytestmark = pytest.mark.integration 을 단다 (testing 7.1)."""
    for path in sorted((BACKEND / "tests" / "integration").glob("test_*.py")):
        if "pytestmark = pytest.mark.integration" not in path.read_text(encoding="utf-8"):
            yield f"{rel(path)} 통합 테스트 표시(pytestmark = pytest.mark.integration)가 없다"


def fake_places() -> Iterator[str]:
    """가짜는 tests/<도메인>/fake.py 한 곳에 둔다 (testing 7.1)."""
    for path in python_files("tests"):
        if path.name == "fake.py" and path.parent.parent == BACKEND / "tests":
            continue
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.ClassDef) and node.name.startswith(FAKE_PREFIXES):
                yield f"{rel(path)}:{node.lineno} {node.name} 가짜는 tests/<도메인>/fake.py 에 둔다"


CHECKS = (
    suppression_comments,
    model_shapes,
    rule_docstrings,
    test_branches,
    integration_marks,
    fake_places,
)


def main() -> int:
    problems = [problem for check in CHECKS for problem in check()]
    for problem in problems:
        print(problem)
    if problems:
        print(f"\n구조 검사 실패 — {len(problems)}곳")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
