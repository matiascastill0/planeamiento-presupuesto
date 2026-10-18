"""Tarjetas KPI en SVG (nativo Power BI) para Resumen y Calidad, con el diseño de la Guía del Proceso.

- Agrega 8 medidas 'KPI … SVG' a _Medidas (dataCategory: ImageUrl, carpeta '5 Diseño KPI').
- Reemplaza las 8 tarjetas (p1_k1..k4, p3_k1..k4) por tablas de una sola celda que muestran el SVG.
- Ajusta la fila de gráficos debajo de las tarjetas.
- --preview <carpeta>: genera un HTML con las 8 tarjetas con valores de ejemplo (mismo diseño que el DAX).

Uso:  python3 kpis_svg.py <carpeta del .pbip> [--preview <carpeta>]
"""
import os, sys, re, json, glob, shutil, uuid

INK, CORAL, CORAL2, BLUE, BG, MUTED, LINE, GREEN, AMBER = '#15192C', '#D74028', '#EA6B58', '#2F71E5', '#ECEFF1', '#4F6772', '#E3E7EA', '#188737', '#D68502'
F = "font-family='Inter,Segoe UI,Helvetica,Arial,sans-serif'"
W, H = 300, 92
CX, CY, R = 258, 46, 22          # anillo / ícono a la derecha
CIRC = 138                       # 2·π·22

# ---------- piezas SVG (con marcadores {X} que se llenan con DAX o con valores de ejemplo) ----------
def base(hero):
    if hero:
        fondo = f"<rect x='2' y='2' width='{W-4}' height='{H-6}' rx='12' fill='{INK}' filter='url(#s)'/>"
        montes = (f"<g clip-path='url(#c)'><g transform='translate(214 38) scale(0.165)'>"
                  f"<polygon points='40,300 150,150 260,300' fill='{BLUE}' opacity='.9'/>"
                  "<polygon points='150,300 330,46 510,300' fill='#9AA9B4'/>"
                  "<polygon points='230,300 300,206 370,300' fill='#3B4D56'/>"
                  f"<polygon points='330,300 440,150 550,300' fill='{CORAL}'/></g></g>")
        return fondo + montes
    return f"<rect x='2.5' y='2.5' width='{W-5}' height='{H-7}' rx='12' fill='#FFFFFF' stroke='{LINE}' filter='url(#s)'/>"


def tarjeta(etq, hero=False, viz=''):
    lbl, val, sub = (CORAL2, '#FFFFFF', '#AAB9C2') if hero else (MUTED, INK, MUTED)
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>"
            "<defs><filter id='s' x='-5%' y='-10%' width='110%' height='135%'>"
            f"<feDropShadow dx='0' dy='1.5' stdDeviation='2' flood-color='{INK}' flood-opacity='0.10'/></filter>"
            f"<clipPath id='c'><rect x='2' y='2' width='{W-4}' height='{H-6}' rx='12'/></clipPath></defs>"
            + base(hero) +
            f"<text x='18' y='25' {F} font-size='9' font-weight='700' letter-spacing='0.9' fill='{lbl}'>{etq}</text>"
            f"<text x='18' y='57' {F} font-size='25' font-weight='800' letter-spacing='-0.4' fill='{val}'>{{VALOR}}</text>"
            f"<text x='18' y='75' {F} font-size='9.5' fill='{sub}'>{{SUB}}</text>" + viz + "</svg>")


def anillo():
    return (f"<circle cx='{CX}' cy='{CY}' r='{R}' fill='none' stroke='{LINE}' stroke-width='6'/>"
            f"<circle cx='{CX}' cy='{CY}' r='{R}' fill='none' stroke='{{COLOR}}' stroke-width='6' "
            f"stroke-dasharray='{{ARCO}} 200' transform='rotate(-90 {CX} {CY})'/>"
            f"<text x='{CX}' y='{CY+4}' {F} font-size='10' font-weight='700' text-anchor='middle' fill='{{COLOR}}'>{{PCT}}</text>")


def insignia(fondo, color, txt, tam=11):
    return (f"<circle cx='{CX}' cy='{CY}' r='{R}' fill='{fondo}'/>"
            f"<text x='{CX}' y='{CY + tam // 3 + 1}' {F} font-size='{tam}' font-weight='800' text-anchor='middle' fill='{color}'>{txt}</text>")


DOC = (f"<circle cx='{CX}' cy='{CY}' r='{R}' fill='#FDE3D3'/>"
       f"<rect x='{CX-7}' y='{CY-10}' width='14' height='19' rx='2' fill='none' stroke='{CORAL}' stroke-width='1.8'/>"
       f"<path d='M{CX-3} {CY-4}h6M{CX-3} {CY}h6M{CX-3} {CY+4}h4' stroke='{CORAL}' stroke-width='1.6' stroke-linecap='round'/>")

# ---------- DAX ----------
def mag(v):
    return (f'SWITCH ( TRUE (), ISBLANK ( {v} ), "0", ABS ( {v} ) >= 1e9, FORMAT ( {v} / 1e9, "#,0.0" ) & " MM", '
            f'ABS ( {v} ) >= 1e6, FORMAT ( {v} / 1e6, "#,0.0" ) & " M", ABS ( {v} ) >= 1e3, FORMAT ( {v} / 1e3, "#,0.0" ) & " K", FORMAT ( {v}, "#,0" ) )')

PCT_COLOR = lambda p: f'SWITCH ( TRUE (), {p} = 0, "{GREEN}", {p} <= 0.02, "{AMBER}", "{CORAL}" )'
ARCO = lambda p: f'FORMAT ( ROUND ( MIN ( {p}, 1 ) * {CIRC}, 0 ), "0" )'
PCT_TXT = lambda p: f'FORMAT ( ROUND ( MIN ( {p}, 1 ) * 100, 0 ), "0" ) & "%"'

KPIS = [
    # (medida, visual a reemplazar, svg, VAR, {marcador: DAX}, {marcador: ejemplo}, descripción)
    ('KPI Gasto Ppto SVG', ('ReportSection1', 'p1_k1'),
     tarjeta('GASTO PPTO 2027 &#183; PEN', hero=True),
     ['_v = [Gasto PEN]'],
     {'VALOR': '"S/ " & ' + mag('_v'), 'SUB': 'FORMAT ( [Líneas], "#,0" ) & " l&#237;neas &#183; " & FORMAT ( [Plantillas], "#,0" ) & " plantillas"'},
     {'VALOR': 'S/ 120,5 M', 'SUB': '12.400 l&#237;neas &#183; 150 plantillas'},
     'Gasto Ppto 2027 en PEN (positivo), con líneas y plantillas.'),
    ('KPI Moneda Local SVG', ('ReportSection1', 'p1_k2'),
     tarjeta('GASTO EN MONEDA LOCAL', viz=insignia('#DCE8FC', BLUE, '{MON}', 10)),
     ['_uno = HASONEVALUE ( dim_pais[id_pais] )', '_mon = SELECTEDVALUE ( dim_pais[moneda_local] )', '_v = [Gasto Moneda Local]'],
     {'VALOR': 'IF ( _uno, ' + mag('_v') + ', "&#8212;" )',
      'SUB': 'IF ( _uno, "Pa&#237;s: " & SELECTEDVALUE ( dim_pais[pais_bi] ), "Elige un pa&#237;s: no se suman monedas" )',
      'MON': 'IF ( _uno, _mon, "FX" )'},
     {'VALOR': '85,2 MM', 'SUB': 'Pa&#237;s: Colombia', 'MON': 'COP'},
     'Gasto en la moneda del país; sólo con un país elegido.'),
    ('KPI Plantillas SVG', ('ReportSection1', 'p1_k3'),
     tarjeta('PLANTILLAS CON PPTO', viz=DOC),
     [],
     {'VALOR': 'FORMAT ( COALESCE ( [Plantillas], 0 ), "#,0" )', 'SUB': 'FORMAT ( COALESCE ( [Líneas], 0 ), "#,0" ) & " l&#237;neas con Ppto 2027"'},
     {'VALOR': '150', 'SUB': '12.400 l&#237;neas con Ppto 2027'},
     'Plantillas y líneas con Ppto 2027.'),
    ('KPI Cuarentena SVG', ('ReportSection1', 'p1_k4'),
     tarjeta('PPTO EN CUARENTENA', viz=anillo()),
     ['_p = COALESCE ( [% Cuarentena], 0 )'],
     {'VALOR': 'FORMAT ( _p, "0.0%" )', 'COLOR': PCT_COLOR('_p'), 'ARCO': ARCO('_p'), 'PCT': PCT_TXT('_p'),
      'SUB': 'SWITCH ( TRUE (), _p = 0, "Todo entra al reporte", _p <= 0.02, "Revisar l&#237;neas retenidas", "Alto: revisar plantillas" )'},
     {'VALOR': '0,0 %', 'COLOR': GREEN, 'ARCO': '0', 'PCT': '0%', 'SUB': 'Todo entra al reporte'},
     '% del Ppto cargado retenido por errores; verde 0 %, ámbar hasta 2 %, coral más.'),
    ('KPI Flags SVG', ('ReportSection3', 'p3_k1'),
     tarjeta('HALLAZGOS DE VALIDACI&#211;N', hero=True),
     [],
     {'VALOR': 'FORMAT ( COALESCE ( [Flags], 0 ), "#,0" )',
      'SUB': '"Errores " & FORMAT ( COALESCE ( [Flags Error], 0 ), "#,0" ) & " &#183; Alertas " & FORMAT ( COALESCE ( [Flags Alerta], 0 ), "#,0" )'},
     {'VALOR': '16', 'SUB': 'Errores 5 &#183; Alertas 7'},
     'Total de flags con su reparto errores / alertas.'),
    ('KPI Flags Error SVG', ('ReportSection3', 'p3_k2'),
     tarjeta('ERRORES', viz=insignia('{TINTE}', '{COLOR}', '{ICONO}', 18)),
     ['_e = COALESCE ( [Flags Error], 0 )'],
     {'VALOR': 'FORMAT ( _e, "#,0" )', 'SUB': 'IF ( _e = 0, "Ninguna l&#237;nea bloqueada", "Bloquean la l&#237;nea: va a cuarentena" )',
      'TINTE': f'IF ( _e = 0, "#DAFAD2", "#FDE3D3" )', 'COLOR': f'IF ( _e = 0, "{GREEN}", "{CORAL}" )', 'ICONO': 'IF ( _e = 0, "&#10003;", "!" )'},
     {'VALOR': '5', 'SUB': 'Bloquean la l&#237;nea: va a cuarentena', 'TINTE': '#FDE3D3', 'COLOR': CORAL, 'ICONO': '!'},
     'Flags de severidad ERROR / BLOQUEANTE.'),
    ('KPI Plantillas Error SVG', ('ReportSection3', 'p3_k3'),
     tarjeta('PLANTILLAS CON ERROR', viz=anillo()),
     ['_e = COALESCE ( [Plantillas con Error], 0 )', '_t = DISTINCTCOUNT ( dim_plantilla[id_plantilla] )', '_p = DIVIDE ( _e, _t, 0 )'],
     {'VALOR': 'FORMAT ( _e, "#,0" )', 'SUB': '"de " & FORMAT ( _t, "#,0" ) & " plantillas cargadas"',
      'COLOR': f'IF ( _e = 0, "{GREEN}", "{CORAL}" )', 'ARCO': ARCO('_p'), 'PCT': PCT_TXT('_p')},
     {'VALOR': '2', 'SUB': 'de 3 plantillas cargadas', 'COLOR': CORAL, 'ARCO': str(round(2 / 3 * CIRC)), 'PCT': '67%'},
     'Plantillas con al menos un error sobre las cargadas.'),
    ('KPI Cuarentena PEN SVG', ('ReportSection3', 'p3_k4'),
     tarjeta('PPTO EN CUARENTENA &#183; PEN', viz=anillo()),
     ['_v = - COALESCE ( [Ppto Cuarentena PEN], 0 )', '_p = COALESCE ( [% Cuarentena], 0 )'],
     {'VALOR': '"S/ " & ' + mag('_v'), 'SUB': 'FORMAT ( _p, "0.0%" ) & " del Ppto cargado"',
      'COLOR': PCT_COLOR('_p'), 'ARCO': ARCO('_p'), 'PCT': PCT_TXT('_p')},
     {'VALOR': 'S/ 486,6 K', 'SUB': '4,5 % del Ppto cargado', 'COLOR': CORAL, 'ARCO': str(round(0.045 * CIRC)), 'PCT': '5%'},
     'Monto retenido en cuarentena (gasto en positivo) y su % del total cargado.'),
]


def dax(svg, vars_, marc):
    partes = re.split(r'\{([A-Z]+)\}', svg); trozos = []
    for i, p in enumerate(partes):
        if i % 2: trozos.append(marc[p])
        elif p: trozos.append('"' + p.replace('"', '""') + '"')
    cuerpo = '\n\t\t\t\t& '.join(trozos)
    v = ''.join(f'\n\t\t\tVAR {x}' for x in vars_)
    # '%' y '#' van codificados en el data URI (en ese orden)
    return (f'{v}\n\t\t\tVAR _svg =\n\t\t\t\t{cuerpo}\n\t\t\tRETURN\n'
            f'\t\t\t\t"data:image/svg+xml;utf8," & SUBSTITUTE ( SUBSTITUTE ( _svg, "%", "%25" ), "#", "%23" )')


def medidas_tmdl():
    out = []
    for nombre, _, svg, vars_, marc, _, desc in KPIS:
        out.append(f"\t/// {desc}\n\tmeasure '{nombre}' = ```{dax(svg, vars_, marc)}\n\t\t\t```\n"
                   f"\t\tdataCategory: ImageUrl\n\t\tdisplayFolder: 5 Diseño KPI\n\t\tlineageTag: {uuid.uuid4()}\n")
    return '\n'.join(out)


lit = lambda v: {'expr': {'Literal': {'Value': v}}}
col = lambda c: {'solid': {'color': lit(f"'{c}'")}}


def visual_tabla(nombre, medida, x, y, w, h, z):
    return {
        '$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.12.0/schema.json',
        'name': nombre, 'position': {'x': x, 'y': y, 'z': z, 'width': w, 'height': h},
        'visual': {
            'visualType': 'tableEx',
            'query': {'queryState': {'Values': {'projections': [{
                'field': {'Measure': {'Expression': {'SourceRef': {'Entity': '_Medidas'}}, 'Property': medida}},
                'queryRef': f'_Medidas.{medida}', 'displayName': ' '}]}}},
            'objects': {
                'columnHeaders': [{'properties': {'fontColor': col(BG), 'backColor': col(BG), 'fontSize': lit('8D')}}],
                'values': [{'properties': {'backColorPrimary': col(BG), 'backColorSecondary': col(BG), 'fontColorPrimary': col(BG)}}],
                'grid': [{'properties': {'gridHorizontal': lit('false'), 'gridVertical': lit('false'), 'rowPadding': lit('0D'),
                                         'outlineColor': col(BG), 'outlineWeight': lit('0D'),
                                         'imageHeight': lit('88D'), 'imageWidth': lit('287D')}}],
            },
            'visualContainerObjects': {
                'title': [{'properties': {'show': lit('false')}}],
                'background': [{'properties': {'show': lit('false')}}],
                'border': [{'properties': {'show': lit('false')}}],
                'dropShadow': [{'properties': {'show': lit('false')}}],
                'visualHeader': [{'properties': {'show': lit('false')}}],
                'padding': [{'properties': {'top': lit('0D'), 'bottom': lit('0D'), 'left': lit('0D'), 'right': lit('0D')}}],
            },
            'drillFilterOtherVisuals': True,
        },
    }


# fila de tarjetas: la cabecera vacía de la tabla queda en el hueco bajo la banda; debajo, el resto baja 12 px
POS_GRAF = {'ReportSection1': {'p1_c1': (16, 232, 616, 224), 'p1_c2': (648, 232, 616, 224),
                               'p1_m1': (16, 472, 616, 224), 'f232ce0ae11587fe96a8': (648, 472, 616, 224)},
            'ReportSection3': {'p3_c1': (16, 232, 490, 464), 'p3_t1': (522, 232, 742, 464)}}


def aplicar(pbip):
    sm = glob.glob(os.path.join(pbip, '*.SemanticModel', 'definition', 'tables', '_Medidas.tmdl'))[0]
    t = open(sm, encoding='utf-8').read()
    if 'KPI Gasto Ppto SVG' in t: raise SystemExit('Las medidas KPI ya existen en el modelo')
    i = t.index('\n\tcolumn Medidas')
    t = t[:i] + '\n' + medidas_tmdl() + t[i:]
    open(sm, 'w', encoding='utf-8').write(t)
    pages = glob.glob(os.path.join(pbip, '*.Report', 'definition', 'pages'))[0]
    for k, (nombre, (pg, vis), *_r) in enumerate(KPIS):
        vd = os.path.join(pages, pg, 'visuals', vis)
        p = json.load(open(os.path.join(vd, 'visual.json'), encoding='utf-8'))['position']
        shutil.rmtree(vd)
        nuevo = vis.replace('_k', '_kpi')
        os.makedirs(os.path.join(pages, pg, 'visuals', nuevo))
        json.dump(visual_tabla(nuevo, nombre, p['x'], 100, p['width'], 126, p['z']),
                  open(os.path.join(pages, pg, 'visuals', nuevo, 'visual.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'{pg}: {vis} -> {nuevo} ({nombre})')
    for pg, pos in POS_GRAF.items():
        for v, (x, y, w, h) in pos.items():
            vp = os.path.join(pages, pg, 'visuals', v, 'visual.json'); j = json.load(open(vp, encoding='utf-8'))
            j['position'].update(x=x, y=y, width=w, height=h); json.dump(j, open(vp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def preview(carpeta):
    os.makedirs(carpeta, exist_ok=True); celdas = []
    import urllib.parse
    for nombre, (pg, _), svg, _, _, ej, _ in KPIS:
        s = re.sub(r'\{([A-Z]+)\}', lambda m: ej[m.group(1)], svg)
        uri = 'data:image/svg+xml;utf8,' + s.replace('%', '%25').replace('#', '%23')
        celdas.append(f"<figure><img src=\"{uri}\" width='300' height='92'><figcaption>{nombre}</figcaption></figure>")
    html = ("<!doctype html><meta charset='utf-8'><link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap'>"
            f"<body style='margin:0;padding:24px;background:{BG};font-family:Inter'><div style='display:grid;grid-template-columns:repeat(4,300px);gap:16px'>"
            + ''.join(celdas) + "</div><style>figure{margin:0}figcaption{font-size:10px;color:#4F6772;margin-top:4px}</style></body>")
    open(os.path.join(carpeta, 'kpis_preview.html'), 'w', encoding='utf-8').write(html)
    return os.path.join(carpeta, 'kpis_preview.html')


if __name__ == '__main__':
    if '--preview' in sys.argv:
        print(preview(sys.argv[sys.argv.index('--preview') + 1]))
    if sys.argv[1] != '--preview':
        aplicar(sys.argv[1])
