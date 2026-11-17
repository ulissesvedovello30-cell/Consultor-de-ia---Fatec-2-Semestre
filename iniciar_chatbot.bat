@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto ambiente
py -3.15 -c "import sys" >nul 2>&1
if not errorlevel 1 goto python315
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 goto launcher
python -c "import sys" >nul 2>&1
if not errorlevel 1 goto python

echo Python nao encontrado. Instale o Python 3.15 e execute este arquivo novamente.
pause
exit /b 1

:ambiente
".venv\Scripts\python.exe" "main.py" %*
goto resultado

:python315
py -3.15 "main.py" %*
goto resultado

:launcher
py -3 "main.py" %*
goto resultado

:python
python "main.py" %*

:resultado
set "CODIGO_SAIDA=%ERRORLEVEL%"
if not "%CODIGO_SAIDA%"=="0" echo O projeto encerrou com erro. Confira a mensagem acima.
pause
exit /b %CODIGO_SAIDA%
