"""«👀 Vista previa de etiquetas y círculos»: una diapositiva por cada etiqueta y cada círculo, sobre el cuadro exacto del
video donde va a aparecer, ANTES de ponerlos (que tarda ~15 min). Así apruebas, editas o quitas sin rehacer nada.

Uso (desde la carpeta del proyecto): python vista.py --proyecto .  [--solo etiqueta:3]
Deja vista_extras/NN.jpg y vista_extras/lista.json. Es una vista aproximada (dibujada aquí, al instante); el video final
usa el mismo lugar, tamaño, colores y textos, con su animación.
"""
import argparse, json, math, os, re, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'senales'))
sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
sys.path.insert(0, os.path.join(RAIZ, 'deteccion'))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

DESFASE = 0.3
ROJO = (255, 45, 85)
FUENTES = [r'C:\Windows\Fonts\ariblk.ttf', r'C:\Windows\Fonts\arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
SALIDA = 'vista_extras'
ESTILO = 'contorno'  # se lee de remotion/src/estilo.ts al empezar
ROSA, FONDO_ROTULO = '#ff2bd6', (12, 14, 22, 209)  # los de remotion/src/estilo.ts


def estilo_senal():
    """El estilo de círculos y recuadros que usa el video (remotion/src/estilo.ts → senal): 'contorno' o 'marcador'."""
    try:
        m = re.search(r"senal:\s*'(\w+)'", open(os.path.join(RAIZ, 'remotion', 'src', 'estilo.ts'), encoding='utf-8').read())
        return m.group(1) if m else 'contorno'
    except OSError:
        return 'contorno'


def flecha(dib, s, col, ancho=11):
    """La flecha de Senal.tsx ya dibujada: llega desde `angulo` (0 = desde la derecha, -35 si no se dice) con una curva leve."""
    x, y, r = float(s['x']), float(s['y']), float(s.get('r') or 70)
    a = math.radians(float(s['angulo']) if s.get('angulo') is not None else -35)
    hueco = float(s['hueco']) if s.get('hueco') is not None else 18
    px, py = x + math.cos(a) * hueco, y + math.sin(a) * hueco
    ox, oy = px + math.cos(a) * r * 2.2, py + math.sin(a) * r * 2.2
    cx, cy = (px + ox) / 2 - math.sin(a) * 30, (py + oy) / 2 + math.cos(a) * 30
    curva = [((1 - t) ** 2 * ox + 2 * (1 - t) * t * cx + t * t * px, (1 - t) ** 2 * oy + 2 * (1 - t) * t * cy + t * t * py)
             for t in (i / 24 for i in range(25))]
    dib.line(curva, fill=col, width=ancho, joint='curve')
    dib.line([(px + math.cos(a + 0.5) * 34, py + math.sin(a + 0.5) * 34), (px, py),
              (px + math.cos(a - 0.5) * 34, py + math.sin(a - 0.5) * 34)], fill=col, width=ancho, joint='curve')


def contorno(img, s):
    """Como Senal.tsx con el estilo «Contorno»: trazo rosa con brillo y la forma del botón si se sabe su tamaño (w, h); el
    foco oscurece alrededor; el rótulo es una píldora oscura con borde rosa. Devuelve la imagen nueva."""
    W, H = img.size
    col = s.get('color') or ROSA
    x, y, r = float(s['x']), float(s['y']), float(s.get('r') or 70)
    w, h = float(s.get('w') or 200), float(s.get('h') or 80)
    tipo, pild = s.get('tipo'), s.get('tipo') == 'circulo' and s.get('w') and s.get('h')
    pw, ph = w + 24, h + 24
    capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    if tipo == 'caja':
        d.rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], radius=min(h / 2, 22), outline=col, width=7)
        alto, marco = h / 2, (w + 20, h + 20, min(h / 2, 22) + 10)
    elif tipo == 'flecha':
        flecha(d, s, col)
        alto, marco = r, None
    elif pild:
        d.rounded_rectangle([x - pw / 2, y - ph / 2, x + pw / 2, y + ph / 2], radius=min(pw, ph) / 2, outline=col, width=7)
        alto, marco = ph / 2, (pw + 20, ph + 20, min(pw, ph) / 2 + 10)
    else:
        d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=7)
        alto, marco = r, None
    base = img.convert('RGBA')
    if s.get('foco') and tipo != 'flecha':  # oscurece el resto (en el video: negro al 85 % con opacidad 0,42)
        hueco = Image.new('L', (W, H), 91)
        dh = ImageDraw.Draw(hueco)
        if marco:
            dh.rounded_rectangle([x - marco[0] / 2, y - marco[1] / 2, x + marco[0] / 2, y + marco[1] / 2], radius=marco[2], fill=0)
        else:
            dh.ellipse([x - r * 1.3 - 30, y - r * 1.3 - 30, x + r * 1.3 + 30, y + r * 1.3 + 30], fill=0)
        base = Image.composite(Image.new('RGBA', (W, H), (0, 0, 0, 255)), base, hueco.filter(ImageFilter.GaussianBlur(20)))
    brillo = capa.filter(ImageFilter.GaussianBlur(6))
    for c in (brillo, brillo, capa):
        base = Image.alpha_composite(base, c)
    if s.get('texto'):  # píldora debajo de la marca, o encima si no cabe; nunca se sale del cuadro
        texto = str(s['texto'])
        ancho = min(620, 60 + len(texto) * 26)
        abajo = y + alto + 110 < H
        left = min(max(x - ancho / 2, 24), W - ancho - 24)
        top = y + alto + 24 if abajo else y - alto - 24 - 74
        rot = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(rot)
        dr.rounded_rectangle([left - 4, top - 4, left + ancho + 4, top + 78], radius=40, fill=FONDO_ROTULO, outline=col, width=4)
        dr.text((left + ancho / 2, top + 37), texto, font=fuente(40), fill='white', anchor='mm')
        base = Image.alpha_composite(base, rot)
    return base.convert('RGB')


def fuente(tam):
    for f in FUENTES:
        if os.path.exists(f):
            return ImageFont.truetype(f, tam)
    return ImageFont.load_default()


def normal(s):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')


def buscar(al, frase):
    chars = [normal(c) for c in al['characters']]
    texto = ''.join(chars)
    mapa = [i for i, c in enumerate(chars) for _ in c]
    pos = texto.find(normal(frase))
    return al['character_start_times_seconds'][mapa[pos]] if pos >= 0 else None


def segundo_de_frase(d, inicio, bloque, frase):
    try:
        al = json.load(open(os.path.join(d, 'voz', f'{bloque}.align.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return None
    t = buscar(al, frase)
    return None if t is None or bloque not in inicio else round(inicio[bloque] + DESFASE + t, 2)


def cuadro(video, t):
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0, t) * 1000)
    ok, f = cap.read()
    cap.release()
    return Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)) if ok else Image.new('RGB', (1920, 1080), (20, 20, 30))


def ovalo_a_mano(dib, x, y, rx, ry, ancho=8):
    """El mismo trazo del video: óvalo levemente irregular que se pasa de largo al cerrar, rojo marcador."""
    pts = []
    for i in range(0, int(64 * 1.12) + 1):
        a = i / 64 * 2 * np.pi - 2.2
        tem = 1 + 0.018 * np.sin(i * 0.45) + 0.01 * np.cos(i * 0.21)
        cre = 1 + 0.06 * i / (64 * 1.12)
        ang = np.radians(-8)
        px, py = np.cos(a) * rx * tem * cre, np.sin(a) * ry * tem * cre
        pts.append((x + px * np.cos(ang) - py * np.sin(ang), y + px * np.sin(ang) + py * np.cos(ang)))
    dib.line(pts, fill=ROJO, width=ancho, joint='curve')


def pildora(dib, x, y, alto_marca, texto, W, H):
    f = fuente(40)
    ancho = min(620, int(dib.textlength(texto, font=f)) + 60)
    abajo = y + alto_marca + 110 < H
    left = int(min(max(x - ancho / 2, 24), W - ancho - 24))
    top = int(y + alto_marca + 24 if abajo else y - alto_marca - 24 - 74)
    dib.rounded_rectangle([left, top, left + ancho, top + 74], radius=14, fill='white')
    dib.rectangle([left, top, left + 12, top + 74], fill=ROJO)
    dib.text((left + 36, top + 37), texto, font=f, fill=(17, 17, 17), anchor='lm')


def etiqueta(dib, e, W, H, lado='izquierda'):
    """La píldora de abajo a la izquierda (como etiquetas/plantilla.html): ícono, título chico y el dato grande."""
    ft, fx = fuente(24), fuente(44)
    tit, txt = str(e.get('titulo') or '').upper(), str(e.get('texto') or '')
    ancho = int(max(dib.textlength(tit, font=ft), dib.textlength(txt, font=fx))) + 130
    alto = 104
    left = W - 80 - ancho if lado == 'derecha' else 80  # a la derecha cuando a la izquierda taparía el teléfono o tu cara
    top = H - 110 - alto
    dib.rounded_rectangle([left - 3, top - 3, left + ancho + 3, top + alto + 3], radius=60, fill=(255, 45, 149))
    dib.rounded_rectangle([left, top, left + ancho, top + alto], radius=58, fill=(20, 17, 36))
    dib.ellipse([left + 20, top + 18, left + 88, top + 86], fill=(34, 211, 238))
    dib.text((left + 108, top + 30), tit, font=ft, fill=(190, 190, 205), anchor='lm')
    dib.text((left + 108, top + 68), txt, font=fx, fill='white', anchor='lm')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--solo', default='', help='clase:índice (etiqueta:3 o senal:0) para rehacer una sola')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    global ESTILO
    ESTILO = estilo_senal()
    video = next((os.path.join(d, v) for v in ('4_musica.mp4', '3_voz.mp4') if os.path.exists(os.path.join(d, v))), None)
    if not video:
        raise SystemExit('ERROR: primero arma el video con voz (falta 3_voz.mp4): la vista previa se dibuja sobre ese video.')
    bloques = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))['bloques']
    inicio = {b['id']: b['inicio_min'] for b in bloques}
    out = os.path.join(d, SALIDA)
    os.makedirs(out, exist_ok=True)
    lista_f = os.path.join(out, 'lista.json')
    previa = {}
    if a.solo and os.path.exists(lista_f):
        previa = {(x['clase'], x['idx']): x for x in json.load(open(lista_f, encoding='utf-8'))}
    leer = lambda n: json.load(open(os.path.join(d, n), encoding='utf-8')) if os.path.exists(os.path.join(d, n)) else []
    import senales as sen
    original = os.path.join(d, 'original.mp4')

    def momento(clase, x):
        """(segundo del video donde aparece, aviso si no se va a poner). Se calcula solo para las que se dibujan."""
        if clase == 'etiqueta':
            if x.get('en') is not None and x.get('bloque') in inicio:
                return round(inicio[x['bloque']] + DESFASE + float(x['en']), 2), None
            return segundo_de_frase(d, inicio, x.get('bloque'), x.get('frase', '')), None
        if x.get('src_t') is not None:
            t0 = sen.segundo_montado(bloques, float(x['src_t']))
            if t0 is None:
                return None, 'ese momento de tu grabación no sale en el video: no se pondrá'
            t, par = sen.afinar(original, video, float(x['src_t']), t0)
            return t, ('no encontré la misma imagen en el video: no se pondrá' if par < 0.6 else None)
        if x.get('t') is not None:
            return float(x['t']), None
        return segundo_de_frase(d, inicio, x.get('bloque'), x.get('frase') or x.get('texto') or ''), None

    senales_ = leer('senales.json')
    items = [('etiqueta', i, e) for i, e in enumerate(leer('etiquetas.json'))] +             [('senal', i, s) for i, s in enumerate(senales_)]
    # tus marcas de «🎯 Flechas y círculos» (marcas_senales/marcas.json) también salen, aunque todavía no estén en senales.json
    # (las que ya se copiaron allí, con el mismo segundo, no se repiten). Se editan en ese panel de la app.
    ya = {round(float(s['src_t']), 1) for s in senales_ if s.get('src_t') is not None}
    copiadas = {str(s['de_marca']) for s in senales_ if isinstance(s, dict) and s.get('de_marca')}  # editadas en el editor de la vista previa
    marcas = leer(os.path.join('marcas_senales', 'marcas.json'))
    for i, m in enumerate(marcas.get('MARCAS', []) if isinstance(marcas, dict) else []):
        z, seg = m.get('zona'), str(m.get('segundo') or '')
        if not z or ':' not in seg or m.get('video', 'original.mp4') != 'original.mp4':
            continue
        src_t = int(seg.split(':')[0]) * 60 + float(seg.split(':')[1])
        if round(src_t, 1) in ya or seg in copiadas:
            continue
        forma = m.get('forma') if m.get('forma') in ('circulo', 'flecha', 'caja') else 'circulo'
        items.append(('marca', i, {'src_t': src_t, 'tipo': forma, 'x': round(z['x'] * 19.2), 'y': round(z['y'] * 10.8),
                                   'r': max(40, round(max(z['w'] * 19.2, z['h'] * 10.8) / 2)), 'w': round(z['w'] * 19.2),
                                   'h': round(z['h'] * 10.8), 'texto': m.get('etiqueta') or '', 'dur': 3,
                                   'por_que': 'tu marca de «🎯 Flechas y círculos» (se edita en ese panel de la app)'}))
    seg_marca = {i: str(m.get('segundo') or '') for i, m in enumerate(marcas.get('MARCAS', []) if isinstance(marcas, dict) else [])}
    lista = []
    for clase, i, x in items:
        clave = f'{clase}:{i}'
        nombre = f"{ {'etiqueta': 'e', 'senal': 's', 'marca': 'm'}[clase] }{i:02d}.jpg"
        if a.solo and a.solo != clave and (clase, i) in previa:
            lista.append({**previa[(clase, i)], 'aprobado': bool(x.get('aprobado'))}); continue
        t, aviso = momento(clase, x)
        if t is None and not aviso:
            aviso = f"no encontré «{x.get('frase', '')}» en la voz de {x.get('bloque')}: no se pondrá"
        img = cuadro(video, (t or 0) + (1.2 if clase == 'etiqueta' else 0.6))
        W, H = img.size
        dib = ImageDraw.Draw(img)
        if t is not None and not aviso:
            if clase == 'etiqueta':
                lado = 'izquierda'
                try:  # el mismo lado que va a elegir el armado (solo si el detector ya está en la PC: aquí no se baja nada)
                    import deteccion, etiquetas as et
                    if os.path.exists(deteccion.MODELO):
                        lado = et.lado_libre(video, t, float(x.get('dur', 4)), [x])
                except Exception:
                    pass
                etiqueta(dib, x, W, H, lado)
            elif ESTILO == 'contorno':  # el mismo estilo que va a tener el video
                img = contorno(img, x)
            elif x.get('tipo') == 'flecha':
                flecha(dib, x, ROJO)
                if x.get('texto'):
                    pildora(dib, x['x'], x['y'], x.get('r', 70), x['texto'], W, H)
            else:
                if x.get('tipo') == 'caja':
                    ovalo_a_mano(dib, x['x'], x['y'], x.get('w', 200) * 0.62, x.get('h', 80) * 0.66)
                    alto = x.get('h', 80) / 2
                else:
                    r = x.get('r', 70)
                    ovalo_a_mano(dib, x['x'], x['y'], r * 1.35, r * 0.85)
                    alto = r
                if x.get('texto'):
                    pildora(dib, x['x'], x['y'], alto, x['texto'], W, H)
        img.resize((960, int(960 * H / W))).save(os.path.join(out, nombre), quality=85)
        lista.append({'clase': clase, 'idx': i, 'archivo': nombre, 't': t, 'aviso': aviso, 'bloque': x.get('bloque'),
                      'frase': x.get('frase'), 'tipo': x.get('tipo'), 'titulo': x.get('titulo'), 'texto': x.get('texto'),
                      'por_que': x.get('por_que'), 'duda': x.get('duda'), 'aprobado': bool(x.get('aprobado')),
                      'x': x.get('x'), 'y': x.get('y'), 'manual': bool(x.get('manual')), 'r': x.get('r'), 'w': x.get('w'), 'h': x.get('h'),
                      'dur': x.get('dur'), 'angulo': x.get('angulo'), 'color': x.get('color'), 'hueco': x.get('hueco'),
                      'src_t': x.get('src_t'), 'segundo': seg_marca.get(i) if clase == 'marca' else None})
    # un círculo con rótulo abajo a la izquierda, mientras está la etiqueta: se tapan entre sí
    etqs = [z for z in lista if z['clase'] == 'etiqueta' and z['t'] is not None]
    for z in lista:
        if z['clase'] in ('senal', 'marca') and z['t'] is not None and z.get('texto') and (z.get('x') or 0) < 1000 and (z.get('y') or 0) > 560:
            if any(abs(e['t'] - z['t']) < 4.5 for e in etqs) and not z.get('aviso'):
                z['duda'] = (z.get('duda') + ' · ' if z.get('duda') else '') + 'su rótulo cae sobre la etiqueta de abajo a la izquierda que sale al mismo tiempo: muévelo o quita el rótulo'
    lista.sort(key=lambda z: (z['t'] is None, z['t'] or 0))
    json.dump(lista, open(lista_f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Vista previa: {len(lista)} diapositivas en {SALIDA}/')


if __name__ == '__main__':
    main()
