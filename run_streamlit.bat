@echo off
cd /d "%~dp0"
python -m pip install -r requirements_streamlit.txt
python -m streamlit run streamlit_app.py
pause
