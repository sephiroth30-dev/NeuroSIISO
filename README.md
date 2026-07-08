# NeuroSIISO — Interfaz web de consulta de historias clínicas

Interfaz gráfica web **local** para consultar las historias clínicas migradas
del software legado SIISO: buscar un paciente por número de documento, ver sus
datos básicos y la lista de sus atenciones, y mostrar en el navegador el PDF
reconstruido de la historia elegida.

> **Importante — estado de este repositorio.** Este repositorio estaba vacío
> cuando se construyó esta interfaz: el código ya validado de las Fases 1 y 2
> (capa de datos `src/db.py`, `src/repository.py`, `src/service.py`,
> `src/models.py`, `src/formatters.py`, generador `src/pdf_render.py` y las
> plantillas del PDF) vive en `C:\NeuroficMigracion`, en el equipo de Andrés,
> y **no** está aquí. Este repositorio contiene únicamente los archivos
> **nuevos** de la interfaz web, ubicados en las mismas rutas relativas del
> proyecto para poder copiarlos directamente encima de `C:\NeuroficMigracion`.
> Se recomienda subir también el resto del proyecto a este repositorio para
> tenerlo versionado.

## Archivos de la interfaz (nuevos)

```
app_web.py                  # Aplicación FastAPI (punto de entrada)
src/web_utils.py            # Utilidades puras: validación, presentación, emparejamiento PDF↔historia
src/pdf_cache.py            # Generación bajo demanda + caché de PDF (reutiliza src/pdf_render.py)
templates/web/base.html     # Plantilla base de la interfaz (no toca las del PDF)
templates/web/index.html    # Búsqueda por documento
templates/web/paciente.html # Ficha del paciente + lista de historias
templates/web/visor.html    # Visor del PDF embebido
tests/test_interfaz_web.py  # Pruebas de las utilidades (sin BD ni Playwright)
requirements_web.txt        # Dependencias adicionales (fastapi, uvicorn)
```

## Instalación (en el equipo con la base restaurada)

1. Copiar estos archivos dentro de `C:\NeuroficMigracion` respetando las rutas
   (los archivos nuevos no pisan ninguno existente; `templates/web/` es una
   subcarpeta nueva junto a las plantillas del PDF).
2. Con el venv activo:

   ```
   py -m pip install -r requirements_web.txt
   ```

## Ejecución

Desde `C:\NeuroficMigracion`, con el venv activo:

```
py -m uvicorn app_web:app --host 127.0.0.1 --port 8000
```

Abrir <http://127.0.0.1:8000> en el navegador.

## Cómo funciona

- **Búsqueda:** `/buscar?documento=...` usa `src.service.obtener_historia_completa`
  sobre una conexión de solo lectura (`src.db.get_connection`). No hay SQL nuevo.
- **Ficha e historias:** los datos del paciente y la tabla de historias se
  muestran a partir de los campos escalares de las dataclasses de dominio
  (se omiten colecciones, firmas en bytes y objetos anidados; el detalle
  completo está en el PDF).
- **PDF bajo demanda:** al elegir una historia, `src/pdf_cache.py` genera los
  PDF del paciente con `src.pdf_render.generar_pdfs_de_paciente` en
  `var/pdf_cache/<documento>/` (una sola vez; las siguientes consultas salen
  de la caché) y el visor lo embebe con el lector de PDF del navegador.
  El enlace «Regenerar PDF» borra la caché de ese paciente y vuelve a generar.
- **Casos manejados:** documento inválido o no encontrado, paciente sin
  historias, índice de historia inexistente y errores de base de datos, todos
  con mensaje en pantalla.

## Punto de ajuste conocido

`generar_pdfs_de_paciente` genera **todos** los PDF del paciente en una
carpeta; la interfaz asocia cada archivo con su historia en
`src/web_utils.py:elegir_archivo_pdf` (por id en el nombre del archivo o, en
su defecto, por posición). Si el nombre de archivo que produce
`src/pdf_render.py` no encaja con esas reglas, ajustar esa única función —
está cubierta por pruebas en `tests/test_interfaz_web.py`.

## Pruebas

```
py -m pytest tests/test_interfaz_web.py
```

## Seguridad y alcance

- Conexión a la base **solo lectura**; la interfaz nunca escribe en SIISO.
- Servida únicamente en `127.0.0.1`; no exponer a la red.
- Sin SQL nuevo: toda consulta pasa por la capa parametrizada existente.
- **Pendiente (fase posterior):** autenticación de usuarios y bitácora de
  accesos. Fuera de alcance por ahora: impresión y exportación masiva.
