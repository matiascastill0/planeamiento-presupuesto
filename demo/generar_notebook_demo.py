"""Genera 08_demo.ipynb: notebook ADAPTATIVO de la demo. Detecta qué carga está vigente en las tablas para las 3 plantillas
de la demo y muestra solo lo que corresponde a esa carga:
  * carga limpia      → qué se subió, validación sin hallazgos, desglose Dir/Ind, cuadre y tiempo;
  * carga con errores → lo mismo + cada hallazgo con su celda exacta, año-mes y lo que dice el Excel, y la comparación
                         contra la carga limpia del mismo lote.
Se corre igual después de cada carga (Run all). Se adapta a la versión de las tablas (metodología Nueva, solo Ppto 2027,
reparto de la cuarentena) y verifica con los datos qué componentes forman la base de reparto.
Uso: python3 generar_notebook_demo.py   ·   --probar <volume_local> [--simular] [--nueva]  ejecuta en Spark local
     contra la foto de las tablas tras cada carga (_warehouse_<carga>)
"""
import json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
WF = os.path.dirname(AQUI)
SALIDA = os.path.join(WF, '08_demo.ipynb')

CELDAS = [
('md', r"""# 08 · Demo Ppto27: de la plantilla al reparto Directo / Indirecto

- El notebook **detecta solo qué carga está subida** y muestra su desglose completo.
- Lee el **Excel original** del área y lo compara contra las tablas finales de Databricks.
- Explica la **metodología de indirectos** con los números reales de Perú.
- **Uso:** correr `99_ejecutar_todo` con la carga y luego este notebook completo."""),

('code', "%pip install openpyxl --quiet"),

('md', r"""### Configuración
- Se adapta sola a las tablas: metodología vigente, solo Ppto 2027.
- Identifica la carga que está en las tablas para las 3 plantillas de la demo."""),

('code', r"""import sys, os, re, json
sys.path.append('/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27/00_codigo')
import pandas as pd
import openpyxl
from openpyxl.utils import range_boundaries
import ppto27_lib as L

CAT = 'catalogo_ppto.esquema_ppto'


def T(n):
    return f'{CAT}.ppto27_gld_{n}'


def S(n):
    return f'{CAT}.ppto27_slv_{n}'


def B(n):
    return f'{CAT}.ppto27_brz_{n}'


VOL = getattr(L, 'VOLUME', '/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27')
TIEMPOS = f'{VOL}/40_tiempos'
pd.set_option('display.float_format', '{:,.2f}'.format)
PAIS, MES = 'Perú', 20270101          # país y mes para explicar la metodología

GA = '03. Gastos Administrativos/'
PLANTILLAS = {
  1: dict(rel=GA + 'UDN/MDK/01. PERU/Ppto27 - MDK Peru - OFICIAL.xlsx', corto='MDK Perú',
          tipo='Imputación directa', destino='100 % a MDK', permitidos={1}, debe={1}),
  2: dict(rel=GA + 'STAFF/Staff - Riesgos/01. PERU/Ppto27 - Staff - Riesgo Peru - OFICIAL.xlsx', corto='Staff Riesgos Perú',
          tipo='Soporte directo', destino='UdN por driver; lo no asignado a la bolsa', permitidos={2, 3, 4}, debe={2}),
  3: dict(rel=GA + 'STAFF/Staff - Finanzas/01. PERU/Ppto27 - Staff - Finanzas - Peru.xlsx', corto='Staff Finanzas Perú',
          tipo='100 % indirecto', destino='bolsa de Perú, con el peso de cada UdN', permitidos={3}, debe={3}),
}
for d in PLANTILLAS.values():
    d['idp'] = L.identificar(d['rel'])['id_plantilla']

COLS_DI = spark.table(T('fact_gestion_dirind')).columns
MET = " AND g.metodologia = 'Nueva'" if 'metodologia' in COLS_DI else ''
AN27 = ' AND g.id_fecha BETWEEN 20270101 AND 20271231'
TODAS = 'estado_linea' in COLS_DI and spark.sql(f'''
  SELECT COUNT(*) AS n FROM {T('fact_gestion_dirind')} g
  WHERE g.estado_linea = 'Cuarentena' {MET} {AN27}''').first().n > 0
COMP = {r.id_componente: r.componente for r in spark.table(T('dim_componente')).collect()}

ids = "', '".join(d['idp'] for d in PLANTILLAS.values())
vig = {r.id_plantilla: r.carga_id for r in spark.sql(
    f"SELECT id_plantilla, MAX(carga_id) AS carga_id FROM {S('archivos')} WHERE id_plantilla IN ('{ids}') GROUP BY 1").collect()}
CARGA = max(vig.values()) if vig else None
ERRORES = bool(CARGA) and 'error' in CARGA.lower()
LIMPIA = f'{CARGA[:8]}_0800_Demo_Limpias' if ERRORES else None
TIPO = 'Plantillas con errores' if ERRORES else 'Plantillas limpias'
MODO = '__MODO__'
if MODO != 'auto' and (MODO == 'limpias') == ERRORES:
    raise Exception(f"Este notebook es para la carga {'limpia' if MODO == 'limpias' else 'con errores'}, pero en las tablas está {CARGA}. "
                    f"Primero correr 99_ejecutar_todo con la carga ..._{'Demo_Limpias' if MODO == 'limpias' else 'Demo_Con_errores'}.")
print('metodología:', 'Nueva' if MET else '(única)', '| Dir/Ind reparte:', 'todas las líneas' if TODAS else 'OK + OK con alerta')
print(f'CARGA EN LAS TABLAS: {CARGA}  ·  {TIPO}')
if len(set(vig.values())) > 1:
    print('⚠ Las 3 plantillas no están en la misma carga:', vig)"""),

('code', r"""MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Dic']
TEXTOS = {1: 'País', 2: 'Vehículo', 3: 'CeCo', 4: 'Sede', 5: 'Cuenta', 6: 'Nivel 1', 7: 'Nivel 2', 8: 'Nivel 3',
          9: 'Nivel 4', 10: 'Proveedor', 11: 'Glosa', 12: 'Comentario', 13: 'Moneda'}
RES, RESUMEN = {}, {}


def ver(df):
    # muestra la tabla con montos legibles: separador de miles y 2 decimales
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].map(lambda x: '' if pd.isna(x) else f'{x:,.2f}')
    display(df)


def seleccion():
    try:
        return dbutils.widgets.get('plantilla')
    except Exception:
        return 'Las 3'


def nota(*lineas):
    print('\n'.join('  • ' + x for x in lineas) + '\n')


EXPLICA = {
  'archivos': (['Se subió la versión limpia de las 3 plantillas, tal como sale de SharePoint.',
                'Cada archivo representa un tipo de gasto distinto: imputación directa, soporte directo y 100 % indirecto.'],
               ['El área reenvió sus 3 plantillas, esta vez con errores típicos de llenado.',
                'La versión nueva reemplaza a la limpia; la anterior queda en el historial.']),
  'validacion': (['63 reglas revisan cada celda de las 3 plantillas: textos, montos, fórmulas y cambios contra lo enviado.',
                  'Resultado esperado: ningún hallazgo; todo entra al BI.'],
                 ['Cada hallazgo indica archivo, fila y celda exacta, y lo que está escrito ahí: se puede abrir el Excel y verlo.',
                  'ERROR → la línea va a cuarentena · ALERTA → entra al BI y se revisa · INFO → se corrige solo.']),
  'desglose': (['Para cada plantilla: Excel = Databricks al céntimo, a dónde va cada sol y contable = gestión.',
                'Si hay indirecto, se comprueba que se reparte con el mismo peso que toda la bolsa del país.'],
               ['Aun con errores, el total del Excel sigue cuadrando con Databricks: nada se pierde.',
                'Lo grave queda en cuarentena (fuera del BI, dentro del cuadre); al final, la comparación contra la versión limpia.']),
  'tiempos': (['Tiempo real de la corrida en Databricks, etapa por etapa.', 'Comparación con el proceso del Ppto 2026.'],
              ['Tiempo de la corrida con errores frente a la limpia: el proceso no se demora más por encontrar errores.',
               'Comparación con el proceso del Ppto 2026.']),
}


def explicar(seccion):
    nota(*EXPLICA[seccion][1 if ERRORES else 0])


def q(sql):
    return spark.sql(sql).toPandas()


def ruta(carga, n):
    return f"{L.CARGAS}/{carga}/{PLANTILLAS[n]['rel']}"


def origen(path):
    # suma Ene-Dic 27 del Excel, solo dentro de Tabla1 (lo que el área presupuestó)
    ws = openpyxl.load_workbook(path, data_only=True)['Ppto27']
    t = ws.tables['Tabla1']
    c1, r0, c2, r1 = range_boundaries(t.ref)
    r1 -= t.totalsRowCount or 0
    tot = 0.0
    for fila in ws.iter_rows(min_row=r0 + 1, max_row=r1, min_col=27, max_col=38, values_only=True):
        for v in fila:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                tot += v
            elif isinstance(v, str) and re.fullmatch(r'-?[\d,]+(\.\d+)?', v.strip()):
                tot += float(v.strip().replace(',', ''))
    return tot


def valor_celda(path, celdas):
    # lo que hay escrito en la(s) celda(s) marcada(s), leído del propio Excel
    ws = openpyxl.load_workbook(path)['Ppto27']
    out = []
    for ref in re.findall(r'[A-Z]{1,3}\d+', celdas or '')[:2]:
        v = ws[ref].value
        out.append(f'{ref} = ' + ('(vacía)' if v is None else repr(v)))
    return ' · '.join(out)


def periodo(celdas, fila):
    # a qué año-mes o columna corresponde cada celda: N-U Real 2026, V-Z Forecast 2026, AA-AL Ppto 2027, A-M textos
    out = []
    for ref in re.findall(r'[A-Z]{1,3}\d+', celdas or ''):
        n = 0
        for ch in re.match(r'[A-Z]+', ref).group():
            n = n * 26 + ord(ch) - 64
        p = (f'Ppto 2027 · {MESES[n - 27]}' if 27 <= n <= 38 else f'Real 2026 · {MESES[n - 14]}' if 14 <= n <= 21
             else 'Forecast 2026' if 22 <= n <= 26 else 'Ppto 2027 · total' if n >= 39 else 'Ppto 2027 · ' + TEXTOS.get(n, 'texto'))
        if p not in out:
            out.append(p)
    return ' · '.join(out[:3]) or ('Ppto 2027 · fila completa' if fila != '' else 'Debajo de la tabla')


def hallazgos(idps, carga):
    # errores y alertas de las plantillas, con celda, año-mes y lo que dice el Excel; el aviso C03 (texto cambiado contra
    # la versión enviada) se une al hallazgo de su misma fila
    lst = "', '".join(idps)
    cf = spark.table(T('dim_flag')).columns
    acc = 'd.accion' if 'accion' in cf else "''"
    fl = q(f'''SELECT a.archivo, f.id_plantilla, f.fila, f.celdas, f.codigo_flag AS flag, f.severidad,
                      d.flag AS que_esta_mal, f.detalle, {acc} AS como_corregir
               FROM {S('flags')} f JOIN {S('archivos')} a ON f.id_plantilla = a.id_plantilla
               LEFT JOIN {T('dim_flag')} d ON f.codigo_flag = d.codigo_flag
               WHERE f.id_plantilla IN ('{lst}') AND f.codigo_flag NOT IN ('M10', 'F15', 'T05') ''')
    fl['celdas'] = fl.celdas.fillna('')
    fl['fila'] = fl.fila.map(lambda x: '' if pd.isna(x) else str(int(x)))
    # los avisos de cambio contra la versión enviada (C01, C03, C04) se unen al hallazgo de su misma fila
    fl['fila_ref'] = [f or (re.search(r'enviado fila (\d+)', c).group(1) if re.search(r'enviado fila (\d+)', c) else '')
                      for f, c in zip(fl.fila, fl.celdas)]
    cambio = fl.flag.isin(['C01', 'C03', 'C04'])
    base = set(zip(fl[~cambio].id_plantilla, fl[~cambio].fila_ref))
    unir = cambio & [(i, f) in base for i, f in zip(fl.id_plantilla, fl.fila_ref)]
    nota = set(zip(fl[unir].id_plantilla, fl[unir].fila_ref))
    fl = fl[~unir].copy()
    fl['detalle'] = [d + (' · además la línea ya no coincide con la versión enviada' if (i, f) in nota else '')
                     for d, i, f in zip(fl.detalle.fillna(''), fl.id_plantilla, fl.fila_ref)]
    rutas = {d['idp']: ruta(carga, n) for n, d in PLANTILLAS.items()}
    fl['año · mes'] = [periodo(c, f) for c, f in zip(fl.celdas, fl.fila)]
    fl['en el Excel'] = [valor_celda(rutas[i], c) if c else '' for i, c in zip(fl.id_plantilla, fl.celdas)]
    fl['orden'] = fl.severidad.map({'BLOQUEANTE': 0, 'ERROR': 1, 'ALERTA': 2}).fillna(3)
    fl['severidad'] = fl.severidad.replace({'INFO': 'INFO (se corrige solo)'})
    return fl.sort_values(['archivo', 'orden', 'fila']).rename(columns={'celdas': 'celda'})


def tiempo(carga):
    try:
        with open(f'{TIEMPOS}/{carga}.json') as f:
            return json.load(f)
    except Exception:
        return None


def guardar(clave, dato):
    try:
        os.makedirs(TIEMPOS, exist_ok=True)
        with open(f'{TIEMPOS}/resumen_{clave}.json', 'w') as f:
            json.dump(dato, f)
    except Exception:
        pass


def leer(clave):
    try:
        with open(f'{TIEMPOS}/resumen_{clave}.json') as f:
            return json.load(f)
    except Exception:
        return None


def archivos():
    a = spark.table(B('archivos')).where(f"carga_id = '{CARGA}' AND id_plantilla IN ('{ids}')").toPandas()
    prev = q(f'''SELECT id_plantilla, MAX(carga_id) AS reemplaza_a FROM {B('archivos')}
                 WHERE id_plantilla IN ('{ids}') AND carga_id < '{CARGA}' GROUP BY 1''')
    a = a.merge(prev, on='id_plantilla', how='left')
    tipo = {d['idp']: d['tipo'] for d in PLANTILLAS.values()}
    out = pd.DataFrame({'archivo': a.archivo, 'tipo de gasto': a.id_plantilla.map(tipo),
                        'carpeta': a.ruta_relativa.str.rsplit('/', n=1).str[0]})
    if 'tamano_bytes' in a:
        out['tamaño KB'] = (a.tamano_bytes / 1024).round(0)
    if 'n_lineas' in a:
        out['líneas leídas'] = a.n_lineas
    if 'estado' in a:
        out['lectura'] = a.estado
    if ERRORES:
        out['reemplaza a la carga'] = a.reemplaza_a.fillna('(primera versión)')
    print(f'CARGA {CARGA} · {TIPO} · {len(out)} archivo(s) subido(s)')
    ver(out.sort_values('archivo'))


def reporte():
    fl = hallazgos([d['idp'] for d in PLANTILLAS.values()], CARGA)
    est = pd.DataFrame([dict(plantilla=d['corto'], tipo=d['tipo'],
                             errores=int(((fl.id_plantilla == d['idp']) & (fl.severidad == 'ERROR')).sum()),
                             alertas=int(((fl.id_plantilla == d['idp']) & (fl.severidad == 'ALERTA')).sum()),
                             correcciones=int(((fl.id_plantilla == d['idp']) & fl.severidad.str.startswith('INFO')).sum()))
                        for d in PLANTILLAS.values()])
    est['estado'] = ['CON ERRORES' if e else 'CON ALERTAS' if a else 'CORREGIDA SOLA' if c else 'LIMPIA'
                     for e, a, c in zip(est.errores, est.alertas, est.correcciones)]
    if not ERRORES:
        est['hallazgos'] = est.errores + est.alertas + est.correcciones
        print(f'CARGA {CARGA} · hallazgos: {int(est.hallazgos.sum())}')
        ver(est[['plantilla', 'tipo', 'hallazgos', 'estado']])
    else:
        print(f'CARGA {CARGA} · errores: {int(est.errores.sum())} · alertas: {int(est.alertas.sum())}'
              f' · correcciones automáticas: {int(est.correcciones.sum())}')
        ver(est)
    if len(fl):
        print('\nCada hallazgo con su archivo, fila, celda exacta, el año-mes al que afecta y lo que dice el Excel:')
        ver(fl[['archivo', 'fila', 'celda', 'año · mes', 'severidad', 'flag', 'que_esta_mal', 'en el Excel', 'como_corregir']])
    else:
        print('✔ Las 3 plantillas pasaron las 63 reglas de validación sin hallazgos.')


def demo(n):
    d = PLANTILLAS[n]
    idp, path = d['idp'], ruta(CARGA, n)
    print(f"PLANTILLA {n} · {d['corto']} · {d['tipo']} → {d['destino']}\n{idp} · carga {CARGA}\n")
    chk = {}

    # 1) Excel de origen vs Databricks
    exc = origen(path)
    est = q(f'''SELECT estado_linea AS estado, COUNT(DISTINCT id_linea) AS lineas,
          ROUND(SUM(monto_origen), 2) AS monto_origen, ROUND(SUM(monto_pen), 2) AS monto_pen
        FROM {T('fact_ppto')} g WHERE id_plantilla = '{idp}' {AN27}
        GROUP BY estado_linea ORDER BY estado_linea''')
    gold = float(est.monto_origen.sum())
    dif = round(exc - gold, 2) + 0.0
    chk['Excel = Databricks'] = abs(dif) < 0.01
    print(f'1) Excel {exc:,.2f} | Databricks {gold:,.2f} | diferencia {dif:,.2f}')
    ver(est)

    # 2) validación
    fl = hallazgos([idp], CARGA)
    info = int(q(f"SELECT COUNT(*) AS n FROM {S('flags')} WHERE id_plantilla = '{idp}' AND codigo_flag IN ('M10', 'F15', 'T05')").n[0])
    if len(fl) == 0:
        chk['Validación sin hallazgos'] = True
        print(f'\n2) validación: sin hallazgos · {info} avisos informativos (ej. Real 2026 positivo que ya venía del contable)')
    else:
        chk['Cada hallazgo con su ubicación exacta'] = bool(((fl.celda != '') | (fl.fila != '')).all())
        print(f"\n2) validación: {int((fl.severidad == 'ERROR').sum())} error(es) · {int((fl.severidad == 'ALERTA').sum())} alerta(s)"
              f" · {int(fl.severidad.str.startswith('INFO').sum())} corrección(es) automática(s)")
        ver(fl[['fila', 'celda', 'año · mes', 'severidad', 'flag', 'que_esta_mal', 'en el Excel', 'detalle']])

    # 3) cuarentena
    cu = q(f'''SELECT id_linea, MAX(flags) AS flags, ROUND(SUM(monto_origen), 2) AS monto_origen
        FROM {T('fact_ppto')} g WHERE id_plantilla = '{idp}' {AN27} AND estado_linea = 'Cuarentena'
        GROUP BY id_linea ORDER BY id_linea''')
    if len(cu):
        print(f'\n3) líneas en cuarentena: {len(cu)} (fuera del BI hasta que el área corrija; siguen en el cuadre)')
        ver(cu)
    else:
        print(f"\n3) cuarentena: ninguna línea · las {int(est.lineas.sum())} líneas entran al BI")

    # 4) Dir/Ind por componente y UdN
    di = q(f'''SELECT g.id_componente AS comp, c.componente, g.id_udn AS udn, ROUND(SUM(g.monto_pen), 2) AS monto_pen
        FROM {T('fact_gestion_dirind')} g JOIN {T('dim_componente')} c USING (id_componente)
        WHERE g.id_plantilla = '{idp}' {MET} {AN27} GROUP BY 1, 2, 3 ORDER BY 1, 4''')
    tot = float(q(f'''SELECT COALESCE(SUM(monto_pen), 0) AS t FROM {T('fact_gestion_dirind')} g
        WHERE g.id_plantilla = '{idp}' {MET} {AN27}''').t[0])
    di['% de la plantilla'] = 100 * di.monto_pen / tot if tot else 0.0
    comps = set(di.comp)
    chk['Componente correcto'] = comps <= d['permitidos'] and d['debe'] <= comps
    print('\n4) a dónde va el gasto (Dir/Ind, PEN, año 2027)')
    ver(di)

    # 5) cuadre contable = Dir/Ind
    filtro = '' if TODAS else " AND estado_linea IN ('OK', 'OK con alerta')"
    cont = float(q(f'''SELECT COALESCE(SUM(monto_pen), 0) AS c FROM {T('fact_ppto')} g
        WHERE id_plantilla = '{idp}' {AN27} {filtro}''').c[0])
    dif2 = round(cont - tot, 2) + 0.0
    chk['Contable = Dir/Ind'] = abs(dif2) < 0.01
    print(f"\n5) contable ({'todas las líneas' if TODAS else 'OK'}) {cont:,.2f} | Dir/Ind {tot:,.2f} | diferencia {dif2:,.2f}")

    # 6) la parte indirecta se reparte con los mismos % que la bolsa del país, mes a mes
    if 3 in comps:
        r = q(f'''WITH p AS (SELECT id_fecha, id_udn, SUM(monto_pen) AS m FROM {T('fact_gestion_dirind')} g
                    WHERE id_plantilla = '{idp}' AND id_componente = 3 {MET} {AN27} GROUP BY 1, 2),
               b AS (SELECT id_fecha, id_udn, SUM(monto_pen) AS m FROM {T('fact_gestion_dirind')} g
                    WHERE id_pais = 'Perú' AND id_componente = 3 {MET} {AN27} GROUP BY 1, 2),
               s AS (SELECT b.id_fecha, b.id_udn, p.m / SUM(p.m) OVER (PARTITION BY p.id_fecha) AS pct_plantilla,
                            b.m / SUM(b.m) OVER (PARTITION BY b.id_fecha) AS pct_bolsa
                     FROM b LEFT JOIN p USING (id_fecha, id_udn))
             SELECT id_udn, ROUND(100 * AVG(pct_plantilla), 4) AS pct_plantilla, ROUND(100 * AVG(pct_bolsa), 4) AS pct_bolsa_pais,
                    ROUND(100 * MAX(ABS(COALESCE(pct_plantilla, 0) - pct_bolsa)), 6) AS dif_max_pp
             FROM s GROUP BY id_udn ORDER BY pct_bolsa_pais DESC''')
        chk['Indirecto repartido como la bolsa'] = float(r.dif_max_pp.max()) < 0.0001
        print('\n6) la parte indirecta se reparte con los mismos % que la bolsa de Perú, mes a mes'
              ' (promedio de 12 meses; dif_max_pp = el peor mes)')
        ver(r)

    v = pd.DataFrame([(k, 'OK' if x else 'REVISAR') for k, x in chk.items()], columns=['control', 'resultado'])
    v.insert(0, '#', range(1, len(v) + 1))
    RES[n] = v.assign(plantilla=d['corto'])
    lin = dict(zip(est.estado, est.lineas))
    RESUMEN[n] = dict(excel=round(exc, 2), lineas_ok=int(lin.get('OK', 0)), lineas_alerta=int(lin.get('OK con alerta', 0)),
                      lineas_cuarentena=int(lin.get('Cuarentena', 0)), hallazgos=int(len(fl)),
                      monto_bi=round(float(est[est.estado != 'Cuarentena'].monto_origen.sum()), 2),
                      monto_cuarentena=round(float(est[est.estado == 'Cuarentena'].monto_origen.sum()), 2))
    guardar(f'{CARGA}_{n}', RESUMEN[n])
    print(f"\nVEREDICTO {d['corto']}:", 'OK' if v.resultado.eq('OK').all() else 'REVISAR')
    ver(v[['#', 'control', 'resultado']])
    if ERRORES:
        comparar(n)


def comparar(n):
    a = leer(f'{LIMPIA}_{n}')
    b = RESUMEN[n]
    if not a:
        try:
            a = dict(excel=round(origen(ruta(LIMPIA, n)), 2))
        except Exception:
            print(f'\n(no hay datos de la carga limpia {LIMPIA} para comparar)')
            return
    nombres = {'excel': 'Ppto 2027 en el Excel', 'lineas_ok': 'Líneas OK', 'lineas_alerta': 'Líneas OK con alerta',
               'lineas_cuarentena': 'Líneas en cuarentena', 'hallazgos': 'Hallazgos',
               'monto_bi': 'Monto que entra al BI', 'monto_cuarentena': 'Monto en cuarentena'}
    fmt = lambda v: '-' if v is None or v == '-' else f'{v:,.2f}' if isinstance(v, float) else f'{v:,}'
    c = pd.DataFrame([(nombres[k], fmt(a.get(k, '-')), fmt(b[k])) for k in nombres], columns=['', 'versión limpia', 'versión con errores'])
    print(f'\nComparación contra la versión limpia ({LIMPIA})')
    ver(c)"""),

('md', "---\n## 1 · ¿Qué se subió?"),
('code', "explicar('archivos')\narchivos()"),

('md', r"""---
## 2 · Metodología de indirectos, con los números reales
- **Directo** de cada UdN = imputación directa + soporte directo.
- **Bolsa** = lo que sobró del soporte directo + áreas 100 % indirectas.
- **Peso** = directo de la UdN ÷ directo del país, en ese mes · **Indirecto** = peso × bolsa.
- Todo sale de las tablas finales (`PAIS`, `MES` en la configuración)."""),

('code', r"""# 1.a ¿Qué componentes usa la base de reparto? Se prueba con los datos de los 12 meses, no se supone
base = q(f'''SELECT g.id_fecha, g.id_udn, g.id_componente AS comp, SUM(g.monto_pen) AS m
  FROM {T('fact_gestion_dirind')} g WHERE g.id_pais = '{PAIS}' {MET} {AN27} GROUP BY 1, 2, 3''')
base = base[base.id_udn != 'Sin base de reparto']
piv = base.pivot_table(index=['id_fecha', 'id_udn'], columns='comp', values='m', aggfunc='sum', fill_value=0.0)
for c in (1, 2, 3, 4):
    if c not in piv:
        piv[c] = 0.0


def error_base(comps):
    b = piv[list(comps)].sum(axis=1)
    peso = b / b.groupby(level=0).transform('sum')
    bolsa = piv[3].groupby(level=0).transform('sum')
    return float((peso * bolsa - piv[3]).abs().max())


candidatas = [(1, 2), (1, 2, 4), (1,)]
errores = {c: error_base(c) for c in candidatas}
BASE = min(errores, key=errores.get)
print('Componentes en la base de reparto:', ' + '.join(COMP.get(c, str(c)) for c in BASE),
      f'· diferencia máxima en los 12 meses: {errores[BASE]:,.6f} PEN')
ver(pd.DataFrame([(' + '.join(map(str, c)), e) for c, e in errores.items()], columns=['base probada', 'diferencia máx. (PEN)']))"""),

('code', r"""# 1.b Directo y peso de cada UdN en el mes
m = piv.loc[MES].copy()
m['directo'] = m[list(BASE)].sum(axis=1)
m['peso %'] = 100 * m.directo / m.directo.sum()
t1 = m[[1, 2, 'directo', 'peso %']].rename(columns={1: 'imputación directa', 2: 'soporte directo'})
t1 = t1.sort_values('directo')
t1.loc['TOTAL'] = t1.sum()
print(f'{PAIS} · {MES}: directo de cada UdN y su peso')
ver(t1.reset_index().rename(columns={'id_udn': 'UdN'}))"""),

('code', r"""# 1.c Cómo se forma la bolsa: sobrante del soporte directo + áreas 100 % indirectas
bol = q(f'''WITH sop AS (SELECT DISTINCT concat(pais, '|', CAST(ceco AS STRING)) AS id_ceco
                        FROM {T('dim_driver')} WHERE componente = 'Soporte directo')
  SELECT CASE WHEN s.id_ceco IS NOT NULL THEN 'Sobrante del soporte directo'
              ELSE 'Áreas 100 % indirectas' END AS origen,
         ce.ceco_nombre, SUM(g.monto_pen) AS monto
  FROM {T('fact_gestion_dirind')} g
  LEFT JOIN sop s ON g.id_ceco_origen = s.id_ceco
  LEFT JOIN {T('dim_ceco')} ce ON g.id_ceco_origen = ce.id_ceco
  WHERE g.id_pais = '{PAIS}' AND g.id_fecha = {MES} AND g.id_componente = 3 {MET}
  GROUP BY 1, 2''')
res = bol.groupby('origen').monto.sum().to_frame('monto')
res['% de la bolsa'] = 100 * res.monto / res.monto.sum()
res.loc['BOLSA TOTAL'] = [res.monto.sum(), 100.0]
print(f'{PAIS} · {MES}: de dónde sale la bolsa de indirectos')
ver(res.reset_index())
for o, g in bol.groupby('origen'):
    print(f'\nTop 5 · {o}')
    ver(g.nsmallest(5, 'monto')[['ceco_nombre', 'monto']])"""),

('code', r"""# 1.d Peso × bolsa = indirecto de cada UdN (lo que está en la tabla final)
bolsa = float(piv.loc[MES][3].sum())
t2 = pd.DataFrame({'peso %': m['peso %'], 'bolsa': bolsa})
t2['peso × bolsa'] = t2['peso %'] / 100 * bolsa
t2['indirecto en la tabla'] = m[3]
t2['diferencia'] = (t2['peso × bolsa'] - t2['indirecto en la tabla']).round(2) + 0.0
t2 = t2.sort_values('peso × bolsa')
print(f'{PAIS} · {MES}: bolsa {bolsa:,.2f} repartida con el peso de cada UdN')
ver(t2.reset_index().rename(columns={'id_udn': 'UdN'}))
print('OK: cada UdN recibe exactamente su peso × bolsa' if t2.diferencia.abs().max() < 0.01 else 'REVISAR')"""),

('code', r"""# 1.e Cuadre del país: el reparto no crea ni borra gasto
filtro = '' if TODAS else " AND estado_linea IN ('OK', 'OK con alerta')"
cont = float(q(f'''SELECT SUM(monto_pen) AS c FROM {T('fact_ppto')} g
  WHERE g.id_pais = '{PAIS}' AND g.id_fecha = {MES} {filtro}''').c[0])
comp = q(f'''SELECT g.id_componente AS comp, SUM(g.monto_pen) AS monto FROM {T('fact_gestion_dirind')} g
  WHERE g.id_pais = '{PAIS}' AND g.id_fecha = {MES} {MET} GROUP BY 1 ORDER BY 1''')
comp['componente'] = comp.comp.map(COMP)
ver(comp[['comp', 'componente', 'monto']])
print(f'Contable {cont:,.2f} | Directo + Indirecto {comp.monto.sum():,.2f} | diferencia {cont - comp.monto.sum():,.2f}')"""),

('code', r"""# 1.f Los 12 meses: el resultado no es volátil
# Cada mes la diferencia peso × bolsa vs tabla es 0, y el peso de una UdN solo cambia si cambia su gasto directo
b = piv[list(BASE)].sum(axis=1)
peso = b / b.groupby(level=0).transform('sum')
bol12 = piv[3].groupby(level=0).sum()
dif12 = (peso * piv[3].groupby(level=0).transform('sum') - piv[3]).abs().groupby(level=0).max()
meses = pd.DataFrame({'directo del país': b.groupby(level=0).sum(), 'bolsa': bol12, 'dif. máx. (PEN)': dif12.round(4)})
ver(meses.reset_index().rename(columns={'id_fecha': 'mes'}))
p = (100 * peso).unstack(level=1)
estab = pd.DataFrame({'peso mín %': p.min(), 'peso máx %': p.max(), 'peso prom %': p.mean(),
                      'indirecto año': piv[3].groupby(level=1).sum()}).sort_values('indirecto año')
ver(estab.reset_index().rename(columns={'id_udn': 'UdN'}))
print('OK: los 12 meses cuadran al céntimo' if dif12.max() < 0.01 else 'REVISAR')"""),


('md', "---\n## 3 · Resultado de la validación"),
('code', "explicar('validacion')\nreporte()"),

('md', "---\n## 4 · Desglose por plantilla"),
('code', "explicar('desglose')"),
('code', "demo(1)"),
('code', "demo(2)"),
('code', "demo(3)"),

('md', "---\n## 5 · Tiempos"),

('code', r"""explicar('tiempos')
etapas = ['bronze', 'silver', 'gold', 'control']
t = tiempo(CARGA)
if not t:
    print('Sin tiempo guardado para esta carga: agregar la línea de tiempos al 99_ejecutar_todo y volver a correrla.')
else:
    tt = pd.DataFrame({f'{CARGA} (s)': [t[k] for k in etapas]}, index=etapas)
    tl = tiempo(LIMPIA) if ERRORES else None
    if tl:
        tt.insert(0, f'{LIMPIA} (s)', [tl[k] for k in etapas])
    tt.loc['TOTAL'] = tt.sum()
    ver(tt.reset_index().rename(columns={'index': 'etapa'}))
    total = sum(t[k] for k in etapas) / 60
    n = int(q(f"SELECT COUNT(*) AS n FROM {T('dim_plantilla')}").n[0])
    ver(pd.DataFrame([
        ('Subir 1 plantilla', '~10 min (TI ~45 min) con ejecutable SQL', 'se copia la carpeta; entra en la corrida'),
        (f'Consolidar las {n} plantillas', 'muchas horas, una por una', f'{total:.1f} min en una corrida'),
        ('Validar cada celda', 'revisión manual', '63 reglas automáticas, con celda exacta'),
        ('Reparto Dir/Ind', 'cálculo aparte en Excel', 'mensual por país, verificado al céntimo'),
    ], columns=['', 'antes (Ppto 2026)', 'ahora (Ppto 2027)']))"""),

('md', "---\n## Resumen para la gerencia"),
('code', r"""fila = []
for n, d in PLANTILLAS.items():
    r, v = RESUMEN.get(n), RES.get(n)
    if r is None:
        continue
    fila.append(dict(plantilla=d['corto'], tipo=d['tipo'], **{'Ppto 2027 (Excel)': r['excel'], 'entra al BI': r['monto_bi'],
                'en cuarentena': r['monto_cuarentena'], 'hallazgos': r['hallazgos'],
                'veredicto': 'OK' if v is not None and v.resultado.eq('OK').all() else 'REVISAR'}))
print(f'CARGA {CARGA} · {TIPO}')
ver(pd.DataFrame(fila))"""),
]


def celda(tipo, txt):
    src = txt.splitlines(True)
    if tipo == 'md':
        return {'cell_type': 'markdown', 'metadata': {}, 'source': src}
    return {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': src}


TITULO = {
  'auto': ('08_demo', None),
  'limpias': ('08a_demo_limpias', r"""# 08a · Demo Ppto27 · Plantillas limpias

- Muestra la carga limpia: qué se subió, cómo se reparte el gasto y la prueba de que todo cuadra al céntimo.
- Lee el **Excel original** del área y lo compara contra las tablas finales de Databricks.
- **Uso:** correr `99_ejecutar_todo` con la carga `…_Demo_Limpias` y luego este notebook completo (Run all)."""),
  'errores': ('08b_demo_errores', r"""# 08b · Demo Ppto27 · Plantillas con errores

- Muestra la carga con errores: cada hallazgo con su celda exacta, lo que dice el Excel, lo retenido y la comparación contra la versión limpia.
- Lee el **Excel original** del área y lo compara contra las tablas finales de Databricks.
- **Uso:** correr `99_ejecutar_todo` con la carga `…_Demo_Con_errores` y luego este notebook completo (Run all)."""),
}


SELECTOR = r"""
# selector opcional (arriba del notebook): 'Las 3' por defecto
try:
    dbutils.widgets.dropdown('plantilla', 'Las 3', ['Las 3'] + [d['corto'] for d in PLANTILLAS.values()], 'Plantilla a mostrar')
except Exception:
    pass"""


def celdas(modo):
    out, saltar = [], False
    for t, s in CELDAS:
        if modo == 'limpias' and t == 'code' and s.startswith('import sys, os, re, json'):
            s = s + '\n' + SELECTOR
        if modo == 'limpias' and t == 'code' and s in ('demo(1)', 'demo(2)', 'demo(3)'):
            n = s[5]
            s = (f"# muestra la plantilla {n}, salvo que en el selector se haya elegido otra\n"
                 f"if seleccion() in ('Las 3', PLANTILLAS[{n}]['corto']):\n    demo({n})\n"
                 f"else:\n    print(f\"{{PLANTILLAS[{n}]['corto']}}: no seleccionada (selector 'Plantilla a mostrar', arriba)\")")
        if t == 'md' and s.startswith('# 08') and TITULO[modo][1]:
            s = TITULO[modo][1]
        if modo == 'errores' and t == 'md' and '## 2 · Metodología' in s:
            saltar = True                                   # la demo de errores no presenta la metodología
            continue
        if saltar and t == 'code' and s.startswith('# 1.'):
            continue
        saltar = False if t == 'md' else saltar
        if modo == 'errores':
            s = s.replace('## 3 · Resultado', '## 2 · Resultado').replace('## 4 · Desglose', '## 3 · Desglose').replace('## 5 · Tiempos', '## 4 · Tiempos')
        out.append((t, s.replace('__MODO__', modo)))
    return out


def generar():
    for modo in ('auto', 'limpias', 'errores'):
        nombre = TITULO[modo][0]
        nb = {'cells': [celda(t, s) for t, s in celdas(modo)],
              'metadata': {'language_info': {'name': 'python'},
                           'application/vnd.databricks.v1+notebook': {'notebookName': nombre, 'language': 'python'}},
              'nbformat': 4, 'nbformat_minor': 5}
        json.dump(nb, open(os.path.join(WF, nombre + '.ipynb'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('generado', nombre)


def probar(volume, carga, simular=False, nueva=False, modo='limpias'):
    """Ejecuta todas las celdas (como Run all) contra la foto de las tablas tras `carga`."""
    os.environ.update(PPTO27_CATALOGO='local', PPTO27_FORMATO='parquet', PPTO27_VOLUME=volume)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(WF)), '02. Entregable 1 - Contable', '02. Databricks'))
    from pyspark.sql import SparkSession, functions as F, Window as W
    spark = (SparkSession.builder.master('local[4]').config('spark.ui.enabled', 'false')
             .config('spark.sql.ansi.enabled', 'true').config('spark.driver.memory', '4g').getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    wh = f'{volume}/_warehouse_{carga}'
    for d in os.listdir(wh):
        if d.startswith(('ppto27_gld', 'ppto27_slv', 'ppto27_brz_archivos')):
            spark.read.parquet(f'{wh}/{d}').createOrReplaceTempView(d)
    if simular or nueva:   # como la versión del usuario: metodologías Nueva/Antigua y estado_linea en el Dir/Ind
        g = spark.table('ppto27_gld_fact_gestion_dirind')
        e = spark.table('ppto27_gld_fact_ppto').select('id_linea', 'id_fecha', 'estado_linea').distinct()
        g = g.join(e, ['id_linea', 'id_fecha'], 'left')
        (g.withColumn('metodologia', F.lit('Nueva'))
          .unionByName(g.withColumn('metodologia', F.lit('Antigua')).withColumn('monto_pen', F.col('monto_pen') * 0.7))
          .localCheckpoint().createOrReplaceTempView('ppto27_gld_fact_gestion_dirind'))
    if nueva:              # base de reparto = imputación + soporte directo
        g = spark.table('ppto27_gld_fact_gestion_dirind')
        k = ['id_pais', 'id_fecha', 'metodologia']
        b = g.where('id_componente IN (1, 2)').groupBy(*k, 'id_udn').agg(F.sum('monto_pen').alias('b'))
        b = b.withColumn('peso', F.col('b') / F.sum('b').over(W.partitionBy(*k)))
        c3 = g.where('id_componente = 3')
        lin = c3.groupBy(*k, *[c for c in c3.columns if c not in k + ['id_udn', 'pct_driver', 'monto_pen', 'monto_local']]).agg(F.sum('monto_pen').alias('tot'))
        nv = (lin.join(b.select(*k, 'id_udn', 'peso'), k).withColumn('monto_pen', F.col('tot') * F.col('peso'))
              .withColumn('pct_driver', F.col('peso')).withColumn('monto_local', F.col('monto_pen')).drop('tot', 'peso'))
        g.where('id_componente <> 3').unionByName(nv.select(*g.columns)).localCheckpoint().createOrReplaceTempView('ppto27_gld_fact_gestion_dirind')

    def ver(df):
        import pyarrow
        pyarrow.Table.from_pandas(df)          # igual que display() en Databricks: falla con columnas de tipos mezclados
        print(df.to_string(index=False, max_colwidth=60, max_rows=40) if hasattr(df, 'to_string') else df)

    class _W:
        def dropdown(self, *a):
            pass

        def get(self, k):
            return os.environ.get('SELECCION', 'Las 3')

    g = {'spark': spark, 'display': ver, 'dbutils': type('D', (), {'widgets': _W()})()}
    for t, s in celdas(modo):
        if t != 'code' or s.startswith('%pip'):
            continue
        s = s.replace("sys.path.append('/Volumes/catalogo_ppto/esquema_ppto/vol_administrado/ppto27/00_codigo')", '')
        for capa in ('gld', 'slv', 'brz'):
            s = s.replace(f"return f'{{CAT}}.ppto27_{capa}_{{n}}'", f"return f'ppto27_{capa}_{{n}}'")
        print('\n>>>', s.splitlines()[0][:90])
        exec(s, g)
    spark.stop()


if __name__ == '__main__':
    generar()
    if '--probar' in sys.argv:
        i = sys.argv.index('--probar')
        probar(sys.argv[i + 1], sys.argv[i + 2], '--simular' in sys.argv, '--nueva' in sys.argv,
               'errores' if '--errores' in sys.argv else 'auto' if '--auto' in sys.argv else 'limpias')
