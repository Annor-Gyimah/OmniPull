#####################################################################################
#   OmniPull Plugin Manager
#   Scans the /plugins directory, dynamically imports modules, and calls
#   the standardized entry-point: initialize_plugin(d_list, main_q)
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

    def __init__(self, name: str, version: str, description: str,
                 module, path: str):
        self.name = name
        self.version = version
        self.description = description
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
        for py_file in sorted(self.plugins_dir.glob("*.py")):
            if py_file.stem.startswith("_"):
                continue
            info = self._load_file_plugin(py_file)
            if info:
                loaded.append(info)

        # Package plugins  (<name>/plugin.py)
        for sub in sorted(self.plugins_dir.iterdir()):
            if sub.is_dir():
                entry = sub / "plugin.py"
                if entry.exists():
                    info = self._load_file_plugin(entry, package_name=sub.name)
                    if info:
                        loaded.append(info)

        log(f"Loaded {len(loaded)} plugin(s): {[p.name for p in loaded]}",
            context="PLUGIN-MGR")
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
            init_fn(d_list=self.d_list, main_q=self.main_q)
            info.active = True
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

    def unload(self, name: str) -> bool:
        """Call optional teardown_plugin() then remove from registry."""
        info = self._plugins.get(name)
        if not info:
            return False

        teardown = getattr(info.module, "teardown_plugin", None)
        if teardown:
            try:
                teardown()
            except Exception as exc:
                log(f"teardown_plugin() error for '{name}': {exc}",
                    log_level=2, context="PLUGIN-MGR")

        sys.modules.pop(f"omnipull_plugin_{name}", None)
        del self._plugins[name]
        log(f"Plugin '{name}' unloaded.", context="PLUGIN-MGR")
        return True

    def reload(self, name: str) -> Optional[PluginInfo]:
        """Unload then re-load a plugin by name."""
        info = self._plugins.get(name)
        if not info:
            return None
        path = Path(info.path)
        self.unload(name)
        return self._load_file_plugin(path, package_name=name if (path.name == "plugin.py") else None)
