"""
video_utils.py

Handles the original (non-DICOM) video files:
  - reading frames for display/scrubbing
  - reading/writing the view label as a JSON sidecar (non-destructive;
    videos don't have a metadata tag system like DICOM does)
  - producing a labeled copy with the text burned into every frame
"""

import json
import os
from typing import List, Optional

import cv2
import numpy as np

from dicom_utils import burn_label_into_frame  # reuse the same text-burn logic


def sidecar_path(path: str) -> str:
    root, _ext = os.path.splitext(path)
    return f"{root}.label.json"


def get_existing_label(path: str) -> Optional[str]:
    sc = sidecar_path(path)
    if os.path.exists(sc):
        with open(sc, "r") as f:
            data = json.load(f)
        return data.get("label")
    return None


def write_label_metadata(path: str, label: str) -> None:
    sc = sidecar_path(path)
    with open(sc, "w") as f:
        json.dump({"label": label, "source_file": os.path.basename(path)}, f, indent=2)


def read_frames(path: str, max_frames: Optional[int] = None) -> List[np.ndarray]:
    """
    Reads frames from a video file as RGB uint8 arrays.
    `max_frames` caps how many frames are pulled (useful for quick preview);
    pass None to read the whole clip.
    """
    cap = cv2.VideoCapture(path)
    frames = []
    try:
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            frames.append(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
            if max_frames is not None and len(frames) >= max_frames:
                break
    finally:
        cap.release()
    return frames


def get_fps(path: str) -> float:
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    cap.release()
    return fps


def save_labeled_copy(path: str, label: str) -> str:
    """
    Destructive save: burns the label into every frame and writes a NEW
    video file next to the original. The original video is untouched.
    """
    frames = read_frames(path)
    if not frames:
        raise ValueError(f"No frames could be read from {path}")

    fps = get_fps(path)
    h, w = frames[0].shape[:2]

    root, ext = os.path.splitext(path)
    ext = ext if ext else ".mp4"
    out_path = f"{root}_labeled{ext}"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    try:
        for frame in frames:
            labeled = burn_label_into_frame(frame, label)
            writer.write(cv2.cvtColor(labeled, cv2.COLOR_RGB2BGR))
    finally:
        writer.release()

    return out_path
