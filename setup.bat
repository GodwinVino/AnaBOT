@echo off
echo ============================================
echo   AnaBOT - First Time Setup
echo ============================================

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate it
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies (this may take a few minutes)...
pip install --upgrade pip
pip install -r backend\requirements.txt

REM Pre-download the embedding model
echo Pre-downloading embedding model...
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

REM Create folder structure
if not exist data\applications mkdir data\applications
if not exist vectorstore mkdir vectorstore

REM Copy .env to backend
copy .env backend\.env >nul

echo.
echo ============================================
echo   Setup complete! 
echo   1. Add your documents to data\applications\<AppName>\
echo   2. Run: run.bat
echo   3. Open: http://localhost:8000
echo ============================================
pause
