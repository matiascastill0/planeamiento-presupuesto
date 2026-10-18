"""Pipeline Ppto27 en PySpark (lo que corre en Databricks): bronze → silver → gold → control.

Diseño
  · Bronze: Spark lee los Excel como binarios (binaryFile) y los reparte entre los workers (mapInPandas): cada worker abre sus
    archivos con openpyxl. El tiempo crece por archivos / núcleos, no por archivos en serie.
  · Silver y gold: DataFrames de Spark (unpivot de meses, interpretación de montos, flags, joins, ventanas).
  · Diccionarios chicos en el driver: cada texto DISTINTO (país, CeCo, cuenta, proveedor…) se limpia y homologa una sola vez con
    las reglas de ppto27_lib y vuelve como tabla de mapeo (broadcast). Escala con los valores distintos, no con las filas.
  · Sin cache (no existe en serverless): los pasos caros se escriben a una tabla intermedia y se leen de ahí.
Las reglas son las mismas de la versión pandas (ppto27_silver / ppto27_gold), que queda como referencia y para las pruebas.
"""
import json, os, re, shutil, sys, unicodedata
from datetime import datetime
from urllib.parse import unquote
import pandas as pd
from pyspark.sql import functions as F, types as T, Window as W
import ppto27_lib as L
import ppto27_silver as SV
import ppto27_gold as GD


def _por_valor():
    """Los workers no tienen estas librerías en su ruta: se envían junto con las funciones (cloudpickle por valor)."""
    from pyspark import cloudpickle
    for m in (L, sys.modules[__name__]):
        try:
            cloudpickle.register_pickle_by_value(m)
        except Exception:
            pass


_por_valor()

# ───────────────────────────── utilidades ─────────────────────────────
ARCH_COLS = [('carga_id', 'string'), ('ruta_relativa', 'string'), ('archivo', 'string'), ('sha256', 'string'), ('tamano_bytes', 'bigint'),
             ('modificado', 'timestamp'), ('id_plantilla', 'string'), ('rubro_cod', 'string'), ('rubro', 'string'), ('sub_rubro', 'string'),
             ('tipo', 'string'), ('area', 'string'), ('pais_carpeta', 'string'), ('nombre_base', 'string'), ('estado', 'string'),
             ('error', 'string'), ('repetido_de', 'string'), ('hojas', 'string'), ('tablas_oculta', 'boolean'), ('ref_tabla', 'string'),
             ('encabezado', 'string'), ('n_lineas', 'int'), ('fila_totales', 'int'), ('tc', 'string'), ('fuera_tabla', 'string'),
             ('listas', 'string'), ('leyenda', 'string'), ('fecha_proceso', 'timestamp')]
LIN_COLS = [('carga_id', 'string'), ('sha256', 'string'), ('id_plantilla', 'string'), ('ruta_relativa', 'string'), ('fila', 'int'),
            *[(c, 'string') for c in L.COLUMNAS], ('tipos', 'string'), ('formulas', 'string'), ('fecha_proceso', 'timestamp')]
_ESQ = {'string': T.StringType(), 'bigint': T.LongType(), 'int': T.IntegerType(), 'boolean': T.BooleanType(),
        'timestamp': T.TimestampType(), 'double': T.DoubleType()}


def esquema(cols):
    return T.StructType([T.StructField(c, _ESQ[t], True) for c, t in cols])


def existe(spark, nombre):
    try:
        spark.table(L.tabla(nombre)).limit(0).collect()
        return True
    except Exception:
        return False


def escribir(df, nombre, modo='overwrite'):
    w = df.write.format(L.FORMATO).mode(modo)
    if modo == 'overwrite':
        w = w.option('overwriteSchema', 'true')
    w.saveAsTable(L.tabla(nombre))


def de_pandas(spark, pdf, cols=None):
    """DataFrame chico de pandas → Spark con tipos estables (los nulos no rompen la inferencia)."""
    import math
    cols = cols or [(c, 'double' if pd.api.types.is_float_dtype(pdf[c]) else 'bigint' if pd.api.types.is_integer_dtype(pdf[c])
                     else 'boolean' if pd.api.types.is_bool_dtype(pdf[c]) else 'string') for c in pdf.columns]
    conv = {'string': lambda v: str(v), 'double': float, 'bigint': int, 'int': int, 'boolean': bool, 'timestamp': lambda v: pd.Timestamp(v).to_pydatetime()}
    filas = [tuple(None if (v is None or v is pd.NaT or (isinstance(v, float) and math.isnan(v))) else conv[t](v)
                   for v, (_, t) in zip(r, cols)) for r in pdf[[c for c, _ in cols]].itertuples(index=False, name=None)]
    return spark.createDataFrame(filas, esquema(cols))


def _nfc(s):
    return unicodedata.normalize('NFC', s)


def _sin_esquema(p):
    p = unquote(p)
    return re.sub(r'^(dbfs:|file:)', '', p)


# ───────────────────────────── BRONZE ─────────────────────────────
def _lector(carga_id, raiz, ahora):
    raiz_n = _nfc(os.path.normpath(raiz))
    arch_n = [c for c, _ in ARCH_COLS]
    lin_n = [c for c, _ in LIN_COLS]

    def leer(it):
        import pandas as pd
        for pdf in it:
            A, LN = [], []
            for r in pdf.itertuples(index=False):
                rel = _nfc(os.path.relpath(_nfc(os.path.normpath(_sin_esquema(r.path))), raiz_n)).replace('\\', '/')
                a = dict(carga_id=carga_id, ruta_relativa=rel, archivo=os.path.basename(rel), sha256=r.sha256, tamano_bytes=int(r.length),
                         modificado=r.modificationTime, **L.identificar(rel), repetido_de=r.repetido_de, fecha_proceso=ahora,
                         estado=None, error=None)
                if r.repetido_de:
                    a['estado'] = 'REPETIDO'
                else:
                    try:
                        info, lineas = L.leer_plantilla(bytes(r.content))
                    except Exception as e:
                        info, lineas = dict(estado='RECHAZADO', error=f'F16 {type(e).__name__}: {e}'[:500]), []
                    a.update(info)
                    LN += [dict(l, registro='LINEA', carga_id=carga_id, sha256=r.sha256, id_plantilla=a['id_plantilla'],
                                ruta_relativa=rel, fecha_proceso=ahora) for l in lineas]
                A.append(dict(a, registro='ARCHIVO'))
            out = pd.DataFrame(A + LN)
            for c in ['registro'] + arch_n + lin_n:
                if c not in out:
                    out[c] = None
            for c in ('tamano_bytes', 'n_lineas', 'fila_totales', 'fila'):
                out[c] = pd.array([None if pd.isna(v) else int(v) for v in out[c]], dtype='Int64')
            out['tablas_oculta'] = pd.array([None if v is None or (isinstance(v, float) and pd.isna(v)) else bool(v) for v in out['tablas_oculta']],
                                            dtype='boolean')
            yield out[['registro'] + list(dict.fromkeys(arch_n + lin_n))]
    return leer


def bronze(spark, raiz, carga_id, ahora=None):
    """Lee todas las plantillas de la carpeta de una carga, en paralelo. Archivos ya cargados (mismo hash) quedan REPETIDO."""
    ahora = ahora or datetime.now()
    try:
        spark.conf.set('spark.sql.files.maxPartitionBytes', str(8 * 1024 * 1024))   # ~1–2 plantillas por tarea → más paralelismo
    except Exception:
        pass
    arch = (spark.read.format('binaryFile').option('recursiveFileLookup', 'true').option('pathGlobFilter', '*.xlsx').load(raiz)
            .withColumn('nombre', F.element_at(F.split('path', '/'), -1))
            .where(~F.col('nombre').rlike(r'^(~\$|\.|~%24)') & ~F.lower(F.col('nombre')).rlike('checklist|validaci'))
            .withColumn('sha256', F.sha2('content', 256)))
    # repetidos: hash ya cargado antes, o repetido dentro de esta misma carga (se lee sólo el primero) — decisión en el driver
    meta = arch.select('path', 'sha256').toPandas().sort_values('path')
    previos = {}
    if existe(spark, 'brz_archivos'):
        previos = {r.sha256: f'{r.carga_id} / {r.ruta_relativa}' for r in spark.table(L.tabla('brz_archivos'))
                   .where("estado <> 'REPETIDO'").select('sha256', 'carga_id', 'ruta_relativa').dropDuplicates(['sha256']).collect()}
    vistos, rep = {}, []
    for p, h in zip(meta.path, meta.sha256):
        rel = _nfc(os.path.relpath(_nfc(os.path.normpath(_sin_esquema(p))), _nfc(os.path.normpath(raiz))))
        rep.append((p, previos.get(h) or (f'{carga_id} / {vistos[h]}' if h in vistos else None)))
        vistos.setdefault(h, rel)
    rep_df = F.broadcast(spark.createDataFrame(rep, 'path string, repetido_de string'))
    entrada = (arch.join(rep_df, 'path')
               .select('path', 'length', 'modificationTime', 'sha256', 'repetido_de',
                       F.when(F.col('repetido_de').isNull(), F.col('content')).alias('content')))
    sal = esquema([('registro', 'string')] + list({c: t for c, t in ARCH_COLS + LIN_COLS}.items()))
    escribir(entrada.mapInPandas(_lector(carga_id, raiz, ahora), sal), 'brz_stage')     # se lee y parsea UNA vez
    st = spark.table(L.tabla('brz_stage'))
    escribir(st.where("registro = 'ARCHIVO'").select(*[c for c, _ in ARCH_COLS]), 'brz_archivos', 'append')
    escribir(st.where("registro = 'LINEA'").select(*[c for c, _ in LIN_COLS]), 'brz_lineas', 'append')
    res = st.where("registro = 'ARCHIVO'").groupBy('estado').count().toPandas()
    n_lin = st.where("registro = 'LINEA'").count()
    est = {r.estado: int(r['count']) for _, r in res.iterrows()}
    try:
        usuario = spark.sql('SELECT current_user()').first()[0]
    except Exception:
        usuario = None
    escribir(de_pandas(spark, pd.DataFrame([dict(carga_id=carga_id, ruta=raiz, fecha_proceso=ahora, usuario=usuario, archivos=sum(est.values()),
                                                   archivos_nuevos=est.get('OK', 0), archivos_repetidos=est.get('REPETIDO', 0),
                                                   archivos_rechazados=est.get('RECHAZADO', 0), lineas=n_lin)]),
                       [('carga_id', 'string'), ('ruta', 'string'), ('fecha_proceso', 'timestamp'), ('usuario', 'string'), ('archivos', 'int'),
                        ('archivos_nuevos', 'int'), ('archivos_repetidos', 'int'), ('archivos_rechazados', 'int'), ('lineas', 'int')]),
             'ctl_cargas', 'append')
    return est, n_lin


# ───────────────────────────── SILVER ─────────────────────────────
IDX = {c: i for i, c in enumerate(L.COLUMNAS)}
MONTOS = SV.MONTOS
FC = [k for k in MONTOS if k.startswith('fc_')]
INVIS_J = '[\\u200b-\\u200f\\u2028\\u2029\\u2060\\ufeff\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]'
MOJI_J = 'Ã[\\x80-\\xbf¡-ÿ]|Â[\\xa0-\\xbf]|â€|\\ufffd|╠|Ì\\x81|ï¿½|\\+\\ufffd'
SEV_NUM = {s: i for i, s in enumerate(L.SEV_ORDEN)}


def _sev(col):
    m = F.create_map(*[x for k, v in L.SEVERIDAD.items() for x in (F.lit(k), F.lit(v))])
    return m[col]


def _flag(cond, cod, celdas=None, detalle=None):
    return F.when(cond, F.struct(F.lit(cod).alias('codigo_flag'), (celdas if celdas is not None else F.lit('')).cast('string').alias('celdas'),
                                 F.substring((detalle if detalle is not None else F.lit('')).cast('string'), 1, 300).alias('detalle')))


def _n(c):
    """Como SV._n: espacios duros → espacio, espacios colapsados, trim."""
    return F.trim(F.regexp_replace(F.regexp_replace(c, ' ', ' '), '\\s+', ' '))


def _monto(df):
    """Celdas de monto en formato largo (txt, tipo, formula) → valor + flag de celda. Mismas reglas que ppto27_lib.monto()."""
    t = F.lower(F.col('tipo'))
    f = F.regexp_replace(F.substring(F.col('formula'), 2, 100000), ' ', '')
    s = F.trim(F.regexp_replace(F.regexp_replace(F.col('txt'), INVIS_J, ''), ' ', ' '))
    x = F.trim(F.regexp_replace(s, 'S/|\\$|USD|COP|CLP|PEN|MXN', ''))
    neg = x.startswith('(') & x.endswith(')')
    x2 = F.regexp_replace(F.regexp_replace(x, '^\\(+|\\)+$', ''), ' ', '')
    x3 = (F.when(x2.rlike('^-?\\d{1,3}(\\.\\d{3})+(,\\d+)?$'), F.regexp_replace(F.regexp_replace(x2, '\\.', ''), ',', '.'))
          .when(x2.rlike('^-?\\d{1,3}(,\\d{3})+(\\.\\d+)?$'), F.regexp_replace(x2, ',', ''))
          .when(x2.rlike('^-?\\d+,\\d{1,2}$'), F.regexp_replace(x2, ',', '.'))
          .otherwise(x2))
    vs = F.expr('try_cast(_x3 as double)')
    vn = F.expr('try_cast(txt as double)')
    df = df.withColumn('_x3', x3)
    sin = F.col('txt').isNull() | F.col('tipo').isNull() | (F.col('tipo') == '-')
    valor = (F.when(sin, F.lit(None).cast('double'))
             .when(t == 'n', F.when(F.col('formula').isNotNull() & (F.instr(f, '[') > 0) & (F.instr(f, '!') > 0), F.lit(None)).otherwise(vn))
             .when(t.isin('b', 'd', 'e'), F.lit(None))
             .when(s == '', F.lit(None))
             .otherwise(F.when(neg, -F.abs(vs)).otherwise(vs)))
    flag = (F.when(sin, F.when(F.col('formula').isNotNull(), F.lit('M05')))
            .when(t == 'n', F.when(F.col('formula').isNotNull(),
                                   F.when((F.instr(f, '[') > 0) & (F.instr(f, '!') > 0), 'M07').when(f.rlike('^[0-9.+\\-*/()]+$'), 'M04').otherwise('M08'))
                  .when(vn == 0, 'M11'))
            .when(t == 'b', 'M03').when(t == 'd', 'M06').when(t == 'e', 'M05')
            .when(s == '', 'M02')
            .when(vs.isNotNull(), 'M03').otherwise('M09'))
    det = (F.when(sin, F.concat(F.col('formula'), F.lit(' (sin valor calculado)')))
           .when(t == 'n', F.col('formula'))
           .when(t == 'b', F.concat(F.lit('booleano '), F.col('txt')))
           .when(t == 'd', F.concat(F.lit('fecha '), F.substring('txt', 1, 10)))
           .when(t == 'e', F.col('txt'))
           .otherwise(F.concat(F.lit("'"), F.col('txt'), F.lit("'"))))
    return df.withColumn('valor', valor).withColumn('flag_celda', flag).withColumn('det_celda', F.when(flag.isNotNull(), det)).drop('_x3')


def _largo(LIN, columnas):
    arr = F.array(*[F.struct(F.lit(k).alias('columna'), F.lit(IDX[k]).alias('idx'), F.lit(L._col(IDX[k] + 1)).alias('letra'),
                             F.col(k).alias('txt'), F.substring('tipos', IDX[k] + 1, 1).alias('tipo'),
                             F.get_json_object('formulas', f'$.{k}').alias('formula')) for k in columnas])
    return LIN.select('id_linea', 'fila', F.explode(arr).alias('c')).select('id_linea', 'fila', 'c.*')


def _diccionarios(spark, LIN, M, AL, sel):
    """Cada texto distinto se limpia y homologa una vez en el driver con las reglas de ppto27_lib."""
    hc, hp = SV.homologadores(M, AL)
    veh = {}
    for r in M['vehiculos'].itertuples():
        veh.setdefault(r.pais, set()).add(str(r.vehiculo))
    cecos = {(r.pais, int(r.ceco)): (r.agrupacion_drivers if isinstance(r.agrupacion_drivers, str) else r.agrupacion)
             for r in M['cecos'].itertuples()}
    k = lambda c: F.coalesce(F.col(c), F.lit(''))
    e = lambda campo, a, b=None: F.struct(F.lit(campo).alias('campo'), k(a).alias('a'), (k(b) if b else F.lit('')).alias('b'))
    D = (LIN.select(F.array(e('pais', 'pais'), e('veh', 'pais', 'vehiculo'), e('ceco', 'pais', 'ceco_nombre'), e('niv', 'nivel_1', 'nivel_2'),
                            e('cta', 'nom_cta_contable'), e('prov', 'proveedor'), e('mon', 'pais', 'moneda'),
                            *[e(c, c) for c in ('sede', 'nivel_3', 'nivel_4', 'glosa', 'comentario_area')]).alias('x'))
         .select(F.explode('x').alias('x')).select('x.*').distinct().toPandas())
    lim = lambda v: L.limpiar(v) if v != '' else None
    alt_p = {L.sin_tildes(x).upper(): x for x in SV.PAISES_OK}

    def pais_ok(raw):
        p = lim(raw) or ''
        if p in SV.PAISES_OK:
            return p, None
        return (alt_p[L.sin_tildes(p).upper()], 'T06') if L.sin_tildes(p).upper() in alt_p else (p, 'L01')

    out = {}
    g = D.groupby('campo')
    rows = []
    for a in (g.get_group('pais').a if 'pais' in g.groups else []):
        p, fl = pais_ok(a)
        rows.append((a, p or None, fl, (lim(a) or '(vacío)') if fl == 'L01' else lim(a)))
    out['pais'] = de_pandas(spark, pd.DataFrame(rows, columns=['k_pais', 'pais_ok', 'fl_pais', 'det_pais']))
    rows = []
    for a, b in (zip(g.get_group('veh').a, g.get_group('veh').b) if 'veh' in g.groups else []):
        p, _ = pais_ok(a)
        vh = lim(b) or ''
        if vh in veh.get(p, set()):
            rows.append((a, b, vh, None, None))
        else:
            alt = {x.upper(): x for x in veh.get(p, set())}.get(L.sin_tildes(vh).upper())
            rows.append((a, b, alt or vh or None, 'T06' if alt else 'L02', vh if alt else f'"{vh}" no es vehículo de {p}'))
    out['veh'] = de_pandas(spark, pd.DataFrame(rows, columns=['k_pais', 'k_veh', 'vehiculo_ok', 'fl_veh', 'det_veh']))
    rows = []
    for a, b in (zip(g.get_group('ceco').a, g.get_group('ceco').b) if 'ceco' in g.groups else []):
        p, _ = pais_ok(a)
        txt = lim(b) or ''
        cn = L.ceco_num(txt)
        if cn is None or not re.match(r'^\d+\s*-\s*\S', txt) or 'VARIOS' in txt.upper():
            fl, det = 'L03', txt or '(vacío)'
        elif (p, cn) not in cecos:
            fl, det = 'L04', txt
        else:
            fl, det = None, None
        ag = cecos.get((p, cn)) if cn else None
        rows.append((a, b, txt or None, cn, fl, det, ag, L.clave_texto(ag) if ag else None))
    out['ceco'] = de_pandas(spark, pd.DataFrame(rows, columns=['k_pais', 'k_ceco', 'ceco_ok', 'ceco_n', 'fl_ceco', 'det_ceco', 'agrup', 'agrup_k']),
                            [('k_pais', 'string'), ('k_ceco', 'string'), ('ceco_ok', 'string'), ('ceco_n', 'bigint'), ('fl_ceco', 'string'),
                             ('det_ceco', 'string'), ('agrup', 'string'), ('agrup_k', 'string')])
    rows = []
    for a, b in (zip(g.get_group('niv').a, g.get_group('niv').b) if 'niv' in g.groups else []):
        n1, n2 = lim(a) or '', lim(b) or ''
        k1, k2 = L.clave_texto(n1), L.clave_texto(n2)
        fl, det = ('L05', n1 or '(vacío)') if k1 not in L.NIVEL2_DE else (('L06', f'"{n2}" no es de {n1}') if k2 not in L.NIVEL2_DE[k1] else (None, None))
        rows.append((a, b, n1 or None, n2 or None, L.MAPA_PYG.get((k1, k2), 0), fl, det))
    out['niv'] = de_pandas(spark, pd.DataFrame(rows, columns=['k_n1', 'k_n2', 'nivel_1_ok', 'nivel_2_ok', 'id_linea_pyg', 'fl_niv', 'det_niv']),
                           [('k_n1', 'string'), ('k_n2', 'string'), ('nivel_1_ok', 'string'), ('nivel_2_ok', 'string'), ('id_linea_pyg', 'bigint'),
                            ('fl_niv', 'string'), ('det_niv', 'string')])
    rows = []
    for a in (g.get_group('cta').a if 'cta' in g.groups else []):
        cta, met, fl = L.homologar_cuenta(hc, a if a != '' else None)
        rows.append((a, lim(a), cta, met, fl, (f'"{a}" → "{cta}"' if fl != 'L17' else f'"{a}"') if fl else None))
    out['cta'] = de_pandas(spark, pd.DataFrame(rows, columns=['k_cta', 'cta_limpia', 'cuenta_oficial', 'metodo_cuenta', 'fl_cta', 'det_cta']))
    rows = []
    for a in (g.get_group('prov').a if 'prov' in g.groups else []):
        pv, met, fl = L.homologar_proveedor(hp, a if a != '' else None)
        rows.append((a, lim(a), pv, met, fl, (f'"{a}" → "{pv}"' if fl == 'L19' else f'"{a}"') if fl else None))
    out['prov'] = de_pandas(spark, pd.DataFrame(rows, columns=['k_prov', 'prov_limpio', 'proveedor_oficial', 'metodo_proveedor', 'fl_prov', 'det_prov']))
    rows = []
    for a, b in (zip(g.get_group('mon').a, g.get_group('mon').b) if 'mon' in g.groups else []):
        p, _ = pais_ok(a)
        mon = (lim(b) or '').upper()
        if mon not in SV.MONEDAS:
            fl, det = 'L09', mon or '(vacío)'
        elif p in SV.MONEDA_PAIS and mon not in SV.MONEDA_PAIS[p]:
            fl, det = 'L10', f'{mon} en {p}'
        else:
            fl, det = None, None
        rows.append((a, b, mon or None, fl, det))
    out['mon'] = de_pandas(spark, pd.DataFrame(rows, columns=['k_pais', 'k_mon', 'moneda_ok', 'fl_mon', 'det_mon']))
    rows = [(c, a, lim(a)) for c in ('sede', 'nivel_3', 'nivel_4', 'glosa', 'comentario_area') if c in g.groups for a in g.get_group(c).a]
    out['txt'] = de_pandas(spark, pd.DataFrame(rows, columns=['campo', 'k_txt', 'limpio']))
    return out


def silver(spark):
    M, AL, _ = L.cargar_maestros()
    A = spark.table(L.tabla('brz_archivos')).toPandas()
    sel = SV.elegir_versiones(A, AL.get('alias_plantilla'), maestro_plantillas=M['plantillas'])
    selr = SV.elegir_versiones(A, referencia=True, maestro_plantillas=M['plantillas'])
    FA, bloq = SV.flags_archivo(sel, M)
    primero = sel.groupby('sha256').id_plantilla.first()                       # mismo contenido en 2 plantillas (F10): líneas sólo en la 1.ª
    sel = sel.assign(lee_lineas=[primero[h] == i for h, i in zip(sel.sha256, sel.id_plantilla)],
                     bloqueado=sel.id_plantilla.isin(bloq),
                     esp_agrup=[L.agrupacion_esperada(t, a) for t, a in zip(sel.tipo, sel.area)])
    sel['esp_k'] = sel.esp_agrup.map(lambda x: L.clave_texto(x) if x else None)
    S_cols = [('sha256', 'string'), ('id_plantilla', 'string'), ('carga_vigente', 'string'), ('rubro_cod', 'string'), ('rubro', 'string'),
              ('sub_rubro', 'string'), ('tipo', 'string'), ('area', 'string'), ('pais_carpeta', 'string'), ('bloqueado', 'boolean'),
              ('esp_agrup', 'string'), ('esp_k', 'string')]
    sel_s = F.broadcast(de_pandas(spark, sel[sel.lee_lineas].rename(columns={'carga_id': 'carga_vigente'}), S_cols))

    LIN = (spark.table(L.tabla('brz_lineas')).drop('id_plantilla').dropDuplicates(['sha256', 'fila']).join(sel_s, 'sha256')
           .withColumn('id_linea', F.concat('id_plantilla', F.lit('#'), F.col('fila'))))

    # ── montos (formato largo, una fila por celda de monto)
    LG = _monto(_largo(LIN, MONTOS))
    piv = LG.groupBy('id_linea').agg(*[F.max(F.when(F.col('columna') == k, F.col('valor'))).alias(k) for k in MONTOS])
    cel = (LG.where('flag_celda IS NOT NULL').groupBy('id_linea', 'flag_celda')
           .agg(F.array_sort(F.collect_list(F.struct('idx', F.concat('letra', 'fila').alias('celda')))).alias('cs'),
                F.array_distinct(F.collect_list('det_celda')).alias('ds'))
           .select('id_linea', F.struct(F.col('flag_celda').alias('codigo_flag'), F.concat_ws(', ', F.transform('cs', lambda x: x.celda)).alias('celdas'),
                                        F.substring(F.concat(F.size('cs'), F.lit(' celdas · '), F.concat_ws('; ', 'ds')), 1, 300).alias('detalle')).alias('f'))
           .groupBy('id_linea').agg(F.collect_list('f').alias('fl_celdas')))

    # ── textos: diccionarios + flags de texto
    Dc = _diccionarios(spark, LIN, M, AL, sel)
    k = lambda c: F.coalesce(F.col(c), F.lit(''))
    base = LIN.drop(*MONTOS)
    for kk in SV.CALC:                                                         # columnas calculadas tal cual vinieron (para M16)
        base = base.withColumnRenamed(kk, f'raw_{kk}')
    X = (base.join(piv, 'id_linea', 'left').join(cel, 'id_linea', 'left')
         .withColumn('k_pais', k('pais')).withColumn('k_veh', k('vehiculo')).withColumn('k_ceco', k('ceco_nombre'))
         .withColumn('k_n1', k('nivel_1')).withColumn('k_n2', k('nivel_2')).withColumn('k_cta', k('nom_cta_contable'))
         .withColumn('k_prov', k('proveedor')).withColumn('k_mon', k('moneda'))
         .join(F.broadcast(Dc['pais']), 'k_pais', 'left').join(F.broadcast(Dc['veh']), ['k_pais', 'k_veh'], 'left')
         .join(F.broadcast(Dc['ceco']), ['k_pais', 'k_ceco'], 'left').join(F.broadcast(Dc['niv']), ['k_n1', 'k_n2'], 'left')
         .join(F.broadcast(Dc['cta']), 'k_cta', 'left').join(F.broadcast(Dc['prov']), 'k_prov', 'left')
         .join(F.broadcast(Dc['mon']), ['k_pais', 'k_mon'], 'left'))
    for c in ('sede', 'nivel_3', 'nivel_4', 'glosa', 'comentario_area'):
        X = X.join(F.broadcast(Dc['txt'].where(F.col('campo') == c).select(F.col('k_txt').alias(f'k_{c}'), F.col('limpio').alias(f'{c}_ok'))),
                   k(c) == F.col(f'k_{c}'), 'left').drop(f'k_{c}')

    # ── reglas de línea
    letra = lambda kk: F.lit(L._col(IDX[kk] + 1))
    pp = F.array(*[F.struct(F.lit(L.ENCABEZADO[IDX[kk]]).alias('n'), letra(kk).alias('l'), F.col(kk).alias('v')) for kk in L.COL_PPTO])
    rr = F.array(*[F.struct(letra(kk).alias('l'), F.col(kk).alias('v')) for kk in L.COL_REAL])
    fcs = F.array(*[F.struct(letra(kk).alias('l'), F.col(kk).alias('v')) for kk in FC])
    celdas = lambda arr, cond: F.concat_ws(', ', F.transform(F.filter(arr, cond), lambda x: F.concat(x.l, F.col('fila').cast('string'))))
    p27 = F.aggregate(pp, F.lit(0.0), lambda acc, x: acc + F.coalesce(x.v, F.lit(0.0)))
    real_s = F.aggregate(rr, F.lit(0.0), lambda acc, x: acc + F.coalesce(x.v, F.lit(0.0)))
    X = X.withColumn('p27', p27).withColumn('real_ene_ago', real_s).withColumn('r_anual', F.col('real_ene_ago') / 8 * 12)
    n_ppto = F.size(F.filter(pp, lambda x: F.coalesce(x.v, F.lit(0.0)) != 0))
    n_real = F.size(F.filter(rr, lambda x: F.coalesce(x.v, F.lit(0.0)) != 0))
    textos = [F.col(c) for c in L.COLUMNAS[:13]]
    hay_texto = F.greatest(*[F.when(F.coalesce(c, F.lit('')) != '', 1).otherwise(0) for c in textos]) == 1
    hay_monto = F.greatest(*[F.when(F.coalesce(F.col(kk), F.lit(0.0)) != 0, 1).otherwise(0) for kk in MONTOS]) == 1
    X = X.withColumn('vacia', ~hay_texto & ~hay_monto)
    clave9 = F.concat_ws('|', *[F.upper(_n(F.coalesce(F.col(L.COLUMNAS[i]), F.lit('')))) for i in SV.CAMPOS_CLAVE])
    X = X.withColumn('clave9', clave9).withColumn(
        'n_dup', F.when(hay_texto, F.sum(hay_texto.cast('int')).over(W.partitionBy('id_plantilla', 'clave9'))))
    calc = []
    for kk in SV.CALC:
        ch = F.substring('tipos', IDX[kk] + 1, 1)
        calc.append(_flag(F.col(f'raw_{kk}').isNotNull() & ~ch.isin('-', 'f') & (ch == F.lower(ch)), 'M16', F.concat(letra(kk), F.col('fila')),
                          F.concat(F.lit(f'{kk} = '), F.lit("'"), F.col(f'raw_{kk}'), F.lit("' (valor en vez de fórmula)"))))
    pos = F.filter(pp, lambda x: x.v > 0)
    ratio = F.col('p27') / F.col('r_anual')
    reglas = [
        _flag(F.size(pos) > 0, 'M01', celdas(pp, lambda x: x.v > 0),
              F.concat_ws(', ', F.transform(F.slice(pos, 1, 6), lambda x: F.concat(x.n, F.lit('='), F.format_number(x.v, 2))))),
        _flag(F.size(F.filter(rr, lambda x: x.v > 0)) > 0, 'M10', celdas(rr, lambda x: x.v > 0)),
        _flag(F.size(F.filter(pp, lambda x: F.abs(x.v * 100 - F.round(x.v * 100)) > 1e-6)) > 0, 'M12',
              celdas(pp, lambda x: F.abs(x.v * 100 - F.round(x.v * 100)) > 1e-6)),
        _flag(F.size(F.filter(fcs, lambda x: F.coalesce(x.v, F.lit(0.0)) != 0)) > 0, 'M17', celdas(fcs, lambda x: F.coalesce(x.v, F.lit(0.0)) != 0)),
        *calc,
        _flag((F.col('p27') != 0) & (n_ppto == 1) & (n_real >= 6), 'M13', celdas(pp, lambda x: F.coalesce(x.v, F.lit(0.0)) != 0),
              F.concat(F.lit('P27 '), F.format_number('p27', 0), F.lit(' en un mes; Real con '), n_real, F.lit(' meses'))),
        _flag((F.col('p27') != 0) & (F.col('r_anual') < 0) & (F.abs(ratio - 1) > 0.5) & (F.coalesce(_n(F.col('comentario_area')), F.lit('')) == ''),
              'M14', F.lit(''), F.concat(F.lit('P27 '), F.format_number('p27', 0), F.lit(' vs Real anualizado '), F.format_number('r_anual', 0))),
        _flag((F.col('p27') != 0) & (F.col('r_anual') != 0) & ((ratio > 500) | ((ratio > 0) & (ratio < 1 / 500))), 'M15', F.lit(''),
              F.concat(F.lit('P27 / Real anualizado = '), F.format_number(ratio, 4))),
        _flag(F.col('fl_pais') == 'T06', 'T06', F.concat(F.lit('A'), F.col('fila')), F.col('det_pais')),
        _flag(F.col('fl_pais') == 'L01', 'L01', F.concat(F.lit('A'), F.col('fila')), F.col('det_pais')),
        _flag(F.col('pais_ok').isin(*SV.PAISES_OK) & F.col('pais_carpeta').isin(*SV.PAISES_OK) & (F.col('pais_ok') != F.col('pais_carpeta')),
              'F11', F.concat(F.lit('A'), F.col('fila')), F.concat(F.col('pais_ok'), F.lit(' en plantilla de '), F.col('pais_carpeta'))),
        *[_flag(F.col(fc) == cod, cod, F.concat(F.lit(col), F.col('fila')), F.col(dc))
          for fc, dc, col, cods in (('fl_veh', 'det_veh', 'B', ('T06', 'L02')), ('fl_ceco', 'det_ceco', 'C', ('L03', 'L04')),
                                    ('fl_niv', 'det_niv', 'F', ('L05',)), ('fl_cta', 'det_cta', 'E', ('L15', 'L16', 'L17')),
                                    ('fl_prov', 'det_prov', 'J', ('L07', 'L08', 'L18', 'L19')), ('fl_mon', 'det_mon', 'M', ('L09', 'L10')))
          for cod in cods],
        _flag(F.col('fl_niv') == 'L06', 'L06', F.concat(F.lit('G'), F.col('fila')), F.col('det_niv')),
        _flag(F.col('glosa_ok').isNull(), 'L11', F.concat(F.lit('K'), F.col('fila'))),
        _flag(F.col('n_dup') > 1, 'L13', F.lit(''), F.concat(F.col('n_dup'), F.lit(' líneas con los mismos textos'))),
        _flag(F.col('esp_k').isNotNull() & F.col('agrup_k').isNotNull() & (F.col('agrup_k') != F.col('esp_k')), 'L14',
              F.concat(F.lit('C'), F.col('fila')),
              F.concat(F.col('ceco_ok'), F.lit(' es de "'), F.col('agrup'), F.lit('" y viene en la plantilla de "'), F.col('esp_agrup'), F.lit('"'))),
    ]
    tx = []
    for i, c in enumerate(L.COLUMNAS[:13]):
        v, ref = F.col(c), F.concat(F.lit(L._col(i + 1)), F.col('fila'))
        tx += [_flag(v.rlike(MOJI_J), 'T01', ref, v), _flag(v.rlike(INVIS_J), 'T03', ref, v),
               _flag(v.rlike('^\\s|\\s$') | v.contains('  ') | v.contains(' ') | v.contains('\n'), 'T02', ref, v),
               _flag(F.length(v) > 255, 'T04', ref, F.concat(F.length(v), F.lit(' caracteres'))),
               _flag(v.rlike('[;|\\t]'), 'T05', ref, F.substring(v, 1, 80))]
    X = X.withColumn('fl_linea', F.filter(F.array(*reglas, *tx), lambda x: x.isNotNull()))
    escribir(X.select('id_linea', 'id_plantilla', 'carga_vigente', 'sha256', 'fila', 'rubro_cod', 'rubro', 'sub_rubro', 'tipo', 'area',
                      'pais_carpeta', 'bloqueado', 'vacia', 'clave9',
                      F.col('pais_ok').alias('pais'), F.col('vehiculo_ok').alias('vehiculo'), F.col('ceco_ok').alias('ceco_nombre'),
                      F.col('ceco_n').alias('ceco'), F.col('sede_ok').alias('sede'), F.col('cta_limpia').alias('nom_cta_contable'),
                      'cuenta_oficial', 'metodo_cuenta', F.col('nivel_1_ok').alias('nivel_1'), F.col('nivel_2_ok').alias('nivel_2'),
                      F.col('nivel_3_ok').alias('nivel_3'), F.col('nivel_4_ok').alias('nivel_4'), 'id_linea_pyg',
                      F.col('prov_limpio').alias('proveedor'), 'proveedor_oficial', 'metodo_proveedor', F.col('glosa_ok').alias('glosa'),
                      F.col('comentario_area_ok').alias('comentario_area'), F.col('moneda_ok').alias('moneda'),
                      *L.COL_REAL, *L.COL_PPTO, 'real_ene_ago', 'p27',
                      F.col('ceco_nombre').alias('raw_ceco'), F.col('nom_cta_contable').alias('raw_cta'),
                      F.concat_ws('|', *[F.coalesce(F.col(L.COLUMNAS[i]), F.lit('')) for i in SV.CAMPOS_CLAVE]).alias('raw9'),
                      F.coalesce('fl_celdas', F.array()).alias('fl_celdas'), 'fl_linea'),
             'slv_stage')
    st = spark.table(L.tabla('slv_stage'))

    # ── cambios contra la versión enviada (C01–C04)
    FC_ = _flags_cambio(spark, st, selr)

    # ── flags y estado
    fl_lin = (st.where(~F.col('vacia')).select('id_plantilla', 'id_linea', 'fila', F.explode(F.concat('fl_celdas', 'fl_linea')).alias('f'))
              .select('id_plantilla', 'id_linea', 'fila', 'f.*'))
    fl_vac = st.where('vacia').select('id_plantilla', 'id_linea', 'fila', F.lit('L12').alias('codigo_flag'), F.lit('').alias('celdas'),
                                      F.lit('').alias('detalle'))
    fa = [f for fs in FA.values() for f in fs]
    fl_arch = de_pandas(spark, pd.DataFrame(fa, columns=['id_plantilla', 'id_linea', 'fila', 'codigo_flag', 'severidad', 'celdas', 'detalle']).drop(columns='severidad'),
                        [('id_plantilla', 'string'), ('id_linea', 'string'), ('fila', 'int'), ('codigo_flag', 'string'), ('celdas', 'string'), ('detalle', 'string')])
    FLG = (fl_arch.unionByName(fl_lin.withColumn('fila', F.col('fila').cast('int'))).unionByName(fl_vac.withColumn('fila', F.col('fila').cast('int')))
           .unionByName(FC_).withColumn('severidad', _sev(F.col('codigo_flag')))
           .select('id_plantilla', 'id_linea', 'fila', 'codigo_flag', 'severidad', 'celdas', 'detalle'))
    escribir(FLG, 'slv_flags')
    FLG = spark.table(L.tabla('slv_flags'))
    orden = F.create_map(*[x for s_, i in SEV_NUM.items() for x in (F.lit(s_), F.lit(i))])
    peor = (FLG.where('id_linea IS NOT NULL').groupBy('id_linea')
            .agg(F.min(orden[F.col('severidad')]).alias('o'), F.concat_ws(', ', F.array_sort(F.collect_set('codigo_flag'))).alias('flags')))
    inv = F.create_map(*[x for s_, i in SEV_NUM.items() for x in (F.lit(i), F.lit(s_))])
    LS = (st.where(~F.col('vacia')).join(peor, 'id_linea', 'left')
          .withColumn('severidad_max', inv[F.col('o')]).withColumn('flags', F.coalesce('flags', F.lit('')))
          .withColumn('estado_linea', F.when(F.col('bloqueado'), 'Rechazada (archivo)').when(F.col('severidad_max').isin('BLOQUEANTE', 'ERROR'), 'Cuarentena')
                      .when(F.col('severidad_max') == 'ALERTA', 'OK con alerta').otherwise('OK'))
          .withColumnRenamed('carga_vigente', 'carga_id')
          .select(*[c for c in ['id_linea', 'id_plantilla', 'carga_id', 'sha256', 'fila', 'rubro_cod', 'rubro', 'sub_rubro', 'tipo', 'area',
                                'pais_carpeta', 'pais', 'vehiculo', 'ceco_nombre', 'ceco', 'sede', 'nom_cta_contable', 'cuenta_oficial',
                                'metodo_cuenta', 'nivel_1', 'nivel_2', 'nivel_3', 'nivel_4', 'id_linea_pyg', 'proveedor', 'proveedor_oficial',
                                'metodo_proveedor', 'glosa', 'comentario_area', 'moneda', *L.COL_REAL, *L.COL_PPTO, 'real_ene_ago', 'p27',
                                'severidad_max', 'flags', 'estado_linea']]))
    escribir(LS, 'slv_lineas')

    # ── archivos (tabla chica: se arma en el driver)
    ls = spark.table(L.tabla('slv_lineas'))
    ok = F.col('estado_linea').isin('OK', 'OK con alerta')
    ag = ls.groupBy('id_plantilla').agg(F.count('*').alias('lineas'), F.sum(ok.cast('int')).alias('lineas_ok'),
                                        F.sum(F.when(ok, F.col('p27')).otherwise(0.0)).alias('p27_ok'),
                                        F.sum(F.when(~ok, F.col('p27')).otherwise(0.0)).alias('p27_cuarentena')).toPandas()
    tot = st.groupBy('id_plantilla').agg(F.sum('p27').alias('p27_archivo'), F.count('*').alias('lineas_bronze')).toPandas()
    nsev = FLG.groupBy('id_plantilla', 'severidad').count().toPandas()
    ARC = sel[['id_plantilla', 'carga_id', 'sha256', 'ruta_relativa', 'archivo', 'rubro_cod', 'rubro', 'sub_rubro', 'tipo', 'area', 'pais_carpeta',
               'n_versiones', 'bloqueado']].copy()
    ARC['n_versiones'] = ARC.n_versiones.fillna(1).astype(int)
    ARC['bloqueado'] = ARC.bloqueado.astype(bool)
    ARC = ARC.merge(tot, on='id_plantilla', how='left').merge(ag, on='id_plantilla', how='left')
    for c in ('p27_archivo', 'p27_ok', 'p27_cuarentena'):
        ARC[c] = ARC[c].fillna(0.0).astype(float).round(6)
    for c in ('lineas_bronze', 'lineas', 'lineas_ok'):
        ARC[c] = ARC[c].fillna(0).astype(int)
    for s_ in L.SEV_ORDEN:
        m = nsev[nsev.severidad == s_].set_index('id_plantilla')['count']
        ARC[s_.lower()] = ARC.id_plantilla.map(m).fillna(0).astype(int)
    ARC['estado_archivo'] = ['Rechazado' if b else 'Con errores' if e else 'Con alertas' if a else 'OK'
                             for b, e, a in zip(ARC.bloqueante, ARC.error, ARC.alerta)]
    escribir(de_pandas(spark, ARC), 'slv_archivos')
    est = ls.groupBy('estado_linea').count().toPandas()
    return {r.estado_linea: int(r['count']) for _, r in est.iterrows()}, FLG.count()


def _flags_cambio(spark, st, selr):
    """C01–C04: compara el Real de cada línea con la versión enviada (carga REF_), por plantilla y textos clave."""
    vacio = spark.createDataFrame([], 'id_plantilla string, id_linea string, fila int, codigo_flag string, celdas string, detalle string')
    if selr is None or not len(selr):
        return vacio
    rs = F.broadcast(de_pandas(spark, selr[['sha256', 'id_plantilla']].drop_duplicates('sha256'), [('sha256', 'string'), ('id_plantilla', 'string')]))
    R = (spark.table(L.tabla('brz_lineas')).drop('id_plantilla').dropDuplicates(['sha256', 'fila']).join(rs, 'sha256')
         .withColumn('id_linea', F.concat(F.lit('REF#'), 'id_plantilla', F.lit('#'), F.col('fila'))))
    RL = _monto(_largo(R, L.COL_REAL)).groupBy('id_linea').agg(
        *[F.round(F.coalesce(F.max(F.when(F.col('columna') == kk, F.col('valor'))), F.lit(0.0)), 2).alias(kk) for kk in L.COL_REAL])
    R = R.drop(*L.COL_REAL).join(RL, 'id_linea')
    k9 = lambda df: F.concat_ws('|', *[F.upper(_n(F.coalesce(F.col(L.COLUMNAS[i]), F.lit('')))) for i in SV.CAMPOS_CLAVE])
    real_arr = lambda df: F.array(*[F.col(kk) for kk in L.COL_REAL])
    R = (R.withColumn('k9', k9(R)).withColumn('rv', real_arr(R)).where(F.exists('rv', lambda x: x != 0))
         .withColumn('kalt', F.concat_ws('|', F.upper(_n(F.coalesce('ceco_nombre', F.lit('')))), F.upper(_n(F.coalesce('nom_cta_contable', F.lit('')))),
                                         F.concat_ws(',', F.transform('rv', lambda x: F.round(x, 0).cast('bigint').cast('string')))))
         .withColumn('raw9_env', F.concat_ws('|', *[F.coalesce(F.col(L.COLUMNAS[i]), F.lit('')) for i in SV.CAMPOS_CLAVE]))
         .select('id_plantilla', F.col('fila').alias('fila_env'), 'k9', 'kalt', 'rv', 'ceco_nombre', 'proveedor', 'glosa', 'raw9_env'))
    ids_ref = R.select('id_plantilla').distinct()
    C = (st.where(~F.col('vacia')).join(ids_ref, 'id_plantilla')
         .withColumn('rv', F.array(*[F.round(F.coalesce(F.col(kk), F.lit(0.0)), 2) for kk in L.COL_REAL]))
         .where(F.exists('rv', lambda x: x != 0))
         .withColumn('k9', F.col('clave9'))
         .withColumn('kalt', F.concat_ws('|', F.upper(_n(F.coalesce('raw_ceco', F.lit('')))), F.upper(_n(F.coalesce('raw_cta', F.lit('')))),
                                         F.concat_ws(',', F.transform('rv', lambda x: F.round(x, 0).cast('bigint').cast('string'))))))
    w1, w2 = W.partitionBy('id_plantilla', 'k9').orderBy('fila'), W.partitionBy('id_plantilla', 'k9').orderBy('fila_env')
    c1 = C.withColumn('rn', F.row_number().over(w1))
    r1 = R.withColumn('rn', F.row_number().over(w2))
    m1 = c1.join(r1.select('id_plantilla', 'k9', 'rn', 'fila_env', F.col('rv').alias('rv_env')), ['id_plantilla', 'k9', 'rn'], 'left')
    meses = F.filter(F.transform(F.sequence(F.lit(0), F.lit(7)), lambda i: F.when(F.abs(F.col('rv_env')[i] - F.col('rv')[i]) > 0.005,
                     F.concat(F.lit('mes '), (i + 1).cast('string'), F.lit(': enviado '), F.format_number(F.col('rv_env')[i], 2), F.lit(' → '),
                              F.format_number(F.col('rv')[i], 2)))), lambda x: x.isNotNull())
    c02 = (m1.where(F.col('fila_env').isNotNull() & (F.size(meses) > 0))
           .select('id_plantilla', 'id_linea', 'fila', F.lit('C02').alias('codigo_flag'), F.lit('').alias('celdas'),
                   F.concat_ws('; ', F.slice(meses, 1, 4)).alias('detalle')))
    usados1 = m1.where(F.col('fila_env').isNotNull()).select('id_plantilla', 'fila_env')
    resto_c = m1.where(F.col('fila_env').isNull()).select(*C.columns)
    resto_r = R.join(usados1, ['id_plantilla', 'fila_env'], 'left_anti')
    w3, w4 = W.partitionBy('id_plantilla', 'kalt').orderBy('fila'), W.partitionBy('id_plantilla', 'kalt').orderBy('fila_env')
    m2 = (resto_c.withColumn('rn', F.row_number().over(w3))
          .join(resto_r.withColumn('rn', F.row_number().over(w4)).select('id_plantilla', 'kalt', 'rn', 'fila_env', 'raw9_env'),
                ['id_plantilla', 'kalt', 'rn'], 'left'))
    nombres = [L.ENCABEZADO[i].split('\n')[0] for i in SV.CAMPOS_CLAVE]
    a9, b9 = F.split('raw9_env', '\\|', -1), F.split('raw9', '\\|', -1)
    camb = F.filter(F.transform(F.sequence(F.lit(0), F.lit(len(nombres) - 1)),
                                lambda i: F.when(F.upper(_n(a9[i])) != F.upper(_n(b9[i])), F.array(*[F.lit(n) for n in nombres])[i])),
                    lambda x: x.isNotNull())
    c03 = (m2.where(F.col('fila_env').isNotNull()).select('id_plantilla', 'id_linea', 'fila', F.lit('C03').alias('codigo_flag'), F.lit('').alias('celdas'),
                                                           F.concat(F.lit('Cambió: '), F.concat_ws(', ', camb)).alias('detalle')))
    c01 = (m2.where(F.col('fila_env').isNull())
           .select('id_plantilla', 'id_linea', 'fila', F.lit('C01').alias('codigo_flag'),
                   F.concat_ws(', ', F.filter(F.transform(F.sequence(F.lit(0), F.lit(7)),
                                                          lambda i: F.when(F.col('rv')[i] != 0, F.concat(F.array(*[F.lit(L._col(IDX[kk] + 1)) for kk in L.COL_REAL])[i],
                                                                                                         F.col('fila').cast('string')))),
                                              lambda x: x.isNotNull())).alias('celdas'),
                   F.concat(F.lit('Real '), F.format_number(F.aggregate('rv', F.lit(0.0), lambda a, x: a + x), 2),
                            F.lit(' en línea que no estaba en la versión enviada')).alias('detalle')))
    usados2 = m2.where(F.col('fila_env').isNotNull()).select('id_plantilla', 'fila_env')
    c04 = (resto_r.join(usados2, ['id_plantilla', 'fila_env'], 'left_anti')
           .select('id_plantilla', F.lit(None).cast('string').alias('id_linea'), F.lit(None).cast('int').alias('fila'), F.lit('C04').alias('codigo_flag'),
                   F.concat(F.lit('(enviado fila '), F.col('fila_env'), F.lit(')')).alias('celdas'),
                   F.concat_ws(' · ', _n(F.coalesce('ceco_nombre', F.lit(''))), _n(F.coalesce('proveedor', F.lit(''))), _n(F.coalesce('glosa', F.lit(''))),
                               F.concat(F.lit('Real '), F.format_number(F.aggregate('rv', F.lit(0.0), lambda a, x: a + x), 2))).alias('detalle')))
    return c02.unionByName(c03).unionByName(c01).unionByName(c04).withColumn('fila', F.col('fila').cast('int'))


# ───────────────────────────── GOLD ─────────────────────────────
def _es_negocio(c):
    return c.isin(*GD.TYBA) | ((F.length(c.cast('string')) == 3) & F.substring(c.cast('string'), 1, 1).isin('2', '5', '6', '8', '9'))


def gold(spark, fecha_carga=None):
    """Modelo del Power BI con las mismas tablas y columnas que los CSV de ejemplo (ppto27_gld_*)."""
    from datetime import date
    M, AL, D0 = L.cargar_maestros()
    D = GD.cargar_drivers(D0)
    tc = GD.tipo_cambio(M)
    fecha_carga = fecha_carga or date.today().isoformat()
    TC = F.broadcast(spark.createDataFrame([(mon, m + 1, float(v)) for mon, vals in tc.items() for m, v in enumerate(vals) if v is not None],
                                           'moneda string, mes int, tc double'))
    loc = F.create_map(*[x for p, m in L.MONEDA_LOCAL.items() for x in (F.lit(p), F.lit(m))])
    txt = lambda c: F.coalesce(F.col(c), F.lit(''))
    S = (spark.table(L.tabla('slv_lineas'))
         .withColumn('cuenta_oficial', txt('cuenta_oficial')).withColumn('nivel_1', txt('nivel_1'))
         .withColumn('nivel_2', txt('nivel_2')).withColumn('nivel_3', txt('nivel_3'))
         .withColumn('proveedor_bi', F.coalesce('proveedor_oficial', F.lit('(sin proveedor)'))))
    meses = F.array(*[F.struct(F.lit(m).alias('mes'), F.col(f'ppto_2027_{m:02d}').alias('v')) for m in range(1, 13)])
    PL = (S.select('id_linea', 'id_plantilla', 'pais', 'ceco', 'vehiculo', 'cuenta_oficial', 'nivel_1', 'nivel_2', 'nivel_3', 'proveedor_bi',
                   'id_linea_pyg', 'glosa', 'moneda', 'estado_linea', 'flags', 'tipo', 'area', F.explode(meses).alias('x'))
          .select('*', 'x.mes', 'x.v').drop('x').where(F.col('v').isNotNull() & (F.col('v') != 0))
          .withColumn('moneda_local', F.coalesce(loc[F.col('pais')], F.lit('PEN')))
          .join(TC.select(F.col('moneda'), 'mes', F.col('tc').alias('tc_o')), ['moneda', 'mes'], 'left')
          .join(TC.where("moneda = 'PEN'").select('mes', F.col('tc').alias('tc_pen')), 'mes', 'left')
          .join(TC.select(F.col('moneda').alias('moneda_local'), 'mes', F.col('tc').alias('tc_loc')), ['moneda_local', 'mes'], 'left')
          .withColumn('usd', F.col('v') / F.col('tc_o'))
          .withColumn('pen', F.coalesce(F.col('usd') * F.col('tc_pen'), F.lit(0.0)))
          .withColumn('loc', F.coalesce(F.col('usd') * F.col('tc_loc'), F.lit(0.0))))
    escribir(PL, 'gld_stage')
    PL = spark.table(L.tabla('gld_stage'))

    # dimensiones que salen de las líneas
    dc = (S.select('cuenta_oficial', 'nivel_1', 'nivel_2', 'nivel_3').distinct().toPandas()
          .sort_values(['nivel_1', 'nivel_2', 'cuenta_oficial', 'nivel_3']).reset_index(drop=True))
    dc.insert(0, 'id_cuenta', range(1, len(dc) + 1))
    provs = sorted(r.proveedor_bi for r in S.select('proveedor_bi').distinct().collect())
    dprov = pd.DataFrame({'id_proveedor': range(1, len(provs) + 1), 'proveedor': provs})
    cta_s = F.broadcast(de_pandas(spark, dc, [('id_cuenta', 'int'), ('cuenta_oficial', 'string'), ('nivel_1', 'string'), ('nivel_2', 'string'), ('nivel_3', 'string')]))
    prv_s = F.broadcast(de_pandas(spark, dprov.rename(columns={'proveedor': 'proveedor_bi'}), [('id_proveedor', 'int'), ('proveedor_bi', 'string')]))
    fecha = (F.lit(20270000) + F.col('mes') * 100 + 1).cast('int')
    clave = lambda *cs: F.concat_ws('|', *cs)
    fact_ppto = (PL.join(cta_s, ['cuenta_oficial', 'nivel_1', 'nivel_2', 'nivel_3'], 'left').join(prv_s, 'proveedor_bi', 'left')
                 .select('id_linea', 'id_plantilla', fecha.alias('id_fecha'), F.col('pais').alias('id_pais'),
                         F.when(F.col('ceco').isNotNull(), clave('pais', F.col('ceco').cast('string'))).alias('id_ceco'),
                         F.when(F.col('vehiculo').isNotNull(), clave('pais', 'vehiculo')).alias('id_vehiculo'), 'id_cuenta', 'id_proveedor',
                         F.col('id_linea_pyg').cast('int').alias('id_linea_pyg'), 'glosa', F.lit('Ppto 2027').alias('escenario'),
                         F.col('moneda').alias('moneda_origen'), F.round('v', 6).alias('monto_origen'), F.round('loc', 6).alias('monto_local'),
                         F.round('pen', 6).alias('monto_pen'), F.lit('Área').alias('origen_monto'), 'estado_linea', 'flags'))
    escribir(fact_ppto, 'gld_fact_ppto')

    # Gestión Dir/Ind: drivers por vehículo exacto; si no, "(todos)"; si no hay driver, regla por CeCo
    Ds = F.broadcast(de_pandas(spark, D[['pais', 'ceco', 'vehiculo', 'componente', 'udn', 'porcentaje']],
                               [('pais', 'string'), ('ceco', 'bigint'), ('vehiculo', 'string'), ('componente', 'string'), ('udn', 'string'), ('porcentaje', 'double')]))
    exactos = Ds.select('pais', 'ceco', 'vehiculo').distinct().withColumn('exacto', F.lit(True))
    OK = (PL.where(F.col('estado_linea').isin(*GD.OK) & F.col('pais').isin(*L.MONEDA_LOCAL) & (F.abs('pen') > 0))
          .join(exactos, ['pais', 'ceco', 'vehiculo'], 'left')
          .withColumn('veh_driver', F.when(F.col('exacto'), F.col('vehiculo')).otherwise(F.lit('(todos)'))))
    A = (OK.join(Ds.withColumnRenamed('vehiculo', 'veh_driver'), ['pais', 'ceco', 'veh_driver'], 'left')
         .withColumn('sin_driver', F.col('componente').isNull()))                # se fija ANTES de rellenar el componente
    sin = F.col('sin_driver')
    regla = F.col('ceco').isNotNull() & _es_negocio(F.col('ceco')) & (F.col('tipo') == 'UdN')
    A = (A.withColumn('componente', F.when(sin, F.when(regla, 'Imputación directa').otherwise('Indirecto')).otherwise(F.col('componente')))
          .withColumn('udn', F.when(sin, F.when(regla, F.col('area')).otherwise('BOLSA')).otherwise(F.col('udn')))
          .withColumn('pct', F.when(sin, F.lit(1.0)).otherwise(F.col('porcentaje')))
          .withColumn('monto', F.col('pen') * F.col('pct')))
    imp = A.where("componente = 'Imputación directa'").groupBy('pais', 'udn', 'mes').agg(F.sum('monto').alias('imp'))
    part = imp.withColumn('part', F.col('imp') / F.sum('imp').over(W.partitionBy('pais', 'mes')))
    con_base = imp.groupBy('pais').agg(F.sum(F.abs('imp')).alias('b')).where('b > 0').select('pais', F.lit(True).alias('con_base'))
    bolsa = A.where("componente = 'Indirecto'").join(con_base, 'pais', 'left')
    asignado = (bolsa.where('con_base').drop('udn').join(part.select('pais', 'mes', 'udn', 'part'), ['pais', 'mes'])
                .withColumn('monto', F.col('monto') * F.coalesce('part', F.lit(0.0))).withColumn('componente', F.lit('Indirecto asignado')))
    sin_base = (bolsa.where(F.col('con_base').isNull()).withColumn('udn', F.lit('Sin base de reparto'))
                .withColumn('componente', F.lit('Indirecto asignado')))
    cols = ['id_linea', 'id_plantilla', 'pais', 'ceco', 'mes', 'id_linea_pyg', 'componente', 'udn', 'pct', 'monto']
    AL_ = A.where("componente <> 'Indirecto'").select(*cols).unionByName(asignado.select(*cols)).unionByName(sin_base.select(*cols))
    comp = F.create_map(*[x for i, c, _ in GD.COMP for x in (F.lit(c), F.lit(i))])
    fact_gd = (AL_.where(F.abs('monto') >= 1e-9)
               .join(TC.where("moneda = 'PEN'").select('mes', F.col('tc').alias('tc_pen')), 'mes')
               .withColumn('moneda_local', loc[F.col('pais')])
               .join(TC.select(F.col('moneda').alias('moneda_local'), 'mes', F.col('tc').alias('tc_loc')), ['moneda_local', 'mes'])
               .select('id_linea', 'id_plantilla', fecha.alias('id_fecha'), F.col('pais').alias('id_pais'), F.col('udn').alias('id_udn'),
                       comp[F.col('componente')].cast('int').alias('id_componente'), clave('pais', F.col('ceco').cast('string')).alias('id_ceco_origen'),
                       F.col('id_linea_pyg').cast('int').alias('id_linea_pyg'), F.round('pct', 6).alias('pct_driver'), F.round('monto', 6).alias('monto_pen'),
                       F.round(F.col('monto') / F.col('tc_pen') * F.col('tc_loc'), 6).alias('monto_local')))
    escribir(fact_gd, 'gld_fact_gestion_dirind')
    escribir(spark.table(L.tabla('slv_flags')).select(*GD.COLS['fact_flags']), 'gld_fact_flags')

    # dimensiones chicas (misma función que la versión pandas)
    usados = (S.where('ceco IS NOT NULL').select('pais', 'ceco', 'ceco_nombre').distinct().toPandas()
              .sort_values(['pais', 'ceco', 'ceco_nombre']).drop_duplicates(['pais', 'ceco']))
    usados['ceco'] = usados.ceco.astype(int)
    veh = {(r.pais, r.vehiculo) for r in S.select('pais', 'vehiculo').distinct().collect()}
    udns = sorted(r.id_udn for r in spark.table(L.tabla('gld_fact_gestion_dirind')).select('id_udn').distinct().collect())
    ARC = spark.table(L.tabla('slv_archivos')).toPandas()
    dims = GD.dimensiones(usados, veh, udns, ARC, M, D, fecha_carga)
    dims['dim_cuenta'] = dc.rename(columns={'cuenta_oficial': 'nom_cta_contable'}).replace('', None)
    dims['dim_proveedor'] = dprov
    tipos = {'id_fecha': 'int', 'anio': 'int', 'mes_num': 'int', 'id_linea_pyg': 'int', 'orden_n1': 'int', 'orden_n2': 'int', 'ceco': 'bigint',
             'id_componente': 'int', 'id_cuenta': 'int', 'id_proveedor': 'int', 'porcentaje': 'double'}
    for n, df in dims.items():
        df = df[GD.COLS[n]]
        escribir(de_pandas(spark, df, [(c, tipos.get(c, 'string')) for c in df.columns]), f'gld_{n}')
    return {n: spark.table(L.tabla(f'gld_{n}')).count() for n in GD.COLS}


# ───────────────────────────── CONTROL ─────────────────────────────
def control(spark):
    """Cuadre 100 = 100 por plantilla, integridad y contable = Dir/Ind. Devuelve (cuadre, controles) en pandas y los guarda."""
    t = lambda n: spark.table(L.tabla(f'gld_{n}'))
    ARC = spark.table(L.tabla('slv_archivos')).toPandas()
    fp = t('fact_ppto')
    g = fp.groupBy('id_plantilla').agg(F.sum('monto_origen').alias('p27_gold')).toPandas().set_index('id_plantilla').p27_gold
    cu = ARC[['id_plantilla', 'archivo', 'rubro', 'pais_carpeta', 'estado_archivo', 'p27_archivo', 'p27_ok', 'p27_cuarentena']].copy()
    cu['p27_gold'] = cu.id_plantilla.map(g).fillna(0.0)
    cu['diferencia'] = (cu.p27_archivo - cu.p27_gold).round(2)
    cu['cuadra'] = cu.diferencia.abs() < 0.01
    ctl = []

    def ok(nombre, cond, det='', tipo='Crítico'):
        ctl.append(dict(control=nombre, tipo=tipo, resultado='OK' if cond else 'FALLA', detalle=det))
    ok('Cuadre 100 = 100: Ppto 2027 del archivo = fact_ppto, por plantilla', bool(cu.cuadra.all()),
       f'{int(cu.cuadra.sum())} de {len(cu)} plantillas; dif. máx. {cu.diferencia.abs().max() if len(cu) else 0:,.2f}')
    nb = spark.table(L.tabla('brz_lineas')).groupBy('sha256').count().toPandas().set_index('sha256')['count']
    dif = int((ARC.set_index('sha256').lineas_bronze - nb.reindex(ARC.sha256).fillna(0).values).abs().sum())
    ok('Filas bronze = filas leídas en silver', dif == 0, f'diferencia {dif}')
    for tb, col, dim, dcol in [('fact_ppto', 'id_fecha', 'dim_fecha', 'id_fecha'), ('fact_ppto', 'id_pais', 'dim_pais', 'id_pais'),
                               ('fact_ppto', 'id_ceco', 'dim_ceco', 'id_ceco'), ('fact_ppto', 'id_vehiculo', 'dim_vehiculo', 'id_vehiculo'),
                               ('fact_ppto', 'id_cuenta', 'dim_cuenta', 'id_cuenta'), ('fact_ppto', 'id_proveedor', 'dim_proveedor', 'id_proveedor'),
                               ('fact_ppto', 'id_plantilla', 'dim_plantilla', 'id_plantilla'), ('fact_ppto', 'id_linea_pyg', 'dim_linea_pyg', 'id_linea_pyg'),
                               ('fact_gestion_dirind', 'id_udn', 'dim_udn', 'id_udn'), ('fact_gestion_dirind', 'id_ceco_origen', 'dim_ceco', 'id_ceco'),
                               ('fact_gestion_dirind', 'id_componente', 'dim_componente', 'id_componente'),
                               ('fact_flags', 'codigo_flag', 'dim_flag', 'codigo_flag'), ('fact_flags', 'id_plantilla', 'dim_plantilla', 'id_plantilla')]:
        falt = [r[0] for r in t(tb).select(col).where(F.col(col).isNotNull()).distinct()
                .join(t(dim).select(F.col(dcol).alias(col)), col, 'left_anti').limit(3).collect()]
        n = t(tb).select(col).where(F.col(col).isNotNull()).distinct().join(t(dim).select(F.col(dcol).alias(col)), col, 'left_anti').count() if falt else 0
        ok(f'{tb}.{col} → {dim}', not falt, f'{n} claves sin dimensión' + (f': {[str(x) for x in falt]}' if falt else ''))
    for dim, k in [('dim_cuenta', 'id_cuenta'), ('dim_proveedor', 'id_proveedor'), ('dim_ceco', 'id_ceco'), ('dim_vehiculo', 'id_vehiculo'),
                   ('dim_plantilla', 'id_plantilla'), ('dim_linea_pyg', 'id_linea_pyg'), ('dim_flag', 'codigo_flag')]:
        r = t(dim).agg(F.count('*').alias('n'), F.countDistinct(k).alias('d')).first()
        ok(f'{dim}.{k} único', r['n'] == r['d'])
    sm = fp.where('id_linea_pyg = 0').select('id_linea').distinct().count()
    ok('Toda línea con monto mapeada al Formato Perú (N1 / N2)', sm == 0, f'{sm} líneas sin mapeo (Nivel 1 / 2 que no existe en el formato)',
       tipo='Dato')
    okp = fp.where(F.col('estado_linea').isin(*GD.OK)).groupBy('id_pais', 'id_fecha').agg(F.sum('monto_pen').alias('c')).toPandas()
    gd = t('fact_gestion_dirind').groupBy('id_pais', 'id_fecha').agg(F.sum('monto_pen').alias('g')).toPandas()
    m = okp.merge(gd, on=['id_pais', 'id_fecha'], how='outer').fillna(0.0)
    d = (m.c - m.g).abs()
    ok('Contable (líneas OK) = Gestión Dir/Ind, por país × mes (PEN)', bool((d < 0.01).all()),
       f'{int((d < 0.01).sum())} de {len(d)} país × mes; dif. máx. {d.max() if len(d) else 0:,.4f}')
    pos = fp.where((F.col('monto_origen') > 0) & F.col('estado_linea').isin(*GD.OK)).count()
    ok('Ningún monto positivo en líneas OK', pos == 0, f'{pos} filas')
    CTL = pd.DataFrame(ctl)
    ahora = datetime.now()
    escribir(de_pandas(spark, cu.assign(fecha_control=ahora), [(c, 'double' if c.startswith('p27') or c == 'diferencia' else 'boolean' if c == 'cuadra'
                                                                 else 'timestamp' if c == 'fecha_control' else 'string') for c in list(cu.columns) + ['fecha_control']]),
             'ctl_cuadre', 'append')
    escribir(de_pandas(spark, CTL.assign(fecha_control=ahora), [('control', 'string'), ('tipo', 'string'), ('resultado', 'string'), ('detalle', 'string'),
                                                                 ('fecha_control', 'timestamp')]),
             'ctl_controles', 'append')
    return cu, CTL


# ───────────────────────────── VALIDACIÓN DEL REPARTO DIR/IND ─────────────────────────────
def _alcance_dirind(spark):
    """Líneas × mes que deben repartirse: contables OK / OK con alerta, de país con moneda local y monto PEN ≠ 0 (con país, CeCo y vehículo)."""
    fp = spark.table(L.tabla('gld_fact_ppto'))
    return (fp.where(F.col('estado_linea').isin(*GD.OK) & F.col('id_pais').isin(*L.MONEDA_LOCAL) & (F.abs('monto_pen') > 0))
            .groupBy('id_linea', 'id_plantilla', 'id_fecha', 'id_pais', 'id_ceco', 'id_vehiculo').agg(F.sum('monto_pen').alias('pen'))
            .withColumn('ceco', F.expr('try_cast(substring(id_ceco, length(id_pais) + 2) AS BIGINT)'))
            .withColumn('vehiculo', F.expr('substring(id_vehiculo, length(id_pais) + 2)')))


def validar(spark, tol=0.01):
    """Recalcula el reparto Dir/Ind SÓLO con las tablas gold (contable + tabla de drivers + plantillas), sin usar gold(), y lo compara con
    fact_gestion_dirind. Devuelve dict de DataFrames pandas: 'checks' (resumen) y el detalle de cada check. Guarda ppto27_ctl_validacion."""
    t = lambda n: spark.table(L.tabla(f'gld_{n}'))
    gd = t('fact_gestion_dirind').join(F.broadcast(t('dim_componente').select('id_componente', 'componente')), 'id_componente', 'left')
    dd = t('dim_driver').select('pais', 'ceco', 'vehiculo', 'componente', 'udn', 'porcentaje')
    A = _alcance_dirind(spark)
    checks, R = [], {}

    def chk(clave, nombre, tipo, fallas, casos, detalle, df=None):
        malo = 'FALLA' if tipo == 'Crítico' else 'REVISAR'
        checks.append(dict(control=nombre, tipo=tipo, resultado='OK' if fallas == 0 else malo, casos=int(casos), con_diferencia=int(fallas),
                           detalle=detalle))
        if df is not None:
            R[clave] = df

    # V1 · conservación: cada línea contable × mes se reparte al 100 % (ni se pierde ni se duplica plata)
    v1 = (A.groupBy('id_linea', 'id_fecha', 'id_pais').agg(F.sum('pen').alias('contable'))
          .join(gd.groupBy('id_linea', 'id_fecha').agg(F.sum('monto_pen').alias('repartido')), ['id_linea', 'id_fecha'], 'full')
          .fillna(0.0, ['contable', 'repartido']).withColumn('diferencia', F.round(F.col('contable') - F.col('repartido'), 4)))
    n, f = v1.count(), v1.where(F.abs('diferencia') >= tol)
    nf = f.count()
    chk('v1_conservacion', '1. Cada línea contable × mes se reparte al 100 % (contable = suma de su reparto)', 'Crítico', nf, n,
        f'{n:,} línea × mes; {nf} con diferencia ≥ {tol}', f.orderBy(F.abs('diferencia').desc()).limit(500).toPandas())

    # V2 · tabla de drivers: cada CeCo × vehículo suma 100 %
    v2 = dd.groupBy('pais', 'ceco', 'vehiculo').agg(F.round(F.sum('porcentaje'), 8).alias('suma_porcentaje'))
    f = v2.where(F.abs(F.col('suma_porcentaje') - 1) > 1e-6)
    nf = f.count()
    chk('v2_drivers_100', '2. Tabla de drivers: cada país × CeCo × vehículo suma 100 %', 'Crítico', nf, v2.count(),
        f'{nf} combinaciones que no suman 100 %', f.toPandas())

    # V3 · recálculo línea por línea: driver por vehículo exacto, si no "(todos)"; sin driver → regla (CeCo de negocio en plantilla UdN →
    #      imputación directa a su UdN; si no, bolsa de indirectos). La parte indirecta se compara como total "(bolsa)" de la línea.
    exactos = dd.select('pais', 'ceco', 'vehiculo').distinct().withColumn('exacto', F.lit(True))
    B = (A.join(exactos.withColumnRenamed('pais', 'id_pais'), ['id_pais', 'ceco', 'vehiculo'], 'left')
         .withColumn('veh_driver', F.when(F.col('exacto'), F.col('vehiculo')).otherwise(F.lit('(todos)'))))
    con = (B.join(dd.withColumnRenamed('pais', 'id_pais').withColumnRenamed('vehiculo', 'veh_driver'), ['id_pais', 'ceco', 'veh_driver'])
           .select('id_linea', 'id_fecha', 'componente', 'udn', (F.col('pen') * F.col('porcentaje')).alias('m')))
    pl = F.broadcast(t('dim_plantilla').select('id_plantilla', 'tipo', 'area'))
    sin = (B.join(dd.select(F.col('pais').alias('id_pais'), 'ceco', F.col('vehiculo').alias('veh_driver')).distinct(),
                  ['id_pais', 'ceco', 'veh_driver'], 'left_anti').join(pl, 'id_plantilla', 'left'))
    regla = F.col('ceco').isNotNull() & _es_negocio(F.col('ceco')) & (F.col('tipo') == 'UdN')
    sin_r = sin.select('id_linea', 'id_fecha', F.when(regla, 'Imputación directa').otherwise('Indirecto').alias('componente'),
                       F.when(regla, F.col('area')).otherwise('BOLSA').alias('udn'), F.col('pen').alias('m'))
    k = lambda: [F.when(F.col('componente').isin('Indirecto', 'Indirecto asignado'), F.lit('Indirecto')).otherwise(F.col('componente')).alias('componente'),
                 F.when(F.col('componente').isin('Indirecto', 'Indirecto asignado'), F.lit('(bolsa)')).otherwise(F.col('udn')).alias('udn')]
    esp = con.unionByName(sin_r).select('id_linea', 'id_fecha', *k(), 'm').groupBy('id_linea', 'id_fecha', 'componente', 'udn').agg(F.sum('m').alias('esperado'))
    act = (gd.withColumnRenamed('id_udn', 'udn').select('id_linea', 'id_fecha', *k(), 'monto_pen')
           .groupBy('id_linea', 'id_fecha', 'componente', 'udn').agg(F.sum('monto_pen').alias('en_tabla')))
    v3 = (esp.join(act, ['id_linea', 'id_fecha', 'componente', 'udn'], 'full').fillna(0.0, ['esperado', 'en_tabla'])
          .withColumn('diferencia', F.round(F.col('esperado') - F.col('en_tabla'), 4)))
    n, f = v3.count(), v3.where(F.abs('diferencia') >= tol)
    nf = f.count()
    chk('v3_recalculo', '3. Recálculo independiente línea × mes × UdN × componente = fact_gestion_dirind (driver o regla)', 'Crítico', nf, n,
        f'{n:,} combinaciones; {nf} con diferencia ≥ {tol}', f.orderBy(F.abs('diferencia').desc()).limit(500).toPandas())

    # V4 · la bolsa de indirectos de cada país × mes se reparte en la misma proporción que la imputación directa de cada UdN
    imp = gd.where("componente = 'Imputación directa'").groupBy('id_pais', 'id_fecha', 'id_udn').agg(F.sum('monto_pen').alias('imp'))
    ind = gd.where("componente = 'Indirecto asignado' AND id_udn <> 'Sin base de reparto'")
    tot = ind.groupBy('id_pais', 'id_fecha').agg(F.sum('monto_pen').alias('bolsa'))
    w = W.partitionBy('id_pais', 'id_fecha')
    v4 = (imp.withColumn('part_imputacion', F.col('imp') / F.sum('imp').over(w))
          .join(ind.groupBy('id_pais', 'id_fecha', 'id_udn').agg(F.sum('monto_pen').alias('indirecto_asignado')), ['id_pais', 'id_fecha', 'id_udn'], 'full')
          .join(tot, ['id_pais', 'id_fecha'], 'left').fillna(0.0, ['imp', 'indirecto_asignado', 'bolsa', 'part_imputacion'])
          .withColumn('esperado', F.col('bolsa') * F.col('part_imputacion'))
          .withColumn('diferencia', F.round(F.col('esperado') - F.col('indirecto_asignado'), 4)))
    n, f = v4.count(), v4.where(F.abs('diferencia') >= tol)
    nf = f.count()
    chk('v4_indirectos', '4. Indirectos de cada país × mes repartidos según la participación de la imputación directa por UdN', 'Crítico', nf, n,
        f'{n:,} país × mes × UdN; {nf} con diferencia ≥ {tol}', v4.orderBy('id_pais', 'id_fecha', 'id_udn').toPandas())

    # V5 · plata que no se pudo repartir (país sin imputación directa)
    sb = gd.where("id_udn = 'Sin base de reparto'").groupBy('id_pais').agg(F.round(F.sum('monto_pen'), 2).alias('monto_pen')).toPandas()
    chk('v5_sin_base', '5. Indirectos sin base de reparto (país sin imputación directa)', 'Dato', len(sb), len(sb),
        'ninguno' if sb.empty else ', '.join(f'{r.id_pais} {r.monto_pen:,.0f}' for r in sb.itertuples()), sb)

    # V6 · líneas contables OK que quedan fuera del Dir/Ind (país sin moneda local, p. ej. Regional)
    fu = (t('fact_ppto').where(F.col('estado_linea').isin(*GD.OK) & ~F.col('id_pais').isin(*L.MONEDA_LOCAL))
          .groupBy('id_pais').agg(F.countDistinct('id_linea').alias('lineas'), F.round(F.sum('monto_pen'), 2).alias('monto_pen')).toPandas())
    chk('v6_fuera', '6. Líneas contables OK fuera del Dir/Ind (país no reconocido)', 'Dato', len(fu), len(fu),
        'ninguna' if fu.empty else ', '.join(f'{r.id_pais}: {r.lineas} líneas' for r in fu.itertuples()), fu)

    # V7 · CeCos sin driver: se repartieron por regla → lista para confirmar con Planeamiento (no es error)
    sd = (sin.join(F.broadcast(t('dim_ceco').select('id_ceco', 'ceco_nombre', 'agrupacion')), 'id_ceco', 'left')
          .withColumn('destino', F.when(regla, F.concat(F.lit('Imputación directa → '), F.col('area'))).otherwise(F.lit('Bolsa de indirectos')))
          .groupBy('id_pais', 'ceco', 'ceco_nombre', 'agrupacion', 'vehiculo', 'destino')
          .agg(F.countDistinct('id_linea').alias('lineas'), F.round(F.sum('pen'), 2).alias('monto_pen'))
          .orderBy('id_pais', 'ceco').toPandas())
    chk('v7_sin_driver', '7. CeCo × vehículo sin driver (repartidos por regla; confirmar con Planeamiento)', 'Revisar', len(sd), len(sd),
        f'{len(sd)} CeCo × vehículo; {sd.monto_pen.sum() if len(sd) else 0:,.0f} PEN', sd)

    # Resumen para cruzar con el Power BI: país × Nivel 1 → contable vs Directo / Indirecto
    pyg = F.broadcast(t('dim_linea_pyg').select('id_linea_pyg', 'orden_n1', 'n1_formato'))
    grp = F.broadcast(t('dim_componente').select('id_componente', 'grupo'))
    c = (t('fact_ppto').where(F.col('estado_linea').isin(*GD.OK) & F.col('id_pais').isin(*L.MONEDA_LOCAL)).join(pyg, 'id_linea_pyg', 'left')
         .groupBy('id_pais', 'orden_n1', 'n1_formato').agg(F.sum('monto_pen').alias('contable_pen')))
    g = (t('fact_gestion_dirind').join(pyg, 'id_linea_pyg', 'left').join(grp, 'id_componente', 'left').groupBy('id_pais', 'orden_n1', 'n1_formato')
         .pivot('grupo', ['Directo', 'Indirecto']).agg(F.sum('monto_pen')))
    res = (c.join(g, ['id_pais', 'orden_n1', 'n1_formato'], 'full').fillna(0.0).toPandas()
           .sort_values(['id_pais', 'orden_n1']).drop(columns='orden_n1').rename(columns={'Directo': 'directo_pen', 'Indirecto': 'indirecto_pen'}))
    res['dirind_pen'] = res.directo_pen + res.indirecto_pen
    res['diferencia'] = (res.contable_pen - res.dirind_pen).round(2)
    for col in ('contable_pen', 'directo_pen', 'indirecto_pen', 'dirind_pen'):
        res[col] = res[col].round(2)
    R['resumen_bi'] = res
    R['udn_pais'] = (t('fact_gestion_dirind').join(grp, 'id_componente', 'left').groupBy('id_pais', 'id_udn')
                     .pivot('grupo', ['Directo', 'Indirecto']).agg(F.round(F.sum('monto_pen'), 2)).fillna(0.0).orderBy('id_pais', 'id_udn').toPandas())

    CH = pd.DataFrame(checks)
    R['checks'] = CH
    escribir(de_pandas(spark, CH.assign(fecha_validacion=datetime.now()),
                       [('control', 'string'), ('tipo', 'string'), ('resultado', 'string'), ('casos', 'bigint'), ('con_diferencia', 'bigint'),
                        ('detalle', 'string'), ('fecha_validacion', 'timestamp')]), 'ctl_validacion', 'append')
    return R


def trazar(spark, id_linea=None):
    """Trazabilidad de UNA línea: contable por mes → drivers que le tocan → cómo quedó en fact_gestion_dirind (UdN × componente).
    Sin id_linea toma la de mayor monto cuyo driver reparte a más de una UdN / componente. Devuelve dict de DataFrames pandas."""
    t = lambda n: spark.table(L.tabla(f'gld_{n}'))
    A = _alcance_dirind(spark)
    dd = t('dim_driver')
    if id_linea is None:
        varios = dd.groupBy(F.col('pais').alias('id_pais'), 'ceco').agg(F.countDistinct('udn', 'componente').alias('n')).where('n > 1')
        id_linea = (A.join(varios.select('id_pais', 'ceco'), ['id_pais', 'ceco'])
                    .groupBy('id_linea').agg(F.sum(F.abs('pen')).alias('a')).orderBy(F.desc('a')).first()['id_linea'])
    lin = A.where(F.col('id_linea') == id_linea)
    x = lin.select('id_pais', 'ceco', 'vehiculo').distinct().first()
    if x is None:
        raise ValueError(f'La línea {id_linea} no está en el alcance del Dir/Ind (estado no OK, país sin moneda local o monto 0)')
    cab = (t('fact_ppto').where(F.col('id_linea') == id_linea)
           .join(t('dim_plantilla').select('id_plantilla', 'archivo', 'tipo', 'area'), 'id_plantilla', 'left')
           .join(t('dim_cuenta').select('id_cuenta', 'nom_cta_contable'), 'id_cuenta', 'left')
           .join(t('dim_linea_pyg').select('id_linea_pyg', 'n1_formato', 'n2_formato'), 'id_linea_pyg', 'left')
           .groupBy('id_linea', 'archivo', 'tipo', 'area', 'id_pais', 'id_ceco', 'id_vehiculo', 'nom_cta_contable', 'n1_formato', 'n2_formato', 'estado_linea')
           .agg(F.round(F.sum('monto_pen'), 2).alias('total_pen')).toPandas())
    drv = dd.where((F.col('pais') == x['id_pais']) & (F.col('ceco') == x['ceco']) & F.col('vehiculo').isin(x['vehiculo'], '(todos)')).toPandas()
    if (drv.vehiculo == x['vehiculo']).any():
        drv = drv[drv.vehiculo == x['vehiculo']]
    else:
        drv = drv[drv.vehiculo == '(todos)']
    meses = (lin.join(t('dim_fecha').select('id_fecha', 'mes_num'), 'id_fecha').select('mes_num', F.round('pen', 2).alias('contable_pen'))
             .orderBy('mes_num').toPandas())
    rep = (t('fact_gestion_dirind').where(F.col('id_linea') == id_linea)
           .join(t('dim_componente').select('id_componente', 'componente'), 'id_componente')
           .join(t('dim_fecha').select('id_fecha', 'mes_num'), 'id_fecha')
           .groupBy('id_udn', 'componente').pivot('mes_num', list(range(1, 13))).agg(F.round(F.sum('monto_pen'), 2))
           .orderBy('componente', 'id_udn').toPandas())
    rep = rep.rename(columns={str(m): GD.PERIODO[m - 1] for m in range(1, 13)})
    rep['total'] = rep[[c for c in GD.PERIODO if c in rep.columns]].fillna(0).sum(axis=1).round(2)
    return dict(id_linea=id_linea, linea=cab, contable_por_mes=meses,
                drivers=drv if len(drv) else pd.DataFrame([{'nota': 'Sin driver: se reparte por regla (negocio en UdN → imputación directa; si no, bolsa)'}]),
                reparto=rep)


def exportar_validacion(R):
    """Excel con el resultado de validar() en 30_bi/ (se arma en memoria y se escribe de una vez: el Volume no admite escritura aleatoria)."""
    import io
    hojas = [('Controles', 'checks'), ('Resumen para el BI', 'resumen_bi'), ('UdN por país', 'udn_pais'), ('Sin driver', 'v7_sin_driver'),
             ('Indirectos por UdN', 'v4_indirectos'), ('Dif. conservación', 'v1_conservacion'), ('Dif. recálculo', 'v3_recalculo'),
             ('Drivers no 100', 'v2_drivers_100'), ('Sin base de reparto', 'v5_sin_base'), ('Fuera del Dir-Ind', 'v6_fuera')]
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine='openpyxl') as w:
        for hoja, k in hojas:
            if k in R:
                R[k].to_excel(w, sheet_name=hoja, index=False)
    os.makedirs(L.BI, exist_ok=True)
    ruta = os.path.join(L.BI, f'Validacion_DirInd_{datetime.now():%Y%m%d_%H%M%S}.xlsx')
    with open(ruta, 'wb') as f:
        f.write(b.getvalue())
    return ruta


# ───────────────────────────── BANDEJA DE ENTRADA ─────────────────────────────
TABLAS_BI = ['fact_ppto', 'fact_flags', 'dim_linea_pyg', 'dim_fecha', 'dim_pais', 'dim_ceco', 'dim_vehiculo', 'dim_cuenta', 'dim_proveedor',
             'dim_plantilla', 'dim_flag']                                       # las que lee el .pbip (scripts/generar_pbip.py)


def _nombre_en_zip(info):
    """Nombre real dentro del zip: UTF-8 (Mac, SharePoint, 7-Zip) o cp850 (Explorador de Windows)."""
    n = info.filename
    if not info.flag_bits & 0x800:
        crudo = n.encode('cp437')
        for cod in ('utf-8', 'cp850', 'cp1252'):
            try:
                n = crudo.decode(cod)
                break
            except UnicodeDecodeError:
                continue
    return unicodedata.normalize('NFC', n.replace('\\', '/'))


def _ignorar(nombre):
    base = os.path.basename(nombre.rstrip('/'))
    return '__MACOSX' in nombre or base.startswith(('.', '~$')) or base.lower() in ('thumbs.db', 'desktop.ini')


def _extraer(zip_path, destino):
    """Extrae conservando la fecha de modificación original (decide la versión vigente si llegan dos iguales)."""
    import zipfile
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            nom = _nombre_en_zip(info)
            if nom.endswith('/') or _ignorar(nom):
                continue
            out = os.path.join(destino, *[p for p in nom.split('/') if p not in ('', '.', '..')])
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with z.open(info) as src, open(out, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            t = datetime(*info.date_time).timestamp()
            os.utime(out, (t, t))
            n += 1
    return n


def recibir(ahora=None):
    """10_entrada → 11_procesado/<carga_id>/ (y REF_<carga_id>/ para la versión enviada). Acepta zips, carpetas y Excel sueltos.
    Primero copia y verifica; recién al final vacía la entrada. Devuelve dict(carga_id, carga, ref, detalle) o None si no hay nada."""
    ahora = ahora or datetime.now()
    os.makedirs(L.ENTRADA, exist_ok=True)
    items = sorted(x for x in os.listdir(L.ENTRADA) if not _ignorar(x))
    if not items:
        return None
    carga_id = ahora.strftime('%Y%m%d_%H%M%S')
    destino = {False: os.path.join(L.PROCESADO, carga_id), True: os.path.join(L.PROCESADO, f'REF_{carga_id}')}
    detalle = []
    for x in items:
        src = os.path.join(L.ENTRADA, x)
        es_ref = x.upper().startswith('REF_')
        if os.path.isdir(src):
            dst = os.path.join(destino[es_ref], x)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.*', '~$*', '__MACOSX'), dirs_exist_ok=True)
            n = sum(len(fs) for _, _, fs in os.walk(dst))
            detalle.append(dict(recibido=x, tipo='Carpeta', referencia=es_ref, archivos=n))
        elif x.lower().endswith('.zip'):
            n = _extraer(src, os.path.join(destino[es_ref], os.path.splitext(x)[0]))
            detalle.append(dict(recibido=x, tipo='Zip', referencia=es_ref, archivos=n))
        elif x.lower().endswith('.xlsx'):
            dst = os.path.join(destino[False], 'sueltos', x)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            detalle.append(dict(recibido=x, tipo='Excel suelto', referencia=False, archivos=1))
        else:
            dst = os.path.join(L.PROCESADO, carga_id, '_no_procesados', x)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            detalle.append(dict(recibido=x, tipo='No es Excel ni zip (no se procesa)', referencia=False, archivos=0))
    for x in items:                                                            # todo copiado: recién ahora se vacía la entrada
        src = os.path.join(L.ENTRADA, x)
        shutil.rmtree(src) if os.path.isdir(src) else os.remove(src)
    hay = {k: os.path.isdir(v) and any(L.es_plantilla(f) for _, _, fs in os.walk(v) for f in fs) for k, v in destino.items()}
    return dict(carga_id=carga_id, carga=destino[False] if hay[False] else None, ref=destino[True] if hay[True] else None,
                detalle=pd.DataFrame(detalle))


def entrega(spark):
    """Checklist de las plantillas esperadas: recibida / pendiente, con su versión vigente y estado."""
    M, _, _ = L.cargar_maestros()
    mp = M['plantillas']
    arc = spark.table(L.tabla('slv_archivos')).toPandas()
    E = mp[['id_plantilla', 'rubro', 'sub_rubro', 'tipo', 'area', 'pais', 'ruta_en_sharepoint']].merge(
        arc[['id_plantilla', 'carga_id', 'archivo', 'ruta_relativa', 'n_versiones', 'estado_archivo', 'lineas', 'lineas_ok']],
        on='id_plantilla', how='left')
    E['entrega'] = E.carga_id.notna().map({True: 'Recibida', False: 'Pendiente'})
    extra = arc[~arc.id_plantilla.isin(mp.id_plantilla)]                      # recibidos que no son del maestro (F14)
    if len(extra):
        E = pd.concat([E, extra.assign(entrega='No reconocida', pais=extra.pais_carpeta)[[c for c in E.columns if c in extra.columns or c in ('entrega', 'pais')]]],
                      ignore_index=True)
    escribir(de_pandas(spark, E.astype(object).where(E.notna(), None)), 'ctl_entrega')
    return E


def exportar_bi(spark, carga_id):
    """Las tablas que lee el Power BI como CSV (UTF-8 con BOM, coma, punto decimal) en un zip de 30_bi/."""
    import io, zipfile
    os.makedirs(L.BI, exist_ok=True)
    ruta = os.path.join(L.BI, f'Ppto27_BI_{carga_id}.zip')
    filas = {}
    with zipfile.ZipFile(ruta, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in TABLAS_BI:
            df = spark.table(L.tabla(f'gld_{n}')).toPandas()
            for c in df.columns:                                               # enteros con nulos: sin ".0"
                if df[c].dtype.kind == 'f' and df[c].dropna().apply(float.is_integer).all() and (c.startswith('id_') or c in
                                                                                                   ('ceco', 'anio', 'mes_num', 'orden_n1', 'orden_n2')):
                    df[c] = df[c].astype('Int64')
            b = df.to_csv(index=False).encode('utf-8-sig')
            zi = zipfile.ZipInfo(f'{n}.csv', datetime.now().timetuple()[:6])
            zi.compress_type, zi.flag_bits, zi.create_system = zipfile.ZIP_DEFLATED, 0x800, 0
            z.writestr(zi, b)
            filas[n] = len(df)
    return ruta, filas


def procesar(spark):
    """Todo el flujo: entrada → bronze → silver → gold → control → BI. Si no hay archivos nuevos, recalcula silver/gold/BI con los
    maestros y alias actuales (sirve después de corregir un alias). Devuelve un dict de resúmenes (pandas)."""
    import time
    t0 = time.time()
    R = {'tiempos': {}}
    rec = recibir()
    R['recepcion'] = rec['detalle'] if rec else pd.DataFrame(columns=['recibido', 'tipo', 'referencia', 'archivos'])
    carga_id = rec['carga_id'] if rec else datetime.now().strftime('%Y%m%d_%H%M%S')
    R['carga_id'] = carga_id
    cargas = []
    if rec and rec['ref']:
        cargas.append((rec['ref'], f'REF_{carga_id}'))
    if rec and rec['carga']:
        cargas.append((rec['carga'], carga_id))
    if not cargas and not existe(spark, 'brz_archivos'):
        raise Exception(f'No hay nada que procesar: sube zips o Excel a {L.ENTRADA} y vuelve a correr.')
    for raiz, cid in cargas:
        t = time.time()
        bronze(spark, raiz, cid)
        R['tiempos'][f'bronze {cid}'] = time.time() - t
    M, _, _ = L.cargar_maestros()
    A = spark.table(L.tabla('brz_archivos')).where(F.col('carga_id').isin([c for _, c in cargas] or ['-'])).toPandas()
    if len(A):
        A['plantilla'] = SV.resolver_ids(A, M['plantillas'])
        A['reconocida'] = A.plantilla.isin(M['plantillas'].id_plantilla)
        R['archivos'] = A[['carga_id', 'ruta_relativa', 'estado', 'reconocida', 'plantilla', 'repetido_de', 'error']].sort_values(['carga_id', 'ruta_relativa'])
    else:
        R['archivos'] = pd.DataFrame(columns=['carga_id', 'ruta_relativa', 'estado', 'reconocida', 'plantilla', 'repetido_de', 'error'])
    for etapa, fn in (('silver', silver), ('gold', gold)):
        t = time.time()
        fn(spark)
        R['tiempos'][etapa] = time.time() - t
    t = time.time()
    R['cuadre'], R['controles'] = control(spark)
    R['tiempos']['control'] = time.time() - t
    E = entrega(spark)
    R['entrega'] = (E[E.entrega != 'No reconocida'].groupby(['rubro', 'entrega']).size().unstack(fill_value=0).reset_index())
    R['pendientes'] = E[E.entrega == 'Pendiente'][['rubro', 'sub_rubro', 'area', 'pais', 'ruta_en_sharepoint']]
    ls = spark.table(L.tabla('slv_lineas'))
    R['lineas'] = ls.groupBy('rubro', 'estado_linea').count().toPandas().pivot(index='rubro', columns='estado_linea', values='count').fillna(0).astype(int).reset_index()
    fl = spark.table(L.tabla('slv_flags'))
    R['a_revisar'] = fl.where(F.col('codigo_flag').isin('F14', 'F17', 'F01', 'F02', 'F03', 'F16')).select('id_plantilla', 'codigo_flag', 'severidad', 'detalle').toPandas()
    R['flags'] = fl.groupBy('severidad', 'codigo_flag').count().orderBy(F.desc('count')).toPandas()
    criticos = R['controles'][(R['controles'].tipo == 'Crítico') & (R['controles'].resultado != 'OK')]
    R['ok'] = criticos.empty
    if R['ok']:
        t = time.time()
        R['bi'], R['bi_filas'] = exportar_bi(spark, carga_id)
        R['tiempos']['exportar BI'] = time.time() - t
    else:
        R['bi'], R['bi_filas'] = None, {}
    R['tiempos']['total'] = time.time() - t0
    return R
