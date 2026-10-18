# Cómo contribuir

## Flujo de trabajo

1. Crear una rama desde `main`: `feature/<tema>`, `fix/<tema>` o `docs/<tema>`.
2. Hacer commits pequeños, con mensajes en imperativo y en español: `Agrega control de duplicados por proveedor`.
3. Abrir un Pull Request con la plantilla del repo y pedir revisión a otra persona del equipo.
4. Fusionar a `main` solo con la CI en verde y una aprobación.

## Reglas que no se negocian

- **Nunca subir datos reales:** plantillas, TD Regional, maestros, salidas de notebooks, `.pbix`/`.pbip` ni capturas con montos reales. La CI rechaza `.xlsx`, `.xlsb`, `.pkl`, `.parquet` y `.zip`.
- **Nunca subir credenciales** ni identificadores del workspace (host, warehouse, tokens). Van en variables de entorno: `DBX_HOSTNAME`, `PPTO27_RAIZ`.
- **Notebooks sin salidas.** Limpiar antes de confirmar: *Clear all outputs*.
- **Reglas de negocio** (ver el README): fuente única TD, IPC excluido, CeCo numerado, nunca "Varios", cuadre por país × vehículo × CeCo × cuenta × mes.
- **Excel se edita por XML** (lxml), nunca guardando con openpyxl encima de una plantilla (pierde validaciones y formatos).

## Antes de abrir el PR

```bash
pip install -r requirements.txt ruff
ruff check .
python -m compileall -q .
python herramientas/verificar_repo.py
```

Si el cambio toca el armado de plantillas o el pipeline, adjuntar en el PR la evidencia del cuadre (por ejemplo, la salida de `v2_verificar.py` o los 25 controles en OK) **sin montos reales**.

---

<sub>© 2026 Credicorp Capital. Uso interno. Ver [LICENSE](LICENSE).</sub>
