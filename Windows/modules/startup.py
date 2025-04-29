import platform
import os
import sys
from Os import OS

home_address = os.path.expanduser("~")

# finding os_type
os_type = platform.system()

if os_type == OS.WINDOWS:
    import winreg


# check startup
def checkStartUp():
    # check if it is linux
    if os_type in OS.UNIX_LIKE:
        # check if the startup exists
        if os.path.exists(home_address + "/.config/autostart/main.desktop"):
            return True
        else:
            return False

    # check if it is mac
    elif os_type == OS.OSX:
        # OS X
        if os.path.exists(home_address + "/Library/LaunchAgents/com.main.plist"):
            return True
        else:
            return False

    # check if it is Windows
    elif os_type == OS.WINDOWS:
        # try to open startup key and check dynamite value
        try:
            aKey = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_ALL_ACCESS)
            startupvalue = winreg.QueryValueEx(aKey, 'main')
            startup = True
        except WindowsError:
            startup = False

        # Close the connection
        winreg.CloseKey(aKey)

        # if the startup enabled or disabled
        if startup:
            return True
        if not startup:
            return False

# add startup file


def addStartUp():
    # check if it is linux
    if os_type in OS.UNIX_LIKE:
        entry = '''
[Desktop Entry]
Name=Dynamite Download Manager
Comment=Download Manager
GenericName=Download Manager
Keywords=Internet;WWW;Web;
Terminal=false
Type=Application
Categories=Qt;Network;
StartupNotify=true
Exec=/opt/main/main --tray
Icon=Dynamite
Path=/opt/main
        '''

        # check if the autostart directory exists & create entry
        if not os.path.exists(home_address + "/.config/autostart"):
            os.makedirs(home_address + "/.config/autostart", 0o755)
        startupfile = open(
            home_address + "/.config/autostart/main.desktop", 'w+')
        startupfile.write(entry)
        os.chmod(home_address
                 + "/.config/autostart/main.desktop", 0o644)

    # check if it is mac
    elif os_type == OS.OSX:
        # OS X
        cwd = sys.argv[0]
        cwd = os.path.dirname(cwd)
        entry = '''
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
            <dict>
                <key>Label</key>
                <string>com.persepolisdm.persepolis</string>
                <key>Program</key>
                <string>{}</string>
                <key>ProgramArguments</key>
                <array>
                    <string>--tray</string>
                </array>
                <key>RunAtLoad</key>
                <true/>
            </dict>
            </plist>\n
        '''

        startupfile = open(
            home_address + '/Library/LaunchAgents/com.main.plist', 'w+')
        startupfile.write(entry)
        os.system('launchctl load ' + home_address
                  + "/Library/LaunchAgents/com.main.plist")

    # check if it is Windows
    elif os_type == OS.WINDOWS:

        # Connect to the startup path in Registry
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_ALL_ACCESS)
        # find current dynamite exe path
        persepolisexetray = '"{}" --tray'#.format(parent.exec_dictionary['exec_file_path'])

        # add dynamite to startup
        winreg.SetValueEx(key, 'main', 0,
                          winreg.REG_SZ, persepolisexetray)

        # Close connection
        winreg.CloseKey(key)


# remove startup file
def removeStartUp():
    # check if it is linux
    if os_type in OS.UNIX_LIKE:
        # remove it
        os.remove(home_address + "/.config/autostart/main.desktop")

    # check if it is mac OS
    elif os_type == OS.OSX:
        # OS X
        if checkStartUp():
            os.system('launchctl unload ' + home_address
                      + "/Library/LaunchAgents/com.main.plist")
            os.remove(home_address
                      + "/Library/LaunchAgents/com.main.plist")

    # check if it is Windows
    elif os_type == OS.WINDOWS:
        if checkStartUp():
            # Connect to the startup path in Registry
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_ALL_ACCESS)

            # remove dynamite from startup
            winreg.DeleteValue(key, 'main')

            # Close connection
            winreg.CloseKey(key)
