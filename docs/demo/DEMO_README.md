# CodeGreen Demo Creation Guide

## Quick Start

### Option 1: Automated Script (Recommended)
```bash
./create_demo_with_audio.sh
```

This will:
1. Generate video with VHS (`demo.mp4`)
2. Add audio track from `prism.mp3` (`demo_with_audio.mp4`)
3. Keep original GIF (`demo.gif`)

### Option 2: Manual Steps

```bash
# Step 1: Generate video with VHS
vhs demo.tape

# Step 2: Add audio with ffmpeg (simple version)
ffmpeg -i demo.mp4 -i prism.mp3 -c:v copy -c:a aac -shortest demo_with_audio.mp4

# Step 3: (Optional) Add fade in/out for professional touch
ffmpeg -i demo.mp4 -stream_loop -1 -i prism.mp3 \
  -filter_complex "[1:a]afade=t=in:st=0:d=1,afade=t=out:st=148:d=2[audio]" \
  -map 0:v -map "[audio]" -c:v copy -c:a aac -b:a 192k \
  -shortest -y demo_with_audio.mp4
```

## Files

- `demo.tape` - VHS recording script
- `prism.mp3` - Background audio (4.9MB)
- `create_demo_with_audio.sh` - Automated creation script

## Output

- `demo.mp4` - Video without audio
- `demo_with_audio.mp4` - **Final video with audio (use this)**
- `demo.gif` - Animated GIF (silent)

## Requirements

```bash
# Install VHS
go install github.com/charmbracelet/vhs@latest

# ffmpeg should already be installed, if not:
sudo apt-get install ffmpeg
```

## Customization

### Change Audio Volume
```bash
ffmpeg -i demo.mp4 -i prism.mp3 \
  -filter_complex "[1:a]volume=0.5[audio]" \
  -map 0:v -map "[audio]" -c:v copy -c:a aac \
  -shortest demo_with_audio.mp4
```

### Loop Audio (if audio shorter than video)
```bash
ffmpeg -i demo.mp4 -stream_loop -1 -i prism.mp3 \
  -c:v copy -c:a aac -shortest demo_with_audio.mp4
```

### Different Audio Format
Replace `prism.mp3` with your audio file and update the script.
