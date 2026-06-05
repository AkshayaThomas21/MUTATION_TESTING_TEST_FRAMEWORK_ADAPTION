@echo off
REM Launch the Area-2 Quality Signal Dashboard (offline demo works out of the box).
cd /d "%~dp0"
echo Starting Mutation Testing Quality Signal Dashboard...
streamlit run dashboard/app.py
