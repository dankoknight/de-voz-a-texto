# De voz a texto

App web sencilla: subes un audio y obtienes la transcripción editable (copiar / descargar `.txt`). Interfaz en español; idioma por defecto `es`.

## Cómo ejecutar

```bash
export PATH="$HOME/.local/bin:$PATH"
cd /ruta/a/transcripcion
pip3 install --user -r requirements.txt
# hace falta ffmpeg en el sistema
./start.sh
# o: python3 -m uvicorn app:app --host 0.0.0.0 --port 8787
```

Abre [http://127.0.0.1:8787](http://127.0.0.1:8787).

Comprobar salud:

```bash
curl -s http://127.0.0.1:8787/api/health
```

## Formatos de audio

Acepta, entre otros: **mp3, wav, m4a, ogg, flac, webm, aac, wma, opus, aiff** (también contenedores con pista de audio como mp4/mkv/mov).

Cualquier formato se convierte con **ffmpeg** a WAV 16 kHz mono antes de transcribir.

## Motores

1. **Local (por defecto):** [faster-whisper](https://github.com/SYSTRAN/faster-whisper), sin API key.
2. **OpenAI Whisper:** si existe la variable `OPENAI_API_KEY`, se usa el endpoint `whisper-1`.

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PORT` | `8787` | Puerto HTTP |
| `HOST` | `0.0.0.0` | Bind |
| `DEFAULT_LANGUAGE` | `es` | Idioma por defecto |
| `WHISPER_MODEL` | `base` | Modelo local (`tiny`, `base`, `small`, …) |
| `WHISPER_DEVICE` | `cpu` | `cpu` o `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` | Tipo de cómputo CTranslate2 |
| `OPENAI_API_KEY` | _(vacío)_ | Si está, usa OpenAI en lugar del motor local |
| `MAX_UPLOAD_MB` | `100` | Límite de subida |

## Uso

1. Abre la página y elige / arrastra un audio.
2. Confirma el idioma (Español por defecto).
3. Pulsa **Transcribir** y espera la barra de progreso.
4. Edita el texto, **Copia** o **Descarga .txt**.

## Dependencias del sistema

- Python 3.10+
- `ffmpeg` en el `PATH`
- Paquetes de `requirements.txt` (incluye `av==12.3.0` por compatibilidad con faster-whisper)
