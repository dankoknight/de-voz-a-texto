"""De voz a texto — transcripción de audio con Whisper local u OpenAI."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"
TMP_DIR = BASE_DIR / "tmp"

UPLOAD_DIR.mkdir(exist_ok=True)
TMP_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".flac",
    ".webm",
    ".aac",
    ".wma",
    ".opus",
    ".mp4",
    ".mkv",
    ".mov",
    ".aiff",
    ".aif",
}

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "es")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))

_local_model: Any = None
_jobs: dict[str, dict[str, Any]] = {}

app = FastAPI(title="De voz a texto", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def engine_info() -> dict[str, Any]:
    return {
        "engine": "openai" if OPENAI_API_KEY else "faster-whisper",
        "model": "whisper-1" if OPENAI_API_KEY else WHISPER_MODEL,
        "device": "api" if OPENAI_API_KEY else WHISPER_DEVICE,
        "default_language": DEFAULT_LANGUAGE,
        "openai_configured": bool(OPENAI_API_KEY),
    }


def get_local_model():
    global _local_model
    if _local_model is None:
        from faster_whisper import WhisperModel

        _local_model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
        )
    return _local_model


def convert_to_wav(src: Path, dst: Path) -> None:
    """Convierte cualquier audio a WAV 16 kHz mono con ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-800:] or "ffmpeg falló al convertir el audio")


def transcribe_local(audio_path: Path, language: str | None) -> str:
    model = get_local_model()
    segments, info = model.transcribe(
        str(audio_path),
        language=language or None,
        vad_filter=False,
        beam_size=1,
    )
    parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
    text = " ".join(parts).strip()
    print(
        f"[whisper] path={audio_path} lang={language} duration={getattr(info, 'duration', '?')} text_len={len(text)}",
        flush=True,
    )
    return text


def transcribe_openai(audio_path: Path, language: str | None) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    with open(audio_path, "rb") as f:
        kwargs: dict[str, Any] = {
            "model": "whisper-1",
            "file": f,
            "response_format": "text",
        }
        if language:
            kwargs["language"] = language
        result = client.audio.transcriptions.create(**kwargs)
    return str(result).strip()


def run_transcription(job_id: str, src: Path, language: str | None) -> None:
    job = _jobs[job_id]
    wav_path = TMP_DIR / f"{job_id}.wav"
    try:
        job["status"] = "converting"
        job["progress"] = 15
        job["message"] = "Convirtiendo audio…"
        convert_to_wav(src, wav_path)

        job["status"] = "transcribing"
        job["progress"] = 40
        job["message"] = "Transcribiendo…"

        if OPENAI_API_KEY:
            text = transcribe_openai(wav_path, language)
            job["engine"] = "openai"
        else:
            text = transcribe_local(wav_path, language)
            job["engine"] = "faster-whisper"

        job["status"] = "done"
        job["progress"] = 100
        job["message"] = "Listo"
        job["text"] = text or "(Sin texto detectado en el audio)"
    except Exception as exc:  # noqa: BLE001 — surface to UI
        job["status"] = "error"
        job["progress"] = 100
        job["message"] = "Error"
        job["error"] = str(exc)
    finally:
        for path in (src, wav_path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"ok": True, **engine_info()}


@app.post("/api/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(default=DEFAULT_LANGUAGE),
):
    if not file.filename:
        raise HTTPException(400, "Falta el nombre del archivo")

    suffix = Path(file.filename).suffix.lower()
    if suffix and suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Formato no soportado: {suffix}. Usa mp3, wav, m4a, ogg, flac, webm, etc.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(400, "El archivo está vacío")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"El archivo supera el límite de {MAX_UPLOAD_MB} MB")

    job_id = uuid.uuid4().hex
    src = UPLOAD_DIR / f"{job_id}{suffix or '.bin'}"
    src.write_bytes(data)

    lang = (language or DEFAULT_LANGUAGE).strip().lower() or None
    if lang in {"auto", "detect", ""}:
        lang = None

    _jobs[job_id] = {
        "status": "queued",
        "progress": 5,
        "message": "En cola…",
        "text": "",
        "error": None,
        "filename": file.filename,
        "language": lang or "auto",
        "engine": None,
    }

    asyncio.create_task(asyncio.to_thread(run_transcription, job_id, src, lang))
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado")
    return JSONResponse(job)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8787"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
