"""«👀 Vista previa de etiquetas y círculos»: una diapositiva por cada etiqueta y cada círculo, sobre el cuadro exacto del
video donde va a aparecer, ANTES de ponerlos (que tarda ~15 min). Así apruebas, editas o quitas sin rehacer nada.

Uso (desde la carpeta del proyecto): python vista.py --proyecto .  [--solo etiqueta:3]
Deja vista_extras/NN.jpg y vista_extras/lista.json. Es una vista aproximada (dibujada aquí, al instante); el video final
usa el mismo lugar, tamaño, colores y textos, con su animación.
"""
import argparse, json, os, re, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'senales'))
sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

DESFASE = 0.3
ROJO = (255, 45, 85)
FUENTES = [r'C:\Windows\Fonts\ariblk.ttf', r'C:\Windows\Fonts\arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
SALIDA = 'vista_extras'


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


def etiqueta(dib, e, W):
    """La tarjeta de arriba a la derecha (como Etiqueta.tsx): título chico y el dato grande."""
    ft, fx = fuente(26), fuente(52)
    tit, txt = str(e.get('titulo') or '').upper(), str(e.get('texto') or '')
    ancho = int(max(dib.textlength(tit, font=ft), dib.textlength(txt, font=fx))) + 150
    right, top = W - 70, 90
    dib.rounded_rectangle([right - ancho, top, right, top + 130], radius=24, fill=(12, 14, 22), outline=(255, 210, 63), width=4)
    dib.text((right - ancho + 110, top + 34), tit, font=ft, fill=(200, 200, 210), anchor='lm')
    dib.text((right - ancho + 110, top + 84), txt, font=fx, fill='white', anchor='lm')
    dib.ellipse([right - ancho + 26, top + 36, right - ancho + 86, top + 96], fill=(255, 210, 63))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--solo', default='', help='clase:índice (etiqueta:3 o senal:0) para rehacer una sola')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
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

    items = [('etiqueta', i, e) for i, e in enumerate(leer('etiquetas.json'))] +             [('senal', i, s) for i, s in enumerate(leer('senales.json'))]
    lista = []
    for clase, i, x in items:
        clave = f'{clase}:{i}'
        nombre = f"{'e' if clase == 'etiqueta' else 's'}{i:02d}.jpg"
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
                etiqueta(dib, x, W)
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
                      'x': x.get('x'), 'y': x.get('y')})
    lista.sort(key=lambda z: (z['t'] is None, z['t'] or 0))
    json.dump(lista, open(lista_f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Vista previa: {len(lista)} diapositivas en {SALIDA}/')


if __name__ == '__main__':
    main()
