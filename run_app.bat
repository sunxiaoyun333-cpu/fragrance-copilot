@echo off
cd /d D:\yunyunni\tiktok-marketing-tool

D:\python.exe -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo Streamlit not found. Installing project dependencies...
    D:\python.exe -m pip install -r requirements.txt
)

D:\python.exe -m streamlit run app.py --browser.gatherUsageStats false
if errorlevel 1 pause
