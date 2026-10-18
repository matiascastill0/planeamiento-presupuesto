"""Guardia del repositorio: falla si hay datos reales, secretos o notebooks con salidas.

Uso:  python herramientas/verificar_repo.py      (lo corre la CI en cada push y PR)
"""
import hashlib, json, os, re, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROHIBIDAS = {'.xlsx', '.xlsm', '.xlsb', '.xls', '.pkl', '.parquet', '.zip', '.pbix', '.abf'}
CSV_PERMITIDO = ('datos-simulados/CSV/', 'datos-simulados/catalogos/')
PATRONES = {
    'host de Databricks': r'adb-\d{6,}\.\d+\.azuredatabricks',
    'HTTP path de warehouse': r'/sql/1\.0/warehouses/[0-9a-f]{8,}',
    'token de Databricks': r'dapi[0-9a-f]{20,}',
    'ruta personal (Mac)': r'/Users/(?!Shared)[A-Za-z0-9._-]+/',
    'ruta personal (Windows)': r'[A-Za-z]:\\\\?Users\\\\?[A-Za-z0-9._-]+',
    'correo electrónico': r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.(?:com|pe|co|cl|net|org)\b',
}
# Identificadores internos (catálogo real, etc.) guardados solo como huella SHA-256, para no escribirlos aquí
PRIVADOS = {'3bf767cbaa4f856da68de50f5b34a4396bd16af078036b47e11fc748f80b2403'}
YO = os.path.relpath(os.path.abspath(__file__), RAIZ)
problemas = []
for base, dirs, files in os.walk(RAIZ):
    dirs[:] = [d for d in dirs if d not in ('.git', '.venv', '__pycache__', '.ruff_cache', 'salida')]
    for f in files:
        ruta = os.path.relpath(os.path.join(base, f), RAIZ).replace(os.sep, '/')
        ext = os.path.splitext(f)[1].lower()
        if ext in PROHIBIDAS: problemas.append(f'{ruta}: archivo de datos ({ext})'); continue
        if ext == '.csv' and not ruta.startswith(CSV_PERMITIDO): problemas.append(f'{ruta}: CSV fuera de datos-simulados'); continue
        if ext in ('.png', '.jpg', '.jpeg', '.gif', '.ico') or ruta == YO: continue
        try: texto = open(os.path.join(base, f), encoding='utf-8').read()
        except UnicodeDecodeError: continue
        for nombre, pat in PATRONES.items():
            m = re.search(pat, texto)
            if m: problemas.append(f'{ruta}: {nombre} ({m.group(0)[:40]})')
        if any(hashlib.sha256(w.encode()).hexdigest() in PRIVADOS for w in set(re.findall(r'[A-Za-z0-9_]{6,}', texto))):
            problemas.append(f'{ruta}: identificador interno del workspace')
        if ext == '.ipynb':
            nb = json.loads(texto)
            if any(c.get('outputs') for c in nb.get('cells', []) if c.get('cell_type') == 'code'):
                problemas.append(f'{ruta}: notebook con salidas (limpiar antes de confirmar)')
if problemas:
    print('Revisar antes de subir:\n  ' + '\n  '.join(problemas)); sys.exit(1)
print('OK: sin datos reales, secretos ni salidas de notebooks')
