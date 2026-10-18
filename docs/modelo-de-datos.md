# Modelo de datos (Power BI)

El BI lee las tablas gold de Databricks (`ppto27_gld_*`) en **DirectQuery**. Modelo en estrella: 3 hechos y 12 dimensiones, relaciones de **muchos a uno** con filtro en una sola dirección.

> Para trabajar sin acceso a Databricks están las mismas tablas con datos simulados en [`datos-simulados/`](../datos-simulados).

## Tablas

### `fact_ppto`
Una fila por línea de plantilla × mes (Ppto 2027). Gasto en negativo.

| Columna | Tipo |
|---|---|
| `id_linea` | texto |
| `id_plantilla` | texto |
| `id_fecha` | entero |
| `id_pais` | texto |
| `id_ceco` | texto |
| `id_vehiculo` | texto |
| `id_cuenta` | entero |
| `id_proveedor` | entero |
| `id_linea_pyg` | entero |
| `glosa` | texto |
| `escenario` | texto |
| `moneda_origen` | texto |
| `monto_origen` | decimal |
| `monto_local` | decimal |
| `monto_pen` | decimal |
| `origen_monto` | texto |
| `estado_linea` | texto |
| `flags` | texto |
| `anio` | entero |

### `fact_gestion_dirind`
Reparto Dir/Ind: cada línea partida por UdN y componente, para las metodologías Nueva y Antigua.

| Columna | Tipo |
|---|---|
| `id_linea` | texto |
| `id_plantilla` | texto |
| `id_fecha` | entero |
| `id_pais` | texto |
| `id_udn` | texto |
| `id_componente` | entero |
| `id_ceco_origen` | texto |
| `id_linea_pyg` | entero |
| `pct_driver` | decimal |
| `monto_pen` | decimal |
| `monto_local` | decimal |
| `estado_linea` | texto |
| `id_vehiculo` | texto |
| `anio` | entero |
| `metodologia` | texto |
| `agrupacion` | texto |

### `fact_flags`
Hallazgos de validación: plantilla, línea, regla y celda exacta.

| Columna | Tipo |
|---|---|
| `id_plantilla` | texto |
| `id_linea` | texto |
| `codigo_flag` | texto |
| `celdas` | texto |
| `detalle` | texto |

### `dim_ceco`
Centros de costo por país (código + nombre, agrupación, tipo).

| Columna | Tipo |
|---|---|
| `id_ceco` | texto |
| `pais` | texto |
| `ceco` | entero |
| `ceco_nombre` | texto |
| `agrupacion` | texto |
| `sub_unidad` | texto |
| `tipo_ceco` | texto |

### `dim_componente`
Componentes del reparto: imputación directa, soporte directo, indirecto.

| Columna | Tipo |
|---|---|
| `id_componente` | entero |
| `componente` | texto |
| `grupo` | texto |

### `dim_cuenta`
Cuentas contables con Nivel 1/2/3.

| Columna | Tipo |
|---|---|
| `id_cuenta` | entero |
| `nom_cta_contable` | texto |
| `nivel_1` | texto |
| `nivel_2` | texto |
| `nivel_3` | texto |

### `dim_fecha`
Calendario mensual 2027.

| Columna | Tipo |
|---|---|
| `id_fecha` | entero |
| `fecha` | texto |
| `anio` | entero |
| `mes_num` | entero |
| `mes` | texto |
| `periodo` | texto |
| `trimestre` | texto |
| `semestre` | texto |

### `dim_flag`
Catálogo de las reglas de validación (código, severidad, acción).

| Columna | Tipo |
|---|---|
| `codigo_flag` | texto |
| `categoria` | texto |
| `severidad` | texto |
| `flag` | texto |
| `regla` | texto |
| `accion` | texto |

### `dim_linea_pyg`
Formato Perú: Nivel 1 / Nivel 2 y su orden.

| Columna | Tipo |
|---|---|
| `id_linea_pyg` | entero |
| `n1_formato` | texto |
| `grupo_n2` | texto |
| `n2_formato` | texto |
| `nivel_1_plantilla` | texto |
| `nivel_2_plantilla` | texto |
| `orden_n1` | entero |
| `orden_n2` | entero |

### `dim_pais`
Países y moneda local.

| Columna | Tipo |
|---|---|
| `id_pais` | texto |
| `pais` | texto |
| `pais_bi` | texto |
| `moneda_local` | texto |

### `dim_plantilla`
Plantillas cargadas: archivo, tipo, área, versión y estado.

| Columna | Tipo |
|---|---|
| `id_plantilla` | texto |
| `archivo` | texto |
| `carpeta` | texto |
| `tipo` | texto |
| `area` | texto |
| `pais` | texto |
| `entrega` | texto |
| `version` | texto |
| `hash` | texto |
| `fecha_carga` | texto |
| `estado_validacion` | texto |

### `dim_proveedor`
Proveedores homologados.

| Columna | Tipo |
|---|---|
| `id_proveedor` | entero |
| `proveedor` | texto |

### `dim_udn`
Unidades de negocio.

| Columna | Tipo |
|---|---|
| `id_udn` | texto |
| `udn` | texto |

### `dim_vehiculo`
Vehículos legales por país.

| Columna | Tipo |
|---|---|
| `id_vehiculo` | texto |
| `pais` | texto |
| `vehiculo` | texto |
| `razon_social` | texto |

### `Moneda`
Tabla auxiliar del selector PEN / Local.

| Columna | Tipo |
|---|---|
| `Moneda` | texto |

## Relaciones

| Desde (muchos) | Hacia (uno) |
|---|---|
| `fact_ppto.id_ceco` | `dim_ceco.id_ceco` |
| `fact_ppto.id_cuenta` | `dim_cuenta.id_cuenta` |
| `fact_ppto.id_linea_pyg` | `dim_linea_pyg.id_linea_pyg` |
| `fact_ppto.id_vehiculo` | `dim_vehiculo.id_vehiculo` |
| `fact_ppto.id_plantilla` | `dim_plantilla.id_plantilla` |
| `fact_ppto.id_fecha` | `dim_fecha.id_fecha` |
| `fact_ppto.id_pais` | `dim_pais.id_pais` |
| `fact_ppto.id_proveedor` | `dim_proveedor.id_proveedor` |
| `fact_flags.id_plantilla` | `dim_plantilla.id_plantilla` |
| `fact_flags.codigo_flag` | `dim_flag.codigo_flag` |
| `fact_gestion_dirind.id_linea_pyg` | `dim_linea_pyg.id_linea_pyg` |
| `fact_gestion_dirind.id_ceco_origen` | `dim_ceco.id_ceco` |
| `fact_gestion_dirind.id_plantilla` | `dim_plantilla.id_plantilla` |
| `fact_gestion_dirind.id_fecha` | `dim_fecha.id_fecha` |
| `fact_gestion_dirind.id_componente` | `dim_componente.id_componente` |
| `fact_gestion_dirind.id_udn` | `dim_udn.id_udn` |
| `fact_gestion_dirind.id_pais` | `dim_pais.id_pais` |
| `fact_gestion_dirind.id_vehiculo` | `dim_vehiculo.id_vehiculo` |

## Medidas

| Carpeta | Medida | Definición |
|---|---|---|
| 1 Contable | `Ppto PEN` | `CALCULATE ( SUM ( fact_ppto[monto_pen] ))` |
| 1 Contable | `Gasto PEN` | `- [Ppto PEN]` |
| 1 Contable | `Ppto Moneda Local` | `IF ( HASONEVALUE ( dim_pais[id_pais] ), CALCULATE ( SUM ( fact_ppto[monto_local] )))` |
| 1 Contable | `Gasto Moneda Local` | `- [Ppto Moneda Local]` |
| 1 Contable | `Líneas` | `DISTINCTCOUNT ( fact_ppto[id_linea] )` |
| 1 Contable | `Plantillas` | `DISTINCTCOUNT ( fact_ppto[id_plantilla] )` |
| 1 Contable | `Gasto PEN Mes Anterior` | `CALCULATE ( [Gasto PEN], DATEADD ( dim_fecha[fecha], -1, MONTH ) )` |
| 1 Contable | `Var % vs Mes Anterior` | `DIVIDE ( [Gasto PEN] - [Gasto PEN Mes Anterior], [Gasto PEN Mes Anterior] )` |
| 2 Calidad | `Ppto Cuarentena PEN` | `CALCULATE ( SUM ( fact_ppto[monto_pen] ), fact_ppto[estado_linea] = "Cuarentena" )` |
| 2 Calidad | `Ppto Total Cargado PEN` | `SUM ( fact_ppto[monto_pen] )` |
| 2 Calidad | `% Cuarentena` | `DIVIDE ( [Ppto Cuarentena PEN], [Ppto Total Cargado PEN] )` |
| 2 Calidad | `Flags` | `COUNTROWS ( fact_flags )` |
| 2 Calidad | `Flags Error` | `CALCULATE ( [Flags], dim_flag[severidad] IN { "BLOQUEANTE", "ERROR" } )` |
| 2 Calidad | `Flags Alerta` | `CALCULATE ( [Flags], dim_flag[severidad] = "ALERTA" )` |
| 2 Calidad | `Plantillas con Error` | `CALCULATE ( DISTINCTCOUNT ( fact_flags[id_plantilla] ), dim_flag[severidad] IN { "BLOQUEANTE", "ERROR" } )` |
| 3 Dir-Ind | `Dir/Ind PEN` | `SUM ( fact_gestion_dirind[monto_pen] )` |
| 3 Dir-Ind | `Dir/Ind Moneda Local` | `IF ( HASONEVALUE ( dim_pais[id_pais] ), SUM ( fact_gestion_dirind[monto_local] ) )` |
| 3 Dir-Ind | `Dir/Ind Gasto Presentado` | `- [Dir/Ind Presentado]` |
| 3 Dir-Ind | `Dir/Ind Cuadre vs Contable PEN` | `[Dir/Ind PEN] - [Ppto PEN]` |
| 4 Moneda seleccionada | `Ppto Presentado` | `SWITCH ( SELECTEDVALUE ( Moneda[Moneda], "PEN" ), "PEN", [Ppto PEN], [Ppto Moneda Local] )` |
| 4 Moneda seleccionada | `Gasto Presentado` | `- [Ppto Presentado]` |
| 4 Moneda seleccionada | `Dir/Ind Presentado` | `SWITCH ( SELECTEDVALUE ( Moneda[Moneda], "PEN" ), "PEN", [Dir/Ind PEN], [Dir/Ind Moneda Local] )` |


Además, la carpeta **5 Diseño KPI** tiene 8 medidas que devuelven tarjetas SVG (categoría *URL de imagen*): `KPI Gasto Ppto SVG`, `KPI Moneda Local SVG`, `KPI Plantillas SVG`, `KPI Cuarentena SVG`, `KPI Flags SVG`, `KPI Flags Error SVG`, `KPI Plantillas Error SVG`, `KPI Cuarentena PEN SVG`. Ver [Power BI](powerbi.md).

---

<sub>© 2026 Credicorp Capital. Uso interno. Ver [LICENSE](../LICENSE).</sub>
