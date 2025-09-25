@echo off
setlocal enableextensions

rem ===== Config =====
set "APP_NAME=OmniPull"
set "DEST_DIR=C:\Program Files\Annorion\OmniPull"
set "APP_EXE=main.exe"
set "LOG_DIR=%ProgramData%\Annorion\%APP_NAME%"
set LOG_FILE=C:\update_success.txt
SET HOME_DIR=%USERPROFILE%

rem ==================

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

set "SOURCE_FILE=%~f1"
set "PAYLOAD_DIR=%~f2"
set "SELF_BAT=%~f0"

>>"%LOG_FILE%" echo [%date% %time%] --- One-shot update started ---
>>"%LOG_FILE%" echo Runner=%USERNAME% WhoAmI=%COMPUTERNAME%\%USERNAME%
>>"%LOG_FILE%" echo SOURCE_FILE=%SOURCE_FILE%
>>"%LOG_FILE%" echo PAYLOAD_DIR=%PAYLOAD_DIR%

if not exist "%SOURCE_FILE%" (
  >>"%LOG_FILE%" echo ERROR: Source file not found.
  exit /b 1
)

if not exist "%DEST_DIR%" (
  mkdir "%DEST_DIR%" 2>>"%LOG_FILE%"
)

rem Try to skip if app is running
tasklist /FI "IMAGENAME eq %APP_EXE%" | find /I "%APP_EXE%" >nul
if %errorlevel%==0 (
  >>"%LOG_FILE%" echo App running; skipping update politely.
  goto :cleanup
)

>>"%LOG_FILE%" echo Copying "%SOURCE_FILE%" to "%DEST_DIR%\%APP_EXE%"
copy /Y "%SOURCE_FILE%" "%DEST_DIR%\%APP_EXE%" >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
  >>"%LOG_FILE%" echo ERROR: Copy failed.
  exit /b 1
)

>>"%LOG_FILE%" echo Update OK.

:cleanup
rem Defer deletion of payload dir and this .bat using a detached PowerShell
rem Delay a bit so this script can exit before files are removed.
for /d %%G in ("%HOME_DIR%\.update_tmp_*") do (
    rd /s /q "%%G"
)
>>"%LOG_FILE%" echo [%date% %time%] Cleanup scheduled. Exiting.
exit /b 0
