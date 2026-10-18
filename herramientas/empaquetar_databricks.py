"""Arma Ppto27_Databricks_para_subir.zip (para llevar a la laptop con Windows): notebooks, librerías, maestros y pasos.
Carpetas del zip sin tildes, nombres en UTF-8 marcados, LEEME con CRLF y BOM (memoria: entregables para Windows)."""
import os, zipfile, time

AQUI = os.path.dirname(os.path.abspath(__file__))
NB = os.path.dirname(AQUI)
SALIDA = os.path.join(os.path.dirname(NB), 'Ppto27_Databricks_para_subir.zip')
RAIZ = 'Ppto27_Databricks'
NOTEBOOKS = ['00_setup.py', '01_procesar.py', '02_validar.py', '99_reiniciar.py']
LIBRERIAS = ['ppto27_lib.py', 'ppto27_silver.py', 'ppto27_gold.py', 'ppto27_spark.py']
MAESTROS = ['maestros_ppto27.xlsx', 'alias_ppto27.xlsx', 'drivers_ppto27.xlsx']

PASOS = r'''PPTO27 EN DATABRICKS · PASOS EXACTOS
===================================

CONTENIDO DE ESTE ZIP
  1_Importar_al_Workspace\        4 notebooks: 00_setup, 01_procesar, 02_validar, 99_reiniciar
  2_Subir_al_Volume_00_codigo\    4 librerías: ppto27_lib.py, ppto27_silver.py, ppto27_gold.py, ppto27_spark.py
  3_Subir_al_Volume_90_maestros\  3 Excel: maestros_ppto27.xlsx, alias_ppto27.xlsx, drivers_ppto27.xlsx

CÓMO FUNCIONA (una idea)
  Todo lo que llega se sube a UNA carpeta (ppto27/10_entrada), como venga: zips de carpetas de SharePoint (completas o
  parciales) o Excel sueltos. Se corre 01_procesar. Ese notebook ordena lo recibido, lo procesa y deja el archivo para el
  Power BI en ppto27/30_bi. No hay que elegir nada ni nombrar nada de una forma especial.

PASO 0 · Laptop
  Clic derecho a este zip > Extraer todo... > C:\  (queda C:\Ppto27_Databricks\)

PASO 1 · Empezar de cero en Databricks
  a. Si existe una carpeta Ppto27 anterior en el Workspace, borrarla.
  b. Workspace > Home > clic derecho > Create > Folder > "Ppto27".
  c. Dentro de Ppto27: clic derecho > Import > File > los 4 archivos de 1_Importar_al_Workspace > Import.
  d. Si antes se corrió algo (tablas ppto27_* o carpetas en el Volume): abrir 99_reiniciar > escribir BORRAR en el campo
     "confirmar" (arriba) > Run all. Si es la primera vez, saltar este paso.

PASO 2 · Carpetas, librerías y maestros (una sola vez)
  a. Abrir 00_setup > Connect > Serverless > Run all.
     Crea las carpetas y termina con un error que lista lo que falta subir. Es normal la primera vez.
  b. Catalog (menú izquierdo) > catalogo_ppto > esquema_ppto > Volumes > vol_administrado > ppto27 > 00_codigo
     > "Upload to this volume" > los 4 .py de 2_Subir_al_Volume_00_codigo > Upload.
  c. Igual en ppto27 > 90_maestros con los 3 Excel de 3_Subir_al_Volume_90_maestros.
  d. 00_setup > Run all: ahora todo dice OK.

PASO 3 · Subir plantillas (cada vez que llegan)
  Catalog > ... > ppto27 > 10_entrada > "Upload to this volume" > seleccionar TODO lo que llegó:
    · zips de SharePoint (en SharePoint: carpeta > Descargar; baja como zip; no hace falta renombrarlo)
    · Excel sueltos
  La versión ENVIADA a las áreas (referencia) se sube una sola vez, como zip cuyo nombre empiece con REF_ (ej.: REF_20261010.zip).
  Para la prueba de hoy: subir los 6 zips de "06. Cargas de prueba por carpeta\01. Zips para subir".

PASO 4 · Procesar
  Abrir 01_procesar > Run all (1 a 3 minutos). Al final muestra:
    1. qué se recibió y si cada archivo se reconoció
    2. entrega por rubro (recibidas / pendientes de las 184), estado de las líneas, archivos a revisar
    3. controles y la ruta del archivo para el BI
  10_entrada queda vacía: lo recibido pasa a 11_procesado\<fecha_hora>.

PASO 5 · Ver en el Power BI
  a. Catalog > ... > ppto27 > 30_bi > el zip más reciente (Ppto27_BI_<fecha_hora>.zip) > menú (⋮) > Download.
  b. Extraer ese zip en C:\Ppto27\01. Datos ejemplo (CSV)\ y elegir "Reemplazar los archivos".
  c. Abrir C:\Ppto27\01. Power BI\Ppto27 Contable.pbip > Inicio > Actualizar.

PASO 6 · Validar el reparto Dir/Ind (después de cada 01_procesar)
  Abrir 02_validar > Run all (menos de 1 minuto). Recalcula el reparto por su cuenta y lo compara con la tabla del BI:
    · 4 controles críticos (conservación, drivers 100 %, recálculo línea por línea, indirectos): deben salir OK.
    · "Cruce con el Power BI": país × Nivel 1 con contable / Directo / Indirecto → deben verse iguales en el BI.
    · CeCos sin driver (repartidos por regla) → para confirmar con Planeamiento.
    · Trazabilidad: una línea contable → sus drivers → su reparto por UdN mes a mes.
  Deja Validacion_DirInd_<fecha_hora>.xlsx en 30_bi (para compartir).

SI LLEGA ALGO DESPUÉS (ej.: CS Administrativo atrasado, o un área corrige)
  Subirlo a 10_entrada (zip o Excel suelto) > 01_procesar > repetir el paso 5. Sólo entra lo nuevo; lo demás queda igual.

SI ALGO FALLA
  · 00_setup dice "FALTA SUBIR": subir ese archivo a esa carpeta (nombre exacto, sin "(1)").
  · 01_procesar dice "No hay nada que procesar": 10_entrada está vacía.
  · 01_procesar termina con "controles CRÍTICOS con FALLA": no se generó el BI; mandar captura de la tabla de controles.
  · Cualquier otro error: captura completa (notebook + celda + mensaje).
'''


def main():
    if os.path.exists(SALIDA):
        os.remove(SALIDA)
    with zipfile.ZipFile(SALIDA, 'w', zipfile.ZIP_DEFLATED) as z:
        def add(src, arc):
            zi = zipfile.ZipInfo(f'{RAIZ}/{arc}', time.localtime(os.path.getmtime(src))[:6])
            zi.create_system, zi.compress_type, zi.flag_bits = 0, zipfile.ZIP_DEFLATED, 0x800
            with open(src, 'rb') as fh:
                z.writestr(zi, fh.read())
        for f in NOTEBOOKS:
            add(os.path.join(NB, f), f'1_Importar_al_Workspace/{f}')
        for f in LIBRERIAS:
            add(os.path.join(NB, f), f'2_Subir_al_Volume_00_codigo/{f}')
        for f in MAESTROS:
            add(os.path.join(NB, '90_maestros (subir al volume)', f), f'3_Subir_al_Volume_90_maestros/{f}')
        zi = zipfile.ZipInfo(f'{RAIZ}/LEEME - Pasos para subir.txt', time.localtime()[:6])
        zi.create_system, zi.compress_type, zi.flag_bits = 0, zipfile.ZIP_DEFLATED, 0x800
        z.writestr(zi, '\ufeff'.encode('utf-8') + PASOS.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
    with zipfile.ZipFile(SALIDA) as z:
        assert z.testzip() is None
        nombres = z.namelist()
    print(SALIDA)
    print(f'{len(nombres)} archivos · ruta más larga en C:\\ = {max(len("C:/" + n) for n in nombres)} caracteres · '
          f'{os.path.getsize(SALIDA) // 1024} KB')
    for n in nombres:
        print('  ', n)


if __name__ == '__main__':
    main()
