import os
import sys
from PySide6.QtCore import QCoreApplication, QTranslator


class LanguageManager:
    def __init__(self, ctx=None):
        self.translator = QTranslator()
        self.ctx = ctx  # optional logging/context

        self.file_map = {
            "English": "app_en.qm",
            "French": "app_fr.qm",
            "Spanish": "app_es.qm",
            "Chinese": "app_zh.qm",
            "Korean": "app_ko.qm",
            "Japanese": "app_ja.qm",
            "Hindi": "app_hi.qm",
            "Russian": "app_ru.qm"
        }

    def resource_path(self, relative_path):
        """Works for dev + PyInstaller"""
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)

    def apply_language(self, language):
        """Load and install translation"""
        app = QCoreApplication.instance()
        if app is None:
            return False

        app.removeTranslator(self.translator)

        if language not in self.file_map:
            return False

        qm_path = self.resource_path(
            f"translations/{self.file_map[language]}"
        )
 
        if self.translator.load(qm_path):
            app.installTranslator(self.translator)
            return True

        return False

    def apply_language_global(self, language):
        """
        Apply language globally and refresh given windows.
        
        windows: list of window instances
        """
        self.apply_language(language)

        for widget in QCoreApplication.instance().allWidgets():
            if hasattr(widget, "retrans"):
                widget.retrans()