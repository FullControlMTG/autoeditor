# Architecture

```
main.py                  — entry point, calls cli()
.env / .env.example      — all configuration
autoeditor/
    config.py            — load_config() → Config dataclass from .env
    project.py           — scan_project() → ProjectFolder (deck_tech + games list)
    pipeline.py          — build_pipeline() → list[Segment] in assembly order
    ffmpeg_ops.py        — all ffmpeg work: probe, normalize, xfade, concat, fades
    cli.py               — click CLI: run / process / batch commands
```

## config.py
`load_config()` reads `.env` and returns a typed `Config` dataclass. Asset paths are `Path | None` — unset = skipped.

## project.py
`scan_project(folder)` sorts video files by mtime then name. First file = **deck tech**, rest = **games**.
`scan_projects_folder(root)` iterates subdirectories for batch mode.

Project folders are named `YYYY.MM.DD-deck-name` (e.g. `2026.03.13-jeskai-control`).

## pipeline.py
`build_pipeline(project, config)` returns `list[Segment]`. Each `Segment` has a `SegmentType` enum (`INTRO`, `OUTRO`, `TRANSITION`, `DECK_TECH`, `GAME`, `MIDROLL_AD`) and a `Path`.
`describe_pipeline()` returns a human-readable string used by `--dry-run`.

## ffmpeg_ops.py
- `probe_clip(path)` → `ClipInfo` (duration, resolution, fps, has_audio)
- `normalize_clip(input, output, config)` — re-encodes to h264/aac, adds silent audio if missing, scales/pads to target resolution
- `render_group_with_xfade(clips, output, fade_dur)` — chains `xfade` + `acrossfade` filters across N clips
- `concat_clips_demuxer(clips, output)` — fast stream-copy concat via ffmpeg concat demuxer
- `apply_final_fades(input, output, fade_in, fade_out)` — fade in at start + fade out at end of final output
- `apply_fade_out(input, output, fade_dur)` — fade out only, used before midroll ad hard cuts
- `render_project(segments, output, config)` — full pipeline orchestrator; temp files in `_tmp_<name>/`, cleaned up on completion

## cli.py
Three commands, all support `--dry-run`:
- `run` — reads `PROCESS_MULTI` from `.env`, routes to single or batch automatically
- `process FOLDER` — explicit single project folder
- `batch FOLDER` — explicit multi-project root folder
