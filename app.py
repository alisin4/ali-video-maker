import streamlit as st
import os, tempfile, subprocess, textwrap, shutil
from pathlib import Path

st.set_page_config(page_title="ALI VIDEO MAKER", page_icon="🎬", layout="centered")
st.title("🎬 ALI VIDEO MAKER")
st.caption("Turn a script into a narrated cinematic video (free-resource workflow)")

st.info("This starter creates a narrated slideshow video from your script using scene cards, TTS and FFmpeg. AI image generation APIs are not included; add a provider later if desired.")

script = st.text_area("Your scenario", height=220, placeholder="Paste your complete scenario here...")
voice = st.selectbox("Narration language", ["Persian/Dari", "English"])
format_choice = st.selectbox("Video format", ["Vertical 9:16 (Reels/Shorts)", "Landscape 16:9"])
title = st.text_input("Video title", "My video")
make = st.button("🎬 Create MP4", type="primary")

def split_scenes(txt):
    chunks=[x.strip() for x in txt.replace("\r","").split("\n\n") if x.strip()]
    if len(chunks)<=1:
        sentences=[x.strip() for x in txt.replace("؟","?").split(".") if x.strip()]
        chunks=sentences or [txt.strip()]
    return chunks[:12]

if make:
    if not script.strip():
        st.warning("Please enter your scenario.")
    else:
        ffmpeg=shutil.which("ffmpeg")
        if not ffmpeg:
            st.error("FFmpeg is not installed in this environment. Add it through packages.txt and redeploy.")
        else:
            try:
                from gtts import gTTS
                from PIL import Image, ImageDraw, ImageFont
                scenes=split_scenes(script)
                work=Path(tempfile.mkdtemp())
                files=[]
                size=(1080,1920) if format_choice.startswith("Vertical") else (1920,1080)
                # Find a suitable font, fallback to default.
                font_path=None
                for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                          "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]:
                    if os.path.exists(p): font_path=p; break
                font=ImageFont.truetype(font_path, 54) if font_path else ImageFont.load_default()
                for i,scene in enumerate(scenes):
                    img=Image.new("RGB",size,(20,24,38))
                    draw=ImageDraw.Draw(img)
                    # subtle decorative bars
                    draw.rectangle((0,0,size[0],22),fill=(220,170,70))
                    draw.rectangle((0,size[1]-22,size[0],size[1]),fill=(220,170,70))
                    margin=int(size[0]*.09)
                    wrapped=textwrap.fill(scene,width=28 if size[0]<1500 else 48)
                    bbox=draw.multiline_textbbox((0,0),wrapped,font=font,spacing=24,align="center")
                    h=bbox[3]-bbox[1]
                    y=(size[1]-h)//2
                    draw.text((size[0]//2,y),wrapped,font=font,fill=(255,255,255),spacing=24,align="center",anchor="mm")
                    draw.text((margin,margin),f"{i+1:02d}",font=font,fill=(220,170,70))
                    image_path=work/f"scene_{i:03d}.png"
                    img.save(image_path)
                    audio_path=work/f"scene_{i:03d}.mp3"
                    lang="fa" if voice=="Persian/Dari" else "en"
                    gTTS(scene,lang=lang).save(str(audio_path))
                    # render a video segment with still image and voice
                    segment=work/f"segment_{i:03d}.mp4"
                    cmd=[ffmpeg,"-y","-loop","1","-i",str(image_path),"-i",str(audio_path),
                         "-c:v","libx264","-tune","stillimage","-c:a","aac","-b:a","128k",
                         "-pix_fmt","yuv420p","-shortest","-vf",f"scale={size[0]}:{size[1]}",
                         "-r","25",str(segment)]
                    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                    files.append(segment)
                listfile=work/"concat.txt"
                listfile.write_text("\n".join(f"file '{f.as_posix()}'" for f in files),encoding="utf-8")
                output=work/"ali_video.mp4"
                subprocess.run([ffmpeg,"-y","-f","concat","-safe","0","-i",str(listfile),
                               "-c","copy",str(output)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                st.success("Video created!")
                st.video(str(output))
                st.download_button("⬇️ Download MP4",output.read_bytes(),file_name="ali_video.mp4",mime="video/mp4")
            except Exception as e:
                st.error(f"Video creation failed: {e}")
                st.caption("Check the deployment logs if this continues.")
