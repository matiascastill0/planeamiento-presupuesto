"""Encaje de líneas generadas (llave de plantilla) en las filas existentes de una plantilla oficial, sin tocarlas.
Niveles (sólo se usa un nivel >1 si la fila candidata es ÚNICA):
 1 exacto: vehículo, CeCo, cuenta, Nivel 2, Nivel 3, sede, proveedor, glosa
 2 igual salvo glosa
 3 igual salvo proveedor
 4 vehículo, CeCo, cuenta, Nivel 2, Nivel 3 (una sola fila para esa cuenta en ese CeCo)
 sin encaje -> fila nueva (amarilla)."""
import re, unicodedata, pandas as pd
from prov_norm import clave as clave_prov

def nk(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return ''
    s = str(v).strip()
    if s in ('nan', 'None', '(sin dato)', '(blank)'): return ''
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'[^A-Z0-9]+', ' ', s).strip()

def kprov(v):
    s = nk(v)
    if s in ('', 'SIN PROVEEDOR'): return 'SIN'
    return clave_prov(str(v)) or s

def kglosa(v):
    return nk(re.sub(r'\(\d+ (clientes|proveedores menores)\)', '', str(v) if v is not None else ''))

def kceco(v):
    m = re.match(r'\s*(\d+)', str(v))
    if not m: return nk(v)
    c = m.group(1)
    return c[-3:] if len(c) == 6 and c.startswith('211') else c      # Panamá: 211248 = 248

def raw(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return ''
    s = str(v).strip()
    return '' if s in ('nan', 'None', '(sin dato)', '(blank)') else re.sub(r'\s+', ' ', s)

def claves(D):
    K = pd.DataFrame(index=D.index)
    for c, n in [('Vehículo', 'r_veh'), ('Ceco - Nombre', 'r_ceco'), ('Nom Cta Contable', 'r_cta'), ('Nivel 2', 'r_n2'), ('Nivel 3', 'r_n3'),
                 ('Sede', 'r_sede'), ('Proveedor', 'r_prov'), ('Glosa / Texto', 'r_glo')]:
        K[n] = D[c].map(raw)
    K['veh'] = D['Vehículo'].map(nk); K['ceco'] = D['Ceco - Nombre'].map(kceco); K['cta'] = D['Nom Cta Contable'].map(nk)
    K['n2'] = D['Nivel 2'].map(nk); K['n3'] = D['Nivel 3'].map(nk); K['sede'] = D['Sede'].map(nk)
    K['prov'] = D['Proveedor'].map(kprov); K['glo'] = D['Glosa / Texto'].map(kglosa)
    return K

NIVELES = {0: ['r_veh', 'r_ceco', 'r_cta', 'r_n2', 'r_n3', 'r_sede', 'r_prov', 'r_glo'],
           1: ['veh', 'ceco', 'cta', 'n2', 'n3', 'sede', 'prov', 'glo'],
           2: ['veh', 'ceco', 'cta', 'n2', 'n3', 'sede', 'prov'],
           3: ['veh', 'ceco', 'cta', 'n2', 'n3', 'sede', 'glo'],
           4: ['veh', 'ceco', 'cta', 'n2', 'n3']}

def encajar(G, T):
    """G: líneas generadas (KEY + ...), T: filas de la plantilla (con 'fila'). Devuelve G con columnas fila (o None) y nivel."""
    kg, kt = claves(G), claves(T)
    kt['fila'] = T['fila'].values
    # columnas que el generador no produce (p.ej. Nivel 3 propio del equipo en Remuneración, Sede) se tratan como comodín
    comodin = [c for c in ('n3', 'sede') if (kg[c] == '').all() and (kt[c] != '').any()]
    fila = pd.Series(None, index=G.index, dtype=object); nivel = pd.Series(0, index=G.index)
    for n, cols in NIVELES.items():
        cols = [c for c in cols if c not in comodin and c.replace('r_', '') not in comodin]
        grp = kt.groupby(cols).fila.agg(list)
        pend = fila.isna()
        if not pend.any(): break
        tup = kg.loc[pend, cols].apply(tuple, axis=1)
        cand = tup.map(lambda t: grp.get(t))
        ok = cand.map(lambda c: c is not None and (len(c) == 1 or n <= 1))
        idx = ok[ok].index
        fila[idx] = cand[idx].map(lambda c: c[0]); nivel[idx] = n
    G = G.copy(); G['fila'] = fila; G['nivel'] = nivel
    return G


# ---------- plantillas en "formato texto" (armadas por el equipo: sin cuenta ni proveedor; glosa = texto del movimiento) ----------
from difflib import SequenceMatcher
def ktexto(v):
    s = nk(v)
    s = re.sub(r'\b\d+\b', ' ', s); s = re.sub(r'\bX{3,}\w*', ' ', s)
    s = re.sub(r'\b(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|SET|OCT|NOV|DIC|ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE|JAN|APR|AUG|DEC)\b', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def es_formato_texto(T):
    return len(T) > 0 and T['Nom Cta Contable'].isna().mean() > 0.5 and T['Proveedor'].isna().mean() > 0.5

def encajar_texto(X, T):
    """X: filas crudas (esquema TD) de la unidad/país; T: filas de la plantilla. Devuelve X con fila (o None) y nivel."""
    t = T.assign(veh=T['Vehículo'].map(nk), ceco=T['Ceco - Nombre'].map(kceco), n2=T['Nivel 2'].map(nk), g=T['Glosa / Texto'].map(ktexto))
    cand = {k: list(zip(g.fila, g.g)) for k, g in t.groupby(['veh', 'ceco', 'n2'])}
    fila, nivel = [], []
    for veh, ce, n2, tx, cta in zip(X['Compañía'].map(nk), X.CeCo.map(lambda v: kceco(str(v)[-3:] if len(str(v)) == 6 and str(v).startswith('211') else v)),
                                    X.Nivel_2.map(nk), X.Texto.map(ktexto), X.Nom_Cta_Contable.map(ktexto)):
        c = cand.get((veh, ce, n2), [])
        f = n = None
        for fl, g in c:
            if g and g == tx: f, n = fl, 1; break
        if f is None:
            for fl, g in c:
                if g and len(g) >= 8 and (tx.startswith(g) or g.startswith(tx)) and len(tx) >= 8: f, n = fl, 2; break
        if f is None:
            for fl, g in c:
                if g and g == cta: f, n = fl, 3; break
        if f is None and c:
            best = max(c, key=lambda z: SequenceMatcher(None, z[1], tx).ratio())
            if SequenceMatcher(None, best[1], tx).ratio() >= 0.8: f, n = best[0], 4
        fila.append(f); nivel.append(n or 0)
    X = X.copy(); X['fila'] = fila; X['nivel'] = nivel
    return X
