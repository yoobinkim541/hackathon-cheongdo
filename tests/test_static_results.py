from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
SECTION_IDS = (
    "record.basic_info", "record.summary", "record.needs", "record.linked_schemes", "record.follow_up",
    "referral.agency", "referral.subject", "referral.schemes", "referral.officer",
)


def read(rel: str) -> str:
    return (STATIC / rel).read_text(encoding="utf-8")


def test_all_section_ids_in_drafts():
    js = read("js/drafts.js")
    for sid in SECTION_IDS:
        assert f'"{sid}"' in js


def test_approval_sends_edited_sections():
    js = read("js/drafts.js")
    assert "sendApproval" in js
    assert "edited_sections" in js
    assert "request_id" in js


def test_results_labels():
    js = read("js/results.js")
    for phrase in ("검증에서 제외됨", "AI 초안", "규칙 판정", "확인 필요", "규칙으로 보완"):
        assert phrase in js


def test_dialog_is_modal():
    html = read("index.html")
    assert "<dialog" in html and 'aria-modal="true"' in html


def test_print_css():
    assert "@media print" in read("print.css")
