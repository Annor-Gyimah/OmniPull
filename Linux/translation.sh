#!/bin/bash

# Define the list of languages
LANGUAGES=("fr" "es" "ja" "ko" "zh" "hi")

# Update and compile translations for each language
for LANG in "${LANGUAGES[@]}"; do
    pyside6-lupdate main.py ui/setting_dialog.py ui/queue_dialog.py ui/user_guide_dialog.py modules/update.py  \
        -ts modules/translations/app_en.ts modules/translations/app_"$LANG".ts

    pyside6-lrelease modules/translations/app_"$LANG".ts -qm modules/translations/app_"$LANG".qm
done

# Compile the English translation separately
pyside6-lrelease modules/translations/app_en.ts -qm modules/translations/app_en.qm

echo "Translation completed."
read -p "Press enter to continue..."
