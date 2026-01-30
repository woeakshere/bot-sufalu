# processor/muxer.py
import ffmpeg
import os
import logging
import asyncio

# Configure logger specifically for the muxer
logger = logging.getLogger(__name__)

def _mux_subtitles_sync(video_path, subtitle_path, output_path):
    """
    Synchronous mux function (blocking), wrapped by asyncio for async usage.
    """
    try:
        # Validation
        if not os.path.exists(video_path):
            return False, f"Video file not found: {video_path}"
        if not os.path.exists(subtitle_path):
            return False, f"Subtitle file not found: {subtitle_path}"

        # Determine subtitle codec
        ext = os.path.splitext(subtitle_path)[1].lower()
        if output_path.lower().endswith(".mp4"):
            subtitle_codec = "mov_text"
        elif ext in [".srt", ".vtt", ".ass"]:
            subtitle_codec = ext[1:]
        else:
            subtitle_codec = "srt"

        logger.info(f"Starting mux: {os.path.basename(video_path)} + {os.path.basename(subtitle_path)}")

        # Build FFmpeg command
        input_video = ffmpeg.input(video_path)
        input_sub = ffmpeg.input(subtitle_path)

        (
            ffmpeg
            .output(
                input_video,
                input_sub,
                output_path,
                vcodec='copy',
                acodec='copy',
                scodec=subtitle_codec,
                **{'metadata:s:s:0': 'language=eng'}
            )
            .global_args('-hide_banner', '-loglevel', 'error')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        logger.info(f"Muxing success: {output_path}")
        return True, None

    except ffmpeg.Error as e:
        error_message = e.stderr.decode('utf-8') if e.stderr else str(e)
        logger.error(f"FFmpeg failed: {error_message}")
        return False, error_message
    except Exception as e:
        logger.error(f"General Muxing Error: {str(e)}")
        return False, str(e)


async def mux_subtitles(video_path, subtitle_path, output_path):
    """
    Async wrapper for muxing subtitles into a video.
    This prevents blocking the bot's main event loop.
    """
    return await asyncio.to_thread(_mux_subtitles_sync, video_path, subtitle_path, output_path)


# --- Testing Block (Optional) ---
if __name__ == "__main__":
    import sys

    video = sys.argv[1] if len(sys.argv) > 1 else "test.mp4"
    sub = sys.argv[2] if len(sys.argv) > 2 else "test.srt"
    out = sys.argv[3] if len(sys.argv) > 3 else "output_test.mp4"

    async def test():
        success, err = await mux_subtitles(video, sub, out)
        if success:
            print(f"✅ Mux successful: {out}")
        else:
            print(f"❌ Mux failed: {err}")

    asyncio.run(test())
