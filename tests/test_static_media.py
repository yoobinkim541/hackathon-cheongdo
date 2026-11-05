from pathlib import Path

JS = (Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "media.js").read_text(encoding="utf-8")


def test_feature_flags_checked():
    for flag in ("features.image_input", "features.audio_input", "features.browser_recording"):
        assert flag in JS


def test_recorder_stops_at_120s():
    assert "MediaRecorder" in JS
    assert "120000" in JS


def test_mic_denied_message():
    assert "녹음 권한이 없어 파일 올리기를 이용하세요" in JS


def test_rerun_with_origin():
    assert "origin_run_id" in JS


def test_labels():
    assert "정리 생략" in JS and "확인 필요" in JS
