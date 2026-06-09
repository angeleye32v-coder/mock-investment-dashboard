@echo off
cd /d D:\AI\mock-investment-dashboard
powershell -Command "Start-Process 'C:\Users\Jane.Kim\AppData\Roaming\Python\Python314\Scripts\streamlit.exe' -ArgumentList 'run app.py' -WorkingDirectory 'D:\AI\mock-investment-dashboard'"
timeout /t 4 /nobreak > nul
start http://localhost:8501
