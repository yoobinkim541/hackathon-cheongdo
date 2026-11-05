import json
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def read(rel: str) -> str:
    return (STATIC / rel).read_text(encoding="utf-8")


def test_banner_text():
    html = read("index.html")
    for phrase in ("합성 데이터 전용", "AI 생성 초안", "담당자 검토"):
        assert phrase in html


def test_regions_and_live_region():
    html = read("index.html")
    for rid in ("input", "timeline", "results", "eval"):
        assert f'id="{rid}"' in html
    assert 'aria-live="polite"' in html


def test_responsive_and_touch_targets():
    css = read("style.css")
    assert "max-width: 768px" in css
    assert "min-height: 44px" in css


def test_api_exports():
    js = read("js/api.js")
    for name in ("getCases", "getFeatures", "startRun", "startUpload", "openEvents", "sendApproval", "ask", "startEval", "openEvalEvents"):
        assert re.search(rf"export (const|function|async function) {name}\b", js), name


def test_app_mounts_all_modules():
    js = read("js/app.js")
    for mod in ("timeline", "results", "drafts", "eval", "ask", "media"):
        assert f'from "./{mod}.js"' in js


def test_fake_events_shape():
    events = json.loads(read("dev/fake-events.json"))
    assert events[0]["type"] == "step_started"
    assert events[-1]["type"] == "approval_required"
    for env in events:
        assert {"seq", "type", "step", "mode", "data"} <= env.keys()
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)


def test_no_external_scripts():
    for path in STATIC.rglob("*"):
        if path.suffix in {".html", ".js", ".css"}:
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"<script[^>]+src=\"https?://", text), path
            assert not re.search(r"@import\s+url\(\s*['\"]?https?://", text), path
