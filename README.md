<!-- MANPAGE: BEGIN EXCLUDED SECTION -->
<div align="center">

[![OmniPull](https://i.stack.imgur.com/TOfqL.png)](#readme)

[![GitHub release](https://img.shields.io/github/v/release/Annor-Gyimah/OmniPull?color=brightgreen&label=Download&style=for-the-badge)](#installation)
[![License](https://img.shields.io/github/license/Annor-Gyimah/OmniPull?color=blue&style=for-the-badge)](LICENSE)
[![Total Downloads](https://img.shields.io/github/downloads/Annor-Gyimah/OmniPull/total?color=orange&style=for-the-badge)](https://github.com/Annor-Gyimah/OmniPull/releases)
[![Stars](https://img.shields.io/github/stars/Annor-Gyimah/OmniPull?color=yellow&style=for-the-badge)](https://github.com/Annor-Gyimah/OmniPull/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/Annor-Gyimah/OmniPull?color=grey&style=for-the-badge)](https://github.com/Annor-Gyimah/OmniPull/commits)

</div>
<!-- MANPAGE: END EXCLUDED SECTION -->

OmniPull is a powerful, cross-platform download manager built with Python and PySide6. It provides a modern, intuitive interface for managing downloads with advanced features like multi-threading, queue management, scheduling, browser integration, and media extraction from popular video platforms.

<!-- MANPAGE: MOVE "USAGE AND OPTIONS" SECTION HERE -->

<!-- MANPAGE: BEGIN EXCLUDED SECTION -->
* [INSTALLATION](#installation)
    * [Windows](#windows)
    * [Linux](#linux)
    * [macOS](#macos)
    * [Building from Source](#building-from-source)
* [FEATURES](#features)
    * [Core Download Management](#core-download-management)
    * [Media & Streaming](#media--streaming)
    * [Browser Integration](#browser-integration)
    * [User Experience](#user-experience)
    * [Advanced Features](#advanced-features)
* [SUPPORTED PLATFORMS](#supported-platforms)
* [SUPPORTED PROTOCOLS](#supported-protocols)
* [USAGE](#usage)
    * [Basic Download](#basic-download)
    * [YouTube Download](#youtube-download)
    * [Queue Management](#queue-management)
    * [Browser Integration](#browser-integration-1)
* [CONFIGURATION](#configuration)
    * [Settings Location](#settings-location)
    * [Key Settings](#key-settings)
* [COMMAND LINE OPTIONS](#command-line-options)
* [TECHNICAL DETAILS](#technical-details)
    * [Download Engines](#download-engines)
    * [Architecture](#architecture)
* [CONTRIBUTING](#contributing)
* [REPORTING ISSUES](#reporting-issues)
* [CHANGELOG](#changelog)
* [LICENSE](#license)
* [ACKNOWLEDGMENTS](#acknowledgments)
* [SUPPORT](#support)
<!-- MANPAGE: END EXCLUDED SECTION -->

# INSTALLATION

<!-- MANPAGE: BEGIN EXCLUDED SECTION -->
[![Windows](https://img.shields.io/badge/-Windows_10/11-blue.svg?style=for-the-badge&logo=windows)](#windows)
[![Linux](https://img.shields.io/badge/-Linux-red.svg?style=for-the-badge&logo=linux)](#linux)
[![macOS](https://img.shields.io/badge/-macOS-lightblue.svg?style=for-the-badge&logo=apple)](#macos)
[![Source](https://img.shields.io/badge/-Source-green.svg?style=for-the-badge)](#building-from-source)
[![All Versions](https://img.shields.io/badge/-All_Versions-lightgrey.svg?style=for-the-badge)](https://github.com/Annor-Gyimah/OmniPull/releases)
<!-- MANPAGE: END EXCLUDED SECTION -->

You can download OmniPull for Windows, Linux, or macOS from the [Releases](https://github.com/Annor-Gyimah/OmniPull/releases) page.

---

### Windows

Download the latest OmniPull from the [Releases](https://github.com/Annor-Gyimah/OmniPull/releases) page.

**Recommended: Direct Download Links**
| File | Description |
|:---|:---
| [OmniPull-Setup-x64.exe](https://github.com/Annor-Gyimah/OmniPull/releases/latest/download/OmniPull-Setup-x64.exe) | Windows x64 Installer |
| [OmniPull-Portable.zip](https://github.com/Annor-Gyimah/OmniPull/releases/latest/download/OmniPull-Portable.zip) | Windows Portable Version |

After installation, launch OmniPull from the Start Menu or desktop shortcut. No additional configuration is needed. `aria2c` is included and ready to go.

---

### Linux

| File | Description |
|:---|:---
| [OmniPull-x.x.x.AppImage](https://github.com/Annor-Gyimah/OmniPull/releases/latest/download/OmniPull-x.x.x.AppImage) | AppImage (Recommended) |
| [omnipull_x.x.x_amd64.deb](https://github.com/Annor-Gyimah/OmniPull/releases/latest/download/omnipull_x.x.x_amd64.deb) | DEB Package |

```bash
# AppImage
wget https://github.com/Annor-Gyimah/OmniPull/releases/latest/download/OmniPull-x.x.x.AppImage
chmod +x OmniPull-x.x.x.AppImage
./OmniPull-x.x.x.AppImage

# DEB Package
wget https://github.com/Annor-Gyimah/OmniPull/releases/latest/download/omnipull_x.x.x_amd64.deb
sudo dpkg -i omnipull_x.x.x_amd64.deb
sudo apt-get install -f  # Fix any missing dependencies
```

---

### macOS

| File | Description |
|:---|:---
| [OmniPull-x.x.x.dmg](https://github.com/Annor-Gyimah/OmniPull/releases/latest/download/OmniPull-x.x.x.dmg) | Intel Mac |
| [OmniPull-arm64-x.x.x.dmg](https://github.com/Annor-Gyimah/OmniPull/releases/latest/download/OmniPull-arm64-x.x.x.dmg) | Apple Silicon Mac |

```bash
# Mount and drag to Applications
hdiutil mount OmniPull-x.x.x.dmg
cp -R /Volumes/OmniPull/OmniPull.app /Applications/

# Or via terminal
hdiutil attach OmniPull-x.x.x.dmg
cp -R /Volumes/OmniPull/OmniPull.app /Applications/
hdiutil detach /Volumes/OmniPull
```

---

### Building from Source

```bash
# Clone the repository
git clone https://github.com/Annor-Gyimah/OmniPull.git
cd OmniPull

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

**Requirements:**
- Python 3.10+
- PySide6
- yt-dlp
- aria2c (optional, for enhanced downloads)
- ffmpeg (optional, for media conversion)

---

# FEATURES

## Core Download Management

- **Multi-threaded Downloads**: Accelerate downloads with parallel connections (up to 16 segments)
- **Pause/Resume Support**: Continue downloads from where they left off after interruptions
- **Queue Management**: Organize, prioritize, and manage multiple download batches
- **Batch Downloads**: Import multiple URLs from files or clipboard
- **Scheduling System**: Set specific times for downloads to start automatically
- **Category Organization**: Organize downloads into custom categories

## Media & Streaming

- **YouTube Integration**: Download videos, playlists, and channels via yt-dlp
- **Platform Support**: Downloads from 1700+ websites including YouTube, Vimeo, TikTok, Instagram, and more
- **Streaming Protocols**: Full support for HLS, DASH, and HTTP streaming
- **Audio Extraction**: Extract audio from video content in MP3, AAC, FLAC, and other formats
- **Quality Selection**: Choose from multiple quality options (1080p, 4K, best available, etc.)
- **Subtitle Download**: Auto-fetch subtitles in multiple languages
- **Thumbnail Embedding**: Embed video thumbnails into downloaded files

## Browser Integration

- **Chrome/Edge Extension**: Capture downloads directly from Chrome-based browsers
- **Firefox Extension**: Native Firefox support
- **Opera Integration**: Full Opera browser integration
- **Clipboard Monitoring**: Auto-detect and add URLs copied to clipboard

## User Experience

- **Modern Dark UI**: Clean, intuitive PySide6 interface with dark theme
- **System Tray**: Background operation with tray icon
- **Progress Monitoring**: Real-time download statistics with speed graphs
- **Download Windows**: Detailed progress for each active download
- **Drag & Drop**: Drag URLs directly into the application
- **Internationalization**: Ready for multiple language translations

## Advanced Features

- **Checksum Verification**: MD5, SHA-256 integrity checks
- **Auto-Retry**: Automatic resume on connection failures
- **Custom Headers**: Support for custom HTTP headers
- **Cookie Import**: Import authentication cookies from browsers
- **Proxy Support**: HTTP, HTTPS, SOCKS4, and SOCKS5 proxy support
- **User Agent**: Customizable user agents
- **Speed Limiting**: Throttle download speeds

---

## Screenshots

| ![Main Window][01] | ![Downloads Queue][02] | ![Settings][03] |
|:---:|:---:|:---:|
| Main Window | Downloads Queue | Settings |
| ![Add Download][04] | ![Queue Manager][05] | ![Scheduler][06] |
| Add Downloads | Queue Manager | Scheduler |

---

# SUPPORTED PLATFORMS

OmniPull runs on:
- **Windows 10/11** (64-bit) - Primary platform with installer
- **Linux** - AppImage and DEB packages
- **macOS** - DMG packages (Intel and Apple Silicon)

---

# SUPPORTED PROTOCOLS

- HTTP, HTTPS, FTP, FTPS
- HTTP Range requests for resumed downloads
- MPEG-DASH streaming
- Apple HLS streaming
- Adobe HDS streaming
- RTMP/RTMPT streaming
- BitTorrent (via external tools)

---

# USAGE

## Basic Download

1. Click "Add Download" or paste a URL
2. Configure download options (location, threads, etc.)
3. Click "Start" to begin downloading

## YouTube Download

1. Paste a YouTube/video URL
2. Select quality and format
3. Click "Download"

## Queue Management

1. Create a new queue via "Queue" → "New Queue"
2. Add downloads to the queue
3. Configure scheduling options
4. Start the queue

## Browser Integration

1. Install the browser extension (Chrome/Firefox)
2. Configure the listening port in OmniPull settings
3. Downloads from the browser will automatically be captured

---

# CONFIGURATION

## Settings Location

- **Windows**: `%APPDATA%\OmniPull\`
- **Linux**: `~/.config/OmniPull/`
- **macOS**: `~/Library/Application Support/OmniPull/`

## Key Settings

| Setting | Description | Default |
|---------|------------|--------|
| Download Directory | Default save location | User's Downloads |
| Max Connections | Parallel segments (1-16) | 8 |
| Speed Limit | KB/s (0 = unlimited) | 0 |
| Proxy | Proxy server URL | None |
| Auto Retry | Retry count on failure | 5 |

---

# COMMAND LINE OPTIONS

```bash
python main.py [OPTIONS]

Options:
  --url TEXT         Add URL to download immediately
  --category TEXT    Category for the download
  --threads N        Number of connection threads
  --output PATH     Output directory
  --quiet           Start minimized to tray
  --help            Show this help message
```

---

# TECHNICAL DETAILS

## Download Engines

OmniPull supports multiple download engines:

1. **Native Engine** - Built-in Python downloader with multi-threading
2. **Aria2c** - High-performance C download engine (recommended for large files)
3. **yt-dlp** - Media extraction for video platforms

## Architecture

```
┌─────────────────────────────────────────────┐
│              UI Layer (PySide6)             │
├─────────────────────────────────────────────┤
│           Business Logic (Python)          │
├─────────────────────────────────────────────┤
│   Download Engines │ Video │ Settings │ DB │
├─────────────────────────────────────────────┤
│            System Integration               │
└─────────────────────────────────────────────┘
```

Downloads and settings are stored in SQLite database for reliability and cross-session persistence.

---

# CONTRIBUTING

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

# REPORTING ISSUES

If you encounter any bugs or have feature requests:
1. Check if the issue [already exists](https://github.com/Annor-Gyimah/OmniPull/issues)
2. Create a new issue with detailed information
3. Include log files and screenshots if applicable

---

# CHANGELOG

See [ChangeLog.txt](ChangeLog.txt) for the complete version history.

---

# LICENSE

This project is licensed under the **GPLv3 License** - see the [LICENSE](LICENSE) file for details.

---

# ACKNOWLEDGMENTS

- [PySide6](https://www.pyside.org/) - For the amazing Qt Python bindings
- [aria2c](https://aria2.github.io/) - High-performance download engine
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube/media downloader
- All contributors and users of OmniPull

---

# SUPPORT

If you find OmniPull useful, please consider:
- Starring the repository
- Reporting bugs and feature requests
- Contributing to the project

<p align="center">Made with ❤️ by Emmanuel Gyimah Annor</p>

<!-- Image Links -->
[//]: # (Screenshot Links)
[01]: https://i.stack.imgur.com/TOfqL.png
[02]: https://i.stack.imgur.com/TOfqL.png
[03]: https://i.stack.imgur.com/TOfqL.png
[04]: https://i.stack.imgur.com/TOfqL.png
[05]: https://i.stack.imgur.com/TOfqL.png
[06]: https://i.stack.imgur.com/TOfqL.png