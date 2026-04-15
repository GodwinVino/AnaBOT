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

echo.
echo NOTE: For image OCR support, Tesseract must be installed separately.
echo   Download: https://github.com/UB-Mannheim/tesseract/wiki
echo   After install, add Tesseract to your PATH or set in .env:
echo   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
echo   (OCR is optional — PPT and other file types work without it)

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
