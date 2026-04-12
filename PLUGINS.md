# OmniPull Plugin System

OmniPull's plugin system allows you to extend the application's functionality by writing Python modules that integrate with the download manager core.

## How It Works

1. **Plugin Discovery**: The `PluginManager` scans the `plugins/` directory for:
   - Single-file plugins: `<name>.py`
   - Package plugins: `<name>/plugin.py`

2. **Loading**: For each plugin found, `PluginManager`:
   - Imports the module dynamically
   - Reads optional `__plugin_meta__` for metadata
   - Calls `initialize_plugin(d_list, main_q)` to activate

3. **Unloading**: On uninstall, calls optional `teardown_plugin()` for cleanup

## Plugin Structure

### Required Entry Point

```python
def initialize_plugin(d_list: list, main_q: Queue) -> None:
    """
    Called when the plugin is loaded.
    
    Args:
        d_list: List of download item objects
        main_q: Queue to send messages to the main GUI thread
    """
    pass
```

### Optional Teardown

```python
def teardown_plugin() -> None:
    """Called when the plugin is unloaded."""
    pass
```

### Optional Metadata

```python
__plugin_meta__ = {
    "name": "My Plugin",
    "version": "1.0.0",
    "author": "Your Name",
    "description": "What the plugin does",
}
```

## Available Resources

### d_list (Download List)

A list of download item objects. Each item has attributes:
- `id` - Unique identifier
- `name` - File name
- `status` - Current status ("downloading", "completed", "error", "queued", etc.)
- `progress` - Progress percentage (0-100)
- `_progress` - Internal progress (may differ)
- `speed` - Current download speed
- `_speed` - Internal speed tracking
- `size` - Total file size
- `downloaded` - Bytes downloaded
- `folder` - Destination folder
- `engine` - Download engine used
- `remaining_time` - Estimated time remaining

### main_q (Main Queue)

A `queue.Queue` to communicate with the GUI thread. Send tuples:
```python
main_q.put(('log', 'Your message here'))           # Log message
main_q.put(('status', 'Status update'))           # Status update
main_q.put(('notify', {'title': 'Alert', 'msg': 'Something happened'}))  # Notification
```

## Best Practices

### 1. Never Import PySide6 at Module Level

Plugins may load before the GUI is ready. Use the main queue to defer UI operations.

```python
# Bad
from PySide6.QtWidgets import QMessageBox

# Good - send to main thread instead
main_q.put(('notify', {'title': 'Alert', 'msg': 'Something happened'}))
```

### 2. Use Daemon Threads for Blocking Work

`initialize_plugin()` must return quickly. Start threads for any long-running work:

```python
def initialize_plugin(d_list, main_q):
    global _running
    _running = True
    thread = threading.Thread(target=_background_task, daemon=True)
    thread.start()

def _background_task():
    while _running:
        # Do work
        time.sleep(1)

def teardown_plugin():
    global _running
    _running = False
```

### 3. Implement teardown_plugin() for Threaded Plugins

Set a flag that your thread checks to allow clean shutdown:

```python
_running = False

def teardown_plugin():
    global _running
    _running = False
```

### 4. Handle Optional Dependencies Gracefully

Check for optional imports and handle missing packages:

```python
try:
    import requests
except ImportError:
    requests = None

def initialize_plugin(d_list, main_q):
    if requests is None:
        main_q.put(('log', 'requests not installed - feature unavailable'))
```

### 5. Don't Mutate d_list Directly

From background threads, only write simple scalar attributes. For structural changes, delegate to the GUI thread via `main_q`.

## Example Plugins

### Completion Logger

```python
__plugin_meta__ = {
    "name": "Completion Logger",
    "version": "1.0.0",
    "author": "You",
    "description": "Logs completed downloads to a file.",
}

import threading
import time
from pathlib import Path

_running = False
_d_list = []
_log_path = Path.home() / "omnipull_completions.log"

def initialize_plugin(d_list, main_q):
    global _d_list, _running
    _d_list = d_list
    _running = True
    
    t = threading.Thread(target=_watch, args=(main_q,), daemon=True)
    t.start()
    main_q.put(('log', '[completion_logger] Plugin started.'))

def teardown_plugin():
    global _running
    _running = False

def _watch(main_q):
    seen_completed = set()
    while _running:
        for d in _d_list:
            if d.status == 'completed' and d.id not in seen_completed:
                seen_completed.add(d.id)
                line = f"{d.name} — {d.folder}\n"
                _log_path.write_text(
                    (_log_path.read_text() if _log_path.exists() else '') + line
                )
                main_q.put(('log', f'[completion_logger] Logged: {d.name}'))
        time.sleep(5)
```

### Remote Monitoring (FastAPI Server)

```python
__plugin_meta__ = {
    "name": "Remote Monitoring",
    "version": "1.0.0",
    "author": "OmniPull Team",
    "description": "Exposes real-time download progress over HTTP.",
}

import threading
from queue import Queue

_d_list = []
_main_q = None
_server_thread = None
_PORT = 7432

def initialize_plugin(d_list, main_q):
    global _d_list, _main_q, _server_thread
    _d_list = d_list
    _main_q = main_q
    
    _server_thread = threading.Thread(target=_run_server, daemon=True)
    _server_thread.start()

def teardown_plugin():
    # Uvicorn server shuts down when daemon thread exits
    pass

def _run_server():
    import uvicorn
    from fastapi import FastAPI
    # ... FastAPI app setup ...
```

## Publishing to Marketplace

To share your plugin via the OmniPull Marketplace:

### 1. Create manifest.json Entry

Add your plugin to `plugin_server/manifest.json`:

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "What it does",
  "icon": "⚡",
  "tags": ["utility", "download"],
  "size": "~10 KB",
  "download_url": "https://your-server.com/my_plugin.zip",
  "requires": ["requests", "pyyaml"]
}
```

### 2. Package as ZIP

Create a ZIP file containing your plugin structure:
```
my_plugin/
├── plugin.py
└── (optional) __init__.py, other modules
```

### 3. Host the ZIP

Upload the ZIP to a publicly accessible URL and update the `download_url` in the manifest.

## Plugin Manager API Reference

```python
from modules.plugin_manager import PluginManager

# Get singleton instance
mgr = PluginManager.instance()

# Initialize (call once from main window)
mgr.setup(d_list=download_list, main_q=main_queue, plugins_dir="plugins")

# Load all plugins
loaded = mgr.load_all()

# Get loaded plugins
plugins = mgr.loaded_plugins

# Get specific plugin
plugin = mgr.get("plugin_name")

# Unload a plugin
mgr.unload("plugin_name")

# Reload a plugin
mgr.reload("plugin_name")
```

## Troubleshooting

**Plugin not loading?**  
- Ensure `initialize_plugin(d_list, main_q)` is defined and callable
- Check the logs for import errors

**Thread not stopping on uninstall?**  
- Ensure `teardown_plugin()` sets a flag your thread checks

**Missing dependencies?**  
- Use try/except for optional imports
- List required packages in the marketplace manifest