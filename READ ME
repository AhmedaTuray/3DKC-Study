# CEUS View Annotator

A desktop GUI for browsing folders of DICOM files and videos, viewing
each one, and labeling the ultrasound view (e.g. "KIDNEY - LONGITUDINAL
RIGHT") when it's missing.

## What it does

- Recursively scans a folder for DICOM files (with or without `.dcm`
  extension) and video files (`.mp4`, `.avi`, `.mov`, `.mkv`, `.wmv`)
- Displays each one — including multi-frame/cine DICOMs and videos,
  with a frame scrubber
- Shows the current view label (if any) in bold white text
- "Missing View" button reveals a text box — type the view and press
  **Enter** to save
- On save, two things happen automatically:
  1. **Metadata is written** (DICOM `ImageComment` tag, or a
     `<filename>.label.json` sidecar for videos) — the *original* file's
     pixel data is never touched
  2. **A labeled copy is generated** (`<filename>_labeled.dcm` or
     `_labeled.mp4`) with the label burned directly into the image in
     the lower portion of each frame, so it's visible in any viewer

## Setup (first time only)

1. Open this project folder in VS Code
2. Open a terminal in VS Code and switch it to **Git Bash** (bottom-right
   terminal dropdown, or `Ctrl+Shift+P` → "Terminal: Select Default
   Profile" → Git Bash)
3. Create a virtual environment and install dependencies:

   ```bash
   python -m venv venv
   source venv/Scripts/activate   # Git Bash on Windows
   pip install -r requirements.txt
   ```

## Running it

Each time you want to use the tool:

```bash
source venv/Scripts/activate
python main.py
```

This opens the GUI window.

## Using it

1. Click **Open Folder…** and select the root folder containing your
   patient/study subfolders
2. The left panel lists every DICOM and video file found. A `✓`
   marker means it already has a view label; `•` means it doesn't
3. Click a file to view it. If it's a video or multi-frame DICOM
   (typical for CEUS cine loops), use the slider below the image to
   scrub through frames
4. If the view isn't labeled, click **Missing View**, type the view
   (e.g. `KIDNEY - LONGITUDINAL RIGHT`), and press **Enter**
5. The label is saved to metadata, a labeled copy is generated next to
   the original, and the file list updates to show the `✓`

## File layout

```
ceus_annotator/
├── main.py            # entry point — run this
├── main_window.py      # the GUI itself
├── file_scanner.py     # finds DICOM/video files in a folder tree
├── dicom_utils.py       # DICOM read/write + text burn-in
├── video_utils.py       # video read/write + text burn-in
├── requirements.txt
└── README.md
```

## Design notes / things to decide as you use it

- **Labels never overwrite the original pixel data.** The original
  DICOM/video stays byte-for-byte visually unchanged except for the
  metadata tag. The visibly-labeled version is always a separate
  `_labeled` file.
- **DICOM label storage** uses the `ImageComment (0020,4000)` tag. If
  your PACS or downstream tools expect the label somewhere else (e.g.
  a private tag, `SeriesDescription`, or a specific standard tag),
  that's a one-line change in `dicom_utils.LABEL_TAG`.
- **Re-labeling**: clicking Missing View on an already-labeled file
  and submitting a new value overwrites the previous label (metadata)
  and regenerates the `_labeled` copy. There's currently no label
  history — say the word if you want old labels kept instead of
  replaced.
- **Multi-frame burn-in** stamps the label onto *every* frame of a
  cine loop. If you only want it on the first frame or a corner
  overlay instead of the lower band, that's a small tweak in
  `burn_label_into_frame`.
