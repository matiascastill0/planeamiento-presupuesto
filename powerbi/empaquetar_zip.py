"""Empaqueta el Entregable 1 para Windows: Ppto27_Entregable1_Contable.zip (se descomprime en C:\\).

Reglas Windows: rutas cortas, carpetas sin tildes dentro del zip, nombres NFC con bandera UTF-8, sin archivos de macOS
(.DS_Store, __MACOSX, ~$), textos con saltos de línea CRLF y raíz "Ppto27\\" para que RutaDatos funcione sin cambios.
"""
import os, unicodedata, zipfile, time

AQUI = os.path.dirname(os.path.abspath(__file__))
ENT = os.path.dirname(AQUI)
TOP = os.path.dirname(ENT)
ZIP = os.path.join(ENT, 'Ppto27_Entregable1_Contable.zip')
ANTIGUO = os.path.join(ENT, 'Ppto27 - Power BI (descomprimir en C).zip')

LEEME = r"""PPTO 2027 - ENTREGABLE 1 - VISTA CONTABLE (Credicorp Capital)
===============================================================

CONTENIDO
  01. Datos ejemplo (CSV)\    15 tablas de ejemplo (hechos y dimensiones)
  01. Power BI\               Ppto27 Contable.pbip + carpetas .Report y .SemanticModel (NO separarlas)
  02. Documentacion\          Modelo de datos (relaciones, medidas DAX) y diccionario de columnas
  Tema Credicorp Capital.json tema de colores para otros reportes (Ver > Temas > Examinar)

PASOS EN WINDOWS
  1. Clic derecho sobre el zip > "Extraer todo..." > destino:  C:\
     Debe quedar:  C:\Ppto27\01. Power BI\Ppto27 Contable.pbip
     (NO abrir el .pbip desde dentro del zip: falta el resto de carpetas y sale "Required artifact is missing")
  2. Abrir  C:\Ppto27\01. Power BI\Ppto27 Contable.pbip  con Power BI Desktop.
     Si no reconoce el formato: Archivo > Opciones > Caracteristicas de version preliminar >
     "Opcion de guardado de proyectos de Power BI (.pbip)" y reiniciar.
  3. Inicio > Actualizar.  La ruta ya viene configurada como:  C:\Ppto27\01. Datos ejemplo (CSV)\
     Si lo extrajiste en otra carpeta: Inicio > Transformar datos (flechita) > Editar parametros >
     RutaDatos = carpeta donde estan los .csv (la que contiene fact_ppto.csv) > Aceptar > Aplicar cambios.
  4. Guardar siempre como .pbip.

QUE DEBES VER
  Pagina "Formato Peru": Nivel 1 / Nivel 2 en el orden del Formato Peru, por mes, en PEN (gasto en negativo).
  Pagina "Resumen": gasto 2027 (aprox. 229 millones PEN en los datos de ejemplo), por mes, Nivel 2 y pais.
  Pagina "Detalle CeCo": agrupacion > CeCo por mes y detalle por cuenta y proveedor.
  Pagina "Calidad": flags de validacion por plantilla, linea y celda.

DATOS
  Son de EJEMPLO (Ppto 2027 supuesto). Cuando Databricks este listo, cada tabla se cambia por su tabla gold
  (catalogo_ppto.esquema_ppto.ppto27_gld_*) con las mismas columnas: medidas y visuales no cambian.
"""


def nfc(s): return unicodedata.normalize('NFC', s)


def agregar(zf, src, arc, texto=None):
    zi = zipfile.ZipInfo(nfc(arc).replace(os.sep, '/'), time.localtime(time.time())[:6])
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.create_system = 0                                   # MS-DOS/Windows
    zi.flag_bits |= 0x800                                  # nombres en UTF-8
    if texto is not None:
        data = texto.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8-sig')
    else:
        with open(src, 'rb') as fh:
            data = fh.read()
    zf.writestr(zi, data)


def main():
    if os.path.exists(ANTIGUO):
        os.remove(ANTIGUO)
    fuentes = [(os.path.join(TOP, '01. Datos ejemplo (CSV)'), 'Ppto27/01. Datos ejemplo (CSV)'),
               (os.path.join(ENT, '01. Power BI'), 'Ppto27/01. Power BI')]
    docs = [(os.path.join(TOP, '00. Documentación', 'Modelo de datos Power BI - Ppto27.md'), 'Ppto27/02. Documentacion/Modelo de datos Power BI - Ppto27.md'),
            (os.path.join(TOP, '00. Documentación', 'Modelo Ppto27 - tablas ejemplo.xlsx'), 'Ppto27/02. Documentacion/Modelo Ppto27 - diccionario y muestra.xlsx'),
            (os.path.join(ENT, 'Tema Credicorp Capital.json'), 'Ppto27/Tema Credicorp Capital.json')]
    with zipfile.ZipFile(ZIP, 'w') as zf:
        for src, dst in fuentes:
            for root, _, files in os.walk(src):
                for f in sorted(files):
                    if f in ('.DS_Store',) or f.startswith('~$') or '__MACOSX' in root:
                        continue
                    p = os.path.join(root, f)
                    agregar(zf, p, os.path.join(dst, os.path.relpath(p, src)))
        for src, arc in docs:
            agregar(zf, src, arc)
        agregar(zf, None, 'Ppto27/LEEME - Instrucciones Windows.txt', LEEME)
    # verificación
    with zipfile.ZipFile(ZIP) as zf:
        assert zf.testzip() is None
        n = zf.namelist()
        req = ['Ppto27/01. Power BI/Ppto27 Contable.pbip', 'Ppto27/01. Power BI/Ppto27 Contable.Report/definition.pbir',
               'Ppto27/01. Power BI/Ppto27 Contable.Report/report.json', 'Ppto27/01. Power BI/Ppto27 Contable.SemanticModel/model.bim',
               'Ppto27/01. Power BI/Ppto27 Contable.SemanticModel/definition.pbism']
        faltan = [r for r in req if r not in n]
        csv = [x for x in n if x.endswith('.csv')]
        largo = max(len('C:\\' + x.replace('/', '\\')) for x in n)
        assert not faltan, faltan
    print(f'{ZIP}\n  {len(n)} archivos · {len(csv)} CSV · ruta más larga en C:\\ = {largo} caracteres · {os.path.getsize(ZIP)//1024} KB')
    return n


if __name__ == '__main__':
    main()
