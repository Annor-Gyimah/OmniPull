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
from modules import downloaditem
from modules.utils import log, handle_exceptions, update_object




     

def get_global_sett_folder():
    """return a proper global setting folder"""
    home_folder = os.path.expanduser('~')

    if config.operating_system == 'Windows':
        roaming = os.getenv('APPDATA')  # return APPDATA\Roaming\ under windows
        _sett_folder = os.path.join(roaming, f'.{config.APP_NAME}')

    elif config.operating_system == 'Linux':
        _sett_folder = f'{home_folder}/.config/{config.APP_NAME}/'

    elif config.operating_system == 'Darwin':
        _sett_folder = f'{home_folder}/Library/Application Support/{config.APP_NAME}/'

    else:
        _sett_folder = config.current_directory

    return _sett_folder


config.global_sett_folder = get_global_sett_folder()



def locate_setting_folder():
    """Determine and return the setting folder. Prefer global folder by default."""
    # Create global setting folder if not exists
    if not os.path.exists(config.global_sett_folder):
        try:
            os.makedirs(config.global_sett_folder, exist_ok=True)
        except Exception as e:
            log(f"[Settings] Could not create global folder: {e}", log_level=3)
            return config.current_directory

    return config.global_sett_folder


def ensure_config_files_exist():
    required_files = ['setting.cfg', 'downloads.cfg', 'queues.cfg', 'log.txt']
    for file in required_files:
        path = os.path.join(config.sett_folder, file)
        if not os.path.exists(path):
            with open(path, 'w') as f:
                if file.endswith('.cfg'):
                    json.dump([] if 'queues' in file or 'downloads' in file else {}, f)
                else:
                    f.write("")  # empty log.txt



config.sett_folder = locate_setting_folder()
ensure_config_files_exist()

def load_d_list():
    """create and return a list of 'DownloadItem objects' based on data extracted from 'downloads.cfg' file"""
    d_list = []
    try:
        file = os.path.join(config.sett_folder, 'downloads.cfg')

        with open(file, 'r') as f:
            # expecting a list of dictionaries
            data = json.load(f)

        # converting list of dictionaries to list of DownloadItem() objects
        for dict_ in data:
            d = update_object(downloaditem.DownloadItem(), dict_)
            d.sched = dict_.get('scheduled', None) 
            d.queue_position = int(dict_.get("queue_position", 0))
            if d:  # if update_object() returned an updated object not None
                d_list.append(d)

        

        # clean d_list
        for d in d_list:
            status = None
            if d.progress >=100:
                status = config.Status.completed
            elif d.progress <= 100 and d.sched != None:
                status = config.Status.scheduled
            elif d.in_queue and d.queue_name:
                if d.status not in (config.Status.downloading, config.Status.completed):
                    status = config.Status.queued
                else:
                    status = d.status  # preserve active or completed
            else:
                if d.status not in (config.Status.downloading, config.Status.completed):
                    status = config.Status.cancelled

            # status = config.Status.completed if d.progress >= 100 else config.Status.cancelled
            d.status = status
            d.live_connections = 0

    except FileNotFoundError:
        log('downloads.cfg file not found', log_level=3)
    except Exception as e:
        log(f'load_d_list()>: {e}', log_level=3)
    finally:
        if not isinstance(d_list, list):
            d_list = []
        return d_list



def save_d_list(d_list):
    try:
        data = []
        for d in d_list:
            data.append(d.get_persistent_properties())

        file = os.path.join(config.sett_folder, 'downloads.cfg')

        with open(file, 'w') as f:
            try:
                json.dump(data, f)
            except Exception as e:
                log('error save d_list:', e)
        #log('list saved')
    except Exception as e:
        handle_exceptions(e)


def load_setting():
    settings = {}
    try:
        log(f'Load Application setting from {config.sett_folder}', log_level=1)
        file = os.path.join(config.sett_folder, 'setting.cfg')
        with open(file, 'r') as f:
            settings = json.load(f)

    except FileNotFoundError:
        log('setting.cfg not found', log_level=2)
    except Exception as e:
        handle_exceptions(e)
    finally:
        if not isinstance(settings, dict):
            settings = {}

        # update config module
        config.__dict__.update(settings)



def save_setting():
    settings = {key: config.__dict__.get(key) for key in config.settings_keys}

    try:
        if not os.path.exists(config.sett_folder):
            os.makedirs(config.sett_folder)

        file = os.path.join(config.sett_folder, 'setting.cfg')
        with open(file, 'w') as f:
            json.dump(settings, f)
    except Exception as e:
        handle_exceptions(e)


QUEUES_CFG_FILE = os.path.join(config.sett_folder, "queues.cfg")

def load_queues():
    """ Load list queues from  a list of queues.cfg """

    try:
        if not os.path.exists(QUEUES_CFG_FILE):
            return []

        with open(QUEUES_CFG_FILE, 'r') as f:
            return json.load(f)

    except Exception as e:
        log(f"Error loading queues.cfg: {e}", log_level=3)
        return []
    


def save_queues(queues):
    """Save list of queues to queues.cfg file"""
    try:
        with open(QUEUES_CFG_FILE, 'w') as f:
            json.dump(queues, f, indent=2)
    except Exception as e:
        log(f"Error saving queues.cfg: {e}", log_level=3)


