"""Normalización fuerte de proveedores: misma empresa escrita distinto -> un solo nombre estándar."""
import re, unicodedata
from collections import Counter, defaultdict

LEGAL = {'S', 'A', 'SA', 'SAS', 'SAC', 'SAA', 'SPA', 'SRL', 'SCRL', 'EIRL', 'LTDA', 'LIMITADA', 'LTD', 'LIMITED', 'INC', 'CORP', 'CORPORATION', 'CORPORACION',
         'LLC', 'LLP', 'LP', 'PLC', 'GMBH', 'BV', 'NV', 'AG', 'SOCIEDAD', 'ANONIMA', 'CERRADA', 'ABIERTA', 'CIVIL', 'RESPONSABILIDAD', 'SOCIEDADES',
         'COMERCIAL', 'CIA', 'COMPANIA', 'CO', 'Y', 'E', 'DE', 'DEL', 'LA', 'EL', 'LOS', 'LAS', 'SUCURSAL', 'SC', 'SL', 'SE', 'CV', 'RL', 'R', 'L', 'C', 'P', 'SCP', 'THE'}

def _sa(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def fix_mojibake(s):
    if 'Ã' in s or 'Â' in s:
        try: s = s.encode('latin1').decode('utf8')
        except Exception: pass
    return s.replace('�', '').replace('Ã?', 'Ñ')

def tokens(nombre):
    s = str(nombre).replace('Ã?', '\x00').replace('\ufffd', '\x00')
    s = _sa(fix_mojibake(s)).upper().replace('\x00', '9')   # 9 = letra dañada (comodín)
    s = s.replace('&', ' AND ')
    s = re.sub(r"[^A-Z0-9 ]+", ' ', s)
    s = re.sub(r'([A-Z])9([A-Z])', lambda m: m.group(1) + '9' + m.group(2), s)
    return [t for t in s.split() if t]

def clave(nombre):
    """Clave de agrupación: tokens significativos, sin forma societaria, sin orden."""
    tk = [t for t in tokens(nombre) if t not in LEGAL]
    if not tk:
        tk = tokens(nombre)
    return ' '.join(sorted(set(tk)))

def nombre_estandar(raw):
    """Formato visible: MAYÚSCULAS, sin puntuación sobrante ni espacios dobles."""
    s = fix_mojibake(str(raw)).replace('\t', ' ')
    s = re.sub(r'\s+', ' ', s).strip(' .,;-"\'')
    s = s.upper()
    s = re.sub(r'\s*,\s*', ', ', s); s = re.sub(r'\s*-\s*', ' - ', s)
    s = re.sub(r'\bS\.? ?A\.? ?C\.?$', 'S.A.C.', s); s = re.sub(r'\bS\.? ?A\.? ?S\.?$', 'S.A.S.', s); s = re.sub(r'\bS\.? ?A\.? ?A\.?$', 'S.A.A.', s)
    s = re.sub(r'\bS\.? ?A\.?$', 'S.A.', s); s = re.sub(r'\bS\.? ?P\.? ?A\.?$', 'SPA', s); s = re.sub(r'\bLTDA\.?$', 'LTDA.', s)
    return s.strip(' ,')


ETIQUETAS = re.compile(r'^\(|^VARIOS\b')

def homologar_fuerte(serie, umbral=0.92):
    """Devuelve un dict nombre -> nombre estándar, uniendo variantes de la misma empresa:
    mayúsculas, puntuación, forma societaria, orden de palabras, letras dañadas y errores de tipeo."""
    from difflib import SequenceMatcher
    cnt = Counter(str(v) for v in serie if not ETIQUETAS.search(str(v)))
    padre = {}
    def find(k):
        padre.setdefault(k, k)
        while padre[k] != k: padre[k] = padre[padre[k]]; k = padre[k]
        return k
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: padre[rb] = ra
    por_clave = defaultdict(Counter)
    for n, c in cnt.items(): por_clave[clave(n)][n] += c
    claves = list(por_clave)
    for k in claves: find(k)
    limpias = [k for k in claves if '9' not in re.sub(r'\b\d+\b', '', k)]
    # letras dañadas (Ã?) -> comodín contra la versión sana
    for k in claves:
        if k in limpias: continue
        pat = re.compile('^' + re.sub(r'[A-Z]*9[A-Z]*', lambda m: m.group(0).replace('9', '[A-Z]{0,2}'), ' '.join(sorted(k.split()))) + '$')
        for l in limpias:
            if pat.match(l): union(l, k); break
        else:
            # token dañado completo (p.ej. SOCIEDAD AN9NIMA): comparar sin ese token
            base = ' '.join(t for t in k.split() if '9' not in t or t.isdigit())
            if base in por_clave: union(base, k)
    # errores de tipeo / letras de más: mismas palabras salvo UNA escrita parecido (CONCESIONARIA ~ CONSECIONARIA),
    # o una palabra de ruido al final (CDT, BIC, ESP, números). Números y romanos distintos NUNCA se unen (fondos II/III).
    RUIDO = {'CDT', 'BIC', 'ESP', 'LLCC', 'CIN', 'INCCI', 'FISI', 'USD'}
    ROMANO = re.compile(r'^(I|II|III|IV|V|VI|VII|VIII|IX|X)$')
    idx = defaultdict(list)
    for k in limpias:
        for t in k.split():
            if len(t) >= 4: idx[t].append(k)
    for k in limpias:
        a = set(k.split())
        cand = {c for t in a if len(t) >= 4 for c in idx[t] if c != k}
        for c in cand:
            if find(c) == find(k): continue
            b = set(c.split()); da, db = a - b, b - a
            if len(a & b) < 2 and not (len(a & b) >= 1 and len(a) == len(b) == 2): continue
            if len(da) == 1 and len(db) == 1:
                x, y = next(iter(da)), next(iter(db))
                if min(len(x), len(y)) >= 5 and not (x.isdigit() or y.isdigit() or ROMANO.match(x) or ROMANO.match(y)) \
                        and abs(len(x) - len(y)) <= 1 and x[0] == y[0] and SequenceMatcher(None, x, y).ratio() >= 0.84:
                    union(k, c)
            elif not da and db and all(t in RUIDO or (t.isdigit() and len(t) <= 3) for t in db):
                union(k, c)
            elif not db and da and all(t in RUIDO or (t.isdigit() and len(t) <= 3) for t in da):
                union(k, c)
    grupos = defaultdict(Counter)
    for k, c in por_clave.items(): grupos[find(k)].update(c)
    out = {}
    for g, c in grupos.items():
        sano = [(n, v) for n, v in c.items() if 'Ã' not in n and '\ufffd' not in n] or list(c.items())
        mejor = sorted(sano, key=lambda kv: (-kv[1], len(kv[0])))[0][0]
        std = nombre_estandar(mejor)
        for n in c: out[n] = std
    return out


# --- reparación de letras dañadas de origen ("VIÃ?A" -> "VIÑA") usando el vocabulario sano de la TD ---
_VOCAB = None
def _vocab():
    global _VOCAB
    if _VOCAB is None:
        import pandas as pd, os
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache_full.pkl')
        cnt = Counter()
        for col in ('Proveedor', 'Texto'):
            try:
                s = pd.read_pickle(f)[col].dropna().astype(str).unique()
            except Exception:
                continue
            for n in s:
                if 'Ã' in n: continue
                for t in re.findall(r'[A-ZÁÉÍÓÚÑÜ]+', n.upper()): cnt[t] += 1
        _VOCAB = cnt
    return _VOCAB

def reparar(nombre):
    s = str(nombre)
    s = s.replace('\u00c2\u00b4', "'").replace('\u00c2', '')
    if 'Ã' not in s and '�' not in s:
        return s
    s = fix_mojibake(s.replace('Ã?', '\x00').replace('�', '\x00')) if 'Ã?' not in s else s.replace('Ã?', '\x00').replace('�', '\x00')
    v = _vocab()
    def arreglar(m):
        w = m.group(0)
        if '\x00' not in w: return w
        from itertools import product
        partes = w.split('\x00')
        cands = []
        for combo in product('ÑÍÁÉÓÚ', repeat=len(partes) - 1):
            c = partes[0]
            for L, p in zip(combo, partes[1:]): c += L + p
            cands.append(c)
        mejor = max(cands, key=lambda c: (v.get(c.upper(), 0), v.get(_sa(c).upper(), 0) > 0 and c.upper().count('Ñ')))
        if v.get(mejor.upper(), 0) == 0:
            sin = [c for c in cands if v.get(_sa(c).upper(), 0)]
            mejor = sin[0] if sin else w.replace('\x00', 'Ñ')
        return mejor
    return re.sub(r'[^\s,.\-]+', arreglar, s)


VARIOS = re.compile(r'^\s*VARIO', re.I)

def sin_varios(nombre, texto=None):
    """REGLA: nunca 'Varios ...' como proveedor. Si el origen trae 'VARIOS', se toma el nombre del texto o '(sin proveedor)'."""
    if not VARIOS.search(str(nombre)):
        return nombre
    from homologacion import proveedor_desde_texto
    q = proveedor_desde_texto(texto) if texto is not None else None
    return q if q and not VARIOS.search(str(q)) else '(sin proveedor)'

def exigir_sin_varios(serie_prov, serie_ceco, etiqueta=''):
    malos = int(serie_prov.astype(str).str.match(VARIOS).sum() + serie_ceco.astype(str).str.match(VARIOS).sum())
    if malos:
        raise ValueError(f'{etiqueta}: {malos} líneas con "Varios" en Proveedor o CeCo (prohibido)')
