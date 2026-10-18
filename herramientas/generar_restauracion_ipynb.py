"""Genera 98_restauracion.ipynb: guardar un punto de regreso de las tablas ppto27_*, ver qué cambiaría y restaurar
(Delta RESTORE por versión exacta, no por hora), más la limpieza opcional de carpetas del Volume.
Nada se restaura ni se borra si no se escribe CONFIRMAR = 'SI'.
Uso: python3 generar_restauracion_ipynb.py [--probar]   (--probar: ejecuta las celdas en Spark local con Delta)
"""
import json, os, sys, shutil, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
DBX = os.path.dirname(os.path.dirname(os.path.dirname(AQUI)))
SALIDA = os.path.join(DBX, '90. Workflows (pruebas y prototipos)', '07. Demo 3 plantillas Dir-Ind', '98_restauracion.ipynb')

CELDAS = [
('md', r"""# 98 · Restauración de las tablas Ppto27

Sirve para **volver las tablas a un momento anterior**, por ejemplo después de ensayar la demo.

| Paso | Qué hace | Cuándo |
|---|---|---|
| **1 · Guardar punto** | Anota la versión de cada tabla `ppto27_*` con un nombre | **Antes** de cargar algo de prueba |
| **2 · Puntos guardados** | Lista los puntos disponibles | Cuando se quiera volver |
| **3 · Vista previa** | Muestra qué tablas y qué cargas cambiarían. No modifica nada | Antes de restaurar |
| **4 · Restaurar** | Devuelve cada tabla a la versión del punto | Solo con `CONFIRMAR = 'SI'` |
| **5 · Limpiar archivos** | Borra del Volume las carpetas de prueba (opcional) | Solo con `CONFIRMAR_BORRADO = 'SI'` |
| **6 · Estado final** | Muestra qué cargas quedaron en las tablas y en `10_cargas` | Al terminar |

Restaurar es necesario para repetir una prueba: las tablas recuerdan cada archivo por su huella y, si se vuelve a subir el mismo Excel sin restaurar, se marca como **REPETIDO** y no se vuelve a leer."""),

('code', r"""import json, os, shutil
import pandas as pd
from pyspark.sql import functions as F

CAT = 'catalogo_ppto.esquema_ppto'
VOL = '/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27'
PUNTOS = f'{VOL}/41_puntos_restauracion'
CARGAS = f'{VOL}/10_cargas'


def tablas():
    return sorted(r.tableName for r in spark.sql(f'SHOW TABLES IN {CAT}').collect() if r.tableName.startswith('ppto27_'))


def historia(t):
    return spark.sql(f'DESCRIBE HISTORY {CAT}.{t}').select('version', 'timestamp', 'operation')


def version_actual(t):
    return historia(t).agg(F.max('version')).first()[0]


def cargas_en_tablas(version=None):
    v = '' if version is None else f' VERSION AS OF {version}'
    try:
        return sorted(r.carga_id for r in spark.sql(f'SELECT DISTINCT carga_id FROM {CAT}.ppto27_brz_archivos{v}').collect())
    except Exception:
        return []


def ahora_utc():
    return str(spark.sql('SELECT current_timestamp() AS t').first().t)[:19]


print(f'{len(tablas())} tablas ppto27_* en {CAT} · hora actual (UTC) {ahora_utc()}')
print('Cargas que hoy están en las tablas:', cargas_en_tablas())"""),

('md', r"""## 1 · Guardar punto de regreso
Correr **antes** de cargar algo de prueba. Cambiar el nombre si se guarda más de un punto."""),

('code', r"""NOMBRE = 'antes_ensayo_demo'                       # sin espacios
NOTA = 'Antes de ensayar la demo de 3 plantillas'
SOBRESCRIBIR = False                                # True para reemplazar un punto con el mismo nombre

ruta = f'{PUNTOS}/{NOMBRE}.json'
if os.path.exists(ruta) and not SOBRESCRIBIR:
    print(f'Ya existe el punto "{NOMBRE}". Usar otro nombre o SOBRESCRIBIR = True.')
else:
    os.makedirs(PUNTOS, exist_ok=True)
    punto = dict(nombre=NOMBRE, nota=NOTA, fecha_utc=ahora_utc(),
                 versiones={t: int(version_actual(t)) for t in tablas()}, cargas=cargas_en_tablas())
    with open(ruta, 'w') as f:
        json.dump(punto, f, indent=1)
    print(f'Punto "{NOMBRE}" guardado · {punto["fecha_utc"]} UTC · {len(punto["versiones"])} tablas')
    print('Cargas en ese momento:', punto['cargas'])"""),

('md', "## 2 · Puntos guardados"),

('code', r"""filas = []
if os.path.isdir(PUNTOS):
    for a in sorted(os.listdir(PUNTOS)):
        if a.endswith('.json'):
            with open(f'{PUNTOS}/{a}') as f:
                p = json.load(f)
            filas.append(dict(punto=p['nombre'], fecha_utc=p['fecha_utc'], nota=p.get('nota', ''),
                              tablas=len(p['versiones']), cargas=len(p.get('cargas', []))))
if filas:
    display(pd.DataFrame(filas).sort_values('fecha_utc', ascending=False))
else:
    print('Todavía no hay puntos guardados (paso 1).')"""),

('md', r"""## 3 · Vista previa (no modifica nada)
`PUNTO` es el nombre de un punto guardado. También acepta una hora UTC `'AAAA-MM-DD HH:MM:SS'` para volver a un momento en el que no se guardó un punto."""),

('code', r"""PUNTO = 'antes_ensayo_demo'


def versiones_del_punto(p):
    ruta = f'{PUNTOS}/{p}.json'
    if os.path.exists(ruta):
        with open(ruta) as f:
            return json.load(f)['versiones']
    vers = {}
    for t in tablas():                                  # por hora: la última versión escrita hasta esa hora
        v = historia(t).where(F.col('timestamp') <= F.lit(p).cast('timestamp')).agg(F.max('version')).first()[0]
        vers[t] = None if v is None else int(v)
    return vers


vers = versiones_del_punto(PUNTO)
plan = []
for t in tablas():
    actual, objetivo = int(version_actual(t)), vers.get(t)
    if objetivo is None:
        accion = 'se deja igual (no existía en ese punto)'
    elif actual == objetivo:
        accion = 'sin cambios'
    else:
        accion = 'RESTAURAR'
    plan.append(dict(tabla=t, version_actual=actual, version_punto=objetivo, accion=accion))
PLAN = pd.DataFrame(plan)
PLAN['version_punto'] = PLAN.version_punto.astype('Int64')
PLAN_DE = PUNTO
display(PLAN)
v_arch = vers.get('ppto27_brz_archivos')
antes, hoy = set(cargas_en_tablas(v_arch)) if v_arch is not None else set(), set(cargas_en_tablas())
print(f'Tablas a restaurar: {(PLAN.accion == "RESTAURAR").sum()} de {len(PLAN)}')
print('Cargas que salen de las tablas:', sorted(hoy - antes) or 'ninguna')
print('Cargas que vuelven:', sorted(antes - hoy) or 'ninguna')"""),

('md', r"""## 4 · Restaurar
Revisar la vista previa y escribir `CONFIRMAR = 'SI'`. Al terminar, volver a dejarlo en `'NO'`."""),

('code', r"""CONFIRMAR = 'NO'

if CONFIRMAR != 'SI':
    print("No se hizo nada. Para restaurar escribir CONFIRMAR = 'SI' y volver a correr esta celda.")
elif 'PLAN' not in globals() or PLAN_DE != PUNTO:
    print('Primero correr la vista previa (paso 3) con este PUNTO.')
else:
    res = []
    for r in PLAN.itertuples():
        if r.accion != 'RESTAURAR':
            res.append((r.tabla, r.accion))
            continue
        try:
            spark.sql(f'RESTORE TABLE {CAT}.{r.tabla} TO VERSION AS OF {int(r.version_punto)}')
            res.append((r.tabla, f'restaurada a la versión {int(r.version_punto)}'))
        except Exception as e:
            res.append((r.tabla, 'ERROR: ' + str(e)[:150]))
    R = pd.DataFrame(res, columns=['tabla', 'resultado'])
    display(R)
    errores = R.resultado.str.startswith('ERROR').sum()
    print('Listo: tablas restauradas.' if not errores else f'{errores} tabla(s) con error: revisar arriba.')
    print('Cargas que quedan en las tablas:', cargas_en_tablas())"""),

('md', r"""## 5 · Limpiar archivos de prueba del Volume (opcional)
Borra carpetas de `10_cargas` y, si se quiere, `40_tiempos` (tiempos y resúmenes del `08_demo`). Primero muestra lo que encontró."""),

('code', r"""BORRAR = ['20261016_0900_Demo1_Imputacion_directa', '20261016_1000_Demo2_Soporte_directo', '20261016_1100_Demo3_Indirecto',
          '20261017_0800_Demo_Limpias', '20261017_0900_Demo_Con_errores']   # carpetas de demos anteriores en 10_cargas
BORRAR_TIEMPOS = True
CONFIRMAR_BORRADO = 'NO'

objetivos = [f'{CARGAS}/{c}' for c in BORRAR if c and '/' not in c and os.path.isdir(f'{CARGAS}/{c}')]
if BORRAR_TIEMPOS and os.path.isdir(f'{VOL}/40_tiempos'):
    objetivos.append(f'{VOL}/40_tiempos')
faltan = [c for c in BORRAR if not os.path.isdir(f'{CARGAS}/{c}')]
print('Se borraría:', *objetivos, sep='\n  ') if objetivos else print('No hay nada que borrar.')
if faltan:
    print('No están en 10_cargas (ya borradas o mal escritas):', faltan)
if CONFIRMAR_BORRADO == 'SI' and objetivos:
    for o in objetivos:
        if 'dbutils' in globals():
            dbutils.fs.rm(o, True)
        else:
            shutil.rmtree(o)
        print('borrado:', o)
elif objetivos:
    print("Para borrar escribir CONFIRMAR_BORRADO = 'SI' y volver a correr esta celda.")"""),

('md', "## 6 · Estado final"),

('code', r"""print('Cargas en las tablas:', cargas_en_tablas())
print('Carpetas en 10_cargas:', sorted(d for d in os.listdir(CARGAS) if os.path.isdir(f'{CARGAS}/{d}')) if os.path.isdir(CARGAS) else '(no existe)')
print('Hora (UTC):', ahora_utc())"""),
]


def celda(tipo, txt):
    src = txt.splitlines(True)
    if tipo == 'md':
        return {'cell_type': 'markdown', 'metadata': {}, 'source': src}
    return {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': src}


def generar():
    nb = {'cells': [celda(t, s) for t, s in CELDAS],
          'metadata': {'language_info': {'name': 'python'},
                       'application/vnd.databricks.v1+notebook': {'notebookName': '98_restauracion', 'language': 'python'}},
          'nbformat': 4, 'nbformat_minor': 5}
    json.dump(nb, open(SALIDA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('generado', SALIDA)


def probar():
    """Spark local con Delta: 2 tablas, punto guardado, una carga de prueba, vista previa, restaurar y limpiar."""
    from pyspark.sql import SparkSession
    ivy = os.path.expanduser('~/.ivy2/jars')
    jars = ','.join(os.path.join(ivy, j) for j in os.listdir(ivy) if j.startswith(('io.delta', 'org.antlr')))
    tmp = tempfile.mkdtemp(prefix='restauracion_')
    spark = (SparkSession.builder.master('local[2]').config('spark.ui.enabled', 'false').config('spark.jars', jars)
             .config('spark.sql.extensions', 'io.delta.sql.DeltaSparkSessionExtension')
             .config('spark.sql.catalog.spark_catalog', 'org.apache.spark.sql.delta.catalog.DeltaCatalog')
             .config('spark.sql.warehouse.dir', f'{tmp}/wh').getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    vol = f'{tmp}/vol'
    os.makedirs(f'{vol}/10_cargas/REF_x')
    spark.createDataFrame([('REF_x', 1)], 'carga_id string, n int').write.format('delta').saveAsTable('ppto27_brz_archivos')
    spark.createDataFrame([(1, 10.0)], 'id int, m double').write.format('delta').saveAsTable('ppto27_gld_fact_ppto')
    g = {'spark': spark, 'display': lambda d: print(d.to_string(index=False))}

    def correr(i, cambios=()):
        s = [s for t, s in CELDAS if t == 'code'][i]
        s = s.replace("CAT = 'catalogo_ppto.esquema_ppto'", "CAT = 'default'").replace("VOL = '/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27'", f"VOL = '{vol}'")
        for a, b in cambios:
            assert a in s, a
            s = s.replace(a, b)
        print(f'\n>>> celda {i}')
        exec(s, g)

    correr(0); correr(1); correr(2)
    # ensayo: llegan 2 cargas de demo (carpetas + filas) y se escriben tablas
    for c in ('20261017_0800_Demo_Limpias', '20261017_0900_Demo_Con_errores'):
        os.makedirs(f'{vol}/10_cargas/{c}')
        spark.createDataFrame([(c, 3)], 'carga_id string, n int').write.format('delta').mode('append').saveAsTable('ppto27_brz_archivos')
    spark.createDataFrame([(2, 20.0)], 'id int, m double').write.format('delta').mode('overwrite').saveAsTable('ppto27_gld_fact_ppto')
    os.makedirs(f'{vol}/40_tiempos')
    spark.createDataFrame([(1,)], 'x int').write.format('delta').saveAsTable('ppto27_ctl_nueva')   # tabla creada después del punto
    correr(3)
    correr(4)                                                    # sin confirmar: no hace nada
    correr(4, [("CONFIRMAR = 'NO'", "CONFIRMAR = 'SI'")])
    assert sorted(r.carga_id for r in spark.table('ppto27_brz_archivos').collect()) == ['REF_x']
    assert spark.table('ppto27_gld_fact_ppto').first().m == 10.0
    correr(5)
    correr(5, [("CONFIRMAR_BORRADO = 'NO'", "CONFIRMAR_BORRADO = 'SI'")])
    assert sorted(os.listdir(f'{vol}/10_cargas')) == ['REF_x'] and not os.path.exists(f'{vol}/40_tiempos')
    correr(6)
    # por hora UTC en vez de nombre
    correr(3, [("PUNTO = 'antes_ensayo_demo'", "PUNTO = '2000-01-01 00:00:00'")])
    print('\nPRUEBA OK')
    spark.stop()
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    generar()
    if '--probar' in sys.argv:
        probar()
