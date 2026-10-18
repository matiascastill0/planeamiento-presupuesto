"""Demo para jefatura: 3 plantillas Ppto27 reales (una por componente del Dir/Ind) con Ppto 2027, en dos cargas:
  <LIMPIAS>   las 3 plantillas sin errores ni alertas (Ppto 2027 = Real anualizado + 3 %)
  <ERRORES>   las mismas 3 con errores clásicos sembrados, cada uno con su celda exacta
La carga con errores tiene carga_id mayor, así que al subirla reemplaza a la limpia (silver toma la carga más reciente).

  Demo 1 · Imputación directa : 03. Gastos Administrativos/UDN/MDK/01. PERU            (CeCos de negocio 5xx → 100 % MDK)
  Demo 2 · Soporte directo    : 03. Gastos Administrativos/STAFF/Staff - Riesgos/01. PERU (driver % por UdN)
  Demo 3 · 100 % indirecto    : 03. Gastos Administrativos/STAFF/Staff - Finanzas/01. PERU (fila STAFF → bolsa del país)

Parte de la versión enviada (01. Ruta Oficial), llena Ene–Dic 27 y siembra errores editando sólo el XML
de la hoja Ppto27 (openpyxl perdería la etiqueta de confidencialidad). Salidas en la carpeta del workflow:
  01. Carpetas para subir/<carga>/     una carpeta por carga con la ruta de SharePoint y sus 3 Excel: se sube tal cual
  Resultado esperado - Demo 3 plantillas.xlsx   errores sembrados, flag esperado y montos del origen
Uso:  python3 generar_demo.py
"""
import os, re, shutil, sys, zipfile
import openpyxl
import pandas as pd
from openpyxl.utils import range_boundaries, get_column_letter
from lxml import etree

AQUI = os.path.dirname(os.path.abspath(__file__))
WF = os.path.dirname(AQUI)
DBX = os.path.dirname(os.path.dirname(WF))
RAIZ = os.path.dirname(DBX)
RUTA = os.path.join(RAIZ, '01. Ruta Oficial Ppto27 (Real Ene-Ago)')
sys.path.insert(0, os.path.join(DBX, '90. Workflows (pruebas y prototipos)', '02. Prueba contable - supuestos y flags', 'scripts'))
sys.path.insert(0, os.path.join(RAIZ, '03. Procesos'))
import plantillas as P
from ppto27_supuestos_flags import supuesto
from agosto_escribir import partes, col_idx, split_ref, q

SUELTAS = os.path.join(WF, '01. Carpetas para subir')
ESPERADO = os.path.join(WF, 'Resultado esperado - Demo final.xlsx')
G_PERU = 0.05
MES = {m: get_column_letter(27 + i) for i, m in enumerate(['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Dic'])}

# dos lotes con el MISMO contenido y distinta huella (fecha de modificación del archivo): uno para ensayar hoy y otro para
# la demo en vivo, que entra sin RESTORE y sin que bronze lo marque REPETIDO
LOTES = [('A. Ensayo (ya usado)', '20261020', '2026-10-20T09:00:00Z'), ('B. Ya usado', '20261021', '2026-10-21T09:00:00Z'),
         ('C. Validacion limpias AHORA', '20261022', '2026-10-22T09:00:00Z'), ('D. Demo en vivo', '20261023', '2026-10-23T09:00:00Z')]
DEMOS = [
    dict(demo=1, componente='1 · Imputación directa',
         rel='03. Gastos Administrativos/UDN/MDK/01. PERU/Ppto27 - MDK Peru - OFICIAL.xlsx',
         regla='CeCos de negocio de MDK (5xx): todo va 100 % a MDK como imputación directa',
         errores=['M01', 'M03', 'M16', 'M11', 'L11']),
    dict(demo=2, componente='2 · Soporte directo',
         rel='03. Gastos Administrativos/STAFF/Staff - Riesgos/01. PERU/Ppto27 - Staff - Riesgo Peru - OFICIAL.xlsx',
         regla='Riesgos es área de soporte: cada línea se reparte entre las UdN con el % de su driver; lo que el driver no asigna va a la bolsa',
         errores=['M05', 'M09', 'L07', 'M08', 'M12']),
    dict(demo=3, componente='3 · Indirecto (100 %)',
         rel='03. Gastos Administrativos/STAFF/Staff - Finanzas/01. PERU/Ppto27 - Staff - Finanzas - Peru.xlsx',
         regla='Finanzas no tiene driver: todo va a la bolsa de Perú y se reparte con el peso de cada UdN',
         errores=['L18', 'F05', 'M13', 'T01', 'T06', 'T02']),
]
OTROS = [  # flags que también aparecen sin haberlos sembrado, y por qué
    ('F15', 'INFO', 'Las 3 plantillas', 'Versión reemplazada: la carga nueva reemplaza a la anterior de la misma plantilla (queda en el historial)'),
    ('C03', 'ALERTA', 'Carga con errores', 'Al cambiar la glosa o el proveedor de una línea con Real, se avisa que el texto ya no es el enviado (misma fila del error)'),
    ('M10', 'INFO', 'Las 3 plantillas', 'Real 2026 positivo (extornos del contable) que ya venía en la plantilla enviada'),
    ('T05', 'INFO', 'MDK', 'Un texto de la plantilla original trae ; o | (rompe CSV)'),
]
QUE = {  # código → (qué se sembró, severidad, efecto esperado)
    'M01': ('Ppto Mar-27 escrito en positivo', 'ERROR', 'La línea va a cuarentena: un gasto nunca es positivo'),
    'M03': ('Ppto Jun-27 escrito como texto ("-12,500")', 'ALERTA', 'Se convierte a número y se registra'),
    'T01': ('Nombre del CeCo con tildes dañadas ("DirecciÃ³n")', 'ALERTA', 'Se repara el texto; el CeCo se reconoce por su número'),
    'L11': ('Glosa borrada', 'ALERTA', 'Entra al BI; se pide la glosa'),
    'M16': ('Total P27 escrito a mano encima de la fórmula', 'ALERTA', 'Databricks recalcula el total'),
    'M11': ('Ppto Jul-27 con un 0 escrito', 'INFO', 'Se trata como celda vacía'),
    'M05': ('Ppto May-27 con #REF!', 'ERROR', 'La línea va a cuarentena; ese mes no tiene monto'),
    'M09': ('Ppto Abr-27 con el texto "ver correo"', 'ERROR', 'La línea va a cuarentena; ese mes no tiene monto'),
    'L07': ('Proveedor de relleno "POR DEFINIR"', 'ALERTA', 'Entra al BI; se pide el proveedor real'),
    'M08': ('Ppto Ago-27 como fórmula que apunta a otra celda (=AA*1.1)', 'ALERTA', 'Se usa el valor calculado y se registra'),
    'M12': ('Ppto Set-27 con 4 decimales', 'INFO', 'Se redondea a 2 decimales'),
    'L18': ('Proveedor "Varios"', 'ERROR', 'La línea va a cuarentena (regla: nunca Varios)'),
    'F05': ('Monto escrito debajo de la tabla (fuera de Tabla1)', 'ERROR', 'No se carga ese monto; se avisa al área'),
    'M13': ('Todo el Ppto 2027 de una línea recurrente en Ene-27', 'ALERTA', 'Entra al BI; se pide revisar la mensualización'),
    'T06': ('País escrito "Peru" sin tilde', 'INFO', 'Se normaliza a "Perú"'),
    'T02': ('Glosa con espacios de más', 'INFO', 'Se limpia el texto'),
}


def limpio(real, g):
    """Ppto 2027 sin alertas: Real anualizado (como lo calcula silver: suma Ene–Ago / 8 × 12) + g, plano en 12 meses.
    Si el Real neto no es gasto, la línea no se presupuesta. Así P27 / Real anualizado = 1 + g (sin M14 / M15)."""
    r_anual = sum(v or 0.0 for v in real) / 8 * 12
    if r_anual > -1:
        return None
    anual = r_anual * (1 + g)
    u = 1 if abs(anual) >= 100 else 0.01
    cent = round(anual / u)
    meses = [int(cent / 12)] * 12
    meses[11] += cent - sum(meses)
    return [(round(m * u, 2) if u < 1 else m) if m else None for m in meses]


# ───────────── edición quirúrgica del XML de la hoja Ppto27 ─────────────
def editar(path, cambios):
    """cambios: {'AA15': ('n', -100.0) | ('s', 'texto') | ('e', '#REF!') | ('f', '-24000/12', -2000) | ('x',)}"""
    zin = zipfile.ZipFile(path)
    sheet, _ = partes(zin)
    S = etree.fromstring(zin.read(sheet))
    sd = S.find(q('sheetData'))
    rows = {int(r.get('r')): r for r in sd.findall(q('row'))}
    for ref, spec in cambios.items():
        col, fila = split_ref(ref)
        row = rows.get(fila)
        if row is None:
            row = etree.Element(q('row'))
            row.set('r', str(fila))
            sig = [r for n, r in sorted(rows.items()) if n > fila]
            (sig[0].addprevious(row) if sig else sd.append(row))
            rows[fila] = row
        cells = {split_ref(c.get('r'))[0]: c for c in row.findall(q('c'))}
        c = cells.get(col)
        if spec[0] == 'x':
            if c is not None:
                for ch in list(c):
                    c.remove(ch)
                for at in ('t', 'cm', 'vm'):
                    c.attrib.pop(at, None)
            continue
        if c is None:
            c = etree.Element(q('c'))
            c.set('r', ref)
            vecino = cells.get('N') or cells.get('AA')
            if vecino is not None and vecino.get('s'):
                c.set('s', vecino.get('s'))
            despues = [x for x in row.findall(q('c')) if col_idx(split_ref(x.get('r'))[0]) > col_idx(col)]
            (despues[0].addprevious(c) if despues else row.append(c))
        for ch in list(c):
            c.remove(ch)
        for at in ('t', 'cm', 'vm'):
            c.attrib.pop(at, None)
        k = spec[0]
        if k == 'n':
            etree.SubElement(c, q('v')).text = repr(float(spec[1]))
        elif k == 's':
            c.set('t', 'inlineStr')
            t = etree.SubElement(etree.SubElement(c, q('is')), q('t'))
            t.text = spec[1]
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        elif k == 'e':
            c.set('t', 'e')
            etree.SubElement(c, q('v')).text = spec[1]
        elif k == 'f':
            etree.SubElement(c, q('f')).text = spec[1]
            etree.SubElement(c, q('v')).text = repr(float(spec[2]))
    dim = S.find(q('dimension'))                       # como Excel al guardar: el rango usado incluye las celdas nuevas
    if dim is not None:
        a1, _, b1 = dim.get('ref').partition(':')
        c2, f2 = split_ref(b1 or a1)
        ultima = max(rows)
        dim.set('ref', f"{a1}:{c2}{max(f2, ultima)}")
    nuevo = {sheet: etree.tostring(S, xml_declaration=True, encoding='UTF-8', standalone=True)}
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            zout.writestr(it, nuevo.get(it.filename, zin.read(it.filename)))
    zin.close()
    os.replace(tmp, path)


def leer_tabla(path):
    wb = openpyxl.load_workbook(path)
    ws = wb['Ppto27']
    c1, r0, c2, r1 = range_boundaries(ws.tables['Tabla1'].ref)
    filas = {r: [ws.cell(r, c).value for c in range(1, 42)] for r in range(r0 + 1, r1 + 1)}
    return filas, r1


def recurrentes(filas):
    """Líneas con gasto en el Real 2026 donde sembrar errores: primero las recurrentes, de mayor a menor gasto."""
    out = []
    for r, v in filas.items():
        real = [x for x in v[13:21] if isinstance(x, (int, float))]
        meses = sum(1 for x in real if x < 0)
        if meses and sum(real) < 0:
            out.append((meses < 3, sum(real), r))          # primero las recurrentes (≥ 3 meses), luego el resto
    return [r for *_, r in sorted(out)]


def sellar(path, fecha):
    """Pone la fecha de modificación del archivo (docProps/core.xml): cambia la huella sin tocar el contenido."""
    zin = zipfile.ZipFile(path)
    core = zin.read('docProps/core.xml').decode('utf-8')
    core = re.sub(r'(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)', r'\g<1>' + fecha + r'\g<2>', core)
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            zout.writestr(it, core.encode('utf-8') if it.filename == 'docProps/core.xml' else zin.read(it.filename))
    zin.close()
    os.replace(tmp, path)


def generar(d, carga, con_errores, lote='', fecha=None):
    dest = os.path.join(SUELTAS, lote, carga, *d['rel'].split('/'))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(os.path.join(RUTA, *d['rel'].split('/')), dest)
    filas, fin = leer_tabla(dest)
    # 1) Ppto 2027 en todas las líneas con gasto (Real anualizado + 3 %)
    ppto = {}
    for r, v in filas.items():
        m = limpio([P.monto(x)[0] for x in v[13:21]], G_PERU)
        if m:
            ppto[r] = m
    P.escribir_ppto(dest, ppto)
    if not con_errores:
        if fecha:
            sellar(dest, fecha)
        return dest, []
    # 2) errores sembrados, cada uno en una línea recurrente distinta
    libres = [r for r in recurrentes(filas) if r in ppto]
    cambios, sembrados = {}, []
    for cod in d['errores']:
        if cod == 'F05':
            r = fin + 3
        elif cod == 'T01':                                   # una línea cuyo CeCo tenga tilde, para dañarla como lo hace Excel
            r = next(x for x in libres if re.search('[áéíóúñÁÉÍÓÚÑ]', str(filas[x][2])))
            libres.remove(r)
        else:
            r = libres.pop(0)
        v = filas.get(r)
        if cod == 'M01':
            celda = f"{MES['Mar']}{r}"
            cambios[celda] = ('n', abs(ppto[r][2] or 1000))
        elif cod == 'M03':
            celda = f"{MES['Jun']}{r}"
            cambios[celda] = ('s', f"{(ppto[r][5] or -12500):,.0f}")
        elif cod == 'T01':
            celda = f'C{r}'
            cambios[celda] = ('s', str(v[2]).encode('utf-8').decode('latin-1'))
        elif cod == 'M16':
            celda = f'AM{r}'
            cambios[celda] = ('n', float(round(sum(x or 0 for x in ppto[r]))))
        elif cod == 'L11':
            celda = f'K{r}'
            cambios[celda] = ('x',)
        elif cod == 'M11':
            celda = f"{MES['Jul']}{r}"
            cambios[celda] = ('n', 0)
        elif cod == 'M05':
            celda = f"{MES['May']}{r}"
            cambios[celda] = ('e', '#REF!')
        elif cod == 'M09':
            celda = f"{MES['Abr']}{r}"
            cambios[celda] = ('s', 'ver correo')
        elif cod == 'L07':
            celda = f'J{r}'
            cambios[celda] = ('s', 'POR DEFINIR')
        elif cod == 'M08':
            celda = f"{MES['Ago']}{r}"
            cambios[celda] = ('f', f"{MES['Ene']}{r}*1.1", round((ppto[r][0] or -1000) * 1.1, 2))
        elif cod == 'M12':
            celda = f"{MES['Set']}{r}"
            cambios[celda] = ('n', (ppto[r][8] or -1000) - 0.3333)
        elif cod == 'L18':
            celda = f'J{r}'
            cambios[celda] = ('s', 'Varios')
        elif cod == 'F05':
            celda = f"K{r} y {MES['Ene']}{r}"
            cambios[f'K{r}'] = ('s', 'Ajuste pendiente de cargar')
            cambios[f"{MES['Ene']}{r}"] = ('n', -5000)
        elif cod == 'M13':
            celda = f"{MES['Ene']}{r}"
            cambios[celda] = ('n', sum(x or 0 for x in ppto[r]))
            for i in range(1, 12):
                cambios[f'{get_column_letter(27 + i)}{r}'] = ('x',)
        elif cod == 'T06':
            celda = f'A{r}'
            cambios[celda] = ('s', 'Peru')
        elif cod == 'T02':
            celda = f'K{r}'
            cambios[celda] = ('s', '  ' + re.sub(r'\s+', '   ', str(v[10] or 'Servicio mensual')) + '  ')
        que, sev, efecto = QUE[cod]
        sembrados.append(dict(demo=d['demo'], carga=carga, plantilla=d['rel'].split('/')[-1], fila_excel=r, celda=celda,
                              linea=(f"{v[2]} | {str(v[4])[:40]} | {v[9]}" if v else '(debajo de la tabla)'),
                              error_sembrado=que, flag_esperado=cod, severidad=sev, efecto=efecto))
    editar(dest, cambios)
    if fecha:
        sellar(dest, fecha)
    return dest, sembrados


def origen(dest):
    """Montos del origen leídos del Excel generado: suma Ene–Dic 27 de las celdas numéricas dentro de Tabla1."""
    ws = openpyxl.load_workbook(dest, data_only=True)['Ppto27']          # fórmulas por su valor calculado, como Databricks
    c1, r0, c2, r1 = range_boundaries(ws.tables['Tabla1'].ref)
    filas = {r: [ws.cell(r, c).value for c in range(1, 42)] for r in range(r0 + 1, r1 + 1)}
    tot = [0.0] * 12
    for v in filas.values():
        for i, x in enumerate(v[26:38]):
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                tot[i] += x
            elif isinstance(x, str) and re.fullmatch(r'-?[\d,]+(\.\d+)?', x.strip()):
                tot[i] += float(x.strip().replace(',', ''))
    return tot


def main():
    shutil.rmtree(SUELTAS, ignore_errors=True)
    os.makedirs(SUELTAS)
    res, errs = [], []
    for lote, dia, fecha in LOTES:
        for carga, con_errores in ((f'{dia}_0800_Demo_Limpias', False), (f'{dia}_0900_Demo_Con_errores', True)):
            for d in DEMOS:
                dest, s = generar(d, carga, con_errores, lote, fecha)
                errs += [dict(lote=lote, **e) for e in s]
                o = origen(dest)
                res.append(dict(lote=lote, carga=carga, demo=d['demo'], componente_esperado=d['componente'], regla=d['regla'],
                                plantilla=d['rel'], lineas=len(leer_tabla(dest)[0]), errores_sembrados=len(s),
                                p27_origen=round(sum(o), 2), **{f'{m}-27': round(x, 2) for m, x in zip(MES, o)}))
    with pd.ExcelWriter(ESPERADO) as w:
        pd.DataFrame(res).to_excel(w, sheet_name='Resumen', index=False)
        pd.DataFrame(errs).to_excel(w, sheet_name='Errores sembrados', index=False)
        pd.DataFrame(OTROS, columns=['flag', 'severidad', 'dónde', 'por qué aparece']).to_excel(w, sheet_name='Otros flags', index=False)
    print(pd.DataFrame(res)[['lote', 'carga', 'demo', 'lineas', 'p27_origen']].to_string(index=False))
    print(pd.DataFrame(errs)[['lote', 'demo', 'fila_excel', 'celda', 'flag_esperado', 'severidad']].drop_duplicates(['demo', 'celda']).to_string(index=False))


if __name__ == '__main__':
    main()
