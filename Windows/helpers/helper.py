from modules import config
import os
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt



def change_cursor(cursor_type: str):
        """Change cursor to busy or normal."""
        if cursor_type == 'busy':
            QApplication.setOverrideCursor(Qt.WaitCursor)  # Busy cursor
        elif cursor_type == 'normal':
            QApplication.restoreOverrideCursor()  # Restore normal cursor


def show_information(title, inform, msg):
    information_box = QMessageBox()
    information_box.setStyleSheet(get_msgbox_style("information"))
    information_box.setText(msg)
    information_box.setWindowTitle(title)
    information_box.setInformativeText(inform)
    information_box.setIcon(QMessageBox.Information)
    information_box.setStandardButtons(QMessageBox.Ok)
    information_box.exec()
    return


def show_critical(title, msg):
    critical_box = QMessageBox()
    critical_box.setStyleSheet(get_msgbox_style("critical"))
    critical_box.setWindowTitle(title)
    critical_box.setText(msg)
    critical_box.setIcon(QMessageBox.Critical)
    critical_box.setStandardButtons(QMessageBox.Ok)
    critical_box.exec()

def show_warning(title, msg):
    warning_box = QMessageBox()
    warning_box.setStyleSheet(get_msgbox_style("warning"))
    warning_box.setWindowTitle(title)
    warning_box.setText(msg)
    warning_box.setIcon(QMessageBox.Warning)
    warning_box.setStandardButtons(QMessageBox.Ok)
    
    warning_box.exec()

def toolbar_buttons_state(status: str) -> dict:
        status_map = {
            config.Status.completed: {
                "Resume": False,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.cancelled: {
                "Resume": True,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.error: { 
                "Resume": True,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.paused: {
                "Resume": True,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },  
            config.Status.failed: {
                "Resume": True,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            }, 
            config.Status.deleted: {
                "Resume": False,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.scheduled: {
                "Resume": False,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.downloading: {
                "Resume": False,
                "Pause": True,
                "Delete": False,
                "Delete All": False,
                "Refresh": False,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": True,
            },
            config.Status.pending: {
                "Resume": False,
                "Pause": True,
                "Delete": False,
                "Delete All": False,
                "Refresh": False,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.merging_audio: {
                "Resume": False,
                "Pause": False,
                "Delete": False,
                "Delete All": False,
                "Refresh": False,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
        }

        return status_map.get(status, {})




def get_msgbox_style(msg_type: str) -> str:
        base_style = """
            QMessageBox {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                color: white;
                font-family: 'Segoe UI';
                font-size: 13px;
                border-radius: 12px;
            }
            QLabel {
                color: white;
            }
        """

        button_styles = {
            "critical": """
                QPushButton {
                    background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                    );
                    color: white;
                    padding: 6px 16px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #B71C1C;
                }
            """,
            "warning": """
                QPushButton {
                    background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                    );
                    color: white;
                    padding: 6px 16px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #FF8F00;
                }
            """,
            "information": """
                QPushButton {
                    background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                    );
                    color: white;
                    padding: 6px 16px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #00B248;
                }
            """,
            "inputdial": """

                QInputDialog {
                    background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                    );
                    color: white;
                    font-family: 'Segoe UI';
                    font-size: 13px;
                    border-radius: 12px;
                }
                QLabel {
                    color: white;
                }
                QLineEdit {
                    background-color: rgba(28, 28, 30, 0.55);  /* Neutral frosted charcoal */
                    color: #e0e0e0;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
                QPushButton {

                    background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                    ); 
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 16px;
                    font-weight: bold;
                
                }
                QPushButton:hover {
                    background-color: #00B248;
                }
                QComboBox, QSpinBox, QLineEdit {
                    background-color: rgba(28, 28, 30, 0.55);  /* Neutral frosted charcoal */
                    color: #e0e0e0;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 6px;
                    padding: 6px 10px;
                }

                QComboBox:hover, QSpinBox:hover, QLineEdit:hover {
                    border: 1px solid rgba(111, 255, 176, 0.18);  /* subtle emerald glow on hover */
                }

                QComboBox::drop-down {
                    border: none;
                    background-color: transparent;
                }
            """,
            "conflict": """
                QPushButton {
                    background-color: qlineargradient(
                        x1: 0, y1: 0, x2: 1, y2: 1,
                        stop: 0 #0F1B14,
                        stop: 1 #050708
                    );
                    color: white;
                    padding: 6px 16px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #1B5E20;
                }
            """,
            "overwrite": """
                QPushButton {
                    background-color: qlineargradient(
                        x1: 0, y1: 0, x2: 1, y2: 1,
                        stop: 0 #0F1B14,
                        stop: 1 #050708
                    );
                    color: white;
                    padding: 6px 16px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #C62828;  /* deep red on hover for overwrite alert */
                }
            """,
            "question": """
                QPushButton {

                    background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                    ); 
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 16px;
                    font-weight: bold;
                
                }
                QPushButton:hover {
                    background-color: #00B248;
                }


            """


        }

        return base_style + button_styles.get(msg_type, "")


