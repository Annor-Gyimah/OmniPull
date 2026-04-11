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





import resources_rc



from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QActionGroup, QFont, QAction, QIcon


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QPushButton, QLabel,
    QLineEdit, QComboBox, QToolBar, QStatusBar, QDockWidget, QListWidget,
    QListWidgetItem, QMenuBar, QMenu, QStackedWidget, QPlainTextEdit, 
    QAbstractItemView, QHeaderView, QStyledItemDelegate, QStyle, QStyleOptionViewItem
)



class NoFocusDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # Create a copy of the option to avoid modifying the original
        item_option = QStyleOptionViewItem(option)
        
        # Explicitly remove the Focus state
        if item_option.state & QStyle.State_HasFocus:
            item_option.state &= ~QStyle.State_HasFocus
            
        # Draw the item using the modified option
        super().paint(painter, item_option, index)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setWindowTitle("Download Manager")

        MainWindow.resize(1100, 650)
        MainWindow.setMinimumSize(900, 550)

        self.central = QWidget(MainWindow)
        MainWindow.setCentralWidget(self.central)

        self.main_layout = QVBoxLayout(self.central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        menu_bar = QMenuBar(MainWindow)  
        MainWindow.setMenuBar(menu_bar)  
        
        self.file_menu = QMenu("&File", menu_bar)
        self.add_action = QAction(QIcon(":/icons/add.png"), "Add new download", self.file_menu)
        self.open_file_menu = QMenu("Open", self.file_menu)
        self.open_file_menu.setIcon(QIcon(":/icons/cil-file.png"))
        self.file_menu.addMenu(self.open_file_menu)
        self.open_file_menu.addAction("")
        self.exit_action = QAction(QIcon(":/icons/exit.svg"), "Exit", self.file_menu)
        self.file_menu.addAction(self.add_action)
        self.file_menu.addAction(self.exit_action)

        self.downloads_menu = QMenu("&Downloads", menu_bar)
        self.resume_all_action = QAction(QIcon(":/icons/resume_all.png"),"Resume All", self.downloads_menu)
        self.stop_all_action = QAction(QIcon(":/icons/stop_all.svg"), "Stop All", self.downloads_menu)
        self.delete_all_action = QAction(QIcon(":/icons/multi_trash.svg"), "Delete All", self.downloads_menu)
        self.downloads_menu.addActions([self.resume_all_action, self.stop_all_action, self.delete_all_action])

        self.view_menu = QMenu("&View", menu_bar)
        self.theme_menu = QMenu("Theme", self.view_menu)
        self.theme_menu.setIcon(QIcon(":/icons/themes.png"))
        self.action_theme_dark = QAction("Dark", self.theme_menu, checkable=True)
        self.action_theme_light = QAction("Light", self.theme_menu, checkable=True)
        theme_group = QActionGroup(self.theme_menu)
        theme_group.addAction(self.action_theme_dark)
        theme_group.addAction(self.action_theme_light)
        self.action_theme_dark.setChecked(True)  # default

        self.theme_menu.addAction(self.action_theme_dark)
        self.theme_menu.addAction(self.action_theme_light)
        self.view_menu.addMenu(self.theme_menu)

        self.tools_menu = QMenu("&Tools", menu_bar)
        self.scheduler_action = QAction(QIcon(":/icons/schedule.svg"), "Scheduler", self.tools_menu)
        self.settings_action = QAction(QIcon(":/icons/settings.png"), "Settings", self.tools_menu)
        self.queue_action = QAction(QIcon(":/icons/queues.png"),"Queues", self.tools_menu)
        self.category_action = QAction(QIcon(":/icons/categories.png"), "Categories", self.tools_menu)
        self.install_ytdlp_action = QAction(QIcon(":/icons/yt_dlp.svg"), "Install yt-dlp", self.tools_menu)
        self.install_deno_action = QAction(QIcon(":/icons/deno.svg"), "Install deno", self.tools_menu)
        self.install_ffmpeg_action = QAction(QIcon(":/icons/ffmpeg.svg"), "Install ffmpeg", self.tools_menu)
        self.marketplace_action = QAction(QIcon(":/icons/marketplace.png"), "Marketplace", self.tools_menu)
        self.tools_menu.addActions([self.scheduler_action, self.settings_action, self.queue_action, self.category_action, 
            self.install_ytdlp_action, self.install_deno_action, self.install_ffmpeg_action, self.marketplace_action])

        self.help_menu = QMenu("&Help", menu_bar)
        self.about_action = QAction(QIcon(":/icons/about.png"), "About", self.help_menu)
        self.tutorials_action = QAction(QIcon(":/icons/help.png"), "Help", self.help_menu)
        self.check_for_updates_action = QAction(QIcon(":/icons/check_updates.png"),"Check for Updates", self.help_menu)
        self.whats_new_action = QAction(QIcon(":/icons/sparkling.png"), "WhatsNew", self.help_menu)
        self.report_issue_action = QAction(QIcon(":/icons/report_issue.png"), "Report an Issue", self.help_menu)

        self.browser_ext_menu = QMenu("Browser Extensions", self.help_menu)
        self.browser_ext_menu.setIcon(QIcon(":/icons/internet-web-browser.svg"))
        self.browser_ext_chrome_action = QAction(QIcon(":/icons/google-chrome.svg"),"Chrome Extension", self.browser_ext_menu)
        self.browser_ext_firefox_action = QAction(QIcon(":/icons/firefox.svg"),"Firefox Add-on", self.browser_ext_menu)
        self.browser_ext_edge_action = QAction(QIcon(":/icons/microsoft-edge.svg"), "Edge Extension", self.browser_ext_menu)
        self.browser_ext_menu.setStyleSheet("""

            QMenu::item {
                padding: 6px 20px;
            }

            QMenu::item:disabled {
                color: #6A6A6A;           
            }

            QMenu::item:disabled:selected {
                background-color: transparent;
            }
        """)
        self.browser_ext_menu.addActions([self.browser_ext_chrome_action, self.browser_ext_firefox_action, self.browser_ext_edge_action])
        self.help_menu.addMenu(self.browser_ext_menu)

        self.help_menu.addActions([self.about_action, self.tutorials_action, self.check_for_updates_action, self.report_issue_action, self.whats_new_action])

        menu_bar.addMenu(self.file_menu)
        menu_bar.addMenu(self.downloads_menu)
        menu_bar.addMenu(self.view_menu)
        menu_bar.addMenu(self.tools_menu)
        menu_bar.addMenu(self.help_menu)

        # Toolbar
        toolbar = QToolBar("Main Toolbar", MainWindow)
        toolbar.setIconSize(QSize(25, 25))
        toolbar.setMovable(False)
        MainWindow.addToolBar(Qt.TopToolBarArea, toolbar)

        self.btn_add = QAction(QIcon(":/icons/add.png"),"Add", toolbar)
        self.btn_resume = QAction(QIcon(":/icons/play.svg"), "Resume", toolbar)
        self.btn_pause = QAction(QIcon(":/icons/pause.svg"), "Pause", toolbar)
        self.btn_stop_all = QAction(QIcon(":/icons/stop_all.svg"), "Stop All", toolbar)
        self.btn_delete = QAction(QIcon(":/icons/trash.svg"), "Delete", toolbar)
        self.btn_delete_all = QAction(QIcon(":/icons/multi_trash.svg"), "Delete All", toolbar)
        self.btn_scheduler = QAction(QIcon(":/icons/schedule.svg"), "Scheduler", toolbar)
        self.btn_refresh = QAction(QIcon(":/icons/refresh.png"), "Refresh", toolbar)
        self.btn_terminal = QAction(QIcon(":/icons/terminal.png"), "Terminal", toolbar)
        self.btn_resume_all = QAction(QIcon(":/icons/resume_all.png"), "Resume All", toolbar)
        self.btn_settings = QAction(QIcon(":/icons/settings.png"),"Settings", toolbar)
        self.btn_terminal.setCheckable(True)
        # self.btn_whatsnew = QAction("What's New",  toolbar)

        toolbar.addAction(self.btn_add)
        toolbar.addAction(self.btn_resume)
        toolbar.addAction(self.btn_pause)
        toolbar.addAction(self.btn_stop_all)
        toolbar.addAction(self.btn_delete_all)
        toolbar.addAction(self.btn_scheduler)
        toolbar.addAction(self.btn_refresh)
        toolbar.addAction(self.btn_resume_all)
        toolbar.addAction(self.btn_settings)
        toolbar.addAction(self.btn_terminal)
        
        

        toolbar.addSeparator()
        self.search_label = QLabel("  Search: ")
        toolbar.addWidget(self.search_label)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Search downloads...")
        self.filter_edit.setMaximumWidth(220)
        toolbar.addWidget(self.filter_edit)
        toolbar.addSeparator()
        

        
        # Side panel with categories + small card

        self.dock = QDockWidget("Categories", MainWindow)
        self.dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.dock.setMinimumWidth(180)

        side_widget = QWidget()
        vlayout = QVBoxLayout(side_widget)
        vlayout.setContentsMargins(8, 8, 8, 8)
        vlayout.setSpacing(10)

        self.category_list = QListWidget()
        self.category_list.setSpacing(4)
        for text in [
            "All Downloads",
            "Completed",
            "Cancelled",
            "Downloading",
            "Queued",
            "Paused",
            "Error",
            "General",
            "Compressed",
            "Documents",
            "Music",
            "Video",
            "Programs",
        ]:
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, text)
            self.category_list.addItem(item)

        self.category_list.setCurrentRow(0)
        self.category_list.setItemDelegate(NoFocusDelegate())
        


        
        vlayout.addWidget(self.category_list)

        # Small info card at bottom
        info_card = QWidget()
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(10, 10, 10, 10)
        info_layout.setSpacing(6)
        self.lbl_title = QLabel("Today")
        self.lbl_title.setObjectName("InfoTitle")
        self.lbl_summary = QLabel("downloads\n completed")
        self.lbl_summary.setObjectName("InfoBody")
        info_layout.addWidget(self.lbl_title)
        info_layout.addWidget(self.lbl_summary)
        info_layout.addStretch()

        vlayout.addWidget(info_card)

        self.dock.setWidget(side_widget)
        MainWindow.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

    
        self.stack = QStackedWidget()
        

        
        downloads_page = QWidget()
        layout = QVBoxLayout(downloads_page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        self.title_label = QLabel("Downloads")
        self.title_label.setObjectName("PageTitle")
        header_row.addWidget(self.title_label)
        header_row.addStretch()
        self.sort_by = QLabel("Sort by:")
        header_row.addWidget(self.sort_by)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Time", "Name", "Status", "Size"])
        header_row.addWidget(self.sort_combo)
        layout.addLayout(header_row)

        self.table = QTableWidget(0, 8)
        self.table.setObjectName("DownloadsTable")
        headers = ["ID", "Name", "Progress", "Speed", "ETA", "Done", "Size", "Status", "I", "Last Try Date"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)

        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultSectionSize(150)
        self.table.verticalHeader().setDefaultSectionSize(36)  
        
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)


        layout.addWidget(self.table)
        QTimer.singleShot(0, self._finalize_table_layout)

        # --- Terminal page ---
        terminal_page = QWidget()
        t_layout = QVBoxLayout(terminal_page)
        t_layout.setContentsMargins(8, 8, 8, 8)
        t_layout.setSpacing(8)

        t_header = QHBoxLayout()
        self.t_label = QLabel("Terminal")
        self.t_label.setObjectName("PageTitle")
        t_header.addWidget(self.t_label)
        # t_header.addStretch()
        self.log_clear_btn = QPushButton("Clear")
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["1", "2", "3", "4"])
        t_header.addStretch()
        t_header.addWidget(self.log_clear_btn)
        self.log_level_label = QLabel("Log Level:")
        t_header.addWidget(self.log_level_label)
        t_header.addWidget(self.log_level_combo)
        t_layout.addLayout(t_header)

        self.terminal_output = QPlainTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setPlaceholderText("Terminal output will appear here...")
        font = QFont("")
        font.setStyleHint(QFont.Monospace)
        self.terminal_output.setFont(font)

        self.terminal_input = TerminalInput()
        self.terminal_input.setPlaceholderText("Enter command here... You can start with helpful commands like 'help' or 'yt-dlp --help'.")
        
        t_layout.addWidget(self.terminal_output)
        t_layout.addWidget(self.terminal_input)

        # Add both pages to stack
        self.stack.addWidget(downloads_page)
        self.stack.addWidget(terminal_page)

        self.downloads_page = downloads_page
        self.terminal_page = terminal_page

        MainWindow.setCentralWidget(self.stack)

        status = QStatusBar()
        MainWindow.setStatusBar(status)

        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(8, 0, 8, 0)
        status_layout.setSpacing(16)

        self.lbl_brand = QLabel("Annorion - Never Cease To Amaze")
        self.lbl_http_status = QLabel("—")
        self.lbl_speed_icon = QLabel()
        self.lbl_speed_icon.setPixmap(
            QIcon(":/icons/speed.png").pixmap(16, 16)
        )
        self.lbl_speed_icon.setAlignment(Qt.AlignCenter)
        self.lbl_speed_icon.setToolTip("Current total download speed")
        self.lbl_speed = QLabel("↓ 0 B/s")
        self.lbl_version = QLabel("v1.0.0")
        self.lbl_version.setStyleSheet("""
            color: #4CAF50;
            font-weight: bold;
            padding: 5px 10px;
            border-radius: 10px;
            background: rgba(76, 175, 80, 0.1);
        """)

        self.lbl_brand.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lbl_http_status.setAlignment(Qt.AlignCenter)
        self.lbl_speed.setAlignment(Qt.AlignCenter)
        self.lbl_version.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lbl_http_status.setToolTip("Last HTTP response status")
        self.lbl_speed.setToolTip("Current total download speed")

        speed_layout = QHBoxLayout()
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.setSpacing(6)
        speed_layout.addWidget(self.lbl_speed_icon)
        speed_layout.addWidget(self.lbl_speed)

        speed_widget = QWidget()
        speed_widget.setLayout(speed_layout)




        status_layout.addWidget(self.lbl_brand)
        status_layout.addStretch()
        status_layout.addWidget(self.lbl_http_status)
        status_layout.addStretch()
        status_layout.addWidget(speed_widget)
        status_layout.addStretch()
        status_layout.addWidget(self.lbl_version)

        status.addWidget(status_container, 1)

    
        self.table.setRowCount(0)
        self.lbl_summary.setText("0 downloads\n0 completed")

    
    def _finalize_table_layout(self):
        header = self.table.horizontalHeader()

        
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # ID
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Name
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Progress widget
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # Speed
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # ETA
        header.setSectionResizeMode(5, QHeaderView.Fixed)  # Done
        header.setSectionResizeMode(6, QHeaderView.Fixed)  # Size
        header.setSectionResizeMode(7, QHeaderView.Fixed)  # Status
        header.setSectionResizeMode(8, QHeaderView.Fixed)  # I (icon/notes)


        
        self.table.setColumnWidth(0, 48)   # ID
        self.table.setColumnWidth(2, 120)  # Progress
        self.table.setColumnWidth(3, 90)   # Speed
        self.table.setColumnWidth(4, 90)   # ETA
        self.table.setColumnWidth(5, 80)   # Done
        self.table.setColumnWidth(6, 90)   # Size
        self.table.setColumnWidth(8, 90)   # I

        self.table.setStyleSheet("""
            QTableWidget {
                outline: 0;
            }
            QTableWidget::item:selected {
                /* This ensures no border is drawn on the individual cells when the row is selected */
                border: 0px;
                background-color: #7C4DFF;
                color: #FFFFFF; /* Ensures text is always readable */
            }
        """)

        self.table.setFocusPolicy(Qt.NoFocus)

        self.table.setItemDelegate(NoFocusDelegate())


class TerminalInput(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.history_index = -1

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            if self.history:
                self.history_index = max(0, self.history_index - 1)
                self.setText(self.history[self.history_index])
            return

        if event.key() == Qt.Key_Down:
            if self.history:
                self.history_index = min(len(self.history) - 1, self.history_index + 1)
                self.setText(self.history[self.history_index])
            return
        

        super().keyPressEvent(event)


        