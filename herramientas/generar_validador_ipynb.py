"""Genera 95_validar.ipynb: validador AUTÓNOMO del Ppto27 (sólo lee las tablas ppto27_gld_*; no necesita las librerías del Volume).
Pensado para el flujo de notebooks 00_setup / 10_bronze / 20_silver / 30_gold / 90_control / 99_ejecutar_todo.
Salida: carpetas-uso-de-trabajo/95_validar.ipynb  (importar al Workspace de Databricks).
Prueba local: python generar_validador_ipynb.py --probar <volume_local>  (Spark 3.5, tablas parquet en <volume>/_warehouse)
"""
import json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, '..', '..', '..', '..'))
SALIDA = os.path.join(RAIZ, 'carpetas-uso-de-trabajo', '95_validar.ipynb')

CELDAS = []


def md(s): CELDAS.append(('markdown', s.strip('\n')))
def py(s): CELDAS.append(('code', s.strip('\n')))


md('''
# Ppto27 · 95 Validar (después de 99_ejecutar_todo / 30_gold)
Valida que **todo se distribuyó correctamente**, leyendo sólo las tablas `ppto27_gld_*` (las mismas que lee el Power BI).
El reparto Dir/Ind se **recalcula por separado** (contable + tabla de drivers + plantillas) y se compara con `ppto27_gld_fact_gestion_dirind`:
no usa el código que lo generó, por eso es una prueba independiente.

| # | Control | Tipo | Qué prueba |
|---|---|---|---|
| A1 | Formato Perú | Dato | Toda línea con monto mapeada a Nivel 1 / Nivel 2 |
| A2 | Signo | Dato | Ningún monto positivo en líneas OK (gasto en negativo) |
| A3 | Tipo de cambio | Crítico | Toda línea con monto en moneda origen tiene monto en PEN y en moneda local |
| B1 | Conservación | Crítico | Cada línea contable × mes se reparte al 100 %: no se pierde ni se duplica plata |
| B2 | Drivers 100 % | Crítico | En la tabla de drivers cada país × CeCo × vehículo suma 100 % |
| B3 | Recálculo | Crítico | Línea × mes × UdN × componente = monto × % del driver (vehículo exacto, si no "(todos)"; sin driver → regla) |
| B4 | Indirectos | Crítico | La bolsa de indirectos de cada país × mes se reparte según la participación de la imputación directa por UdN |
| B5 | Sin base | Dato | Indirectos que no se pudieron repartir (país sin imputación directa) |
| B6 | Fuera | Dato | Líneas contables OK que no entran al Dir/Ind (país no reconocido) |
| B7 | Sin driver | Revisar | CeCo × vehículo sin driver, repartidos por regla → confirmar con Planeamiento |

Deja el Excel `Validacion_Ppto27_<fecha_hora>.xlsx` en `ppto27/95_validacion` (para compartir) y el historial en `ppto27_ctl_validacion`.
''')
py('%pip install openpyxl --quiet')
py('''
# ── Configuración (igual que en Power BI: catálogo y esquema) ──
CATALOGO, ESQUEMA = 'catalogo_ppto', 'esquema_ppto'
VOLUME = '/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27'
TOL = 0.01                                                          # tolerancia de cuadre (PEN)

# Reglas del reparto (las mismas de ppto27_gold / ppto27_spark)
ESTADOS_OK = ['OK', 'OK con alerta']
PAISES_DIRIND = ['Perú', 'Colombia', 'Chile', 'Panamá', 'USA', 'México']   # países con moneda local (entran al Dir/Ind)
TYBA = [113, 346, 810, 811, 818]                                    # CeCos de negocio fuera de la regla de 3 dígitos

import os, io
from datetime import datetime
import pandas as pd
from pyspark.sql import functions as F, Window as W

def tabla(n):
    return f'{CATALOGO}.{ESQUEMA}.ppto27_{n}' if CATALOGO else f'ppto27_{n}'

def T(n):
    return spark.table(tabla(f'gld_{n}'))

def es_negocio(c):
    s = c.cast('string')
    return c.isin(*TYBA) | ((F.length(s) == 3) & F.substring(s, 1, 1).isin('2', '5', '6', '8', '9'))

# las columnas que usa el validador deben existir (si gold es de otra versión, lo dice aquí y no a mitad de camino)
NECESARIAS = {'fact_ppto': ['id_linea', 'id_plantilla', 'id_fecha', 'id_pais', 'id_ceco', 'id_vehiculo', 'id_linea_pyg', 'monto_origen',
                            'monto_local', 'monto_pen', 'estado_linea'],
              'fact_gestion_dirind': ['id_linea', 'id_fecha', 'id_pais', 'id_udn', 'id_componente', 'monto_pen'],
              'dim_driver': ['pais', 'ceco', 'vehiculo', 'componente', 'udn', 'porcentaje'],
              'dim_componente': ['id_componente', 'componente', 'grupo'], 'dim_plantilla': ['id_plantilla', 'archivo', 'tipo', 'area'],
              'dim_linea_pyg': ['id_linea_pyg', 'n1_formato', 'n2_formato', 'orden_n1', 'orden_n2'], 'dim_fecha': ['id_fecha', 'mes_num', 'periodo'],
              'dim_ceco': ['id_ceco', 'ceco_nombre', 'agrupacion']}
falta = [f'ppto27_gld_{t}.{c}' for t, cs in NECESARIAS.items() for c in cs if c not in T(t).columns]
if falta:
    raise Exception(f'Faltan columnas en gold (correr 30_gold con las librerías actuales): {falta}')
CHECKS, DET = [], {}

def chk(clave, nombre, tipo, fallas, casos, detalle, df=None):
    malo = 'FALLA' if tipo == 'Crítico' else 'REVISAR'
    CHECKS.append(dict(control=nombre, tipo=tipo, resultado='OK' if fallas == 0 else malo, casos=int(casos), con_diferencia=int(fallas), detalle=detalle))
    if df is not None:
        DET[clave] = df
print('Tablas gold OK:', ', '.join(NECESARIAS))
''')
md('''
## A · Contable (lo que ve la página Formato Perú)
''')
py('''
fp = T('fact_ppto')
ok = fp.where(F.col('estado_linea').isin(*ESTADOS_OK))

sm = fp.where('id_linea_pyg = 0').groupBy('id_plantilla', 'id_linea').agg(F.round(F.sum('monto_pen'), 2).alias('monto_pen'))
n = sm.count()
chk('a1_sin_mapeo', 'A1. Toda línea con monto mapeada al Formato Perú (N1 / N2)', 'Dato', n, fp.select('id_linea').distinct().count(),
    f'{n} líneas sin Nivel 1 / Nivel 2 del formato', sm.toPandas())

pos = ok.where('monto_origen > 0').select('id_plantilla', 'id_linea', 'id_fecha', 'monto_origen')
n = pos.count()
chk('a2_positivos', 'A2. Ningún monto positivo en líneas OK (gasto en negativo)', 'Dato', n, ok.count(), f'{n} filas positivas', pos.limit(500).toPandas())

sin_tc = fp.where((F.abs('monto_origen') > 0) & ((F.coalesce('monto_pen', F.lit(0.0)) == 0) | (F.coalesce('monto_local', F.lit(0.0)) == 0)))
n = sin_tc.count()
chk('a3_tc', 'A3. Todo monto en moneda origen tiene monto PEN y moneda local (tipo de cambio)', 'Crítico', n, fp.count(),
    f'{n} filas sin conversión', sin_tc.select('id_plantilla', 'id_linea', 'id_fecha', 'id_pais', 'moneda_origen', 'monto_origen').limit(500).toPandas())

display(fp.groupBy('estado_linea').agg(F.countDistinct('id_linea').alias('lineas'), F.round(F.sum('monto_pen'), 0).alias('monto_pen')).orderBy('estado_linea'))
''')
md('''
## B · Gestión Dir/Ind (lo que ve la página Dir-Ind)
''')
py('''
gd = T('fact_gestion_dirind').join(F.broadcast(T('dim_componente').select('id_componente', 'componente')), 'id_componente', 'left')
dd = T('dim_driver').select('pais', 'ceco', 'vehiculo', 'componente', 'udn', 'porcentaje')

# Alcance: líneas contables OK, de país con moneda local, con monto PEN ≠ 0 (CeCo y vehículo salen de las claves "País|valor")
A = (fp.where(F.col('estado_linea').isin(*ESTADOS_OK) & F.col('id_pais').isin(*PAISES_DIRIND) & (F.abs('monto_pen') > 0))
     .groupBy('id_linea', 'id_plantilla', 'id_fecha', 'id_pais', 'id_ceco', 'id_vehiculo').agg(F.sum('monto_pen').alias('pen'))
     .withColumn('ceco', F.expr('try_cast(substring(id_ceco, length(id_pais) + 2) AS BIGINT)'))
     .withColumn('vehiculo', F.expr('substring(id_vehiculo, length(id_pais) + 2)')))

# B1 · conservación
b1 = (A.groupBy('id_linea', 'id_fecha', 'id_pais').agg(F.sum('pen').alias('contable'))
      .join(gd.groupBy('id_linea', 'id_fecha').agg(F.sum('monto_pen').alias('repartido')), ['id_linea', 'id_fecha'], 'full')
      .fillna(0.0, ['contable', 'repartido']).withColumn('diferencia', F.round(F.col('contable') - F.col('repartido'), 4)))
n, f = b1.count(), b1.where(F.abs('diferencia') >= TOL)
nf = f.count()
chk('b1_conservacion', 'B1. Cada línea contable × mes se reparte al 100 % (contable = suma de su reparto)', 'Crítico', nf, n,
    f'{n:,} línea × mes; {nf} con diferencia ≥ {TOL}', f.orderBy(F.abs('diferencia').desc()).limit(500).toPandas())

# B2 · drivers 100 %
b2 = dd.groupBy('pais', 'ceco', 'vehiculo').agg(F.round(F.sum('porcentaje'), 8).alias('suma_porcentaje'))
f = b2.where(F.abs(F.col('suma_porcentaje') - 1) > 1e-6)
nf = f.count()
chk('b2_drivers_100', 'B2. Tabla de drivers: cada país × CeCo × vehículo suma 100 %', 'Crítico', nf, b2.count(), f'{nf} combinaciones que no suman 100 %', f.toPandas())

# B3 · recálculo línea por línea (la parte indirecta se compara como total "(bolsa)" de la línea)
exactos = dd.select(F.col('pais').alias('id_pais'), 'ceco', 'vehiculo').distinct().withColumn('exacto', F.lit(True))
B = (A.join(exactos, ['id_pais', 'ceco', 'vehiculo'], 'left')
     .withColumn('veh_driver', F.when(F.col('exacto'), F.col('vehiculo')).otherwise(F.lit('(todos)'))))
ddk = dd.withColumnRenamed('pais', 'id_pais').withColumnRenamed('vehiculo', 'veh_driver')
con = B.join(ddk, ['id_pais', 'ceco', 'veh_driver']).select('id_linea', 'id_fecha', 'componente', 'udn', (F.col('pen') * F.col('porcentaje')).alias('m'))
sin = (B.join(ddk.select('id_pais', 'ceco', 'veh_driver').distinct(), ['id_pais', 'ceco', 'veh_driver'], 'left_anti')
       .join(F.broadcast(T('dim_plantilla').select('id_plantilla', 'tipo', 'area')), 'id_plantilla', 'left'))
regla = F.col('ceco').isNotNull() & es_negocio(F.col('ceco')) & (F.col('tipo') == 'UdN')
sin_r = sin.select('id_linea', 'id_fecha', F.when(regla, 'Imputación directa').otherwise('Indirecto').alias('componente'),
                   F.when(regla, F.col('area')).otherwise('BOLSA').alias('udn'), F.col('pen').alias('m'))
es_ind = F.col('componente').isin('Indirecto', 'Indirecto asignado')
clave = [F.when(es_ind, F.lit('Indirecto')).otherwise(F.col('componente')).alias('componente'), F.when(es_ind, F.lit('(bolsa)')).otherwise(F.col('udn')).alias('udn')]
k4 = ['id_linea', 'id_fecha', 'componente', 'udn']
esp = con.unionByName(sin_r).select('id_linea', 'id_fecha', *clave, 'm').groupBy(*k4).agg(F.sum('m').alias('esperado'))
act = gd.withColumnRenamed('id_udn', 'udn').select('id_linea', 'id_fecha', *clave, 'monto_pen').groupBy(*k4).agg(F.sum('monto_pen').alias('en_tabla'))
b3 = esp.join(act, k4, 'full').fillna(0.0, ['esperado', 'en_tabla']).withColumn('diferencia', F.round(F.col('esperado') - F.col('en_tabla'), 4))
n, f = b3.count(), b3.where(F.abs('diferencia') >= TOL)
nf = f.count()
chk('b3_recalculo', 'B3. Recálculo independiente línea × mes × UdN × componente = fact_gestion_dirind (driver o regla)', 'Crítico', nf, n,
    f'{n:,} combinaciones; {nf} con diferencia ≥ {TOL}', f.orderBy(F.abs('diferencia').desc()).limit(500).toPandas())

# B4 · indirectos proporcionales a la imputación directa de cada UdN (país × mes)
imp = gd.where("componente = 'Imputación directa'").groupBy('id_pais', 'id_fecha', 'id_udn').agg(F.sum('monto_pen').alias('imp'))
ind = gd.where("componente = 'Indirecto asignado' AND id_udn <> 'Sin base de reparto'")
b4 = (imp.withColumn('part_imputacion', F.col('imp') / F.sum('imp').over(W.partitionBy('id_pais', 'id_fecha')))
      .join(ind.groupBy('id_pais', 'id_fecha', 'id_udn').agg(F.sum('monto_pen').alias('indirecto_asignado')), ['id_pais', 'id_fecha', 'id_udn'], 'full')
      .join(ind.groupBy('id_pais', 'id_fecha').agg(F.sum('monto_pen').alias('bolsa')), ['id_pais', 'id_fecha'], 'left')
      .fillna(0.0, ['imp', 'indirecto_asignado', 'bolsa', 'part_imputacion'])
      .withColumn('esperado', F.col('bolsa') * F.col('part_imputacion'))
      .withColumn('diferencia', F.round(F.col('esperado') - F.col('indirecto_asignado'), 4)))
n, f = b4.count(), b4.where(F.abs('diferencia') >= TOL)
nf = f.count()
chk('b4_indirectos', 'B4. Indirectos de cada país × mes repartidos según la participación de la imputación directa por UdN', 'Crítico', nf, n,
    f'{n:,} país × mes × UdN; {nf} con diferencia ≥ {TOL}', b4.orderBy('id_pais', 'id_fecha', 'id_udn').toPandas())

# B5 · sin base de reparto
sb = gd.where("id_udn = 'Sin base de reparto'").groupBy('id_pais').agg(F.round(F.sum('monto_pen'), 2).alias('monto_pen')).toPandas()
chk('b5_sin_base', 'B5. Indirectos sin base de reparto (país sin imputación directa)', 'Dato', len(sb), len(sb),
    'ninguno' if sb.empty else ', '.join(f'{r.id_pais} {r.monto_pen:,.0f}' for r in sb.itertuples()), sb)

# B6 · líneas OK fuera del Dir/Ind
fu = (ok.where(~F.col('id_pais').isin(*PAISES_DIRIND)).groupBy('id_pais')
      .agg(F.countDistinct('id_linea').alias('lineas'), F.round(F.sum('monto_pen'), 2).alias('monto_pen')).toPandas())
chk('b6_fuera', 'B6. Líneas contables OK fuera del Dir/Ind (país no reconocido)', 'Dato', len(fu), len(fu),
    'ninguna' if fu.empty else ', '.join(f'{r.id_pais}: {r.lineas} líneas' for r in fu.itertuples()), fu)

# B7 · CeCos sin driver (repartidos por regla)
sd = (sin.join(F.broadcast(T('dim_ceco').select('id_ceco', 'ceco_nombre', 'agrupacion')), 'id_ceco', 'left')
      .withColumn('destino', F.when(regla, F.concat(F.lit('Imputación directa → '), F.col('area'))).otherwise(F.lit('Bolsa de indirectos')))
      .groupBy('id_pais', 'ceco', 'ceco_nombre', 'agrupacion', 'vehiculo', 'destino')
      .agg(F.countDistinct('id_linea').alias('lineas'), F.round(F.sum('pen'), 2).alias('monto_pen')).orderBy('id_pais', 'ceco').toPandas())
chk('b7_sin_driver', 'B7. CeCo × vehículo sin driver (repartidos por regla; confirmar con Planeamiento)', 'Revisar', len(sd), len(sd),
    f'{len(sd)} CeCo × vehículo; {sd.monto_pen.sum() if len(sd) else 0:,.0f} PEN', sd)

CH = pd.DataFrame(CHECKS)
display(CH)
''')
md('''
## C · Cruce con el Power BI
Filtrar el mismo país en el BI: **Formato Perú** (contable, líneas OK) debe dar `contable_pen` y **Dir-Ind** debe dar `directo_pen` + `indirecto_pen`.
`diferencia` = 0 en todas las filas. Si en el BI no cuadra pero aquí sí, el problema está en la medida DAX o en un filtro de la página, no en los datos.
''')
py('''
pyg = F.broadcast(T('dim_linea_pyg').select('id_linea_pyg', 'orden_n1', 'n1_formato', 'orden_n2', 'n2_formato'))
grp = F.broadcast(T('dim_componente').select('id_componente', 'grupo'))
kk = ['id_pais', 'orden_n1', 'n1_formato', 'orden_n2', 'n2_formato']
c = ok.where(F.col('id_pais').isin(*PAISES_DIRIND)).join(pyg, 'id_linea_pyg', 'left').groupBy(*kk).agg(F.sum('monto_pen').alias('contable_pen'))
g = (T('fact_gestion_dirind').join(pyg, 'id_linea_pyg', 'left').join(grp, 'id_componente', 'left').groupBy(*kk)
     .pivot('grupo', ['Directo', 'Indirecto']).agg(F.sum('monto_pen')))
RES = (c.join(g, kk, 'full').fillna(0.0).toPandas().rename(columns={'Directo': 'directo_pen', 'Indirecto': 'indirecto_pen'})
       .sort_values(['id_pais', 'orden_n1', 'orden_n2']).drop(columns=['orden_n1', 'orden_n2']))
RES['dirind_pen'] = RES.directo_pen + RES.indirecto_pen
RES['diferencia'] = (RES.contable_pen - RES.dirind_pen).round(2)
for col in ('contable_pen', 'directo_pen', 'indirecto_pen', 'dirind_pen'):
    RES[col] = RES[col].round(2)
N1 = RES.groupby(['id_pais', 'n1_formato'], sort=False)[['contable_pen', 'directo_pen', 'indirecto_pen', 'dirind_pen', 'diferencia']].sum().round(2).reset_index()
UDN = (T('fact_gestion_dirind').join(grp, 'id_componente', 'left').groupBy('id_pais', 'id_udn')
       .pivot('grupo', ['Directo', 'Indirecto']).agg(F.round(F.sum('monto_pen'), 2)).fillna(0.0).orderBy('id_pais', 'id_udn').toPandas())
display(N1)
display(UDN)
''')
md('''
## D · Para revisar con Planeamiento: CeCos sin driver
''')
py('''
display(DET['b7_sin_driver'])
''')
md('''
## E · Detalle de diferencias (sólo si algún control dio FALLA)
''')
py('''
for k, v in DET.items():
    if len(v) and k not in ('b4_indirectos', 'b7_sin_driver', 'b5_sin_base', 'b6_fuera'):
        print(k); display(v)
''')
md('''
## F · Trazabilidad de una línea (prueba a mano)
Pega un `id_linea` (del BI o de `ppto27_gld_fact_ppto`) entre comillas. Con `None` toma la de mayor monto cuyo driver reparte entre varias UdN.
Muestra: la línea contable → los drivers que le tocan → cómo quedó repartida por UdN y componente, mes a mes. `total` debe ser igual al contable.
''')
py('''
ID_LINEA = None          # ejemplo: '03 | UDN | WM | Perú | WM#78'

if ID_LINEA is None:
    varios = dd.groupBy(F.col('pais').alias('id_pais'), 'ceco').agg(F.countDistinct('udn', 'componente').alias('n')).where('n > 1')
    ID_LINEA = (A.join(varios.select('id_pais', 'ceco'), ['id_pais', 'ceco']).groupBy('id_linea')
                .agg(F.sum(F.abs('pen')).alias('a')).orderBy(F.desc('a')).first()['id_linea'])
lin = A.where(F.col('id_linea') == ID_LINEA)
x = lin.select('id_pais', 'ceco', 'vehiculo').distinct().first()
if x is None:
    raise Exception(f'La línea {ID_LINEA} no entra al Dir/Ind (estado no OK, país sin moneda local o monto 0)')
print('Línea:', ID_LINEA)
display(fp.where(F.col('id_linea') == ID_LINEA).join(T('dim_plantilla').select('id_plantilla', 'archivo', 'tipo', 'area'), 'id_plantilla', 'left')
        .join(T('dim_linea_pyg').select('id_linea_pyg', 'n1_formato', 'n2_formato'), 'id_linea_pyg', 'left')
        .groupBy('id_linea', 'archivo', 'tipo', 'area', 'id_pais', 'id_ceco', 'id_vehiculo', 'n1_formato', 'n2_formato', 'estado_linea')
        .agg(F.round(F.sum('monto_pen'), 2).alias('total_pen')))
drv = dd.where((F.col('pais') == x['id_pais']) & (F.col('ceco') == x['ceco']))
drv = drv.where(F.col('vehiculo') == (x['vehiculo'] if drv.where(F.col('vehiculo') == x['vehiculo']).count() else '(todos)'))
if drv.count():
    display(drv)
else:
    print('Sin driver: se reparte por regla (CeCo de negocio en plantilla UdN → imputación directa a su UdN; si no, bolsa de indirectos)')
meses = [r.periodo for r in T('dim_fecha').orderBy('mes_num').select('periodo').collect()]
rep = (T('fact_gestion_dirind').where(F.col('id_linea') == ID_LINEA)
       .join(T('dim_componente').select('id_componente', 'componente'), 'id_componente')
       .join(T('dim_fecha').select('id_fecha', 'periodo'), 'id_fecha')
       .groupBy('id_udn', 'componente').pivot('periodo', meses).agg(F.round(F.sum('monto_pen'), 2)))
rep = rep.withColumn('total', F.round(sum(F.coalesce(F.col(f'`{m}`'), F.lit(0.0)) for m in meses), 2)).orderBy('componente', 'id_udn')
display(lin.join(T('dim_fecha').select('id_fecha', 'periodo', 'mes_num'), 'id_fecha').select('periodo', F.round('pen', 2).alias('contable_pen')).orderBy('mes_num'))
display(rep)
''')
md('''
## G · Guardar resultado (Excel en el Volume + historial) y veredicto
''')
py('''
ahora = datetime.now()
hojas = [('Controles', CH), ('Cruce BI N1', N1), ('Cruce BI N2', RES), ('UdN por país', UDN)] + \\
        [(n, DET[k]) for n, k in [('Sin driver', 'b7_sin_driver'), ('Indirectos por UdN', 'b4_indirectos'), ('Dif conservacion', 'b1_conservacion'),
                                  ('Dif recalculo', 'b3_recalculo'), ('Drivers no 100', 'b2_drivers_100'), ('Sin base de reparto', 'b5_sin_base'),
                                  ('Fuera del Dir-Ind', 'b6_fuera'), ('Sin mapeo FP', 'a1_sin_mapeo'), ('Positivos', 'a2_positivos'), ('Sin TC', 'a3_tc')]]
b = io.BytesIO()
with pd.ExcelWriter(b, engine='openpyxl') as w:
    for n, df in hojas:
        df.to_excel(w, sheet_name=n, index=False)
os.makedirs(f'{VOLUME}/95_validacion', exist_ok=True)
ruta = f'{VOLUME}/95_validacion/Validacion_Ppto27_{ahora:%Y%m%d_%H%M%S}.xlsx'
with open(ruta, 'wb') as fh:                                        # se escribe de una vez (el Volume no admite escritura aleatoria)
    fh.write(b.getvalue())
print('Excel:', ruta)

(spark.createDataFrame(CH.assign(fecha_validacion=ahora))
 .write.mode('append').option('mergeSchema', 'true').saveAsTable(tabla('ctl_validacion')))

criticos = CH[(CH.tipo == 'Crítico') & (CH.resultado != 'OK')]
if len(criticos):
    raise Exception(f'{len(criticos)} control(es) CRÍTICO(s) con FALLA: ' + '; '.join(criticos.control) + '. Ver la sección E.')
print('✔ Todo distribuido correctamente: controles críticos OK.', f'{(CH.resultado == "REVISAR").sum()} punto(s) para revisar (Dato / Revisar).')
''')

md('''
## H · Reporte en texto (para copiar y pegar a Claude / al equipo)
''')
py(r'''
# REPORTE PARA COPIAR (tras 95_validar)
out = []

def p(*xs):
    s = [str(x) for x in xs]
    out.append(" | ".join(s))

def m(x):
    return f"{x:,.2f}"

p("PPTO27 VALIDACION", datetime.now())

p("== FILAS GOLD ==")
TB = ["fact_ppto", "fact_flags",
      "fact_gestion_dirind",
      "dim_plantilla", "dim_driver",
      "dim_ceco", "dim_udn"]
for n in TB:
    p(n, T(n).count())
PL = T("dim_plantilla")
PL = PL.groupBy("entrega").count()
for r in PL.collect():
    p("plantillas", r[0], r[1])

p("== CONTROLES ==")
for r in CH.itertuples():
    cod = r.control.split(".")[0]
    p(r.resultado, cod, r.casos,
      r.con_diferencia, r.detalle)

p("== ESTADO: lineas | PEN ==")
E = fp.groupBy("estado_linea")
E = E.agg(
    F.countDistinct("id_linea"),
    F.sum("monto_pen"))
for r in E.collect():
    p(r[0], r[1], m(r[2]))

p("== PAIS: cont | dir | ind | dif ==")
C = ["contable_pen", "directo_pen",
     "indirecto_pen", "diferencia"]
PA = N1.groupby("id_pais")[C].sum()
for k, r in PA.iterrows():
    p(k, *[m(r[c]) for c in C])
TT = PA.sum()
p("TOTAL", *[m(TT[c]) for c in C])

p("== PAIS x N1: cont | dirind | dif ==")
for r in N1.itertuples():
    p(r.id_pais, r.n1_formato,
      m(r.contable_pen),
      m(r.dirind_pen),
      m(r.diferencia))

p("== UDN x PAIS: dir | ind ==")
for r in UDN.itertuples():
    p(r.id_pais, r.id_udn,
      m(r.Directo), m(r.Indirecto))

p("== SIN DRIVER (top 15) ==")
SD = DET["b7_sin_driver"].copy()
SD["a"] = SD["monto_pen"].abs()
SD = SD.sort_values("a", ascending=False)
for r in SD.head(15).itertuples():
    p(r.id_pais, r.ceco, r.vehiculo,
      r.destino, r.lineas,
      m(r.monto_pen))

p("== SIN MAPEO FORMATO PERU ==")
SM = DET["a1_sin_mapeo"]
for r in SM.head(15).itertuples():
    p(r.id_linea, m(r.monto_pen))

p("== DIFERENCIAS (top 10) ==")
for k in ["b1_conservacion",
          "b3_recalculo"]:
    p(k, len(DET[k]), "filas")
    DD = DET[k].head(10)
    for x in DD.to_dict("records"):
        p(x)

CR = CH[CH.tipo == "Crítico"]
NO = CR[CR.resultado != "OK"]
p("VEREDICTO",
  "OK" if len(NO) == 0 else "FALLA")
print("\n".join(out))
''')


def notebook():
    def fuente(s):
        ls = s.split('\n')
        return [l + '\n' for l in ls[:-1]] + [ls[-1]]
    cells = []
    for tipo, s in CELDAS:
        c = {'cell_type': tipo, 'metadata': {}, 'source': fuente(s)}
        if tipo == 'code':
            c.update(execution_count=None, outputs=[])
        cells.append(c)
    return {'cells': cells, 'metadata': {'language_info': {'name': 'python'}, 'application/vnd.databricks.v1+notebook': {
        'notebookName': '95_validar', 'language': 'python'}}, 'nbformat': 4, 'nbformat_minor': 0}


def probar(volume):
    """Corre las celdas con Spark local sobre las tablas parquet de una prueba (sin catálogo)."""
    from pyspark.sql import SparkSession
    spark = (SparkSession.builder.master('local[*]').config('spark.ui.enabled', 'false').config('spark.sql.shuffle.partitions', '8')
             .config('spark.sql.ansi.enabled', 'true').config('spark.sql.warehouse.dir', os.path.join(volume, '_warehouse_validar')).getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    wh = os.path.join(volume, '_warehouse')
    for d in os.listdir(wh):
        if d.startswith('ppto27_gld'):
            spark.read.parquet(os.path.join(wh, d)).createOrReplaceTempView(d)
    import shutil
    shutil.rmtree(os.path.join(volume, '_warehouse_validar'), ignore_errors=True)
    g = dict(spark=spark, display=lambda d: print(type(d).__name__, getattr(d, 'shape', '') or (d.count(), len(d.columns))))
    for tipo, s in CELDAS:
        if tipo != 'code' or s.startswith('%pip'):
            continue
        s = s.replace("CATALOGO, ESQUEMA = 'catalogo_ppto', 'esquema_ppto'", 'CATALOGO, ESQUEMA = None, None')
        s = s.replace("VOLUME = '/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27'", f'VOLUME = {volume!r}')
        exec(s, g)
    print(g['CH'][['control', 'resultado', 'con_diferencia', 'detalle']].to_string())
    print(g['N1'].to_string())
    return g


if __name__ == '__main__':
    if '--probar' in sys.argv:
        probar(sys.argv[sys.argv.index('--probar') + 1])
    else:
        with open(SALIDA, 'w', encoding='utf-8') as f:
            json.dump(notebook(), f, ensure_ascii=False, indent=1)
        print('OK', SALIDA)
