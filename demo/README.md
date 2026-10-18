# Demo · plantillas limpias y con errores

- `generar_demo.py`: genera lotes de 3 plantillas reales de Perú (MDK, Staff Riesgos, Staff Finanzas) en versión limpia y con 16 errores clásicos sembrados (cada uno con su celda). Cada lote tiene distinta huella, así que entra sin RESTORE.
- `generar_notebook_demo.py`: genera `08_demo` (adaptativo) y `08a_demo_limpias`. Con `--probar <volume> <carga>` ejecuta las celdas en Spark local.
- `probar_demo_spark.py`: prueba de punta a punta en Spark 3.5 local (bronze → silver → gold → control) con todas las cargas en secuencia.

---

<sub>© 2026 Credicorp Capital. Uso interno. Ver [LICENSE](../LICENSE).</sub>
