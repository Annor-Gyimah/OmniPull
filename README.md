# OmniPull Download Manager

<p align="center">
    <img src="Windows/icons/logo1.png" alt="OmniPull Logo" width="200"/>
</p>

<div align="center">

[![Build Status](https://github.com/soimort/you-get/workflows/develop/badge.svg)](https://github.com/soimort/you-get/actions)

[![PyPI version](https://badge.fury.io/py/ytsage.svg)](https://badge.fury.io/py/ytsage)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://static.pepy.tech/badge/ytsage)](https://pepy.tech/project/ytsage)
[![Total Downloads](https://static.pepy.tech/badge/ytsage/month)](https://pepy.tech/project/ytsage)
    
</div>

OmniPull is a powerful, cross-platform download manager built with Python and PySide6. It provides a modern, intuitive interface for managing downloads with advanced features like multi-threading, queue management, and media extraction.

<p align="center">
    <img src="Windows/icons/screenshot.png" alt="Main Window" width="800"/>
</p>

## 🚀 Key Feature

### Core Functionality
- **Multi-threaded Downloads**: Accelerate downloads with parallel processing
- **Pause/Resume Support**: Continue downloads from where they left off
- **Queue Management**: Organize and prioritize downloads
- **Scheduling System**: Set specific times for downloads to start
- **Browser Integration**: Direct download capture from browsers

### Media Features
- **YouTube Integration**: Download videos and playlists via yt-dlp
- **Streaming Support**: Handle various streaming protocols (HLS, DASH)
- **Audio Extraction**: Extract audio from video content
- **Format Selection**: Choose from multiple quality options

### User Experience
- **Modern UI**: Clean, intuitive interface with dark theme
- **Progress Monitoring**: Real-time download statistics
- **Download Windows**: Detailed progress for each download
- **Clipboard Monitoring**: Auto-detect URLs from clipboard
- **Multiple Language Support**: Internationalization ready

<p align="center">
    <img src="path_to_screenshots/queue_manager.png" alt="Queue Manager" width="400"/>
    <img src="path_to_screenshots/settings.png" alt="Settings Window" width="400"/>
</p>

## 🛠️ Technical Features

### Download Engines
- **Aria2c Integration**: High-performance download engine
- **Native Downloader**: Built-in download capabilities
- **yt-dlp Support**: Advanced media extraction

### Performance
- **Segmented Downloads**: Split large files for faster downloading
- **Smart Queuing**: Efficient download queue management
- **Resource Management**: Optimize system resource usage

### File Management
- **Checksum Verification**: Ensure file integrity
- **Auto-Resume**: Recover from interrupted downloads
- **File Organization**: Customizable download locations



## 📦 Installation

OmniPull is cross-platform and runs on Windows and Linux.

### 🪟 Windows Installation

You can [download the latest OmniPull installer for Windows](https://github.com/Annor-Gyimah/omnipull/releases) from the Releases section. Just run the installer and follow the on-screen instructions.

- After installation, launch OmniPull from the Start Menu or desktop shortcut.
- No additional configuration is needed. `aria2c` is included and ready to go.

---

### 🐧 Linux Installation

See the full instructions in the [Linux README](Linux/README.linux.md) to learn how to:

- Build and run the app on Debian-based systems
- Bundle `aria2c` into the package
- Create a `.deb` installer with `fpm`

### Script Kiddies

```bash
# Clone the repository
git clone https://github.com/yourusername/omnipull.git

# Navigate to the project directory
cd omnipull

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

```



## 🌐 Browser Integration
OmniPull integrates with major browsers through extensions:
- Chrome/Edge
- Firefox
- Opera

## 🎯 Upcoming Features
- [ ] Cloud storage integration
- [ ] Advanced download scheduling
- [ ] Browser extension improvements
- [ ] More language support
- [ ] Enhanced media processing

## 🤝 Contributing
Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author
Emmanuel Gyimah Annor

## 🙏 Acknowledgments
- PySide6 team for the amazing GUI framework
- aria2c developers for the download engine
- yt-dlp team for YouTube integration
- All contributors and users of OmniPull

<p align="center">Made with ❤️ by Emmanuel Gyimah Annor</p>
