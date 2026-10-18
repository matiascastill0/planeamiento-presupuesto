"""Compactación de líneas sin perder detalle: proveedores homologados y reversas pegadas a su proveedor."""
import pandas as pd
from prov_norm import homologar_fuerte, reparar, sin_varios, exigir_sin_varios

SIN = '(sin proveedor)'
# partidas puramente contables: se muestran dentro del concepto real del gasto (misma cuenta, CeCo y proveedor)
GLOSAS_CONTABLES = {'Recuperación de provisiones', 'Liquidación de otros pasivos', 'Ajuste al mil', 'Reversa de provisiones',
                    'Reclasificación contable', 'Reclasificación de provisiones'}

def _pegar(X, col, es_hueco, k):
    """Filas 'hueco' toman el valor de col cuando, con el resto de la llave igual, existe un único valor real."""
    resto = [c for c in k if c != col]
    hueco = X[col].map(es_hueco)
    ref = X[~hueco].groupby(resto, observed=True, dropna=False)[col].agg(lambda s: s.iloc[0] if s.nunique() == 1 else None).dropna()
    if hueco.any() and len(ref):
        idx = X.loc[hueco, resto].apply(tuple, axis=1)
        X.loc[hueco, col] = [ref.get(t, v) for t, v in zip(idx, X.loc[hueco, col])]
    return X

def compactar(X, k):
    """X: movimientos con 'Proveedor_H'; k: columnas de la llave de la plantilla (incluye Proveedor_H).
    1) Unifica variantes del mismo proveedor en un único nombre estándar.
    2) Partidas contables (recuperación/reversa de provisiones, ajuste al mil...) se muestran en el concepto real
       del gasto cuando en el mismo CeCo / compañía / cuenta / proveedor hay UN solo concepto.
    3) Movimientos '(sin proveedor)' (reversas, provisiones, NIIF 16) toman el proveedor cuando en el mismo
       CeCo / compañía / cuenta / glosa existe UN solo proveedor; si hay varios o ninguno, se dejan como están."""
    X = X.copy()
    X['Proveedor_H'] = X.Proveedor_H.astype(object).map(reparar)
    X['Proveedor_H'] = [sin_varios(p, t) for p, t in zip(X.Proveedor_H, X.Texto if 'Texto' in X else [None] * len(X))]
    m = homologar_fuerte(X.Proveedor_H.unique())
    X['Proveedor_H'] = X.Proveedor_H.map(lambda v: m.get(v, v))
    X['Glosa'] = X.Glosa.astype(object)
    for _ in range(2):
        X = _pegar(X, 'Glosa', lambda g: g in GLOSAS_CONTABLES, k)
        X = _pegar(X, 'Proveedor_H', lambda p: p == SIN, k)
    from agregar import CUENTAS_CLIENTE
    X = agrupar_amplios(X, k, CUENTAS_CLIENTE)
    exigir_sin_varios(X.Proveedor_H, X['Ceco - Nombre'], 'compactar')
    return X


# --- Criterio del equipo (Ppto26): montos pequeños con apertura amplia de proveedor/cliente
#     -> una sola línea por CeCo y cuenta contable, sin proveedor, con descripción en la glosa. Nunca "Varios".
import re as _re
CTA_CLIENTE = _re.compile(r'DEUDOR|RECUPERACI[OÓ]N(?:ES)? (?:DE )?CARTERA|INCOBRABLE|REDONDEO|AJUSTE AL MIL|P[EÉ]RDIDA ESPERADA', _re.I)
MIN_PROV = 10        # desde cuántos proveedores distintos en el mismo CeCo + cuenta se considera apertura amplia
PESO_MIN = 0.10      # proveedor con >= 10% del monto del grupo conserva su línea propia

def agrupar_amplios(X, k, cuentas_cliente=()):
    X = X.copy()
    g = [c for c in k if c not in ('Proveedor_H', 'Glosa')]
    es_cli = X.Nom_Cta_Contable.astype(str).str.contains(CTA_CLIENTE) | X.Nom_Cta_Contable.isin(set(cuentas_cliente))
    if 'Nivel_2' in X:
        es_cli |= X.Nivel_2.astype(str).eq('Provisión de Incobrables')
    X['_cli'] = es_cli
    peso = X.groupby(g + ['Proveedor_H'], observed=True, dropna=False).Monto.sum().abs()
    tot = peso.groupby(level=list(range(len(g))), dropna=False).transform('sum')
    nprov = peso.groupby(level=list(range(len(g))), dropna=False).transform('size')
    cli_grp = X.groupby(g, observed=True, dropna=False)._cli.any()
    info = pd.DataFrame({'peso': peso, 'tot': tot, 'n': nprov}).reset_index()
    info['_cligrp'] = [cli_grp.get(tuple(r)) for r in info[g].itertuples(index=False)]
    # cliente: todo el grupo a una línea (si hay más de un tercero); proveedores: sólo la cola menor cuando la apertura es amplia
    info['_agrupa'] = (info._cligrp & (info.n > 1)) | ((info.n >= MIN_PROV) & (info.peso < PESO_MIN * info.tot))
    info = info.merge(info[info._agrupa].groupby(g, dropna=False).size().rename('_ncola').reset_index(), on=g, how='left')
    info.loc[info._agrupa & (info._ncola < 2) & ~info._cligrp, '_agrupa'] = False   # un solo proveedor chico: se queda con su nombre
    marca = info[info._agrupa].set_index(g + ['Proveedor_H'])._ncola
    llave = X[g + ['Proveedor_H']].apply(tuple, axis=1)
    ncola = llave.map(lambda t: marca.get(t))
    sel = ncola.notna()
    if sel.any():
        glosa_top = (X[sel].assign(_a=X.loc[sel, 'Monto'].abs()).groupby(g, observed=True, dropna=False)
                     .apply(lambda d: d.groupby('Glosa')._a.sum().idxmax()))
        gtop = X.loc[sel, g].apply(tuple, axis=1).map(lambda t: glosa_top.get(t))
        tipo = ['clientes' if c else 'proveedores menores' for c in X.loc[sel, '_cli']]
        X.loc[sel, 'Glosa'] = [f'{gl} ({int(n)} {t})' for gl, n, t in zip(gtop, ncola[sel], tipo)]
        X.loc[sel, 'Proveedor_H'] = SIN
    return X.drop(columns='_cli')
