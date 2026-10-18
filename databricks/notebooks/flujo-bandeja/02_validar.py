# Databricks notebook source
# MAGIC %md
# MAGIC # Ppto27 · 02 Validar el reparto Dir/Ind (después de 01_procesar)
# MAGIC Recalcula el reparto **por su cuenta**, sólo con las tablas gold (contable + tabla de drivers + plantillas), y lo compara con
# MAGIC `ppto27_gld_fact_gestion_dirind`. No usa el código que generó el reparto, por eso sirve como prueba independiente.
# MAGIC
# MAGIC | # | Control | Tipo | Qué prueba |
# MAGIC |---|---|---|---|
# MAGIC | 1 | Conservación | Crítico | Cada línea contable × mes se reparte al 100 %: no se pierde ni se duplica plata |
# MAGIC | 2 | Drivers 100 % | Crítico | En la tabla de drivers cada país × CeCo × vehículo suma 100 % |
# MAGIC | 3 | Recálculo | Crítico | Línea × mes × UdN × componente = monto × % del driver (vehículo exacto, si no "(todos)"; sin driver → regla) |
# MAGIC | 4 | Indirectos | Crítico | La bolsa de indirectos de cada país × mes se reparte según la participación de la imputación directa por UdN |
# MAGIC | 5 | Sin base | Dato | Indirectos que no se pudieron repartir (país sin imputación directa) |
# MAGIC | 6 | Fuera | Dato | Líneas contables OK que no entran al Dir/Ind (país no reconocido) |
# MAGIC | 7 | Sin driver | Revisar | CeCo × vehículo sin driver, repartidos por regla → confirmar con Planeamiento |
# MAGIC
# MAGIC Deja el Excel `Validacion_DirInd_<fecha>.xlsx` en `ppto27/30_bi` (para compartir) y el historial en `ppto27_ctl_validacion`.

# COMMAND ----------

# MAGIC %pip install openpyxl --quiet

# COMMAND ----------

import sys
sys.path.append('/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27/00_codigo')
import ppto27_spark as SP

R = SP.validar(spark)
display(R['checks'])
print('Excel:', SP.exportar_validacion(R))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cruce con el Power BI
# MAGIC Estos números deben verse iguales en el BI: página Formato Perú (contable, líneas OK) y página Dir-Ind (Directo + Indirecto), filtrando el mismo país.
# MAGIC `diferencia` debe ser 0 en todas las filas.

# COMMAND ----------

display(R['resumen_bi'])
display(R['udn_pais'])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Para revisar con Planeamiento: CeCos sin driver (repartidos por regla)

# COMMAND ----------

display(R['v7_sin_driver'])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Detalle de diferencias (sólo si algún control crítico dio FALLA)

# COMMAND ----------

for k in ('v1_conservacion', 'v2_drivers_100', 'v3_recalculo'):
    if len(R[k]):
        print(k); display(R[k])
display(R['v4_indirectos'])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trazabilidad de una línea (prueba a mano)
# MAGIC Pega un `id_linea` (cópialo del BI o de `ppto27_gld_fact_ppto`) entre comillas. Con `None` toma la de mayor monto cuyo driver reparte entre varias UdN.
# MAGIC Muestra: la línea contable → los drivers que le tocan → cómo quedó repartida por UdN y componente, mes a mes. El `total` debe ser igual al contable.

# COMMAND ----------

ID_LINEA = None          # ejemplo: '03 | UDN | WM | Perú | WM#78'
T = SP.trazar(spark, ID_LINEA)
print('Línea:', T['id_linea'])
display(T['linea'])
display(T['drivers'])
display(T['contable_por_mes'])
display(T['reparto'])

# COMMAND ----------

criticos = R['checks'][(R['checks'].tipo == 'Crítico') & (R['checks'].resultado != 'OK')]
if len(criticos):
    raise Exception(f'{len(criticos)} control(es) CRÍTICO(s) con FALLA: el reparto Dir/Ind NO es confiable. Ver el detalle de diferencias.')
print('✔ Reparto Dir/Ind validado: los 4 controles críticos OK.')
