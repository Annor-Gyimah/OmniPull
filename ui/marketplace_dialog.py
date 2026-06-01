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

import io
import time
import shutil
import traceback
import zipfile
from pathlib import Path



from modules.config import lang

from PySide6.QtCore import Qt, Signal, QThread, QCoreApplication, QTranslator
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QProgressBar, QLineEdit,
    QGraphicsDropShadowEffect, QSizePolicy, QStackedWidget,
    QMessageBox,
)

try:
    import requests
except ImportError:
    requests = None

try:
    from modules.plugin_manager import PluginManager
except ImportError:
    try:
        from modules.plugin_manager import PluginManager
    except ImportError:
        PluginManager = None

try:
    from modules.utils import log
except ImportError:
    def log(msg, log_level=1, context="MARKETPLACE"):
        print(f"[{context}] {msg}")

from ui.language_manager import LanguageManager


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDED PLUGIN SOURCES
#
# The complete plugin.py text for every plugin whose download_url is
# "__bundled__" lives here.  That way install works regardless of where
# marketplace_dialog.py or the app's plugins/ folder are located on disk.
#
# To add a new bundled plugin:  add one more key to _BUNDLED_SOURCES.
# ─────────────────────────────────────────────────────────────────────────────



# ── Manifest ──────────────────────────────────────────────────────────────────
MANIFEST_URL = "https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/dev/plugin_server/manifest.json"
# MANIFEST_URL = "http://localhost/lite/plugin_server/manifest.json"




# ── Worker threads ────────────────────────────────────────────────────────────

class ManifestFetcher(QThread):
    """Downloads and parses the marketplace manifest JSON."""
    ready = Signal(list)
    error = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            if requests is None:
                raise ImportError("requests not installed")
            resp = requests.get(self.url, timeout=6)
            resp.raise_for_status()
            self.ready.emit(resp.json())
        except Exception:
            log("Network unavailable — using bundled manifest.", context="MARKETPLACE")
            # self.ready.emit(BUNDLED_MANIFEST)


class PluginInstaller(QThread):
    """
    Writes the real plugin source to disk, then hot-loads it via PluginManager.

    For __bundled__ plugins the source is taken from _BUNDLED_SOURCES so the
    installer works independently of the app's directory layout.

    Hot-load sequence:
      1. Unload any stale module with the same name (handles reinstall).
      2. Call PluginManager._load_file_plugin() on the freshly written file.
    """
    progress = Signal(int)       # 0–100
    success  = Signal(str)       # plugin_id
    error    = Signal(str, str)  # plugin_id, message

    def __init__(self, plugin_id: str, download_url: str, plugins_dir: Path):
        super().__init__()
        self.plugin_id    = plugin_id
        self.download_url = download_url
        self.plugins_dir  = plugins_dir

    def run(self):
        pid = self.plugin_id
        try:
            dest = self.plugins_dir / pid
            dest.mkdir(parents=True, exist_ok=True)

            # if self.download_url == "__bundled__":
            #     self._write_bundled(dest)
            # elif self.download_url == "__coming_soon__":
            #     raise RuntimeError("This plugin is not yet available for download.")
            # else:
            self._download_and_extract(dest)

            self._hot_load(dest, pid)
            self.success.emit(pid)

        except Exception as exc:
            log(f"Install failed for '{pid}': {exc}", log_level=3, context="MARKETPLACE")
            log(traceback.format_exc(), log_level=4, context="MARKETPLACE")
            self.error.emit(pid, str(exc))
        finally:
            # Allow Qt event loop to process signals before thread exits
            self.msleep(50)

    # ── helpers ──────────────────────────────────────────────────────────────

    # def _write_bundled(self, dest: Path):
    #     """Write plugin.py from the embedded source — no stub, no filesystem search."""
    #     source = _BUNDLED_SOURCES.get(self.plugin_id)
    #     if not source:
    #         raise RuntimeError(
    #             f"No embedded source for plugin '{self.plugin_id}'. "
    #             "Add it to _BUNDLED_SOURCES in marketplace_dialog.py."
    #         )
    #     plugin_file = dest / "plugin.py"
    #     plugin_file.write_text(source.strip(), encoding="utf-8")
    #     log(
    #         f"Wrote {len(source)} chars → {plugin_file}",
    #         context="MARKETPLACE",
    #     )
    #     self.progress.emit(100)

    def _download_and_extract(self, dest: Path):
        if requests is None:
            raise ImportError("'requests' is not installed.")
        with requests.get(self.download_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total      = int(r.headers.get("content-length", 0))
            downloaded = 0
            buf        = io.BytesIO()
            for chunk in r.iter_content(chunk_size=8192):
                buf.write(chunk)
                downloaded += len(chunk)
                if total:
                    self.progress.emit(int(downloaded * 100 / total))
        buf.seek(0)
        with zipfile.ZipFile(buf) as zf:
            zf.extractall(dest)
        self.progress.emit(100)

    def _hot_load(self, dest: Path, pid: str):
        """
        Unload any stale version, then import the freshly written plugin.py.
        This ensures the new source (not a cached stub module) is executed.
        """
        if PluginManager is None:
            log("PluginManager unavailable — plugin loads on next restart.",
                log_level=2, context="MARKETPLACE")
            return

        mgr = PluginManager.instance()
        if not getattr(mgr, "_initialized", False):
            log("PluginManager not initialised yet — plugin loads on next restart.",
                log_level=2, context="MARKETPLACE")
            return

        # Flush any previous version (stub or older install) from sys.modules
        # AFTER
        if pid in mgr._plugins:
            log(f"Unloading previous '{pid}' module before hot-reload.", context="MARKETPLACE")
            mgr.unload(pid)
            # Poll for port release (up to 4s) before reimporting
            import socket as _socket
            for _ in range(20):
                time.sleep(0.2)
                try:
                    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                    s.bind(("0.0.0.0", 7432))
                    s.close()
                    break
                except OSError:
                    pass

        entry = dest / "plugin.py"
        if entry.exists():
            info = mgr._load_file_plugin(entry, package_name=pid)
            if info:
                log(f"Hot-loaded: {info}", context="MARKETPLACE")
            else:
                log(f"_load_file_plugin returned None for '{pid}'.", log_level=2,
                    context="MARKETPLACE")
        else:
            log(f"plugin.py missing at {entry} — cannot hot-load.", log_level=3,
                context="MARKETPLACE")


# ── Plugin card widget ────────────────────────────────────────────────────────

class PluginCard(QFrame):
    install_requested   = Signal(dict)
    uninstall_requested = Signal(str)

    def __init__(self, meta: dict, is_installed: bool = False, parent=None):
        super().__init__(parent)
        self.meta       = meta
        self.pid        = meta["id"]
        self._installed = is_installed

        self.setObjectName("PluginCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(148)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

        self._build_ui()
        self._apply_card_style()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(16)

        # Icon
        icon_lbl = QLabel(self.meta.get("icon", "🔌"))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedSize(52, 52)
        icon_lbl.setStyleSheet(
            "QLabel{font-size:28px;background:rgba(43,128,255,0.15);border-radius:12px;}"
        )
        root.addWidget(icon_lbl, 0, Qt.AlignTop)

        # Text
        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        header = QHBoxLayout()
        name_lbl = QLabel(f"<b>{self.meta['name']}</b>")
        name_lbl.setStyleSheet("font-size:14px;color:#e8eaed;")
        ver_lbl = QLabel(f"v{self.meta.get('version','?')}")
        ver_lbl.setStyleSheet(
            "font-size:10px;color:#9aa0a6;padding:2px 7px;"
            "background:rgba(255,255,255,0.07);border-radius:8px;"
        )
        author_lbl = QLabel(f"by {self.meta.get('author','Unknown')}")
        author_lbl.setStyleSheet("font-size:10px;color:#5f6368;")
        header.addWidget(name_lbl)
        header.addWidget(ver_lbl)
        header.addWidget(author_lbl)
        header.addStretch()
        size_lbl = QLabel(self.meta.get("size", ""))
        size_lbl.setStyleSheet("font-size:10px;color:#5f6368;")
        header.addWidget(size_lbl)
        text_col.addLayout(header)

        desc_lbl = QLabel(self.meta.get("description", ""))
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size:12px;color:#9aa0a6;line-height:150%;")
        text_col.addWidget(desc_lbl)

        tags_row = QHBoxLayout()
        tags_row.setSpacing(6)
        for tag in self.meta.get("tags", [])[:4]:
            t = QLabel(f"#{tag}")
            t.setStyleSheet(
                "font-size:10px;color:#2b80ff;padding:1px 6px;"
                "background:rgba(43,128,255,0.12);border-radius:6px;"
            )
            tags_row.addWidget(t)
        tags_row.addStretch()
        text_col.addLayout(tags_row)
        root.addLayout(text_col, 1)

        # Button column
        btn_col = QVBoxLayout()
        btn_col.setSpacing(8)
        btn_col.setAlignment(Qt.AlignVCenter)

        self.action_btn = QPushButton()
        self.action_btn.setFixedWidth(110)
        self.action_btn.setFixedHeight(34)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_button_state()
        self.action_btn.clicked.connect(self._on_action)
        btn_col.addWidget(self.action_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(110)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.hide()
        self.progress_bar.setStyleSheet(
            "QProgressBar{background:#1f2227;border-radius:3px;}"
            "QProgressBar::chunk{background:#2b80ff;border-radius:3px;}"
        )
        btn_col.addWidget(self.progress_bar)
        root.addLayout(btn_col)

    def _refresh_button_state(self):
        coming = self.meta.get("download_url") == "__coming_soon__"
        if coming:
            self.action_btn.setText("Coming Soon")
            self.action_btn.setEnabled(False)
            self.action_btn.setStyleSheet(self._btn_style(disabled=True))
        elif self._installed:
            self.action_btn.setText("✓ Installed")
            self.action_btn.setEnabled(True)
            self.action_btn.setStyleSheet(self._btn_style(installed=True))
        else:
            self.action_btn.setText("Install")
            self.action_btn.setEnabled(True)
            self.action_btn.setStyleSheet(self._btn_style())

    def _btn_style(self, installed=False, disabled=False) -> str:
        if disabled:
            return ("QPushButton{background:#2a2d35;color:#5f6368;"
                    "border:1px solid #3c4043;border-radius:8px;font-size:12px;}")
        if installed:
            return ("QPushButton{background:rgba(0,180,80,0.15);color:#00c853;"
                    "border:1px solid #00c853;border-radius:8px;font-size:12px;}"
                    "QPushButton:hover{background:rgba(200,0,0,0.15);color:#f44336;"
                    "border-color:#f44336;}")
        return ("QPushButton{background:#2b80ff;color:#fff;"
                "border:none;border-radius:8px;font-size:12px;font-weight:600;}"
                "QPushButton:hover{background:#1a6fe8;}"
                "QPushButton:pressed{background:#1260d4;}")

    def _on_action(self):
        if self._installed:
            self.uninstall_requested.emit(self.pid)
        else:
            self.install_requested.emit(self.meta)

    def set_installing(self, progress: int):
        self.action_btn.setText("Installing…")
        self.action_btn.setEnabled(False)
        self.action_btn.setStyleSheet(self._btn_style(disabled=True))
        self.progress_bar.setValue(progress)
        self.progress_bar.show()

    def set_installed(self):
        self._installed = True
        self.progress_bar.hide()
        self._refresh_button_state()

    def set_error(self):
        self.action_btn.setText("Retry")
        self.action_btn.setEnabled(True)
        self.action_btn.setStyleSheet(
            "QPushButton{background:rgba(244,67,54,0.15);color:#f44336;"
            "border:1px solid #f44336;border-radius:8px;font-size:12px;}"
        )
        self.progress_bar.hide()

    def _apply_card_style(self):
        self.setStyleSheet("""
            QFrame#PluginCard{background:#1f2227;border:1px solid #2d3139;border-radius:14px;}
            QFrame#PluginCard:hover{border-color:#3a3f4a;background:#22252c;}
        """)


# ── Main dialog ───────────────────────────────────────────────────────────────

class MarketplaceDialog(QDialog):
    """
    Full-featured plugin marketplace dialog.
    Open with:
        MarketplaceDialog(parent=self, plugins_dir=str(config.DATA_ROOT / "plugins")).exec()
    """

    def __init__(self, parent=None, plugins_dir: str = "plugins"):
        super().__init__(parent)
        self.plugins_dir = Path(plugins_dir).resolve()
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        self._cards:    dict[str, PluginCard]      = {}
        self._workers:  dict[str, PluginInstaller] = {}
        self._manifest: list[dict]                 = []

        self.setWindowTitle(self.tr("OmniPull Marketplace"))
        self.setMinimumSize(780, 580)
        self.setModal(True)
        self._apply_global_style()
        self._build_ui()
        self._fetch_manifest()
        self.apply_language_market(lang)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(72)
        header.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #141720,stop:1 #1a1e27);"
            "border-bottom:1px solid #2d3139;"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)
        logo = QLabel("🛒")
        logo.setStyleSheet("font-size:28px;")
        self.title    = QLabel(self.tr("Plugin Marketplace"))
        self.title.setStyleSheet("font-size:20px;font-weight:700;color:#e8eaed;letter-spacing:-0.5px;")
        self.subtitle = QLabel(self.tr("Extend OmniPull with community plugins"))
        self.subtitle.setStyleSheet("font-size:12px;color:#5f6368;")
        tc = QVBoxLayout()
        tc.setSpacing(1)
        tc.addWidget(self.title)
        tc.addWidget(self.subtitle)
        hl.addWidget(logo)
        hl.addSpacing(10)
        hl.addLayout(tc)
        hl.addStretch()
        self.refresh_btn = QPushButton(self.tr("Refresh"))
        self.refresh_btn.setFixedHeight(32)
        self.refresh_btn.setStyleSheet("""
            QPushButton{background:rgba(255,255,255,0.06);color:#9aa0a6;
                border:1px solid #3c4043;border-radius:8px;font-size:12px;padding:0 14px;}
            QPushButton:hover{background:rgba(255,255,255,0.10);color:#e8eaed;}
        """)
        self.refresh_btn.clicked.connect(self._fetch_manifest)
        hl.addWidget(self.refresh_btn)
        root.addWidget(header)

        # Search
        sb = QWidget()
        sb.setFixedHeight(52)
        sb.setStyleSheet("background:#14161a;border-bottom:1px solid #232730;")
        sl = QHBoxLayout(sb)
        sl.setContentsMargins(24, 0, 24, 0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(self.tr("Search plugins…"))
        self.search_edit.setStyleSheet("""
            QLineEdit{background:#1f2227;color:#e8eaed;border:1px solid #2d3139;
                border-radius:8px;padding:6px 12px;font-size:13px;}
            QLineEdit:focus{border-color:#2b80ff;}
        """)
        self.search_edit.textChanged.connect(self._filter_cards)
        sl.addWidget(self.search_edit)
        self.count_lbl = QLabel()
        self.count_lbl.setStyleSheet("font-size:11px;color:#5f6368;padding-left:12px;")
        sl.addWidget(self.count_lbl)
        root.addWidget(sb)

        # Stack
        self.stack = QStackedWidget()

        # 0 — loading
        lp = QWidget()
        lpl = QVBoxLayout(lp)
        lpl.setAlignment(Qt.AlignCenter)
        spin = QLabel(self.tr("Fetching plugin registry…"))
        spin.setStyleSheet("font-size:14px;color:#5f6368;")
        lpl.addWidget(spin, 0, Qt.AlignCenter)
        self.stack.addWidget(lp)

        # 1 — list
        list_page = QWidget()
        list_page.setStyleSheet("background:#14161a;")
        lp2 = QVBoxLayout(list_page)
        lp2.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("background:#14161a;")
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cards_widget = QWidget()
        self.cards_widget.setStyleSheet("background:#14161a;")
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(20, 16, 20, 20)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch()
        self.scroll.setWidget(self.cards_widget)
        lp2.addWidget(self.scroll)
        self.stack.addWidget(list_page)

        # 2 — error
        ep = QWidget()
        epl = QVBoxLayout(ep)
        epl.setAlignment(Qt.AlignCenter)
        self.error_lbl = QLabel()
        self.error_lbl.setStyleSheet("font-size:13px;color:#f44336;")
        self.error_lbl.setWordWrap(True)
        epl.addWidget(self.error_lbl, 0, Qt.AlignCenter)
        self.stack.addWidget(ep)

        root.addWidget(self.stack, 1)

        # Footer
        footer = QWidget()
        footer.setFixedHeight(48)
        footer.setStyleSheet("background:#0f1014;border-top:1px solid #1f2227;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)
        self.status_lbl = QLabel(self.tr("Ready"))
        self.status_lbl.setStyleSheet("font-size:11px;color:#5f6368;")
        fl.addWidget(self.status_lbl)
        fl.addStretch()
        self.close_btn = QPushButton(self.tr("Close"))
        self.close_btn.setFixedHeight(30)
        self.close_btn.setStyleSheet("""
            QPushButton{background:#2a2d35;color:#9aa0a6;border:1px solid #3c4043;
                border-radius:7px;padding:0 18px;font-size:12px;}
            QPushButton:hover{background:#33363f;color:#e8eaed;}
        """)
        self.close_btn.clicked.connect(self.accept)
        fl.addWidget(self.close_btn)
        root.addWidget(footer)

    # ── Manifest ─────────────────────────────────────────────────────────────
    def _fetch_manifest(self):
        self.stack.setCurrentIndex(0)
        self.refresh_btn.setEnabled(False)
        self.status_lbl.setText(self.tr("Fetching plugin registry…"))
        self._fetcher = ManifestFetcher(MANIFEST_URL)
        self._fetcher.ready.connect(self._on_manifest_ready)
        self._fetcher.error.connect(self._on_manifest_error)
        self._fetcher.start()

    def _on_manifest_ready(self, data: list):
        self._manifest = data
        self._render_cards(data)
        self.stack.setCurrentIndex(1)
        self.refresh_btn.setEnabled(True)
        self.len_of_data = str(len(data))
        self.status_lbl.setText(self.tr("%1 plugin(s) available").replace("%1", self.len_of_data))
        self.count_lbl.setText(self.tr(f"%1 plugins").replace("%1", self.len_of_data))
        

    def _on_manifest_error(self, msg: str):
        self.error_lbl.setText(f"Could not load registry:\n{msg}")
        self.stack.setCurrentIndex(2)
        self.refresh_btn.setEnabled(True)

    # ── Cards ─────────────────────────────────────────────────────────────────
    def _installed_ids(self) -> set:
        ids: set[str] = set()
        if not self.plugins_dir.exists():
            return ids
        for sub in self.plugins_dir.iterdir():
            if sub.is_dir() and (sub / "plugin.py").exists():
                ids.add(sub.name)
            elif sub.suffix == ".py" and sub.stem not in {"__init__"}:
                ids.add(sub.stem)
        return ids

    def _render_cards(self, plugins: list):
        self._cards.clear()
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        installed = self._installed_ids()
        for meta in plugins:
            pid  = meta.get("id", "unknown")
            card = PluginCard(meta, is_installed=pid in installed)
            card.install_requested.connect(self._start_install)
            card.uninstall_requested.connect(self._start_uninstall)
            self._cards[pid] = card
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _filter_cards(self, text: str):
        text = text.lower().strip()
        for pid, card in self._cards.items():
            m = card.meta
            match = (
                not text
                or text in m.get("name", "").lower()
                or text in m.get("description", "").lower()
                or any(text in t for t in m.get("tags", []))
            )
            card.setVisible(match)

    def apply_language_market(self, lang):
        self.current_language = lang
        self.lang_manager = LanguageManager()
        self.lang_manager.apply_language(self.current_language)
        self.retrans()

    def retrans(self):
        self.setWindowTitle(self.tr("OmniPull Marketplace"))
        self.title.setText(self.tr("Plugin Marketplace"))
        self.subtitle.setText(self.tr("Extend OmniPull with community plugins"))
        self.refresh_btn.setText(self.tr("Refresh"))
        self.search_edit.setPlaceholderText(self.tr("Search plugins…"))
        self.close_btn.setText(self.tr("Close"))
        
        # If data exists, update with count; otherwise show "Ready"
        if hasattr(self, 'len_of_data'):
            self.status_lbl.setText(self.tr("%1 plugin(s) available").replace("%1", self.len_of_data))
            self.count_lbl.setText(self.tr(f"%1 plugins").replace("%1", self.len_of_data))
        else:
            self.status_lbl.setText(self.tr("Ready"))


    # ── Install ───────────────────────────────────────────────────────────────
    def _start_install(self, meta: dict):
        pid  = meta.get("id")
        card = self._cards.get(pid)
        if not card:
            return
        card.set_installing(0)
        self.status_lbl.setText(f"Installing '{meta['name']}'…")
        worker = PluginInstaller(pid, meta.get("download_url", ""), self.plugins_dir)
        worker.progress.connect(lambda p, c=card: c.set_installing(p))
        worker.success.connect(self._on_install_success)
        worker.error.connect(self._on_install_error)
        self._workers[pid] = worker
        worker.start()

    # def _on_install_success(self, pid: str):
    #     card = self._cards.get(pid)
    #     if card:
    #         card.set_installed()
    #     self.status_lbl.setText(f"✓ '{pid}' installed and running.")
    #     self._workers.pop(pid, None)
    #     QMessageBox.information(
    #         self, "Plugin Installed",
    #         f"'{pid}' is now active.\n\n"
    #         "Remote Monitoring: open  http://localhost:7432  in your browser.",
    #     )
    

    def _on_install_success(self, pid: str):
        card = self._cards.get(pid)
        if card:
            card.set_installed()
        self.status_lbl.setText(f"✓ '{pid}' installed and running.")
        worker = self._workers.pop(pid, None)
        
        # Refresh plugin manager to load the new plugin and trigger UI update
        if PluginManager:
            try:
                mgr = PluginManager.instance()
                mgr.refresh()
            except Exception as e:
                log(f"Error refreshing plugins: {e}", log_level=2, context="MARKETPLACE")
        
        QMessageBox.information(
            self, "Plugin Installed",
            f"'{pid}' is now active.\n\n"
            "Remote Monitoring: open  http://localhost:7432  in your browser.",
        )
        if worker and worker.isRunning():
            worker.wait(500)  # Wait for thread to fully exit
            

    def _on_install_error(self, pid: str, msg: str):
        card = self._cards.get(pid)
        if card:
            card.set_error()
        self.status_lbl.setText(f"✗ Install failed: {msg}")
        self._workers.pop(pid, None)
        QMessageBox.critical(self, "Install Error", f"Failed to install '{pid}':\n\n{msg}")

    # ── Uninstall ─────────────────────────────────────────────────────────────
    def _start_uninstall(self, pid: str):
        reply = QMessageBox.question(
            self, "Uninstall Plugin",
            f"Remove '{pid}'?\nThe plugin will be deactivated immediately.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # AFTER
        if PluginManager is not None:
            mgr = PluginManager.instance()
            if getattr(mgr, "_initialized", False):
                mgr.unload(pid)
                # Wait for OS to release the socket; poll instead of flat sleep
                import socket as _socket
                for _ in range(20):          # up to 4 seconds
                    time.sleep(0.2)
                    try:
                        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                        s.bind(("0.0.0.0", 7432))
                        s.close()
                        break                # port is free
                    except OSError:
                        pass                # still in TIME_WAIT, keep waiting

        plugin_dir = self.plugins_dir / pid
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir, ignore_errors=True)
        else:
            py_file = self.plugins_dir / f"{pid}.py"
            if py_file.exists():
                py_file.unlink()

        card = self._cards.get(pid)
        if card:
            card._installed = False
            card._refresh_button_state()
        
        # Refresh plugin manager to remove the plugin from the bar
        if PluginManager:
            try:
                mgr = PluginManager.instance()
                mgr.refresh()
            except Exception as e:
                log(f"Error refreshing plugins: {e}", log_level=2, context="MARKETPLACE")
        
        self.status_lbl.setText(f"'{pid}' uninstalled.")

    # ── Style ─────────────────────────────────────────────────────────────────
    def _apply_global_style(self):
        self.setStyleSheet("""
            QDialog{background:#14161a;color:#e8eaed;}
            QScrollBar:vertical{background:#14161a;width:8px;border-radius:4px;}
            QScrollBar::handle:vertical{background:#2d3139;border-radius:4px;min-height:30px;}
            QScrollBar::handle:vertical:hover{background:#3c4043;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
        """)