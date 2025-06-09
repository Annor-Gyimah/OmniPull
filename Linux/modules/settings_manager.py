from modules import config
import os
import json
from modules.utils import log, handle_exceptions, update_object
from modules.downloaditem import DownloadItem

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
            self.d_list = []
            self.sett_folder = self._get_global_sett_folder()
            self._ensure_config_files_exist()

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
        required_files = ['setting.cfg', 'downloads.cfg', 'queues.cfg', 'log.txt', '.omnipull_url_queue.json']
        for file in required_files:
            path = os.path.join(self.sett_folder, file)
            if not os.path.exists(path):
                with open(path, 'w') as f:
                    if file.endswith('.cfg'):
                        json.dump([] if 'queues' in file or 'downloads' in file else {}, f)
                    elif file.endswith('.json'):
                        # Create an empty queue file
                        json.dump([], f)
                    else:
                        f.write("")

    def load_settings(self, force=False):
        """Load all settings, optionally force reload"""
        if self._settings_loaded and not force:
            return

        try:
            # Load main settings
            settings_path = os.path.join(self.sett_folder, 'setting.cfg')
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
            log('Loaded Application setting from', self.sett_folder)

        except Exception as e:
            log(f"Error loading settings: {e}")

    def load_d_list(self):
        """Load download list from file"""
        d_list = []
        try:
            file_path = os.path.join(self.sett_folder, 'downloads.cfg')
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                for dict_ in data:
                    d = update_object(DownloadItem(), dict_)
                    if d:
                        d_list.append(d)

            self._clean_d_list(d_list)
        except FileNotFoundError:
            log(f"downloads.cfg not found!")
        except Exception as e:
            log(f"Error loading download list: {e}")
        
        return d_list

    def _clean_d_list(self, d_list):
        """Clean and update download list statuses"""
        for d in d_list:
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
            # Save main settings
            settings = {key: config.__dict__.get(key) for key in config.settings_keys}
            with open(os.path.join(self.sett_folder, 'setting.cfg'), 'w') as f:
                json.dump(settings, f)

            # Save download list
            self.save_d_list(self.d_list)

            # Save queues
            self.save_queues(self.queues)

            # log("Settings saved successfully")

        except Exception as e:
            log(f"Error saving settings: {e}")

    def save_d_list(self, d_list):
        """Save download list to file"""
        try:
            data = [d.get_persistent_properties() for d in d_list]
            with open(os.path.join(self.sett_folder, 'downloads.cfg'), 'w') as f:
                json.dump(data, f)
        except Exception as e:
            log(f"Error saving download list: {e}")

    def load_queues(self):
        """Load queues from file"""
        try:
            queue_path = os.path.join(self.sett_folder, 'queues.cfg')
            if os.path.exists(queue_path):
                with open(queue_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            log(f"Error loading queues: {e}")
        return []

    def save_queues(self, queues):
        """Save queues to file"""
        try:
            with open(os.path.join(self.sett_folder, 'queues.cfg'), 'w') as f:
                json.dump(queues, f, indent=2)
        except Exception as e:
            log(f"Error saving queues: {e}")

    def get_setting(self, key, default=None):
        """Get a specific setting value"""
        return config.__dict__.get(key, default)

    def set_setting(self, key, value):
        """Set a specific setting value"""
        config.__dict__[key] = value