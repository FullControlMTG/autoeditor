# FullControl MTG – Auto Editor

A Python CLI tool for automatically stitching Magic: The Gathering content videos together using ffmpeg. Point it at a folder of raw recordings and it produces a fully assembled, ready-to-upload video with intros, outros, transitions, midroll ads, and audio/video fades — all driven by a single `.env` config file.

---

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) and `ffprobe` installed and available on your `PATH`

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Setup

1. Copy the example config and fill in your values:

```bash
cp .env.example .env
```

2. Edit `.env` with your asset paths and preferences (see [Configuration](#configuration) below).

3. Place your project recording folders inside the folder pointed to by `PROJECT_FOLDER_PATH`.

---

## Project Folder Structure

Each project is a folder named in the format `YYYY.MM.DD-deck-name`, containing the raw video recordings as `.mp4` or `.mov` files:

```
input/
└── 2026.03.13-jeskai-control/
    ├── 2026-03-13 21-04-11.mp4   ← deck tech  (earliest by modified date)
    ├── 2026-03-13 21-34-55.mp4   ← game 1
    ├── 2026-03-13 21-58-22.mp4   ← game 2
    ├── 2026-03-13 22-17-40.mp4   ← game 3
    └── 2026-03-13 22-45-03.mp4   ← game 4
```

- **Deck tech** — the first video file by modification date.
- **Games** — all remaining files in modification date order.

Supported input formats: `.mp4`, `.mov`, `.mkv`, `.avi`.

---

## Default Pipeline

For a project with **N games**, the assembled output follows this order:

```
Intro → Deck Tech → Midroll Ad 1 → Transition
      → Game 1 → Transition → ... → Game ⌈N/2⌉ [fade out]
      → Midroll Ad 2
      → Game ⌈N/2⌉+1 → Transition → ... → Game N
      → Outro
```

**Rules:**
- The transition clip plays after Midroll Ad 1, immediately before Game 1.
- There is no transition before Midroll Ad 1, or on either side of Midroll Ad 2.
- The content group immediately preceding each midroll ad fades out to black before the hard cut.
- Midroll Ad 2 is only inserted when there are 2 or more games (it splits the games roughly in half).
- Any asset whose path is unset or whose enabled flag is `false` is silently skipped.
- A global fade-in is applied to the very first frame of the output; a fade-out is applied to the very last.

**Example — 5 games:**

```
Intro → Deck Tech [fade out] → Midroll Ad 1 → Transition
      → Game 1 → T → Game 2 → T → Game 3 [fade out]
      → Midroll Ad 2
      → Game 4 → T → Game 5
      → Outro
```

---

## Features

- **Automatic pipeline assembly** — intro, outro, transition clips, and midroll ads are inserted in the correct order automatically based on the number of games in the project folder.
- **Batch or single-project processing** — process an entire folder of projects in one run, or target a single project folder, controlled by a flag in `.env`.
- **Crossfade between clips** — configurable `xfade` / `acrossfade` crossfades between content clips within a group for smooth transitions.
- **Hard cuts around ads** — midroll ads always cut in and out cleanly with no crossfade bleed.
- **Global fade-in / fade-out** — the final output video fades up from black at the start and fades to black at the end.
- **Mixed format support** — accepts `.mp4`, `.mov`, `.mkv`, and `.avi` source files. All clips are normalised to a common format (h264/aac) before stitching.
- **Resolution and FPS normalisation** — all clips are scaled (with letterbox/pillarbox padding) and resampled to the configured target resolution and frame rate.
- **Missing audio handling** — clips with no audio track (e.g. silent transition overlays) automatically receive a synthesised silent audio stream so the concat pipeline never breaks.
- **Midroll ad toggles** — each midroll ad can be enabled or disabled independently in `.env` without removing its path, useful for toggling ads per-upload.
- **Dry-run mode** — preview the full pipeline order for every project without rendering anything.
- **Temporary file cleanup** — intermediate normalised clips and group renders are written to a `_tmp_` folder beside the output and deleted automatically on completion.

---

## Commands

All commands are run from the project root:

```bash
python main.py <command> [options]
```

---

### `run` — Normal entry point

Reads `PROJECT_FOLDER_PATH` and `PROCESS_MULTI` from `.env` and routes automatically.

```bash
python main.py run [--dry-run]
```

| `PROCESS_MULTI` | Behaviour |
|---|---|
| `false` | `PROJECT_FOLDER_PATH` is treated as the single project folder to process |
| `true` | `PROJECT_FOLDER_PATH` is treated as the parent folder; all subfolders are processed |

**Examples:**

```bash
# Render based on .env settings
python main.py run

# Preview pipeline(s) without rendering
python main.py run --dry-run
```

---

### `process` — Single project (explicit path)

Process one specific project folder, ignoring `PROCESS_MULTI`.

```bash
python main.py process FOLDER [--output PATH] [--dry-run]
```

| Argument / Option | Description |
|---|---|
| `FOLDER` | Path to the project folder (the `YYYY.MM.DD-deck-name` directory) |
| `--output`, `-o` | Output file path. Defaults to `<OUTPUT_FOLDER>/<project-name>.mp4` |
| `--dry-run` | Print the pipeline without rendering |

**Examples:**

```bash
python main.py process "./input/2026.03.13-jeskai-control"

python main.py process "./input/2026.03.13-jeskai-control" --output "./output/jeskai.mp4"

python main.py process "./input/2026.03.13-jeskai-control" --dry-run
```

---

### `batch` — Multiple projects (explicit path)

Process all project subfolders inside a given root folder, ignoring `PROCESS_MULTI`.

```bash
python main.py batch FOLDER [--dry-run]
```

| Argument / Option | Description |
|---|---|
| `FOLDER` | Path to the parent folder containing project subfolders |
| `--dry-run` | Print pipelines without rendering |

**Examples:**

```bash
python main.py batch "./input"

python main.py batch "./input" --dry-run
```

---

## Configuration

Copy `.env.example` to `.env` and edit as needed. All paths accept forward slashes on Windows. Wrap paths containing spaces in double quotes.

```ini
# Use forward slashes, even on Windows
# Wrap paths with spaces in double quotes: PROJECT_FOLDER_PATH="C:/My Videos/input"
```

| Variable | Description | Default |
|---|---|---|
| `INTRO_PATH` | Path to the intro video clip | *(unset — skipped)* |
| `OUTRO_PATH` | Path to the outro video clip | *(unset — skipped)* |
| `TRANSITION_PATH` | Path to the transition video clip inserted between games | *(unset — skipped)* |
| `MIDROLL_AD_PATH_1` | Path to midroll ad 1 (placed after deck tech) | *(unset — skipped)* |
| `MIDROLL_AD_PATH_2` | Path to midroll ad 2 (placed halfway through games) | *(unset — skipped)* |
| `MIDROLL_AD_1_ENABLED` | Set to `false` to skip midroll ad 1 without removing its path | `true` |
| `MIDROLL_AD_2_ENABLED` | Set to `false` to skip midroll ad 2 without removing its path | `true` |
| `PROJECT_FOLDER_PATH` | Project folder (single mode) or parent of project folders (multi mode) | `./input` |
| `OUTPUT_FOLDER` | Folder where rendered `.mp4` files are written | `./output` |
| `PROCESS_MULTI` | `true` = batch mode, `false` = single project mode | `true` |
| `TARGET_RESOLUTION` | Output resolution (`WxH`) | `3440x2160` |
| `TARGET_FPS` | Output frame rate | `60` |
| `FADE_DURATION` | Crossfade duration in seconds between clips within a group. `0` = hard cuts | `0.3` |
| `OUTPUT_FADE_DURATION` | Fade-in / fade-out duration in seconds on the final output. `0` = no fade | `0.5` |

---

## Asset Folder Suggestion

```
assets/
├── intro.mp4
├── outro.mp4
├── transition.mp4
├── midroll_1.mp4
└── midroll_2.mp4

input/
├── 2026.03.13-jeskai-control/
│   └── *.mp4
└── 2026.03.17-mono-red/
    └── *.mp4

output/
├── 2026.03.13-jeskai-control.mp4
└── 2026.03.17-mono-red.mp4
```
