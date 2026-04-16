
#####################################################################################
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

#   © 2024 Emmanuel Gyimah Annor. All rights reserved.
#####################################################################################

import os
import sys

from modules.config import download_folder, current_theme, lang
from modules.settings_manager import SettingsManager

from PySide6.QtCore import Qt, QCoreApplication, QTranslator
from PySide6.QtWidgets import (QDialog, QLabel, QLineEdit, QComboBox, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QProgressBar, QSizePolicy, QWidget, QSpacerItem, QFormLayout, QFileDialog, QMessageBox, QApplication,
)

from ui.styles import get_stylesheet


# default categories to show when no persisted categories exist
DEFAULT_CATEGORIES = [
    {"name": "General", "types": "", "path": ""},
    {"name": "Compressed", "types": "zip,rar,7z", "path": ""},
    {"name": "Video", "types": "mp4,mkv,avi,webm", "path": ""},
    {"name": "Music", "types": "mp3,flac,aac,opus", "path": ""},
    {"name": "Documents", "types": "pdf,doc,docx,xls,xlsx", "path": ""},
    {"name": "Programs", "types": "exe,msi,deb,rpm,apk", "path": ""},
]
from PySide6.QtGui import QPixmap


class AddDownloadWindow(QWidget):
    def __init__(self, main_window):
        super().__init__(None)   

        self.setWindowTitle("AddDownload")
        self.setMinimumWidth(760)
        self.setMaximumHeight(450)

        self.setObjectName("AddDownloadWindow")
        

        
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        # Normal window, not modal
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self.main_window = main_window


        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)


        self.settings_manager = SettingsManager()
        self.translator = QTranslator()
        self.categories = self.settings_manager.load_categories()

        # ==============================
        # Top grid (URL + right info)
        # ==============================
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)   
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 0)

        label_style = lambda t: QLabel(t, self)

        # --- URL row ---
        self.lbl_url = label_style(self.tr("URL:"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com/file")

        grid.addWidget(self.lbl_url, 0, 0)
        grid.addWidget(self.url_edit, 0, 1, 1, 2)
        

        # Divider
        divider1 = QFrame()
        divider1.setFrameShape(QFrame.HLine)
        divider1.setFrameShadow(QFrame.Sunken)

        # ==============================
        # Save / Category / Filename
        # ==============================
        self.lbl_save = label_style(self.tr("Save to:"))
        self.save_to_edit = QLineEdit()

        self.lbl_cat = label_style(self.tr("Category:"))
        self.category_combo = QComboBox()
        # build merged category list: defaults first, then persisted extras
        self._category_map = {}
        self.category_combo.clear()

        seen = set()

        # Add defaults first (locked names)
        for c in DEFAULT_CATEGORIES:
            name = c["name"].strip()
            key = self._norm(name)

            seen.add(key)
            self.category_combo.addItem(name)

            self._category_map[name] = {
                "types": c.get("types", ""),
                "path": c.get("path", "")
            }

        # Merge persisted categories
        for c in self.categories:
            name = c.get("name", "").strip()
            if not name:
                continue

            key = self._norm(name)

            if key in seen:
                # override default metadata ONLY (not name)
                existing_name = next(
                    k for k in self._category_map.keys()
                    if self._norm(k) == key
                )
                self._category_map[existing_name].update({
                    "types": c.get("types", ""),
                    "path": c.get("path", "")
                })
            else:
                self.category_combo.addItem(name)
                self._category_map[name] = {
                    "types": c.get("types", ""),
                    "path": c.get("path", "")
                }
                seen.add(key)


        self.category_combo.setFixedWidth(190)
        # when category changes, update save_to_edit path if category has an associated path
        self.category_combo.currentTextChanged.connect(self._on_category_changed)

        self.lbl_file = label_style(self.tr("File name:"))
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("Optional file name (leave empty to auto-detect)")


        grid.addWidget(self.lbl_save, 1, 0)
        grid.addWidget(self.save_to_edit, 1, 1, 1, 2)

        
        # --- Category row with + button ---
        cat_row = QHBoxLayout()
        cat_row.setSpacing(4)  # tighter spacing

        cat_row.addWidget(self.category_combo)

        self.btn_add_category = QPushButton("+")
        self.btn_add_category.setFixedSize(22, 28)
        self.btn_add_category.setToolTip("Add new category")
        self.btn_add_category.setObjectName("AddCategoryButton")
        self.btn_add_category.setStyleSheet("""
        QPushButton {
            padding: 6px 10px;
        }
        """)
        
        cat_row.addWidget(self.btn_add_category)
        cat_row.addStretch()

        grid.addWidget(self.lbl_cat, 2, 0)
        grid.addLayout(cat_row, 2, 1)


        grid.addWidget(self.lbl_file, 3, 0)
        grid.addWidget(self.filename_edit, 3, 1, 1, 2)

        # ==============================
        # Queue + Resolution (same row)
        # ==============================
        self.lbl_queue = label_style(self.tr("Queue:"))
        # self.queue_combo = QComboBox()
        # # self.queue_combo.addItems(["Default", "Night", "Weekend"])
        # self.queue_combo.setFixedWidth(190)

        # self.lbl_resolution = label_style(self.tr("Resolution:"))
        # self.resolution_combo = QComboBox()
        # self.resolution_combo.setFixedWidth(190)

        # queue_res_row = QHBoxLayout()
        # queue_res_row.setSpacing(6)
        # queue_res_row.addWidget(self.lbl_queue)
        # queue_res_row.addWidget(self.queue_combo)
        # queue_res_row.addSpacing(16)
        # queue_res_row.addWidget(self.lbl_resolution)
        # queue_res_row.addWidget(self.resolution_combo)
        # queue_res_row.addStretch()

        # grid.addLayout(queue_res_row, 4, 1, 1, 2)
        self.lbl_queue = label_style(self.tr("Queue:"))
        self.queue_combo = QComboBox()
        self.queue_combo.setFixedWidth(190)

        self.lbl_resolution = label_style(self.tr("Resolution:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.setFixedWidth(190)

        queue_res_row = QHBoxLayout()
        queue_res_row.setSpacing(6)
        queue_res_row.addWidget(self.lbl_queue)
        queue_res_row.addWidget(self.queue_combo)
        queue_res_row.addSpacing(16)
        queue_res_row.addWidget(self.lbl_resolution)
        queue_res_row.addWidget(self.resolution_combo)
        queue_res_row.addStretch()

        grid.addLayout(queue_res_row, 4, 1, 1, 2)

        # ── Engine selector row (non-intrusive, sits under queue/resolution) ──
        self.lbl_engine = label_style(self.tr("Engine:"))
        self.engine_combo = QComboBox()
        self.engine_combo.setFixedWidth(120)
        self.engine_combo.addItems(["yt-dlp", "aria2c", "curl"])
        self.engine_combo.setToolTip(self.tr("Select download engine for this download"))

        engine_row = QHBoxLayout()
        engine_row.setSpacing(6)
        engine_row.addWidget(self.lbl_engine)
        engine_row.addWidget(self.engine_combo)
        engine_row.addStretch()

        grid.addLayout(engine_row, 5, 1, 1, 2)

        # ==============================
        # Right info panel (thumbnail + size)
        # ==============================
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(20, 0, 0, 0)  
        right_panel.setSpacing(10)

        # Tiny progress bar (URL processing)
        self.url_progress = QProgressBar()
        self.url_progress.setFixedSize(140, 6)
        self.url_progress.setRange(0, 0)  
        self.url_progress.setTextVisible(False)
        self.url_progress.hide()

        right_panel.addWidget(self.url_progress)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(140, 90)
        
        
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setText("Thumbnail")
        

        right_panel.addWidget(self.thumbnail_label, alignment=Qt.AlignTop)

        # spacer to control gap between thumbnail and size info
        right_panel.addSpacerItem(QSpacerItem(10, 2, QSizePolicy.Minimum, QSizePolicy.Fixed))

       
        self.lbl_size_value = QLabel("0.0 GB")
        self.lbl_size_value.setAlignment(Qt.AlignCenter)
        

        
        right_panel.addWidget(self.lbl_size_value)
        right_panel.addStretch()

        grid.addLayout(right_panel, 1, 3, 4, 1)

        # ==============================
        # Bottom buttons
        # ==============================
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.HLine)
        divider2.setFrameShadow(QFrame.Sunken)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.advance_btn = QPushButton(self.tr("Advanced"))
        self.retry_btn = QPushButton(self.tr("Retry"))
        self.change_folder_btn = QPushButton(self.tr("Change Folder"))
        self.import_btn = QPushButton(self.tr("Import File"))
        self.import_btn.setToolTip(self.tr("Import multiple links from a text file"))
        

        btn_row.addWidget(self.advance_btn)
        btn_row.addWidget(self.retry_btn)
        btn_row.addWidget(self.change_folder_btn)
        btn_row.addWidget(self.import_btn)
        btn_row.addStretch()

        self.cancel_close_btn = QPushButton(self.tr("Close"))
        self.download_btn = QPushButton(self.tr("Start Download"))
        self.download_btn.setDefault(True)

        btn_row.addWidget(self.cancel_close_btn)
        btn_row.addWidget(self.download_btn)

        # ==============================
        # Assemble
        # ==============================
        main_layout.addLayout(grid)
        main_layout.addWidget(divider1)
        main_layout.addLayout(btn_row)
        self.cancel_close_btn.clicked.connect(self.close)
        self.btn_add_category.clicked.connect(self.open_add_category_dialog)
        # initialize save path to selected category's preferred path (if any)
        try:
            self._on_category_changed(self.category_combo.currentText())
        except Exception:
            pass

        self.current_theme = current_theme  # default theme 

        self._apply_styles()
        self.current_language = lang
        self.apply_language(self.current_language)

        
    
    def _apply_styles(self):
        """Apply the stylesheet based on current theme."""
        qss = get_stylesheet(self.current_theme)
        try:
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss)
        except Exception:
            # fallback to per-window stylesheet
            try:
                self.setStyleSheet(qss)
            except Exception:
                pass

    def _on_category_changed(self, name: str):
        """When category selection changes, update the Save-to path if category has a preferred path."""
        if not name:
            return
        info = self._category_map.get(name)
        if info:
            p = info.get("path") or ""
            if p:
                # if path exists, set it; otherwise leave current save_to_edit
                try:
                    self.save_to_edit.setText(p)
                except Exception:
                    pass
    
    def _norm(self, name: str) -> str:
        return name.strip().lower()


    def open_add_category_dialog(self):
        from modules.config import lang
        old_language = lang
        dlg = AddCategoryDialog(self)
        dlg.apply_language(lang)   # ensure dialog is translated
        result = dlg.exec()
        if result == QDialog.Accepted and lang != old_language:
            self.apply_language(lang)
            self.retrans()

        name = dlg.name_edit.text().strip()
        if not name:
            return

        key = self._norm(name)

        # Prevent duplicates (defaults OR existing)
        existing_keys = {self._norm(k) for k in self._category_map.keys()}
        if key in existing_keys:
            QMessageBox.warning(
                self,
                "Duplicate Category",
                f"The category '{name}' already exists."
            )
            return

        types = dlg.types_edit.text().strip()
        path = dlg.path_edit.text().strip() if key not in existing_keys else download_folder

        # persist safely
        try:
            self.settings_manager.add_category(name, types=types, path=path)
        except Exception:
            pass

        # add new category
        self._category_map[name] = {"types": types, "path": path}
        self.category_combo.addItem(name)
        self.category_combo.setCurrentText(name)

        if path:
            self.save_to_edit.setText(path)

    def closeEvent(self, event):
        """
        Override close event to just hide the window instead of closing it.
        This prevents the window from being destroyed and allows it to be reused.
        Also ensures closing this dialog doesn't quit the entire application.
        """
        # Don't destroy the window, just hide it
        self.hide()

        # Ignore the close event (don't actually close/destroy the window)
        event.ignore()


    def resource_path2(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)


    def apply_language(self, language):
        QCoreApplication.instance().removeTranslator(self.translator)

        file_map = {
            "French": "app_fr.qm",
            "Spanish": "app_es.qm",
            "Chinese": "app_zh.qm",
            "Korean": "app_ko.qm",
            "Japanese": "app_ja.qm",
            "English": "app_en.qm",
            "Hindi": "app_hi.qm"
        }

        if language in file_map:
            qm_path = self.resource_path2(f"../modules/translations/{file_map[language]}")
            if self.translator.load(qm_path):
                QCoreApplication.instance().installTranslator(self.translator)
                

       

        self.retrans()

    def retrans(self):
        self.setWindowTitle(self.tr("Add Download"))
        
        self.lbl_url.setText(self.tr("URL:"))
        self.lbl_file.setText(self.tr("File name:"))
        self.lbl_save.setText(self.tr("Save to:"))
        self.lbl_cat.setText(self.tr("Category:"))
        self.lbl_queue.setText(self.tr("Queue:"))
        self.lbl_resolution.setText(self.tr("Resolution:"))
        self.lbl_engine.setText(self.tr("Engine:"))
        self.engine_combo.setToolTip(self.tr("Select download engine for this download"))
        self.change_folder_btn.setText(self.tr("Change Folder"))
        self.retry_btn.setText(self.tr("Retry"))
        self.download_btn.setText(self.tr("Start Download"))
        self.cancel_close_btn.setText(self.tr("Close"))
        self.import_btn.setText(self.tr("Import File"))
        self.advance_btn.setText(self.tr("Advanced"))

        



class AddCategoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Add Category"))
        self.setFixedWidth(420)
        self.translator = QTranslator()
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Category name ---
        self.lbl_name = QLabel(self.tr("Category name"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(self.tr("e.g. Archives, Books"))

        layout.addWidget(self.lbl_name)
        layout.addWidget(self.name_edit)

        # --- File types ---
        self.lbl_types = QLabel(self.tr("Automatically put this category the following file types"))
        self.types_edit = QLineEdit()
        self.types_edit.setPlaceholderText(self.tr("mp4, mkv, avi, zip, rar"))

        layout.addWidget(self.lbl_types)
        layout.addWidget(self.types_edit)

        # --- Save location ---
        self.lbl_path = QLabel(self.tr("Save future downloads for this category to"))
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(self.tr("Choose folder path…"))
        self.btn_browse = QPushButton(self.tr("Browse"))

        path_row.addWidget(self.path_edit)
        path_row.addWidget(self.btn_browse)

        layout.addWidget(self.lbl_path)
        layout.addLayout(path_row)

        # --- Buttons (IDM-style flat) ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton(self.tr("Cancel"))
        self.btn_ok = QPushButton(self.tr("OK"))
        self.btn_ok.setDefault(True)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)

        layout.addSpacing(6)
        layout.addLayout(btn_row)

        # --- Signals ---
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_browse.clicked.connect(self.browse_folder)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Category Folder")
        if folder:
            self.path_edit.setText(folder)
    

    def resource_path2(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)


    def apply_language(self, language):
        QCoreApplication.instance().removeTranslator(self.translator)

        file_map = {
            "French": "app_fr.qm",
            "Spanish": "app_es.qm",
            "Chinese": "app_zh.qm",
            "Korean": "app_ko.qm",
            "Japanese": "app_ja.qm",
            "English": "app_en.qm",
            "Hindi": "app_hi.qm"
        }

        if language in file_map:
            qm_path = self.resource_path2(f"../modules/translations/{file_map[language]}")
            if self.translator.load(qm_path):
                QCoreApplication.instance().installTranslator(self.translator)
            

       

        self.retrans()

    def retrans(self):
        self.setWindowTitle(self.tr("Add Category"))
        self.lbl_name.setText(self.tr("Category name"))
        self.name_edit.setPlaceholderText(self.tr("e.g. Archives, Books"))
        self.lbl_types.setText(self.tr("Automatically put this category the following file types"))
        self.types_edit.setPlaceholderText(self.tr("mp4, mkv, avi, zip, rar"))
        self.lbl_path.setText(self.tr("Save future downloads for this category to"))
        self.path_edit.setPlaceholderText(self.tr("Choose folder path…"))
        self.btn_browse.setText(self.tr("Browse"))
        self.btn_cancel.setText(self.tr("Cancel"))
        self.btn_ok.setText(self.tr("OK"))