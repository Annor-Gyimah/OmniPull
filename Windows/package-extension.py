import os
import zipfile
import struct
import subprocess

EXT_DIR = 'extension'
KEY_FILE = 'pyiconic-key.pem'
PUB_KEY = 'pyiconic-pub.der'
ZIP_NAME = 'pyiconic.zip'
CRX_NAME = 'pyiconic.crx'

# Step 1: Create ZIP of extension files
def create_zip():
    with zipfile.ZipFile(ZIP_NAME, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(EXT_DIR):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, EXT_DIR)
                zipf.write(full_path, rel_path)
    print("✅ Created:", ZIP_NAME)

# Step 2: Sign the ZIP file with OpenSSL
def sign_zip():
    cmd = [
        'openssl', 'sha1', '-sign', KEY_FILE, '-out', 'sig',
        ZIP_NAME
    ]
    subprocess.run(cmd, check=True)
    print("🔏 Signed ZIP → sig")

# Step 3: Build CRX (v2 format)
def build_crx():
    with open('sig', 'rb') as f:
        sig = f.read()
    with open(PUB_KEY, 'rb') as f:
        pub = f.read()
    with open(ZIP_NAME, 'rb') as f:
        zip_data = f.read()

    # CRX header:
    # 4 bytes: magic 'Cr24'
    # 4 bytes: version (2)
    # 4 bytes: pub key length
    # 4 bytes: sig length
    header = b'Cr24' + struct.pack('<III', 2, len(pub), len(sig))

    with open(CRX_NAME, 'wb') as f:
        f.write(header)
        f.write(pub)
        f.write(sig)
        f.write(zip_data)

    print(f"📦 Created CRX: {CRX_NAME}")

if __name__ == "__main__":
    create_zip()
    sign_zip()
    build_crx()
