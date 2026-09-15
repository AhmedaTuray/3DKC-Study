"""
file_scanner.py

Walks a root folder and finds all DICOM files and video files so the
GUI can build a review queue. Handles nested per-patient / per-study
folder structures.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

DICOM_EXTENSIONS = {".dcm", ".dicom", ""}  # DICOM files often have no extension
VIDEO_EXTENSIONS = {".avi", ".mp4", ".mov", ".mkv", ".wmv"}

# Files we never want to treat as cases even if extension-less
SKIP_NAMES = {"dicomdir", ".ds_store", "thumbs.db"}


@dataclass
class MediaFile:
    path: str
    kind: str  # "dicom" or "video"
    label: Optional[str] = None          # current view label, if any
    label_source: Optional[str] = None   # "metadata" | "sidecar" | None
    labeled_copy_path: Optional[str] = None  # burned-in copy, if it exists


def _looks_like_dicom(path: str) -> bool:
    """
    Cheap check: DICOM files (with or without .dcm extension) start with a
    128-byte preamble followed by the 'DICM' magic word at byte 128.
    Falls back to False on any read error.
    """
    try:
        with open(path, "rb") as f:
            preamble = f.read(132)
        return len(preamble) == 132 and preamble[128:132] == b"DICM"
    except OSError:
        return False


def scan_folder(root: str) -> List[MediaFile]:
    """
    Recursively scan `root` for DICOM and video files.
    Returns a list of MediaFile entries, sorted by path for stable ordering.
    """
    results: List[MediaFile] = []

    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            lower = name.lower()
            if lower in SKIP_NAMES or lower.endswith(".json"):
                continue

            full_path = os.path.join(dirpath, name)
            ext = os.path.splitext(name)[1].lower()

            if ext in VIDEO_EXTENSIONS:
                results.append(MediaFile(path=full_path, kind="video"))
            elif ext in DICOM_EXTENSIONS:
                # extension-less files: verify magic bytes before claiming DICOM
                if ext == "" and not _looks_like_dicom(full_path):
                    continue
                results.append(MediaFile(path=full_path, kind="dicom"))

    results.sort(key=lambda m: m.path)
    return results
