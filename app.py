import streamlit as st
import os
import tempfile
import subprocess
import textwrap
import shutil
import asyncio
from pathlib import Path

import edge_tts
from PIL import Image, ImageDraw, ImageFont

st.set_page_config(
    page_title="ALI VIDEO MAKER",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 ALI VIDEO MAKER")
st.caption("Create narrated videos from your script")

st.markdown("### 🎥 Video Studio")

script = st.text_area(
    "Your scenario",
    height=220,
    placeholder="Write your video scenario here..."
)

voice_choice = st.selectbox(
    "Narration language",
    ["Persian/Dari", "English"]
)

format_choice = st.selectbox(
    "Video format",
    ["Vertical 9:16", "Landscape 16:9"]
)

title = st.text_input("Video title", "My Video")

make = st.button("🎬 Create Video", type="primary")


def split_scenes(text):
    scenes = [
        s.strip()
        for s in text.replace("\r", "").split("\n\n")
        if s.strip()
    ]

    if len(scenes) <= 1:
        scenes = [
            s.strip()
            for s in text.replace("؟", "?").split(".")
            if s.strip()
        ]

    return scenes[:12]


async def create_voice(text, filename, language):
    if language == "Persian/Dari":
        voice = "fa-IR-FaridNeural"
    else:
        voice = "en-US-GuyNeural"

    communicate = edge_tts.Communicate(
        text,
        voice
    )

    await communicate.save(filename)


def make_image(text, filename, size, number):
    img = Image.new("RGB", size, (18, 22, 35))
    draw = ImageDraw.Draw(img)

    draw.rectangle(
        (0, 0, size[0], 18),
        fill=(212, 170, 75)
    )

    draw.rectangle(
        (0, size[1] - 18, size[0], size[1]),
        fill=(212, 170, 75)
    )

    font = None

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, 55)
                break
            except Exception:
                pass

    if font is None:
        font = ImageFont.load_default()

    wrapped = textwrap.fill(text, width=26)

    draw.multiline_text(
        (size[0] // 2, size[1] // 2),
        wrapped,
        fill="white",
        font=font,
        anchor="mm",
        align="center",
        spacing=25
    )

    draw.text(
        (50, 50),
        str(number),
        fill=(212, 170, 75),
        font=font
    )

    img.save(filename)


def render_video(image, audio, output, size):
    width, height = size

    command = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(image),
        "-i", str(audio),
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan=z='min(zoom+0.0005,1.08)':"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"d=125:s={width}x{height}:fps=25",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-r", "25",
        str(output)
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )


if make:

    if not script.strip():
        st.warning("Please enter your scenario.")

    else:

        ffmpeg = shutil.which("ffmpeg")

        if not ffmpeg:
            st.error("FFmpeg is not installed.")
        else:

            try:

                scenes = split_scenes(script)

                work = Path(tempfile.mkdtemp())

                segments = []

                size = (
                    (1080, 1920)
                    if format_choice.startswith("Vertical")
                    else (1920, 1080)
                )

                progress = st.progress(0)

                status = st.empty()

                for i, scene in enumerate(scenes):

                    status.write(
                        f"Creating scene {i+1}/{len(scenes)}..."
                    )

                    image_path = work / f"scene_{i}.png"

                    audio_path = work / f"audio_{i}.mp3"

                    segment_path = work / f"segment_{i}.mp4"

                    make_image(
                        scene,
                        image_path,
                        size,
                        i + 1
                    )

                    language = voice_choice

                    asyncio.run(
                        create_voice(
                            scene,
                            str(audio_path),
                            language
                        )
                    )

                    render_video(
                        image_path,
                        audio_path,
                        segment_path,
                        size
                    )

                    segments.append(segment_path)

                    progress.progress(
                        (i + 1) / len(scenes)
                    )

                status.write("Combining scenes...")

                list_file = work / "list.txt"

                with open(
                    list_file,
                    "w",
                    encoding="utf-8"
                ) as f:

                    for segment in segments:
                        f.write(
                            f"file '{segment.as_posix()}'\n"
                        )

                final_video = work / "final_video.mp4"

                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f", "concat",
                        "-safe", "0",
                        "-i", str(list_file),
                        "-c", "copy",
                        str(final_video)
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )

                status.success("Video created successfully!")

                st.video(str(final_video))

                with open(
                    final_video,
                    "rb"
                ) as video_file:

                    st.download_button(
                        "⬇️ Download MP4",
                        video_file,
                        file_name="ALI_VIDEO.mp4",
                        mime="video/mp4"
                    )

            except Exception as e:

                st.error(
                    f"Video creation failed: {e}"
                )
