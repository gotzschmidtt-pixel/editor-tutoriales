"""La pantalla de la PC (material.mp4) en los Shorts resumen (fabian, 03/11/2026: «no se usa el material extra, no hay zooms»).

Gratis. Lee la grabación con el OCR de la app (una vez: queda en material_mapa.json) y, según lo que dice la voz, cambia las
tomas de cámara de esa frase por tomas de la PC con su encuadre: leer el serial, la KEY en la web, pegar la KEY y la página.
«OKAY, Finished» sigue en la cámara: la grabación de pantalla puede traer intentos fallidos. Lo elegido queda en
shorts_resumen.json ({"material": true, "src": s, "claves": [...]}) y fabian lo revisa o cambia en la pestaña antes de armar.
Sin material.mp4 no cambia nada.
"""
import json, os, re

MATERIAL = 'material.mp4'
MAPA = 'material_mapa.json'
PASO_S = 2.0
RE_LEER = re.compile(r'read fastboot|lee[s]? el serial|fastboot reader', re.I)
RE_KEY = re.compile(r'\bkey\b.*(genera|servidor|whatsapp)|(genera|pides).*\bkey\b', re.I)
RE_PEGA = re.compile(r'pega[s]?\s+la\s+key|paste the key', re.I)
RE_ACERCAR = re.compile(r'\bokay\b|\bomitir\b|\bajustes\b', re.I)  # pasos clave: acercamiento en la cámara


def es_pc(toma):
    return isinstance(toma, dict) and bool(toma.get('material'))


def toma_pc(src, cx, cy, w0, w1):
    return {'material': True, 'src': round(float(src), 2),
            'claves': [{'t': 0, 'cx': round(cx, 3), 'cy': round(cy, 3), 'w': round(w0, 3)},
                       {'t': 1, 'cx': round(cx, 3), 'cy': round(cy, 3), 'w': round(w1, 3)}]}


def circulo(src, cx, cy, ancho, dur=8):
    """Un círculo sobre un dato de la grabación (fracciones de la imagen, como las claves)."""
    return {'tipo': 'circulo', 'src': round(float(src), 2), 'cx': round(cx, 3), 'cy': round(cy, 3), 'r': round(ancho, 3), 'dur': dur}


def clave_senal(sn):
    return json.dumps(sn, sort_keys=True)


def dibujar_senales(d, tomas, tmp):
    """Las señales de las tomas de la PC con el mismo dibujo que las de la cámara: {clave: archivo .mov}. Si falla, sin señales."""
    import short
    distintas = {clave_senal(sn): sn for t in tomas for sn in t.get('senales') or []}
    if not distintas:
        return {}
    import cv2
    cap = cv2.VideoCapture(os.path.join(d, MATERIAL))
    W, H = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()
    senales = short._senales()
    trabajos, movs = [], {}
    for k, (c, sn) in enumerate(distintas.items(), 1):
        # el dibujo sale a 1920 de ancho y luego se escala al ancho de la grabación: por eso «y» va en esa misma escala
        s = {'tipo': sn['tipo'], 'x': sn['cx'] * 1920, 'y': sn['cy'] * H * 1920 / W, 'r': sn['r'] * 1920, 'dur': sn.get('dur', 3), 'seguir': False}
        tr, _ = senales.trabajo(os.path.join(d, MATERIAL), s, sn['src'], os.path.join(tmp, f'senal_pc{k:02d}.mov'))
        trabajos.append(tr)
        movs[c] = tr['salida']
    try:
        senales.dibujar(trabajos, tmp)
    except SystemExit as e:
        print(f'· AVISO: las tomas de la PC salen sin círculos: {e}', flush=True)
        return {}
    return {c: f for c, f in movs.items() if os.path.exists(f)}


def mapa(d, avance=print):
    """[{'t': s, 'c': [[texto, x0, y0, x1, y1], ...]}] de material.mp4 con posiciones de 0 a 1. Los cuadros iguales no se releen."""
    import cv2, numpy as np
    video, f = os.path.join(d, MATERIAL), os.path.join(d, MAPA)
    firma = os.path.getmtime(video)
    try:
        g = json.load(open(f, encoding='utf-8'))
        if g.get('firma') == firma:
            return g['cuadros']
    except (OSError, ValueError, KeyError):
        pass
    import ia
    ocr = ia.lector_ocr()
    if ocr is None:
        return []
    cap = cv2.VideoCapture(video)
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30)
    out, prev, textos, t = [], None, [], 0.0
    avance(f'· leo la pantalla de la PC (solo la primera vez): {dur / 60:.0f} min de grabación')
    while t < dur:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, im = cap.read()
        if not ok:
            break
        chico = cv2.cvtColor(cv2.resize(im, (160, 90)), cv2.COLOR_BGR2GRAY).astype(np.int16)
        if prev is None or np.abs(chico - prev).mean() > 0.4:
            H, W = im.shape[:2]
            textos = [[x[0], x[1] / W, x[2] / H, x[3] / W, x[4] / H] for x in ia.leer_textos(ocr, im)]
            prev = chico
        out.append({'t': round(t, 2), 'c': textos})
        t += PASO_S
    cap.release()
    json.dump({'firma': firma, 'cuadros': out}, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
    return out


def _caja(lineas):
    return min(x[1] for x in lineas), min(x[2] for x in lineas), max(x[3] for x in lineas), max(x[4] for x in lineas)


def _con(cuadro, patron):
    return [x for x in cuadro['c'] if re.search(patron, x[0], re.I)]


def momentos(cuadros):
    """Dónde pasa cada cosa en la grabación. Falta la clave si no aparece. Nada después de un intento fallido («FAILED»)."""
    m = {}
    for i, c in enumerate(cuadros):
        if _con(c, r'\bfailed\b'):
            cuadros = cuadros[:i]
            break
    for c in cuadros:
        boton = _con(c, r'read\s*fastboot')
        datos = _con(c, r'device\s*(model|firmware|fb|fastboot)|firmware|fb\s*lock')
        if boton and len(datos) >= 2:
            x0, y0, x1, y1 = _caja(boton + _con(c, r'erase\s*frp|clear\s*log|checking') + datos)
            xd0, yd0, xd1, yd1 = _caja(datos)
            m['leer'] = toma_pc(max(0, c['t'] - 4), (x0 + x1) / 2, (y0 + y1) / 2, min(1, (x1 - x0) * 1.15), (x1 - x0) * 1.03)
            m['datos'] = toma_pc(c['t'] + 1, (xd0 + xd1) / 2, (yd0 + yd1) / 2, max(.2, (xd1 - xd0) * 1.6), max(.16, (xd1 - xd0) * 1.25))
            sn = _con(c, r'fastboot\s*sn')
            if sn:  # el círculo sobre el serial, en cuanto aparece
                x0, y0, x1, y1 = _caja(sn + [x for x in c['c'] if 0 < x[2] - sn[0][2] < .03 and abs(x[1] - sn[0][1]) < .02])
                m['datos']['senales'] = m['leer']['senales'] = [circulo(c['t'], (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * .5)]
                for cl in m['datos']['claves']:  # el serial más arriba: que no lo tapen los subtítulos
                    cl['cy'] = round(((y0 + y1) / 2 + cl['cy']) / 2 + .03, 3)
            break
    for c in cuadros:
        if _con(c, r'key\s*code') and _con(c, r'^\s*key\s*:?\s*$'):
            lin = _con(c, r'^\s*key\s*:?\s*$')[0]
            m['key'] = toma_pc(c['t'] + 1, .5, (lin[2] + lin[4]) / 2, .62, .5)
            m['key2'] = toma_pc(c['t'] + 5, min(.8, lin[1] + .08), (lin[2] + lin[4]) / 2 + .02, .34, .27)
            m['key']['senales'] = m['key2']['senales'] = [circulo(c['t'], lin[1] + .05, lin[4] + .004, .062, 14)]  # el recuadro de la KEY
            break
    desde = m['key']['src'] if 'key' in m else 0
    for c in cuadros:
        if c['t'] <= desde:
            continue
        campo = _con(c, r'erase\s*frp')
        if campo:
            f = campo[0]
            cerca = [x for x in c['c'] if x is not f and abs((x[2] + x[4]) - (f[2] + f[4])) / 2 < .015 and x[1] > f[1]]
            if re.search(r'by\s*code.{8,}', f[0], re.I) or any(len(re.sub(r'\W', '', x[0])) >= 8 for x in cerca):
                m['pega'] = toma_pc(max(0, c['t'] - 1.5), min(.8, f[1] + .1), (f[2] + f[4]) / 2, .38, .27)
                break
    web = [c for c in cuadros if _con(c, r'place\s*order')]
    if web:
        m['web'] = toma_pc(web[0]['t'], .5, .58, .62, .52)
        if len(web) > 5:
            m['web2'] = toma_pc(web[5]['t'], .42, .42, .52, .42)
    return m


def desde_insertos(d):
    """Sin OCR: los momentos del video largo (insertos.json), por lo que nombra cada inserto."""
    try:
        lista = json.load(open(os.path.join(d, 'insertos.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    m = {}
    for i in lista:
        if i.get('material') != MATERIAL or not i.get('claves'):
            continue
        a, b = i['claves'][0], i['claves'][-1]
        t = toma_pc(i['src_t'], a['cx'], a['cy'], a['w'], b['w'])
        frase = i.get('frase', '')
        if re.search(r'read fastboot', frase, re.I):
            m.setdefault('leer', t)
        elif re.search(r'\bkey\b', frase, re.I):
            m.setdefault('key', t)
        elif re.search(r'xiaomiunlock|gsmprime|p[aá]gina', frase, re.I):
            m.setdefault('web', t)
    return m


def elegir(frases, m):
    """Cambia las tomas de las frases según lo que dicen. Devuelve cuántas tocó; respeta las que ya tienen tomas de la PC."""
    n = 0
    for f in frases:
        if any(es_pc(x) for x in f.get('tomas') or []):
            continue
        t = f.get('texto', '')
        nuevas = None
        if f.get('id') == 'WEBS':
            nuevas = [m[k] for k in ('web', 'web2') if k in m]
        elif RE_PEGA.search(t) and 'pega' in m:
            nuevas = [m['pega']] + list(f.get('tomas') or [])[1:]  # el clic y el OKAY siguen en la cámara
        elif RE_LEER.search(t) and RE_KEY.search(t):
            nuevas = [m[k] for k in ('leer', 'key') if k in m]
        elif RE_LEER.search(t):
            nuevas = [m[k] for k in ('leer', 'datos') if k in m]
        elif RE_KEY.search(t):
            nuevas = [m[k] for k in ('key', 'key2') if k in m]
        if nuevas:
            f['tomas'] = nuevas
            n += 1
    return n


def poner(d, r, avance=print):
    """Lo elige para los 3 Shorts (no gasta). Sin material.mp4 no hace nada. Devuelve cuántas frases cambió."""
    if not os.path.isfile(os.path.join(d, MATERIAL)):
        return 0
    try:
        m = momentos(mapa(d, avance)) or desde_insertos(d)
    except Exception as e:  # sin OCR o sin video legible el Short sale con la cámara, como antes
        avance(f'· no pude leer la pantalla de la PC ({e}); uso insertos.json')
        m = desde_insertos(d)
    n = sum(elegir(s.get('frases') or [], m) for s in r.get('shorts') or [])
    r['pc_elegido'] = True
    return n
