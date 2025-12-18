'''
H.264 compressed video

960px width (height auto-scaled)

Audio re-encoded to AAC 96k

Streaming-friendly (+faststart)

Overwrites output without asking (-y)
'''

ffmpeg -i output.mp4 \
  -c:v libx264 \
  -crf 28 \
  -preset medium \
  -vf "scale=960:-2" \
  -c:a aac \
  -b:a 96k \
  -movflags +faststart \
  output_compressed.mp4 -y


'''
THE 20 MB COMPRESSION COMMAND

This forces:

640px width

~70kbps video

~16kbps mono audio

ultra-fast preset (no refinement)

ultralow quality
'''

ffmpeg -i PXL_20251120_174645293.mp4 \
  -c:v libx264 \
  -b:v 70k \
  -maxrate 70k \
  -bufsize 140k \
  -vf "scale=640:-2" \
  -preset veryfast \
  -c:a aac \
  -b:a 16k \
  -ac 1 \
  -movflags +faststart \
  PXL_20251120_174645293_20MB.mp4 -y


'''
Ultra-Tight Compression Preset (Target ≈20–25 MB)

This preset uses:

H.264 constrained bitrate

tiny resolution

very low audio bitrate

aggressive frame skipping tolerance

faststart for streaming

motion-adaptive scaling

tuned GOP to improve quality at ultra-low bitrate
'''
ffmpeg -i PXL_20251120_174645293.mp4 \
  -vf "scale=480:-2:flags=lanczos" \
  -c:v libx264 \
  -b:v 60k \
  -maxrate 60k \
  -bufsize 120k \
  -preset veryfast \
  -profile:v baseline \
  -level 3.0 \
  -x264-params "keyint=240:min-keyint=60:no-scenecut=1" \
  -c:a aac \
  -b:a 12k \
  -ac 1 \
  -ar 22050 \
  -movflags +faststart \
  PXL_20251120_174645293_20MB.mp4 -y
