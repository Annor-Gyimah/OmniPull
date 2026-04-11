
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

from modules.settings_manager import SettingsManager
from modules.utils import log

from PySide6.QtCore import Qt, Slot, QCoreApplication, QTranslator
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox, QLineEdit, QFormLayout, QWidget, QStyle, QStyledItemDelegate
)



class NoFocusDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if option.state & QStyle.State_HasFocus:
            option.state = option.state ^ QStyle.State_HasFocus
        super().paint(painter, option, index)


class CategoryDialog(QDialog):
    """Manage persisted (user-created) categories.

    Lists categories stored in modules/category_manager.py (category.cfg)
    and allows removing them. Defaults are not shown here.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Manage Categories"))
        self.setMinimumWidth(520)
        self.settings_manager = SettingsManager()
        self.translator = QTranslator()
        self.categories = self.settings_manager.load_categories()

        self.layout = QVBoxLayout(self)

        self.info_label = QLabel(self.tr("Select a category to view details or remove it."))
        self.layout.addWidget(self.info_label)

        self.list = QListWidget()
        self.list.setItemDelegate(NoFocusDelegate())
        self.layout.addWidget(self.list, 1)

        # details area (read-only)
        form = QFormLayout()
        self.name_label = QLabel(self.tr("Name:"))
        self.name_view = QLineEdit()
        self.name_view.setReadOnly(True)

        self.types_label = QLabel(self.tr("Types:"))
        self.types_view = QLineEdit()
        self.types_view.setReadOnly(True)

        self.path_label = QLabel(self.tr("Path:"))
        self.path_view = QLineEdit()
        self.path_view.setReadOnly(True)

        form.addRow(self.name_label, self.name_view)
        form.addRow(self.types_label, self.types_view)
        form.addRow(self.path_label, self.path_view)
        self.layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.remove_btn = QPushButton(self.tr("Remove"))
        self.remove_btn.setEnabled(False)
        self.close_btn = QPushButton(self.tr("Close"))
        btn_row.addWidget(self.remove_btn)
        btn_row.addWidget(self.close_btn)
        self.layout.addLayout(btn_row)

        # wire
        self.list.currentItemChanged.connect(self._on_selection_changed)
        self.remove_btn.clicked.connect(self._on_remove)
        self.close_btn.clicked.connect(self.accept)

        # load items
        self._load_items()

    def _load_items(self) -> None:
        self.list.clear()
        try:
            cats = self.categories
        except Exception:
            cats = []

        for c in cats:
            name = c.get("name")
            if not name:
                continue
            item = QListWidgetItem(name)
            # store full dict in UserRole for quick access
            item.setData(Qt.UserRole, c)
            self.list.addItem(item)

        # disable remove if none
        self.remove_btn.setEnabled(self.list.count() > 0)

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            self.name_view.clear()
            self.types_view.clear()
            self.path_view.clear()
            self.remove_btn.setEnabled(False)
            return

        data = current.data(Qt.UserRole) or {}
        self.name_view.setText(data.get("name", ""))
        self.types_view.setText(data.get("types", ""))
        self.path_view.setText(data.get("path", ""))
        self.remove_btn.setEnabled(True)

    def _confirm_remove(self, name: str) -> bool:
        if not name:
            return False
        reply = QMessageBox.question(
            self,
            self.translated_messages["confirm_remove_title"],
            self.translated_messages["confirm_remove_text"] % name,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes


    @Slot()
    def _on_remove(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        data = item.data(Qt.UserRole) or {}
        name = data.get("name")
        if not name:
            return
        if not self._confirm_remove(name):
            return

        ok = self.settings_manager.remove_category(name)
        if ok:
            row = self.list.currentRow()
            self.list.takeItem(row)
            self.name_view.clear()
            self.types_view.clear()
            self.path_view.clear()
            QMessageBox.information(
                self,
                self.translated_messages["removed_title"],
                self.translated_messages["removed_text"] % name
            )
            if hasattr(self.parent(), "update_category_list"):
                self.parent().update_category_list()
            if hasattr(self.parent(), "update_category_combo"):
                self.parent().update_category_combo()
        else:
            QMessageBox.warning(
                self,
                self.translated_messages["not_removed_title"],
                self.translated_messages["not_removed_text"] % name
            )

    


    def resource_path(self, relative_path):
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
        }

        if language in file_map:
            qm_path = self.resource_path(f"../modules/translations/{file_map[language]}")
            if self.translator.load(qm_path):
                QCoreApplication.instance().installTranslator(self.translator)
                
            else:
                log(f"[Language] Failed to load {qm_path}", log_level=1)

       

        self.retrans()

    def retrans(self):
        # Update window title and labels
        self.setWindowTitle(self.tr("Manage Categories"))
        self.info_label.setText(self.tr("Select a category to view details or remove it."))
        self.name_label.setText(self.tr("Name:"))
        self.types_label.setText(self.tr("Types:"))
        self.path_label.setText(self.tr("Path:"))
        self.remove_btn.setText(self.tr("Remove"))
        self.close_btn.setText(self.tr("Close"))

        # --- Add translated messages ---
        self.translated_messages = {
            "confirm_remove_title": self.tr("Remove category"),
            "confirm_remove_text": self.tr("Remove category %s? This cannot be undone."),
            "removed_title": self.tr("Removed"),
            "removed_text": self.tr("Category %s removed."),
            "not_removed_title": self.tr("Not removed"),
            "not_removed_text": self.tr("Category %s could not be removed.")
        }

        

