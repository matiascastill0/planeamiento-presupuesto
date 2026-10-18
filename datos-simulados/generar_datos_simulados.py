"""Tablas del BI Ppto27 con datos SIMULADOS (misma estructura que las tablas gold de Databricks).

Para quien no tiene acceso a Databricks: conecta Power BI a estos CSV / Excel y trabaja con el mismo modelo.
- Mismas 15 tablas, mismas columnas, mismos tipos y mismas llaves que ppto27_gld_* (ver LEEME).
- Catálogos (país, UdN, componente, Formato Perú, flags, vehículos, meses) iguales a los reales.
- CeCos, cuentas, proveedores, plantillas y montos: simulados y chicos, pero coherentes:
  las llaves cruzan, Dir/Ind reparte con la metodología real y gestión = contable al céntimo.

Uso:  python3 generar_datos_simulados.py
"""
import os, hashlib
import numpy as np, pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(AQUI, 'catalogos')                            # catálogos oficiales (sin montos)
OUT_CSV = os.path.join(AQUI, 'CSV')
OUT_XLSX = os.path.join(AQUI, 'salida', 'Ppto27 - Tablas BI simuladas.xlsx')
rng = np.random.default_rng(2027)
leer = lambda n: pd.read_csv(os.path.join(REF, f'{n}.csv'), encoding='utf-8-sig', dtype=str, keep_default_na=False)

# ---------------- catálogos (iguales a Databricks) ----------------
dim_pais = leer('dim_pais')
dim_udn = leer('dim_udn')
dim_componente = leer('dim_componente').astype({'id_componente': int})
dim_linea_pyg = leer('dim_linea_pyg').astype({'id_linea_pyg': int, 'orden_n1': int, 'orden_n2': int})
dim_flag = leer('dim_flag')
dim_vehiculo = leer('dim_vehiculo')
dim_fecha = leer('dim_fecha').astype({'id_fecha': int, 'anio': int, 'mes_num': int})
MESES = list(dim_fecha.id_fecha)

TC_PEN = {'Perú': 1.0, 'Colombia': 0.00095, 'Chile': 0.0036}      # moneda local -> PEN (simulado)
MON = {'Perú': 'PEN', 'Colombia': 'COP', 'Chile': 'CLP'}
ESCALA = {'Perú': 1.0, 'Colombia': 1 / 0.00095, 'Chile': 1 / 0.0036}   # montos base en PEN -> local

# ---------------- CeCos simulados (código - nombre) ----------------
CECOS = [  # pais, ceco, nombre, agrupacion, sub_unidad, tipo
    ('Perú', 401, 'Banca Privada Lima', 'WM', 'WM', 'Negocio'),
    ('Perú', 421, 'Mercado de Capitales', 'MDK', 'MDK', 'Negocio'),
    ('Perú', 109, 'Riesgos Operativos', 'Staff - Riesgo', 'STAFF', 'Staff'),
    ('Perú', 303, 'Dirección Finanzas', 'Staff - Finanzas', 'STAFF', 'Staff'),
    ('Colombia', 451, 'Asset Management Fondos', 'AM', 'AM', 'Negocio'),
    ('Colombia', 109, 'Riesgos Operativos', 'Staff - Riesgo', 'STAFF', 'Staff'),
    ('Colombia', 101, 'Gerencia General', 'Staff - Gerencia General', 'STAFF', 'Staff'),
    ('Chile', 402, 'Wealth Management Santiago', 'WM', 'WM', 'Negocio'),
    ('Chile', 303, 'Dirección Finanzas', 'Staff - Finanzas', 'STAFF', 'Staff'),
]
dim_ceco = pd.DataFrame([{'id_ceco': f'{p}|{c}', 'pais': p, 'ceco': c, 'ceco_nombre': f'{c} - {n}', 'agrupacion': a,
                          'sub_unidad': s, 'tipo_ceco': t} for p, c, n, a, s, t in CECOS])

# ---------------- cuentas simuladas por Nivel 2 ----------------
N1_PLANT = {'Gastos del Personal': 'Gastos del Personal', 'Gastos Administrativos': 'Gastos Administrativos',
            'Gastos de TI': 'Tecnología y Comunicaciones'}
pyg = dim_linea_pyg.set_index('id_linea_pyg')
CUENTAS = [  # id_linea_pyg, nombre de cuenta
    (1, 'SUELDOS Y SALARIOS'), (1, 'GRATIFICACIONES'), (2, 'BONIFICACION POR DESEMPEÑO'), (11, 'CURSOS Y CAPACITACION'),
    (12, 'BONO ANUAL'), (6, 'SEGURO MEDICO'), (14, 'PASAJES AEREOS'), (14, 'ALOJAMIENTO INTERNACIONAL'),
    (15, 'HONORARIOS PROFESIONALES'), (16, 'SERVICIOS ADMINISTRATIVOS'), (17, 'PUBLICIDAD Y EVENTOS'),
    (19, 'SUSCRIPCIONES DE INFORMACION'), (22, 'UTILES DE OFICINA'), (25, 'LICENCIAS DE SOFTWARE'), (29, 'SERVICIOS CLOUD'),
]
dim_cuenta = pd.DataFrame([{'id_cuenta': i, 'nom_cta_contable': n, 'nivel_1': pyg.loc[l, 'nivel_1_plantilla'],
                            'nivel_2': pyg.loc[l, 'nivel_2_plantilla'], 'nivel_3': ''} for i, (l, n) in enumerate(CUENTAS, 1)])
CTA = {n: (i, l) for i, (l, n) in enumerate(CUENTAS, 1)}

PROVS = ['Consultora Andina SAC', 'Data Markets Info Ltda', 'Viajes Corporativos SA', 'Nube Segura SpA',
         'Software Global Inc', 'Eventos y Marca SAS', 'Seguros Salud Plus', 'Oficina Express SAC', 'Estudio Legal Pacífico']
dim_proveedor = pd.DataFrame({'id_proveedor': range(1, len(PROVS) + 1), 'proveedor': PROVS})
PRV = {p: i for i, p in enumerate(PROVS, 1)}

# ---------------- plantillas ----------------
#  (pais, tipo, area, ceco, udn (UdN) | driver {udn: %} (Soporte) | None (Indirecto), vehiculo, líneas)
PERSONAL = [('SUELDOS Y SALARIOS', None, 40000), ('GRATIFICACIONES', None, 7000), ('BONIFICACION POR DESEMPEÑO', None, 9000),
            ('SEGURO MEDICO', 'Seguros Salud Plus', 2500), ('CURSOS Y CAPACITACION', 'Consultora Andina SAC', 900)]
ADMIN = [('PASAJES AEREOS', 'Viajes Corporativos SA', 1800), ('HONORARIOS PROFESIONALES', 'Estudio Legal Pacífico', 3000),
         ('SUSCRIPCIONES DE INFORMACION', 'Data Markets Info Ltda', 2200), ('UTILES DE OFICINA', 'Oficina Express SAC', 400)]
TI = [('LICENCIAS DE SOFTWARE', 'Software Global Inc', 2600), ('SERVICIOS CLOUD', 'Nube Segura SpA', 1500)]
PLANTILLAS = [
    ('Perú', 'UdN', 'MDK', 421, 'MDK', 'CCB', PERSONAL + [('PUBLICIDAD Y EVENTOS', 'Eventos y Marca SAS', 1200)] + ADMIN[:3], 1.6),
    ('Perú', 'UdN', 'WM', 401, 'WM', 'CCB', PERSONAL + ADMIN[:2] + [('PUBLICIDAD Y EVENTOS', 'Eventos y Marca SAS', 2000)], 2.2),
    ('Perú', 'Soporte directo', 'Riesgos', 109, {'MDK': .12, 'WM': .08}, 'CCP', PERSONAL[:4] + TI, 0.7),
    ('Perú', 'Indirecto', 'Finanzas', 303, None, 'CCP', PERSONAL[:4] + ADMIN[1:3] + TI[:1], 0.9),
    ('Colombia', 'UdN', 'AM', 451, 'AM', 'FI', PERSONAL + ADMIN[:3], 1.4),
    ('Colombia', 'Soporte directo', 'Riesgos', 109, {'AM': .20}, 'SC', PERSONAL[:4] + TI[:1], 0.5),
    ('Colombia', 'Indirecto', 'Gerencia General', 101, None, 'SC', PERSONAL[:4] + ADMIN[:2], 1.1),
    ('Chile', 'UdN', 'WM', 402, 'WM', 'CCCB', PERSONAL + ADMIN[:2] + TI[:1], 1.2),
    ('Chile', 'Indirecto', 'Finanzas', 303, None, 'CCCH', PERSONAL[:4] + ADMIN[2:4], 0.6),
]
CARP = {'Perú': '01. PERU', 'Colombia': '02. COLOMBIA', 'Chile': '03. CHILE'}
RUBRO = {'UdN': 'UDN', 'Soporte directo': 'Staff', 'Indirecto': 'Staff'}

plant, ppto = [], []
for (pais, tipo, area, ceco, udn, veh, lineas, k) in PLANTILLAS:
    nom = f'{RUBRO[tipo]} - {area}' if tipo != 'UdN' else f'UdN - {area}'
    carpeta = f'{nom}/{CARP[pais]}'
    archivo = f'Ppto27 - {nom} {pais.replace("ú", "u")} - OFICIAL.xlsx'
    idp = f'{carpeta}/{archivo}'
    plant.append({'id_plantilla': idp, 'archivo': archivo, 'carpeta': carpeta, 'tipo': tipo, 'area': area, 'pais': pais,
                  'entrega': 'Tocada por el área', 'version': 'v1-simulada', 'hash': hashlib.md5(idp.encode()).hexdigest()[:16],
                  'fecha_carga': '2026-10-20', 'estado_validacion': 'Con alertas', '_udn': udn, '_ceco': f'{pais}|{ceco}'})
    for i, (cta, prov, base) in enumerate(lineas):
        fila = 10 + i; id_cta, id_pyg = CTA[cta]
        anual = base * 12 * k * rng.uniform(0.85, 1.15)
        estacional = np.ones(12)
        if 'BONIFICACION' in cta: estacional = np.r_[np.zeros(2), [12], np.zeros(9)]          # variable pagado en marzo
        elif 'GRATIFICACIONES' in cta: estacional = np.r_[np.zeros(6), [6], np.zeros(4), [6]]  # julio y diciembre
        else: estacional = estacional * rng.uniform(0.9, 1.1, 12)
        mens = -anual * estacional / estacional.sum()
        for m, (idf, v) in enumerate(zip(MESES, mens)):
            if abs(v) < 0.005: continue
            local = round(v * ESCALA[pais], 2)
            ppto.append({'id_linea': f'{idp}#{fila}', 'id_plantilla': idp, 'id_fecha': idf, 'id_pais': pais,
                         'id_ceco': f'{pais}|{ceco}', 'id_vehiculo': f'{pais}|{veh}', 'id_cuenta': id_cta,
                         'id_proveedor': PRV.get(prov), 'id_linea_pyg': id_pyg, 'glosa': cta.capitalize(),
                         'escenario': 'Ppto 2027', 'moneda_origen': MON[pais], 'monto_origen': local, 'monto_local': local,
                         'monto_pen': round(local * TC_PEN[pais], 6), 'origen_monto': 'Área', 'estado_linea': 'OK',
                         'flags': '', 'anio': 2027})
fact_ppto = pd.DataFrame(ppto)
fact_ppto['id_proveedor'] = fact_ppto['id_proveedor'].astype('Int64')
dim_plantilla = pd.DataFrame(plant)

# ---------------- errores sembrados (clásicos, con celda exacta) ----------------
COL_MES = dict(zip(MESES, ['AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AI', 'AJ', 'AK', 'AL']))
flags = []
def sembrar(idx_plant, fila, mes_i, codigo, estado, detalle, positivo=False):
    idp = dim_plantilla.id_plantilla[idx_plant]; idl = f'{idp}#{fila}'; idf = MESES[mes_i]
    m = (fact_ppto.id_linea == idl) & (fact_ppto.id_fecha == idf)
    if positivo:
        for c in ('monto_origen', 'monto_local', 'monto_pen'): fact_ppto.loc[m, c] = fact_ppto.loc[m, c].abs()
    fl = fact_ppto.id_linea == idl
    fact_ppto.loc[fl, 'estado_linea'] = estado
    fact_ppto.loc[fl, 'flags'] = (fact_ppto.loc[fl, 'flags'] + ', ' + codigo).str.strip(', ')
    flags.append({'id_plantilla': idp, 'id_linea': idl, 'codigo_flag': codigo, 'celdas': f'{COL_MES[idf]}{fila}', 'detalle': detalle})

sembrar(0, 15, 4, 'M01', 'Cuarentena', 'May-27 con monto positivo (gasto debe ir en negativo)', positivo=True)
sembrar(2, 11, 2, 'M10', 'OK con alerta', 'Mar-27 sin Real 2026 en la línea')
sembrar(4, 12, 0, 'M14', 'OK con alerta', 'Variación > 50 % vs F26 sin comentario del área')
sembrar(6, 14, 7, 'M01', 'Cuarentena', 'Ago-27 con monto positivo (gasto debe ir en negativo)', positivo=True)
sembrar(7, 13, 5, 'M10', 'OK con alerta', 'Jun-27 sin Real 2026 en la línea')
flags.append({'id_plantilla': dim_plantilla.id_plantilla[8], 'id_linea': '', 'codigo_flag': 'T06',
              'celdas': 'A19', 'detalle': 'País escrito "Chile " con espacio al final'})
fact_flags = pd.DataFrame(flags)
dim_plantilla.loc[dim_plantilla.id_plantilla.isin(fact_flags[fact_flags.codigo_flag == 'M01'].id_plantilla), 'estado_validacion'] = 'Con errores'

# ---------------- Dir/Ind (metodología Nueva y Antigua) ----------------
info = dim_plantilla.set_index('id_plantilla')
agr = dim_ceco.set_index('id_ceco').agrupacion
filas = []
for met in ('Nueva', 'Antigua'):
    directo, bolsa = [], []
    for r in fact_ppto.to_dict('records'):
        p = info.loc[r['id_plantilla']]; udn = p['_udn']
        if p['tipo'] == 'UdN': directo.append((r, udn, 1, 1.0))
        elif p['tipo'] == 'Soporte directo':
            for u, pct in udn.items(): directo.append((r, u, 2, pct))
            bolsa.append((r, 1 - sum(udn.values())))
        else: bolsa.append((r, 1.0))
    base = {}
    for r, u, comp, pct in directo:
        if met == 'Antigua' and comp == 2: continue          # Antigua: peso solo con imputación directa
        k = (r['id_pais'], r['id_fecha']); base.setdefault(k, {}).setdefault(u, 0.0)
        base[k][u] += r['monto_pen'] * pct
    def fila(r, u, comp, pct):
        return {'id_linea': r['id_linea'], 'id_plantilla': r['id_plantilla'], 'id_fecha': r['id_fecha'], 'id_pais': r['id_pais'],
                'id_udn': u, 'id_componente': comp, 'id_ceco_origen': r['id_ceco'], 'id_linea_pyg': r['id_linea_pyg'],
                'pct_driver': round(pct, 6), 'monto_pen': round(r['monto_pen'] * pct, 6), 'monto_local': round(r['monto_local'] * pct, 6),
                'estado_linea': r['estado_linea'], 'id_vehiculo': r['id_vehiculo'], 'anio': 2027, 'metodologia': met,
                'agrupacion': agr[r['id_ceco']]}
    for r, u, comp, pct in directo: filas.append(fila(r, u, comp, pct))
    for r, pct_b in bolsa:
        b = base[(r['id_pais'], r['id_fecha'])]; tot = sum(b.values())
        for u, v in b.items(): filas.append(fila(r, u, 3, pct_b * v / tot))
fact_gestion_dirind = pd.DataFrame(filas)

moneda = pd.DataFrame({'Moneda': ['Local', 'PEN']})

TABLAS = {'dim_pais': dim_pais, 'dim_udn': dim_udn, 'dim_componente': dim_componente, 'dim_linea_pyg': dim_linea_pyg,
          'dim_flag': dim_flag, 'dim_vehiculo': dim_vehiculo, 'dim_fecha': dim_fecha, 'dim_ceco': dim_ceco,
          'dim_cuenta': dim_cuenta, 'dim_proveedor': dim_proveedor,
          'dim_plantilla': dim_plantilla.drop(columns=['_udn', '_ceco']), 'fact_ppto': fact_ppto, 'fact_flags': fact_flags,
          'fact_gestion_dirind': fact_gestion_dirind, 'Moneda': moneda}


def controles():
    ok = True
    def chk(nombre, cond):
        nonlocal ok; ok &= bool(cond); print(('OK   ' if cond else 'FALLA'), nombre)
    T = TABLAS
    chk('fact_ppto -> dims (llaves existen)', all(fact_ppto[c].dropna().isin(T[d][k]).all() for c, d, k in [
        ('id_ceco', 'dim_ceco', 'id_ceco'), ('id_vehiculo', 'dim_vehiculo', 'id_vehiculo'), ('id_cuenta', 'dim_cuenta', 'id_cuenta'),
        ('id_proveedor', 'dim_proveedor', 'id_proveedor'), ('id_linea_pyg', 'dim_linea_pyg', 'id_linea_pyg'),
        ('id_plantilla', 'dim_plantilla', 'id_plantilla'), ('id_fecha', 'dim_fecha', 'id_fecha'), ('id_pais', 'dim_pais', 'id_pais')]))
    chk('fact_flags -> dims', fact_flags.codigo_flag.isin(dim_flag.codigo_flag).all() and fact_flags.id_plantilla.isin(dim_plantilla.id_plantilla).all())
    chk('dirind -> dims', fact_gestion_dirind.id_udn.isin(dim_udn.id_udn).all() and fact_gestion_dirind.id_ceco_origen.isin(dim_ceco.id_ceco).all())
    for met in ('Nueva', 'Antigua'):
        g = fact_gestion_dirind[fact_gestion_dirind.metodologia == met].groupby(['id_pais', 'id_fecha']).monto_pen.sum()
        c = fact_ppto.groupby(['id_pais', 'id_fecha']).monto_pen.sum()
        chk(f'Gestión {met} = Contable por país × mes (máx dif {abs(g - c).max():.6f})', abs(g - c).max() < 0.01)
    chk('gasto en negativo salvo líneas en cuarentena', (fact_ppto[fact_ppto.estado_linea != 'Cuarentena'].monto_pen <= 0).all())
    return ok


def guardar():
    os.makedirs(OUT_CSV, exist_ok=True)
    for n, df in TABLAS.items():
        df.to_csv(os.path.join(OUT_CSV, f'{n}.csv'), index=False, encoding='utf-8-sig', lineterminator='\r\n')
    os.makedirs(os.path.dirname(OUT_XLSX), exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine='openpyxl') as w:
        for n, df in TABLAS.items(): df.to_excel(w, sheet_name=n, index=False)
    for n, df in TABLAS.items(): print(f'{n:22} {len(df):6} filas · {len(df.columns)} columnas')


if __name__ == '__main__':
    if not controles(): raise SystemExit('Controles con falla: no se guardó nada')
    guardar()
