"""NFR-007 설계서의 규칙마다 대응 테스트가 있어야 한다.

설계서 3절 표에서 규칙 ID 를 긁고, 테스트 코드에서 규칙 ID 를 긁어 대조한다.
사람이 「테스트 다 썼다」고 말하는 대신 이 검사가 센다.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN_DIR = ROOT / "docs" / "design"
TESTS_DIR = Path(__file__).resolve().parent
ID = re.compile(r"\b([A-Z]{3}-R\d{3})\b")
RULE_ROW = re.compile(r"^\|\s*([A-Z]{3}-R\d{3})\s*\|", re.MULTILINE)


def design_rule_ids() -> set[str]:
    ids: set[str] = set()
    for doc in DESIGN_DIR.glob("*.md"):
        text = doc.read_text(encoding="utf-8")
        section = text.split("## 3. 비즈니스 규칙", 1)
        if len(section) == 2:
            rules = section[1].split("\n## ", 1)[0]
            ids |= set(RULE_ROW.findall(rules))
    return ids


def rule_ids_cited_in_tests() -> set[str]:
    ids: set[str] = set()
    for path in TESTS_DIR.rglob("*.py"):
        if path.name == Path(__file__).name:
            continue
        ids |= {i.replace("_", "-").upper() for i in ID.findall(path.read_text(encoding="utf-8"))}
        # 테스트 함수 이름의 qry_r001 꼴도 센다
        ids |= {
            f"{a.upper()}-R{b}"
            for a, b in re.findall(r"\b([a-z]{3})_r(\d{3})", path.read_text(encoding="utf-8"))
        }
    return ids


def test_design_has_rules() -> None:
    """검사가 아무것도 읽지 못한 채 통과하지 않게 한다."""
    assert len(design_rule_ids()) >= 10


def test_every_rule_has_a_test() -> None:
    missing = sorted(design_rule_ids() - rule_ids_cited_in_tests())
    assert not missing, f"테스트가 없는 규칙: {missing}"


def test_tests_do_not_cite_unknown_rules() -> None:
    """오타로 적은 ID 때문에 그 규칙이 영영 안 걸리는 것을 막는다."""
    unknown = sorted(rule_ids_cited_in_tests() - design_rule_ids())
    assert not unknown, f"설계서에 없는 규칙 ID: {unknown}"
