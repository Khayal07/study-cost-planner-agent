"""Tests for the transcript-analysis and voice-transcription upload endpoints."""
from __future__ import annotations

import io
from datetime import date

from app.api import transcribe as transcribe_api
from app.core.config import settings
from app.services import transcript as transcript_service

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


def _register(client, email="uploads@t.com"):
    token = client.post(
        "/auth/register", json={"email": email, "password": "secret123"}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _reset_voice_counter():
    transcribe_api._calls["day"] = date.min
    transcribe_api._calls["count"] = 0


# --- transcript analysis ---

def test_transcript_requires_auth(client):
    resp = client.post("/profile/transcript", files={"file": ("t.png", io.BytesIO(PNG), "image/png")})
    assert resp.status_code in (401, 403)


def test_transcript_rejects_bad_type(client, monkeypatch):
    monkeypatch.setattr(transcript_service.llm, "enabled", True)
    auth = _register(client)
    resp = client.post(
        "/profile/transcript",
        files={"file": ("t.gif", io.BytesIO(b"GIF89a" + b"\x00" * 32), "image/gif")},
        headers=auth,
    )
    assert resp.status_code == 415


def test_transcript_rejects_magic_byte_mismatch(client, monkeypatch):
    monkeypatch.setattr(transcript_service.llm, "enabled", True)
    auth = _register(client, email="magic@t.com")
    # Declared PNG, actually a PDF.
    resp = client.post(
        "/profile/transcript",
        files={"file": ("t.png", io.BytesIO(b"%PDF-1.4" + b"\x00" * 32), "image/png")},
        headers=auth,
    )
    assert resp.status_code == 415


def test_transcript_rejects_oversize(client, monkeypatch):
    monkeypatch.setattr(transcript_service.llm, "enabled", True)
    auth = _register(client, email="big@t.com")
    big = PNG + b"\x00" * settings.transcript_max_bytes
    resp = client.post(
        "/profile/transcript",
        files={"file": ("t.png", io.BytesIO(big), "image/png")},
        headers=auth,
    )
    assert resp.status_code == 413


def test_transcript_503_when_llm_disabled(client, monkeypatch):
    monkeypatch.setattr(transcript_service.llm, "enabled", False)
    auth = _register(client, email="nollm@t.com")
    resp = client.post(
        "/profile/transcript",
        files={"file": ("t.png", io.BytesIO(PNG), "image/png")},
        headers=auth,
    )
    assert resp.status_code == 503


def test_transcript_extraction_validated(client, monkeypatch):
    monkeypatch.setattr(transcript_service.llm, "enabled", True)
    monkeypatch.setattr(
        transcript_service.llm,
        "complete_json_content",
        lambda *a, **k: {
            "gpa": "87",
            "gpa_scale": 100,
            "gpa_on_4_scale": 3.48,
            "degree_level": "bachelor",
            "institution": "Baku State University",
            "confidence": "high",
        },
    )
    auth = _register(client, email="ok@t.com")
    resp = client.post(
        "/profile/transcript",
        files={"file": ("t.png", io.BytesIO(PNG), "image/png")},
        headers=auth,
    )
    assert resp.status_code == 200
    ex = resp.json()["extraction"]
    assert ex["gpa_on_4_scale"] == 3.48
    assert ex["degree_level"] == "bachelor"


def test_transcript_out_of_range_values_dropped(client, monkeypatch):
    monkeypatch.setattr(transcript_service.llm, "enabled", True)
    monkeypatch.setattr(
        transcript_service.llm,
        "complete_json_content",
        lambda *a, **k: {"gpa_on_4_scale": 7.5, "degree_level": "wizard", "confidence": "sky-high"},
    )
    auth = _register(client, email="range@t.com")
    resp = client.post(
        "/profile/transcript",
        files={"file": ("t.png", io.BytesIO(PNG), "image/png")},
        headers=auth,
    )
    ex = resp.json()["extraction"]
    assert ex["gpa_on_4_scale"] is None
    assert ex["degree_level"] is None
    assert ex["confidence"] == "low"


# --- voice transcription ---

def test_transcribe_rejects_bad_type(client, monkeypatch):
    monkeypatch.setattr(transcribe_api.llm, "enabled", True)
    monkeypatch.setattr(type(transcribe_api.llm), "use_openai", property(lambda self: True), raising=False)
    _reset_voice_counter()
    resp = client.post(
        "/chat/transcribe",
        files={"file": ("a.mp3", io.BytesIO(b"ID3" + b"\x00" * 32), "audio/mpeg")},
    )
    assert resp.status_code == 415


def test_transcribe_happy_path(client, monkeypatch):
    monkeypatch.setattr(transcribe_api.llm, "enabled", True)
    monkeypatch.setattr(type(transcribe_api.llm), "use_openai", property(lambda self: True), raising=False)
    monkeypatch.setattr(transcribe_api.llm, "transcribe", lambda data, filename, language=None: "salam dünya")
    _reset_voice_counter()
    resp = client.post(
        "/chat/transcribe",
        data={"language": "az"},
        files={"file": ("a.webm", io.BytesIO(WEBM), "audio/webm")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "salam dünya"
    assert body["limited"] is False


def test_transcribe_daily_cap(client, monkeypatch):
    monkeypatch.setattr(transcribe_api.llm, "enabled", True)
    monkeypatch.setattr(type(transcribe_api.llm), "use_openai", property(lambda self: True), raising=False)
    monkeypatch.setattr(transcribe_api.llm, "transcribe", lambda *a, **k: "hi")
    _reset_voice_counter()
    transcribe_api._calls["day"] = date.today()
    transcribe_api._calls["count"] = settings.voice_daily_limit
    resp = client.post(
        "/chat/transcribe",
        files={"file": ("a.webm", io.BytesIO(WEBM), "audio/webm")},
    )
    assert resp.status_code == 200
    assert resp.json()["limited"] is True
    _reset_voice_counter()


def test_transcribe_503_when_disabled(client, monkeypatch):
    monkeypatch.setattr(transcribe_api.llm, "enabled", False)
    resp = client.post(
        "/chat/transcribe",
        files={"file": ("a.webm", io.BytesIO(WEBM), "audio/webm")},
    )
    assert resp.status_code == 503
