"""Aplica el diseño corporativo (Guía del Proceso: Inter, paleta Credicorp, estilo Apple) a un .pbip en formato PBIR.

- Tema: reemplaza StaticResources/RegisteredResources/CredicorpCapital.json.
- Fondo de cada página: PNG con banda, logo, título y montañas (generar_diseno_bi.py), registrado como recurso.
- Quita la banda, los títulos en cuadro de texto y el logo vacío (ya vienen en el fondo).
- Reacomoda los visuales en una grilla de 16 px: filtros generales dentro de la banda, contenido debajo.
No toca el modelo semántico, las medidas ni los filtros guardados.

Uso:  python3 disenar_pbip.py <carpeta con el .pbip> <carpeta de salida>
"""
import os, sys, json, shutil, tempfile, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generar_diseno_bi as G

# página -> (n° de fondo, visuales a quitar, posiciones {visual: (x, y, w, h)})
BANDA_Y, BANDA_H, FIN_BANDA = 24, 60, 1100


def banda(*nombres, anchos=None):
    """Filtros generales alineados a la derecha dentro de la banda oscura, antes de las montañas."""
    anchos = anchos or [128] * len(nombres)
    x = FIN_BANDA - sum(anchos) - 8 * (len(nombres) - 1); out = {}
    for n, w in zip(nombres, anchos):
        out[n] = (x, BANDA_Y, w, BANDA_H); x += w + 8
    return out


def fila(nombres, y, h, x0=16, ancho=1248, gap=16, pesos=None):
    pesos = pesos or [1] * len(nombres)
    util = ancho - gap * (len(nombres) - 1); x = x0; out = {}
    for n, p in zip(nombres, pesos):
        w = round(util * p / sum(pesos)); out[n] = (x, y, w, h); x += w + gap
    return out


QUITAR = ['hdr_band', 'p0_titulo', 'p1_titulo', 'p2_titulo', 'p3_titulo', 'd_titulo', 'p2_marca']
PAGINAS = {
    'ReportSection1': ('01', {**banda('p1_s_pais', 'a8ba84c364f335cb755a', 'p1_s_mes', 'p1_s_vehiculo', anchos=[100, 100, 100, 108]),
                              **fila(['p1_k1', 'p1_k2', 'p1_k3', 'p1_k4'], 112, 92),
                              **fila(['p1_c1', 'p1_c2'], 220, 232),
                              **fila(['p1_m1', 'f232ce0ae11587fe96a8'], 468, 228)}),
    'ReportSection0': ('02', {**banda('p0_s_pais', 'p0_s_tipo', 'p0_s_mes'),
                              **fila(['7442d89636597f568b1c', 'p0_s_ceco', 'd5bc0e26ccb1d54cbfcb'], 112, 60),
                              'p0_m1': (16, 188, 1248, 508)}),
    'ReportSectionDirInd': ('03', {**banda('04443e1b53e8d836638d', '2b35c67e623d925d034b', anchos=[128, 156]),
                                   **fila(['d_s_pais', 'd_s_udn', 'd_s_vehiculo', 'd_s_mon'], 112, 60),
                                   'd_m1': (16, 188, 1248, 508)}),
    'ReportSection2': ('04', {**banda('p2_s_pais', 'a2e3ac96175e6077935b', 'p2_s_mes'),
                              **fila(['p2_s_area', 'p2_s_n1', 'p2_s_vehiculo'], 112, 60),
                              'p2_m1': (16, 188, 1248, 252), 'p2_t1': (16, 456, 1248, 240)}),
    'ReportSection3': ('05', {**banda('p3_s_sev', 'p3_s_pais', '015574957c74db68f30d'),
                              **fila(['p3_k1', 'p3_k2', 'p3_k3', 'p3_k4'], 112, 92),
                              **fila(['p3_c1', 'p3_t1'], 220, 476, pesos=[2, 3])}),
}
lit = lambda v: {'expr': {'Literal': {'Value': v}}}
# filtro Vehículo (dim_vehiculo) clonado del de Contable/Gestión y sincronizado (grupo 'vehiculo').
# No va en Calidad: los flags no se relacionan con dim_vehiculo.
VEHICULO = {'ReportSection1': 'p1_s_vehiculo', 'ReportSectionDirInd': 'd_s_vehiculo', 'ReportSection2': 'p2_s_vehiculo'}
VEH_BASE = ('ReportSection0', 'p0_s_ceco')


def main(src, dst):
    if os.path.exists(dst): raise SystemExit(f'Ya existe la salida: {dst}')
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('cache.abf', '~$*'))
    rep = glob.glob(os.path.join(dst, '**', '*.Report'), recursive=True)[0]
    d = os.path.join(rep, 'definition'); rr = os.path.join(rep, 'StaticResources', 'RegisteredResources')
    # tema
    json.dump(G.tema(), open(os.path.join(rr, 'CredicorpCapital.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    # fondos
    tmp = tempfile.mkdtemp(); G.main(tmp)
    rj = json.load(open(os.path.join(d, 'report.json'), encoding='utf-8'))
    pkg = [p for p in rj['resourcePackages'] if p['name'] == 'RegisteredResources'][0]
    cambios = []
    base = json.load(open(os.path.join(d, 'pages', *VEH_BASE[:1], 'visuals', VEH_BASE[1], 'visual.json'), encoding='utf-8'))
    for pg, nombre in VEHICULO.items():
        v = json.loads(json.dumps(base)); v['name'] = nombre; v['position'].pop('tabOrder', None)
        os.makedirs(os.path.join(d, 'pages', pg, 'visuals', nombre))
        json.dump(v, open(os.path.join(d, 'pages', pg, 'visuals', nombre, 'visual.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        cambios.append(f'{pg}: filtro Vehículo agregado ({nombre})')
    for pg, (n, pos) in PAGINAS.items():
        png = glob.glob(os.path.join(tmp, f'Fondo {n} - *.png'))[0]; item = f'fondo_{n}.png'
        shutil.copy(png, os.path.join(rr, item))
        pkg['items'] = [i for i in pkg['items'] if i['name'] != item] + [{'name': item, 'path': item, 'type': 'Image'}]
        pj_path = os.path.join(d, 'pages', pg, 'page.json'); pj = json.load(open(pj_path, encoding='utf-8'))
        pj.setdefault('objects', {})['background'] = [{'properties': {
            'image': {'image': {'name': lit(f"'{item}'"),
                                'url': {'expr': {'ResourcePackageItem': {'PackageName': 'RegisteredResources', 'PackageType': 1, 'ItemName': item}}},
                                'scaling': lit("'Fit'")}},
            'transparency': lit('0D')}}]
        pj['objects']['outspace'] = [{'properties': {'color': {'solid': {'color': lit(f"'{G.BG}'")}}}}]
        json.dump(pj, open(pj_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        vis = os.path.join(d, 'pages', pg, 'visuals')
        for q in QUITAR:
            if os.path.isdir(os.path.join(vis, q)): shutil.rmtree(os.path.join(vis, q)); cambios.append(f'{pj["displayName"]}: quitado {q}')
        for v, (x, y, w, h) in pos.items():
            vp = os.path.join(vis, v, 'visual.json')
            if not os.path.exists(vp): raise SystemExit(f'No existe el visual {v} en {pg}')
            vj = json.load(open(vp, encoding='utf-8')); vj['position'].update(x=x, y=y, width=w, height=h)
            json.dump(vj, open(vp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        sobran = [os.path.basename(x) for x in glob.glob(os.path.join(vis, '*'))
                  if os.path.basename(x) not in pos and not json.load(open(os.path.join(x, 'visual.json'))).get('isHidden')]
        if sobran: raise SystemExit(f'{pg}: visuales visibles sin posición asignada: {sobran}')
        cambios.append(f'{pj["displayName"]}: fondo {item} · {len(pos)} visuales reubicados')
    json.dump(rj, open(os.path.join(d, 'report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('\n'.join(cambios))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
