@echo off
echo ============================================
echo    AnaBOT - Starting Server
echo ============================================

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Copy .env to backend if not present
if not exist backend\.env (
    copy .env backend\.env >nul
)

REM Start FastAPI server
echo Starting backend on http://localhost:8000
echo Frontend available at http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.
cd backend
python main.py
