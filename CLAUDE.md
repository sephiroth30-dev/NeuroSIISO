# NeuroFic SIISO — contexto del proyecto

Migración/consulta de historias clínicas del backup SIISO de NeuroFic
(SQL Server, ~136.475 pacientes). El proyecto tiene tres capas, dos de
las cuales **no viven en este repositorio de GitHub**: solo existen en
este equipo, copiadas por `montar_proyecto.bat` desde el proyecto
original.

## Las tres fases

1. **Fase 1 — Lectura de datos** (`src/db.py`, `src/config.py`,
   `src/repository.py`, `src/models.py`, `src/service.py`,
   `src/formatters.py`, `leer_paciente.py`). Conecta a SQL Server con
   Autenticación de Windows y arma la historia clínica completa de un
   paciente. **Ya validada, no tocar sin razón fuerte.**
2. **Fase 2 — Generación de PDF** (`src/pdf_render.py`,
   `generar_pdf.py`, `templates/historia_clinica.html` y afines,
   `assets/`). Usa Playwright + Chromium para reproducir el PDF
   original fielmente. **Ya validada** contra el paciente de prueba
   `29957147`.
3. **Fase 3 — Interfaz web** (`app_web.py`, `src/web_utils.py`,
   `src/pdf_cache.py`, `templates/web/`, `tests/test_interfaz_web.py`).
   Construida en una sesión remota de Claude sin acceso a este equipo
   ni a la base real; reutiliza las Fases 1 y 2 sin modificarlas.
   **Esta es la única capa que vive en GitHub** (rama
   `claude/new-session-ozfvn2`).

## Punto crítico a verificar primero

`src/web_utils.py::elegir_archivo_pdf` empareja cada PDF generado por
`generar_pdfs_de_paciente` con su historia clínica, por id en el
nombre de archivo o por posición. Se probó con un paciente de una sola
historia (`29957147`, con éxito). **Falta probar con un paciente de
varias historias** — si falla, revisar cómo `pdf_render.py` nombra los
archivos y ajustar esa función (tiene pruebas en
`tests/test_interfaz_web.py`).

## Cómo ejecutar

```bat
iniciar_web.bat            REM solo este equipo (127.0.0.1:8000)
iniciar_web_intranet.bat   REM toda la red interna (0.0.0.0:8000)
montar_proyecto.bat        REM vuelve a copiar el codigo original si hace falta
```

Requiere `.env` (config de la base) en la raíz del proyecto — nunca se
sube a GitHub.

## Decisión de seguridad ya tomada

El modo intranet se pidió **sin login** (decisión explícita de la
IPS, con la advertencia hecha y aceptada): cualquier equipo de la red
interna puede consultar cualquier paciente por documento. Como
mitigación mínima, `app_web.py` tiene un middleware que registra cada
consulta en `var/bitacora/accesos-AAAA-MM.csv` (fecha, IP, ruta,
documento). Es *best-effort*: nunca debe interrumpir la respuesta.

No agregar login/usuarios sin que el usuario lo pida explícitamente:
ya se le preguntó y prefirió esta vía.

## Qué NUNCA debe llegar a git

- `.env` (ya en `.gitignore`)
- `var/` — caché de PDF y bitácora de accesos, tiene datos de
  pacientes (ya en `.gitignore`)
- `venv/`, `__pycache__/`
- Cualquier JSON/PDF suelto de un paciente real (p. ej. salidas de
  `leer_paciente.py`) que se haya generado a mano en la raíz del
  proyecto — revisar `git status` a mano antes de cualquier commit
  que incluya código de las Fases 1-2.

## Estado actual (última sesión remota)

- Fase 3 completa y con 16/16 pruebas en verde.
- Código de Fases 1-2 copiado a este equipo con `montar_proyecto.bat`,
  pendiente de: confirmar que `.env` se copió, correr
  `iniciar_web.bat` y volver a probar con `29957147` en este montaje
  nuevo (ya se había probado en un montaje anterior).
- Pendiente subir el código de Fases 1-2 a GitHub (revisando primero
  `git status` para no filtrar datos sensibles).
