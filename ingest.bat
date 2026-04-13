@echo off
echo ============================================
echo   AnaBOT - Document Ingestion
echo ============================================

call venv\Scripts\activate.bat

if "%1"=="" (
    echo Usage: ingest.bat ^<ApplicationName^>
    echo Example: ingest.bat IBIS
    echo.
    echo Available applications:
    dir /b data\applications
    pause
    exit /b 1
)

echo Ingesting documents for: %1
cd backend
python -c "
from app.services.ingest_service import IngestService
svc = IngestService()
result = svc.ingest('%1')
print(f'Done: {result}')
"
pause
