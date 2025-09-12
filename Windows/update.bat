@echo off
SETLOCAL ENABLEEXTENSIONS
SET SOURCE_FILE=%1
SET DESTINATION_DIR=C:\Program Files\Annorion\OmniPull\
SET LOG_FILE=C:\update_success.txt
SET TEMP_DIR=%~dp0  
REM This gets the directory of the running script

echo Starting update process... >> "%LOG_FILE%"

REM Check if the source file exists
IF EXIST "%SOURCE_FILE%" (
    echo Source file found at %SOURCE_FILE% >> "%LOG_FILE%"
    
    REM Create the destination directory if it does not exist
    IF NOT EXIST "%DESTINATION_DIR%" (
        mkdir "%DESTINATION_DIR%"
    )

    REM Copy the source file to the destination directory
    copy /Y "%SOURCE_FILE%" "%DESTINATION_DIR%\main.exe" >> "%LOG_FILE%" 2>&1
    IF %ERRORLEVEL% EQU 0 (
        echo Update completed successfully at %DATE% %TIME% >> "%LOG_FILE%"
    ) ELSE (
        echo Failed to copy the file. >> "%LOG_FILE%"
        exit /b 1
    )
) ELSE (
    echo Source file not found: %SOURCE_FILE% >> "%LOG_FILE%"
    exit /b 1
)


REM Now delete the temporary directory
rd /s /q "%SOURCE_FILE%"
echo Temporary directory deleted. >> "%LOG_FILE%"
