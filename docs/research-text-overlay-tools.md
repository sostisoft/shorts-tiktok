# Research: Local Software for Video Text Overlays (YouTube Shorts)

Date: 2026-03-20

This document covers local/open-source tools for adding text overlays to videos,
specifically for creating YouTube Shorts (1080x1920 vertical video).

---

## Table of Contents

1. [FFmpeg Text Overlay Capabilities](#1-ffmpeg-text-overlay-capabilities)
2. [MoviePy (Python)](#2-moviepy-python)
3. [Remotion (JavaScript/React)](#3-remotion-javascriptreact)
4. [Editly (Node.js / JSON-based)](#4-editly-nodejs--json-based)
5. [Manim (Python)](#5-manim-python)
6. [VidPy (Python / MLT)](#6-vidpy-python--mlt)
7. [MLT / Melt (CLI)](#7-mlt--melt-cli)
8. [Kdenlive](#8-kdenlive)
9. [Shotcut](#9-shotcut)
10. [OpenShot](#10-openshot)
11. [Natron](#11-natron)
12. [ASS Subtitle Format for Styled Overlays](#12-ass-subtitle-format-for-styled-overlays)
13. [Open-Source Short Video Pipelines](#13-open-source-short-video-pipelines)
14. [Tool Comparison Matrix](#14-tool-comparison-matrix)
15. [Recommendations](#15-recommendations)

---

## 1. FFmpeg Text Overlay Capabilities

FFmpeg's `drawtext` filter is the most powerful CLI-based text overlay tool. It
supports dynamic expressions evaluated per-frame, enabling sophisticated animations.

### Basic drawtext Usage

```bash
ffmpeg -i input.mp4 -vf "drawtext=text='Hello World': \
  fontfile=/path/to/font.ttf:fontsize=64:fontcolor=white: \
  x=(w-text_w)/2:y=(h-text_h)/2" \
  -c:a copy output.mp4
```

### Styling Options

| Parameter       | Example                          | Description                        |
|-----------------|----------------------------------|------------------------------------|
| `fontfile`      | `/path/to/Arial.ttf`            | TrueType font path                 |
| `fontsize`      | `64`                             | Font size in pixels                 |
| `fontcolor`     | `white`, `#FF0000`, `0xRRGGBB`  | Text color                          |
| `shadowcolor`   | `black`                          | Shadow color                        |
| `shadowx/y`     | `2`                              | Shadow offset                       |
| `bordercolor`   | `black`                          | Outline/border color                |
| `borderw`       | `3`                              | Border/outline width                |
| `box`           | `1`                              | Enable background box               |
| `boxcolor`      | `black@0.5`                      | Box color with alpha                |
| `boxborderw`    | `10`                             | Padding inside box                  |

### Text Positioning for Vertical Video (1080x1920)

```bash
# Center of screen
x=(w-text_w)/2:y=(h-text_h)/2

# Top third (good for Shorts titles)
x=(w-text_w)/2:y=h*0.15

# Bottom third (good for captions)
x=(w-text_w)/2:y=h*0.75

# Offset from center
x=(w-text_w)/2+0:y=(h-text_h)/2-200
```

### Animation: Fade In / Fade Out

```bash
# Fade in from t=1.0 to t=1.5, visible until t=4.7, fade out by t=5.0
ffmpeg -y -i input.mp4 \
  -vf "drawtext=text='Fade Demo': \
    fontfile=font.ttf:fontsize=64:fontcolor=white: \
    x=(w-text_w)/2:y=(h-text_h)/2: \
    alpha=if(lt(t\,1.0)\,0\,if(lt(t\,1.5)\,(t-1.0)/0.5\,if(lt(t\,4.7)\,1\,if(lt(t\,5.0)\,((5.0-t)/0.3)\,0)))): \
    enable='between(t,1.0,5.0)'" \
  -c:a copy output.mp4
```

**Alpha expression breakdown:**
- `t < 1.0` => alpha=0 (invisible)
- `1.0 <= t < 1.5` => alpha ramps 0->1 (fade in over 0.5s)
- `1.5 <= t < 4.7` => alpha=1 (fully visible)
- `4.7 <= t < 5.0` => alpha ramps 1->0 (fade out over 0.3s)

### Animation: Pop / Scale-In (Sine Easing)

```bash
# Text pops from 70% to 100% size with sine easing
fontsize=if(lt(t\,1.3)\,48*0.7+48*0.3*sin(PI/2*(t-1.0)/0.3)\,48)

# Pop-bounce (overshoots to ~110% then settles)
fontsize=if(lt(t\,1.3)\,48*0.7+48*0.4*sin(PI/2*(t-1.0)/0.3)\,48)
```

### Animation: Scrolling Text (Bottom to Top)

```bash
# Credits-style scroll
ffmpeg -i input.mp4 -vf "drawtext=textfile=credits.txt: \
  x=(w-text_w)/2:y=h-80*t: \
  fontsize=36:fontcolor=yellow@0.9: \
  box=1:boxcolor=black@0.6" \
  -c:a copy output.mp4
```

The formula `y=h-[speed]*t` moves text upward. Adjust the multiplier for speed.

### Animation: Slide In from Left

```bash
# Slide in from off-screen left to center over 0.5s starting at t=1
x=if(lt(t\,1)\,-text_w\,if(lt(t\,1.5)\,-text_w+(w/2+text_w/2)*(t-1)/0.5\,(w-text_w)/2))
```

### Timing Control with `enable`

```bash
# Show text only between t=2s and t=5s
enable='between(t,2,5)'

# Show text based on frame number
enable='between(n,60,150)'
```

### Chaining Multiple Text Overlays (Sequential)

```bash
ffmpeg -i input.mp4 -filter_complex " \
  [0:v]drawtext=text='First':fontsize=72:fontcolor=white: \
    x=(w-text_w)/2:y=(h-text_h)/2: \
    enable='between(t,0,2)'[v1]; \
  [v1]drawtext=text='Second':fontsize=72:fontcolor=yellow: \
    x=(w-text_w)/2:y=(h-text_h)/2: \
    enable='between(t,2,4)'[v2]; \
  [v2]drawtext=text='Third':fontsize=72:fontcolor=cyan: \
    x=(w-text_w)/2:y=(h-text_h)/2: \
    enable='between(t,4,6)'" \
  -map "[v2]" -c:a copy output.mp4
```

**Performance note:** Each drawtext filter adds overhead. For many overlays, consider
pre-rendering text sequences or using ASS subtitles instead.

### Burning Subtitles (SRT/ASS) into Video

```bash
# Burn SRT subtitles
ffmpeg -i input.mp4 -vf "subtitles=captions.srt" output.mp4

# Burn ASS subtitles (preserves all styling)
ffmpeg -i input.mp4 -vf "ass=styled.ass" output.mp4

# Burn SRT with forced styling
ffmpeg -i input.mp4 -filter_complex \
  "subtitles=input.srt:force_style='FontName=Arial,FontSize=24, \
  PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000, \
  BackColour=&HA0000000,BorderStyle=4,Outline=2'" output.mp4
```

### FFmpeg Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | YES - fully CLI-based |
| Fonts/colors/styling       | Full TrueType font support, colors, shadows, outlines, boxes |
| Animations                 | Fade, slide, scroll, scale via per-frame expressions |
| Vertical video (1080x1920) | YES - any resolution |
| Subtitle support           | SRT, ASS, SSA via subtitles/ass filters |
| Batch processing           | Excellent - shell scripting |
| Limitations                | Complex expression syntax, no curve-based keyframes, performance degrades with many drawtext filters |

---

## 2. MoviePy (Python)

MoviePy is a Python library for video editing that wraps FFmpeg with a Pythonic API.

### Basic Text Overlay

```python
import moviepy as mp

# Load video
clip = mp.VideoFileClip("input.mp4")

# Create text clip
text = (
    mp.TextClip(
        font="Arial.ttf",
        text="Hello Shorts!",
        font_size=72,
        color="white",
        stroke_color="black",
        stroke_width=3,
        bg_color="#00000088",
        margin=(20, 10, 10, 10),
        text_align="center",
    )
    .with_duration(3)
    .with_position("center")
    .with_start(1)  # appear at t=1s
)

# Composite
result = mp.CompositeVideoClip([clip, text])
result.write_videofile("output.mp4", fps=30)
```

### Vertical Video (1080x1920)

```python
# Create vertical base
base = mp.ColorClip((1080, 1920), color=(0, 0, 0), duration=10)

# Or resize existing video to vertical
clip = mp.VideoFileClip("input.mp4").resized((1080, 1920))

# Position text for vertical layout
title = (
    mp.TextClip("Arial.ttf", "YOUR TITLE", font_size=80, color="white")
    .with_duration(3)
    .with_position(("center", 300))  # 300px from top
)
```

### Animated Text (Position Function)

```python
# Slide in from left
def slide_in(t):
    if t < 0.5:
        x = -500 + (540 + 500) * (t / 0.5)  # slide to center
    else:
        x = 540  # stay centered (for 1080 width)
    return (x, 960)

text = (
    mp.TextClip("font.ttf", "Sliding!", font_size=64, color="white")
    .with_duration(3)
    .with_position(slide_in)
)
```

### Built-in Effects

```python
from moviepy import vfx

# Fade in
text = text.with_effects([vfx.FadeIn(0.5)])

# Fade out
text = text.with_effects([vfx.FadeOut(0.5)])

# Slide in (if available in your version)
text = text.with_effects([vfx.SlideIn(0.5, "left")])
```

### MoviePy Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | YES - Python scripting, can wrap in CLI |
| Fonts/colors/styling       | Full font support via Pango, colors, stroke, bg |
| Animations                 | Position functions, fade, slide, custom per-frame |
| Vertical video (1080x1920) | YES - arbitrary dimensions |
| Subtitle support           | Can load SRT, render as TextClips |
| Batch processing           | Excellent - Python loops, multiprocessing |
| Limitations                | Slower than raw FFmpeg, TextClip rendering uses ImageMagick/Pango, memory-heavy for long videos |

---

## 3. Remotion (JavaScript/React)

Remotion lets you create videos programmatically using React components.
Every frame is a React component render.

### Key Concepts

```tsx
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

export const TitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Fade in over 15 frames
  const opacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Slide up from 50px below
  const translateY = interpolate(frame, [0, 20], [50, 0], {
    extrapolateRight: "clamp",
  });

  return (
    <div style={{
      opacity,
      transform: `translateY(${translateY}px)`,
      fontSize: 72,
      color: "white",
      textShadow: "2px 2px 4px black",
    }}>
      Your Text Here
    </div>
  );
};
```

### Vertical Video (1080x1920)

```tsx
// In root composition
<Composition
  id="MyShort"
  component={MyShortVideo}
  width={1080}
  height={1920}
  fps={30}
  durationInFrames={30 * 60}  // 60 seconds
/>
```

### TikTok-Style Word-by-Word Captions

Remotion has a dedicated TikTok template with `createTikTokStyleCaptions()`:

```tsx
import { createTikTokStyleCaptions } from "@remotion/captions";

const { pages } = createTikTokStyleCaptions({
  captions: transcribedCaptions,
  combineTokensWithinMilliseconds: 800,  // words per "page"
});
```

- Low values (200-500ms): word-by-word animation (classic TikTok style)
- High values (1200-2000ms): multiple words per page

### CLI Rendering

```bash
npx remotion render src/index.tsx MyShort out/short.mp4
```

### Remotion Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | YES - CLI rendering, programmatic API |
| Fonts/colors/styling       | Full CSS/React styling (unlimited possibilities) |
| Animations                 | React + `interpolate()` = any animation imaginable |
| Vertical video (1080x1920) | YES - set in Composition config |
| Subtitle support           | Native caption support, TikTok template, SRT import |
| Batch processing           | YES - parameterized renders, Lambda support |
| Limitations                | Node.js ecosystem required, heavier setup, rendering can be slow, Chromium dependency |

---

## 4. Editly (Node.js / JSON-based)

Editly is a declarative, JSON-driven video editor built on FFmpeg.

### JSON Configuration

```json5
{
  "outPath": "short.mp4",
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "clips": [
    {
      "duration": 4,
      "transition": { "name": "fade" },
      "layers": [
        { "type": "video", "path": "background.mp4", "cutFrom": 0, "cutTo": 4 },
        { "type": "title", "text": "YOUR TITLE HERE", "textColor": "#ffffff" }
      ]
    },
    {
      "duration": 3,
      "layers": [
        { "type": "image", "path": "photo.jpg" },
        { "type": "subtitle", "text": "Caption text goes here" }
      ]
    },
    {
      "duration": 3,
      "layers": [
        { "type": "video", "path": "clip2.mp4" },
        {
          "type": "news-title",
          "text": "Breaking: Something Happened",
          "backgroundColor": "#cc0000"
        }
      ]
    }
  ]
}
```

### Built-in Text Layer Types

| Type               | Description                                      |
|--------------------|--------------------------------------------------|
| `title`            | Large centered text with customizable color       |
| `subtitle`         | Smaller caption-style text                        |
| `title-background` | Text with gradient or solid color background       |
| `news-title`       | Broadcast-style lower-third with background color  |
| `slide-in-text`    | Animated text with character spacing               |

### CLI Usage

```bash
# Quick creation
editly title:'My Short' clip1.mp4 title:'THE END' --fast

# From JSON spec
editly my-spec.json5 --out output.mp4

# With audio
editly spec.json5 --audio-file-path music.mp3 --keep-source-audio
```

### Editly Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | YES - CLI + JSON specs + Node.js API |
| Fonts/colors/styling       | Built-in text types, custom Canvas/Fabric.js for advanced |
| Animations                 | 50+ transitions, slide-in text, Ken Burns on images |
| Vertical video (1080x1920) | YES - any width/height, auto letterboxing |
| Subtitle support           | Built-in subtitle layer type |
| Batch processing           | YES - generate JSON specs programmatically |
| Limitations                | Limited text animation variety, no per-character animation, project less actively maintained (5k stars, last update varies) |

---

## 5. Manim (Python)

Manim is an animation engine originally built for 3Blue1Brown's math videos.

### Text Animation Example

```python
from manim import *

class ShortTitle(Scene):
    def construct(self):
        # Configure for vertical video
        self.camera.frame_width = 6.0  # adjust aspect ratio

        title = Text("AMAZING FACT", font_size=72, color=WHITE)
        subtitle = Text("You won't believe this", font_size=36, color=YELLOW)
        subtitle.next_to(title, DOWN)

        # Animated appearance
        self.play(Write(title), run_time=1)
        self.play(FadeIn(subtitle, shift=UP), run_time=0.5)
        self.wait(2)
        self.play(FadeOut(title, subtitle))
```

### Available Text Animations

- `Write()` - handwriting-style appearance
- `FadeIn()` / `FadeOut()` - with optional shift direction
- `GrowFromCenter()`, `SpinInFromNothing()`
- `Transform()` - morph between text states
- `AddTextLetterByLetter()` - typewriter effect
- LaTeX rendering for mathematical formulas (`MathTex`, `Tex`)

### Rendering

```bash
manim -pql scene.py ShortTitle     # preview quality
manim -qh scene.py ShortTitle      # high quality
manim --resolution 1080,1920 ...   # custom resolution
```

### Manim Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | YES - Python + CLI rendering |
| Fonts/colors/styling       | Fonts, colors, LaTeX, SVG |
| Animations                 | Exceptional - Write, FadeIn, Transform, morphing, etc. |
| Vertical video (1080x1920) | YES - custom resolution flag |
| Subtitle support           | No native subtitle format support |
| Batch processing           | YES - Python scripting |
| Limitations                | Designed for math/educational content, not general video editing. Cannot overlay on existing video directly (renders to its own scene). Requires LaTeX for Tex features. |

---

## 6. VidPy (Python / MLT)

VidPy is a Python video editing library built on the MLT multimedia framework.

### Text Overlay

```python
from vidpy import Clip, Composition, Text

# Text overlay on video
clip = Clip("video.mp4")
clip.text("Title Text", color="#ffffff", size=100,
          halign="center", valign="top",
          font="Sans Bold", olcolor="#000000")

comp = Composition([clip])
comp.save("output.mp4")

# Standalone text clip
title = Text("Hello World!", font="Arial", size=80,
             color="#ffffff", bgcolor="#000000",
             bbox=(0, 0, 1080, 1920))
```

### Text Parameters

- `font` - Font family name
- `size` - Font size
- `color` - Text foreground color
- `olcolor` - Outline color
- `bgcolor` - Background color
- `halign` - center, left, right
- `valign` - middle, top, bottom
- `weight` - 100-1000 (font weight)
- `style` - normal, italic
- `bbox` - bounding box as (x, y, w, h), supports percentages

### VidPy Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | YES - Python API |
| Fonts/colors/styling       | Full font control, colors, outlines, backgrounds |
| Animations                 | move(), zoompan() with keyframes, speed control |
| Vertical video (1080x1920) | YES - set in Composition |
| Subtitle support           | Via MLT filters |
| Batch processing           | YES - Python scripting |
| Limitations                | Smaller community, depends on MLT installation, less documentation than MoviePy |

---

## 7. MLT / Melt (CLI)

MLT (Media Lovin' Toolkit) is the framework behind Kdenlive and Shotcut.
`melt` is its CLI tool.

### Text Overlay with Melt

```bash
melt input.mp4 -filter dynamictext text="Hello World" \
  fgcolour=#ffffffff bgcolour=#00000080 \
  halign=center valign=middle \
  size=72 family=Arial
```

### Key Features

- Direct CLI video processing
- All Kdenlive/Shotcut filters available
- Language bindings: C++, Python, Ruby, Lua, Java, Perl, PHP, Tcl
- Can run headless on servers / render farms
- XML-based project format interoperable with Kdenlive

### MLT/Melt Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | YES - melt CLI + language bindings |
| Fonts/colors/styling       | Full text styling via dynamictext filter |
| Animations                 | Keyframe-based via XML, transitions |
| Vertical video (1080x1920) | YES |
| Subtitle support           | Via filters |
| Batch processing           | Excellent - headless server rendering |
| Limitations                | Sparse documentation, steep learning curve, less intuitive than FFmpeg for simple tasks |

---

## 8. Kdenlive

Kdenlive is a professional open-source video editor built on MLT.

### Automation Capabilities

- Can generate `melt` rendering scripts for batch processing
- Rendering scripts can be accumulated and executed in batch overnight
- `kdenlive_render` CLI command for headless rendering
- MLT XML project format can be generated/modified programmatically

### Text Features

- Rich text editor with fonts, sizes, colors, alignment
- Letter spacing, line spacing
- Text shadows, backgrounds, patterns
- Title animations

### Kdenlive Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | PARTIAL - render scripts via melt, MLT XML manipulation |
| Fonts/colors/styling       | Rich text editor: fonts, colors, shadows, backgrounds |
| Animations                 | Keyframe-based, title animations |
| Vertical video (1080x1920) | YES - custom project profiles |
| Subtitle support           | SRT import/export, subtitle track |
| Batch processing           | YES - via render scripts and melt |
| Limitations                | Primarily GUI, automation requires MLT XML knowledge |

---

## 9. Shotcut

Shotcut is an open-source video editor also built on MLT.

### Text Features

- Three text modes: GPS text, Simple text, Rich text
- Timer, frame counter, and timecode overlays
- Font, size, color, alignment, outline, background
- HTML-based text editor for rich formatting

### Shotcut Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | MINIMAL - primarily GUI, uses MLT under the hood |
| Fonts/colors/styling       | Good - multiple text modes with rich formatting |
| Animations                 | Keyframe-based position/size/opacity |
| Vertical video (1080x1920) | YES - custom video mode |
| Subtitle support           | SRT import |
| Batch processing           | LIMITED - no built-in batch, could use MLT XML |
| Limitations                | GUI-focused, no real CLI/API for automation |

---

## 10. OpenShot

OpenShot is a beginner-friendly open-source video editor.

### Text Features

- Blender-based 3D animated titles
- SVG title templates
- Basic text overlay with font/color

### OpenShot Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | PARTIAL - Python API (libopenshot) exists |
| Fonts/colors/styling       | Basic text + Blender 3D titles |
| Animations                 | Keyframe-based, Blender integration for 3D |
| Vertical video (1080x1920) | YES - custom profiles |
| Subtitle support           | Basic |
| Batch processing           | LIMITED |
| Limitations                | Fewer text effects than Kdenlive/Shotcut, stability issues reported |

---

## 11. Natron

Natron is an open-source node-based compositor (similar to After Effects/Nuke).

### Key Features

- Node-graph compositing (After Effects-like power)
- Python scripting API
- Can run headless (no GUI) for batch rendering / render farms
- PySide integration for custom UI extensions
- Text node with font/size/color controls

### Natron Summary

| Feature                    | Capability |
|----------------------------|------------|
| Scriptable/CLI             | YES - Python scripting, headless CLI rendering |
| Fonts/colors/styling       | Full text node with fonts, colors, sizing |
| Animations                 | Full keyframe animation on any parameter |
| Vertical video (1080x1920) | YES |
| Subtitle support           | No native subtitle format support |
| Batch processing           | YES - headless rendering, render farm support |
| Limitations                | Complex setup for simple text overlays, development pace has slowed (community-maintained), overkill for basic text on video |

---

## 12. ASS Subtitle Format for Styled Overlays

ASS (Advanced SubStation Alpha) is the most powerful subtitle format for styled text.
It can be burned into video with FFmpeg, producing results comparable to motion graphics.

### File Structure

```
[Script Info]
Title: My Shorts Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,1,3,1,2,30,30,60,1
Style: Title,Impact,90,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,4,2,5,30,30,30,1
Style: Highlight,Arial,70,&H0000FFFF,&H000000FF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,1,3,1,2,30,30,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Title,,0,0,0,,{\fad(500,0)\an5\pos(540,400)}AMAZING FACT
Dialogue: 0,0:00:03.00,0:00:06.00,Default,,0,0,0,,{\fad(300,300)}This is the first caption
Dialogue: 0,0:00:06.00,0:00:09.00,Highlight,,0,0,0,,{\fad(300,300)}And this is highlighted
```

### Color Format

ASS uses `&HAABBGGRR` format (NOT standard RGB):
- `&H00FFFFFF` = white (fully opaque)
- `&H000000FF` = red
- `&H00FF0000` = blue
- `&HA0000000` = semi-transparent black

Four color channels:
- `PrimaryColour` (\c or \1c) - main text fill
- `SecondaryColour` (\2c) - karaoke fill before highlight
- `OutlineColour` (\3c) - border/outline
- `BackColour` (\4c) - shadow

### Override Tags (Inline Styling)

These tags go inside `{}` in the dialogue text:

**Positioning & Movement:**
```
{\pos(540,960)}           - Fixed position (centered on 1080x1920)
{\an5}                    - Alignment: 5=center, 2=bottom-center, 8=top-center
{\move(0,960,540,960)}    - Move from (0,960) to (540,960) over line duration
{\move(x1,y1,x2,y2,t1,t2)} - Move with specific timing (ms)
{\org(540,960)}           - Set rotation origin point
```

**Fade & Transparency:**
```
{\fad(500,300)}           - Fade in 500ms, fade out 300ms
{\fade(a1,a2,a3,t1,t2,t3,t4)} - Complex multi-point fade
{\alpha&H80}              - Set all channels to 50% transparent
{\1a&H00}                 - Primary color fully opaque
{\3a&HFF}                 - Outline fully transparent
```

**Transform (Animation Over Time):**
```
{\t(\fscx150\fscy150)}                    - Scale to 150% over line duration
{\t(0,2000,\frz360)}                      - Rotate 360 degrees over 2 seconds
{\t(0,1000,\fscx80\fscy80\t(1000,2000,\fscx100\fscy100))} - Scale down then up
{\t(0,2000,3,\frz360)}                    - Rotate with acceleration (3=start slow, end fast)
{\fscx80\fscy80\t(0,2000,\fscx100\fscy100)} - Grow from 80% to 100% over 2s
```

**Accel parameter in \t:**
- `1` = linear (constant speed)
- `< 1` = start fast, end slow (decelerate)
- `> 1` = start slow, end fast (accelerate)

**Font & Text Styling:**
```
{\fn Impact}              - Change font
{\fs72}                   - Font size
{\b1}                     - Bold on
{\i1}                     - Italic on
{\fsp5}                   - Letter spacing +5
{\c&H00FFFF&}             - Primary color (yellow)
{\3c&H000000&}            - Outline color (black)
{\bord4}                  - Outline width 4
{\shad2}                  - Shadow distance 2
{\blur2}                  - Edge blur (softer text)
{\fscx120}                - Horizontal scale 120%
{\fscy120}                - Vertical scale 120%
{\frz-10}                 - Rotate -10 degrees on Z axis
{\frx30}                  - 3D rotation on X axis
{\fry30}                  - 3D rotation on Y axis
```

**Karaoke Effects:**
```
{\k50}Word                - Highlight after 500ms (instant fill)
{\kf50}Word               - Smooth sweep fill over 500ms
{\ko50}Word               - Outline appears on highlight
```

**Clipping (Masking):**
```
{\clip(100,100,500,500)}  - Only show text within rectangle
{\iclip(100,100,500,500)} - Hide text within rectangle (inverse)
```

### Burning ASS into Video with FFmpeg

```bash
# Simple burn
ffmpeg -i input.mp4 -vf "ass=styled.ass" output.mp4

# With font directory
ffmpeg -i input.mp4 -vf "ass=styled.ass:fontsdir=/path/to/fonts" output.mp4

# Using subtitles filter (also supports ASS)
ffmpeg -i input.mp4 -vf "subtitles=styled.ass" output.mp4
```

### Tools for Creating ASS Files

| Tool       | Type        | Description |
|------------|-------------|-------------|
| **Aegisub** | GUI (desktop) | Gold standard ASS editor, visual timing, preview |
| **NyuFX**  | Lua scripting | Karaoke effects creation tool for ASS |
| **Python**  | Scripting   | Generate ASS files programmatically (plain text format) |

### Why ASS is Powerful for Shorts

1. **One file controls all text** - easier to manage than many drawtext filters
2. **Frame-accurate timing** - millisecond precision
3. **Rich styling per-line** - different styles for different text elements
4. **Animation via \t tag** - scale, rotate, fade, color change over time
5. **Movement via \move** - slide text across screen
6. **Karaoke effects** - word-by-word highlighting
7. **Performant** - FFmpeg renders ASS subtitles efficiently in a single pass
8. **Portable** - text file, easy to version control and generate programmatically

---

## 13. Open-Source Short Video Pipelines

### short-video-maker (gyoridavid)

- **Tech:** Remotion + FFmpeg + Whisper.cpp + Kokoro TTS
- **URL:** https://github.com/gyoridavid/short-video-maker
- **What it does:** Converts text input into complete short videos with:
  - Auto-generated voiceover (Kokoro TTS)
  - Auto-generated captions (Whisper)
  - Background video from Pexels API
  - Background music (mood/genre selectable)
  - Portrait or landscape orientation
- **Interfaces:** REST API + MCP server + Web UI
- **Docker:** `docker run -p 3123:3123 -e PEXELS_API_KEY=... gyoridavid/short-video-maker:latest-tiny`
- **Note:** Uses local TTS and Whisper (not cloud AI), but the speech/caption generation is AI-adjacent

### Remotion Superpowers (DojoCodingLabs)

- **Tech:** Remotion + multiple MCP servers
- **URL:** https://github.com/dojocodinglabs/remotion-superpowers
- **What it does:** Claude Code plugin for full video production
- **Features:** AI voiceovers, stock footage, image generation, TikTok captions, 3D, transitions

### AI-Youtube-Shorts-Generator (SaarD00)

- **Tech:** Python + FFmpeg + Pexels API
- **URL:** https://github.com/SaarD00/AI-Youtube-Shorts-Generator
- **What it does:** "Faceless" YouTube Shorts factory
- **Note:** Uses Gemini AI for scripts, but the video assembly pipeline (FFmpeg + stock footage + text overlay) is instructive for building a non-AI version

### DIY Pipeline (No AI) - Conceptual

A fully non-AI pipeline could be built with:

```
1. Stock footage: Pexels/Pixabay API (free, no AI)
2. Text overlays: FFmpeg drawtext OR ASS subtitles
3. Audio: royalty-free music files
4. Assembly: FFmpeg filter_complex or Editly JSON
5. Orchestration: Python/Bash script

Flow:
  config.json -> Python script -> generates ASS file
                               -> downloads stock footage
                               -> calls FFmpeg to composite
                               -> outputs final 1080x1920 MP4
```

---

## 14. Tool Comparison Matrix

| Tool          | CLI/Script | Text Style | Animations    | Vertical | Subtitles | Batch  | Best For |
|---------------|-----------|------------|---------------|----------|-----------|--------|----------|
| **FFmpeg**    | CLI       | Good       | Expression-based | Yes    | SRT/ASS   | Great  | Direct CLI automation |
| **MoviePy**   | Python    | Good       | Function-based | Yes     | SRT       | Great  | Python pipelines |
| **Remotion**  | JS/CLI    | Excellent  | React/CSS     | Yes      | Native    | Great  | Complex animations |
| **Editly**    | JSON/CLI  | Good       | Transitions   | Yes      | Basic     | Great  | Quick JSON-driven videos |
| **Manim**     | Python    | Good       | Excellent     | Yes      | No        | Good   | Educational/math content |
| **VidPy**     | Python    | Good       | Keyframes     | Yes      | Via MLT   | Good   | MLT-based workflows |
| **Melt/MLT**  | CLI       | Good       | Keyframes     | Yes      | Filters   | Great  | Server-side rendering |
| **Kdenlive**  | GUI+CLI   | Excellent  | Keyframes     | Yes      | SRT       | Partial| Manual + batch render |
| **Shotcut**   | GUI       | Good       | Keyframes     | Yes      | SRT       | Poor   | Manual editing |
| **OpenShot**  | GUI       | Basic      | Basic         | Yes      | Basic     | Poor   | Beginners |
| **Natron**    | GUI+Python| Good       | Full keyframe | Yes      | No        | Good   | VFX compositing |
| **ASS subs**  | Text file | Excellent  | Move/Transform| Yes      | IS subtitle| Great | Styled captions |

---

## 15. Recommendations

### For a Fully Automated Shorts Pipeline (No GUI):

**Best approach: FFmpeg + ASS subtitles**
- Generate ASS files programmatically (Python)
- Use FFmpeg to composite stock footage + ASS overlays
- Shell/Python script for orchestration
- Pros: Fast, reliable, no heavy dependencies
- Cons: Complex ASS syntax for advanced animations

**Runner-up: Editly (JSON-based)**
- Define videos as JSON5 specs
- Generate specs from Python/Node.js
- Built-in text layers and transitions
- Pros: Simple, declarative, good transitions
- Cons: Limited text animation variety

### For Maximum Animation Quality:

**Best: Remotion**
- Full React/CSS animation capabilities
- TikTok caption template built-in
- Any animation possible via JavaScript
- Pros: Unlimited styling, great ecosystem
- Cons: Heavier setup, Node.js required, slower rendering

### For Python-First Workflows:

**Best: MoviePy + FFmpeg ASS burn-in**
- MoviePy for video assembly/composition
- Generate ASS files for styled text
- FFmpeg for final render with burned subtitles
- Pros: Pythonic, flexible, well-documented
- Cons: Slower than pure FFmpeg

### For Quick Prototyping:

**Editly** for fast iteration with JSON specs, or **short-video-maker** if you
want a ready-made pipeline with REST API.

---

## Key Sources

- [FFmpeg drawtext animations exploration](https://www.braydenblackwell.com/blog/ffmpeg-text-rendering)
- [FFmpeg drawtext dynamic overlays (OTTVerse)](https://ottverse.com/ffmpeg-drawtext-filter-dynamic-overlays-timecode-scrolling-text-credits/)
- [FFmpeg By Example: Fade text](https://ffmpegbyexample.com/examples/50gowmkq/fade_in_and_out_text_using_the_drawtext_filter/)
- [FFmpeg subtitle burn-in guide](https://maxime.sh/posts/burn-styled-subtitles-with-ffmpeg/)
- [FFmpeg subtitles with 5 styles (Bannerbear)](https://www.bannerbear.com/blog/how-to-add-subtitles-to-a-video-with-ffmpeg-5-different-styles/)
- [FFmpeg subtitles comprehensive (ffmpeg.media)](https://www.ffmpeg.media/articles/subtitles-burn-in-soft-subs-format-conversion)
- [MoviePy GitHub](https://github.com/Zulko/moviepy)
- [MoviePy TextClip docs](https://zulko.github.io/moviepy/reference/reference/moviepy.video.VideoClip.TextClip.html)
- [Remotion official site](https://www.remotion.dev/)
- [Remotion TikTok template](https://www.remotion.dev/templates/tiktok)
- [Remotion createTikTokStyleCaptions](https://www.remotion.dev/docs/captions/create-tiktok-style-captions)
- [Editly GitHub](https://github.com/mifi/editly)
- [Editly npm](https://www.npmjs.com/package/editly)
- [Manim Community](https://www.manim.community/)
- [Manim text rendering docs](https://docs.manim.community/en/stable/guides/using_text.html)
- [VidPy documentation](https://antiboredom.github.io/vidpy/documentation.html)
- [MLT melt documentation](https://www.mltframework.org/docs/melt/)
- [Natron GitHub](https://github.com/NatronGitHub/Natron)
- [Natron Python scripting](https://github.com/NatronGitHub/natron-python-scripting)
- [ASS format guide (QuickLRC)](https://www.quicklrc.com/subtitle-formats/ass)
- [ASS override tags (Aegisub)](https://aegisub.org/docs/latest/ass_tags/)
- [ASS advanced typesetting (unanimated)](https://unanimated.github.io/ts/ts-moving.htm)
- [SSA/ASS styling guide (SubZap)](https://subzap.ai/blog/004-ssa-ass)
- [short-video-maker GitHub](https://github.com/gyoridavid/short-video-maker)
- [Remotion Superpowers GitHub](https://github.com/dojocodinglabs/remotion-superpowers)
- [Kdenlive rendering docs](https://docs.kdenlive.org/en/exporting/render.html)
