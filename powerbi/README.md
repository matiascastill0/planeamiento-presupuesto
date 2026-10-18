# Power BI · diseño corporativo y tarjetas KPI

| Script | Qué hace |
|---|---|
| `generar_pbip.py` | Arma el `.pbip` (modelo + reporte) conectado a las tablas gold. El host va en `DBX_HOSTNAME`. |
| `generar_diseno_bi.py` | Genera el tema (`tema/tema-ppto27.json`) y un fondo PNG por página con Chrome headless (`CHROME_PATH` opcional). |
| `disenar_pbip.py` | Aplica a un `.pbip` (formato PBIR) el tema, los fondos, la grilla de 16 px y el filtro Vehículo sincronizado. |
| `kpis_svg.py` | Agrega 8 medidas DAX que dibujan tarjetas SVG y reemplaza las tarjetas de Resumen y Calidad. `--preview <carpeta>` las muestra con valores de ejemplo. |
| `empaquetar_pbi_databricks.py`, `empaquetar_zip.py` | Empaquetan el reporte para compartir (zip compatible con Windows). |

```bash
python disenar_pbip.py "<carpeta con el .pbip>" "<carpeta de salida>"
python kpis_svg.py "<carpeta de salida>"
python kpis_svg.py --preview salida
```

Más detalle en [docs/powerbi.md](../docs/powerbi.md).

---

<sub>© 2026 Credicorp Capital. Uso interno. Ver [LICENSE](../LICENSE).</sub>
