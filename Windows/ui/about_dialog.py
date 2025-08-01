from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QGraphicsBlurEffect, QWidget, QSizePolicy,
)
from PySide6.QtGui import QPixmap, QCursor, QIcon
from PySide6.QtCore import Qt, QSize
import webbrowser
import os
from modules import config
import resources_rc

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {config.APP_NAME}")
        self.setFixedSize(650, 360)
        # self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

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
        pix = QPixmap(":/icons/logo1.png").scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo.setPixmap(pix)
        logo.setAlignment(Qt.AlignCenter)

        title = QLabel(f"{config.APP_NAME}")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)

        version = QLabel(F"{config.APP_VERSION}")
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
        right_layout.setSpacing(10)
        right_layout.setAlignment(Qt.AlignTop)

        # Main Labels (Styled like informative lines)
        label1 = QLabel("OmniPull")
        label1.setObjectName("Title")

        label2 = QLabel("ODM is a python open source Internet Download Manager with multi-connections,\nhigh speed engine, it downloads general files and videos from YouTube\nand tons of other streaming websites.")
        label2.setWordWrap(True)

        label3 = QLabel("GPL v3 License")
        label4 = QLabel("Created by: Emmanuel Gyimah Annor")
        label5 = QLabel("Inspiration")
        label6 = QLabel("PyIDM - by Mahmoud Elshahat")

        # Icon bar (5 icons)
        icon_bar = QHBoxLayout()
        icon_bar.setSpacing(12)

        icon_list = {}

        icon_map = {
            "github": ":/icons/github.svg",
            "telegram": "icons/telegram.png",
            "browser": ":/icons/internet-web-browser.svg",

        }

        # for icon in icon_map.values():
        #     btn = QPushButton()
        #     btn.setFixedSize(34, 34)
        #     btn.setIcon(QIcon(icon))
        #     btn.setIconSize(QSize(24, 24))
        #     btn.setStyleSheet("""
        #         QPushButton {
        #             background-color: transparent;
        #             border: none;
        #         }
        #         QPushButton:hover {
        #             background-color: rgba(0, 255, 180, 0.1);
        #             border-radius: 6px;
        #         }
        #     """)
        #     icon_bar.addWidget(btn)

        for label, icon in icon_map.items():
            btn = QPushButton()
            btn.setFixedSize(34, 34)
            btn.setIcon(QIcon(icon))
            btn.setIconSize(QSize(24, 24))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background-color: rgba(0, 255, 180, 0.1);
                    border-radius: 6px;
                }
            """)
            # if os.path.exists(icon):
            #     btn.setIcon(QIcon(icon))
            icon_list[label] = btn
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            if label == "github":
                btn.clicked.connect(lambda: webbrowser.open("https://github.com/Annor-Gyimah/OmniPull"))
            elif label == "telegram":
                btn.clicked.connect(lambda: webbrowser.open("https://t.me/your_channel"))
            elif label == "browser":
                btn.clicked.connect(lambda: webbrowser.open("https://pyiconicdownloader.com"))
            icon_bar.addWidget(btn)

        # Add widgets to layout
        right_layout.addWidget(label1)
        right_layout.addWidget(label2)
        right_layout.addSpacing(6)
        right_layout.addWidget(label3)
        right_layout.addWidget(label4)
        right_layout.addWidget(label5)
        right_layout.addWidget(label6)
        right_layout.addStretch()
        right_layout.addLayout(icon_bar)


        # === Compose Main Layout ===
        # Container wrappers for control over layout behavior
        left_container = QWidget()
        left_container.setLayout(left_layout)
        left_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_container.setMinimumWidth(260)  # Keeps left compact

        right_container = QWidget()
        right_container.setLayout(right_layout)
        right_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Add to main layout with stretch ratios
        main_layout.addWidget(left_container, 2)
        main_layout.addWidget(divider)
        main_layout.addWidget(right_container, 4)

