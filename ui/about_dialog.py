from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QGraphicsBlurEffect
)
from PySide6.QtGui import QPixmap, QCursor
from PySide6.QtCore import Qt
import webbrowser


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About PyIconic")
        self.setFixedSize(650, 360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        # === Frosted Glass Blur ===
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(18)
        self.setGraphicsEffect(blur)

        # === Glassy, Spacey QSS ===
        self.setStyleSheet("""
            QDialog {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                border: 1px solid rgba(80, 255, 180, 0.08);
                border-radius: 18px;
            }

            QLabel {
                color: rgba(220, 255, 230, 210);
                background: transparent;
                font-size: 13px;
            }

            QLabel#Title {
                font-size: 22px;
                font-weight: bold;
                color: #6FFFB0;
            }

            QLabel#Tagline {
                color: #88ccaa;
                font-size: 12px;
            }

            QLabel#Footer {
                color: #2DE099;
                font-size: 11px;
            }

            QPushButton {
                background-color: rgba(0, 128, 96, 0.4);
                color: white;
                padding: 10px 16px;
                border-radius: 10px;
                font-size: 13px;
                border: 1px solid rgba(0, 255, 180, 0.08);
            }

            QPushButton:hover {
                background-color: rgba(0, 192, 128, 0.6);
            }

            QFrame#line {
                background-color: rgba(0, 255, 180, 0.1);
            }
        """)


        # === Main Layout ===
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(24)

        # === LEFT SIDE ===
        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)
        left_layout.setAlignment(Qt.AlignTop)

        logo = QLabel()
        pix = QPixmap("../icons/d_window.png").scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo.setPixmap(pix)
        logo.setAlignment(Qt.AlignCenter)

        title = QLabel("PyIconic Downloader")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)

        version = QLabel("Version 1.5.4")
        version.setAlignment(Qt.AlignCenter)

        tagline = QLabel("Developed with ❤️ for you")
        tagline.setObjectName("Tagline")
        tagline.setAlignment(Qt.AlignCenter)

        link = QLabel('<a href="https://pyiconicdownloader.com">pyiconicdownloader.com</a>')
        link.setObjectName("Footer")
        link.setAlignment(Qt.AlignCenter)
        link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        link.setOpenExternalLinks(True)

        left_layout.addWidget(logo)
        left_layout.addWidget(title)
        left_layout.addWidget(version)
        left_layout.addSpacing(6)
        left_layout.addWidget(tagline)
        left_layout.addSpacing(6)
        left_layout.addWidget(link)

        # === DIVIDER ===
        divider = QFrame()
        divider.setObjectName("line")
        divider.setFrameShape(QFrame.VLine)
        divider.setFixedWidth(1)

        # === RIGHT SIDE ===
        right_layout = QVBoxLayout()
        right_layout.setSpacing(16)
        right_layout.setAlignment(Qt.AlignTop)

        def make_btn(text, url):
            btn = QPushButton(text)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda: webbrowser.open(url))
            btn.setMinimumHeight(56)
            return btn

        btn1 = make_btn("💖  This is a free & Open Source software\n     See the Source Code", "https://github.com/your-repo")
        btn2 = make_btn("🛠️  Powered by Open Source Software\n     View the Open-Source licenses", "https://github.com/your-repo/blob/main/LICENSE")
        btn3 = make_btn("🌍  Localized by Translators\n     Meet the Translators", "https://github.com/your-repo#translations")

        right_layout.addWidget(btn1)
        right_layout.addWidget(btn2)
        right_layout.addWidget(btn3)

        # === Compose Main Layout ===
        main_layout.addLayout(left_layout, 2)
        main_layout.addWidget(divider)
        main_layout.addLayout(right_layout, 3)
