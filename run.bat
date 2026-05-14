@echo off
echo Installing dependencies...
pip install -r requirements.txt --quiet
echo.
echo Starting OmniQuant Trading Dashboard...
echo Open http://localhost:8501 in your browser
echo.
streamlit run app.py
pause
