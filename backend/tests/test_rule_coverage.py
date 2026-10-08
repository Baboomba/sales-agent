"""NFR-007 설계서의 규칙마다 대응 테스트가 있어야 한다.

설계서 3절(규칙)과 4절(테스트 사항)에서 규칙 ID 를 긁고, 테스트 함수의 이름과 문서 문자열에서
규칙 ID 를 긁어 대조한다. 사람이 「테스트 다 썼다」고 말하는 대신 이 검사가 센다.

주석 · 가짜 모듈 · 보조 함수에 적힌 ID 는 세지 않는다. 테스트를 지우고 주석만 남아도
「덮였다」로 세던 빈틈을 감사 1차(#17)가 찾았다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN_DIR = ROOT / "docs" / "design"
TESTS_DIR = Path(__file__).resolve().parent
ID = re.compile(r"\b([A-Z]{3}-R\d{3})\b")
NAME_ID = re.compile(r"(?:^|_)([a-z]{3})_r(\d{3})(?:_|$)")
ROW = re.compile(r"^\|\s*([A-Z]{3}-R\d{3})\s*\|", re.MULTILINE)


def _section(text: str, heading: str) -> str:
    parts = text.split(heading, 1)
    return parts[1].split("\n## ", 1)[0] if len(parts) == 2 else ""


def design_ids(heading: str) -> set[str]:
    ids: set[str] = set()
    for doc in DESIGN_DIR.glob("*.md"):
        ids |= set(ROW.findall(_section(doc.read_text(encoding="utf-8"), heading)))
    return ids


def rule_ids_in_source(source: str) -> set[str]:
    """테스트 함수(test_*)의 이름과 문서 문자열에 적힌 ID 만 센다."""
    ids: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test_"
        ):
            ids |= {f"{a.upper()}-R{b}" for a, b in NAME_ID.findall(node.name)}
            ids |= set(ID.findall(ast.get_docstring(node) or ""))
    return ids


def rule_ids_cited_in_tests() -> set[str]:
    ids: set[str] = set()
    for path in TESTS_DIR.rglob("test_*.py"):
        if path.name != Path(__file__).name:
            ids |= rule_ids_in_source(path.read_text(encoding="utf-8"))
    return ids


# --- 검사 ------------------------------------------------------------------


def test_design_has_rules() -> None:
    """검사가 아무것도 읽지 못한 채 통과하지 않게 한다."""
    assert len(design_ids("## 3. 비즈니스 규칙")) >= 10


def test_every_rule_has_a_test_item() -> None:
    """3절의 규칙과 4절의 테스트 사항이 같은 ID 묶음이다."""
    rules = design_ids("## 3. 비즈니스 규칙")
    items = design_ids("## 4. 테스트 사항")
    assert rules == items, f"3절에만: {sorted(rules - items)}, 4절에만: {sorted(items - rules)}"


def test_every_rule_has_a_test() -> None:
    missing = sorted(design_ids("## 3. 비즈니스 규칙") - rule_ids_cited_in_tests())
    assert not missing, f"테스트가 없는 규칙: {missing}"


def test_tests_do_not_cite_unknown_rules() -> None:
    """오타로 적은 ID 때문에 그 규칙이 영영 안 걸리는 것을 막는다."""
    unknown = sorted(rule_ids_cited_in_tests() - design_ids("## 3. 비즈니스 규칙"))
    assert not unknown, f"설계서에 없는 규칙 ID: {unknown}"


# --- 검사기 자신 ------------------------------------------------------------


def test_counts_test_names_and_docstrings_only() -> None:
    """주석 · 보조 함수 · 문자열 값에 적힌 ID 는 세지 않는다."""
    source = '''
# --- ZZZ-R001 주석
def helper():
    """ZZZ-R002 보조 함수"""

def test_zzz_r003_by_name():
    value = "ZZZ-R004"

async def test_by_docstring():
    """ZZZ-R005 문서 문자열"""
'''
    assert rule_ids_in_source(source) == {"ZZZ-R003", "ZZZ-R005"}
