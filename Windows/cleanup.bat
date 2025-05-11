@echo off
SET TEMP_DIR=%1

:: Remove the specified temporary directory
rd /s /q "%TEMP_DIR%"

:: Define the user's home directory
SET HOME_DIR=%USERPROFILE%

:: Delete all directories with the prefix ".update_tmp_" in the user's home directory
for /d %%G in ("%HOME_DIR%\.update_tmp_*") do (
    rd /s /q "%%G"
)

echo Cleanup completed.
