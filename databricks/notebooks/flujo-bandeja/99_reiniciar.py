# Databricks notebook source
# MAGIC %md
# MAGIC # Ppto27 · 99 Reiniciar (sólo para empezar de cero)
# MAGIC Borra **todas** las tablas `ppto27_*` y el contenido de `10_entrada`, `11_procesado` y `30_bi`.
# MAGIC **No** borra `00_codigo` ni `90_maestros`. Para ejecutar: escribir `BORRAR` en el campo **confirmar** (arriba) y Run all.

# COMMAND ----------

import os, shutil
dbutils.widgets.text('confirmar', '')
if dbutils.widgets.get('confirmar').strip() != 'BORRAR':
    raise Exception('No se borró nada. Escribe BORRAR en el campo "confirmar" (arriba) y vuelve a correr.')

VOLUME = '/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27'
tablas = [r.tableName for r in spark.sql("SHOW TABLES IN catalogo_ppto.esquema_ppto LIKE 'ppto27_*'").collect()]
for t in tablas:
    spark.sql(f'DROP TABLE IF EXISTS catalogo_ppto.esquema_ppto.{t}')
for c in ('10_entrada', '11_procesado', '30_bi'):
    d = f'{VOLUME}/{c}'
    if os.path.isdir(d):
        for x in os.listdir(d):
            p = os.path.join(d, x)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
dbutils.widgets.remove('confirmar')
print(f'Listo: {len(tablas)} tablas borradas; 10_entrada, 11_procesado y 30_bi vacías. Siguiente: 00_setup.')
