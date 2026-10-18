"""Fondos de página (PNG 1280x720) y tema Power BI con el diseño de la Guía del Proceso.

Salida: ../Diseño Power BI/
  - Fondo NN - <página>.png   (Formato de página > Fondo del lienzo > Imagen · Ajustar · Transparencia 0 %)
  - Tema Ppto27 Guia.json      (Ver > Temas > Buscar temas)
Uso:  python3 generar_diseno_bi.py
"""
import os, re, json, subprocess, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(AQUI, 'salida')
GUIA = os.path.join(AQUI, '..', 'docs', 'guia-del-proceso.html')
CHROME = os.environ.get('CHROME_PATH') or next((c for c in ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
          r'C:\Program Files\Google\Chrome\Application\chrome.exe', '/usr/bin/google-chrome') if os.path.exists(c)), 'chrome')

INK, CORAL, CORAL2, BLUE, BG, PAPER, MUTED, LINE = '#15192C', '#D74028', '#EA6B58', '#2F71E5', '#ECEFF1', '#FFFFFF', '#4F6772', '#D7DDE2'

PAGINAS = [
    ('01', 'Resumen', 'Resumen del presupuesto'),
    ('02', 'Contable y Gestión', 'Contable y gestión'),
    ('03', 'Dir-Ind (UdN)', 'Gestión Dir/Ind por UdN · Formato Perú'),
    ('04', 'Detalle CeCo', 'Detalle por CeCo y cuenta'),
    ('05', 'Calidad', 'Calidad de las plantillas'),
    ('00', 'Generico', ''),
]

MONTES = f'''<svg class="montes" viewBox="0 0 520 300"><defs>
<linearGradient id="mg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#D7DDE2"/><stop offset="1" stop-color="#637D8D"/></linearGradient>
<linearGradient id="mr" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#DE604D"/><stop offset="1" stop-color="#B23521"/></linearGradient></defs>
<polygon points="40,300 150,150 260,300" fill="{BLUE}" opacity=".9"/><polygon points="150,300 330,46 510,300" fill="url(#mg)"/>
<polygon points="230,300 300,206 370,300" fill="#3B4D56"/><polygon points="330,300 440,150 550,300" fill="url(#mr)"/></svg>'''


def html(titulo, logo):
    return f'''<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1280px;height:720px;overflow:hidden;background:{BG};font-family:Inter,'Segoe UI',Helvetica,Arial,sans-serif}}
.banda{{position:absolute;left:16px;top:12px;width:1248px;height:84px;background:{INK};border-radius:14px;overflow:hidden}}
.montes{{position:absolute;right:-4px;bottom:-2px;width:150px;opacity:.95}}
.fila{{position:absolute;left:18px;top:0;height:84px;display:flex;align-items:center;gap:18px}}
.logo{{flex:none;background:#fff;border-radius:8px;padding:8px 12px;display:flex;align-items:center}}
.logo img{{height:26px;width:auto;display:block;max-width:none}}
.txt{{flex:none}}
.eyebrow{{font-size:10.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:{CORAL2}}}
h1{{font-size:22px;font-weight:800;letter-spacing:-.01em;color:#fff;margin-top:4px;white-space:nowrap;line-height:1.15}}
.pie{{position:absolute;left:24px;right:24px;bottom:8px;display:flex;justify-content:space-between;font-size:10px;color:{MUTED}}}
.pie b{{color:{INK};font-weight:600}}
</style></head><body>
<div class="banda">{MONTES}
<div class="fila">{f'<span class="logo"><img src="{logo}"></span>' if logo else ''}
<div class="txt"><div class="eyebrow">Planeamiento · Presupuesto 2027</div>{f'<h1>{titulo}</h1>' if titulo else '<h1>Ppto 2027</h1>'}</div></div>
</div>
<div class="pie"><span><b>Ppto27</b> · Databricks → Power BI (DirectQuery) · montos en negativo = gasto</span><span>Planeamiento · Credicorp Capital</span></div>
</body></html>'''


def main(out=None):
    out = out or OUT
    os.makedirs(out, exist_ok=True)
    m = re.search(r'<span class="logo"><img src="(data:image/[^"]+)"', open(GUIA, encoding='utf-8').read())
    logo = m.group(1) if m else ''
    tmp = tempfile.mkdtemp()
    for n, nombre, titulo in PAGINAS:
        h = os.path.join(tmp, f'p{n}.html'); open(h, 'w', encoding='utf-8').write(html(titulo, logo))
        png = os.path.join(out, f'Fondo {n} - {nombre}.png')
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                        '--window-size=1280,720', '--virtual-time-budget=4000', f'--screenshot={png}', 'file://' + h],
                       check=True, capture_output=True)
        print('OK', os.path.basename(png))
    json.dump(tema(), open(os.path.join(out, 'Tema Ppto27 Guia.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('OK Tema Ppto27 Guia.json')


def tema():
    """Tema corporativo estilo Apple: Inter, mucho aire, tarjetas blancas redondeadas con sombra suave."""
    sol = lambda c: {'solid': {'color': c}}
    semi = 'Inter SemiBold, Segoe UI Semibold, wf_segoe-ui_semibold, helvetica, arial, sans-serif'
    norm = 'Inter, Segoe UI, wf_segoe-ui_normal, helvetica, arial, sans-serif'
    TRAZO, SUAVE = '#E3E7EA', '#F6F8F9'
    tabla = {
        'columnHeaders': [{'fontColor': sol('#FFFFFF'), 'backColor': sol(INK), 'fontFamily': semi, 'fontSize': 9, 'outline': 'None'}],
        'total': [{'fontColor': sol(INK), 'backColor': sol('#FDE3D3'), 'fontFamily': semi, 'fontSize': 9}],
        'grid': [{'gridHorizontal': True, 'gridHorizontalColor': sol(TRAZO), 'gridVertical': False, 'rowPadding': 4, 'outlineColor': sol(TRAZO)}],
        'values': [{'fontColorPrimary': sol(INK), 'backColorPrimary': sol(PAPER), 'fontColorSecondary': sol(INK),
                    'backColorSecondary': sol(SUAVE), 'fontFamily': norm, 'fontSize': 9}],
    }
    grafico = {
        'dataPoint': [{'defaultColor': sol(CORAL)}],
        'categoryAxis': [{'showAxisTitle': False, 'labelColor': sol(MUTED), 'fontFamily': norm, 'fontSize': 8}],
        'valueAxis': [{'showAxisTitle': False, 'labelColor': sol(MUTED), 'fontFamily': norm, 'fontSize': 8,
                       'gridlineShow': True, 'gridlineColor': sol(TRAZO), 'gridlineStyle': 'solid'}],
        'legend': [{'labelColor': sol(MUTED), 'fontFamily': norm}],
    }
    return {
        'name': 'Credicorp Capital · Ppto27',
        'dataColors': [CORAL, INK, BLUE, '#637D8D', '#D68502', '#188737', CORAL2, '#6294EB', '#FBC141', '#AAB9C2'],
        'background': PAPER, 'foreground': INK, 'tableAccent': INK,
        'good': '#188737', 'neutral': '#D68502', 'bad': CORAL,
        'maximum': CORAL, 'center': '#FBC141', 'minimum': '#FDE3D3', 'null': LINE,
        'textClasses': {
            'callout': {'fontSize': 24, 'fontFace': semi, 'color': INK},
            'title': {'fontSize': 11, 'fontFace': semi, 'color': INK},
            'header': {'fontSize': 10, 'fontFace': semi, 'color': INK},
            'label': {'fontSize': 9, 'fontFace': norm, 'color': MUTED},
        },
        'visualStyles': {
            '*': {'*': {
                'background': [{'show': True, 'color': sol(PAPER), 'transparency': 0}],
                'border': [{'show': True, 'color': sol(TRAZO), 'radius': 12}],
                'dropShadow': [{'show': True, 'color': sol(INK), 'position': 'Outer', 'preset': 'Bottom', 'transparency': 90}],
                'title': [{'show': True, 'fontColor': sol(INK), 'fontSize': 11, 'fontFamily': semi}],
                'visualHeader': [{'show': True, 'transparency': 100}],
                'padding': [{'top': 10, 'bottom': 10, 'left': 14, 'right': 14}],
            }},
            'page': {'*': {
                'background': [{'color': sol(BG), 'transparency': 0}],
                'outspace': [{'color': sol(BG)}],
            }},
            'slicer': {'*': {
                'background': [{'show': True, 'color': sol(PAPER), 'transparency': 0}],
                'border': [{'show': True, 'color': sol(TRAZO), 'radius': 10}],
                'dropShadow': [{'show': False}],
                'padding': [{'top': 4, 'bottom': 4, 'left': 10, 'right': 10}],
                'title': [{'show': True, 'fontColor': sol(MUTED), 'fontSize': 8, 'fontFamily': semi}],
                'header': [{'fontColor': sol(MUTED), 'textSize': 8, 'fontFamily': semi}],
                'items': [{'fontColor': sol(INK), 'textSize': 9, 'fontFamily': norm}],
            }},
            'card': {'*': {
                'labels': [{'color': sol(INK), 'fontSize': 24, 'fontFamily': semi}],
                'categoryLabels': [{'show': False}],
                'title': [{'show': True, 'fontColor': sol(MUTED), 'fontSize': 9, 'fontFamily': semi}],
            }},
            'tableEx': {'*': tabla},
            'pivotTable': {'*': {**tabla,
                'rowHeaders': [{'fontColor': sol(INK), 'backColor': sol(PAPER), 'fontFamily': norm, 'fontSize': 9}],
                'subTotals': [{'fontColor': sol(INK), 'backColor': sol(SUAVE), 'fontFamily': semi}],
            }},
            'clusteredColumnChart': {'*': grafico},
            'clusteredBarChart': {'*': grafico},
            'columnChart': {'*': grafico},
            'barChart': {'*': grafico},
            'textbox': {'*': {'background': [{'show': False}], 'border': [{'show': False}], 'dropShadow': [{'show': False}]}},
            'image': {'*': {'background': [{'show': False}], 'border': [{'show': False}], 'dropShadow': [{'show': False}]}},
            'shape': {'*': {'background': [{'show': False}], 'border': [{'show': False}], 'dropShadow': [{'show': False}]}},
        },
    }


if __name__ == '__main__':
    main()
