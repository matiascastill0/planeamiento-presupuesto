"""Genera los maestros que se suben a /Volumes/.../ppto27/90_maestros (se corre en local, una vez por versión).

  maestros_ppto27.xlsx   plantillas · cuentas · proveedores · cecos · tipo_cambio      (los genera este script)
  alias_ppto27.xlsx      alias_cuenta · alias_proveedor · alias_plantilla              (los llena Planeamiento a mano;
                                                                                         si ya existe NO se pisa)
Fuentes:
  · Plantillas, cuentas, proveedores y TC: las 184 plantillas de 01. Ruta Oficial (armadas desde la TD con filtros oficiales).
  · Plan de cuentas: TD Regional (cache_full.pkl) con filtros oficiales: Real/Ppto 2026, Vista 1 y 3, sin INTERCOM/ELIM, sin IPC.
  · CeCos: TD + agrupación de la tabla de drivers v2.
Formato xlsx (no CSV) porque los alias se editan en Excel en Windows y un CSV sin BOM rompe las tildes.
"""
import os, sys, unicodedata, collections, json
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
DBX_NB = os.path.dirname(AQUI)                                                 # 02. Databricks
sys.path.insert(0, DBX_NB)
import ppto27_lib as L

RAIZ = AQUI
while not os.path.isdir(os.path.join(RAIZ, '01. Ruta Oficial Ppto27 (Real Ene-Ago)')):
    RAIZ = os.path.dirname(RAIZ)
RUTA = os.path.join(RAIZ, '01. Ruta Oficial Ppto27 (Real Ene-Ago)')
PROC = os.path.join(RAIZ, '03. Procesos')
DRIVERS = os.path.join(RAIZ, '05. Databricks', '03. Entregable 2 - Gestión Dir-Ind', 'Drivers Ppto27 - tabla actualizada v2.xlsx')
SALIDA = os.path.join(DBX_NB, '90_maestros (subir al volume)')
CACHE_LECTURA = os.path.join(AQUI, '_lectura_ruta.pkl')


def nfc(s): return unicodedata.normalize('NFC', s)


def leer_ruta():
    """Lee las 184 plantillas una vez (se guarda en _lectura_ruta.pkl para no repetir)."""
    fs = sorted(nfc(os.path.relpath(os.path.join(d, x), RUTA)) for d, _, f in os.walk(RUTA) if '00. versiones' not in d
                for x in f if L.es_plantilla(x))
    if os.path.exists(CACHE_LECTURA):
        c = pd.read_pickle(CACHE_LECTURA)
        if c['archivos'] == fs and c['mtime'] == max(os.path.getmtime(os.path.join(RUTA, f)) for f in fs):
            return c['A'], c['L']
    A, LIN = [], []
    for f in fs:
        a, l = L.leer_plantilla(os.path.join(RUTA, f))
        a.update(ruta_relativa=f, archivo=os.path.basename(f), **L.identificar(f))
        A.append(a)
        LIN += [dict(x, id_plantilla=a['id_plantilla']) for x in l]
    pd.to_pickle({'archivos': fs, 'mtime': max(os.path.getmtime(os.path.join(RUTA, f)) for f in fs), 'A': A, 'L': LIN}, CACHE_LECTURA)
    return A, LIN


def main():
    A, LIN = leer_ruta()
    A, LIN = pd.DataFrame(A), pd.DataFrame(LIN)

    plantillas = A[['id_plantilla', 'rubro_cod', 'rubro', 'sub_rubro', 'tipo', 'area', 'pais_carpeta', 'nombre_base',
                    'ruta_relativa', 'archivo']].rename(columns={'pais_carpeta': 'pais', 'ruta_relativa': 'ruta_en_sharepoint'})

    # plan de cuentas: TD oficial + nombres usados en la ruta (con su Nivel 1 / 2 del formato plantilla)
    sys.path.insert(0, PROC)
    import td_filter as T
    td = pd.read_pickle(os.path.join(PROC, 'cache_full.pkl'),)
    m = (td.Datos.isin(['Real 2026', 'Ppto 2026']) & td.Vista.isin(T.VISTAS) & ~td['Compañía'].astype(str).str.contains('INTERCOM')
         & ~td['Compañía'].astype(str).isin(T.NO_CONTABLES) & T.sin_ipc(td))
    tdc = td.loc[m, ['Cta_Contable', 'Nom_Cta_Contable']].dropna().astype(str).drop_duplicates()
    tdc['Nom_Cta_Contable'] = tdc.Nom_Cta_Contable.map(L.limpiar)
    cta_por_nombre = tdc.groupby('Nom_Cta_Contable').Cta_Contable.agg(lambda s: ', '.join(sorted(set(s))))
    LIN['cuenta'] = LIN.nom_cta_contable.map(L.limpiar)
    usadas = (LIN.dropna(subset=['cuenta']).groupby('cuenta')
              .agg(nivel_1=('nivel_1', lambda s: s.mode().iat[0] if s.notna().any() else None),
                   nivel_2=('nivel_2', lambda s: s.mode().iat[0] if s.notna().any() else None),
                   lineas_en_ruta=('fila', 'size')))
    nombres = sorted(set(cta_por_nombre.index) | set(usadas.index))
    cuentas = pd.DataFrame({'nom_cta_contable': nombres})
    cuentas['cta_contable'] = cuentas.nom_cta_contable.map(cta_por_nombre)
    cuentas = cuentas.join(usadas, on='nom_cta_contable')
    cuentas['origen'] = ['TD y ruta' if pd.notna(c) and pd.notna(n) else ('TD' if pd.notna(c) else 'Ruta')
                         for c, n in zip(cuentas.cta_contable, cuentas.lineas_en_ruta)]
    cuentas['clave'] = cuentas.nom_cta_contable.map(L.clave_texto)

    # proveedores: los de las líneas + las listas de la hoja Tablas (columna S, ya homologados)
    prov = collections.Counter(L.limpiar(p) for p in LIN.proveedor.dropna())
    for js in A.listas.dropna():
        for p in json.loads(js).get('Proveedor', []):
            prov.setdefault(L.limpiar(p), 0)
    proveedores = pd.DataFrame([{'proveedor': p, 'lineas_en_ruta': n} for p, n in prov.items()
                                if p and p.upper() not in L.SIN_PROVEEDOR and not p.startswith('(')])
    proveedores['clave'] = proveedores.proveedor.map(L.clave_proveedor)
    proveedores = proveedores.sort_values(['clave', 'lineas_en_ruta'], ascending=[True, False])
    proveedores['duplicado_por_clave'] = proveedores.duplicated('clave')
    # nombre oficial por clave = la variante con más líneas (p. ej. "AVIATUR SAS" 191 líneas vs "AVIATUR S.A.S." 7)
    proveedores['proveedor_oficial'] = proveedores.groupby('clave').proveedor.transform('first')
    proveedores = proveedores[['proveedor_oficial', 'proveedor', 'lineas_en_ruta', 'clave', 'duplicado_por_clave']]

    # CeCos: TD (nombre) + agrupación de drivers v2
    tc_ = td.loc[m, ['Pais', 'CeCo', 'Nom_CeCo', 'Agrupación_CeCo']].dropna(subset=['CeCo']).drop_duplicates(['Pais', 'CeCo'])
    tc_['pais'] = tc_.Pais.map(lambda x: L.PAISES.get(L.sin_tildes(x).upper(), x))
    tc_['ceco'] = pd.to_numeric(tc_.CeCo, errors='coerce')
    tc_ = tc_.dropna(subset=['ceco'])
    tc_['ceco'] = tc_.ceco.astype(int).map(lambda c: c - 211000 if c > 211000 else c)
    cecos = tc_.rename(columns={'Nom_CeCo': 'nombre', 'Agrupación_CeCo': 'agrupacion'})[['pais', 'ceco', 'nombre', 'agrupacion']]
    cecos = cecos.drop_duplicates(['pais', 'ceco']).sort_values(['pais', 'ceco'])
    dv = pd.read_excel(DRIVERS, 'Drivers', header=4).dropna(axis=1, how='all')
    dv['pais'] = dv.Pais.map(lambda x: L.PAISES.get(L.sin_tildes(x).upper(), x))
    dv['ceco'] = dv['CeCo (proyecto)'].astype(int)
    ag = dv.drop_duplicates(['pais', 'ceco']).set_index(['pais', 'ceco'])['Agrupación_CeCo']
    cecos['agrupacion_drivers'] = [ag.get((p, c)) for p, c in zip(cecos.pais, cecos.ceco)]
    cecos['tiene_driver'] = cecos.agrupacion_drivers.notna()

    # tipo de cambio 2027 (cabecera de las plantillas): debe ser el mismo en todas
    tcs = collections.Counter(A.tc.dropna())
    tc_json, n_tc = tcs.most_common(1)[0]
    tipo_cambio = pd.DataFrame([{'anio': 2027, 'mes': i + 1, 'moneda': mon, 'unidades_por_usd': v}
                                for mon, vals in json.loads(tc_json).items() for i, v in enumerate(vals)]
                               + [{'anio': 2027, 'mes': i + 1, 'moneda': 'USD', 'unidades_por_usd': 1.0} for i in range(12)])
    tipo_cambio['fuente'] = f'Cabecera de las plantillas Ppto27 (filas 3–5, Ene–Dic 27): igual en {n_tc} de {len(A)}'

    # vehículos por país: líneas de la ruta + drivers, con la razón social de la leyenda de las plantillas
    rs = {}
    for r in A.dropna(subset=['leyenda']).itertuples():
        for v, nom in json.loads(r.leyenda).items():
            rs.setdefault((r.pais_carpeta, v), nom)
    LIN['pais_l'] = LIN.pais.map(L.limpiar)
    vs = set(zip(LIN.pais_l, LIN.vehiculo.map(L.limpiar))) | set(zip(dv.dropna(subset=['Vehiculo']).pais, dv.dropna(subset=['Vehiculo']).Vehiculo.astype(str)))
    vehiculos = pd.DataFrame(sorted((p, v) for p, v in vs if p in L.MONEDA_LOCAL and v and not str(v).upper().startswith('INTERCOM')),
                             columns=['pais', 'vehiculo'])
    vehiculos['razon_social'] = [rs.get((p, v)) for p, v in zip(vehiculos.pais, vehiculos.vehiculo)]

    os.makedirs(SALIDA, exist_ok=True)
    import shutil
    shutil.copy2(DRIVERS, os.path.join(SALIDA, 'drivers_ppto27.xlsx'))
    with pd.ExcelWriter(os.path.join(SALIDA, 'maestros_ppto27.xlsx')) as w:
        for n, df in (('plantillas', plantillas), ('cuentas', cuentas), ('proveedores', proveedores), ('cecos', cecos),
                      ('tipo_cambio', tipo_cambio), ('vehiculos', vehiculos)):
            df.to_excel(w, sheet_name=n, index=False)
    ali = os.path.join(SALIDA, 'alias_ppto27.xlsx')
    if not os.path.exists(ali):
        cols = ['alias', 'oficial', 'aprobado_por', 'fecha', 'comentario']
        with pd.ExcelWriter(ali) as w:
            pd.DataFrame(columns=cols).to_excel(w, sheet_name='alias_cuenta', index=False)
            pd.DataFrame(columns=cols).to_excel(w, sheet_name='alias_proveedor', index=False)
            pd.DataFrame(columns=['ruta_o_archivo', 'id_plantilla', 'aprobado_por', 'fecha', 'comentario']).to_excel(
                w, sheet_name='alias_plantilla', index=False)
    print('plantillas', len(plantillas), '· cuentas', len(cuentas), cuentas.origen.value_counts().to_dict(),
          '· proveedores', len(proveedores), '(claves repetidas', int(proveedores.duplicado_por_clave.sum()), ')',
          '· cecos', len(cecos), '· vehículos', len(vehiculos), '· TC distintos entre plantillas', len(tcs))
    return dict(A=A, LIN=LIN, plantillas=plantillas, cuentas=cuentas, proveedores=proveedores, cecos=cecos, tipo_cambio=tipo_cambio)


if __name__ == '__main__':
    main()
