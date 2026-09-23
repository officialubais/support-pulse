import os
import shutil
import subprocess
import static_ffmpeg

ARTIFACTS_DIR = "/config/.gemini/antigravity/brain/0eca49ad-1285-4ad3-95c8-e21604a6a68a"
SRC_VIDEO = os.path.join(ARTIFACTS_DIR, "support_pulse_demo.webm")
LOFI_AUDIO = os.path.join(os.path.dirname(__file__), "lofi_background.wav")

OUT_MP4 = os.path.join(ARTIFACTS_DIR, "support_pulse_demo_lofi.mp4")
OUT_WEBM = os.path.join(ARTIFACTS_DIR, "support_pulse_demo_lofi.webm")

def combine_video_audio():
    ffmpeg_exe, _ = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()

    print(f"Combining {SRC_VIDEO} with {LOFI_AUDIO} into MP4...")
    cmd_mp4 = [
        ffmpeg_exe, "-y",
        "-i", SRC_VIDEO,
        "-i", LOFI_AUDIO,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUT_MP4
    ]
    res_mp4 = subprocess.run(cmd_mp4, capture_output=True, text=True)
    if res_mp4.returncode == 0:
        print(f"Successfully created MP4 demo video with music: {OUT_MP4}")
        print(f"MP4 size: {os.path.getsize(OUT_MP4)} bytes")
    else:
        print(f"Error creating MP4: {res_mp4.stderr}")

    print(f"Combining {SRC_VIDEO} with {LOFI_AUDIO} into WEBM...")
    cmd_webm = [
        ffmpeg_exe, "-y",
        "-i", SRC_VIDEO,
        "-i", LOFI_AUDIO,
        "-c:v", "copy",
        "-c:a", "libopus",
        "-b:a", "128k",
        "-shortest",
        OUT_WEBM
    ]
    res_webm = subprocess.run(cmd_webm, capture_output=True, text=True)
    if res_webm.returncode == 0:
        print(f"Successfully created WEBM demo video with music: {OUT_WEBM}")
        print(f"WEBM size: {os.path.getsize(OUT_WEBM)} bytes")
    else:
        print(f"Error creating WEBM: {res_webm.stderr}")

if __name__ == "__main__":
    combine_video_audio()
