"""Lector genérico del caché de la tabla dinámica (.xlsb): detecta campos, inline strings y nº de filas.
Uso: python3 parse_cache_v2.py salida.pkl"""
import struct, numpy as np, pandas as pd, sys, time
from biff import recs
d = open('xl/pivotCache/pivotCacheDefinition1.bin', 'rb').read()
names, items, cur = [], [], None
def rstr(p, o):
    n = struct.unpack_from('<I', p, o)[0]; return p[o + 4:o + 4 + 2 * n].decode('utf-16le'), o + 4 + 2 * n
for t, i, s in recs(d):
    p = d[i:i + s]
    if t == 183:
        n = struct.unpack_from('<I', p, 20)[0]; names.append(p[24:24 + 2 * n].decode('utf-16le')); cur = []; items.append(cur)
    elif t == 191:
        typ, cnt = struct.unpack_from('<HI', p, 0); o = 6
        for _ in range(cnt):
            if typ == 2: v, o = rstr(p, o)
            elif typ == 0x20: y, m, dd = struct.unpack_from('<HHB', p, o); v = f'{y:04d}-{m:02d}-{dd:02d}'; o += 8
            else: raise Exception(('runtype', typ))
            cur.append(v)
    elif t in (31, 24, 26) and cur is not None: cur.append(rstr(p, 0)[0])
    elif t in (20, 27) and cur is not None: cur.append(None)
    elif t == 32 and cur is not None: y, m, dd = struct.unpack_from('<HHB', p, 0); cur.append(f'{y:04d}-{m:02d}-{dd:02d}')
NF = 30                                   # campos con datos en los registros (los demás son agrupaciones)
names = names[:NF]; items = items[:NF]
NUM = [k for k in range(NF) if names[k] in ('Monto', 'Monto_USD_Oficial', 'Monto_PEN_Oficial', 'Monto_USD_Cumplimiento', 'Monto_PEN_Cumplimiento')]
STR = [k for k in range(NF) if len(items[k]) == 0 and k not in NUM]
GUARDAR = [k for k in STR if names[k] in ('Nivel_4', 'Factura', 'Nom_CeCo')]
print('NUM', [names[k] for k in NUM], '| STR inline', [names[k] for k in STR])
r = open('xl/pivotCache/pivotCacheRecords1.bin', 'rb').read()
N = sum(1 for t, i, s in recs(r) if t in (33, 34)); print('filas', N, flush=True)
codes = np.full((N, NF), -1, dtype=np.int32); nums = np.zeros((N, len(NUM))); strs = {k: [None] * N for k in GUARDAR}
row = -1; dyn = -1; unp = struct.unpack_from; t0 = time.time()
for t, i, s in recs(r):
    if t == 33:
        row += 1; o = i
        for k in range(NF):
            if k in STR:
                n = unp('<I', r, o)[0]
                if k in strs: strs[k][row] = r[o + 4:o + 4 + 2 * n].decode('utf-16le')
                o += 4 + 2 * n
            elif k in NUM: nums[row, NUM.index(k)] = unp('<d', r, o)[0]; o += 8
            else: codes[row, k] = unp('<I', r, o)[0]; o += 4
    elif t == 34: row += 1; dyn = 0
    elif t in (26, 21, 20, 24) and dyn >= 0:
        k = dyn
        if t == 26: codes[row, k] = unp('<I', r, i)[0]
        elif t == 21: nums[row, NUM.index(k)] = unp('<d', r, i)[0]
        elif t == 24:
            if k in strs: strs[k][row] = rstr(r, i)[0]
        dyn += 1
        if dyn == NF: dyn = -1
    if t == 33 and row % 1000000 == 0: print(row, round(time.time() - t0), flush=True)
df = {}
for k in range(NF):
    if k in NUM: df[names[k]] = nums[:, NUM.index(k)]
    elif k in STR: df[names[k]] = strs[k] if k in strs else [None] * N
    else:
        vals = np.array([(x if x is not None else '(blank)') for x in items[k]], dtype=object)
        c = codes[:, k]; df[names[k]] = pd.Categorical(np.where(c >= 0, vals[np.clip(c, 0, max(len(vals) - 1, 0))] if len(vals) else '(blank)', '(blank)'))
df = pd.DataFrame(df); df.to_pickle(sys.argv[1]); print(df.shape)
