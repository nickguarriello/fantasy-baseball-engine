@echo off
REM ============================================================
REM  Fantasy Baseball Daily Pipeline
REM  Runs every morning via Windows Task Scheduler
REM  - Fetches fresh MLB + ESPN data
REM  - Recalculates all z-scores
REM  - Generates docs/index.html
REM  - Pushes to GitHub (GitHub Pages auto-updates)
REM ============================================================

SET PROJECT=C:\Users\nickg\FANTASY-BASEBALL-PROJECT\fantasy-baseball-engine
SET PYTHON=C:\Users\nickg\AppData\Local\Microsoft\WindowsApps\python.exe
SET GIT="C:\Program Files\Git\mingw64\bin\git.exe"
SET LOG=%PROJECT%\logs\daily_run.log

REM Create logs directory if needed
if not exist "%PROJECT%\logs" mkdir "%PROJECT%\logs"

echo ============================================================ >> "%LOG%"
echo  Run started: %DATE% %TIME% >> "%LOG%"
echo ============================================================ >> "%LOG%"

REM Step 1: Run the pipeline
cd /d "%PROJECT%"
"%PYTHON%" -X utf8 main.py >> "%LOG%" 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo  PIPELINE FAILED — see log >> "%LOG%"
    exit /b 1
)

REM Step 2: Stage the updated report
%GIT% add docs/index.html >> "%LOG%" 2>&1

REM Step 3: Commit with today's date
FOR /F "tokens=1-3 delims=/ " %%a IN ("%DATE%") DO SET TODAY=%%c-%%a-%%b
%GIT% commit -m "Daily update %TODAY%" >> "%LOG%" 2>&1

REM Step 4: Push to GitHub
%GIT% push origin main >> "%LOG%" 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo  GIT PUSH FAILED — see log >> "%LOG%"
    exit /b 1
)

echo  Done: %TIME% >> "%LOG%"
exit /b 0
