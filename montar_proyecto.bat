@echo off
REM ============================================================
REM  NeuroFic - Montaje automatico del proyecto en este equipo.
REM
REM  Ejecutar DESPUES de clonar el repositorio, parado dentro de
REM  la carpeta del clon (donde esta este mismo archivo).
REM
REM  Que hace:
REM    1) Busca en el disco C: el proyecto original (por pdf_render.py).
REM    2) Copia su codigo fuente (src, templates, *.py, requirements.txt,
REM       .env) a esta carpeta.
REM    3) Restaura los archivos de la interfaz web a la version de GitHub
REM       (por si el paso 2 sobreescribio algo).
REM    4) Crea el entorno virtual e instala las dependencias.
REM    5) Corre las pruebas de la interfaz web.
REM ============================================================
setlocal EnableDelayedExpansion
title NeuroFic - Montaje automatico
cd /d "%~dp0"
set "DESTINO=%cd%"

echo ============================================================
echo  Montando el proyecto en: %DESTINO%
echo ============================================================
echo.
echo  Buscando el proyecto original (pdf_render.py) en el disco C:...
echo  Esto puede tardar uno o dos minutos, espere por favor.
echo.

set "PDF_RENDER="
for /f "delims=" %%F in ('where /r C:\ pdf_render.py 2^>nul') do (
    echo %%F | findstr /i /c:"%DESTINO%" >nul
    if errorlevel 1 (
        echo %%F | findstr /i /c:"\venv\" >nul
        if errorlevel 1 (
            if not defined PDF_RENDER set "PDF_RENDER=%%F"
        )
    )
)

if not defined PDF_RENDER (
    echo  [AVISO] No se encontro pdf_render.py automaticamente en el disco C:.
    echo.
    set /p ORIGEN="  Escriba la ruta completa del proyecto original (ej. C:\NeuroficMigracion): "
) else (
    echo  Encontrado: !PDF_RENDER!
    for %%P in ("!PDF_RENDER!") do set "CARPETA_SRC=%%~dpP"
    pushd "!CARPETA_SRC!.."
    set "ORIGEN=!cd!"
    popd
    echo  Proyecto original detectado en: !ORIGEN!
)

echo.
if /i "!ORIGEN!"=="!DESTINO!" (
    echo  [ERROR] El proyecto original coincide con este destino. Cancelando.
    pause
    exit /b 1
)
if not exist "!ORIGEN!\src" (
    echo  [ERROR] No existe "!ORIGEN!\src". Revise la ruta e intente de nuevo.
    pause
    exit /b 1
)

echo  Copiando codigo fuente de:
echo    "!ORIGEN!"
echo  hacia:
echo    "%DESTINO%"
echo.

xcopy /E /I /Y "!ORIGEN!\src" "src" >nul
xcopy /E /I /Y "!ORIGEN!\templates" "templates" >nul
if exist "!ORIGEN!\assets" xcopy /E /I /Y "!ORIGEN!\assets" "assets" >nul
copy /Y "!ORIGEN!\*.py" . >nul
if exist "!ORIGEN!\requirements.txt" copy /Y "!ORIGEN!\requirements.txt" . >nul
if exist "!ORIGEN!\.env" (
    copy /Y "!ORIGEN!\.env" . >nul
    echo  Se copio .env ^(configuracion local^); NUNCA se sube a GitHub.
)

echo.
echo  Restaurando los archivos de la interfaz web a la version de GitHub...
git checkout -- app_web.py src\web_utils.py src\pdf_cache.py templates\web tests\test_interfaz_web.py requirements_web.txt 2>nul

echo.
echo  Creando entorno virtual e instalando dependencias...
if not exist venv (
    py -m venv venv
)
venv\Scripts\python.exe -m pip install --upgrade pip >nul
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install -r requirements_web.txt

echo.
echo ============================================================
echo  Ejecutando pruebas de la interfaz web...
echo ============================================================
venv\Scripts\python.exe -m pytest tests\test_interfaz_web.py -v

echo.
echo ============================================================
echo  Listo. Revise arriba: si dice "passed" en verde, todo esta OK.
echo.
echo  Para iniciar la interfaz:
echo    - Solo este equipo:  iniciar_web.bat
echo    - Intranet:          iniciar_web_intranet.bat
echo.
echo  Antes de hacer commit, revise "git status": nunca debe aparecer
echo  el archivo .env ni datos de pacientes.
echo ============================================================
pause
endlocal
