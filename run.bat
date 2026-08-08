@echo off

echo ========================================
echo  LAMDAG — Lesson Plan Generator
echo ========================================
echo.
echo Starting LAMDAG Lesson Plan Generator...
echo.
echo Note: This application requires Python 3.12 or higher with the required packages installed.
echo If Python is not installed, please install it from https://www.python.org/downloads/
echo.
echo Installing required packages...
echo.
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo Starting Flask server...
echo Open http://127.0.0.1:5000 in your browser
echo Press Ctrl+C to stop the server
echo.
".venv\Scripts\python.exe" app.py

pause
