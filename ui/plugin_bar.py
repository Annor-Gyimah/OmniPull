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


import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
from PySide6.QtWidgets import (
    QPushButton, QToolButton, QWidget, QHBoxLayout, QVBoxLayout,
    QDialog, QLabel
)



class PluginIconButton(QToolButton):
    """Clickable icon button for a single plugin."""
    
    plugin_clicked = Signal(dict)  # Emits plugin metadata
    
    def __init__(self, plugin_info, parent=None):
        super().__init__(parent)
        self.plugin_info = plugin_info
        self.metadata = plugin_info.get("metadata", {})
        
        # Basic setup
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.setIconSize(QSize(32, 32))
        self.setFixedSize(40, 40)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        
        # Icon from metadata or default
        icon_str = self.metadata.get("icon", "🔌")
        self.setToolTip(self.metadata.get("name", "Plugin"))
        self._set_emoji_icon(icon_str)
        
        # Style
        self.setStyleSheet("""
            QToolButton {
                background: rgba(43, 128, 255, 0.1);
                border: 1px solid rgba(43, 128, 255, 0.3);
                border-radius: 6px;
                padding: 0px;
            }
            QToolButton:hover {
                background: rgba(43, 128, 255, 0.2);
                border-color: rgba(43, 128, 255, 0.6);
            }
            QToolButton:pressed {
                background: rgba(43, 128, 255, 0.3);
            }
        """)
        
        # Connect
        self.clicked.connect(self._on_click)
    
    def _set_emoji_icon(self, emoji: str):
        """Create an icon from an emoji string."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        font = QFont()
        font.setPixelSize(24)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, emoji)
        painter.end()
        
        self.setIcon(QIcon(pixmap))
    
    def _on_click(self):
        """Emit signal with plugin info when clicked."""
        self.plugin_clicked.emit(self.plugin_info)


class PluginBar:
    
    def __init__(self, container_layout, no_plugins_label, main_window=None):
        self.container = container_layout
        self.no_plugins_label = no_plugins_label
        self.main_window = main_window
        self.plugin_buttons = {}
    
    def refresh(self, plugin_manager=None):
        """
        Refresh the plugin bar from PluginManager.
        Must be called on the main Qt thread.
        """
        # Clear existing buttons (keep stretch at the end)
        while self.container.count() > 1:
            item = self.container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.plugin_buttons.clear()
        
        # Get plugins from manager
        if plugin_manager is None:
            try:
                from modules.plugin_manager import PluginManager
                from modules.utils import log
                plugin_manager = PluginManager.instance()
            except ImportError:
                try:
                    from modules.utils import log
                    log("Could not import PluginManager in refresh", log_level=2, context="PLUGIN-BAR")
                except:
                    print("[PLUGIN-BAR] Could not import PluginManager")
                self.no_plugins_label.show()
                return
        
        if not plugin_manager._initialized:
            try:
                from modules.utils import log
                log("PluginManager not initialized in refresh", log_level=1, context="PLUGIN-BAR")
            except:
                pass
            self.no_plugins_label.show()
            return
        
        plugins = plugin_manager.loaded_plugins
        
        try:
            from modules.utils import log
            log(f"Plugin bar refresh: found {len(plugins)} plugins: {list(plugins.keys())}", 
                log_level=1, context="PLUGIN-BAR")
        except:
            print(f"[PLUGIN-BAR] Found {len(plugins)} plugins: {list(plugins.keys())}")
        
        if not plugins:
            self.no_plugins_label.show()
            return
        
        # Hide the "no plugins" label
        self.no_plugins_label.hide()
        
        # Create buttons for each plugin (insert before stretch)
        for pid, pinfo in plugins.items():
            meta = getattr(pinfo.module, "__plugin_meta__", {})
            plugin_data = {
                "id": pid,
                "name": meta.get("name", pid),
                "version": meta.get("version", "0.0.1"),
                "icon": meta.get("icon", "🔌"),
                "metadata": meta,
                "module": pinfo.module,
            }
            
            btn = PluginIconButton(plugin_data, parent=None)
            btn.plugin_clicked.connect(lambda p, mw=self.main_window: 
                                      self._handle_plugin_click(p, mw))
            
            # Insert button before the stretch (which is always last)
            self.container.insertWidget(self.container.count() - 1, btn)
            self.plugin_buttons[pid] = btn
            
        try:
            from modules.utils import log
            log(f"Plugin bar: {len(self.plugin_buttons)} buttons created", context="PLUGIN-BAR")
        except:
            print(f"[PLUGIN-BAR] {len(self.plugin_buttons)} buttons created")
    
    @staticmethod
    def _handle_plugin_click(plugin_info: dict, main_window=None):
        """
        Handle plugin icon click.
        
        Priority:
        1. Call plugin's open_ui() method if available
        2. Open plugin_url if provided
        3. Show info dialog
        """
        module = plugin_info.get("module")
        
        # Try to call open_ui method
        if module and hasattr(module, "open_ui"):
            try:
                module.open_ui(parent=main_window)
                return
            except Exception as e:
                print(f"Error opening UI for {plugin_info['name']}: {e}")
        
        # Try to open plugin_url
        if "metadata" in plugin_info and "plugin_url" in plugin_info["metadata"]:
            try:
                webbrowser.open(plugin_info["metadata"]["plugin_url"])
                return
            except Exception as e:
                print(f"Error opening URL: {e}")
        
        # Fallback: show info dialog
        PluginBar._show_plugin_info(plugin_info, main_window)
    
    @staticmethod
    def _show_plugin_info(plugin_info: dict, parent=None):
        """Show a simple info dialog for the plugin."""
        dialog = QDialog(parent)
        dialog.setWindowTitle(plugin_info["name"])
        dialog.setMinimumSize(400, 250)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        # Header with icon
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        icon_label = QLabel(plugin_info["icon"])
        icon_label.setStyleSheet("font-size: 36px;")
        icon_label.setFixedSize(50, 50)
        
        title_layout = QVBoxLayout()
        name_label = QLabel(plugin_info["name"])
        name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        ver_label = QLabel(f"v{plugin_info['version']}")
        ver_label.setStyleSheet("font-size: 10px; color: #888;")
        title_layout.addWidget(name_label)
        title_layout.addWidget(ver_label)
        
        header_layout.addWidget(icon_label)
        header_layout.addLayout(title_layout, 1)
        layout.addWidget(header)
        
        # Description
        if "description" in plugin_info.get("metadata", {}):
            desc_label = QLabel(plugin_info["metadata"]["description"])
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #999; font-size: 11px;")
            layout.addWidget(desc_label)
        
        layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
