#!/bin/sh

# Clean and prepare folders
[ -e package ] && rm -r package
mkdir -p package/opt/omnipull
mkdir -p package/usr/share/applications
mkdir -p package/usr/share/icons/hicolor/scalable/apps

# Copy your PyInstaller binary
cp -r ../Lin_Exec/main package/opt/omnipull/

# ✅ Copy your static aria2c binary
cp ../Lin_Exec/aria2c package/opt/omnipull/aria2c
cp ../Lin_Exec/ffmpeg package/opt/omnipull/ffmpeg

# Copy icon and .desktop file
cp icons/logo1.png package/usr/share/icons/hicolor/scalable/apps/logo1.png
cp omnipull.desktop package/usr/share/applications

# Copy omnipull-watcher
cp ../Lin_Exec/omnipull-watcher package/opt/omnipull/omnipull-watcher


# Add the native messaging manifest
mkdir -p package/home/$USER/.config/google-chrome/NativeMessagingHosts
cp browser_extensions/chrome/com.omnipull.downloader.json package/home/$USER/.config/google-chrome/NativeMessagingHosts/com.omnipull.downloader.json



mkdir -p package/usr/lib/mozilla/native-messaging-hosts
cp browser_extensions/firefox/com.omnipull.downloader.json package/usr/lib/mozilla/native-messaging-hosts/com.omnipull.downloader.json


# Permissions
find package/opt/omnipull -type f -exec chmod 644 -- {} +
find package/opt/omnipull -type d -exec chmod 755 -- {} +
find package/usr/share -type f -exec chmod 644 -- {} +

# Make sure your main binary is executable
chmod +x package/opt/omnipull/main
chmod +x package/opt/omnipull/aria2c
chmod +x package/opt/omnipull/ffmpeg
chmod +x package/opt/omnipull/omnipull-watcher
chmod +x package/home/$USER/.config/google-chrome/NativeMessagingHosts/com.omnipull.downloader.json
chmod +x package/usr/lib/mozilla/native-messaging-hosts/com.omnipull.downloader.json


