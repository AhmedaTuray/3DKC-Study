"""
main_window.py

The GUI itself. Layout:

  +------------------+-------------------------------------------+
  | File list         |              Image / video viewer          |
  | (left panel)       |                                             |
  |                    |  [ <  frame slider  > ]  (video/cine only)  |
  |                    +---------------------------------------------+
  |                    | Current label:  KIDNEY - LONGITUDINAL RIGHT |
  |                    | [ Missing View ]  [_____________] (Enter)   |
  +--------------------+---------------------------------------------+

Workflow:
  1. Open Folder -> scans for DICOM + video files
  2. Click a file in the list -> loads and displays it
  3. If the view is unlabeled, click "Missing View", type the label,
     press Enter
  4. That writes the label to metadata (DICOM tag or JSON sidecar) AND
     saves a labeled copy with the text burned into the image, then
     refreshes the display and the file list.
"""

import os

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import dicom_utils
import video_utils
from file_scanner import MediaFile, scan_folder


def np_frame_to_qpixmap(frame: np.ndarray) -> QPixmap:
    if frame.ndim == 2:
        frame = np.stack([frame] * 3, axis=-1)
    h, w, _ = frame.shape
    frame = np.ascontiguousarray(frame)
    qimg = QImage(frame.data, w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CEUS View Annotator")
        self.resize(1200, 800)

        self.media_files: list[MediaFile] = []
        self.current_index: int = -1
        self.current_frames: list[np.ndarray] = []  # raw (unlabeled) frames of the selection

        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)

        # --- left panel: file list ---
        left_panel = QVBoxLayout()
        self.open_folder_btn = QPushButton("Open Folder…")
        self.open_folder_btn.clicked.connect(self.open_folder)
        left_panel.addWidget(self.open_folder_btn)

        self.file_list = QListWidget()
        self.file_list.currentRowChanged.connect(self.on_file_selected)
        left_panel.addWidget(self.file_list)

        left_container = QWidget()
        left_container.setLayout(left_panel)
        left_container.setFixedWidth(320)
        root_layout.addWidget(left_container)

        # --- right panel: viewer + controls ---
        right_panel = QVBoxLayout()

        self.image_label = QLabel("Open a folder to begin")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black; color: gray;")
        self.image_label.setMinimumSize(640, 480)
        right_panel.addWidget(self.image_label, stretch=1)

        # frame scrubber (for multi-frame DICOM / video)
        self.frame_slider = QSlider(Qt.Horizontal)
        self.frame_slider.setEnabled(False)
        self.frame_slider.valueChanged.connect(self.on_frame_slider_changed)
        right_panel.addWidget(self.frame_slider)

        # current label readout
        self.label_display = QLabel("No file loaded")
        self.label_display.setAlignment(Qt.AlignCenter)
        self.label_display.setStyleSheet(
            "color: white; background-color: #111; font-weight: bold; font-size: 16px; padding: 8px;"
        )
        right_panel.addWidget(self.label_display)

        # missing-view controls
        controls_row = QHBoxLayout()
        self.missing_view_btn = QPushButton("Missing View")
        self.missing_view_btn.clicked.connect(self.show_label_input)
        self.missing_view_btn.setEnabled(False)
        controls_row.addWidget(self.missing_view_btn)

        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("Type view, e.g. 'KIDNEY - LONGITUDINAL RIGHT', then press Enter")
        self.label_input.setVisible(False)
        self.label_input.returnPressed.connect(self.submit_label)
        controls_row.addWidget(self.label_input, stretch=1)
        right_panel.addLayout(controls_row)

        # prev/next navigation
        nav_row = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.clicked.connect(self.go_previous)
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.go_next)
        nav_row.addWidget(self.prev_btn)
        nav_row.addWidget(self.next_btn)
        right_panel.addLayout(nav_row)

        right_container = QWidget()
        right_container.setLayout(right_panel)
        root_layout.addWidget(right_container, stretch=1)

    # ------------------------------------------------------------- actions

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder containing DICOMs / videos")
        if not folder:
            return
        self.media_files = scan_folder(folder)
        self._refresh_metadata()
        self.file_list.clear()
        for mf in self.media_files:
            self.file_list.addItem(self._list_item_text(mf))
        if self.media_files:
            self.file_list.setCurrentRow(0)

    def _refresh_metadata(self):
        for mf in self.media_files:
            if mf.kind == "dicom":
                try:
                    ds = dicom_utils.load_dicom(mf.path)
                    mf.label = dicom_utils.get_existing_label(ds)
                except Exception:
                    mf.label = None
            else:
                mf.label = video_utils.get_existing_label(mf.path)

    def _list_item_text(self, mf: MediaFile) -> str:
        tag = "✓" if mf.label else "•"
        name = os.path.basename(mf.path)
        return f"{tag} [{mf.kind}] {name}"

    def on_file_selected(self, row: int):
        if row < 0 or row >= len(self.media_files):
            return
        self.current_index = row
        mf = self.media_files[row]

        try:
            if mf.kind == "dicom":
                ds = dicom_utils.load_dicom(mf.path)
                self.current_frames = dicom_utils.get_frames_as_uint8(ds)
            else:
                self.current_frames = video_utils.read_frames(mf.path)
        except Exception as exc:
            QMessageBox.warning(self, "Failed to load file", f"{mf.path}\n\n{exc}")
            self.current_frames = []

        n_frames = len(self.current_frames)
        self.frame_slider.setEnabled(n_frames > 1)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(max(0, n_frames - 1))
        self.frame_slider.setValue(0)

        self._render_frame(0)
        self._update_label_display(mf)
        self.missing_view_btn.setEnabled(True)
        self.label_input.setVisible(False)

    def on_frame_slider_changed(self, value: int):
        self._render_frame(value)

    def _render_frame(self, index: int):
        if not self.current_frames:
            self.image_label.setText("Could not load preview")
            return
        index = max(0, min(index, len(self.current_frames) - 1))
        pixmap = np_frame_to_qpixmap(self.current_frames[index])
        scaled = pixmap.scaled(
            self.image_label.width(), self.image_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

    def _update_label_display(self, mf: MediaFile):
        if mf.label:
            self.label_display.setText(mf.label)
        else:
            self.label_display.setText("(unlabeled)")

    def show_label_input(self):
        self.label_input.setVisible(True)
        self.label_input.setFocus()

    def submit_label(self):
        if self.current_index < 0:
            return
        mf = self.media_files[self.current_index]
        label = self.label_input.text().strip()
        if not label:
            return

        try:
            if mf.kind == "dicom":
                dicom_utils.write_label_metadata(mf.path, label)
                labeled_path = dicom_utils.save_labeled_copy(mf.path, label)
            else:
                video_utils.write_label_metadata(mf.path, label)
                labeled_path = video_utils.save_labeled_copy(mf.path, label)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", f"Could not save label:\n\n{exc}")
            return

        mf.label = label
        mf.labeled_copy_path = labeled_path

        self.label_input.clear()
        self.label_input.setVisible(False)
        self._update_label_display(mf)
        self.file_list.item(self.current_index).setText(self._list_item_text(mf))

        QMessageBox.information(
            self, "Saved", f"Label saved.\n\nMetadata updated in place:\n{mf.path}\n\nLabeled copy:\n{labeled_path}"
        )

    def go_previous(self):
        if self.current_index > 0:
            self.file_list.setCurrentRow(self.current_index - 1)

    def go_next(self):
        if self.current_index < len(self.media_files) - 1:
            self.file_list.setCurrentRow(self.current_index + 1)


def run():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
