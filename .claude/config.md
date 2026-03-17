# Configuration Reference

All config lives in `.env` (copy from `.env.example`). Loaded by `autoeditor/config.py` → `Config` dataclass.

Use forward slashes for paths on Windows. Wrap paths with spaces in double quotes.

## Asset paths

| Variable | Description |
|---|---|
| `INTRO_PATH` | Intro clip |
| `OUTRO_PATH` | Outro clip |
| `TRANSITION_PATH` | Transition clip — inserted after deck tech, before gameplay |
| `MIDROLL_AD_PATH_1` | Ad clip inserted after deck tech + transition |
| `MIDROLL_AD_PATH_2` | Ad clip inserted ~halfway through the games section |
| `MIDROLL_AD_1_ENABLED` | `true`/`false` — toggle ad 1 without removing its path |
| `MIDROLL_AD_2_ENABLED` | `true`/`false` — toggle ad 2 without removing its path |

All asset paths are optional. Unset = asset is skipped.

## Folders

| Variable | Default | Description |
|---|---|---|
| `PROJECT_FOLDER_PATH` | `./input` | The project folder itself (`PROCESS_MULTI=false`) or parent of project folders (`PROCESS_MULTI=true`) |
| `OUTPUT_FOLDER` | `./output` | Where rendered `.mp4` files are written |

## Behaviour

| Variable | Default | Description |
|---|---|---|
| `PROCESS_MULTI` | `true` | `true` = batch all subfolders in `PROJECT_FOLDER_PATH`; `false` = treat `PROJECT_FOLDER_PATH` as a single project folder |

## Output settings

| Variable | Default | Description |
|---|---|---|
| `TARGET_RESOLUTION` | `3440x2160` | Output resolution as `WxH` |
| `TARGET_FPS` | `60` | Output frame rate |
| `FADE_DURATION` | `0.3` | Crossfade duration in seconds between clips within a group. `0` = hard cuts |
| `OUTPUT_FADE_DURATION` | `0.5` | Duration in seconds for: fade-in at start of final output, fade-out at end of final output, and fade-out before each midroll ad |
