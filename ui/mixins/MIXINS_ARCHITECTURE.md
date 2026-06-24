# OmniPull — Mixin Architecture

## Overview

`DownloadManagerWindow` was a monolithic god class. It has been decomposed into **8 Python mixins** using multiple inheritance. Each mixin owns a distinct responsibility domain. The final class is assembled in `main.py` by listing all mixins in the class declaration.

---

## How It Works

Python resolves method calls using **MRO (Method Resolution Order)** — it walks the inheritance chain left to right and uses the first matching method it finds. All mixin methods have full access to `self`, which is the live `DownloadManagerWindow` instance at runtime.

```
DownloadManagerWindow(instance)
  ├── self.ui              → Ui_MainWindow (Qt designer widgets)
  ├── self.ui_add_download → AddDownloadWindow
  ├── self.ui_settings     → SettingsDialog
  ├── self.d_list          → list[DownloadItem]
  ├── self.selected_d      → DownloadItem (property on TableManagerMixin)
  └── ...all other state set in __init__
```

All 8 mixins + `QMainWindow` are composed via:

```python
class DownloadManagerWindow(
    UIManagerMixin,
    TerminalMixin,
    UpdateControllerMixin,
    DownloadControllerMixin,
    URLProcessorMixin,
    MediaPreviewMixin,
    ContextMenuMixin,
    TableManagerMixin,
    QMainWindow,         # ← must be last; it's the real Qt base
):
```

---

## What Lives in `main.py`

`DownloadManagerWindow.__init__` is the only constructor and it owns:

| Responsibility | Detail |
|---|---|
| Qt setup | `QMainWindow.__init__(self)`, `self.ui.setupUi(self)` |
| Sub-window instantiation | `AddDownloadWindow`, `SettingsDialog`, `QueueDialog`, `ScheduleDialog` |
| Global widget aliases | `widgets = self.ui`, `widgets_add_download`, `widgets_settings` (legacy compat) |
| Core state | `d_list`, `d`, `yt_thread`, `video`, `playlist`, batch state, etc. |
| Signal wiring | `update_gui_signal = Signal(dict)`, `_connect_signals()` |
| Background service launch | `_start_background_services()` → `LogRecorderThread`, `BrowserQueueMonitor` |
| Timers | `run_timer` (900 ms), `update_timer` (250 ms), `scheduler_timer` (60 s) |
| Startup sequence | `populate_table()`, `set_theme()`, `retrans()`, `setup_context_menu_actions()` |

Core methods that remain in `main.py` (not in any mixin):

- `__init__`, `_start_background_services`, `_on_plugins_changed`
- `_connect_signals`, `_setup_terminal_interface`
- `run`, `process_gui_updates`, `check_for_gui_updates`
- `on_advanced_button_clicked`, `_update_plugin_bar_if_needed`

---

## The 8 Mixins

### 1. `UIManagerMixin` — `ui/mixins/ui_manager.py`

**~55 methods** — Application shell, dialogs, theming, language, and lifecycle.

| Group | Methods |
|---|---|
| Dialogs | `show_add_dialog`, `show_queue_dialog`, `show_settings_dialog`, `show_subtitle_failed_dialog`, `show_marketplace`, `show_about_dialog`, `show_whatsnew_dialog`, `ask_for_sched_time` |
| Navigation | `change_page`, `open_help`, `open_github_issues`, `open_completed_file`, `populate_open_menu` |
| Theme / Style | `get_system_theme`, `set_theme`, `_apply_styles` |
| Language | `apply_language_global`, `retrans` |
| Queue UI | `queue_combo`, `on_selection_queue`, `register_queue_background_thread` |
| Category UI | `category_list`, `update_category_combo`, `update_category_list` |
| Lifecycle | `closeEvent`, `changeEvent`, `quit_app`, `force_exit_for_update`, `_hide_to_tray`, `exit_app` |
| Clipboard / Browser | `on_clipboard_change`, `on_browser_download_detected` |
| Utilities | `update_http_status`, `ensure_dependency`, `on_startup`, `update_datetime`, `toggle_details_panel`, `install_browser_extension`, `on_filename_changed`, `clear_log`, `set_log`, `open_folder_dialog`, `_debug_threads` |

---

### 2. `TerminalMixin` — `ui/mixins/terminal.py`

**5 methods** — Embedded yt-dlp CLI terminal inside the app.

| Method | Purpose |
|---|---|
| `toggle_terminal_view(checked)` | Switches main stack between downloads table and terminal page |
| `_terminal_exec()` | Parses user input; checks for busy state; spawns subprocess thread |
| `_run_ytdlp_command(cmd)` | Low-level subprocess handler; streams stdout to terminal output widget |
| `load_ytdlp_options()` | Returns list of known yt-dlp flags for autocomplete |
| `_handle_internal_command(cmd)` | Handles `clear`, `history`, `abort`, `help` without a subprocess |

---

### 3. `UpdateControllerMixin` — `ui/mixins/update_controller.py`

**~19 methods** — All update logic: app, yt-dlp, ffmpeg, deno.

| Group | Methods |
|---|---|
| Dependency install | `install_ffmpeg`, `install_deno`, `install_ytdlp` |
| Version checks | `_handle_version_status`, `check_update_frequency`, `update_available`, `_grace_expired` |
| Update banner | `_show_update_banner`, `_on_banner_update_now`, `_on_banner_later` |
| Update execution | `start_update`, `start_update_yt_dlp`, `apply_pending_yt_dlp_update_on_startup`, `on_yt_dlp_update_finished` |
| App update flow | `update_app`, `show_update_gui`, `handle_update`, `on_update_finished` |

---

### 4. `DownloadControllerMixin` — `ui/mixins/download_controller.py`

**~18 methods** — Download lifecycle: start, pause, resume, delete, queue management.

| Group | Methods |
|---|---|
| Queue control | `start_queue_by_id`, `check_scheduled_queues`, `check_scheduled`, `schedule_all` |
| Row actions | `resume_btn`, `pause_btn`, `delete_btn`, `delete_all_downloads` |
| Bulk actions | `pause_all_downloads`, `stop_all_downloads`, `resume_all_downloads` |
| Queries | `file_in_d_list`, `get_queue_id`, `active_downloads`, `pending_jobs`, `get_yt_id` |
| Core engine | `_prompt_file_conflict`, `start_download` |

---

### 5. `URLProcessorMixin` — `ui/mixins/url_processor.py`

**~45 methods** — URL intake, engine routing, YouTube/playlist extraction, batch import.

| Group | Methods |
|---|---|
| Batch import | `on_import_file_clicked`, `_on_batch_item_ready`, `_refresh_batch_button_label`, `_on_batch_finished`, `_on_batch_failed` |
| URL analysis | `clean_url`, `is_youtube_url`, `fast_process_url`, `url_text_change`, `process_url`, `decide_download_engine`, `extract_ext_from_url`, `category_checker`, `get_header` |
| Progress UI | `update_progress_bar_value`, `update_progress_bar`, `_cancel_url_processing`, `_show_cancel_button`, `_show_close_button`, `on_cancel_close_clicked`, `reset`, `retry`, `refresh_headers` |
| YouTube | `on_youtube_finished`, `on_youtube_error`, `get_video_info`, `_youtube_url_expired`, `refresh_link_btn`, `on_advanced_button_clicked` |
| Playlist | `update_pl_menu`, `update_stream_menu`, `playlist_OnChoice`, `stream_OnChoice`, `category_onChoice`, `download_playlist` |
| Batch picker | `_show_youtube_batch_picker` (261-line method: formats dialog, format labels, per-item fetch) |
| Download trigger | `on_download_button_clicked`, `_add_to_selected_queue` |

---

### 6. `MediaPreviewMixin` — `ui/mixins/media_preview.py`

**6 methods** — Thumbnail and media preview handling.

| Method | Purpose |
|---|---|
| `show_thumbnail(thumbnail)` | Displays video thumbnail in the add-download panel |
| `reset_to_default_thumbnail()` | Clears to placeholder image |
| `show_filetype_thumbnail(ext)` | Shows file-type icon when no video thumbnail is available |
| `on_thumbnail_downloaded(reply)` | `QNetworkReply` slot; decodes image bytes and renders it |
| `is_playable_media(d)` | Returns `True` if file extension is audio/video |
| `watch_downloading` | Opens a live preview of an in-progress download in a media player |

---

### 7. `ContextMenuMixin` — `ui/mixins/context_menu.py`

**~21 methods** — Right-click table context menu and all its actions.

| Group | Methods |
|---|---|
| Setup | `setup_context_menu_actions`, `update_context_menu_actions_state`, `show_table_context_menu` |
| File actions | `open_item`, `open_item_with`, `_on_file_thread_error`, `open_file_location` |
| Queue actions | `add_to_queue_from_context`, `remove_from_queue_from_context` |
| Scheduling | `schedule_download`, `cancel_schedule` |
| Metadata | `file_properties` |
| Remux | `_find_audio_file_for`, `_find_video_file_for`, `_build_output_path`, `_cleanup_separate_streams`, `_start_ffmpeg_remerge`, `remerge_audio_video` |
| Checksum | `start_file_checksum`, `show_file_checksum_result` |
| List management | `pop_download_item` |

---

### 8. `TableManagerMixin` — `ui/mixins/table_manager.py`

**~13 methods** — Download table rendering, filtering, sorting, and selection.

| Method | Purpose |
|---|---|
| `on_sort_changed(text)` | Re-sorts `d_list` by column (name, size, speed, status, date) |
| `selected_d` *(property)* | Getter: looks up `DownloadItem` by `selected_row_num` |
| `selected_d.setter` | Sets `_selected_d` and updates `selected_row_num` |
| `filter_download_table(text)` | Text search filter across name/URL |
| `_categorize_download(filename, status)` | Maps file extension + status to a UI category |
| `_filter_by_category(current, previous)` | `QListWidget` slot; re-runs table filter on category change |
| `populate_table()` | Kicks off `PopulateTableWorker` thread for async row generation |
| `populate_table_apply(prepared_rows)` | Receives pre-built rows from worker and writes them to the `QTableWidget` |
| `_create_readonly_item(text)` | Factory for non-editable `QTableWidgetItem` |
| `update_table_progress()` | Fast in-place update of speed/progress/time cells without full repaint |
| `set_row_color(row, status)` | Applies status color coding to all cells in a row |
| `refresh_table_row(d)` | Updates a single row to reflect a `DownloadItem`'s new state |
| `update_toolbar_buttons_for_selection()` | Enables/disables toolbar buttons based on what's selected |

---

## File Layout

```
OmniPull/
├── main.py                          ← DownloadManagerWindow class + entry point
└── ui/
    └── mixins/
        ├── __init__.py              ← Re-exports all 8 mixin classes
        ├── ui_manager.py            ← UIManagerMixin       (~55 methods)
        ├── terminal.py              ← TerminalMixin         (5 methods)
        ├── update_controller.py     ← UpdateControllerMixin (~19 methods)
        ├── download_controller.py   ← DownloadControllerMixin (~18 methods)
        ├── url_processor.py         ← URLProcessorMixin     (~45 methods)
        ├── media_preview.py         ← MediaPreviewMixin     (6 methods)
        ├── context_menu.py          ← ContextMenuMixin      (~21 methods)
        └── table_manager.py         ← TableManagerMixin     (~13 methods)
```

---

## Key Design Notes

**Widget access** — All mixin methods reference `self.ui`, `self.ui_add_download`, and `self.ui_settings` (set in `__init__`). An earlier version used module-level globals (`widgets`, `widgets_add_download`, `widgets_settings`); those were replaced during extraction via regex substitution with word-boundary matching (`\b`).

**`Signal` declaration** — `update_gui_signal = Signal(dict)` is a class-level attribute and must stay in `DownloadManagerWindow` itself, not in any mixin. PySide6 signals are bound to the concrete class at metaclass time.

**`selected_d` property** — Defined across two `FunctionDef` nodes in `TableManagerMixin`: the `@property` getter and the `@selected_d.setter`. Both are extracted into `table_manager.py` and work correctly because the setter decorator references the getter by name within the same class scope.

**MRO priority** — Mixins are listed left-to-right. If two mixins defined a method with the same name, the leftmost one would win. Currently there are no conflicts; `QMainWindow` is rightmost so its implementations are always shadowed by any mixin that defines the same method name.

**No `__init__` in mixins** — None of the 8 mixins define `__init__`. All instance state (`self.d_list`, `self.video`, `self._batch_items`, etc.) is initialized exclusively in `DownloadManagerWindow.__init__`. Mixins only consume that state via `self`.
