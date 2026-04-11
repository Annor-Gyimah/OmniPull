import xml.etree.ElementTree as ET
import os
import time
from deep_translator import GoogleTranslator

def translate_text(text, lang_code):
    """Uses deep-translator for stable, modern translation."""
    try:
        # Map ja to ja, ko to ko, hi to hi, etc.
        target = 'zh-CN' if lang_code == 'zh' else lang_code
        
        # Initialize translator for this specific target language
        translated = GoogleTranslator(source='auto', target=target).translate(text)
        time.sleep(0.2) # Slight delay to be safe
        return translated
    except Exception as e:
        print(f"Error translating '{text}': {e}")
        return None

def process_file_with_api(file_path, lang_code):
    """Cleans vanished blocks and fills unfinished/empty translations."""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    tree = ET.parse(file_path)
    root = tree.getroot()

    for context in root.findall('context'):
        messages = context.findall('message')
        for message in messages:
            source_elem = message.find('source')
            trans_elem = message.find('translation')
            
            if source_elem is None or trans_elem is None:
                continue

            # 1. Cleanup: Remove Vanished blocks
            if trans_elem.get('type') == 'vanished':
                context.remove(message)
                continue

            # 2. Translate: Fill empty or unfinished blocks
            source_text = source_elem.text or ""
            current_trans = trans_elem.text or ""
            is_unfinished = trans_elem.get('type') == 'unfinished'

            # Fix: Ensure we check current_trans and that the source isn't empty
            if (not current_trans or is_unfinished) and source_text:
                print(f"[{lang_code}] Translating: {source_text}")
                new_text = translate_text(source_text, lang_code)
                
                if new_text:
                    trans_elem.text = new_text
                    # Remove the 'unfinished' attribute so Qt accepts it
                    if 'type' in trans_elem.attrib:
                        del trans_elem.attrib['type']

    tree.write(file_path, encoding='utf-8', xml_declaration=True)
    print(f"Finished processing: {file_path}")

if __name__ == "__main__":
    base_path = r"C:\Users\Annorion\Desktop\softenv\New-PyIDM\modules\translations"
    
    # Language mapping
    files = {
        # 'en': 'app_en.ts',
        # 'fr': 'app_fr.ts',
        'es': 'app_es.ts',
        # 'ja': 'app_ja.ts',
        # 'ko': 'app_ko.ts',
        # 'zh': 'app_zh.ts',
        # 'hi': 'app_hi.ts' 
    }

    for lang, filename in files.items():
        full_path = os.path.join(base_path, filename)
        process_file_with_api(full_path, lang)