import argparse
import math
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class MediaInfo:
    duration_s: float
    bit_rate_bps: Optional[int]
    size_bytes: int


def _run(cmd: list[str]) -> None:
    print("\n$ " + " ".join(shlex.quote(c) for c in cmd))
    subprocess.run(cmd, check=True)


def _ffprobe_media_info(input_path: Path) -> MediaInfo:
    size_bytes = input_path.stat().st_size

    # duration
    duration_out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()

    duration_s = float(duration_out)

    # bit_rate may be missing for some containers; treat as optional
    bit_rate_out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=bit_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()

    bit_rate_bps: Optional[int]
    if bit_rate_out:
        try:
            bit_rate_bps = int(float(bit_rate_out))
        except ValueError:
            bit_rate_bps = None
    else:
        bit_rate_bps = None

    return MediaInfo(duration_s=duration_s, bit_rate_bps=bit_rate_bps, size_bytes=size_bytes)


def _parse_hms_to_seconds(value: str) -> float:
    """Parse seconds or HH:MM:SS[.ms] into seconds."""
    value = value.strip()
    if ":" not in value:
        return float(value)

    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError("Expected HH:MM:SS or seconds")

    hours = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def _default_output_ext(input_path: Path) -> str:
    ext = input_path.suffix
    return ext if ext else ".mp4"


def cmd_chunk_time(args: argparse.Namespace) -> None:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    segment_s = _parse_hms_to_seconds(args.segment_time)
    if segment_s <= 0:
        raise SystemExit("--segment-time must be > 0")

    ext = args.ext or _default_output_ext(input_path)
    if not ext.startswith("."):
        ext = "." + ext

    template = str(out_dir / f"{args.prefix}_%03d{ext}")

    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", str(input_path)]
    if args.copy:
        cmd += ["-map", "0", "-c", "copy"]
    else:
        # fallback: a reasonable default transcode, still fast-ish
        cmd += [
            "-map",
            "0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
        ]

    cmd += [
        "-f",
        "segment",
        "-segment_time",
        str(segment_s),
        "-reset_timestamps",
        "1",
        template,
    ]

    _run(cmd)


def cmd_chunk_size(args: argparse.Namespace) -> None:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    info = _ffprobe_media_info(input_path)
    if info.duration_s <= 0:
        raise SystemExit("Could not determine duration")

    # Prefer container-reported bitrate; fallback to size/duration.
    if info.bit_rate_bps and info.bit_rate_bps > 0:
        bitrate_bps = info.bit_rate_bps
    else:
        bitrate_bps = int((info.size_bytes * 8) / info.duration_s)

    target_bytes = int(float(args.target_mb) * 1024 * 1024)
    if target_bytes <= 0:
        raise SystemExit("--target-mb must be > 0")

    # Duration per chunk ≈ target_bits / bitrate
    chunk_s = (target_bytes * 8) / bitrate_bps

    if args.min_seconds is not None:
        chunk_s = max(chunk_s, float(args.min_seconds))

    if args.max_seconds is not None:
        chunk_s = min(chunk_s, float(args.max_seconds))

    # Guardrails
    chunk_s = max(chunk_s, 1.0)

    print("\n--- chunk-size plan ---")
    print(f"duration: {info.duration_s:.3f}s")
    print(f"size: {info.size_bytes / (1024 * 1024):.2f}MB")
    print(f"bitrate: {bitrate_bps / 1_000:.1f} kbps")
    print(f"target: {args.target_mb}MB")
    print(f"segment_time: {chunk_s:.3f}s")

    # Delegate to chunk-time
    args2 = argparse.Namespace(
        input=str(input_path),
        out_dir=args.out_dir,
        prefix=args.prefix,
        segment_time=str(chunk_s),
        copy=args.copy,
        ext=args.ext,
    )
    cmd_chunk_time(args2)


def cmd_concat(args: argparse.Namespace) -> None:
    out_path = Path(args.output).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    inputs: list[Path]
    if bool(args.dir) == bool(args.inputs):
        raise SystemExit("Provide either --dir OR one or more input files")

    if args.dir:
        in_dir = Path(args.dir).expanduser().resolve()
        if not in_dir.exists():
            raise SystemExit(f"Directory not found: {in_dir}")
        inputs = sorted(p for p in in_dir.iterdir() if p.is_file())
        if args.ext:
            ext = args.ext
            if not ext.startswith("."):
                ext = "." + ext
            inputs = [p for p in inputs if p.suffix.lower() == ext.lower()]
    else:
        inputs = [Path(p).expanduser().resolve() for p in args.inputs]

    if not inputs:
        raise SystemExit("No input files found")

    for p in inputs:
        if not p.exists():
            raise SystemExit(f"Missing input: {p}")

    # concat demuxer expects a list file
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        list_path = Path(f.name)
        for p in inputs:
            # Use POSIX-style quoting; ffmpeg's concat demuxer supports this
            f.write(f"file {p.as_posix()!r}\n")

    try:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
        ]

        if args.copy:
            cmd += ["-c", "copy"]
        else:
            cmd += [
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
            ]

        cmd += [str(out_path)]
        _run(cmd)
    finally:
        try:
            list_path.unlink(missing_ok=True)
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="video_tools",
        description="Small ffmpeg/ffprobe helpers (chunking + concat)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_time = sub.add_parser("chunk-time", help="Split into N-second chunks (fast)")
    p_time.add_argument("input", help="Input video path")
    p_time.add_argument("--segment-time", required=True, help="Seconds or HH:MM:SS")
    p_time.add_argument("--out-dir", default="chunks", help="Output directory")
    p_time.add_argument("--prefix", default="chunk", help="Output file prefix")
    p_time.add_argument("--ext", default=None, help="Output extension (default: input ext)")
    p_time.add_argument("--copy", action=argparse.BooleanOptionalAction, default=True, help="Stream copy (default: true)")
    p_time.set_defaults(func=cmd_chunk_time)

    p_size = sub.add_parser("chunk-size", help="Split into ~target-MB chunks (approx)")
    p_size.add_argument("input", help="Input video path")
    p_size.add_argument("--target-mb", required=True, type=float, help="Approx target chunk size in MB")
    p_size.add_argument("--out-dir", default="chunks", help="Output directory")
    p_size.add_argument("--prefix", default="chunk", help="Output file prefix")
    p_size.add_argument("--ext", default=None, help="Output extension (default: input ext)")
    p_size.add_argument("--copy", action=argparse.BooleanOptionalAction, default=True, help="Stream copy (default: true)")
    p_size.add_argument("--min-seconds", type=float, default=None, help="Clamp segment time minimum")
    p_size.add_argument("--max-seconds", type=float, default=None, help="Clamp segment time maximum")
    p_size.set_defaults(func=cmd_chunk_size)

    p_cat = sub.add_parser("concat", help="Join files (same codec/params recommended)")
    p_cat.add_argument("--dir", help="Directory of chunks to concat")
    p_cat.add_argument("inputs", nargs="*", help="Input files to concat in order")
    p_cat.add_argument("--ext", default=None, help="If using --dir, only include this extension")
    p_cat.add_argument("--output", required=True, help="Output file path")
    p_cat.add_argument("--copy", action=argparse.BooleanOptionalAction, default=True, help="Stream copy (default: true)")
    p_cat.set_defaults(func=cmd_concat)

    return p


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except subprocess.CalledProcessError as e:
        return e.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
