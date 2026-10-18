"""Genera 'Ppto27 Dashboard Validacion.html': dashboard AUTÓNOMO (un solo archivo, sin internet ni librerías externas) con la
validación del reparto y la explicación del proyecto. Funciona con doble clic en Edge/Chrome de la laptop corporativa.
Datos: el reporte en texto de la sección H de 95_validar (reporte_validacion_ultimo.txt). En el propio HTML se puede pegar uno nuevo.
Uso: python generar_dashboard_html.py [reporte.txt]
"""
import json, os, sys
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
NB = os.path.dirname(AQUI)
sys.path.insert(0, NB)
import ppto27_lib as L

SALIDA = os.path.join(os.path.dirname(NB), 'Ppto27 Dashboard Validacion.html')


def main():
    rep = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, 'reporte_validacion_ultimo.txt')
    texto = open(rep, encoding='utf-8').read().strip()
    cat = [[k, v[0], v[1], v[2], v[3], v[4]] for k, v in sorted(L.CATALOGO.items(), key=lambda kv: (L.SEV_ORDEN.index(kv[1][1]), kv[0]))]
    est = [[n1, g, n2] for n1, g, n2, _, _ in L.ESTRUCTURA]
    js = lambda o: json.dumps(o, ensure_ascii=False).replace('</', '<\\/')
    html = open(os.path.join(AQUI, 'dashboard_plantilla.html'), encoding='utf-8').read()
    for k, v in {'__REPORTE__': js(texto), '__CATALOGO__': js(cat), '__ESTRUCTURA__': js(est),
                 '__GENERADO__': js(datetime.now().strftime('%d/%m/%Y %H:%M'))}.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    with open(SALIDA, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(html)
    print('OK', SALIDA, f'{len(html.encode()) / 1024:.0f} KB')


if __name__ == '__main__':
    main()
