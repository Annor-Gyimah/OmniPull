# OmniPull Download Manager

<p align="center">
    <img src="Windows/icons/logo1.png" alt="OmniPull Logo" width="200"/>
</p>

<div align="center">

![GitHub Release](https://img.shields.io/github/v/release/Annor-Gyimah/OmniPull)
![GitHub License](https://img.shields.io/github/license/Annor-Gyimah/OmniPull)

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
![GitHub Downloads (all assets, latest release)](https://img.shields.io/github/downloads/Annor-Gyimah/Li-Dl/latest/total)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/Annor-Gyimah/Li-Dl/total)

    
</div>

OmniPull is a powerful, cross-platform download manager built with Python and PySide6. It provides a modern, intuitive interface for managing downloads with advanced features like multi-threading, queue management, and media extraction.

### ✨ Wiki  

See [Wiki](https://github.com/Annor-Gyimah/OmniPull/wiki) for more information.


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

<!-- <p align="center">
    <img src="path_to_screenshots/queue_manager.png" alt="Queue Manager" width="400"/>
    <img src="path_to_screenshots/settings.png" alt="Settings Window" width="400"/>
</p> -->

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

OmniPull is cross-platform and runs on Windows, Linux and MacOS.

### 🪟 Windows Installation

You can [download the latest OmniPull installer for Windows](https://github.com/Annor-Gyimah/omnipull/releases) from the Releases section. Just run the installer and follow the on-screen instructions.

- After installation, launch OmniPull from the Start Menu or desktop shortcut.
- No additional configuration is needed. `aria2c` is included and ready to go.

---

### 🐧 Linux Installation

You can [download the latest OmniPull installer for Linux](https://github.com/Annor-Gyimah/omnipull/releases) from the Releases section. 

- Download the latest version for Linux either the AppImage or deb file.
- Change permissions of the appimage or dmg by using chmod.
- Run sudo command or double click to extract package and install.
- Summary
```bash
# deb
chmod +x omnipull*.deb

sudo dpkg -i omnipull*.deb

# for appimage
chmod +x omnipull*.appimage

./omnipull*.appimage
```



### 🖥️ MacOS Installation

You can [download the latest OmniPull installer for MacOS](https://github.com/Annor-Gyimah/omnipull/releases) from the Releases section. 

- After download of the latest version release, use xattr to relief it of the gatekeeper.
- Change permissions of the dmg by using chmod.
- Double click to then install by dragging the OmniPull to the application's folder and double click on the Browser connectors to install the them.
- Summary
```bash


```



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
- [ ] N/A

## 🤝 Contributing
Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License
This project is licensed under the GPLV3 License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author
Emmanuel Gyimah Annor

## 🙏 Acknowledgments
- PySide6 team for the amazing GUI framework
- aria2c developers for the download engine
- yt-dlp team for YouTube integration
- All contributors and users of OmniPull

<p align="center">Made with ❤️ by Emmanuel Gyimah Annor</p>
