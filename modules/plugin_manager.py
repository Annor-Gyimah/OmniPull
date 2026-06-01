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
import importlib
import importlib.util
import traceback
from pathlib import Path
from queue import Queue
from typing import Optional

# ── Logging shim (falls back to print outside of the main app) ──────────────
try:
    from modules.utils import log
except ImportError:
    def log(msg, log_level=1, context="PLUGIN-MGR"):
        print(f"[{context}] {msg}")


class PluginInfo:
    """Holds runtime metadata for a loaded plugin."""

    def __init__(self, name: str, version: str, description: str, icon: str,
                 module, path: str):
        self.name = name
        self.version = version
        self.description = description
        self.icon = icon
        self.module = module
        self.path = path
        self.active = False
        self.error: Optional[str] = None

    def __repr__(self):
        return f"<Plugin '{self.name}' v{self.version} active={self.active}>"


class PluginManager:
    """
    Singleton that owns the plugin lifecycle.

    Usage
    -----
    mgr = PluginManager.instance()
    mgr.setup(d_list=app_d_list, main_q=config.main_window_q, plugins_dir="plugins")
    mgr.load_all()
    """

    _instance: Optional["PluginManager"] = None
    
    # Optional callback for when plugins change (refresh UI)
    on_plugins_changed = None

    # ── Singleton constructor ────────────────────────────────────────────────
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    def instance(cls) -> "PluginManager":
        return cls()

    # ── One-time setup ───────────────────────────────────────────────────────
    def setup(self, d_list: list, main_q: Queue,
        plugins_dir: str = "plugins") -> None:
        """Call once from the main window __init__."""
        if self._initialized:
            return
        self.d_list = d_list
        self.main_q = main_q
        self.plugins_dir = Path(plugins_dir).resolve()
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._plugins: dict[str, PluginInfo] = {}
        self._initialized = True
        log(f"Plugin directory: {self.plugins_dir}", context="PLUGIN-MGR")

    # ── Discovery & Loading ──────────────────────────────────────────────────
    def load_all(self) -> list[PluginInfo]:
        """
        Scan self.plugins_dir for:
          - <name>.py  (single-file plugin)
          - <name>/plugin.py  (package plugin)
        Returns the list of successfully loaded PluginInfo objects.
        """
        if not self._initialized:
            log("PluginManager.setup() must be called before load_all()", log_level=2)
            return []

        loaded = []

        # Single-file plugins (*.py, but not __init__)
        log(f"Scanning plugins directory: {self.plugins_dir}", context="PLUGIN-MGR")
        
        if not self.plugins_dir.exists():
            log(f"Plugins directory does not exist: {self.plugins_dir}", log_level=2, context="PLUGIN-MGR")
            self._notify_plugins_changed()
            return []
        
        py_files = sorted(self.plugins_dir.glob("*.py"))
        log(f"Found {len(py_files)} .py files in plugins directory", context="PLUGIN-MGR")
        
        for py_file in py_files:
            if py_file.stem.startswith("_"):
                continue
            log(f"Loading single-file plugin: {py_file.name}", log_level=1, context="PLUGIN-MGR")
            info = self._load_file_plugin(py_file)
            if info:
                loaded.append(info)

        # Package plugins  (<name>/plugin.py)
        subdirs = [d for d in sorted(self.plugins_dir.iterdir()) if d.is_dir()]
        log(f"Found {len(subdirs)} subdirectories in plugins directory", context="PLUGIN-MGR")
        
        for sub in subdirs:
            entry = sub / "plugin.py"
            if entry.exists():
                log(f"Loading package plugin: {sub.name}", log_level=1, context="PLUGIN-MGR")
                info = self._load_file_plugin(entry, package_name=sub.name)
                if info:
                    loaded.append(info)

        log(f"Loaded {len(loaded)} plugin(s): {[p.name for p in loaded]}",
            context="PLUGIN-MGR")
        
        # Notify listeners
        log(f"Notifying {len(loaded)} plugin(s) changed listeners", context="PLUGIN-MGR")
        self._notify_plugins_changed()
        
        return loaded

    def _load_file_plugin(self, path: Path,
            package_name: str = None) -> Optional[PluginInfo]:
        """Import a single plugin file and call its initialize_plugin entry-point."""
        plugin_name = package_name or path.stem
        module_name = f"omnipull_plugin_{plugin_name}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            log(f"Module imported successfully: {plugin_name} from {path}", log_level=1, context="PLUGIN-MGR")
        except Exception as exc:
            log(f"Failed to import plugin '{plugin_name}': {exc}",
                log_level=3, context="PLUGIN-MGR")
            log(traceback.format_exc(), log_level=4, context="PLUGIN-MGR")
            return None

        # Read metadata (optional __plugin_meta__ dict)
        meta = getattr(module, "__plugin_meta__", {})
        info = PluginInfo(
            name=meta.get("name", plugin_name),
            version=meta.get("version", "0.0.1"),
            description=meta.get("description", "No description."),
            icon=meta.get("icon", "🔌"),
            module=module,
            path=str(path),
        )

        # Call the required entry-point
        init_fn = getattr(module, "initialize_plugin", None)
        if init_fn is None:
            log(f"Plugin '{plugin_name}' has no initialize_plugin(); skipping.",
                log_level=2, context="PLUGIN-MGR")
            return None

        try:
            log(f"Calling initialize_plugin() for '{plugin_name}'", log_level=1, context="PLUGIN-MGR")
            init_fn(d_list=self.d_list, main_q=self.main_q)
            info.active = True
            log(f"initialize_plugin() succeeded for '{plugin_name}'", log_level=1, context="PLUGIN-MGR")
        except Exception as exc:
            info.error = str(exc)
            log(f"initialize_plugin() failed for '{plugin_name}': {exc}",
                log_level=3, context="PLUGIN-MGR")
            log(traceback.format_exc(), log_level=4, context="PLUGIN-MGR")
            return None

        self._plugins[plugin_name] = info
        log(f"Plugin loaded: {info}", context="PLUGIN-MGR")
        return info

    # ── Public API ───────────────────────────────────────────────────────────
    @property
    def loaded_plugins(self) -> dict[str, PluginInfo]:
        return dict(self._plugins)

    def get(self, name: str) -> Optional[PluginInfo]:
        return self._plugins.get(name)

    # AFTER
    def unload(self, name: str) -> bool:
        """Call optional teardown_plugin() then remove from registry."""
        info = self._plugins.get(name)
        if not info:
            return False

        teardown = getattr(info.module, "teardown_plugin", None)
        if teardown:
            try:
                import threading, concurrent.futures
                # Run teardown in a thread so we can enforce a hard timeout.
                # Asyncio servers (like the remote-monitoring plugin) may block
                # on loop.run_forever(); teardown must stop the loop AND join
                # its thread before returning.
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(teardown)
                    try:
                        future.result(timeout=6)   # 6-second hard limit
                    except concurrent.futures.TimeoutError:
                        log(f"teardown_plugin() timed out for '{name}' — forcing removal.",
                            log_level=2, context="PLUGIN-MGR")
                    except Exception as exc:
                        log(f"teardown_plugin() error for '{name}': {exc}",
                            log_level=2, context="PLUGIN-MGR")
            except Exception as exc:
                log(f"teardown_plugin() executor error for '{name}': {exc}",
                    log_level=2, context="PLUGIN-MGR")

        sys.modules.pop(f"omnipull_plugin_{name}", None)
        del self._plugins[name]
        log(f"Plugin '{name}' unloaded.", context="PLUGIN-MGR")
        return True

    def shutdown_all(self) -> None:
        """Unload every plugin gracefully. Call from the app closeEvent."""
        for name in list(self._plugins.keys()):
            self.unload(name)
        log("All plugins unloaded.", context="PLUGIN-MGR")

    def reload(self, name: str) -> Optional[PluginInfo]:
        """Unload then re-load a plugin by name."""
        info = self._plugins.get(name)
        if not info:
            return None
        path = Path(info.path)
        self.unload(name)
        result = self._load_file_plugin(path, package_name=name if (path.name == "plugin.py") else None)
        self._notify_plugins_changed()
        return result
    
    def refresh(self) -> list[PluginInfo]:
        """
        Unload all plugins and reload from disk.
        Useful after marketplace installs a new plugin.
        """
        pids = list(self._plugins.keys())
        for pid in pids:
            self.unload(pid)
        return self.load_all()
    
    def _notify_plugins_changed(self):
        """Call the registered callback when plugins change."""
        if self.on_plugins_changed and callable(self.on_plugins_changed):
            try:
                log(f"Invoking on_plugins_changed callback", context="PLUGIN-MGR")
                self.on_plugins_changed()
                log(f"on_plugins_changed callback completed successfully", context="PLUGIN-MGR")
            except Exception as exc:
                log(f"Error in on_plugins_changed callback: {exc}",
                    log_level=2, context="PLUGIN-MGR")
        else:
            log(f"on_plugins_changed callback not set or not callable", log_level=1, context="PLUGIN-MGR")
