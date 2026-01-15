"""FFmpeg utilities for video processing."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass

from app.core.exceptions import FFmpegError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VideoInfo:
    """Video metadata."""

    duration_sec: float
    fps: float
    width: int
    height: int
    resolution: str
    has_audio: bool
    codec: str
    file_size_bytes: int


def probe_video(video_path: str) -> VideoInfo:
    """
    Probe video file to get metadata.

    Args:
        video_path: Path to video file

    Returns:
        VideoInfo with metadata

    Raises:
        FFmpegError: If probing fails
    """
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            video_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            raise FFmpegError(f"ffprobe failed: {result.stderr}")

        data = json.loads(result.stdout)

        # Find video stream
        video_stream = None
        has_audio = False
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio":
                has_audio = True

        if not video_stream:
            raise FFmpegError("No video stream found")

        # Extract metadata
        format_info = data.get("format", {})

        duration = float(format_info.get("duration", 0))
        if duration == 0 and video_stream.get("duration"):
            duration = float(video_stream["duration"])

        # Parse FPS from r_frame_rate (e.g., "30/1" or "30000/1001")
        fps_str = video_stream.get("r_frame_rate", "30/1")
        try:
            num, den = map(int, fps_str.split("/"))
            fps = num / den if den > 0 else 30.0
        except (ValueError, ZeroDivisionError):
            fps = 30.0

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))

        file_size = int(format_info.get("size", 0))
        if file_size == 0:
            file_size = os.path.getsize(video_path)

        return VideoInfo(
            duration_sec=duration,
            fps=fps,
            width=width,
            height=height,
            resolution=f"{width}x{height}",
            has_audio=has_audio,
            codec=video_stream.get("codec_name", "unknown"),
            file_size_bytes=file_size,
        )

    except subprocess.TimeoutExpired:
        raise FFmpegError("ffprobe timed out")
    except json.JSONDecodeError as e:
        raise FFmpegError(f"Failed to parse ffprobe output: {e}")
    except Exception as e:
        if isinstance(e, FFmpegError):
            raise
        raise FFmpegError(f"Failed to probe video: {e}")


def extract_audio(
    video_path: str, output_path: str, sample_rate: int = 16000, channels: int = 1
) -> str:
    """
    Extract audio from video file.

    Args:
        video_path: Path to video file
        output_path: Path for output audio file
        sample_rate: Audio sample rate (default: 16000 for Whisper)
        channels: Number of audio channels (default: 1 for mono)

    Returns:
        Path to extracted audio file

    Raises:
        FFmpegError: If extraction fails
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i",
            video_path,
            "-vn",  # No video
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            output_path,
        ]

        logger.info(f"Extracting audio from {video_path}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )

        if result.returncode != 0:
            raise FFmpegError(f"ffmpeg audio extraction failed: {result.stderr}")

        if not os.path.exists(output_path):
            raise FFmpegError("Audio file was not created")

        logger.info(f"Audio extracted to {output_path}")
        return output_path

    except subprocess.TimeoutExpired:
        raise FFmpegError("Audio extraction timed out")
    except Exception as e:
        if isinstance(e, FFmpegError):
            raise
        raise FFmpegError(f"Failed to extract audio: {e}")


def extract_frame(
    video_path: str, output_path: str, time_sec: float, width: int | None = 1280, quality: int = 2
) -> str:
    """
    Extract a single frame from video.

    Args:
        video_path: Path to video file
        output_path: Path for output image file
        time_sec: Time in seconds to extract frame
        width: Target width (height auto-scaled), None to keep original
        quality: JPEG/PNG quality (1-31, lower is better for ffmpeg)

    Returns:
        Path to extracted frame

    Raises:
        FFmpegError: If extraction fails
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(time_sec),
            "-i",
            video_path,
            "-vframes",
            "1",
        ]

        # Add scaling if width specified
        if width:
            cmd.extend(["-vf", f"scale={width}:-1"])

        cmd.extend(["-q:v", str(quality), output_path])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            raise FFmpegError(f"ffmpeg frame extraction failed: {result.stderr}")

        if not os.path.exists(output_path):
            raise FFmpegError(f"Frame file was not created at {output_path}")

        return output_path

    except subprocess.TimeoutExpired:
        raise FFmpegError("Frame extraction timed out")
    except Exception as e:
        if isinstance(e, FFmpegError):
            raise
        raise FFmpegError(f"Failed to extract frame: {e}")


def extract_frames_batch(
    video_path: str,
    output_dir: str,
    times_sec: list[float],
    width: int | None = 1280,
    filename_prefix: str = "frame",
) -> list[str]:
    """
    Extract multiple frames from video.

    Args:
        video_path: Path to video file
        output_dir: Output directory for frames
        times_sec: List of times in seconds
        width: Target width
        filename_prefix: Prefix for output filenames

    Returns:
        List of paths to extracted frames
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = []

    for i, time_sec in enumerate(times_sec):
        output_path = os.path.join(output_dir, f"{filename_prefix}_{i + 1:03d}.png")
        extract_frame(video_path, output_path, time_sec, width)
        paths.append(output_path)

    return paths
