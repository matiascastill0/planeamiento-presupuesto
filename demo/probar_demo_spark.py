"""Prueba local (Spark 3.5) de la demo: carga base (REF + 5 rubros del workflow 06) y después cada demo por separado,
como lo hará el usuario en Databricks (descomprimir → bronze → silver → gold → control). Para cada demo verifica:
flags esperados presentes, total del origen = contable en gold, y que todo cae en el componente esperado.
Uso: python probar_demo_spark.py   (entorno con pyspark 3.5 y Java 11)
"""
import os, sys, shutil, zipfile, unicodedata, json, time, datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
WF = os.path.dirname(AQUI)
DBX = os.path.dirname(os.path.dirname(WF))
NB = os.path.join(DBX, '02. Entregable 1 - Contable', '02. Databricks')
W06 = os.path.join(DBX, '90. Workflows (pruebas y prototipos)', '06. Cargas de prueba por carpeta', '01. Zips para subir')
VOLUME = os.environ.get('PPTO27_VOLUME_LOCAL', '/private/tmp/claude-501/ppto27_volume_demo')
os.environ.update(PPTO27_CATALOGO='local', PPTO27_FORMATO='parquet', PPTO27_VOLUME=VOLUME)
sys.path.insert(0, NB)
sys.path.insert(0, AQUI)
import pandas as pd
from pyspark.sql import SparkSession
import ppto27_lib as L, ppto27_spark as SP
CARPETAS = os.path.join(WF, '01. Carpetas para subir')
ESPERADO = os.path.join(WF, 'Resultado esperado - Demo final.xlsx')

pd.set_option('display.width', 220)


def descomprimir(zip_path, destino):
    with zipfile.ZipFile(zip_path) as z:
        for i in z.infolist():
            n = unicodedata.normalize('NFC', i.filename)
            if n.endswith('/') or '__MACOSX' in n:
                continue
            out = os.path.join(destino, *n.split('/'))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with z.open(i) as s, open(out, 'wb') as d:
                d.write(s.read())


def main():
    shutil.rmtree(VOLUME, ignore_errors=True)
    os.makedirs(f'{VOLUME}/90_maestros')
    for f in ('maestros_ppto27.xlsx', 'alias_ppto27.xlsx', 'drivers_ppto27.xlsx'):
        shutil.copy2(os.path.join(NB, '90_maestros (subir al volume)', f), f'{VOLUME}/90_maestros/{f}')
    spark = (SparkSession.builder.master('local[*]').config('spark.ui.enabled', 'false')
             .config('spark.sql.warehouse.dir', f'{VOLUME}/_warehouse').config('spark.sql.shuffle.partitions', '8')
             .config('spark.sql.ansi.enabled', 'true').config('spark.driver.memory', '6g').getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    base = sorted(f for f in os.listdir(W06) if f.endswith('.zip'))
    base = [z for z in base if z.startswith('REF_')] + [z for z in base if not z.startswith('REF_')]
    for z in base:
        c = z[:-4]
        descomprimir(os.path.join(W06, z), f'{L.CARGAS}/{c}')
        print('base', c, SP.bronze(spark, f'{L.CARGAS}/{c}', c))
    SP.silver(spark); SP.gold(spark)
    tb = lambda n: spark.table(L.tabla(n)).toPandas()
    esperado = pd.read_excel(ESPERADO, 'Errores sembrados')
    resumen = pd.read_excel(ESPERADO, 'Resumen')
    salida = []
    for lote, c in resumen[['lote', 'carga']].drop_duplicates().itertuples(index=False):
        shutil.copytree(os.path.join(CARPETAS, lote, c), f'{L.CARGAS}/{c}')   # = subir la carpeta tal cual al Volume
        tiempos = {}
        t = time.time(); print('\n=====', c, SP.bronze(spark, f'{L.CARGAS}/{c}', c)); tiempos['bronze'] = time.time() - t
        t = time.time(); SP.silver(spark); tiempos['silver'] = time.time() - t
        t = time.time(); SP.gold(spark); tiempos['gold'] = time.time() - t
        t = time.time(); CU, CTL = SP.control(spark); tiempos['control'] = time.time() - t
        os.makedirs(f'{VOLUME}/40_tiempos', exist_ok=True)                    # = la línea que se agrega al 99_ejecutar_todo
        with open(f'{VOLUME}/40_tiempos/{c}.json', 'w') as f: json.dump(dict(carga=c, fecha=datetime.datetime.now().isoformat(timespec='seconds'), **{k: round(v, 1) for k, v in tiempos.items()}), f)
        shutil.copytree(f'{VOLUME}/_warehouse', f'{VOLUME}/_warehouse_{c}')   # foto de las tablas tras cada carga (para probar el notebook)
        fallas = CTL[CTL.resultado != 'OK']
        print('controles con FALLA:', fallas[['control', 'detalle']].to_dict('records') or 'ninguno')
        fl_all, lin, fp_all, g_all = tb('slv_flags'), tb('slv_lineas'), tb('gld_fact_ppto'), tb('gld_fact_gestion_dirind')
        for d in resumen[resumen.carga == c].to_dict('records'):
            idp = L.identificar(d['plantilla'])['id_plantilla']
            fl = fl_all[fl_all.id_plantilla == idp]
            esp = esperado[(esperado.carga == c) & (esperado.demo == d['demo'])] if len(esperado) else esperado
            sembr = set(esp.flag_esperado) if len(esp) else set()
            faltan = sorted(sembr - set(fl.codigo_flag))
            sin_celda = sorted(fl[fl.codigo_flag.isin(sembr) & (fl.celdas.fillna('') == '')].codigo_flag.unique())
            otros = fl[~fl.codigo_flag.isin(sembr) & (fl.severidad != 'INFO')]
            fp = fp_all[fp_all.id_plantilla == idp]
            g = g_all[g_all.id_plantilla == idp]
            orig = float(d['p27_origen'])
            ok = fp[fp.estado_linea.isin(['OK', 'OK con alerta'])]
            ceco_nulo = int(lin[(lin.id_plantilla == idp) & lin.ceco.isna()].shape[0])
            print(f"\n--- demo {d['demo']} · {idp}")
            print('flags:', fl.groupby(['codigo_flag', 'severidad']).size().to_dict())
            print('sembrados sin detectar:', faltan or 'ninguno', '| sembrados sin celda:', sin_celda or 'ninguno')
            print('otros ERROR/ALERTA no sembrados:', otros[['codigo_flag', 'fila', 'celdas', 'detalle']].to_dict('records') or 'ninguno')
            print('estado líneas:', fp.groupby('estado_linea').id_linea.nunique().to_dict(), '| líneas con CeCo nulo:', ceco_nulo)
            print(f'origen {orig:,.2f} | gold {fp.monto_origen.sum():,.2f} | dif {orig - fp.monto_origen.sum():,.2f}')
            print(f'contable OK {ok.monto_pen.sum():,.2f} | Dir/Ind {g.monto_pen.sum():,.2f} | por componente',
                  g.groupby('id_componente').monto_pen.sum().round(2).to_dict())
            salida.append(dict(carga=c, demo=d['demo'], fallas=len(fallas), faltan=faltan, sin_celda=sin_celda,
                               otros=sorted(otros.codigo_flag.unique()), ceco_nulo=ceco_nulo,
                               dif_origen=round(orig - fp.monto_origen.sum(), 2), dif_dirind=round(ok.monto_pen.sum() - g.monto_pen.sum(), 2),
                               componentes=sorted(g.id_componente.unique().tolist())))
    print('\nRESUMEN', json.dumps(salida, ensure_ascii=False, indent=1, default=str))
    spark.stop()


if __name__ == '__main__':
    main()
