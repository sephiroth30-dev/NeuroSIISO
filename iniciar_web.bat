@echo off
REM ============================================================
REM  NeuroFic - Lanzador de la interfaz web de consulta (local)
REM  Copiar este archivo en C:\NeuroficMigracion y hacer doble clic.
REM  Sirve la app SOLO en localhost (127.0.0.1:8000).
REM ============================================================
setlocal
cd /d "%~dp0"

REM --- Elegir el Python del entorno virtual si existe ---
set "PYEXE=venv\Scripts\python.exe"
if not exist "%PYEXE%" set "PYEXE=py"

echo.
echo  Verificando dependencias de la interfaz web...
"%PYEXE%" -m pip install -r requirements_web.txt

echo.
echo  Iniciando la interfaz en http://127.0.0.1:8000
echo  (Se abrira el navegador en unos segundos. Para detener: cierra esta ventana.)
echo.

REM --- Abrir el navegador con un pequeno retraso, sin bloquear el servidor ---
start "" cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:8000"

REM --- Arrancar el servidor en primer plano ---
"%PYEXE%" -m uvicorn app_web:app --host 127.0.0.1 --port 8000

echo.
echo  El servidor se detuvo.
pause
endlocal
