# Seguridad y datos

## Qué no entra al repositorio

| No se sube | Dónde vive |
|---|---|
| Plantillas Excel, TD Regional, consolidados | Carpetas del proyecto en OneDrive / SharePoint |
| Maestros, alias y drivers | Volume `ppto27/90_maestros` |
| Tablas y salidas | Unity Catalog / Volume del proyecto |
| Host del workspace, HTTP path, tokens | Variables de entorno de cada usuario |
| Archivos de Power BI | Área de trabajo de Power BI |

La única data versionada es la **simulada** de `datos-simulados/` y los catálogos sin montos (países, UdN, componentes, Formato Perú, flags, vehículos y meses).

## Controles automáticos

`herramientas/verificar_repo.py` corre en la CI y falla si encuentra archivos de datos, hosts de Databricks, tokens, rutas personales o correos.

## Si se subió algo por error

1. Avisar de inmediato a la jefatura de Planeamiento.
2. No basta con borrar el archivo en un commit nuevo: queda en el historial. Hay que reescribir el historial (`git filter-repo`) y rotar cualquier credencial expuesta.

---

<sub>© 2026 Credicorp Capital. Uso interno. Ver [LICENSE](LICENSE).</sub>
