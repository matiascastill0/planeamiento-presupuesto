# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado [SemVer](https://semver.org/lang/es/).

## [1.0.0] - 2026-10-17

### Agregado
- Armado de las 184 plantillas Ppto27 con el Real 2026 Ene–Ago de la TD Regional, con cuadre por país × vehículo × CeCo × cuenta × mes y controles de duplicados, IPC y "Varios".
- Pipeline medallion en Databricks (bronze → silver → gold → control) con 63 reglas de validación por celda, cuarentena de líneas y versiones por plantilla.
- Reparto Dir/Ind por UdN, país y mes con la metodología nueva (imputación + soporte directo), y la anterior para comparar.
- 25 controles de cuadre previos a la publicación y reporte de la carga con hallazgos por celda.
- Restauración de tablas por versión Delta y validador independiente.
- Power BI en DirectQuery con diseño corporativo, tarjetas KPI en SVG y filtro de vehículo sincronizado.
- Datos simulados con la estructura exacta del modelo, para trabajar sin acceso a Databricks.
- Plantillas especiales: intercompanies (Contable + Intercom = Gestión) y comisiones de Panamá.
- Demo de plantillas limpias y con errores, y guía del proceso para el negocio.

---

<sub>© 2026 Credicorp Capital. Uso interno. Ver [LICENSE](LICENSE).</sub>
