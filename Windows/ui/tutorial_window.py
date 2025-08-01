from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt
import os
from modules import config, setting


tutorial_steps = [
    ("Welcome to OmniPull", "This is your powerful cross-platform download manager.", ":/tutorial_images/step1.png"),
    ("Queue System", "Manage downloads by organizing them into queues.", ":/tutorial_images/step2.png"),
    ("Settings Panel", "Customize your experience in the settings panel.", ":/tutorial_images/step3.png"),
    ("Download Options", "Choose from different engines and formats.", ":/tutorial_images/step4.png"),
]

class TutorialOverlay(QWidget):
    def __init__(self, parent, steps):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.setFixedSize(parent.size())

        self.steps = steps
        self.current_step = 0

        # Image QLabel
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            border-radius: 12px;
            border: 2px solid #ffffff40;
            padding: 5px;
            background-color: rgba(255, 255, 255, 0.1);
        """)
        self.image_label.setFixedHeight(400)
        self.image_label.setFixedWidth(600)
        self.image_label.setScaledContents(True)

        # Tutorial text
        self.label = QLabel(self)
        self.label.setStyleSheet("""
            color: white;
            font-size: 18px;
            padding: 60px;
            background-color: rgba(0,0,0,200);
            border-radius: 8px;
        """)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)

        # Next button
        self.next_button = QPushButton("Next", self)
        self.previous_button = QPushButton("Previous", self)
        button_style = """
            background-color: #4CAF50;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            """
        self.next_button.setStyleSheet(button_style)
        self.previous_button.setStyleSheet(button_style)
        self.next_button.clicked.connect(self.next_step)
        self.previous_button.clicked.connect(self.previous_step)

        # Horizontal layout for buttons
        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(self.previous_button)
        self.button_layout.addWidget(self.next_button)

        # Layout setup
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.image_label, alignment=Qt.AlignCenter)
        self.layout.addWidget(self.label)
        self.layout.addLayout(self.button_layout)
        self.setLayout(self.layout)

        self.update_step()
        self.resize(parent.size())
        self.move(0, 0)
        self.show()

    def update_step(self):
        if self.current_step >= len(self.steps):
            self.finish_tutorial()
            return

        title, msg, image_path = self.steps[self.current_step]
        self.label.setText(f"<b>{title}</b><br>{msg}")

        if image_path:
            pixmap = QPixmap(image_path)
            self.image_label.setPixmap(pixmap)
        else:
            #self.image_label.clear()
            pixmap = QPixmap(560, 200)
            pixmap.fill(QColor("gray"))

    def next_step(self):
        self.current_step += 1
        self.update_step()
    
    def previous_step(self):
        if self.current_step > 0:
            self.current_step -= 1
            self.update_step()

    def finish_tutorial(self):
        config.tutorial_completed = True
        setting.save_setting()
        self.close()