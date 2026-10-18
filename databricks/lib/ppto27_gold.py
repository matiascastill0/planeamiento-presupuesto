"""Gold del Ppto27: modelo estrella del Power BI (mismas tablas y columnas que 05. Databricks/01. Datos ejemplo (CSV)).

  hechos:      fact_ppto (contable, línea × mes) · fact_gestion_dirind (línea × UdN × componente × mes) · fact_flags
  dimensiones: dim_fecha · dim_linea_pyg (Formato Perú N1/N2) · dim_pais · dim_ceco · dim_udn · dim_componente · dim_vehiculo
               dim_cuenta · dim_proveedor · dim_plantilla · dim_flag · dim_driver
Más control(): cuadre 100 = 100 por plantilla, integridad de claves, mapeo al Formato Perú, contable = Dir/Ind.
Python puro sobre pandas (lo llama el notebook 30_gold y la prueba local).
"""
from datetime import date
import pandas as pd
import ppto27_lib as L

NOMBRE_MES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Setiembre', 'Octubre', 'Noviembre', 'Diciembre']
PERIODO = ['Ene-27', 'Feb-27', 'Mar-27', 'Abr-27', 'May-27', 'Jun-27', 'Jul-27', 'Ago-27', 'Set-27', 'Oct-27', 'Nov-27', 'Dic-27']
COMP = [(1, 'Imputación directa', 'Directo'), (2, 'Soporte directo', 'Directo'), (3, 'Indirecto asignado', 'Indirecto')]
UDN_AGRUP = {'AM', 'MDK', 'WM', 'NNFF', 'Tesorería', 'JV CND', 'FINCORP'}
TYBA = {113, 346, 810, 811, 818}
COMP_V2 = {'Imputación directa': 'Imputación directa', 'Soporte directo': 'Soporte directo',
           'Soporte directo - asignado (driver propio)': 'Soporte directo',
           'Staff → Indirecto (bolsa)': 'Indirecto', 'Indirecto (bolsa)': 'Indirecto'}
OK = ('OK', 'OK con alerta')

COLS = {
    'fact_ppto': ['id_linea', 'id_plantilla', 'id_fecha', 'id_pais', 'id_ceco', 'id_vehiculo', 'id_cuenta', 'id_proveedor', 'id_linea_pyg',
                  'glosa', 'escenario', 'moneda_origen', 'monto_origen', 'monto_local', 'monto_pen', 'origen_monto', 'estado_linea', 'flags'],
    'fact_gestion_dirind': ['id_linea', 'id_plantilla', 'id_fecha', 'id_pais', 'id_udn', 'id_componente', 'id_ceco_origen', 'id_linea_pyg',
                            'pct_driver', 'monto_pen', 'monto_local'],
    'fact_flags': ['id_plantilla', 'id_linea', 'codigo_flag', 'celdas', 'detalle'],
    'dim_fecha': ['id_fecha', 'fecha', 'anio', 'mes_num', 'mes', 'periodo', 'trimestre', 'semestre'],
    'dim_linea_pyg': ['id_linea_pyg', 'n1_formato', 'grupo_n2', 'n2_formato', 'nivel_1_plantilla', 'nivel_2_plantilla', 'orden_n1', 'orden_n2'],
    'dim_pais': ['id_pais', 'pais', 'pais_bi', 'moneda_local'],
    'dim_ceco': ['id_ceco', 'pais', 'ceco', 'ceco_nombre', 'agrupacion', 'sub_unidad', 'tipo_ceco'],
    'dim_udn': ['id_udn', 'udn'],
    'dim_componente': ['id_componente', 'componente', 'grupo'],
    'dim_vehiculo': ['id_vehiculo', 'pais', 'vehiculo', 'razon_social'],
    'dim_cuenta': ['id_cuenta', 'nom_cta_contable', 'nivel_1', 'nivel_2', 'nivel_3'],
    'dim_proveedor': ['id_proveedor', 'proveedor'],
    'dim_plantilla': ['id_plantilla', 'archivo', 'carpeta', 'tipo', 'area', 'pais', 'entrega', 'version', 'hash', 'fecha_carga',
                      'estado_validacion'],
    'dim_flag': ['codigo_flag', 'categoria', 'severidad', 'flag', 'regla', 'accion'],
    'dim_driver': ['version_driver', 'id_ceco', 'pais', 'ceco', 'vehiculo', 'agrupacion', 'udn', 'dir_ind', 'componente', 'porcentaje'],
}


def id_fecha(m): return 20270000 + m * 100 + 1


def clave(*xs): return '|'.join(str(x) for x in xs)


def es_negocio(c): return c in TYBA or (len(str(c)) == 3 and str(c)[0] in '25689')


def tipo_cambio(M):
    """{moneda: [12 meses]} unidades por 1 USD (maestro único)."""
    tc = {}
    for r in M['tipo_cambio'].itertuples():
        tc.setdefault(r.moneda, [None] * 12)[int(r.mes) - 1] = float(r.unidades_por_usd)
    tc.setdefault('USD', [1.0] * 12)
    return tc


def cargar_drivers(D0):
    """Tabla de drivers v2 (hoja Drivers): sólo filas que cuentan en el control 100 %, sin INTERCOM, normalizadas a 100 %."""
    D = D0[D0['Cuenta en control 100 %'].eq('Sí') & ~D0.Vehiculo.fillna('').astype(str).str.upper().str.startswith('INTERCOM')].copy()
    D['pais'] = D.Pais.map(lambda x: L.PAISES.get(L.sin_tildes(x).upper(), x))
    D['ceco'] = D['CeCo (proyecto)'].astype(int)
    D['vehiculo'] = D.Vehiculo.fillna('(todos)').astype(str)
    D['componente'] = D.Componente.map(COMP_V2)
    D['udn'] = [('BOLSA' if c == 'Indirecto' else ('Tesorería' if L.clave_texto(u) == 'TESORERIA' else u)) for c, u in zip(D.componente, D.UdN)]
    D['porcentaje'] = D.Porcentaje.fillna(0.0)
    D = D[D.porcentaje.abs() > 1e-12].copy()
    D['porcentaje'] = D.porcentaje / D.groupby(['pais', 'ceco', 'vehiculo']).porcentaje.transform('sum')
    return D


# ───────────────────────────── Dir/Ind ─────────────────────────────
def dirind(S, D, tc):
    """S: líneas silver OK con montos PEN por mes (columnas pen_01..pen_12). Devuelve filas de fact_gestion_dirind."""
    dv = {k: list(zip(g.componente, g.udn, g.porcentaje)) for k, g in D.groupby(['pais', 'ceco', 'vehiculo'])}
    meses = [f'pen_{m:02d}' for m in range(1, 13)]
    A = []
    for r in S.itertuples():
        dest = dv.get((r.pais, r.ceco, r.vehiculo)) or dv.get((r.pais, r.ceco, '(todos)'))
        if dest is None:
            dest = [('Imputación directa', r.area, 1.0)] if (pd.notna(r.ceco) and es_negocio(int(r.ceco)) and r.tipo == 'UdN') else [('Indirecto', 'BOLSA', 1.0)]
        for comp, u, pct in dest:
            A.append((r.id_linea, r.id_plantilla, r.pais, r.ceco, r.id_linea_pyg, comp, u, pct, *[getattr(r, m) * pct for m in meses]))
    A = pd.DataFrame(A, columns=['id_linea', 'id_plantilla', 'pais', 'ceco', 'id_linea_pyg', 'componente', 'udn', 'pct', *meses])
    imp = A[A.componente == 'Imputación directa'].groupby(['pais', 'udn'])[meses].sum()
    part = imp.div(imp.groupby(level='pais').transform('sum')).fillna(0.0)
    out = [A[A.componente != 'Indirecto']]
    for p, gb in A[A.componente == 'Indirecto'].groupby('pais'):
        if p in part.index.get_level_values('pais') and imp.xs(p, level='pais').abs().to_numpy().sum() > 0:
            for u, pr in part.xs(p, level='pais').iterrows():
                x = gb.copy()
                x['udn'], x['componente'] = u, 'Indirecto asignado'
                for m in meses:
                    x[m] = x[m] * pr[m]
                out.append(x)
        else:                                                                  # país sin imputación directa: no se puede repartir
            out.append(gb.assign(udn='Sin base de reparto', componente='Indirecto asignado'))
    AL = pd.concat(out, ignore_index=True)
    comp_id = {c: i for i, c, _ in COMP}
    filas = []
    for r in AL.itertuples():
        loc = L.MONEDA_LOCAL[r.pais]
        for m in range(1, 13):
            v = getattr(r, f'pen_{m:02d}')
            if abs(v) < 1e-9:
                continue
            filas.append(dict(id_linea=r.id_linea, id_plantilla=r.id_plantilla, id_fecha=id_fecha(m), id_pais=r.pais, id_udn=r.udn,
                              id_componente=comp_id[r.componente], id_ceco_origen=clave(r.pais, r.ceco), id_linea_pyg=int(r.id_linea_pyg),
                              pct_driver=round(r.pct, 6), monto_pen=round(v, 6),
                              monto_local=round(v / tc['PEN'][m - 1] * tc[loc][m - 1], 6)))
    return pd.DataFrame(filas, columns=COLS['fact_gestion_dirind'])


# ───────────────────────────── gold ─────────────────────────────
def gold(slv, M, drivers0, fecha_carga=None):
    """slv: dict(lineas, flags, archivos) de silver · M: maestros · drivers0: hoja Drivers de drivers_ppto27.xlsx."""
    S, FLG, ARC = slv['lineas'].copy(), slv['flags'], slv['archivos']
    tc = tipo_cambio(M)
    fecha_carga = fecha_carga or date.today().isoformat()
    D = cargar_drivers(drivers0)

    # conversión: moneda origen → USD → PEN y moneda local, mes a mes (México en PEN; MXN sin TC queda sin convertir)
    for m in range(1, 13):
        k = f'ppto_2027_{m:02d}'
        usd = [v / tc[mon][m - 1] if pd.notna(v) and mon in tc else None for v, mon in zip(S[k], S.moneda)]
        S[f'pen_{m:02d}'] = [u * tc['PEN'][m - 1] if u is not None else 0.0 for u in usd]
        S[f'loc_{m:02d}'] = [u * tc[L.MONEDA_LOCAL.get(p, 'PEN')][m - 1] if u is not None else 0.0 for u, p in zip(usd, S.pais)]
    S['ceco'] = S.ceco.astype('Int64')
    S['proveedor_bi'] = S.proveedor_oficial.fillna('(sin proveedor)')

    txt = lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
    for c in ('cuenta_oficial', 'nivel_1', 'nivel_2', 'nivel_3'):
        S[c] = S[c].map(txt)
    dim_cuenta = (S[['cuenta_oficial', 'nivel_1', 'nivel_2', 'nivel_3']].drop_duplicates()
                  .sort_values(['nivel_1', 'nivel_2', 'cuenta_oficial']).reset_index(drop=True))
    dim_cuenta.insert(0, 'id_cuenta', range(1, len(dim_cuenta) + 1))
    cta = {tuple(x[1:]): x[0] for x in dim_cuenta.itertuples(index=False)}
    dim_cuenta = dim_cuenta.rename(columns={'cuenta_oficial': 'nom_cta_contable'}).replace('', None)
    provs = sorted(set(S.proveedor_bi))
    dim_proveedor = pd.DataFrame({'id_proveedor': range(1, len(provs) + 1), 'proveedor': provs})
    prv = dict(zip(dim_proveedor.proveedor, dim_proveedor.id_proveedor))

    fp = []
    for r in S.itertuples():
        idc = cta[(r.cuenta_oficial, r.nivel_1, r.nivel_2, r.nivel_3)]
        for m in range(1, 13):
            v = getattr(r, f'ppto_2027_{m:02d}')
            if pd.isna(v) or v == 0:
                continue
            fp.append(dict(id_linea=r.id_linea, id_plantilla=r.id_plantilla, id_fecha=id_fecha(m), id_pais=r.pais,
                           id_ceco=clave(r.pais, r.ceco) if pd.notna(r.ceco) else None,
                           id_vehiculo=clave(r.pais, r.vehiculo) if r.vehiculo else None, id_cuenta=idc,
                           id_proveedor=prv[r.proveedor_bi], id_linea_pyg=int(r.id_linea_pyg), glosa=r.glosa, escenario='Ppto 2027',
                           moneda_origen=r.moneda, monto_origen=round(v, 6), monto_local=round(getattr(r, f'loc_{m:02d}'), 6),
                           monto_pen=round(getattr(r, f'pen_{m:02d}'), 6), origen_monto='Área', estado_linea=r.estado_linea,
                           flags=r.flags))
    fact_ppto = pd.DataFrame(fp, columns=COLS['fact_ppto'])

    ok = S[S.estado_linea.isin(OK) & S.pais.isin(L.MONEDA_LOCAL)]
    ok = ok[ok[[f'pen_{m:02d}' for m in range(1, 13)]].abs().sum(axis=1) > 0]
    fact_gestion_dirind = dirind(ok, D, tc)

    fact_flags = FLG[COLS['fact_flags']].copy()

    usados = S.dropna(subset=['ceco']).drop_duplicates(['pais', 'ceco'])[['pais', 'ceco', 'ceco_nombre']]
    dims = dimensiones(usados, set(zip(S.pais, S.vehiculo)), sorted(set(fact_gestion_dirind.id_udn)), ARC, M, D, fecha_carga)
    T = dict(fact_ppto=fact_ppto, fact_gestion_dirind=fact_gestion_dirind, fact_flags=fact_flags, dim_cuenta=dim_cuenta,
             dim_proveedor=dim_proveedor, **dims)
    return {k: v[COLS[k]].reset_index(drop=True) for k, v in T.items()}


def dimensiones(usados, vehiculos_lineas, udns, ARC, M, D, fecha_carga):
    """Dimensiones del modelo (tablas chicas; las usan la versión pandas y la de Spark).
    usados: DataFrame (pais, ceco, ceco_nombre) de las líneas · vehiculos_lineas: pares (pais, vehiculo) · udns: id_udn de Dir/Ind ·
    ARC: plantillas vigentes (silver) · M: maestros · D: drivers cargados (cargar_drivers)."""
    dim_fecha = pd.DataFrame([dict(id_fecha=id_fecha(m), fecha=date(2027, m, 1).isoformat(), anio=2027, mes_num=m, mes=NOMBRE_MES[m - 1],
                                   periodo=PERIODO[m - 1], trimestre=f'T{(m - 1) // 3 + 1}', semestre=f'S{(m - 1) // 6 + 1}')
                              for m in range(1, 13)])
    dim_linea_pyg = pd.DataFrame(L.formato_peru())
    paises = sorted(set(L.MONEDA_LOCAL))
    dim_pais = pd.DataFrame([dict(id_pais=p, pais=p, pais_bi='ASB' if p == 'Panamá' else p, moneda_local=L.MONEDA_LOCAL[p]) for p in paises])

    mc = M['cecos'].copy()
    sub = D.drop_duplicates(['pais', 'ceco']).set_index(['pais', 'ceco'])['Sub_Unidad'] if 'Sub_Unidad' in D else {}
    mc['agrupacion'] = mc.agrupacion_drivers.where(mc.agrupacion_drivers.notna(), mc.agrupacion)
    dc = usados.merge(mc[['pais', 'ceco', 'nombre', 'agrupacion']], on=['pais', 'ceco'], how='outer')
    dc = pd.concat([dc, D.drop_duplicates(['pais', 'ceco'])[['pais', 'ceco', 'Nom_CeCo', 'Agrupación_CeCo']]
                    .rename(columns={'Nom_CeCo': 'nombre', 'Agrupación_CeCo': 'agrupacion'})]).drop_duplicates(['pais', 'ceco'])
    dc['ceco'] = dc.ceco.astype(int)
    dc['ceco_nombre'] = dc.ceco_nombre.fillna(dc.ceco.astype(str) + ' - ' + dc.nombre.fillna('').astype(str))
    dc['sub_unidad'] = [sub.get((p, c)) if hasattr(sub, 'get') else None for p, c in zip(dc.pais, dc.ceco)]
    dc['tipo_ceco'] = [('Negocio' if a in UDN_AGRUP else 'Staff') if isinstance(a, str) else ('Negocio' if es_negocio(c) else 'Staff')
                       for a, c in zip(dc.agrupacion, dc.ceco)]
    dc['id_ceco'] = [clave(p, c) for p, c in zip(dc.pais, dc.ceco)]
    dim_ceco = dc[COLS['dim_ceco']].sort_values(['pais', 'ceco']).reset_index(drop=True)

    mv = M['vehiculos']
    vs = set(zip(mv.pais, mv.vehiculo)) | set(vehiculos_lineas) | set(zip(D.pais, D.vehiculo))
    rs = dict(zip(zip(mv.pais, mv.vehiculo), mv.razon_social))
    dim_vehiculo = pd.DataFrame([dict(id_vehiculo=clave(p, v), pais=p, vehiculo=v, razon_social=rs.get((p, v)))
                                 for p, v in sorted((p, v) for p, v in vs if p and v and v != '(todos)')])
    dim_udn = pd.DataFrame({'id_udn': list(udns)}).assign(udn=lambda d: d.id_udn)
    dim_componente = pd.DataFrame([dict(id_componente=i, componente=c, grupo=g) for i, c, g in COMP])
    dim_flag = pd.DataFrame([dict(codigo_flag=k, categoria=v[0], severidad=v[1], flag=v[2], regla=v[3], accion=v[4])
                             for k, v in L.CATALOGO.items()])
    dim_driver = D.assign(version_driver='2026 v2', id_ceco=[clave(p, c) for p, c in zip(D.pais, D.ceco)],
                          agrupacion=D['Agrupación_CeCo'], dir_ind=D['DIR/IND'])[COLS['dim_driver']]

    # plantillas: las 184 esperadas (checklist) + las recibidas que no están en el maestro
    mp = M['plantillas'].set_index('id_plantilla')
    rec = ARC.set_index('id_plantilla') if len(ARC) else pd.DataFrame()
    ids = list(mp.index) + [i for i in rec.index if i not in mp.index]
    pl = []
    for i in ids:
        m_, r_ = (mp.loc[i] if i in mp.index else None), (rec.loc[i] if i in rec.index else None)
        src = r_ if r_ is not None else m_
        ruta = r_['ruta_relativa'] if r_ is not None else m_['ruta_en_sharepoint']
        pl.append(dict(id_plantilla=i, archivo=r_['archivo'] if r_ is not None else m_['archivo'], carpeta=ruta.rsplit('/', 1)[0],
                       tipo=src['tipo'], area=src['area'], pais=(r_['pais_carpeta'] if r_ is not None else m_['pais']),
                       entrega='Recibida' if r_ is not None else 'Pendiente', version=r_['carga_id'] if r_ is not None else None,
                       hash=r_['sha256'][:16] if r_ is not None else None, fecha_carga=fecha_carga if r_ is not None else None,
                       estado_validacion=r_['estado_archivo'] if r_ is not None else 'Pendiente de entrega'))
    dim_plantilla = pd.DataFrame(pl, columns=COLS['dim_plantilla'])

    return dict(dim_fecha=dim_fecha, dim_linea_pyg=dim_linea_pyg, dim_pais=dim_pais, dim_ceco=dim_ceco, dim_udn=dim_udn,
                dim_componente=dim_componente, dim_vehiculo=dim_vehiculo, dim_plantilla=dim_plantilla, dim_flag=dim_flag, dim_driver=dim_driver)


# ───────────────────────────── control ─────────────────────────────
def control(slv, G, filas_bronze=None):
    """Cuadre 100 = 100 por plantilla e integridad del modelo. Devuelve (cuadre, controles)."""
    ARC = slv['archivos']
    fp = G['fact_ppto']
    g_orig = fp.groupby('id_plantilla').monto_origen.sum()
    cu = ARC[['id_plantilla', 'archivo', 'rubro', 'pais_carpeta', 'estado_archivo', 'p27_archivo', 'p27_ok', 'p27_cuarentena']].copy()
    cu['p27_gold'] = cu.id_plantilla.map(g_orig).fillna(0.0)
    cu['diferencia'] = (cu.p27_archivo - cu.p27_gold).round(2)
    cu['cuadra'] = cu.diferencia.abs() < 0.01
    ctl = []
    def ok(nombre, cond, det=''):
        ctl.append(dict(control=nombre, resultado='OK' if cond else 'FALLA', detalle=det))
    ok('Cuadre 100 = 100: Ppto 2027 del archivo = fact_ppto, por plantilla', bool(cu.cuadra.all()),
       f'{int(cu.cuadra.sum())} de {len(cu)} plantillas; dif. máx. {cu.diferencia.abs().max() if len(cu) else 0:,.2f}')
    if filas_bronze is not None:                                               # Serie sha256 → filas en bronze
        nb = filas_bronze
        dif = (ARC.set_index('sha256').lineas_bronze - nb.reindex(ARC.sha256).values).abs().sum()
        ok('Filas bronze = filas leídas en silver', dif == 0, f'diferencia {dif}')
    for t, col, dim, dcol in [('fact_ppto', 'id_fecha', 'dim_fecha', 'id_fecha'), ('fact_ppto', 'id_pais', 'dim_pais', 'id_pais'),
                              ('fact_ppto', 'id_ceco', 'dim_ceco', 'id_ceco'), ('fact_ppto', 'id_vehiculo', 'dim_vehiculo', 'id_vehiculo'),
                              ('fact_ppto', 'id_cuenta', 'dim_cuenta', 'id_cuenta'), ('fact_ppto', 'id_proveedor', 'dim_proveedor', 'id_proveedor'),
                              ('fact_ppto', 'id_plantilla', 'dim_plantilla', 'id_plantilla'), ('fact_ppto', 'id_linea_pyg', 'dim_linea_pyg', 'id_linea_pyg'),
                              ('fact_gestion_dirind', 'id_udn', 'dim_udn', 'id_udn'), ('fact_gestion_dirind', 'id_ceco_origen', 'dim_ceco', 'id_ceco'),
                              ('fact_gestion_dirind', 'id_componente', 'dim_componente', 'id_componente'),
                              ('fact_flags', 'codigo_flag', 'dim_flag', 'codigo_flag'), ('fact_flags', 'id_plantilla', 'dim_plantilla', 'id_plantilla')]:
        falt = set(G[t][col].dropna()) - set(G[dim][dcol])
        ok(f'{t}.{col} → {dim}', not falt, f'{len(falt)} claves sin dimensión' + (f': {sorted(map(str, falt))[:3]}' if falt else ''))
    for dim, k in [('dim_cuenta', 'id_cuenta'), ('dim_proveedor', 'id_proveedor'), ('dim_ceco', 'id_ceco'), ('dim_vehiculo', 'id_vehiculo'),
                   ('dim_plantilla', 'id_plantilla'), ('dim_linea_pyg', 'id_linea_pyg'), ('dim_flag', 'codigo_flag')]:
        ok(f'{dim}.{k} único', G[dim][k].is_unique)
    sm = fp[fp.id_linea_pyg == 0]
    ok('Toda línea con monto mapeada al Formato Perú (N1 / N2)', sm.empty,
       f'{sm.id_linea.nunique()} líneas sin mapeo' + (f' (ej. {sm.id_linea.iloc[0]})' if len(sm) else ''))
    okp = fp[fp.estado_linea.isin(OK)].groupby(['id_pais', 'id_fecha']).monto_pen.sum()
    gd = G['fact_gestion_dirind'].groupby(['id_pais', 'id_fecha']).monto_pen.sum()
    d = okp.sub(gd, fill_value=0).abs()
    ok('Contable (líneas OK) = Gestión Dir/Ind, por país × mes (PEN)', bool((d < 0.01).all()),
       f'{int((d < 0.01).sum())} de {len(d)} país × mes; dif. máx. {d.max() if len(d) else 0:,.4f}')
    pos = fp[(fp.monto_origen > 0) & fp.estado_linea.isin(OK)]
    ok('Ningún monto positivo en líneas OK', pos.empty, f'{len(pos)} filas')
    return cu, pd.DataFrame(ctl)
