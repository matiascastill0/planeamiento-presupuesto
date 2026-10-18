# Databricks notebook source
# MAGIC %md
# MAGIC # Ppto27 · 01 Procesar (cada vez que se sube algo)
# MAGIC **Antes:** subir a `ppto27/10_entrada` lo que llegó, como venga: zips de carpetas de SharePoint (completas o parciales) y/o Excel sueltos.
# MAGIC La versión enviada a las áreas (referencia) se sube una sola vez como zip o carpeta que empiece con `REF_`.
# MAGIC
# MAGIC **Qué hace (sin elegir nada):** recibe lo de `10_entrada` → lo ordena en `11_procesado/<fecha_hora>` → lee las plantillas (bronze) →
# MAGIC limpia, homologa y marca flags (silver) → arma las tablas del Power BI (gold) → controla el cuadre 100 = 100 → deja el zip para el BI en `30_bi`.
# MAGIC Si no hay nada nuevo, recalcula todo con los maestros y alias actuales.
# MAGIC
# MAGIC **Después:** Catalog > `ppto27/30_bi` > descargar el zip más reciente > extraer en `C:\Ppto27\01. Datos ejemplo (CSV)\` (reemplazar) > Power BI > Actualizar.

# COMMAND ----------

# MAGIC %pip install openpyxl --quiet

# COMMAND ----------

import sys
sys.path.append('/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27/00_codigo')
import ppto27_spark as SP

R = SP.procesar(spark)
print(f"Carga {R['carga_id']} · tiempos: " + ', '.join(f'{k} {v:.0f}s' for k, v in R['tiempos'].items()))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Qué se recibió

# COMMAND ----------

display(R['recepcion'])
display(R['archivos'])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Entrega (184 plantillas esperadas) y calidad

# COMMAND ----------

display(R['entrega'])
display(R['lineas'])
display(R['a_revisar'])
display(R['pendientes'])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Controles y archivo para el Power BI

# COMMAND ----------

display(R['controles'])
if not R['ok']:
    raise Exception('Hay controles CRÍTICOS con FALLA: no se generó el archivo para el BI. Revisar la tabla de controles.')
print('Archivo para el Power BI:', R['bi'])
print('Filas por tabla:', R['bi_filas'])
print(r'Descargar desde Catalog > ppto27/30_bi y extraer en C:\Ppto27\01. Datos ejemplo (CSV)\ (reemplazar) > Power BI > Actualizar.')
