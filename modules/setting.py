

import os
import json

from . import config
from . import downloaditem
from .utils import log, handle_exceptions, update_object


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
    """check local folder and global setting folder for setting.cfg file"""
    # look for previous setting file
    try:
        if 'setting.cfg' in os.listdir(config.current_directory):
            return config.current_directory
        elif 'setting.cfg' in os.listdir(config.global_sett_folder):
            return config.global_sett_folder
    except:
        pass

    # no setting file found will check local folder for writing permission, otherwise will return global sett folder
    try:
        folder = config.current_directory
        with open(os.path.join(folder, 'test'), 'w') as test_file:
            test_file.write('0')
        os.unlink(os.path.join(folder, 'test'))
        return config.current_directory

    except PermissionError:
        log("No enough permission to store setting at local folder:", folder)
        log('Global setting folder will be selected:', config.global_sett_folder)

        # create global setting folder if it doesn't exist
        if not os.path.isdir(config.global_sett_folder):
            os.mkdir(config.global_sett_folder)

        return config.global_sett_folder


config.sett_folder = locate_setting_folder()


def load_d_list():
    """create and return a list of 'DownloadItem objects' based on data extracted from 'downloads.cfg' file"""
    d_list = []
    try:
        log('Load previous download items from', config.sett_folder)
        file = os.path.join(config.sett_folder, 'downloads.cfg')

        with open(file, 'r') as f:
            # expecting a list of dictionaries
            data = json.load(f)

        # converting list of dictionaries to list of DownloadItem() objects
        for dict_ in data:
            d = update_object(downloaditem.DownloadItem(), dict_)
            d.sched = dict_.get('scheduled', None) 
            if d:  # if update_object() returned an updated object not None
                d_list.append(d)

        # clean d_list
        for d in d_list:
            status = None
            if d.progress >=100:
                status = config.Status.completed
            elif d.progress <= 100 and d.sched != None:
                status = config.Status.scheduled
            else:
                status=config.Status.cancelled
            # status = config.Status.completed if d.progress >= 100 else config.Status.cancelled
            d.status = status
            d.live_connections = 0

    except FileNotFoundError:
        log('downloads.cfg file not found')
    except Exception as e:
        log(f'load_d_list()>: {e}')
    finally:
        if not isinstance(d_list, list):
            d_list = []
        return d_list

# def load_d_list():
#     """Create and return a list of 'DownloadItem' objects based on data extracted from 'downloads.cfg' file"""
#     d_list = []
#     try:
#         log('Load previous download items from', config.sett_folder)
#         file = os.path.join(config.sett_folder, 'downloads.cfg')

#         with open(file, 'r') as f:
#             # Expecting a list of dictionaries
#             data = json.load(f)

#         # Converting list of dictionaries to list of DownloadItem objects
#         for dict_ in data:
#             d = downloaditem.DownloadItem()  # Create an instance first
#             d = update_object(d, dict_)  # Update with stored values
            
#             # Ensure `self.sched` is explicitly assigned
#             d.sched = dict_.get('scheduled', None)  

#             if d:  # If update_object() returned an updated object
#                 d_list.append(d)

#         # Clean `d_list`
#         for d in d_list:
#             status = config.Status.completed if d.progress >= 100 else config.Status.cancelled
#             d.status = status
#             d.live_connections = 0

#         return d_list

#     except Exception as e:
#         log(f"Error loading downloads: {e}")
#         return []



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
                print('error save d_list:', e)
        #log('list saved')
    except Exception as e:
        handle_exceptions(e)


def load_setting():
    settings = {}
    try:
        log('Load Application setting from', config.sett_folder)
        file = os.path.join(config.sett_folder, 'setting.cfg')
        with open(file, 'r') as f:
            settings = json.load(f)

    except FileNotFoundError:
        log('setting.cfg not found')
    except Exception as e:
        handle_exceptions(e)
    finally:
        if not isinstance(settings, dict):
            settings = {}

        # update config module
        config.__dict__.update(settings)


# def save_setting():
#     settings = {key: config.__dict__.get(key) for key in config.settings_keys}

#     try:
#         file = os.path.join(config.sett_folder, 'setting.cfg')
#         with open(file, 'w') as f:
#             json.dump(settings, f)
#             #log('setting saved')
#     except Exception as e:
#         handle_exceptions(e)

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
