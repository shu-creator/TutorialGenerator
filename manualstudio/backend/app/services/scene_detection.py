"""Scene detection service for finding key frames."""
import os
from dataclasses import dataclass
from typing import Optional

from app.core.logging import get_logger
from app.utils.timecode import seconds_to_mmss

logger = get_logger(__name__)


@dataclass
class CandidateFrame:
    """A candidate frame for step extraction."""
    time_sec: float
    time_mmss: str
    filename: str
    scene_index: int


def detect_scenes_pyscenedetect(
    video_path: str,
    threshold: float = 27.0,
    min_scene_len: float = 2.0
) -> list[float]:
    """
    Detect scene changes using PySceneDetect.

    Args:
        video_path: Path to video file
        threshold: Content detector threshold (lower = more sensitive)
        min_scene_len: Minimum scene length in seconds

    Returns:
        List of scene start times in seconds
    """
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector

        logger.info(f"Detecting scenes with PySceneDetect: {video_path}")

        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(threshold=threshold, min_scene_len=int(min_scene_len * video.frame_rate))
        )

        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        # Get the start time of each scene
        scene_times = []
        for scene in scene_list:
            start_frame = scene[0]
            start_sec = start_frame.get_seconds()
            scene_times.append(start_sec)

        # Always include 0 as the first scene
        if not scene_times or scene_times[0] > 1.0:
            scene_times.insert(0, 0.0)

        logger.info(f"Detected {len(scene_times)} scenes")
        return scene_times

    except ImportError:
        logger.warning("PySceneDetect not available, falling back to interval sampling")
        return []
    except Exception as e:
        logger.warning(f"Scene detection failed: {e}, falling back to interval sampling")
        return []


def sample_frames_interval(
    duration_sec: float,
    interval_sec: float = 2.0,
    max_frames: int = 100
) -> list[float]:
    """
    Generate frame times at regular intervals.

    Args:
        duration_sec: Video duration in seconds
        interval_sec: Sampling interval
        max_frames: Maximum number of frames

    Returns:
        List of frame times in seconds
    """
    times = []
    t = 0.0
    while t < duration_sec and len(times) < max_frames:
        times.append(t)
        t += interval_sec

    return times


def get_candidate_frames(
    video_path: str,
    duration_sec: float,
    output_dir: str,
    use_scene_detection: bool = True,
    fallback_interval: float = 3.0,
    max_frames: int = 50
) -> list[CandidateFrame]:
    """
    Get candidate frames for step extraction.

    Args:
        video_path: Path to video file
        duration_sec: Video duration in seconds
        output_dir: Directory for frame images
        use_scene_detection: Whether to try PySceneDetect first
        fallback_interval: Interval for fallback sampling
        max_frames: Maximum number of frames

    Returns:
        List of candidate frames
    """
    scene_times = []

    # Try scene detection first
    if use_scene_detection:
        scene_times = detect_scenes_pyscenedetect(video_path)

    # Fallback to interval sampling if scene detection failed or returned too few
    if len(scene_times) < 3:
        logger.info("Using interval sampling for frame candidates")
        scene_times = sample_frames_interval(
            duration_sec,
            interval_sec=fallback_interval,
            max_frames=max_frames
        )

    # Limit to max frames
    if len(scene_times) > max_frames:
        # Sample evenly
        step = len(scene_times) / max_frames
        scene_times = [scene_times[int(i * step)] for i in range(max_frames)]

    # Create candidate frame objects
    candidates = []
    for i, time_sec in enumerate(scene_times):
        filename = f"candidate_{i+1:03d}.png"
        candidates.append(CandidateFrame(
            time_sec=time_sec,
            time_mmss=seconds_to_mmss(time_sec),
            filename=filename,
            scene_index=i + 1
        ))

    logger.info(f"Generated {len(candidates)} candidate frames")
    return candidates


def filter_similar_frames(
    frame_paths: list[str],
    threshold: float = 0.9
) -> list[int]:
    """
    Filter out similar consecutive frames using perceptual hashing.

    Args:
        frame_paths: List of frame image paths
        threshold: Similarity threshold (higher = more similar allowed)

    Returns:
        List of indices to keep
    """
    try:
        import imagehash
        from PIL import Image

        if not frame_paths:
            return []

        keep_indices = [0]  # Always keep first frame
        prev_hash = imagehash.phash(Image.open(frame_paths[0]))

        for i, path in enumerate(frame_paths[1:], 1):
            curr_hash = imagehash.phash(Image.open(path))

            # Calculate normalized difference (0 = identical, 1 = completely different)
            diff = (curr_hash - prev_hash) / 64.0

            if diff > (1 - threshold):
                keep_indices.append(i)
                prev_hash = curr_hash

        logger.info(f"Kept {len(keep_indices)}/{len(frame_paths)} frames after filtering")
        return keep_indices

    except ImportError:
        logger.warning("imagehash not available, keeping all frames")
        return list(range(len(frame_paths)))
    except Exception as e:
        logger.warning(f"Frame filtering failed: {e}, keeping all frames")
        return list(range(len(frame_paths)))
