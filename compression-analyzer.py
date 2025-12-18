import os
import subprocess
import math

# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------
RIGHTEOUS_SIZE_MB = 250  # target final size
AUDIO_BITRATE_K = 96     # good enough for speech
MIN_VIDEO_BITRATE_K = 150  # don't starve even the wicked
MAX_VIDEO_BITRATE_K = 5000 # cap for innocent files


def get_video_duration(path):
    """Returns video duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return float(result.stdout.strip())


def judge_sinfulness(input_path):
    """Returns sin score (MB per minute) and duration."""
    input_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    duration_s = get_video_duration(input_path)
    sin_score = input_size_mb / (duration_s / 60)  # MB per minute
    return sin_score, input_size_mb, duration_s


def compute_target_bitrate(duration_s):
    """Compute righteous bitrate needed to hit ~250MB final size."""
    target_bits = RIGHTEOUS_SIZE_MB * 8 * 1024 * 1024   # MB → bits
    bitrate_bps = target_bits / duration_s
    bitrate_k = int(bitrate_bps / 1000)
    return bitrate_k


def compress_with_righteousness(input_path, output_path):
    """
    Applies the Whistler Doctrine:
    - Judge sinfulness
    - Spare the innocent
    - Redeem the wicked
    - Produce righteous ~250MB output
    """

    sin_score, size_mb, duration_s = judge_sinfulness(input_path)
    print(f"\n--- Whistler Compression Doctrine ---")
    print(f"Input Size: {size_mb:.2f} MB")
    print(f"Duration: {duration_s:.1f} sec")
    print(f"Sin Score (MB/min): {sin_score:.2f}")

    # Step 1: Compute righteous target bitrate
    righteous_bitrate_k = compute_target_bitrate(duration_s)
    print(f"Righteous bitrate target: {righteous_bitrate_k} kbps total")

    # Decide treatment
    if size_mb < RIGHTEOUS_SIZE_MB * 1.2:
        # Innocent: use CRF (quality-based)
        print("Judgment: Innocent. Applying gentle CRF compression.")
        video_params = [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23"
        ]
        audio_params = [
            "-c:a", "aac",
            "-b:a", f"{AUDIO_BITRATE_K}k"
        ]
    else:
        # Wicked: apply strict bitrate target
        print("Judgment: Wicked. Applying strict bitrate compression.")
        video_bitrate_k = max(
            MIN_VIDEO_BITRATE_K,
            righteous_bitrate_k - AUDIO_BITRATE_K
        )
        video_bitrate_k = min(video_bitrate_k, MAX_VIDEO_BITRATE_K)

        print(f"Assigned Video Bitrate: {video_bitrate_k} kbps")

        video_params = [
            "-c:v", "libx264",
            "-b:v", f"{video_bitrate_k}k",
            "-maxrate", f"{video_bitrate_k}k",
            "-bufsize", f"{video_bitrate_k * 2}k",
            "-preset", "medium"
        ]
        audio_params = [
            "-c:a", "aac",
            "-b:a", f"{AUDIO_BITRATE_K}k"
        ]

    # Resolution scaling: gentle 720p downscale for wicked files
    scale_params = [
        "-vf", "scale='min(1280,iw)':-2"
    ]

    ffmpeg_cmd = [
        "ffmpeg", "-i", input_path,
        *video_params,
        *audio_params,
        *scale_params,
        "-movflags", "+faststart",
        output_path,
        "-y"
    ]

    print("\nRunning ffmpeg:")
    print(" ".join(ffmpeg_cmd))

    subprocess.run(ffmpeg_cmd)


if __name__ == "__main__":
    INPUT = "output_compressed.mp4"
    OUTPUT = "output_righteous.mp4"
    compress_with_righteousness(INPUT, OUTPUT)
