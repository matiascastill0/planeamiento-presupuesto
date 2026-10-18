# Herramientas

| Script | Qué genera |
|---|---|
| `generar_validador_ipynb.py` | `95_validar.ipynb`, validador independiente |
| `generar_restauracion_ipynb.py` | `98_restauracion.ipynb` (`--probar` lo ejecuta con Delta local) |
| `generar_dashboard_html.py` + `dashboard_plantilla.html` | Dashboard HTML autónomo de validación |
| `generar_maestros.py` | Los 3 maestros que se suben al Volume |
| `empaquetar_databricks.py` | Paquete para importar en Databricks |
| `verificar_repo.py` | Guardia de la CI: sin datos reales, secretos ni notebooks con salidas |

---

<sub>© 2026 Credicorp Capital. Uso interno. Ver [LICENSE](../LICENSE).</sub>
