"""
dicom_utils.py

Handles everything DICOM-specific:
  - loading pixel data (single-frame and multi-frame/cine, common for
    CEUS ultrasound loops)
  - reading/writing the view label as DICOM metadata (non-destructive)
  - producing a labeled copy with the text burned into the pixels
    (destructive, saved as a separate file so the original is untouched)

Label metadata is stored in ImageComment (0020,4000), a free-text tag
that's safe to reuse for this purpose. If a value is already present,
it's overwritten only when the user explicitly re-labels the file.
"""

import os
from typing import List, Optional

import numpy as np
import pydicom
from pydicom.dataset import FileDataset
from PIL import Image, ImageDraw, ImageFont

LABEL_TAG = (0x0020, 0x4000)  # ImageComment


def load_dicom(path: str) -> FileDataset:
    return pydicom.dcmread(path, force=True)


def get_existing_label(ds: FileDataset) -> Optional[str]:
    if LABEL_TAG in ds:
        value = str(ds[LABEL_TAG].value).strip()
        return value or None
    return None


def get_frames_as_uint8(ds: FileDataset) -> List[np.ndarray]:
    """
    Returns a list of frames as uint8 grayscale-or-RGB numpy arrays,
    regardless of whether the DICOM is single-frame or multi-frame (cine).
    """
    arr = ds.pixel_array

    # Normalize to a list of 2D/3D frames
    if arr.ndim == 2:
        frames = [arr]
    elif arr.ndim == 3:
        # Could be (frames, rows, cols) grayscale OR (rows, cols, 3) single RGB
        if getattr(ds, "SamplesPerPixel", 1) == 3 and arr.shape[-1] == 3:
            frames = [arr]
        else:
            frames = [arr[i] for i in range(arr.shape[0])]
    elif arr.ndim == 4:
        # (frames, rows, cols, 3) - multi-frame RGB (typical for CEUS cine loops)
        frames = [arr[i] for i in range(arr.shape[0])]
    else:
        raise ValueError(f"Unsupported pixel array shape: {arr.shape}")

    out = []
    for f in frames:
        f = f.astype(np.float32)
        f -= f.min()
        max_val = f.max()
        if max_val > 0:
            f = f / max_val * 255.0
        out.append(f.astype(np.uint8))
    return out


def write_label_metadata(path: str, label: str) -> None:
    """
    Non-destructive save: writes the label into the DICOM's metadata
    and overwrites the file in place. Pixel data is untouched.
    """
    ds = load_dicom(path)
    ds.add_new(LABEL_TAG, "LT", label)
    ds.save_as(path)


def _get_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def burn_label_into_frame(frame: np.ndarray, label: str) -> np.ndarray:
    """
    Draws `label` in bold white text into the lower portion of the frame
    (typically the unused dark space below the ultrasound sector on a
    CEUS image). Returns a new array; does not mutate the input.
    """
    mode = "RGB" if frame.ndim == 3 else "L"
    img = Image.fromarray(frame, mode=mode)
    if mode == "L":
        img = img.convert("RGB")

    draw = ImageDraw.Draw(img)
    w, h = img.size
    font_size = max(14, h // 20)
    font = _get_font(font_size)

    text_bbox = draw.textbbox((0, 0), label, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    x = max(8, (w - text_w) // 2)
    y = h - font_size - 12  # lower band of the image

    # subtle dark backing so white text stays legible over any content
    pad = 4
    draw.rectangle(
        [x - pad, y - pad, x + text_w + pad, y + font_size + pad],
        fill=(0, 0, 0),
    )
    draw.text((x, y), label, fill=(255, 255, 255), font=font)

    return np.array(img)


def save_labeled_copy(path: str, label: str) -> str:
    """
    Destructive save: burns the label into every frame's pixels and
    writes the result as a NEW file next to the original, so the
    original DICOM is never modified.

    Returns the path to the labeled copy.
    """
    ds = load_dicom(path)
    frames = get_frames_as_uint8(ds)
    labeled_frames = [burn_label_into_frame(f, label) for f in frames]

    stacked = np.stack(labeled_frames, axis=0) if len(labeled_frames) > 1 else labeled_frames[0]

    out_ds = ds.copy()
    out_ds.PhotometricInterpretation = "RGB"
    out_ds.SamplesPerPixel = 3
    out_ds.BitsAllocated = 8
    out_ds.BitsStored = 8
    out_ds.HighBit = 7
    out_ds.PixelRepresentation = 0
    out_ds.PlanarConfiguration = 0
    if len(labeled_frames) > 1:
        out_ds.NumberOfFrames = len(labeled_frames)
    out_ds.PixelData = stacked.tobytes()
    out_ds.add_new(LABEL_TAG, "LT", label)

    root, ext = os.path.splitext(path)
    ext = ext if ext else ".dcm"
    out_path = f"{root}_labeled{ext}"
    out_ds.save_as(out_path)
    return out_path
