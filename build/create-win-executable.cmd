@echo off
rmdir /S /Q %~dp0\dist
py -m venv %~dp0\venv
CALL %~dp0\venv\Scripts\activate.bat
pip install -r %~dp0\..\requirements.txt
pyinstaller --onefile %~dp0\..\src\spot-pricing.py
rmdir /S /Q %~dp0\build %~dp0\venv
del %~dp0\spot-pricing.spec
