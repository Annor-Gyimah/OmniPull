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

from modules import config
from ui.styles import get_stylesheet
from modules.config import accent_color, lang

from PySide6.QtCore import Qt,  Signal, QThread, QCoreApplication, QTranslator
from PySide6.QtGui  import QFont, QColor, QPalette, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QFrame, QGraphicsDropShadowEffect,
    QWidget, QSpacerItem, QSizePolicy, QScrollArea, QGridLayout, QStackedWidget
)




# ── Colour palette (dark industrial / utilitarian theme) ─────────────────────
_C = {
    "bg":           "#f8f9fb",   # bright, clean canvas
    "surface":      "#ffffff",   # white card surface
    "border":       "#e2e8f0",   # light grey borders
    # "accent":       "#2b6cb0",   # deep professional blue (darker for contrast)
    "accent": accent_color,
    "accent_dim":   "#ebf8ff",   # very light blue for badges/hover
    "text_primary": "#1a202c",   # dark slate for high-readability
    "text_muted":   "#718096",   # cool grey for hints
    "text_label":   "#4a5568",   # slate for form labels
    "success":      "#38a169",   # forest green
    "warn":         "#dd6b20",   # burnt orange (better contrast on white)
    "danger":       "#e53e3e",   # red
    "input_bg":     "#f1f5f9",   # subtle grey for inputs
    "separator":    "#edf2f7",
}




def _hr(parent=None) -> QFrame:
    """Thin horizontal separator line."""
    line = QFrame(parent)
    line.setObjectName("hr")
    line.setFrameShape(QFrame.HLine)
    return line


def _section_header(text: str, parent=None) -> QLabel:
    lbl = QLabel(text.upper(), parent)
    lbl.setObjectName("section_header")
    return lbl


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    return frame


class AdvancedMetadataDialog(QDialog):
    """
    Advanced Download Configuration dialog for OmniPull.

    Focused purely on per-download yt-dlp knobs:
        • Subtitle language  (QComboBox)
        • Subtitle format    (QComboBox: best / srt / vtt / ass / lrc)
        • Download comments  (QCheckBox)

    Data is persisted onto video_obj when the user clicks "Apply & Close":
        video_obj.selected_subtitle  – str  | None   (language code)
        video_obj.subtitle_format    – str           (format string)
        video_obj.is_auto_sub        – bool          (True if auto-caption was selected)
        video_obj.download_comments  – bool
    """

    # ─── Known language codes → display names ───────────────────────────────
    _LANG_NAMES: dict[str, str] = {
        "af": "Afrikaans", "ak": "Akan", "sq": "Albanian", "am": "Amharic",
        "ar": "Arabic", "hy": "Armenian", "as": "Assamese", "ay": "Aymara",
        "az": "Azerbaijani", "bn": "Bengali", "bs": "Bosnian", "bg": "Bulgarian",
        "ca": "Catalan", "zh": "Chinese", "zh-Hans": "Chinese (Simplified)",
        "zh-Hant": "Chinese (Traditional)", "hr": "Croatian", "cs": "Czech",
        "da": "Danish", "nl": "Dutch", "en": "English", "eo": "Esperanto",
        "et": "Estonian", "fi": "Finnish", "fr": "French", "gl": "Galician",
        "ka": "Georgian", "de": "German", "el": "Greek", "gu": "Gujarati",
        "ht": "Haitian Creole", "ha": "Hausa", "he": "Hebrew", "hi": "Hindi",
        "hu": "Hungarian", "id": "Indonesian", "is": "Icelandic", "it": "Italian",
        "ja": "Japanese", "jv": "Javanese", "kn": "Kannada", "kk": "Kazakh",
        "km": "Khmer", "ko": "Korean", "ku": "Kurdish", "lo": "Lao",
        "la": "Latin", "lv": "Latvian", "lt": "Lithuanian", "mk": "Macedonian",
        "mg": "Malagasy", "ms": "Malay", "ml": "Malayalam", "mr": "Marathi",
        "mi": "Māori", "mn": "Mongolian", "my": "Myanmar (Burmese)",
        "ne": "Nepali", "no": "Norwegian", "or": "Odia", "fa": "Persian",
        "pl": "Polish", "pt": "Portuguese", "pa": "Punjabi", "ro": "Romanian",
        "ru": "Russian", "sr": "Serbian", "si": "Sinhala", "sk": "Slovak",
        "sl": "Slovenian", "so": "Somali", "es": "Spanish", "su": "Sundanese",
        "sw": "Swahili", "sv": "Swedish", "tl": "Filipino", "tg": "Tajik",
        "ta": "Tamil", "te": "Telugu", "th": "Thai", "tr": "Turkish",
        "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek", "vi": "Vietnamese",
        "cy": "Welsh", "xh": "Xhosa", "yi": "Yiddish", "yo": "Yoruba",
        "zu": "Zulu",
    }

    _SUBTITLE_FORMATS = ["best", "srt", "vtt", "ass", "lrc"]

    def __init__(self, video_obj, parent=None):
        super().__init__(parent)
        self.video_obj = video_obj
        # vid_info may be None / missing; always default to empty dict
        self.vid_info: dict = getattr(video_obj, "vid_info", None) or {}

        self._setup_window()
        self._build_ui()
        self.setObjectName("AdvancedMetadataDialog")
        self.current_theme = config.current_theme

        self.header_label = None
        self.subtitle_header = None
        self.comments_header = None

        self.translator = QTranslator()
        self.current_language = lang
        self.apply_language(self.current_language)
        
        self._apply_styles()
        self._restore_existing_settings()

    # ─────────────────────────────────────────────────────────────────────────
    #  Window chrome
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle(self.tr("Advanced Download Configuration  ·  OmniPull"))
        self.setMinimumSize(850, 500)
        self.setSizeGripEnabled(False)
        self.setModal(True)
        # Drop shadow (works on compositing WMs / Windows DWM)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)

    # ─────────────────────────────────────────────────────────────────────────
    #  UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Left Sidebar Navigation ──────────────────────────────────────────
        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        # ── Right Side: Content + Footer ─────────────────────────────────────
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_container.setObjectName("right_content_area")
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = self._build_header()
        right_layout.addWidget(header)

        # Stacked content (scrollable)
        self.stacked_widget = QStackedWidget()
        right_layout.addWidget(self.stacked_widget, 1)

        # Add pages
        self.stacked_widget.addWidget(self._build_media_subs_page())
        self.stacked_widget.addWidget(self._build_processing_page())

        # Footer
        footer = self._build_footer()
        right_layout.addWidget(footer)

        root.addWidget(right_container, 1)

    def _build_sidebar(self) -> QWidget:
        """Build the left sidebar with navigation buttons."""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(4)
        layout.setContentsMargins(12, 20, 12, 12)

        # Navigation buttons
        self.nav_buttons = []
        
        self.btn_media = QPushButton(self.tr("Media & Subs"))
        self.btn_media.setObjectName("nav_button")
        self.btn_media.setCursor(Qt.PointingHandCursor)
        self.btn_media.setCheckable(True)
        self.btn_media.setChecked(True)
        self.btn_media.clicked.connect(lambda: self._switch_page(0))
        self.nav_buttons.append(self.btn_media)
        layout.addWidget(self.btn_media)

        self.btn_processing = QPushButton(self.tr("Processing"))
        self.btn_processing.setObjectName("nav_button")
        self.btn_processing.setCursor(Qt.PointingHandCursor)
        self.btn_processing.setCheckable(True)
        self.btn_processing.clicked.connect(lambda: self._switch_page(1))
        self.nav_buttons.append(self.btn_processing)
        layout.addWidget(self.btn_processing)

        layout.addStretch()

        return sidebar

    def _build_header(self) -> QWidget:
        """Build the header with title."""
        header = QFrame()
        header.setObjectName("header")
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 20, 24, 20)

        icon_lbl = QLabel("⚙")
        icon_lbl.setStyleSheet(f"font-size:22px; color:{_C['accent']}; padding-right:8px;")
        
        self.title_lbl = QLabel(self.tr("Advanced Download Configuration"))
        self.title_lbl.setObjectName("title_header")
        # title_lbl.setStyleSheet(f"font-size:15px; font-weight:700; color:{_C['text_primary']};")
        
        layout.addWidget(icon_lbl)
        layout.addWidget(self.title_lbl, 1)

        return header

    def _build_footer(self) -> QWidget:
        """Build the footer with action buttons."""
        footer = QFrame()
        footer.setObjectName("footer")
        
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.addStretch()

        self.cancel_btn = QPushButton(self.tr("Cancel"))
        self.cancel_btn.setObjectName("btn_cancel")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton(self.tr("Apply & Close"))
        self.apply_btn.setObjectName("btn_apply")
        self.apply_btn.setDefault(True)
        self.apply_btn.setCursor(Qt.PointingHandCursor)
        self.apply_btn.clicked.connect(self.accept)
        layout.addWidget(self.apply_btn)

        return footer

    def _switch_page(self, index: int):
        """Switch to the specified page and update button states."""
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def _build_media_subs_page(self) -> QWidget:
        """Build Page 1: Media & Subtitles."""
        page = QWidget()
        
        # Make the page scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content.setObjectName("scroll_content")
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Add cards
        layout.addWidget(self._build_subtitle_card())
        layout.addWidget(self._build_comments_card())
        layout.addStretch()

        scroll.setWidget(content)
        
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        return page

    def _build_processing_page(self) -> QWidget:
        """Build Page 2: Post-Processing."""
        page = QWidget()
        
        # Make the page scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content.setObjectName("scroll_content")
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Add card
        layout.addWidget(self._build_postprocess_card())
        layout.addStretch()

        scroll.setWidget(content)
        
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        return page

    # ── Post-Processing card ──────────────────────────────────────────────────

    
    def _build_postprocess_card(self) -> QFrame:
        card = _card()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 14, 16, 16)

        self.header_label = _section_header(self.tr("Post-Processing & Conversion"))
        layout.addWidget(self.header_label)
        layout.addWidget(_hr())

        # ── Row 1: Conversion Mode ───────────────────────────────────────────
        conv_row = QHBoxLayout()
        self.action_label = QLabel(self.tr("Action:"))
        conv_row.addWidget(self.action_label)
        
        self.conv_mode_combo = QComboBox()
        self.conv_mode_combo.addItems([self.tr("None (Original)"), self.tr("Extract Audio"), self.tr("Remux Video"), self.tr("Recode Video")])
        conv_row.addWidget(self.conv_mode_combo, 1)
        
        layout.addLayout(conv_row)

        # ── Row 2: Target Format ─────────────────────────────────────────────
        fmt_row = QHBoxLayout()
        self.target_format_lbl = QLabel(self.tr("Target Format:"))
        fmt_row.addWidget(self.target_format_lbl)
        
        self.target_fmt_combo = QComboBox()
        # Audio formats + Video formats
        self.target_fmt_combo.addItems(["mp3", "m4a", "wav", "flac", "mp4", "mkv", "mov"])
        fmt_row.addWidget(self.target_fmt_combo, 1)
        
        layout.addLayout(fmt_row)

        # ── Row 3: Checkboxes (Grid) ─────────────────────────────────────────
        grid = QGridLayout()
        self.embed_metadata_chk = QCheckBox(self.tr("Embed Metadata"))
        self.embed_chapters_chk = QCheckBox(self.tr("Embed Chapters"))
        self.embed_thumb_chk    = QCheckBox(self.tr("Embed Thumbnail"))
        self.keep_video_chk     = QCheckBox(self.tr("Keep Original Video")) # --keep-video
        
        grid.addWidget(self.embed_metadata_chk, 0, 0)
        grid.addWidget(self.embed_chapters_chk, 0, 1)
        grid.addWidget(self.embed_thumb_chk,    1, 0)
        grid.addWidget(self.keep_video_chk,     1, 1)
        
        layout.addLayout(grid)

        return card

    # ── Subtitle card ─────────────────────────────────────────────────────────

    def _build_subtitle_card(self) -> QFrame:
        card = _card()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 14, 16, 16)

        # Section header
        self.subtitle_header = _section_header(self.tr("Subtitles"))
        layout.addWidget(self.subtitle_header)
        layout.addWidget(_hr())

        # ── Language row ──────────────────────────────────────────────────────
        lang_row = QHBoxLayout()
        self.lang_lbl = QLabel(self.tr("Language"))
        self.lang_lbl.setFixedWidth(100)
        lang_row.addWidget(self.lang_lbl)

        self.lang_combo = QComboBox()
        self.lang_combo.setPlaceholderText("— None —")
        self.lang_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lang_row.addWidget(self.lang_combo, 1)

        layout.addLayout(lang_row)

        # ── Format row ────────────────────────────────────────────────────────
        fmt_row = QHBoxLayout()
        self.fmt_lbl = QLabel(self.tr("Format"))
        self.fmt_lbl.setFixedWidth(100)
        fmt_row.addWidget(self.fmt_lbl)

        self.format_combo = QComboBox()
        self.format_combo.addItems(self._SUBTITLE_FORMATS)
        self.format_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        fmt_row.addWidget(self.format_combo, 1)

        layout.addLayout(fmt_row)

        # ── Availability hint ─────────────────────────────────────────────────
        self.sub_hint_lbl = QLabel("")
        self.sub_hint_lbl.setObjectName("hint")
        self.sub_hint_lbl.setWordWrap(True)
        layout.addWidget(self.sub_hint_lbl)

        # Populate the language combo from vid_info
        self.populate_subtitles()

        return card

    # ── Comments card ─────────────────────────────────────────────────────────

    def _build_comments_card(self) -> QFrame:
        card = _card()
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 14, 16, 16)

        self.comments_header = _section_header(self.tr("Comments"))
        layout.addWidget(self.comments_header)
        layout.addWidget(_hr())

        self.comments_chk = QCheckBox(self.tr("Download video comments  (YouTube only)"))
        layout.addWidget(self.comments_chk)

        self.hint = QLabel(
            self.tr("Comments are saved inside the .info.json file next to the download.")
        )
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        return card



    # ─────────────────────────────────────────────────────────────────────────
    #  Subtitle population  (public, callable externally)
    # ─────────────────────────────────────────────────────────────────────────

    def populate_subtitles(self):
        """
        Parse self.vid_info for available subtitles and auto-captions,
        then populate self.lang_combo.

        Each item stores a tuple as UserRole data:
            (lang_code: str, is_auto: bool)

        Handles gracefully when vid_info is missing or empty.
        """
        self.lang_combo.clear()

        # Sentinel: "no subtitle" option always first
        self.lang_combo.addItem(self.tr("— None (skip subtitles) —"))
        self.lang_combo.setItemData(0, ("", False), Qt.UserRole)

        if not self.vid_info:
            self.sub_hint_lbl.setText(
                self.tr("No video metadata available — subtitle list cannot be populated.")
            )
            return

        manual_subs: dict = self.vid_info.get("subtitles") or {}
        auto_caps:   dict = self.vid_info.get("automatic_captions") or {}

        # Build ordered list: manual first, then auto (de-duplicate by lang code)
        entries: list[tuple[str, bool]] = []
        seen: set[str] = set()

        for lang_code in sorted(manual_subs.keys()):
            if lang_code not in seen:
                entries.append((lang_code, False))
                seen.add(lang_code)

        for lang_code in sorted(auto_caps.keys()):
            if lang_code not in seen:
                entries.append((lang_code, True))
                seen.add(lang_code)

        if not entries:
            self.sub_hint_lbl.setText(
                "No subtitles or automatic captions found for this video."
            )
            return

        # Count for hint text
        n_manual = sum(1 for _, is_auto in entries if not is_auto)
        n_auto   = sum(1 for _, is_auto in entries if is_auto)
        parts = []
        if n_manual:
            parts.append(f"{n_manual} manual")
        if n_auto:
            parts.append(f"{n_auto} auto-generated")
        self.sub_hint_lbl.setText(self.tr("%1 track(s) found.").replace("%1", ", ".join(parts)))

        # Populate combo
        for lang_code, is_auto in entries:
            base_code  = lang_code.split("-")[0]
            lang_name  = self._LANG_NAMES.get(lang_code) \
                      or self._LANG_NAMES.get(base_code) \
                      or lang_code.upper()

            label = f"{lang_name}  ({lang_code})"
            if is_auto:
                label += "  [Auto]"

            self.lang_combo.addItem(label)
            idx = self.lang_combo.count() - 1
            self.lang_combo.setItemData(idx, (lang_code, is_auto), Qt.UserRole)

    # ─────────────────────────────────────────────────────────────────────────
    #  Restore previously saved settings from video_obj
    # ─────────────────────────────────────────────────────────────────────────

    def _restore_existing_settings(self):
        """Pre-fills all widgets from whatever was already stored on video_obj."""

        # ── Restore post-processing ─────────────────────────────────────────

        
        self.embed_metadata_chk.setChecked(bool(getattr(self.video_obj, "embed_metadata", True)))
        self.embed_chapters_chk.setChecked(bool(getattr(self.video_obj, "embed_chapters", True)))
    
        # Set Combos
        mode = getattr(self.video_obj, "conv_mode", "None (Original)")
        fmt  = getattr(self.video_obj, "target_format", "mp4")
        
        self.conv_mode_combo.setCurrentText(mode)
        self.target_fmt_combo.setCurrentText(fmt)
        
        # Set Keep Video Checkbox
        self.keep_video_chk.setChecked(bool(getattr(self.video_obj, "keep_video", False)))

        self.embed_thumb_chk.setChecked(bool(getattr(self.video_obj, "embed_thumbnail", False)))

        # ── Restore subtitle language ─────────────────────────────────────────
        saved_lang = getattr(self.video_obj, "selected_subtitle", None)
        if saved_lang:
            for i in range(self.lang_combo.count()):
                data = self.lang_combo.itemData(i, Qt.UserRole)
                if data and data[0] == saved_lang:
                    self.lang_combo.setCurrentIndex(i)
                    break

        # ── Restore subtitle format ───────────────────────────────────────────
        saved_fmt = getattr(self.video_obj, "subtitle_format", None)
        if saved_fmt:
            idx = self.format_combo.findText(saved_fmt)
            if idx >= 0:
                self.format_combo.setCurrentIndex(idx)

        # ── Restore comments ──────────────────────────────────────────────────
        self.comments_chk.setChecked(
            bool(getattr(self.video_obj, "download_comments", False))
        )

    def _apply_styles(self):
        """Apply the stylesheet based on current theme."""

        qss = get_stylesheet(self.current_theme)
        self.setStyleSheet(qss)

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

        
        self.setWindowTitle(self.tr("Advanced Download Configuration  ·  OmniPull"))
        self.btn_media.setText(self.tr("Media & Subs"))
        self.btn_processing.setText(self.tr("Processing"))
        self.title_lbl.setText(self.tr("Advanced Download Configuration"))
        self.cancel_btn.setText(self.tr("Cancel"))
        self.apply_btn.setText(self.tr("Apply & Close"))
        self.action_label.setText(self.tr("Action:"))
        self.target_format_lbl.setText(self.tr("Target Format:"))
        self.lang_lbl.setText(self.tr("Language"))
        self.fmt_lbl.setText(self.tr("Format"))
        self.hint.setText(
            self.tr("Comments are saved inside the .info.json file next to the download.")
        )
        self.sub_hint_lbl.setText(
            self.tr("No video metadata available — subtitle list cannot be populated.")
        )

        if self.header_label:
            self.header_label.setText(self.tr("Post-Processing & Conversion").upper())
        
        if self.subtitle_header:
            self.subtitle_header.setText(self.tr("Subtitles"))

        if self.comments_header:
            self.comments_header.setText(self.tr("Comments"))


        # Save current selection
        current_conv_idx = self.conv_mode_combo.currentIndex()
        
        self.conv_mode_combo.clear()
        self.conv_mode_combo.addItems([
            self.tr("None (Original)"), 
            self.tr("Extract Audio"), 
            self.tr("Remux Video"), 
            self.tr("Recode Video")
        ])
        
        # Restore selection
        self.conv_mode_combo.setCurrentIndex(current_conv_idx)

        # Re-populate subtitles after clearing (important for localization)
        # Store current selection before clearing
        current_data = None
        if self.lang_combo.currentIndex() >= 0:
            current_data = self.lang_combo.itemData(self.lang_combo.currentIndex(), Qt.UserRole)
        
        # Repopulate the entire combo with fresh translations
        self.populate_subtitles()
        
        # Try to restore the previous selection
        if current_data:
            for i in range(self.lang_combo.count()):
                if self.lang_combo.itemData(i, Qt.UserRole) == current_data:
                    self.lang_combo.setCurrentIndex(i)
                    break



    
        

    # ─────────────────────────────────────────────────────────────────────────
    #  Save state → video_obj when user clicks "Apply & Close"
    # ─────────────────────────────────────────────────────────────────────────

    def accept(self):
        """
        Persist all widget state onto self.video_obj using the canonical
        attribute names expected by get_advanced_opts().
        """

        # ── Post-processing Attributes ───────────────────────────────────────
        # Store the text from the combos so the logic can identify the action
        self.video_obj.conv_mode     = self.conv_mode_combo.currentText()
        self.video_obj.target_format  = self.target_fmt_combo.currentText()
        
        # Store the boolean for the 'Keep Video' checkbox
        self.video_obj.keep_video     = self.keep_video_chk.isChecked()
        
        # (Ensure the other metadata/chapter/thumb checkboxes are also saved here)
        self.video_obj.embed_metadata  = self.embed_metadata_chk.isChecked()
        self.video_obj.embed_chapters  = self.embed_chapters_chk.isChecked()
        self.video_obj.embed_thumbnail = self.embed_thumb_chk.isChecked()


        # ── Subtitle attributes ───────────────────────────────────────────────
        idx  = self.lang_combo.currentIndex()
        data = self.lang_combo.itemData(idx, Qt.UserRole)

        if data and data[0]:
            lang_code = data[0]   # e.g. "en", "fr", "ja"
            is_auto   = data[1]   # True if from automatic_captions
        else:
            lang_code = None
            is_auto   = False

        self.video_obj.selected_subtitle = lang_code
        self.video_obj.subtitle_format   = self.format_combo.currentText()
        self.video_obj.is_auto_sub       = is_auto

        # ── Comment attribute ─────────────────────────────────────────────────
        self.video_obj.download_comments = self.comments_chk.isChecked()

        super().accept()












