# Databricks notebook source
# Reporte de la carga: controles evaluados sobre el Ppto 2027 + cada error de las plantillas con su celda exacta y año-mes
import re
from functools import reduce
T = L.tabla
EN_TABLAS = spark.sql(f"SELECT MAX(carga_id) AS c FROM {T('slv_archivos')} WHERE carga_id NOT LIKE 'REF%'").first().c
AVISO = '' if spark.sql(f"SELECT COUNT(*) AS n FROM {T('slv_archivos')} WHERE carga_id = '{CARGA}'").first().n else f'(En el desplegable está {CARGA}, pero en las tablas quedó {EN_TABLAS}: el reporte muestra {EN_TABLAS}.)'
CARGA = CARGA if not AVISO else EN_TABLAS
A27 = 'x.id_fecha BETWEEN 20270101 AND 20271231'
patron = lambda c: re.match(r'(fact_\w+)\.(\w+) \S+ (dim_\w+)', c)
clave = lambda col, d: col if col in spark.table(T('gld_' + d)).columns else spark.table(T('gld_' + d)).columns[0]
alcance = lambda f: A27 if 'id_fecha' in spark.table(T('gld_' + f)).columns else 'x.id_plantilla IS NOT NULL'
huerfanas = lambda f, col, d: spark.sql(f"SELECT COUNT(DISTINCT x.{col}) AS n FROM {T('gld_' + f)} x LEFT ANTI JOIN {T('gld_' + d)} y ON x.{col} = y.{clave(col, d)} WHERE x.{col} IS NOT NULL AND {alcance(f)}").first().n
DE_CARGA = f"x.id_plantilla IN (SELECT id_plantilla FROM {T('slv_archivos')} WHERE carga_id = '{CARGA}')"
positivos = lambda: spark.sql(f"SELECT COUNT(*) AS n FROM {T('gld_fact_ppto')} x WHERE x.estado_linea LIKE 'OK%' AND x.monto_origen > 0 AND {A27} AND {DE_CARGA}").first().n
en_2027 = lambda c: ('OK' if huerfanas(*patron(c).groups()) == 0 else 'FALLA') if patron(c) else ('OK' if positivos() == 0 else 'FALLA') if 'positivo' in c else None
C = controles.copy()
C['ppto_2027'] = [r.resultado if r.resultado == 'OK' else (en_2027(r.control) or 'FALLA') for r in C.itertuples()]
C['nota'] = ['' if r.resultado == 'OK' else 'falla solo por datos fuera del Ppto 2027 (real histórico)' if r.ppto_2027 == 'OK' else 'revisar' for r in C.itertuples()]
fallas = C[C.ppto_2027 != 'OK']
historico = C[(C.resultado != 'OK') & (C.ppto_2027 == 'OK')]
MES12 = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Dic']
TXT = {1: 'País', 2: 'Vehículo', 3: 'CeCo', 4: 'Sede', 5: 'Cuenta', 6: 'Nivel 1', 7: 'Nivel 2', 8: 'Nivel 3', 9: 'Nivel 4', 10: 'Proveedor', 11: 'Glosa', 12: 'Comentario', 13: 'Moneda'}
num = lambda ref: reduce(lambda a, ch: a * 26 + ord(ch) - 64, re.match(r'[A-Z]+', ref).group(), 0)
per1 = lambda n: f'Ppto 2027 · {MES12[n - 27]}' if 27 <= n <= 38 else f'Real 2026 · {MES12[n - 14]}' if 14 <= n <= 21 else 'Forecast 2026' if 22 <= n <= 26 else 'Ppto 2027 · total' if n >= 39 else 'Ppto 2027 · ' + TXT.get(n, 'texto')
periodo = lambda c, f: ' · '.join(dict.fromkeys(per1(num(r)) for r in re.findall(r'[A-Z]{1,3}\d+', c or ''))) or ('Ppto 2027 · fila completa' if f == f and f is not None else 'Debajo de la tabla')
q = "SELECT a.archivo, f.fila AS fila_excel, COALESCE(f.celdas, '') AS celda, f.codigo_flag AS flag, f.severidad, d.flag AS que_esta_mal, f.detalle, d.accion AS como_corregir FROM " + T('slv_flags') + " f JOIN " + T('slv_archivos') + " a ON f.id_plantilla = a.id_plantilla LEFT JOIN " + T('gld_dim_flag') + " d ON f.codigo_flag = d.codigo_flag WHERE f.codigo_flag NOT IN ('M10', 'F15', 'T05') AND a.carga_id = '" + CARGA + "' ORDER BY a.archivo, f.fila"
E = spark.sql(q).toPandas()
E['fila_excel'] = E.fila_excel.map(lambda x: '' if x != x or x is None else str(int(x)))
E['ref'] = [f or (re.search(r'enviado fila (\d+)', c).group(1) if re.search(r'enviado fila (\d+)', c) else '') for f, c in zip(E.fila_excel, E.celda)]
cambio = E.flag.isin(['C01', 'C03', 'C04'])
base = set(zip(E[~cambio].archivo, E[~cambio].ref))
unir = cambio & [(a, f) in base for a, f in zip(E.archivo, E.ref)]
juntas = set(zip(E[unir].archivo, E[unir].ref))
E = E[~unir].copy()
E['detalle'] = [str(d or '') + (' · además la línea ya no coincide con la versión enviada' if (a, f) in juntas else '') for d, a, f in zip(E.detalle, E.archivo, E.ref)]
E['severidad'] = E.severidad.replace({'INFO': 'INFO (se corrige solo)'})
E['año · mes'] = [periodo(c, f) for c, f in zip(E.celda, E.fila_excel)]
corto = lambda a: re.sub(r'^Ppto ?27 - | - OFICIAL|\.xlsx$', '', str(a))
E['plantilla'] = E.archivo.map(corto)
E['orden'] = E.severidad.map(lambda x: 0 if x == 'ERROR' else 1 if x == 'ALERTA' else 2)
E = E.sort_values(['orden', 'plantilla', 'fila_excel'])
n_ok = int((C.ppto_2027 == 'OK').sum())
print('=' * 90)
print(f"CARGA {CARGA}  ·  {'PLANTILLAS CON ERRORES' if 'error' in CARGA.lower() else 'PLANTILLAS LIMPIAS' if 'limpia' in CARGA.lower() else ''}")
if AVISO: print(AVISO)
print(f'Controles del Ppto 2027: {n_ok} de {len(C)} OK  ·  Hallazgos en las plantillas: {len(E)} (errores {int((E.severidad == "ERROR").sum())} · alertas {int((E.severidad == "ALERTA").sum())} · se corrigen solos {int(E.severidad.str.startswith("INFO").sum())})')
print('=' * 90)
if len(fallas): print('\nControles con FALLA:'); display(fallas[['control', 'detalle']])
if len(E): print('\nHallazgos: dónde está cada uno y cómo corregirlo'); display(E[['plantilla', 'fila_excel', 'celda', 'año · mes', 'severidad', 'que_esta_mal', 'detalle', 'como_corregir']].rename(columns={'fila_excel': 'fila', 'que_esta_mal': 'qué está mal', 'como_corregir': 'cómo corregir'}))
else: print('\n✔ Las plantillas de esta carga pasaron las 63 reglas de validación sin hallazgos.')
P = spark.sql(f"SELECT p.archivo, x.id_linea, x.id_fecha, x.monto_origen FROM {T('gld_fact_ppto')} x LEFT JOIN {T('gld_dim_plantilla')} p ON x.id_plantilla = p.id_plantilla WHERE x.estado_linea LIKE 'OK%' AND x.monto_origen > 0 AND {A27} AND {DE_CARGA}").toPandas()
if len(P): P['fila'] = P.id_linea.str.split('#').str[-1]; P['celda'] = ['A' + chr(64 + int(str(f)[4:6])) + r for f, r in zip(P.id_fecha, P.fila)]; P['año · mes'] = [per1(26 + int(str(f)[4:6])) for f in P.id_fecha]; P['plantilla'] = P.archivo.map(corto); P['monto_origen'] = P.monto_origen.map(lambda v: f'{v:,.2f}'); print('\nMontos positivos del Ppto 2027 en líneas OK de esta carga:'); display(P[['plantilla', 'fila', 'celda', 'año · mes', 'monto_origen']].astype(str))
if len(fallas): raise Exception(str(len(fallas)) + ' control(es) del Ppto 2027 con FALLA en ' + CARGA + ': ' + '; '.join(fallas.control))
print('\nListo: todos los controles del Ppto 2027 OK. En Power BI: Actualizar.')
