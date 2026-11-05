import struct

import pytest

from app import limits
from app.config import MAX_AUDIO_BYTES, MAX_IMAGE_BYTES, MAX_TEXT_CHARS
from app.masking import find_residual, mask
from app.render import render_final
from app.schemas import (
    AuditEntry,
    ConditionResult,
    DecisionRecord,
    DraftDocuments,
    DraftSection,
    MatchResult,
    MatchSubmission,
    Recommendation,
    Scheme,
)
from app.textnum import fix_ocr_digits, new_numbers, parse_numbers
from app.verify import check_citations, coverage_gaps, verify


# ---------- masking ----------

def test_mask_rrn_phone_account_address_name():
    text = (
        "박순자 어르신(450312-2123456) 연락처 010-1234-5678, 집 054-371-1234. "
        "계좌 351-1234-5678-93. 청도군 화양읍 범곡리 312-5번지, 아파트 101동 1203호, 화양로 12."
    )
    r = mask(text)
    for leaked in ("박순자", "450312-2123456", "010-1234-5678", "054-371-1234", "351-1234-5678-93",
                   "312-5번지", "101동 1203호", "화양로 12"):
        assert leaked not in r.text
    assert "[이름1] 어르신" in r.text
    assert "[주민번호1]" in r.text and "[전화1]" in r.text and "[전화2]" in r.text
    assert "[계좌1]" in r.text and "[주소1]" in r.text
    assert r.residual == []
    kinds = {s.kind for s in r.spans}
    assert kinds == {"rrn", "phone", "account", "address", "name"}
    first = r.spans[0]
    assert text[first.start:first.end] == "박순자"


def test_mask_placeholder_reuse_and_known():
    known: dict[str, str] = {}
    r = mask("정민호 씨는 혼자 산다. 정민호 씨 번호 010-2222-3333, 다시 010-2222-3333.", known=known)
    assert r.text.count("[이름1]") == 2
    assert r.text.count("[전화1]") == 2
    assert "[전화2]" not in r.text
    r2 = mask("이춘식 님 전화 010-2222-3333", known=known)
    assert "[전화1]" in r2.text
    assert "[이름2] 님" in r2.text


def test_mask_names_list_and_non_names():
    r = mask("최영호가 말했다. 이웃 할머니가 도와준다. 아저씨가 왔다.", names=["최영호"])
    assert r.text.startswith("[이름1]가")
    assert "이웃 할머니" in r.text and "아저씨" in r.text


def test_mask_korean_digit_phone():
    r = mask("번호는 공일공 일이삼사 오육칠팔이에요")
    assert "[전화1]" in r.text
    assert "일이삼사" not in r.text
    assert r.text.endswith("이에요")


def test_mask_digit_run_and_ocr_fix():
    assert fix_ocr_digits("O1O-l234-5678") == "010-1234-5678"
    assert fix_ocr_digits("Oil 3O만 l번") == "Oil 30만 l번"
    r = mask("전화 O1O-l234-5678", source="image")
    assert r.text == "전화 [전화1]"
    r2 = mask("전화 01012345678 입니다")
    assert r2.text == "전화 [전화1] 입니다"


def test_mask_keeps_amounts_and_dates():
    r = mask("2026-11-05 방문. 병원비로 30만 원, 월세 25만 원.")
    assert "30만 원" in r.text and "2026-11-05" in r.text
    assert r.spans == []


def test_find_residual():
    assert find_residual("[전화1] 연락") == []
    assert find_residual("주민 4503122123456") == ["4503122123456"]


# ---------- textnum ----------

def test_parse_korean_numerals():
    assert 300000 in parse_numbers("월세 삼십만 원")
    assert 75 in parse_numbers("칠십오 세 어르신")
    assert 120_000_000 in parse_numbers("재산 1억 2천만 원")
    assert 300000 in parse_numbers("30만원")
    assert 1_250_000 in parse_numbers("소득 1,250,000원")
    assert {2, 3} <= parse_numbers("두 명이 산다. 세 식구")
    assert 305000 in parse_numbers("삼십만 오천 원")


def test_parse_ignores_words_and_placeholders():
    assert parse_numbers("[전화1] 오늘 이웃 사회 구청 일이 많다") == set()


def test_new_numbers():
    assert new_numbers("월세 삼십만 원, 칠십오 세", "월세 300,000원, 75세") == set()
    assert new_numbers("월세 삼십만 원", "월세 35만 원, 80세") == {350000, 80}


# ---------- verify ----------

def _decision(did, sid, status="eligible", domain="living", source="tool", missing=None):
    return DecisionRecord(
        decision_id=did, source=source, step=f"match_{domain}", scheme_id=sid, scheme_name=f"{sid} 이름",
        domain=domain, status=status,
        conditions=[ConditionResult(id="c1", label="나이", met=True), ConditionResult(id="c2", label="소득", met=None)],
        missing_fields=missing or [], source_url="https://example.org",
    )


def _scheme(sid, domain="living"):
    return Scheme(id=sid, name=sid, domain=domain, summary="", rule="r", required_fields=[],
                  source_url="https://example.org", checked_at="2026-11-05")


def _rec(sid, did, cids=("c1",), priority=1):
    return Recommendation(scheme_id=sid, decision_id=did, condition_ids=list(cids), explanation="설명", priority=priority)


def test_coverage_gaps():
    decisions = {"d1": _decision("d1", "s1")}
    schemes = [_scheme("s1"), _scheme("s2"), _scheme("h1", "health")]
    assert coverage_gaps("living", decisions, schemes) == ["s2"]


def test_check_citations_reasons():
    decisions = {"d1": _decision("d1", "s1"), "d2": _decision("d2", "s2", status="ineligible"),
                 "d3": _decision("d3", "h1", domain="health")}
    assert check_citations(_rec("s1", "d1"), decisions, "living") is None
    assert "없는 판정" in check_citations(_rec("s1", "d9"), decisions, "living")
    assert "s2" in check_citations(_rec("s2", "d1"), decisions, "living")
    assert "분야" in check_citations(_rec("h1", "d3"), decisions, "living")
    assert "조건 ID" in check_citations(_rec("s1", "d1", ("c9",)), decisions, "living")
    assert "대상 아님" in check_citations(_rec("s2", "d2"), decisions, "living")


def test_verify_rules_and_fill():
    decisions = {
        "d1": _decision("d1", "s1"),
        "d2": _decision("d2", "s2", status="unknown", missing=["monthly_income_krw"]),
        "d3": _decision("d3", "s3", status="ineligible"),
        "d4": _decision("d4", "s4", source="verifier"),
        "d5": _decision("d5", "h1", domain="health", source="verifier", status="unknown", missing=["age"]),
    }
    matches = [
        MatchResult(domain="living", status="ok", submission=MatchSubmission(recommendations=[
            _rec("s1", "d1"), _rec("s2", "d2", ("c2",), priority=2), _rec("s1", "d9"),
        ])),
        MatchResult(domain="health", status="failed", error_code="timeout"),
    ]
    audit = {"match_living": [AuditEntry(tool="check_eligibility", decision_id="d1", has_result=True)]}
    schemes = [_scheme("s1"), _scheme("s2"), _scheme("s3"), _scheme("s4"), _scheme("h1", "health")]
    r = verify(matches, decisions, audit, {"match_living": True}, schemes)
    reasons = {(x.scheme_id, x.decision_id): x.reason for x in r.removed}
    assert "받지 않은" in reasons[("s2", "d2")]
    assert "없는 판정" in reasons[("s1", "d9")]
    assert [i.scheme_id for i in r.eligible] == ["s1", "s4"]
    assert r.eligible[0].source == "model" and r.eligible[0].explanation == "설명"
    assert r.eligible[1].source == "verifier"
    assert [i.scheme_id for i in r.unknown] == ["s2", "h1"]
    assert r.unknown[0].follow_up_questions == ["월 소득을 확인해야 합니다"]
    assert r.unknown[1].follow_up_questions == ["나이를 확인해야 합니다"]
    assert [i.scheme_id for i in r.ineligible] == ["s3"]
    assert r.failed_domains == ["health"]
    assert r.verifier_filled == ["s4", "h1"]
    assert r.audit_rule_skipped == []


def test_verify_rule7_skipped_when_audit_incomplete():
    decisions = {"d1": _decision("d1", "s1")}
    matches = [MatchResult(domain="living", status="ok",
                           submission=MatchSubmission(recommendations=[_rec("s1", "d1")]))]
    r = verify(matches, decisions, {"match_living": []}, {"match_living": False}, [_scheme("s1")])
    assert r.removed == []
    assert r.eligible[0].source == "model"
    assert r.audit_rule_skipped == ["match_living"]


# ---------- render ----------

def _verified():
    decisions = {"d1": _decision("d1", "s1"), "d2": _decision("d2", "s2", status="ineligible")}
    return verify([], decisions, {}, {}, [_scheme("s1"), _scheme("s2")])


def test_render_subset_check():
    draft = DraftDocuments(sections=[])
    with pytest.raises(ValueError):
        render_final(draft, {}, _verified(), ["s2"], "2026-11-05T15:00:00+09:00")


def test_render_edited_override():
    draft = DraftDocuments(sections=[
        DraftSection(id="record.summary", text="초안 요약"),
        DraftSection(id="record.needs", text="초안 욕구"),
        DraftSection(id="referral.schemes", text="초안 제도"),
    ])
    edited = {"record.summary": "고친 요약", "referral.schemes": "담당자 메모"}
    final = render_final(draft, edited, _verified(), ["s1"], "2026-11-05T15:00:00+09:00")
    record = {s.id: s for s in final.record}
    referral = {s.id: s for s in final.referral}
    assert len(final.record) == 5 and len(final.referral) == 4
    assert record["record.summary"].text == "고친 요약"
    assert record["record.summary"].title == "상담 내용 요약"
    assert record["record.needs"].text == "초안 욕구"
    assert record["record.basic_info"].text == ""
    text = referral["referral.schemes"].text
    assert text.startswith("담당자 메모\n\n- s1 이름")
    assert "c1" in text and "초안 제도" not in text
    assert final.scheme_ids == ["s1"]


# ---------- limits ----------

def _wav(seconds: float, rate: int = 8000) -> bytes:
    data = b"\x00" * int(rate * 2 * seconds)
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    body = b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data
    return b"RIFF" + struct.pack("<I", len(body)) + body


def test_check_text():
    assert limits.check_text("") is not None
    assert limits.check_text("   ") is not None
    assert limits.check_text("가" * (MAX_TEXT_CHARS + 1)) is not None
    assert limits.check_text("메모") is None


def test_sniff_media():
    assert limits.sniff_media(b"\xff\xd8\xff\xe0rest") == "jpeg"
    assert limits.sniff_media(b"\x89PNG\r\n\x1a\nxxxx") == "png"
    assert limits.sniff_media(_wav(0.01)[:16]) == "wav"
    assert limits.sniff_media(b"ID3\x03") == "mp3"
    assert limits.sniff_media(b"\xff\xfb\x90") == "mp3"
    assert limits.sniff_media(b"\x1a\x45\xdf\xa3") == "webm"
    assert limits.sniff_media(b"OggS\x00") == "ogg"
    assert limits.sniff_media(b"hello") is None


def test_check_media():
    assert limits.check_media("image", b"\x89PNG\r\n\x1a\n" + b"0" * 10) == (None, "png")
    err, fmt = limits.check_media("image", b"ID3" + b"0" * 10)
    assert err and fmt == "mp3"
    err, _ = limits.check_media("image", b"\xff\xd8\xff" + b"0" * MAX_IMAGE_BYTES)
    assert err
    err, _ = limits.check_media("audio", b"OggS" + b"0" * MAX_AUDIO_BYTES)
    assert err
    assert limits.check_media("audio", _wav(1.0)) == (None, "wav")
    err, fmt = limits.check_media("audio", _wav(121.0, rate=8000))
    assert err and "2분" in err and fmt == "wav"
    err, _ = limits.check_media("video", b"OggS")
    assert err
