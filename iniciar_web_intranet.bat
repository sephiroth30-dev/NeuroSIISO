@echo off
REM ============================================================
REM  NeuroFic - Lanzador de la interfaz web para la INTRANET
REM  Copiar en C:\NeuroficMigracion y ejecutar con doble clic.
REM
REM  Sirve la app a TODA la red interna (host 0.0.0.0:8000).
REM
REM  ADVERTENCIA: esta version NO pide contrasena. Cualquier equipo
REM  de la intranet podra consultar cualquier paciente por documento.
REM  Cada consulta queda registrada en var\bitacora\ (fecha, IP del
REM  equipo, documento consultado). Usar SOLO en una red interna
REM  controlada; nunca exponer este puerto a Internet.
REM ============================================================
setlocal
cd /d "%~dp0"

set "PYEXE=venv\Scripts\python.exe"
if not exist "%PYEXE%" set "PYEXE=py"

echo.
echo  Verificando dependencias de la interfaz web...
"%PYEXE%" -m pip install -r requirements_web.txt

echo.
echo  Direcciones IP de este equipo (comparte una de estas con el sufijo :8000):
ipconfig | findstr /i "IPv4"

echo.
echo  Iniciando la interfaz para la intranet en el puerto 8000...
echo  (Para detener el servidor: cierra esta ventana.)
echo.
echo  NOTA: si otros equipos no logran conectarse, abre el puerto 8000
echo        (TCP, entrante) en el Firewall de Windows de este equipo.
echo.

"%PYEXE%" -m uvicorn app_web:app --host 0.0.0.0 --port 8000

echo.
echo  El servidor se detuvo.
pause
endlocal
