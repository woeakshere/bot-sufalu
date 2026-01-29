import ffmpeg
import os
import logging

# Configure logger specifically for the muxer
logger = logging.getLogger(__name__)

def mux_subtitles(video_path, subtitle_path, output_path):
    """
    Muxes a subtitle file into a video container without re-encoding video/audio.
    
    Args:
        video_path (str): Path to the input video file.
        subtitle_path (str): Path to the input subtitle file (.srt, .vtt, .ass).
        output_path (str): Path where the final video will be saved.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # 1. Validation
        if not os.path.exists(video_path):
            logger.error(f"Muxer Error: Video file not found: {video_path}")
            return False
        if not os.path.exists(subtitle_path):
            logger.error(f"Muxer Error: Subtitle file not found: {subtitle_path}")
            return False

        # 2. Determine Subtitle Codec
        # MP4 containers have strict subtitle format support (mov_text).
        # MKV containers are flexible and can accept almost anything (srt, ass, ssa).
        if output_path.lower().endswith(".mp4"):
            subtitle_codec = "mov_text"
        else:
            # For MKV/WebM, 'copy' usually works for SRT/ASS, or explicit 'srt'
            subtitle_codec = "srt"

        logger.info(f"Starting mux: {os.path.basename(video_path)} + {os.path.basename(subtitle_path)}")

        # 3. Build FFmpeg Stream
        input_video = ffmpeg.input(video_path)
        input_sub = ffmpeg.input(subtitle_path)

        (
            ffmpeg
            .output(
                input_video, 
                input_sub, 
                output_path, 
                vcodec='copy',   # Video: Direct Stream Copy (No CPU usage)
                acodec='copy',   # Audio: Direct Stream Copy
                scodec=subtitle_codec, # Subtitles: Determined above
                **{'metadata:s:s:0': 'language=eng'} # Optional: Set language tag to English
            )
            .global_args('-hide_banner', '-loglevel', 'error') # Keep logs clean
            .overwrite_output() # Overwrite if output file exists
            .run(capture_stdout=True, capture_stderr=True) # Run logic
        )
        
        logger.info(f"Muxing success: {output_path}")
        return True

    except ffmpeg.Error as e:
        # FFmpeg specific errors (e.g., corrupt file)
        error_message = e.stderr.decode('utf-8') if e.stderr else str(e)
        logger.error(f"FFmpeg failed: {error_message}")
        return False
        
    except Exception as e:
        # General Python errors (e.g., permission denied)
        logger.error(f"General Muxing Error: {str(e)}")
        return False

# --- Testing Block (Optional, for local debugging) ---
if __name__ == "__main__":
    # You can run 'python processor/muxer.py' to test this manually
    test_video = "test.mp4"
    test_sub = "test.srt"
    if os.path.exists(test_video) and os.path.exists(test_sub):
        mux_subtitles(test_video, test_sub, "output_test.mp4")