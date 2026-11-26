import asyncio
import gc
import os
import re
import shutil
import subprocess
import tempfile

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import edge_tts
import arabic_reshaper
from bidi.algorithm import get_display


# ==========================================
# ALI VIDEO MAKER
# Lightweight version for Render 512MB
# ==========================================

st.set_page_config(
    page_title="ALI VIDEO MAKER",
    page_icon="🎬",
    layout="centered"
)

WIDTH = 360
HEIGHT = 640
FPS = 15

MAX_SCRIPT_CHARS = 1200
MAX_SCENES = 5

VOICE = "fa-IR-FaridNeural"

st.title("🎬 ALI VIDEO MAKER")
st.caption("ساخت ویدیوی کوتاه با صدای فارسی")


# ==========================================
# CHECK VIDEO TOOLS
# ==========================================

def check_tools():

    missing = [
        name for name in ("ffmpeg", "ffprobe")
        if shutil.which(name) is None
    ]

    if missing:
        raise RuntimeError(
            "ابزارهای ویدیو در سرور نصب نیستند: "
            + ", ".join(missing)
        )


# ==========================================
# SPLIT SCRIPT INTO SCENES
# ==========================================

def split_scenes(text):

    normalized = (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )

    sentences = []

    for paragraph in re.split(r"\n+", normalized):

        paragraph = paragraph.strip()

        if not paragraph:
            continue

        pieces = re.split(
            r"(?<=[.!?؟؛])\s+",
            paragraph
        )

        sentences.extend(
            piece.strip()
            for piece in pieces
            if piece.strip()
        )

    bounded = []

    for sentence in sentences:

        words = sentence.split()

        if len(words) <= 38:
            bounded.append(sentence)

        else:
            for start in range(0, len(words), 38):

                bounded.append(
                    " ".join(words[start:start + 38])
                )

    if not bounded:
        return []

    if len(bounded) <= MAX_SCENES:
        return bounded

    groups = [[] for _ in range(MAX_SCENES)]

    total_words = sum(
        max(1, len(item.split()))
        for item in bounded
    )

    target = max(1, total_words / MAX_SCENES)

    group_index = 0
    words_in_group = 0

    for item in bounded:

        item_words = max(1, len(item.split()))

        if (
            group_index < MAX_SCENES - 1
            and words_in_group >= target
        ):

            group_index += 1
            words_in_group = 0

        groups[group_index].append(item)

        words_in_group += item_words

    return [
        " ".join(group)
        for group in groups
        if group
    ]


# ==========================================
# PERSIAN FONT
# ==========================================

def find_persian_font():

    candidates = [

        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",

        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",

        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",

        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    ]

    for candidate in candidates:

        if os.path.isfile(candidate):
            return candidate

    raise RuntimeError(
        "فونت فارسی در سرور پیدا نشد."
    )


# ==========================================
# PERSIAN TEXT SHAPING
# ==========================================

def rtl_display(text):

    shaped = arabic_reshaper.reshape(text)

    return get_display(
        shaped,
        base_dir="R"
    )


# ==========================================
# CREATE SCENE IMAGE
# ==========================================

def create_image(text, output_path):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (17, 21, 34)
    )

    draw = ImageDraw.Draw(image)

    font_path = find_persian_font()

    font = ImageFont.truetype(
        font_path,
        25
    )

    small_font = ImageFont.truetype(
        font_path,
        16
    )

    words = text.split()

    lines = []
    current = ""

    max_width = WIDTH - 44

    # Wrap Persian text before shaping

    for word in words:

        candidate = (
            f"{current} {word}"
            if current else word
        )

        visual = rtl_display(candidate)

        box = draw.textbbox(
            (0, 0),
            visual,
            font=font
        )

        text_width = box[2] - box[0]

        if text_width <= max_width:

            current = candidate

        else:

            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    # Reduce font size if necessary

    while (
        len(lines) * 42 > HEIGHT - 170
        and font.size > 19
    ):

        font = ImageFont.truetype(
            font_path,
            font.size - 1
        )

    line_height = font.size + 18

    total_height = len(lines) * line_height

    y = max(
        105,
        (HEIGHT - total_height) // 2
    )

    # Decorative line

    draw.rounded_rectangle(
        (24, 28, WIDTH - 24, 34),
        radius=3,
        fill=(205, 164, 92)
    )

    # Footer

    draw.text(
        (WIDTH // 2, HEIGHT - 55),
        rtl_display("ALI VIDEO MAKER"),
        font=small_font,
        fill=(170, 176, 190),
        anchor="mm"
    )

    # Draw Persian sentences

    for line in lines:

        visual_line = rtl_display(line)

        box = draw.textbbox(
            (0, 0),
            visual_line,
            font=font
        )

        text_width = box[2] - box[0]

        x = (
            (WIDTH - text_width) // 2
            - box[0]
        )

        y_adjusted = y - box[1]

        # Text shadow

        draw.text(
            (x + 1, y_adjusted + 1),
            visual_line,
            font=font,
            fill=(0, 0, 0)
        )

        # Main text

        draw.text(
            (x, y_adjusted),
            visual_line,
            font=font,
            fill=(255, 255, 255)
        )

        y += line_height

    image.save(
        output_path,
        format="JPEG",
        quality=68,
        optimize=True
    )

    image.close()

    del draw

    gc.collect()


# ==========================================
# PERSIAN VOICE
# ==========================================

async def create_voice(text, output_path):

    communicate = edge_tts.Communicate(
        text,
        VOICE
    )

    await asyncio.wait_for(
        communicate.save(output_path),
        timeout=90
    )

    if (
        not os.path.isfile(output_path)
        or os.path.getsize(output_path) < 100
    ):

        raise RuntimeError(
            "صدای صحنه ساخته نشد."
        )


# ==========================================
# RUN COMMANDS
# ==========================================

def run_command(command, timeout=180):

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False
    )

    if result.returncode != 0:

        detail = (
            result.stderr
            or result.stdout
            or "Unknown FFmpeg error"
        ).strip()

        raise RuntimeError(detail[-1400:])

    return result


# ==========================================
# AUDIO DURATION
# ==========================================

def get_duration(audio_path):

    result = run_command([

        "ffprobe",
        "-v", "error",

        "-show_entries",
        "format=duration",

        "-of",
        "default=noprint_wrappers=1:nokey=1",

        audio_path

    ], timeout=30)

    try:

        duration = float(
            result.stdout.strip()
        )

    except (TypeError, ValueError):

        raise RuntimeError(
            "مدت صدای تولیدشده قابل تشخیص نیست."
        )

    if duration <= 0 or duration > 90:

        raise RuntimeError(
            "مدت صدا نامعتبر یا بیش از حد طولانی است."
        )

    return duration


# ==========================================
# CREATE VIDEO SEGMENT
# ==========================================

def make_segment(
    image_path,
    audio_path,
    output_path
):

    duration = get_duration(audio_path)

    command = [

        "ffmpeg",
        "-y",

        "-hide_banner",
        "-loglevel", "error",

        "-threads", "1",
        "-filter_threads", "1",

        "-loop", "1",
        "-framerate", str(FPS),
        "-i", image_path,

        "-i", audio_path,

        "-t", f"{duration:.3f}",

        "-vf",
        f"fps={FPS},format=yuv420p",

        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "31",

        "-threads", "1",

        "-pix_fmt", "yuv420p",

        "-c:a", "aac",
        "-b:a", "48k",
        "-ac", "1",

        "-shortest",

        output_path

    ]

    run_command(
        command,
        timeout=180
    )

    if (
        not os.path.isfile(output_path)
        or os.path.getsize(output_path) == 0
    ):

        raise RuntimeError(
            "یکی از صحنه‌های ویدیو ساخته نشد."
        )


# ==========================================
# JOIN VIDEO SEGMENTS
# ==========================================

def join_segments(
    segment_paths,
    output_path,
    work_dir
):

    list_path = os.path.join(
        work_dir,
        "concat_list.txt"
    )

    with open(
        list_path,
        "w",
        encoding="utf-8"
    ) as file_list:

        for segment_path in segment_paths:

            safe_path = segment_path.replace(
                "'",
                "'\\''"
            )

            file_list.write(
                f"file '{safe_path}'\n"
            )

    run_command([

        "ffmpeg",
        "-y",

        "-hide_banner",
        "-loglevel", "error",

        "-threads", "1",

        "-f", "concat",
        "-safe", "0",

        "-i", list_path,

        "-c", "copy",

        "-movflags", "+faststart",

        output_path

    ], timeout=180)

    if (
        not os.path.isfile(output_path)
        or os.path.getsize(output_path) < 500
    ):

        raise RuntimeError(
            "فایل نهایی ویدیو ساخته نشد."
        )


# ==========================================
# USER INTERFACE
# ==========================================

if "ali_video_bytes" not in st.session_state:

    st.session_state.ali_video_bytes = None


script = st.text_area(

    "متن یا سناریوی خود را وارد کنید",

    height=220,

    max_chars=MAX_SCRIPT_CHARS,

    placeholder="داستان خود را اینجا بنویسید..."

)

st.caption(
    f"حداکثر {MAX_SCRIPT_CHARS} حرف و "
    f"{MAX_SCENES} صحنه"
)


# ==========================================
# VIDEO GENERATION
# ==========================================

if st.button(
    "🎬 ساخت ویدیو",
    use_container_width=True,
    type="primary"
):

    st.session_state.ali_video_bytes = None

    if not script.strip():

        st.warning(
            "لطفاً ابتدا سناریو را وارد کنید."
        )

    else:

        work_dir = tempfile.mkdtemp(
            prefix="ali_video_"
        )

        progress = st.progress(0)

        status = st.empty()

        try:

            check_tools()

            scenes = split_scenes(script)

            if not scenes:

                raise RuntimeError(
                    "متنی برای ساخت ویدیو پیدا نشد."
                )

            segment_paths = []

            # Process scenes one by one

            for index, scene in enumerate(scenes):

                status.info(
                    f"در حال ساخت صحنه "
                    f"{index + 1} از {len(scenes)} ..."
                )

                image_path = os.path.join(
                    work_dir,
                    f"scene_{index}.jpg"
                )

                audio_path = os.path.join(
                    work_dir,
                    f"voice_{index}.mp3"
                )

                segment_path = os.path.join(
                    work_dir,
                    f"part_{index}.mp4"
                )

                create_image(
                    scene,
                    image_path
                )

                asyncio.run(
                    create_voice(
                        scene,
                        audio_path
                    )
                )

                make_segment(
                    image_path,
                    audio_path,
                    segment_path
                )

                segment_paths.append(
                    segment_path
                )

                gc.collect()

                progress.progress(
                    (index + 1) / (len(scenes) + 1)
                )

            # Join all scenes

            status.info(
                "در حال یکپارچه‌سازی ویدیو..."
            )

            final_path = os.path.join(
                work_dir,
                "ALI_VIDEO.mp4"
            )

            join_segments(
                segment_paths,
                final_path,
                work_dir
            )

            # Save video in Streamlit memory
            # before deleting temporary files

            with open(final_path, "rb") as video_file:

                st.session_state.ali_video_bytes = (
                    video_file.read()
                )

            progress.progress(1.0)

            status.success(
                "✅ ویدیو آماده شد."
            )

        except Exception as error:

            st.session_state.ali_video_bytes = None

            st.error(
                f"ساخت ویدیو انجام نشد: {error}"
            )

        finally:

            shutil.rmtree(
                work_dir,
                ignore_errors=True
            )

            gc.collect()


# ==========================================
# VIDEO PREVIEW AND DOWNLOAD
# ==========================================

if st.session_state.ali_video_bytes:

    st.subheader(
        "🎥 پیش‌نمایش ویدیو"
    )

    st.video(
        st.session_state.ali_video_bytes,
        format="video/mp4"
    )

    st.download_button(

        label="⬇️ دانلود ویدیو (MP4)",

        data=st.session_state.ali_video_bytes,

        file_name="ALI_VIDEO.mp4",

        mime="video/mp4",

        use_container_width=True,

        key="ali_video_download"

    )
