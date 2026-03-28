"""Low-level ffmpeg operations used by the render pipeline."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .pipeline import Segment, SegmentType


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------

@dataclass
class ClipInfo:
    path: Path
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool


def probe_clip(path: Path) -> ClipInfo:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)

    video_stream = next(
        (s for s in data["streams"] if s["codec_type"] == "video"), None
    )
    if video_stream is None:
        raise ValueError(f"No video stream in {path}")

    audio_streams = [s for s in data["streams"] if s["codec_type"] == "audio"]

    fps_num, fps_den = video_stream.get("r_frame_rate", "30/1").split("/")
    fps = int(fps_num) / int(fps_den)

    return ClipInfo(
        path=path,
        duration=float(data["format"].get("duration", 0)),
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=fps,
        has_audio=bool(audio_streams),
    )


# ---------------------------------------------------------------------------
# Encoder helpers
# ---------------------------------------------------------------------------

# Quality args per encoder. These are appended after -c:v <encoder>.
_ENCODER_QUALITY: dict[str, list[str]] = {
    "libx264":    ["-preset", "fast", "-crf", "18"],
    "h264_nvenc": ["-preset", "p4", "-cq", "20"],
    "h264_amf":   ["-quality", "balanced", "-qp_i", "20", "-qp_p", "20"],
    "h264_qsv":   ["-preset", "fast", "-global_quality", "20"],
}

# Hardware decode args to insert before -i, per encoder.
_ENCODER_HWACCEL: dict[str, list[str]] = {
    "libx264":    [],
    "h264_nvenc": ["-hwaccel", "cuda"],
    "h264_amf":   [],
    "h264_qsv":   ["-hwaccel", "qsv"],
}


def _encode_args(config: Config) -> list[str]:
    """Return [-c:v <encoder> + quality flags] for the configured encoder."""
    enc = config.video_encoder
    quality = _ENCODER_QUALITY.get(enc, ["-preset", "fast", "-crf", "18"])
    return ["-c:v", enc] + quality


def _hwaccel_args(config: Config) -> list[str]:
    """Return hardware-decode flags to place before -i, or [] for software decode."""
    return _ENCODER_HWACCEL.get(config.video_encoder, [])


# ---------------------------------------------------------------------------
# Normalize
# ---------------------------------------------------------------------------

def normalize_clip(input_path: Path, output_path: Path, config: Config) -> Path:
    """Re-encode a clip to the common target format.

    Handles:
    - Scaling / padding to target resolution with black bars
    - FPS conversion
    - Adding a silent audio track if the source has no audio
    - h264 video + aac audio at 48 kHz stereo
    """
    w, h = config.target_resolution.split("x")
    width, height = int(w), int(h)
    fps = config.target_fps

    info = probe_clip(input_path)

    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"fps={fps},"
        f"format=yuv420p"
    )

    cmd = ["ffmpeg", "-y", *_hwaccel_args(config), "-i", str(input_path)]

    if not info.has_audio:
        # Synthesize a silent stereo audio stream for the duration of the clip.
        cmd += [
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        ]
        cmd += ["-map", "0:v", "-map", "1:a", "-shortest"]
    else:
        cmd += ["-map", "0:v", "-map", "0:a"]

    cmd += [
        "-vf", vf,
        *_encode_args(config),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(output_path),
    ]

    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


# ---------------------------------------------------------------------------
# Crossfade render for a single group
# ---------------------------------------------------------------------------

def _build_xfade_filter(n: int, durations: list[float], fade_dur: float) -> tuple[str, str, str]:
    """Build filter_complex, video_out_label, audio_out_label for N clips."""
    if n == 1:
        return "", "0:v", "0:a"

    parts = []
    cumulative = 0.0

    for i in range(n - 1):
        # Timeline offset where the crossfade should begin
        offset = max(0.0, cumulative + durations[i] - (i + 1) * fade_dur)
        cumulative += durations[i]

        v_in1 = "[0:v]" if i == 0 else f"[xv{i}]"
        v_in2 = f"[{i + 1}:v]"
        v_out = "[vout]" if i == n - 2 else f"[xv{i + 1}]"

        a_in1 = "[0:a]" if i == 0 else f"[xa{i}]"
        a_in2 = f"[{i + 1}:a]"
        a_out = "[aout]" if i == n - 2 else f"[xa{i + 1}]"

        parts.append(
            f"{v_in1}{v_in2}xfade=transition=fade:duration={fade_dur}:offset={offset:.3f}{v_out}"
        )
        parts.append(
            f"{a_in1}{a_in2}acrossfade=d={fade_dur}:c1=tri:c2=tri{a_out}"
        )

    return ";".join(parts), "vout", "aout"


def render_group_with_xfade(clips: list[Path], output: Path, fade_dur: float, config: Config) -> Path:
    """Merge a list of clips into one file using xfade crossfades."""
    if len(clips) == 1:
        shutil.copy(clips[0], output)
        return output

    durations = [probe_clip(c).duration for c in clips]
    filter_complex, v_out, a_out = _build_xfade_filter(len(clips), durations, fade_dur)

    cmd = ["ffmpeg", "-y"]
    for clip in clips:
        cmd += ["-i", str(clip)]

    cmd += [
        "-filter_complex", filter_complex,
        "-map", f"[{v_out}]",
        "-map", f"[{a_out}]",
        *_encode_args(config),
        "-c:a", "aac", "-b:a", "192k",
        str(output),
    ]

    subprocess.run(cmd, check=True, capture_output=True)
    return output


# ---------------------------------------------------------------------------
# Hard-cut concatenation (concat demuxer, stream copy)
# ---------------------------------------------------------------------------

def concat_clips_demuxer(clips: list[Path], output: Path) -> Path:
    """Fast stream-copy concatenation. Requires all clips to share codec/resolution/fps."""
    if len(clips) == 1:
        shutil.copy(clips[0], output)
        return output

    list_file = output.parent / f"_concatlist_{output.stem}.txt"
    with open(list_file, "w") as f:
        for clip in clips:
            f.write(f"file '{clip.resolve().as_posix()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink()
    return output


# ---------------------------------------------------------------------------
# Final fade-in / fade-out pass
# ---------------------------------------------------------------------------

def apply_final_fades(input_path: Path, output_path: Path, fade_in_dur: float, fade_out_dur: float, config: Config) -> Path:
    """Add a fade-in at the start and fade-out at the end of a video."""
    info = probe_clip(input_path)
    fade_out_start = max(0.0, info.duration - fade_out_dur)

    vf = f"fade=t=in:st=0:d={fade_in_dur},fade=t=out:st={fade_out_start:.3f}:d={fade_out_dur}"
    af = f"afade=t=in:st=0:d={fade_in_dur},afade=t=out:st={fade_out_start:.3f}:d={fade_out_dur}"

    cmd = [
        "ffmpeg", "-y", *_hwaccel_args(config), "-i", str(input_path),
        "-vf", vf, "-af", af,
        *_encode_args(config),
        "-c:a", "aac", "-b:a", "192k",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


# ---------------------------------------------------------------------------
# Fade-out only pass (used before midroll ad hard cuts)
# ---------------------------------------------------------------------------

def apply_fade_out(input_path: Path, output_path: Path, fade_dur: float, config: Config) -> Path:
    """Apply a video and audio fade-out to the end of a clip."""
    info = probe_clip(input_path)
    fade_out_start = max(0.0, info.duration - fade_dur)

    cmd = [
        "ffmpeg", "-y", *_hwaccel_args(config), "-i", str(input_path),
        "-vf", f"fade=t=out:st={fade_out_start:.3f}:d={fade_dur}",
        "-af", f"afade=t=out:st={fade_out_start:.3f}:d={fade_dur}",
        *_encode_args(config),
        "-c:a", "aac", "-b:a", "192k",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


# ---------------------------------------------------------------------------
# Group splitting
# ---------------------------------------------------------------------------

def _split_into_groups(segments: list[Segment]) -> list[tuple[bool, list[int]]]:
    """Split segment indices into groups separated by midroll ads.

    Returns a list of (is_midroll_ad, [segment_indices]) tuples.
    Midroll ads are isolated into their own single-item groups so that the
    surrounding content is always hard-cut to/from them.
    """
    groups: list[tuple[bool, list[int]]] = []
    current: list[int] = []

    for i, seg in enumerate(segments):
        if seg.type == SegmentType.MIDROLL_AD:
            if current:
                groups.append((False, current))
                current = []
            groups.append((True, [i]))
        else:
            current.append(i)

    if current:
        groups.append((False, current))

    return groups


# ---------------------------------------------------------------------------
# Main render entry point
# ---------------------------------------------------------------------------

def render_project(
    segments: list[Segment],
    output_path: Path,
    config: Config,
    *,
    verbose: bool = True,
) -> Path:
    """Full pipeline: normalize → group → xfade within groups → concat → final fades."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_path.parent / f"_tmp_{output_path.stem}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        if verbose:
            print(msg)

    try:
        # ------------------------------------------------------------------
        # Step 1: Normalize every segment clip
        # ------------------------------------------------------------------
        log("  Normalizing clips...")
        normalized: dict[int, Path] = {}
        for i, seg in enumerate(segments):
            norm_path = tmp_dir / f"norm_{i:03d}_{seg.type.name.lower()}.mp4"
            log(f"    [{i + 1}/{len(segments)}] {seg.label}: {seg.path.name}")
            normalize_clip(seg.path, norm_path, config)
            normalized[i] = norm_path

        # ------------------------------------------------------------------
        # Step 2: Split into groups (isolated midroll ads + content groups)
        # ------------------------------------------------------------------
        groups = _split_into_groups(segments)

        # ------------------------------------------------------------------
        # Step 3: Render each group
        # ------------------------------------------------------------------
        log("  Merging groups...")
        group_outputs: list[Path] = []

        for g_idx, (is_midroll, indices) in enumerate(groups):
            clips = [normalized[i] for i in indices]
            group_out = tmp_dir / f"group_{g_idx:03d}.mp4"

            if is_midroll or len(clips) == 1 or config.fade_duration <= 0:
                if len(clips) == 1:
                    shutil.copy(clips[0], group_out)
                    group_label = segments[indices[0]].label
                else:
                    concat_clips_demuxer(clips, group_out)
                    group_label = f"group {g_idx + 1}"
                log(f"    {group_label}: hard cut (no crossfade)")
            else:
                labels = " > ".join(segments[i].label for i in indices)
                log(f"    Group {g_idx + 1} [{labels}]: applying crossfade")
                render_group_with_xfade(clips, group_out, config.fade_duration, config)

            # If the next group is a midroll ad, fade out the end of this group.
            next_is_midroll = (g_idx + 1 < len(groups)) and groups[g_idx + 1][0]
            if not is_midroll and next_is_midroll and config.output_fade_duration > 0:
                faded = tmp_dir / f"group_{g_idx:03d}_fadeout.mp4"
                log(f"    → fading out before midroll ad")
                apply_fade_out(group_out, faded, config.output_fade_duration, config)
                group_out = faded

            group_outputs.append(group_out)

        # ------------------------------------------------------------------
        # Step 4: Hard-cut concat all groups
        # ------------------------------------------------------------------
        if len(group_outputs) == 1:
            pre_fade = group_outputs[0]
        else:
            log("  Concatenating all groups...")
            pre_fade = tmp_dir / "pre_fade.mp4"
            concat_clips_demuxer(group_outputs, pre_fade)

        # ------------------------------------------------------------------
        # Step 5: Apply final fade-in / fade-out
        # ------------------------------------------------------------------
        if config.output_fade_duration > 0:
            log("  Applying final fades...")
            apply_final_fades(pre_fade, output_path, config.output_fade_duration, config.output_fade_duration, config)
        else:
            shutil.copy(pre_fade, output_path)

        log(f"  Output: {output_path}")
        return output_path

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
