import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Arma '01. Ruta Oficial Ppto27 (Real Ene-Ago)': copia exacta del esqueleto de la ruta original + plantillas base para carpetas vacías con real."""
import os, shutil, glob, unicodedata
B = RAIZ
ORIG = B + '02. Insumos/04. Ruta original validada (ene-jul)/'
NEW = B + '01. Ruta Oficial Ppto27 (Real Ene-Ago)/'
SAL = B + '99. Archivo/Versiones anteriores (salida)/'
CARP = {'PERU': '01. PERU', 'COLOMBIA': '02. COLOMBIA', 'CHILE': '03. CHILE', 'PANAMA': '04. PANAMA', 'USA': '05. US', 'MEXICO': '06. MEXICO'}
NOMP = {'PERU': 'Peru', 'COLOMBIA': 'Colombia', 'CHILE': 'Chile', 'PANAMA': 'Panama', 'USA': 'USA', 'MEXICO': 'Mexico'}
SALP = {'PERU': 'Perú', 'COLOMBIA': 'Colombia', 'CHILE': 'Chile', 'PANAMA': 'Panamá', 'USA': 'USA', 'MEXICO': 'México'}
GA = NEW + '03. Gastos Administrativos/'
def nfc(s): return unicodedata.normalize('NFC', s)
def buscar(patron):
    r = [f for f in glob.glob(SAL + '**/*.xlsx', recursive=True) if nfc(f).endswith(nfc(patron))]
    if not r: raise FileNotFoundError(patron)
    return r[0]
nuevas = []
def poner(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst): raise FileExistsError(dst)
    shutil.copy2(src, dst); nuevas.append(os.path.relpath(dst, NEW))
if __name__ == '__main__':
    if os.path.exists(NEW): raise SystemExit('ya existe ' + NEW)
    shutil.copytree(ORIG, NEW); os.system(f'chmod -R u+w "{NEW}"')
    for f in glob.glob(NEW + '**/.DS_Store', recursive=True): os.remove(f)
    # UdN nuevas
    for u, paises in {'WM': ['CHILE', 'COLOMBIA', 'PANAMA', 'PERU', 'USA'], 'NNFF': ['COLOMBIA', 'PERU']}.items():
        for p in paises: poner(buscar(f'UdN/{u}/Ppto27 - {u} - {SALP[p]} - OFICIAL.xlsx'), GA + f'UDN/{u}/{CARP[p]}/Ppto27 - {u} {NOMP[p]} - OFICIAL.xlsx')
    # Staff nuevas (carpeta de la ruta -> unidad de salida)
    staff = {'Staff - Auditoría': ('Staff - Auditoría', ['CHILE', 'COLOMBIA', 'PANAMA', 'PERU']),
             'Staff - Crecimiento Rentable': ('Staff - Crecimiento Rentable', ['PERU']),
             'Staff - Oficina Representación': ('Staff - Oficina de Representación', ['CHILE', 'COLOMBIA', 'PANAMA', 'USA']),
             'Staff - Operaciones': ('Staff - Operaciones', ['CHILE', 'COLOMBIA', 'PANAMA', 'PERU', 'USA']),
             'Staff - Research': ('Staff - Research', ['CHILE', 'COLOMBIA', 'PERU']),
             'Staff - Responsabilidad Social': ('Staff - Responsabilidad Social', ['CHILE', 'COLOMBIA', 'PERU'])}
    for carpeta, (unidad, paises) in staff.items():
        for p in paises: poner(buscar(f'Staff/{unidad}/Ppto27 - {unidad} - {SALP[p]} - OFICIAL.xlsx'), GA + f'STAFF/{carpeta}/{CARP[p]}/Ppto27 - {carpeta} {NOMP[p]} - OFICIAL.xlsx')
    # Marketing por país
    for p in ['CHILE', 'COLOMBIA', 'PERU', 'USA']:
        poner(buscar(f'Marketing/Ppto27 - Marketing - {SALP[p]} - OFICIAL.xlsx'), GA + f'Marketing/Ppto27 - Marketing {NOMP[p]} - OFICIAL.xlsx')
    # Consultorías y Honorarios: Legales y Tributarias/Financieras por país, Dietas regional
    for p in ['CHILE', 'COLOMBIA', 'MEXICO', 'PANAMA', 'PERU', 'USA']:
        poner(buscar('Consultorías y Honorarios/Ppto27 - Consultorías y Honorarios Asesorías Legales - OFICIAL.xlsx'), GA + f'Asesorías Legales/Ppto27 - Asesorías Legales {NOMP[p]} - OFICIAL.xlsx')
    for p in ['CHILE', 'COLOMBIA', 'PANAMA', 'PERU', 'USA']:
        poner(buscar('Consultorías y Honorarios/Ppto27 - Consultorías y Honorarios Auditorías - OFICIAL.xlsx'), GA + f'Asesorías Tributarias y Financieras/Ppto27 - Asesorías Tributarias y Financieras {NOMP[p]} - OFICIAL.xlsx')
    poner(buscar('Consultorías y Honorarios/Ppto27 - Consultorías y Honorarios Dietas - OFICIAL.xlsx'), GA + 'Dietas/Ppto27 - Dietas - OFICIAL.xlsx')
    # ILP por país (archivos ILP corregidos)
    for p in ['CHILE', 'COLOMBIA', 'PANAMA', 'PERU', 'USA']:
        poner(B + f'99. Archivo/02. Gastos de Personal - corregido (eliminada)/Plantilla PPTO 2027 - {p} ILP.xlsx', NEW + f'02. Gastos de Personal/{p}/Ppto27 - ILP {NOMP[p]} - OFICIAL.xlsx')
    print('plantillas nuevas:', len(nuevas)); [print('  ', n) for n in nuevas]
    print('total xlsx:', len(glob.glob(NEW + '**/*.xlsx', recursive=True)))
