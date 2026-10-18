"""Silver del Ppto27: versión vigente de cada plantilla, montos interpretados, textos limpios, cuentas y proveedores
homologados, flags (catálogo F/L/C/M/T) y estado de cada línea (OK · OK con alerta · Cuarentena · Rechazada).

Python puro sobre pandas: el notebook 20_silver lee las tablas bronze, llama a `silver()` y escribe el resultado.
La misma función corre en local para las pruebas.
"""
import json, re
from collections import Counter, defaultdict
import pandas as pd
import ppto27_lib as L

MONEDAS = {'PEN', 'COP', 'CLP', 'USD', 'MXN'}
MONEDA_PAIS = {'Perú': {'PEN', 'USD'}, 'Colombia': {'COP', 'USD'}, 'Chile': {'CLP', 'USD'}, 'Panamá': {'USD'}, 'USA': {'USD'},
               'México': {'PEN', 'MXN', 'USD'}}                                  # México se presupuesta en PEN
PAISES_OK = set(L.PAISES.values())
HOJAS_STD = {'Ppto27', 'Tablas', 'TD - Ppto26', 'BD - Ppto26'}
CAMPOS_CLAVE = [0, 1, 2, 4, 5, 6, 9, 10, 12]                                      # textos que identifican una línea
IDX = {c: i for i, c in enumerate(L.COLUMNAS)}
MONTOS = L.COL_REAL + [f'fc_2026_{m:02d}' for m in range(9, 13)] + L.COL_PPTO
CALC = ['f26', 'p27', 'var_pct', 'var_abs']
ES_REF = re.compile(r'^REF_', re.I)                                             # cargas de referencia (versión enviada)


def _n(v):
    return re.sub(r'\s+', ' ', str(v).replace('\xa0', ' ')).strip() if v is not None else ''


# ───────────────────────────── 1) versión vigente de cada plantilla ─────────────────────────────
def _carpeta(idp):
    return idp.rsplit(' | ', 1)[0]


def resolver_ids(A, maestro):
    """id_plantilla de cada archivo contra el maestro, de lo más estricto a lo más flexible:
    1) id exacto (carpeta + nombre) · 2) misma carpeta, si ahí hay una sola plantilla (el área renombró el archivo) ·
    3) mismo id sin el rubro (se subió sólo la subcarpeta, p. ej. "CS ADMINISTRATIVO/…") ·
    4) mismo nombre de archivo + país, si es único en el maestro (se subieron los Excel sueltos).
    Si nada coincide queda su id propio y silver lo marca F14 (asignar en alias_plantilla)."""
    M = maestro if isinstance(maestro, pd.DataFrame) else pd.DataFrame({'id_plantilla': list(maestro)})
    ids = list(M.id_plantilla)
    unico = lambda claves: {k: v[0] for k, v in pd.Series(ids).groupby(claves).agg(list).items() if len(v) == 1}
    por_carpeta = unico([_carpeta(i) for i in ids])
    sin_rubro = unico([i.split(' | ', 1)[1] if ' | ' in i else i for i in ids])
    por_nombre = unico([f"{p}|{b}" for p, b in zip(M.pais, M.nombre_base)]) if {'pais', 'nombre_base'} <= set(M.columns) else {}
    out = []
    for r in A.itertuples():
        i = r.id_plantilla
        if i in set(ids):
            out.append(i)
            continue
        cand = (por_carpeta.get(_carpeta(i)) or sin_rubro.get(i.split(' | ', 1)[1] if ' | ' in i else i)
                or por_nombre.get(f"{getattr(r, 'pais_carpeta', '')}|{getattr(r, 'nombre_base', '')}"))
        out.append(cand or i)
    return out


def elegir_versiones(A, alias_plantilla=None, referencia=False, maestro_plantillas=None):
    """brz_archivos (historial completo) → una fila por id_plantilla con la última versión recibida.
    Las cargas REF_* son la versión enviada (para comparar) y no cuentan como entrega, salvo referencia=True."""
    orig = A[A.estado != 'REPETIDO'].sort_values('carga_id').drop_duplicates('sha256').set_index('sha256')   # lectura original de cada hash
    A = A[A.carga_id.str.match(ES_REF) == referencia].copy()
    if A.empty:
        return A
    if alias_plantilla is not None and len(alias_plantilla):
        m = {**dict(zip(alias_plantilla.ruta_o_archivo.astype(str), alias_plantilla.id_plantilla))}
        A['id_plantilla'] = [m.get(r, m.get(a, i)) for r, a, i in zip(A.ruta_relativa, A.archivo, A.id_plantilla)]
    if maestro_plantillas is not None:
        A['id_plantilla'] = resolver_ids(A, maestro_plantillas)
    # última versión: carga más reciente y, dentro de la misma carga, el archivo modificado más tarde
    A['_mod'] = pd.to_datetime(A['modificado'], errors='coerce') if 'modificado' in A else pd.NaT
    A = A.sort_values(['carga_id', '_mod', 'ruta_relativa'])
    nver = A.groupby('id_plantilla').sha256.nunique()
    sel = A.groupby('id_plantilla').tail(1).copy()
    sel['n_versiones'] = sel.id_plantilla.map(nver)
    misma = A.merge(sel[['id_plantilla', 'carga_id', 'sha256']].rename(columns={'sha256': '_vig'}), on=['id_plantilla', 'carga_id'])
    otras = misma[misma.sha256 != misma._vig].groupby('id_plantilla').ruta_relativa.agg(lambda s: ' | '.join(sorted(set(s))))
    sel['otras_misma_carga'] = sel.id_plantilla.map(otras)
    sel = sel.drop(columns='_mod')
    rep = list(sel.estado.eq('REPETIDO'))
    for c in ['estado', 'error', 'hojas', 'tablas_oculta', 'ref_tabla', 'encabezado', 'n_lineas', 'fila_totales', 'tc', 'fuera_tabla',
              'listas', 'leyenda']:
        if c in sel:
            sel[c] = [orig.at[h, c] if r and h in orig.index else v for h, r, v in zip(sel.sha256, rep, sel[c])]
    sel = sel.reset_index(drop=True)
    return sel.astype(object).where(sel.notna(), None)                         # NaN → None (textos JSON opcionales)


def lineas_de(sel, LIN):
    """Filas bronze de las versiones elegidas (por hash), con el id_plantilla vigente."""
    sha_id = sel.drop_duplicates('sha256').set_index('sha256').id_plantilla
    X = LIN[LIN.sha256.isin(sha_id.index)].sort_values(['carga_id']).drop_duplicates(['sha256', 'fila']).copy()
    X['id_plantilla'] = X.sha256.map(sha_id)
    return X.astype(object).where(X.notna(), None)


# ───────────────────────────── 2) silver ─────────────────────────────
def homologadores(M, AL):
    al = lambda h: dict(zip(AL[h].alias.astype(str), AL[h].oficial.astype(str))) if h in AL and len(AL[h]) else {}
    hc = L.Homologador(M['cuentas'].nom_cta_contable.dropna().astype(str), L.clave_texto, al('alias_cuenta'), umbral=0.90)
    hp = L.Homologador(M['proveedores'].proveedor_oficial.dropna().astype(str).unique(), L.clave_proveedor, al('alias_proveedor'),
                       umbral=0.92)
    return hc, hp


def flags_archivo(sel, M):
    """Flags de archivo (F01–F16) de las versiones vigentes. Tabla chica: corre en el driver (pandas o Spark).
    Devuelve (dict id_plantilla → [flags], set de id_plantilla bloqueados)."""
    ids_maestro = set(M['plantillas'].id_plantilla)
    tc_m = {(r.moneda, int(r.mes)): float(r.unidades_por_usd) for r in M['tipo_cambio'].itertuples()}
    sha_ids = sel.groupby('sha256').id_plantilla.agg(list)
    FA = defaultdict(list)
    for a in sel.itertuples():
        idp = a.id_plantilla
        def flag(cod, fila=None, celdas='', detalle='', idp=idp):
            FA[idp].append(dict(id_plantilla=idp, id_linea=f'{idp}#{fila}' if fila else None, fila=fila, codigo_flag=cod,
                                severidad=L.SEVERIDAD[cod], celdas=celdas, detalle=str(detalle)[:300]))
        if a.estado == 'RECHAZADO':
            flag((a.error or 'F16')[:3], None, '', a.error)
        if idp not in ids_maestro:
            flag('F14', None, '', f'{a.ruta_relativa}')
        if len(sha_ids.get(a.sha256, [])) > 1 and sha_ids[a.sha256][0] != idp:
            flag('F10', None, '', 'Mismo contenido que: ' + sha_ids[a.sha256][0])
        if getattr(a, 'otras_misma_carga', None):
            flag('F17', None, '', f'Vigente: {a.ruta_relativa} · descartada(s): {a.otras_misma_carga}')
        if (a.n_versiones or 1) > 1:
            flag('F15', None, '', f'{a.n_versiones} versiones; vigente: carga {a.carga_id}')
        if a.estado != 'RECHAZADO':
            enc = json.loads(a.encabezado or '[]')[:L.NCOL]
            dif = [(L._col(i + 1), e, x) for i, (e, x) in enumerate(zip(L.ENCABEZADO, enc)) if _n(e) != _n(x)]
            if dif:
                mov = [d for d in dif if _n(d[2]) in {_n(e) for e in L.ENCABEZADO}]
                flag('F03' if mov else 'F04', None, ', '.join(d[0] for d in dif),
                     '; '.join(f'{c}: "{x}" (esperado "{_n(e)}")' for c, e, x in dif))
            if a.fuera_tabla:
                fu = json.loads(a.fuera_tabla)
                flag('F05', None, f'{fu[0][0]}…{fu[-1][0]}', f'{len(fu)} celdas. Ej.: ' + '; '.join(f'{c}={v}' for c, v in fu[:4]))
            if (a.fila_totales or 0) > 0:
                flag('F06', None, '', 'Fila de totales activada en Tabla1')
            hojas = set(json.loads(a.hojas or '[]'))
            if not hojas <= HOJAS_STD or (a.tablas_oculta is not None and not bool(a.tablas_oculta)):
                flag('F08', None, '', f'Hojas: {sorted(hojas)} · Tablas oculta: {a.tablas_oculta}')
            if a.tc:
                tc = json.loads(a.tc)
                d = [f'{mon} {m + 1}' for mon, vals in tc.items() for m, v in enumerate(vals)
                     if v is None or abs(v - tc_m.get((mon, m + 1), v)) > 0.005]
                if d:
                    flag('F13', 3, 'AA3:AL5', f'TC distinto al maestro en {len(d)} celdas: {", ".join(d[:6])}')
    bloq = {i for i, fs in FA.items() if any(f['severidad'] == 'BLOQUEANTE' for f in fs)}
    return dict(FA), bloq


def silver(sel, LIN, M, AL, REF=None):
    """sel: versiones vigentes (elegir_versiones) · LIN: filas bronze de esas versiones (lineas_de) ·
    M: maestros (dict de DataFrames) · AL: alias · REF: filas bronze de la versión enviada (opcional, para flags C).
    Devuelve dict(lineas, flags, archivos)."""
    hc, hp = homologadores(M, AL)
    FA, bloq = flags_archivo(sel, M)
    veh = defaultdict(set)
    for r in M['vehiculos'].itertuples():
        veh[r.pais].add(str(r.vehiculo))
    cecos = {(r.pais, int(r.ceco)): (r.agrupacion_drivers if isinstance(r.agrupacion_drivers, str) else r.agrupacion)
             for r in M['cecos'].itertuples()}
    sha_ids = sel.groupby('sha256').id_plantilla.agg(list)
    ref_por_id = dict(tuple(REF.groupby('id_plantilla'))) if REF is not None and len(REF) else {}
    lin_por_sha = dict(tuple(LIN.groupby('sha256')))

    FL, OUT, ARCH = [], [], []
    for a in sel.itertuples():
        idp = a.id_plantilla
        def flag(cod, fila=None, celdas='', detalle=''):
            FL.append(dict(id_plantilla=idp, id_linea=f'{idp}#{fila}' if fila else None, fila=fila, codigo_flag=cod,
                           severidad=L.SEVERIDAD[cod], celdas=celdas, detalle=str(detalle)[:300]))
        FL.extend(FA.get(idp, []))
        bloqueado = idp in bloq

        # ── líneas
        X = lin_por_sha.get(a.sha256)
        lineas = [] if X is None or (len(sha_ids.get(a.sha256, [])) > 1 and sha_ids[a.sha256][0] != idp) else X.to_dict('records')
        crudos = {l['fila']: [l.get(c) for c in L.COLUMNAS] for l in lineas}
        clave = lambda c: tuple(_n(c[i]).upper() for i in CAMPOS_CLAVE)
        vistos = Counter(clave(c) for c in crudos.values() if any(c[i] for i in range(13)))
        # versión enviada: líneas con Real por clave de textos
        env, env_alt, usados = defaultdict(list), {}, set()
        for r in (ref_por_id.get(idp).to_dict('records') if idp in ref_por_id else []):
            c = [r.get(k) for k in L.COLUMNAS]
            real = tuple(round(L.monto(r[k], r['tipos'][IDX[k]], None)[0] or 0, 2) for k in L.COL_REAL)
            if any(real):
                env[clave(c)].append((r['fila'], real, c))
                env_alt[(_n(c[2]).upper(), _n(c[4]).upper(), tuple(round(x) for x in real))] = (r['fila'], c)
        p27_archivo = 0.0
        for l in lineas:
            f, c, tipos = l['fila'], crudos[l['fila']], l['tipos'] or '-' * L.NCOL
            fml = json.loads(l['formulas']) if l.get('formulas') else {}
            textos = [c[i] for i in range(13)]
            parse, por_cod = {}, defaultdict(list)
            for k in MONTOS:
                v, cod, det = L.monto(l[k], tipos[IDX[k]], fml.get(k))
                parse[k] = v
                if cod:
                    por_cod[cod].append((f'{L._col(IDX[k] + 1)}{f}', det))
            ppto = [parse[k] for k in L.COL_PPTO]
            p27_archivo += sum(v or 0 for v in ppto)
            if not any(t for t in textos) and not any(v for v in parse.values()):
                flag('L12', f)
                continue
            for cod, xs in por_cod.items():
                flag(cod, f, ', '.join(x[0] for x in xs), f'{len(xs)} celdas · ' + '; '.join(dict.fromkeys(x[1] for x in xs)))
            cl = lambda ks: ', '.join(f'{L._col(IDX[k] + 1)}{f}' for k in ks)
            real = [parse[k] for k in L.COL_REAL]
            pos = [k for k in L.COL_PPTO if (parse[k] or 0) > 0]
            if pos:
                flag('M01', f, cl(pos), ', '.join(f'{L.ENCABEZADO[IDX[k]]}={parse[k]:,.2f}' for k in pos[:6]))
            if any((v or 0) > 0 for v in real):
                flag('M10', f, cl([k for k in L.COL_REAL if (parse[k] or 0) > 0]))
            dec = [k for k in L.COL_PPTO if parse[k] is not None and abs(parse[k] * 100 - round(parse[k] * 100)) > 1e-6]
            if dec:
                flag('M12', f, cl(dec))
            fc = [k for k in MONTOS if k.startswith('fc_') and parse[k]]
            if fc:
                flag('M17', f, cl(fc))
            for k in CALC:
                if l[k] is not None and tipos[IDX[k]] not in '-' and tipos[IDX[k]].islower() and tipos[IDX[k]] != 'f':
                    flag('M16', f, f'{L._col(IDX[k] + 1)}{f}', f'{k} = {l[k]!r} (valor en vez de fórmula)')
            p27 = sum(v or 0 for v in ppto)
            r_anual = sum(v or 0 for v in real) / 8 * 12
            com = _n(c[11])
            if p27:
                act = sum(1 for v in real if v)
                if sum(1 for v in ppto if v) == 1 and act >= 6:
                    flag('M13', f, cl([k for k in L.COL_PPTO if parse[k]]), f'P27 {p27:,.0f} en un mes; Real con {act} meses')
                if r_anual < 0 and abs(p27 / r_anual - 1) > 0.5 and not com:
                    flag('M14', f, '', f'P27 {p27:,.0f} vs Real anualizado {r_anual:,.0f} ({p27 / r_anual - 1:+.0%})')
                if r_anual and (p27 / r_anual > 500 or 0 < p27 / r_anual < 1 / 500):
                    flag('M15', f, '', f'P27 / Real anualizado = {p27 / r_anual:,.4g}')
            # identidad
            pais, vh, ceco_txt, n1, n2, mon, glosa = (L.limpiar(c[0]) or '', L.limpiar(c[1]) or '', L.limpiar(c[2]) or '',
                                                     L.limpiar(c[5]) or '', L.limpiar(c[6]) or '', (L.limpiar(c[12]) or '').upper(),
                                                     L.limpiar(c[10]))
            if pais not in PAISES_OK:
                alt = {L.sin_tildes(x).upper(): x for x in PAISES_OK}.get(L.sin_tildes(pais).upper())
                if alt:
                    flag('T06', f, f'A{f}', pais)
                    pais = alt
                else:
                    flag('L01', f, f'A{f}', pais or '(vacío)')
            if pais in PAISES_OK and a.pais_carpeta in PAISES_OK and pais != a.pais_carpeta:
                flag('F11', f, f'A{f}', f'{pais} en plantilla de {a.pais_carpeta}')
            if vh not in veh.get(pais, set()):
                alt = {x.upper(): x for x in veh.get(pais, set())}.get(L.sin_tildes(vh).upper())
                if alt:
                    flag('T06', f, f'B{f}', vh)
                    vh = alt
                else:
                    flag('L02', f, f'B{f}', f'"{vh}" no es vehículo de {pais}')
            cn = L.ceco_num(ceco_txt)
            if cn is None or not re.match(r'^\d+\s*-\s*\S', ceco_txt) or 'VARIOS' in ceco_txt.upper():
                flag('L03', f, f'C{f}', ceco_txt or '(vacío)')
            elif (pais, cn) not in cecos:
                flag('L04', f, f'C{f}', ceco_txt)
            k1, k2 = L.clave_texto(n1), L.clave_texto(n2)
            if k1 not in L.NIVEL2_DE:
                flag('L05', f, f'F{f}', n1 or '(vacío)')
            elif k2 not in L.NIVEL2_DE[k1]:
                flag('L06', f, f'G{f}', f'"{n2}" no es de {n1}')
            cta, met_c, fl_c = L.homologar_cuenta(hc, c[4])
            if fl_c:
                flag(fl_c, f, f'E{f}', f'"{c[4]}" → "{cta}"' if fl_c != 'L17' else f'"{c[4]}"')
            prov, met_p, fl_p = L.homologar_proveedor(hp, c[9])
            if fl_p:
                flag(fl_p, f, f'J{f}', f'"{c[9]}" → "{prov}"' if fl_p == 'L19' else f'"{c[9]}"')
            if mon not in MONEDAS:
                flag('L09', f, f'M{f}', mon or '(vacío)')
            elif pais in MONEDA_PAIS and mon not in MONEDA_PAIS[pais]:
                flag('L10', f, f'M{f}', f'{mon} en {pais}')
            if not glosa:
                flag('L11', f, f'K{f}')
            if vistos[clave(c)] > 1:
                flag('L13', f, '', f'{vistos[clave(c)]} líneas con los mismos textos')
            esp = L.agrupacion_esperada(a.tipo, a.area)
            ag = cecos.get((pais, cn)) if cn else None
            if esp and ag and L.clave_texto(ag) != L.clave_texto(esp):
                flag('L14', f, f'C{f}', f'{ceco_txt} es de "{ag}" y viene en la plantilla de "{esp}"')
            for i in range(13):
                v = c[i]
                if not isinstance(v, str):
                    continue
                col = f'{L._col(i + 1)}{f}'
                if L.MOJIBAKE.search(v):
                    flag('T01', f, col, v)
                if L.INVISIBLES.search(v):
                    flag('T03', f, col, repr(v))
                if v != v.strip() or '  ' in v or '\xa0' in v or '\n' in v:
                    flag('T02', f, col, repr(v))
                if len(v) > 255:
                    flag('T04', f, col, f'{len(v)} caracteres')
                if re.search(r'[;|\t]', v):
                    flag('T05', f, col, v[:80])
            # cambios contra la versión enviada (solo alerta: el Real oficial sale de la TD)
            rr = tuple(round(v or 0, 2) for v in real)
            if env and any(rr):
                cand = [x for x in env.get(clave(c), []) if x[0] not in usados]
                if cand:
                    fe, re_env, _ = min(cand, key=lambda x: sum(abs(p - q) for p, q in zip(x[1], rr)))
                    usados.add(fe)
                    dm = [(i + 1, re_env[i], rr[i]) for i in range(8) if abs(re_env[i] - rr[i]) > 0.005]
                    if dm:
                        flag('C02', f, '', '; '.join(f'mes {m}: enviado {p:,.2f} → {q:,.2f}' for m, p, q in dm[:4]))
                else:
                    alt = env_alt.get((_n(c[2]).upper(), _n(c[4]).upper(), tuple(round(x) for x in rr)))
                    if alt and alt[0] not in usados:
                        usados.add(alt[0])
                        cols = [L.ENCABEZADO[i].split('\n')[0] for i in CAMPOS_CLAVE if _n(alt[1][i]).upper() != _n(c[i]).upper()]
                        flag('C03', f, '', 'Cambió: ' + ', '.join(cols))
                    else:
                        flag('C01', f, cl([k for k in L.COL_REAL if parse[k]]), f'Real {sum(rr):,.2f} en línea que no estaba en la versión enviada')
            OUT.append(dict(
                id_linea=f'{idp}#{f}', id_plantilla=idp, carga_id=a.carga_id, sha256=a.sha256, fila=int(f),
                rubro_cod=a.rubro_cod, rubro=a.rubro, sub_rubro=a.sub_rubro, tipo=a.tipo, area=a.area, pais_carpeta=a.pais_carpeta,
                pais=pais or None, vehiculo=vh or None, ceco_nombre=ceco_txt or None, ceco=cn, sede=L.limpiar(c[3]),
                nom_cta_contable=L.limpiar(c[4]), cuenta_oficial=cta, metodo_cuenta=met_c,
                nivel_1=n1 or None, nivel_2=n2 or None, nivel_3=L.limpiar(c[7]), nivel_4=L.limpiar(c[8]),
                id_linea_pyg=L.MAPA_PYG.get((k1, k2), 0),
                proveedor=L.limpiar(c[9]), proveedor_oficial=prov, metodo_proveedor=met_p,
                glosa=glosa, comentario_area=L.limpiar(c[11]), moneda=mon or None,
                **{k: parse[k] for k in L.COL_REAL}, **{k: parse[k] for k in L.COL_PPTO},
                real_ene_ago=sum(v or 0 for v in real), p27=p27))
        for fe_list in env.values():
            for fe, re_env, cr in fe_list:
                if fe not in usados:
                    flag('C04', None, f'(enviado fila {fe})', f'{_n(cr[2])} · {_n(cr[9])} · {_n(cr[10])} · Real {sum(re_env):,.2f}')
        ARCH.append(dict(id_plantilla=idp, carga_id=a.carga_id, sha256=a.sha256, ruta_relativa=a.ruta_relativa, archivo=a.archivo,
                         rubro_cod=a.rubro_cod, rubro=a.rubro, sub_rubro=a.sub_rubro, tipo=a.tipo, area=a.area,
                         pais_carpeta=a.pais_carpeta, n_versiones=int(a.n_versiones or 1), bloqueado=bloqueado,
                         p27_archivo=round(p27_archivo, 6), lineas_bronze=len(lineas)))

    FLG = pd.DataFrame(FL, columns=['id_plantilla', 'id_linea', 'fila', 'codigo_flag', 'severidad', 'celdas', 'detalle'])
    LIN_S = pd.DataFrame(OUT)
    ARC = pd.DataFrame(ARCH)
    # estado de cada línea = peor severidad de sus flags; archivo con BLOQUEANTE → todas sus líneas rechazadas
    orden = {s: i for i, s in enumerate(L.SEV_ORDEN)}
    peor = FLG.dropna(subset=['id_linea']).groupby('id_linea').severidad.agg(lambda s: min(s, key=orden.get))
    cods = FLG.dropna(subset=['id_linea']).groupby('id_linea').codigo_flag.agg(lambda s: ', '.join(sorted(set(s))))
    bloq = set(ARC.loc[ARC.bloqueado, 'id_plantilla']) if len(ARC) else set()
    if len(LIN_S):
        LIN_S['severidad_max'] = LIN_S.id_linea.map(peor)
        LIN_S['flags'] = LIN_S.id_linea.map(cods).fillna('')
        LIN_S['estado_linea'] = ['Rechazada (archivo)' if p in bloq else 'Cuarentena' if s in ('BLOQUEANTE', 'ERROR')
                                 else 'OK con alerta' if s == 'ALERTA' else 'OK' for p, s in zip(LIN_S.id_plantilla, LIN_S.severidad_max)]
        ok = LIN_S.estado_linea.isin(['OK', 'OK con alerta'])
        g = LIN_S.assign(ok=ok).groupby('id_plantilla')
        ARC['lineas'] = ARC.id_plantilla.map(g.size()).fillna(0).astype(int)
        ARC['lineas_ok'] = ARC.id_plantilla.map(g.ok.sum()).fillna(0).astype(int)
        ARC['p27_ok'] = ARC.id_plantilla.map(LIN_S[ok].groupby('id_plantilla').p27.sum()).fillna(0.0)
        ARC['p27_cuarentena'] = ARC.id_plantilla.map(LIN_S[~ok].groupby('id_plantilla').p27.sum()).fillna(0.0)
    n = FLG.groupby(['id_plantilla', 'severidad']).size().unstack(fill_value=0) if len(FLG) else pd.DataFrame()
    for s in L.SEV_ORDEN:
        ARC[s.lower()] = ARC.id_plantilla.map(n[s] if s in n else {}).fillna(0).astype(int)
    ARC['estado_archivo'] = ['Rechazado' if b else 'Con errores' if e else 'Con alertas' if al else 'OK'
                             for b, e, al in zip(ARC.bloqueante, ARC.error, ARC.alerta)]
    return dict(lineas=LIN_S, flags=FLG, archivos=ARC)
