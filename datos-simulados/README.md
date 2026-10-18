# Datos simulados

Las **15 tablas del BI** (`ppto27_gld_*` + `Moneda`) con la **misma estructura** que Databricks: mismas columnas, tipos y llaves. Sirven para construir visuales y medidas sin acceso a Databricks y luego cambiar la fuente sin rehacer nada.

| | |
|---|---|
| Catálogos reales (sin montos) | País, UdN, componente, Formato Perú, flags, vehículos y meses (`catalogos/`) |
| Simulados | 3 países, 9 plantillas, CeCos, cuentas, proveedores y montos 2027 |
| Coherencia | Las llaves cruzan, Dir/Ind reparte con la metodología real y **gestión = contable** por país × mes |

## Uso

1. **Power BI → Obtener datos → Texto/CSV** (o el Excel que genera el script) y cargar las 15 tablas de `CSV/`.
2. Crear las relaciones de [docs/modelo-de-datos.md](../docs/modelo-de-datos.md#relaciones) (muchos a uno, filtro en una dirección).
3. Pegar las medidas de `medidas-dax.txt`.

Con Windows en español, al importar los CSV hay que elegir *Configuración regional: Inglés (Estados Unidos)*, para que el punto se lea como decimal.

## Regenerar

```bash
python generar_datos_simulados.py      # corre los controles y escribe CSV/ y salida/*.xlsx
```

---

<sub>© 2026 Credicorp Capital. Uso interno. Ver [LICENSE](../LICENSE).</sub>
