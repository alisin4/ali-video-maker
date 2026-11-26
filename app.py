import streamlit as st
import os
import asyncio
import subprocess
import tempfile
import gc
import re
import shutil
from PIL import Image, ImageDraw, ImageFont
import edge_tts

st.set_page_config(page_title="ALI VIDEO MAKER", page_icon="🎬")

st.title("🎬 ALI VIDEO MAKER")
st.caption("Lightweight Script-to-Video Studio")

WIDTH = 480
HEIGHT = 854
FPS = 20
MAX_SCENES = 6

def split_scenes(text):
    parts = re.split(r'(?<=[.!؟])\s+|\n+', text.strip())
    parts = [p.strip() for p in parts if p.strip()]
    return parts[:MAX_SCENES]

def get_font():
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def create_image(text, path):
    img = Image.new("RGB", (WIDTH, HEIGHT), (20, 20, 30))
    draw = ImageDraw.Draw(img)

    font_path = get_font()
    font = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()

    # Persian text shaping and RTL
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        text = get_display(arabic_reshaper.reshape(text))
    except Exception:
        pass

    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = current + " " + word if current else word
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= WIDTH - 50:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    line_height = 42
    total_height = len(lines) * line_height
    y = max(60, (HEIGHT - total_height) // 2)

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (WIDTH - text_width) // 2
        draw.text((x, y), line, font=font, fill="white")
        y += line_height

    img.save(path, "JPEG", quality=75)
    del img, draw
    gc.collect()

async def create_voice(text, path):
    communicate = edge_tts.Communicate(
        text,
        "fa-IR-FaridNeural"
    )
    await communicate.save(path)

def get_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ],
        capture_output=True,
        text=True,
        check=True
    )
    return float(result.stdout.strip())

def make_segment(image, audio, output):
    duration = get_duration(audio)

    command = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image,
        "-i", audio,
        "-t", str(duration),
        "-vf", f"scale={WIDTH}:{HEIGHT},fps={FPS}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-threads", "1",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "64k",
        "-shortest",
        output
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def join_segments(files, output, folder):
    list_file = os.path.join(folder, "list.txt")

    with open(list_file, "w") as f:
        for file in files:
            f.write("file '{}'\n".format(file.replace("'", "'\\''")))

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

st.subheader("📝 Script")

script = st.text_area(
    "Enter your script",
    height=250,
    placeholder="داستان خود را اینجا بنویسید..."
)

if st.button("🎬 Create Video", use_container_width=True):

    if not script.strip():
        st.warning("Please enter a script.")

    else:

        folder = tempfile.mkdtemp(prefix="ali_video_")

        try:
            scenes = split_scenes(script)

            if not scenes:
                st.warning("No scenes found.")
                st.stop()

            progress = st.progress(0)
            status = st.empty()

            segment_files = []

            for i, scene in enumerate(scenes):

                status.write(f"Processing scene {i+1}/{len(scenes)}")

                image_path = os.path.join(folder, f"img_{i}.jpg")
                audio_path = os.path.join(folder, f"audio_{i}.mp3")
                segment_path = os.path.join(folder, f"segment_{i}.mp4")

                create_image(scene, image_path)

                asyncio.run(create_voice(scene, audio_path))

                make_segment(image_path, audio_path, segment_path)

                segment_files.append(segment_path)

                progress.progress((i + 1) / len(scenes))

                gc.collect()

            status.write("Joining video...")

            video_file = os.path.join(folder, "ALI_VIDEO.mp4")

            join_segments(segment_files, video_file, folder)

            status.empty()
            progress.empty()

            st.success("✅ Video created successfully!")

            st.video(video_file)

            with open(video_file, "rb") as f:
                video_bytes = f.read()

            st.download_button(
                label="⬇️ Download MP4",
                data=video_bytes,
                file_name="ALI_VIDEO.mp4",
                mime="video/mp4",
                use_container_width=True
            )

            del video_bytes
            gc.collect()

        except Exception as e:
            st.error(f"Video creation failed: {e}")

        finally:
            shutil.rmtree(folder, ignore_errors=True)
            gc.collect()
