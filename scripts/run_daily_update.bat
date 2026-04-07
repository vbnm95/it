@echo off
cd /d "%~dp0"
call "%~dp0\.venv\Scripts\activate.bat"
python "%~dp0daily_update.py" --verbose