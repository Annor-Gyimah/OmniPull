
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
import webbrowser


from PySide6.QtCore import Qt
from PySide6.QtGui import  QPixmap

from modules.config import  lang, APP_VERSION

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QTextEdit
)

from PySide6.QtCore import Qt, QCoreApplication

from ui.language_manager import LanguageManager



class AboutDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setObjectName("AboutDialog")
        self.resize(460, 360)
        self.setMinimumSize(420, 320)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # ===== HEADER: LOGO + TITLE/URL =====
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        # Logo placeholder
        self.logo_label = QLabel()
        self.logo_label.setObjectName("AboutLogoLabel")
        self.logo_label.setFixedSize(64, 64)
        self.logo_label.setAlignment(Qt.AlignCenter) 
        pix = QPixmap(":/icons/logo4.png").scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.logo_label.setPixmap(pix)

        header_row.addWidget(self.logo_label)

        # App name + version + URL
        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        self.app_name_label = QLabel("")
        self.app_name_label.setObjectName("AboutAppNameLabel")

        self.version_label = QLabel(self.tr("Version"))
        self.version_label.setObjectName("AboutVersionLabel")

        self.url_label = QLabel("")
        self.url_label.setObjectName("AboutUrlLabel")
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        title_col.addWidget(self.app_name_label)
        title_col.addWidget(self.version_label)
        title_col.addWidget(self.url_label)

        header_row.addLayout(title_col)
        header_row.addStretch()

        main_layout.addLayout(header_row)

        # ===== SEPARATOR =====
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)

        # ===== DESCRIPTION =====
        desc_title = QLabel(self.tr("About this app"))
        desc_title.setObjectName("AboutSectionTitleLabel")
        main_layout.addWidget(desc_title)

        self.description_text = QTextEdit()
        self.description_text.setObjectName("AboutDescriptionText")
        self.description_text.setReadOnly(True)
        self.description_text.setMinimumHeight(100)
        self.description_text.setPlainText(self.tr(
            "ODM is a python open source Internet Download Manager with multi-connections, "
            "high speed engine, it downloads general files and videos from YouTube"
            "and tons of other streaming websites."
            )   
        )
        main_layout.addWidget(self.description_text, 1)

        # ===== CREATOR + LICENSE =====
        info_row = QHBoxLayout()
        info_row.setSpacing(20)

        creator_col = QVBoxLayout()
        self.creator_label = QLabel(self.tr("Creator"))
        self.creator_label.setObjectName("AboutInfoHeadingLabel")
        self.creator_value_label = QLabel("")
        self.creator_value_label.setObjectName("AboutInfoValueLabel")
        creator_col.addWidget(self.creator_label)
        creator_col.addWidget(self.creator_value_label)

        self.license_col = QVBoxLayout()
        self.license_label = QLabel(self.tr("License"))
        self.license_label.setObjectName("AboutInfoHeadingLabel")
        self.license_value_label = QLabel("")
        self.license_value_label.setObjectName("AboutInfoValueLabel")
        self.license_col.addWidget(self.license_label)
        self.license_col.addWidget(self.license_value_label)

        info_row.addLayout(creator_col)
        info_row.addLayout(self.license_col)
        info_row.addStretch()

        main_layout.addLayout(info_row)

        # ===== BUTTONS =====
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_website = QPushButton(self.tr("Website"))
        self.btn_website.clicked.connect(lambda: webbrowser.open("https://omnipull.pythonanywhere.com/"))
        self.btn_secondary = QPushButton(self.tr("Source code"))  
        self.btn_secondary.clicked.connect(lambda: webbrowser.open("https://github.com/Annor-Gyimah/OmniPull"))
        btn_row.addWidget(self.btn_website)
        btn_row.addWidget(self.btn_secondary)
        btn_row.addStretch()

        self.btn_close = QPushButton(self.tr("Close"))
        btn_row.addWidget(self.btn_close)

        main_layout.addLayout(btn_row)

        self.btn_close.clicked.connect(self.accept)
        self.apply_language_about(lang)


    
    def apply_language_about(self, lang):
        self.current_language = lang
        self.lang_manager = LanguageManager()
        self.lang_manager.apply_language(self.current_language)
        self.retrans()



    def retrans(self):

        self.setWindowTitle(self.tr("About"))
        self.btn_website.setText(self.tr("Website"))
        self.btn_secondary.setText(self.tr("Source code"))
        self.btn_close.setText(self.tr("Close"))
        self.description_text.setPlainText(self.tr(
            "ODM is a python open source Internet Download Manager with multi-connections, "
            "high speed engine, it downloads general files and videos from YouTube"
            "and tons of other streaming websites."
            )   
        )
        self.creator_label.setText(self.tr("Creator"))
        self.license_label.setText(self.tr("License"))
        self.version_label.setText(self.tr("Version %1").replace("%1", APP_VERSION))
        


    def set_app_info(self, name: str, version: str, url: str):
        self.app_name_label.setText(name)
        self.version_label.setText(self.tr("Version %1").replace("%1", version))
        self.url_label.setText(url)

    def set_creator(self, creator: str):
        self.creator_value_label.setText(creator)

    def set_license(self, license_text: str):
        self.license_value_label.setText(license_text)

    def set_description(self, text: str):
        self.description_text.setPlainText(text)
