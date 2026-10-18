"""Empaqueta el Power BI conectado a Databricks para Windows: Ppto27_PowerBI_Databricks.zip (se extrae en C:\\).
Mismas reglas que empaquetar_zip.py: raíz Ppto27\\, carpetas sin tildes, nombres UTF-8 marcados, LEEME con CRLF y BOM.
Antes: python3 generar_pbip.py databricks
"""
import os, unicodedata, zipfile, time

AQUI = os.path.dirname(os.path.abspath(__file__))
ENT = os.path.dirname(AQUI)
SRC = os.path.join(ENT, '01. Power BI (Databricks)')
ZIP = os.path.join(ENT, 'Ppto27_PowerBI_Databricks.zip')

LEEME = r"""PPTO 2027 - POWER BI CONECTADO A DATABRICKS (vista contable)
=============================================================
Mismo reporte que la version con CSV (Formato Peru, Resumen, Detalle CeCo, Calidad), pero lee directo las tablas
catalogo_ppto.esquema_ppto.ppto27_gld_* que deja el notebook 01_procesar. Ya no hay que descargar CSV.
Requisitos (guia corporativa): acceso al Workspace Databricks (Sandbox), permiso para usar un Serverless SQL warehouse,
licencia PRO de Power BI y cuenta Credicorp Capital (Azure Active Directory).

PASO 1 - Extraer
  Clic derecho al zip > Extraer todo... > C:\
  Debe quedar: C:\Ppto27\01. Power BI (Databricks)\Ppto27 Contable.pbip   (no abrirlo desde dentro del zip)

PASO 2 - Copiar los datos de conexion en Databricks
  Databricks > menu izquierdo > SQL Warehouses > el Serverless SQL warehouse que tengas asignado > pestana "Connection details".
  Copiar:  Server hostname  (ej.: adb-xxxxxxxxxxxx.x.azuredatabricks.net)
           HTTP path        (ej.: /sql/1.0/warehouses/xxxxxxxxxxxxxxxx)

PASO 3 - Poner los parametros en Power BI
  a. Abrir C:\Ppto27\01. Power BI (Databricks)\Ppto27 Contable.pbip con Power BI Desktop.
     (Si sale un aviso de credenciales o de error de actualizacion, cerrarlo: primero van los parametros.)
  b. Inicio > Transformar datos (flechita) > Editar parametros:
       Hostname = el Server hostname copiado   (viene precargado el del workspace; verificar que sea el mismo)
       HttpPath = el HTTP path copiado         (viene como /sql/1.0/warehouses/COMPLETAR: reemplazarlo)
       Catalogo = catalogo_ppto               (no cambiar)
       Esquema  = esquema_ppto                          (no cambiar)
     Aceptar > "Aplicar cambios".

PASO 4 - Iniciar sesion (solo la primera vez)
  En la ventana "Azure Databricks": elegir  Azure Active Directory  > Iniciar sesion con la cuenta de Credicorp Capital >
  Conectar. Nivel de privacidad: Organizacional.

PASO 5 - Actualizar
  Inicio > Actualizar. La primera vez puede tardar 1-2 minutos (el warehouse serverless se enciende solo).
  Guardar siempre como .pbip.

DIA A DIA
  Subir plantillas a ppto27/10_entrada > correr 01_procesar en Databricks > en Power BI: Inicio > Actualizar.

PUBLICAR EN POWER BI SERVICE (cuando se quiera compartir)
  Publicar en el Workspace del area > modelo semantico > Configuracion > Credenciales del origen de datos > Editar credenciales >
  OAuth2 (cuenta Credicorp) > revisar que los Parametros Hostname / HttpPath sean los mismos.

SI ALGO FALLA
  - "No se encuentra la tabla ppto27_gld_..."  -> 01_procesar no termino bien, o Catalogo/Esquema no son catalogo_ppto / esquema_ppto.
  - "PERMISSION_DENIED" o "no tiene acceso"     -> falta permiso USE CATALOG / USE SCHEMA / SELECT en catalogo_ppto.esquema_ppto o
                                                   permiso de uso del SQL warehouse: pedirlo al administrador de Databricks.
  - Error con HttpPath "COMPLETAR"              -> falta el paso 3b.
  - Pide usuario/contrasena o token             -> elegir Azure Active Directory (no Personal Access Token).
"""


def main():
    if os.path.exists(ZIP):
        os.remove(ZIP)
    n, largo = 0, 0
    with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
        def add(arc, data, fecha=None):
            zi = zipfile.ZipInfo(unicodedata.normalize('NFC', arc), (fecha or time.localtime())[:6])
            zi.create_system, zi.compress_type, zi.flag_bits = 0, zipfile.ZIP_DEFLATED, 0x800
            z.writestr(zi, data)
        for d, _, fs in os.walk(SRC):
            for f in sorted(fs):
                if f.startswith('.DS_Store') or f.startswith('~$'):
                    continue
                p = os.path.join(d, f)
                arc = 'Ppto27/01. Power BI (Databricks)/' + os.path.relpath(p, SRC).replace(os.sep, '/')
                add(arc, open(p, 'rb').read(), time.localtime(os.path.getmtime(p)))
                n += 1
                largo = max(largo, len('C:/' + arc))
        add('Ppto27/LEEME - Power BI Databricks.txt', '\ufeff'.encode() + LEEME.replace('\n', '\r\n').encode('utf-8'))
    with zipfile.ZipFile(ZIP) as z:
        assert z.testzip() is None
        assert any(x.endswith('Ppto27 Contable.pbip') for x in z.namelist())
        assert any(x.endswith('definition.pbir') for x in z.namelist()) and any(x.endswith('model.bim') for x in z.namelist())
    print(ZIP, f'· {n + 1} archivos · ruta más larga en C:\\ = {largo} · {os.path.getsize(ZIP) // 1024} KB')


if __name__ == '__main__':
    main()
