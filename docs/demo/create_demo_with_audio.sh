#!/bin/bash
set -e

echo "Creating CodeGreen demo with audio..."
echo ""

# Generate video with VHS
echo "[1/3] Generating video with VHS..."
vhs demo.tape

# Check if video was created
if [ ! -f "demo.mp4" ]; then
    echo "Error: demo.mp4 not found. VHS may have failed."
    exit 1
fi

echo "✓ Video generated: demo.mp4"
echo ""

# Add audio with ffmpeg
echo "[2/3] Adding audio track..."

# Check if audio file exists
if [ ! -f "prism.mp3" ]; then
    echo "Error: prism.mp3 not found"
    exit 1
fi

# Get video duration
VIDEO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 demo.mp4)
echo "Video duration: ${VIDEO_DURATION}s"

# Combine video and audio
# Loop audio if shorter than video, fade in/out for smoothness
ffmpeg -i demo.mp4 -stream_loop -1 -i prism.mp3 -filter_complex \
  "[1:a]afade=t=in:st=0:d=1,afade=t=out:st=$(echo "$VIDEO_DURATION - 2" | bc):d=2[audio]" \
  -map 0:v -map "[audio]" -c:v copy -c:a aac -b:a 192k \
  -shortest -y demo_with_audio.mp4

echo "✓ Audio added: demo_with_audio.mp4"
echo ""

# Optional: Also create version with audio for GIF (silent, but keeping both)
echo "[3/3] Keeping original GIF (silent)..."
echo "✓ Original GIF: demo.gif"
echo ""

# Copy to website/docs/assets/demo.mp4
cp demo_with_audio.mp4 docs/website/docs/assets/demo.mp4
cp demo.gif docs/website/docs/assets/demo.gif

echo "=========================================="
echo "Demo creation complete!"
echo "=========================================="
echo ""
echo "Files created:"
echo "  • demo.mp4 (original, no audio)"
echo "  • demo_with_audio.mp4 (with music)"
echo "  • demo.gif (original)"
echo ""
echo "Recommended: Use demo_with_audio.mp4 for presentations"
