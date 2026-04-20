@echo off
setlocal

cd /d "%~dp0"

echo Starting FastAPI backend on http://127.0.0.1:8000 ...
start "AI SQL Copilot - Backend" /D "%~dp0" cmd /k python -m uvicorn main:app --port 8000

echo Starting Streamlit UI on http://localhost:8503 ...
start "AI SQL Copilot - Streamlit" /D "%~dp0" cmd /k python -m streamlit run streamlit_app.py --server.port 8503

echo.
echo Both services were launched in separate windows.
echo Open this URL in browser: http://localhost:8503
echo If one window shows an error, install missing packages with:
echo python -m pip install -r requirements.txt

endlocal
