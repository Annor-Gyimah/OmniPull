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
import json

from modules import config
from typing import List, Dict, Optional
from modules.downloaditem import DownloadItem
from modules.utils import log, update_object
from modules.db_manager import DatabaseManager, migrate_json_to_sqlite


class SettingsManager:
    _instance = None
    _initialized = False
    _settings_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.current_settings = {}
            self.queues = []
            self.categories = []
            self.d_list = []
            self.sett_folder = self._get_global_sett_folder()
            self._ensure_config_files_exist()

            

            _cfg  = os.path.join(self.sett_folder, "downloads.cfg")
            _db   = os.path.join(self.sett_folder, "downloads.db")

            migrate_json_to_sqlite(_cfg, _db)          # no-op after first run
            self._db = DatabaseManager(_db)


    def _get_global_sett_folder(self):
        """Return a proper global setting folder"""
        home_folder = os.path.expanduser('~')

        if config.operating_system == 'Windows':
            roaming = os.getenv('APPDATA')
            return os.path.join(roaming, f'.{config.APP_NAME}')
        elif config.operating_system == 'Linux':
            return f'{home_folder}/.config/{config.APP_NAME}/'
        elif config.operating_system == 'Darwin':
            return f'{home_folder}/Library/Application Support/{config.APP_NAME}/'
        else:
            return config.current_directory

    def _ensure_config_files_exist(self):
        """Ensure all required config files exist"""
        required_files = ['setting_2.cfg', 'categories.cfg', 'queues.cfg', 'log.txt']
        for file in required_files:
            path = os.path.join(self.sett_folder, file)
            if not os.path.exists(path):
                with open(path, 'w') as f:
                    if file.endswith('.cfg'):
                        json.dump([] if 'queues' in file or 'downloads' in file or 'categories' in file else {}, f)
                    else:
                        f.write("")

    def load_settings(self, force=False):
        """Load all settings, optionally force reload"""
        if self._settings_loaded and not force:
            return

        try:
            # Load main settings
            settings_path = os.path.join(self.sett_folder, 'setting_2.cfg')
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                    config.__dict__.update(settings)

            # Load download list
            self.d_list = self.load_d_list()

            # Load queues
            self.queues = self.load_queues()

            self._settings_loaded = True
            # log("Settings loaded successfully")
            log(f'Loaded Application setting from {self.sett_folder}', log_level=1)
            config.ffmpeg_actual_path = config._find_tool(
                "ffmpeg",
                selected=config.user_selected_ffmpeg,
                bundled_name="ffmpeg",
                extra_paths=config._ffmpeg_extra,
            )
            log(f'ffmpeg path: {config.ffmpeg_actual_path}', log_level=1)
            # Update ffmpeg_selected_path and ytdlp_config ffmpeg_location with resolved path
            config.ffmpeg_selected_path = config.ffmpeg_actual_path
            config.ytdlp_config['ffmpeg_location'] = config.ffmpeg_actual_path
            
            config.yt_dlp_actual_path = config._find_tool(
                "yt-dlp",
                selected=(config.yt_dlp_exe or config.user_selected_ytdlp),
                bundled_name="yt-dlp",
                extra_paths=config._ytdlp_extra,
            )
            log(f'yt-dlp path: {config.yt_dlp_actual_path}', log_level=1)
            config.deno_actual_path = config._find_tool(
                "deno",
                selected=(config.deno_exe or config.user_selected_deno),
                bundled_name = "deno",
                extra_paths = config._deno_extra
            )
            log(f'deno path: {config.deno_actual_path}', log_level=1)
            config.deno_verified = True if config.deno_actual_path else False
        except Exception as e:
            log(f"Error loading settings: {e}", log_level=3)

    


    def load_d_list(self) -> list:
        """Load download list from SQLite."""
        d_list = []
        try:
            rows = self._db.load_all_downloads()
            for row_dict in rows:
                d = update_object(DownloadItem(), row_dict)
                d.sched = row_dict.get("scheduled", None)
                d.queue_position = int(row_dict.get("queue_position") or 0)
                if d:
                    d_list.append(d)

            self._clean_d_list(d_list)

        except Exception as e:
            log(f"[DB] Error loading download list: {e}", log_level=3)

        return d_list
    
    def load_refresh_table(self):
        import re
        try:
            old_file_path = os.path.join(self.sett_folder, 'downloads.cfg')
            os.remove if os.path.exists(old_file_path) else print('Good')
            new_file_path = os.path.exists(self.sett_folder, 'downloads_copy.cfg')
            if new_file_path := os.rename(new_file_path, old_file_path):
                self.load_d_list()
                log('[Table Refreshed] Table has been refreshed!!!')
            else:
                log('[Table Refresh Error] Unable to refresh')
        except Exception as e:
            log(f'[Error] Unable to refresh {e}')


    def _clean_d_list(self, d_list):
        """Clean and update download list statuses"""
        for d in d_list:
            if d.status == config.Status.error:
                d.status = config.Status.error
                d.live_connections = 0
                continue

            status = None
            if d.progress >= 100:
                status = config.Status.completed
            elif d.progress <= 100 and d.sched is not None:
                status = config.Status.scheduled
            elif d.in_queue and d.queue_name:
                if d.status not in (config.Status.downloading, config.Status.completed):
                    status = config.Status.queued
                else:
                    status = d.status
            else:
                if d.status not in (config.Status.downloading, config.Status.completed):
                    status = config.Status.cancelled

            d.status = status
            d.live_connections = 0

    
    def save_settings(self):
        """Save all current settings"""
        try:
            # Save main settings — coerce Path objects to strings before serialising
            settings = {}
            for key in config.settings_keys:
                val = config.__dict__.get(key)
                if isinstance(val, os.PathLike):
                    val = str(val)
                settings[key] = val

            with open(os.path.join(self.sett_folder, 'setting_2.cfg'), 'w') as f:
                json.dump(settings, f, indent=4, sort_keys=True)

            # Save download list
            self.save_d_list(self.d_list)

            # Save queues
            self.save_queues(self.queues)

        except Exception as e:
            log(f"Error saving settings: {e}", log_level=3)


    def save_d_list(self, d_list: list):
        """Persist the full download list to SQLite (batch upsert + prune orphans)."""
        try:
            if not d_list:
                # If list is empty, clear all rows
                with self._db._connect() as conn:
                    conn.execute("DELETE FROM downloads")
                    conn.commit()
                return

            props_list = [d.get_persistent_properties() for d in d_list]
            self._db.upsert_many(props_list)

            # Prune DB rows whose IDs are no longer in d_list
            current_ids = [d.id for d in d_list]
            placeholders = ",".join("?" for _ in current_ids)
            with self._db._connect() as conn:
                conn.execute(
                    f'DELETE FROM downloads WHERE "id" NOT IN ({placeholders})',
                    current_ids
                )
                conn.commit()

        except Exception as e:
            log(f"[DB] Error saving download list: {e}", log_level=3)
    

    def load_queues(self):
        """Load queues from file"""
        try:
            queue_path = os.path.join(self.sett_folder, 'queues.cfg')
            if os.path.exists(queue_path):
                with open(queue_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            log(f"Error loading queues: {e}", log_level=3)
        return []

    def save_queues(self, queues):
        """Save queues to file"""
        try:
            with open(os.path.join(self.sett_folder, 'queues.cfg'), 'w') as f:
                json.dump(queues, f, indent=2)
        except Exception as e:
            log(f"Error saving queues: {e}", log_level=3)

    def get_setting(self, key, default=None):
        """Get a specific setting value"""
        return config.__dict__.get(key, default)

    def set_setting(self, key, value):
        """Set a specific setting value"""
        config.__dict__[key] = value
    

    def load_categories(self) -> List[Dict[str, str]]:
        try:
            _FNAME = os.path.join(self.sett_folder, "categories.cfg")
            with open(_FNAME, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    # normalize entries
                    out = []
                    for it in data:
                        if not isinstance(it, dict):
                            continue
                        name = it.get("name")
                        if not name:
                            continue
                        out.append({
                            "name": str(name),
                            "types": str(it.get("types", "")) if it.get("types") is not None else "",
                            "path": str(it.get("path", "")) if it.get("path") is not None else "",
                        })
                    return out
        except Exception:
            pass
        return []


    def save_categories(self, categories: List[Dict[str, str]]) -> None:
        _FNAME = os.path.join(self.sett_folder, "categories.cfg")
        try:
            with open(_FNAME, "w", encoding="utf-8") as f:
                json.dump(categories, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    

    def add_category(self, name: str, types: Optional[str] = None, path: Optional[str] = None) -> bool:
        """Add a category if it doesn't exist. Returns True if added, False if already exists."""
        name = (name or "").strip()
        if not name:
            return False
        cats = self.load_categories()
        for c in cats:
            if c.get("name", "").strip().lower() == name.lower():
                return False
        cats.append({"name": name, "types": (types or "").strip(), "path": (path or "").strip()})
        self.save_categories(cats)
        config.main_window_q.put(('category_list', ''))
        return True


    def remove_category(self, name: str) -> bool:
        name = (name or "").strip()
        if not name:
            return False
        cats = self.load_categories()
        new = [c for c in cats if c.get("name", "").strip().lower() != name.lower()]
        if len(new) == len(cats):
            return False
        self.save_categories(new)
        return True