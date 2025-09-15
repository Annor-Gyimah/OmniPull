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


from modules import config, setting

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
)



tutorial_steps = [
    ("Welcome to OmniPull", "Your powerful cross-platform download manager.", ":/tutorial_images/step1.png"),
    ("Download Table", "View on the download table, completed downloads, paused downloads, queued downloads, scheduled downloads, pending downloads, etc.", ":/tutorial_images/step2.png"),
    ("Toolbar Options", "Download operations like pause, resume, cancel, delete, schedule all etc on single downloads or a batch downloads.", ":/tutorial_images/step2a.png"),
    ("Table Options", "Schedule, open completed downloads, view download file properties, add downloads to queues etc.", ":/tutorial_images/step2b.png"),
    ("Schedule Download Dialog", "Schedule downloads at specific dates and time at your own convenience.", ":/tutorial_images/step2c.png"),
    ("Settings Panel", "Customize your experience in the settings panel, selection of desired language, download engines, customizing download engines, checking for updates,etc. Please change the QT FONT DPI value for it to suit your window display.", ":/tutorial_images/step2d.png"),
    ("Queue System", "Manage downloads by organizing them into queues.", ":/tutorial_images/step2e.png"),
    ("Terminal Logs", "See detailed events like processing of youtube links and other site links, errors, and important informations.", ":/tutorial_images/step3.png"),
]


class TutorialOverlay(QWidget):
    def __init__(self, parent, steps, show_exit_button=False):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.setFixedSize(parent.size())
        self.setFocusPolicy(Qt.StrongFocus)  # Ensure it accepts keyboard events
        self.setFocus()  # Immediately set focus to this widget

        self.steps = steps
        self.current_step = 0
        self.show_exit_button = show_exit_button

        # Tutorial Image
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            border-radius: 12px;
            border: 2px solid #ffffff40;
            padding: 5px;
            background-color: rgba(255, 255, 255, 0.1);
        """)
        self.image_label.setFixedSize(QSize(600, 400))
        self.image_label.setScaledContents(True)

        # Tutorial Text
        self.label = QLabel(self)
        self.label.setStyleSheet("""
            color: white;
            font-size: 18px;
            padding: 40px;
            background-color: rgba(0,0,0,200);
            border-radius: 8px;
        """)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)

        # Buttons
        # Buttons with individual styles
        self.previous_button = QPushButton("Previous", self)
        self.previous_button.setStyleSheet("""
            background-color: #f44336;  /* Red */
            color: white;
            padding: 6px 16px;
            border: none;
            border-radius: 4px;
            font-size: 14px;
        """)
        self.previous_button.clicked.connect(self.previous_step)

        self.exit_button = QPushButton("Exit", self)
        self.exit_button.setStyleSheet("""
            background-color: #4CAF50;  /* Green */
            color: white;
            padding: 6px 16px;
            border: none;
            border-radius: 4px;
            font-size: 14px;
        """)
        self.exit_button.clicked.connect(self.finish_tutorial)
        self.exit_button.setVisible(show_exit_button)

        self.next_button = QPushButton("Next", self)
        self.next_button.setStyleSheet("""
            background-color: #2196F3;  /* Blue */
            color: white;
            padding: 6px 16px;
            border: none;
            border-radius: 4px;
            font-size: 14px;
        """)
        self.next_button.clicked.connect(self.next_step)

        # Layout for buttons with tighter spacing
        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(10)  # Reduce space between buttons
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.previous_button)
        if self.show_exit_button:
            self.button_layout.addWidget(self.exit_button)
        self.button_layout.addWidget(self.next_button)
        self.button_layout.addStretch()


        # Main layout
        self.layout = QVBoxLayout()
        self.layout.addStretch()
        self.layout.addWidget(self.image_label, alignment=Qt.AlignCenter)
        self.layout.addSpacing(10)
        self.layout.addWidget(self.label)
        self.layout.addSpacing(10)
        self.layout.addLayout(self.button_layout)
        self.layout.addStretch()

        self.setLayout(self.layout)

        self.update_step()
        self.showFullScreen()  # Ensure it covers the screen

    def update_step(self):
        if self.current_step >= len(self.steps):
            self.finish_tutorial()
            return

        title, msg, image_path = self.steps[self.current_step]
        # self.label.setText(f"<b>{title}</b><br>{msg}")
        self.label.setText(f"<b>{title}</b><br>{msg}<br><br><i>Use ← and → keys to navigate</i>")


        pixmap = QPixmap(image_path)
        self.image_label.setPixmap(pixmap if not pixmap.isNull() else QPixmap(600, 400).fill(QColor("gray")))

    def next_step(self):
        self.current_step += 1
        self.update_step()

    def previous_step(self):
        if self.current_step > 0:
            self.current_step -= 1
            self.update_step()
            
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.next_step()
        elif event.key() == Qt.Key_Left:
            self.previous_step()
        elif event.key() == Qt.Key_Escape and self.show_exit_button:
            self.finish_tutorial()


    def finish_tutorial(self):
        config.tutorial_completed = True
        setting.save_setting()
        self.close()