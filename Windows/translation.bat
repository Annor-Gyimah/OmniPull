@echo off
set LANGUAGES=fr es ja ko zh hi

for %%L in (%LANGUAGES%) do (
    pyside6-lupdate main.py ui/setting_dialog.py ui/queue_dialog.py ui/user_guide_dialog.py modules/updater.py -ts modules/translations/app_en.ts modules/translations/app_%%L.ts
    pyside6-lrelease modules/translations/app_%%L.ts -qm modules/translations/app_%%L.qm
)

pyside6-lrelease modules/translations/app_en.ts -qm modules/translations/app_en.qm

@echo Translation completed.
pause
