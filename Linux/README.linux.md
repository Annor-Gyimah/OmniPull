
# 🐧 OmniPull on Linux (Debian/Ubuntu)

This guide explains how to build, bundle, and package OmniPull for Debian-based Linux systems.

---

## 🧰 Prerequisites

Install the required tools:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv build-essential fpm gettext \
    autoconf automake libtool libxml2-dev libssl-dev libsqlite3-dev \
    libcppunit-dev zlib1g-dev libssh2-1-dev libc-ares-dev
```

---

## ⚙️ Step 1: Build the App with PyInstaller

1. Install PyInstaller:

```bash
pip install pyinstaller
```

2. Generate a standalone binary:

```bash
pyinstaller --noconfirm --onefile --name=main main.py
```

3. The binary will be in `dist/main`.

---

## ⚙️ Step 2: Build `aria2c` (Static Binary)

```bash
git clone https://github.com/aria2/aria2.git
cd aria2
autoreconf -i
./configure --enable-static --disable-shared
make -j$(nproc)
strip src/aria2c
```

Copy `aria2c` from `src/aria2c` into your build folder.

---

## 🧱 Step 3: Package App with FPM

1. Prepare directory structure:

```bash
./package.sh
```

> This copies your `main` binary, desktop file, icons, and `aria2c` into `/opt/omnipull/`

2. Create the `.deb` package:

```bash
./build.sh
```

3. Install the package:

```bash
sudo dpkg -i omnipull_v_1.2.24.deb
```

---

## 🧪 Test the Installation

```bash
/opt/omnipull/main
```

To verify `aria2c` is included and working:

```bash
/opt/omnipull/aria2c --version
```

---

## 🐞 Troubleshooting

- If you get `PermissionError: ... /opt/omnipull/aria2c`, make sure it's executable:
```bash
sudo chmod +x /opt/omnipull/aria2c
```

- If OmniPull appears in the wrong menu category, edit the `Categories=` in the `.desktop` file.

---

## ✅ Tips

- Use `strip aria2c` to reduce binary size (~93 MB → ~3–30 MB)
- Use `Categories=Network;FileTransfer;DownloadManager;` in `.desktop` files
- To update icons: `sudo gtk-update-icon-cache /usr/share/icons/hicolor`

---

Made with ❤️ for Linux users. Feedback and PRs are welcome!
