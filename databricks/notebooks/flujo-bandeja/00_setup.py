# Databricks notebook source
# MAGIC %md
# MAGIC # Ppto27 · 00 Setup (una sola vez)
# MAGIC Crea las carpetas del Volume y verifica que estén las librerías y los maestros. Si falta algo, dice exactamente qué y dónde.
# MAGIC
# MAGIC ```
# MAGIC /Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27/
# MAGIC ├── 00_codigo/      ← subir: ppto27_lib.py, ppto27_silver.py, ppto27_gold.py, ppto27_spark.py
# MAGIC ├── 10_entrada/     ← subir aquí las plantillas, como vengan: zips de SharePoint, Excel sueltos (cada vez)
# MAGIC ├── 11_procesado/   (lo llena 01_procesar: lo recibido, ordenado por carga)
# MAGIC ├── 30_bi/          (lo llena 01_procesar: el zip con los CSV para el Power BI)
# MAGIC └── 90_maestros/    ← subir: maestros_ppto27.xlsx, alias_ppto27.xlsx, drivers_ppto27.xlsx
# MAGIC ```

# COMMAND ----------

import os
VOLUME = '/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27'
for c in ('00_codigo', '10_entrada', '11_procesado', '30_bi', '90_maestros'):
    os.makedirs(f'{VOLUME}/{c}', exist_ok=True)

requeridos = {'00_codigo': ['ppto27_lib.py', 'ppto27_silver.py', 'ppto27_gold.py', 'ppto27_spark.py'],
              '90_maestros': ['maestros_ppto27.xlsx', 'alias_ppto27.xlsx', 'drivers_ppto27.xlsx']}
filas, faltan = [], []
for carpeta, archivos in requeridos.items():
    for a in archivos:
        ok = os.path.exists(f'{VOLUME}/{carpeta}/{a}')
        filas.append((f'ppto27/{carpeta}', a, 'OK' if ok else 'FALTA SUBIR'))
        if not ok:
            faltan.append(f'ppto27/{carpeta}/{a}')
display(spark.createDataFrame(filas, 'carpeta string, archivo string, estado string'))
if faltan:
    raise Exception('Carpetas listas. Falta subir (Catalog > catalogo_ppto > esquema_ppto > Volumes > vol_administrado): ' + ', '.join(faltan))
print('Setup completo. Siguiente: subir las plantillas a ppto27/10_entrada y correr 01_procesar.')
