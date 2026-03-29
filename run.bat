@echo off
echo Installing required packages...
pip install -r requirements.txt
echo.
echo Starting OlderCare App...
python Main.py
pause
