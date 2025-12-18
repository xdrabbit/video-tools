# video-tools

Small local helpers around `ffmpeg` / `ffprobe`.

## Prereqs

- `ffmpeg` and `ffprobe` installed and on `PATH`
- Python 3

## CLI

### Chunk by time (fast)

Stream-copy split (no re-encode):

```bash
python video_tools.py chunk-time input.mp4 --segment-time 600 --out-dir chunks --prefix part
```

If you need “exact” cuts (re-encode):

```bash
python video_tools.py chunk-time input.mp4 --segment-time 00:10:00 --no-copy
```

Note: `--copy` cuts on keyframes; boundaries may be slightly off.

### Chunk by target size (approx)

This estimates a segment duration from bitrate and uses the same segmenter:

```bash
python video_tools.py chunk-size input.mp4 --target-mb 200 --out-dir chunks --prefix part
```

### Concat back together

Concat files in a directory (sorted by filename):

```bash
python video_tools.py concat --dir chunks --ext .mp4 --output joined.mp4
```

Or provide inputs explicitly:

```bash
python video_tools.py concat part_000.mp4 part_001.mp4 part_002.mp4 --output joined.mp4
```

Tip: `--copy` requires the chunks to be compatible (same codec/profile, etc.). Use `--no-copy` to re-encode if needed.
