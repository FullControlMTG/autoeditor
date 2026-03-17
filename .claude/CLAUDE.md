# FullControl MTG – Auto Editor

Python CLI that assembles MTG content videos from raw recordings using ffmpeg.
Raw clips + branded assets → single upload-ready mp4, driven entirely by `.env`.

**Stack:** Python 3.10+, ffmpeg/ffprobe (on PATH), `ffmpeg-python`, `python-dotenv`, `click`
**Input:** `.mp4` `.mov` `.mkv` `.avi` — **Output:** h264/aac mp4

See also:
- [architecture.md](architecture.md) — modules and what each one does
- [pipeline.md](pipeline.md) — video assembly order and rendering steps
- [config.md](config.md) — all .env variables and defaults
