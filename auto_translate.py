

import os
import subprocess
import xml.etree.ElementTree as ET
import time
import re
import platform
from deep_translator import GoogleTranslator

# --- CONFIGURATION ---
if platform.system().lower() == "win":
    BASE_PATH = r"C:\Users\Annorion\Desktop\softenv\New-PyIDM\modules\translations"
else:
    BASE_PATH = "/home/annorion/Desktop/pyiconic/New-PyIDM/modules/translations"
    
LANGUAGES = ['en', 'fr', 'es', 'ja', 'ko', 'zh', 'hi']

# List all your UI and logic files here
UI_FILES = [
    "main.py",
    "ui/setting_dialog.py",
    "ui/add_downloads.py",
    "ui/queue_dialog.py",
    "ui/category_dialog.py",
    "ui/marketplace_dialog.py",
    "ui/download_window.py",
    "ui/advanced_metadata_dialog.py",
    "ui/about_dialog.py",
    "modules/video.py",
    "modules/updater.py",
]

# --- 1. SCANNING (lupdate) ---
def run_lupdate():
    print("\n--- [1/3] Scanning source files (lupdate) ---")
    ts_files = [os.path.join(BASE_PATH, "app_en.ts")]
    for lang in LANGUAGES:
        ts_files.append(os.path.join(BASE_PATH, f"app_{lang}.ts"))
    
    # Construct the command: pyside6-lupdate [files] -ts [ts_targets]
    cmd = ["pyside6-lupdate"] + UI_FILES + ["-ts"] + ts_files
    
    try:
        subprocess.run(cmd, check=True)
        print("Success: Source strings updated in .ts files.")
    except subprocess.CalledProcessError as e:
        print(f"Error during lupdate: {e}")

# --- 2. TRANSLATING (Logic from before) ---
def translate_text(text, lang_code):
    """Translates text and protects placeholders like %1 or %n."""
    try:
        target = 'zh-CN' if lang_code == 'zh' else lang_code
        translated = GoogleTranslator(source='auto', target=target).translate(text)
        
        # POST-PROCESS: Fix common Google Translate artifacts in placeholders
        # Fixes "% n" -> "%n", "% 1" -> "%1", etc.
        translated = re.sub(r'%\s?([n0-9])', r'%\1', translated)
        
        time.sleep(0.4) 
        return translated
    except Exception as e:
        print(f"Error translating '{text}': {e}")
        return None

def process_translations():
    print("\n--- [2/3] Translating strings with Correct Plural & Source Protection ---")
    for lang in LANGUAGES:
        # SKIP ENGLISH: We don't translate the source language!
        # if lang == 'en': 
        #     continue

        file_path = os.path.join(BASE_PATH, f"app_{lang}.ts")
        if not os.path.exists(file_path): continue

        tree = ET.parse(file_path)
        root = tree.getroot()
        changed = False

        for context in root.findall('context'):
            for message in context.findall('message'):
                source_elem = message.find('source')
                trans_elem = message.find('translation')
                
                if source_elem is None or trans_elem is None: continue
                if trans_elem.get('type') == 'vanished':
                    context.remove(message)
                    changed = True
                    continue

                source_text = source_elem.text or ""
                is_unfinished = trans_elem.get('type') == 'unfinished'

                # --- CORRECT PLURAL (NUMERUS) HANDLING ---
                if trans_elem.get('numerus') == 'yes':
                    # Crucial: The parent <translation> tag must have NO text content
                    # if it contains <numerusform> children.
                    if trans_elem.text:
                        trans_elem.text = None 
                        changed = True

                    forms = trans_elem.findall('numerusform')
                    for form in forms:
                        if not form.text or is_unfinished:
                            print(f"[{lang}] Translating Plural Form: {source_text}")
                            new_text = translate_text(source_text, lang)
                            if new_text:
                                form.text = new_text
                                changed = True
                    
                    if is_unfinished and changed:
                        trans_elem.attrib.pop('type', None)

                # --- STANDARD HANDLING ---
                else:
                    current_trans = trans_elem.text or ""
                    if (not current_trans or is_unfinished) and source_text:
                        print(f"[{lang}] Translating: {source_text}")
                        new_text = translate_text(source_text, lang)
                        if new_text:
                            trans_elem.text = new_text
                            trans_elem.attrib.pop('type', None)
                            changed = True

        if changed:
            # Use a more robust save to ensure XML declaration and encoding
            tree.write(file_path, encoding='utf-8', xml_declaration=True)
            print(f"Saved: {file_path}")

# --- 3. RELEASING (lrelease) ---
def run_lrelease():
    print("\n--- [3/3] Compiling to binary (lrelease) ---")
    # Release English
    subprocess.run(["pyside6-lrelease", os.path.join(BASE_PATH, "app_en.ts"), "-qm", os.path.join(BASE_PATH, "app_en.qm")])
    
    # Release Targets
    for lang in LANGUAGES:
        ts_path = os.path.join(BASE_PATH, f"app_{lang}.ts")
        qm_path = os.path.join(BASE_PATH, f"app_{lang}.qm")
        try:
            subprocess.run(["pyside6-lrelease", ts_path, "-qm", qm_path], check=True)
        except Exception as e:
            print(f"Failed to release {lang}: {e}")
    print("Success: All .qm files updated.")

if __name__ == "__main__":
    start_time = time.time()
    
    run_lupdate()
    process_translations()
    run_lrelease()
    
    end_time = time.time()
    print(f"\nDone! Entire workflow took {round(end_time - start_time, 2)} seconds.")