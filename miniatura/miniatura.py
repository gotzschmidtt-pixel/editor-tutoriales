"""«🖼 Miniatura automática»: 3 opciones de miniatura de YouTube (1280×720) sacadas de tu video, para probarlas con la
prueba A/B de miniaturas de YouTube.

Gratis, en tu PC:
  1. Elige los cuadros más nítidos y quietos (nitidez/) donde el detector ve el teléfono grande: uno del PROBLEMA (la
     pantalla bloqueada, al comienzo), uno del RESULTADO (al final) y uno contigo con el teléfono si sales en cámara.
  2. Recorta el teléfono del fondo (GrabCut de OpenCV dentro de la caja del detector) y lo pone grande con un borde
     blanco tipo sticker; si en «🎛 Audio e imagen» activaste «✨ Mejorar imagen», el cuadro pasa antes por Real-ESRGAN.
  3. Pone el texto grande con tus colores (remotion/src/estilo.ts) y una flecha hacia el teléfono.
Deja miniatura_1.jpg, miniatura_2.jpg, miniatura_3.jpg y miniatura.json (de dónde sale cada una).

Uso: python miniatura.py --proyecto . [--texto "MOTOROLA|SIN CUENTA"] (la | parte en dos líneas; sin texto, lo arma solo)
"""
import argparse, json, os, re, sys
import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('nitidez', 'deteccion', 'mejorar', 'pantalla'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
import deteccion  # noqa: E402
import mejorar  # noqa: E402
import enderezar  # noqa: E402  el rectángulo de la pantalla: el recorte más limpio del teléfono
from nitidez import analizar  # noqa: E402

W, H = 1280, 720
FUENTES = ['C:/Windows/Fonts/impact.ttf', 'C:/Windows/Fonts/ariblk.ttf', 'C:/Windows/Fonts/arialbd.ttf',
           '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf', '/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf',
           '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
MARCAS = {'MOTOROLA': r'\bmoto(rola)?\b', 'IPHONE': r'iphone|icloud|\bios\b', 'SAMSUNG': r'samsung|galaxy', 'XIAOMI': r'xiaomi|redmi|\bpoco\b',
          'HONOR': r'\bhonor\b', 'HUAWEI': r'huawei'}
PROBLEMAS = [(r'\bfrp\b|cuenta (de )?google', 'SIN CUENTA GOOGLE'), (r'icloud|hello|activaci', 'SIN ICLOUD'),
             (r'\bmdm\b', 'ADIÓS MDM'), (r'bypass', 'BYPASS FÁCIL'), (r'sold', 'PASO A PASO')]


def colores():
    try:
        txt = open(os.path.join(RAIZ, 'remotion', 'src', 'estilo.ts'), encoding='utf-8').read()
        c = dict(re.findall(r"(\w+):\s*'#([0-9a-fA-F]{6})'", txt))
    except OSError:
        c = {}
    hexa = lambda k, x: tuple(int((c.get(k) or x)[i:i + 2], 16) for i in (0, 2, 4))
    return {'rosa': hexa('rosa', 'ff2bd6'), 'amarillo': hexa('amarillo', 'ffd23f'), 'verde': hexa('verde', '38f28a'), 'rojo': hexa('marcador', 'ff2d55')}


def textos(d):
    """Tres textos de dos líneas a partir del guion: la marca y el problema."""
    try:
        g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
        todo = ' '.join(str(b.get('texto') or '') for b in g.get('bloques', []))
    except (OSError, ValueError):
        todo = ''
    try:
        todo = open(os.path.join(d, 'idea.txt'), encoding='utf-8').read() + ' ' + todo
    except OSError:
        pass
    marca = next((m for m, rx in MARCAS.items() if re.search(rx, todo, re.I)), 'TU CELULAR')
    problema = next((t for rx, t in PROBLEMAS if re.search(rx, todo, re.I)), 'PASO A PASO')
    anio = re.search(r'\b20(2\d)\b', todo)
    return [(marca, problema), (problema.split()[0] + ' ' + (problema.split()[1] if len(problema.split()) > 1 else ''), 'EN 1 CLIC'),
            (marca + (f' 20{anio.group(1)}' if anio else ''), '¡FUNCIONA!')]


def candidatos(d, orig):
    """[(etiqueta, segundo)]: el problema (primer tercio), el resultado (último tercio) y tú con el teléfono."""
    t, n, m = analizar(orig, os.path.splitext(orig)[0] + '.nitidez.npz')
    dur = float(t[-1]) if len(t) else 0
    puntaje = (n / (np.median(n) + 1e-6)) / (1 + m / (np.median(m) + 1e-6))
    cap = cv2.VideoCapture(orig)
    vistos, orden = [], []
    for k in range(3):  # los más nítidos de cada tercio del video: se mira dónde se ve el teléfono grande
        sel = np.where((t >= dur * k / 3) & (t < dur * (k + 1) / 3 + 0.01))[0]
        orden += list(sel[np.argsort(-puntaje[sel])][:60])
    por_tercio = {}
    for i in orden:
        s = float(t[i])
        tercio = min(2, int(s / max(dur, 1e-6) * 3))
        if por_tercio.get(tercio, 0) >= 14 or any(abs(s - v[0]) < 4 for v in vistos):
            continue
        por_tercio[tercio] = por_tercio.get(tercio, 0) + 1
        cap.set(cv2.CAP_PROP_POS_MSEC, s * 1000)
        ok, c = cap.read()
        if not ok:
            continue
        c = cv2.resize(c, (1920, 1080)) if c.shape[1] != 1920 else c
        objs = deteccion.objetos(c)
        tel = deteccion.telefono(objs)
        cara = deteccion.caras(c)
        alto = tel[3] / c.shape[0] if tel else 0
        q = enderezar.pantalla(c, tel) if tel else None
        prendida = q is not None and cv2.mean(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), mascara_poligono(c, q))[0] > 90
        # mejor con la pantalla encendida y entera a la vista: se entiende qué se muestra
        vistos.append((s, float(puntaje[i]) * (0.3 + alto) * (2.5 if prendida else 1), (tel, q if prendida else None), bool(cara)))
    cap.release()
    elegir = lambda f: max((v for v in vistos if f(v)), key=lambda v: v[1], default=None)
    out = []
    for nombre, f in (('problema', lambda v: v[0] < dur * 0.4 and v[2][0]), ('resultado', lambda v: v[0] > dur * 0.6 and v[2][0]),
                      ('contigo', lambda v: v[3] and v[2][0]), ('con el teléfono', lambda v: v[2][0]), ('nítido', lambda v: True)):
        libre = lambda v: all(abs(v[0] - o[1]) > 8 for o in out)
        # primero con la pantalla encendida (se entiende qué muestra); si no hay, la mejor que haya
        v = elegir(lambda v, f=f: f(v) and libre(v) and v[2][1] is not None) or elegir(lambda v, f=f: f(v) and libre(v))
        if v and len(out) < 3:
            out.append((nombre, v[0], v[2]))
    return out


def mascara_poligono(c, q, crecer=1.0):
    m = np.zeros(c.shape[:2], np.uint8)
    centro = q.mean(0)
    cv2.fillPoly(m, [((q - centro) * crecer + centro).astype(np.int32)], 255)
    return m


def recortar_telefono(c, caja, q=None):
    """(imagen BGRA del teléfono recortado, caja): con la pantalla encontrada, su rectángulo con el marco del teléfono;
    si no, GrabCut dentro de la caja del detector."""
    if q is not None:
        m = cv2.GaussianBlur(mascara_poligono(c, q, 1.07), (5, 5), 0)
        x, y, w, h = cv2.boundingRect(np.where(m > 0, 255, 0).astype(np.uint8))
        bgra = cv2.cvtColor(c, cv2.COLOR_BGR2BGRA)
        bgra[:, :, 3] = m
        return bgra[y:y + h, x:x + w], (x, y, w, h)
    x, y, w, h = [int(v) for v in caja]
    mx, my = int(w * 0.06), int(h * 0.04)
    x0, y0 = max(0, x - mx), max(0, y - my)
    x1, y1 = min(c.shape[1], x + w + mx), min(c.shape[0], y + h + my)
    mascara = np.zeros(c.shape[:2], np.uint8)
    try:
        cv2.grabCut(c, mascara, (x0, y0, x1 - x0, y1 - y0), np.zeros((1, 65)), np.zeros((1, 65)), 4, cv2.GC_INIT_WITH_RECT)
        m = np.where((mascara == cv2.GC_FGD) | (mascara == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    except cv2.error:
        m = np.zeros(c.shape[:2], np.uint8)
        m[y0:y1, x0:x1] = 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:  # la pieza más grande (el teléfono con la mano), sin manchas sueltas
        m = np.where(lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA])), 255, 0).astype(np.uint8)
    m = cv2.GaussianBlur(m, (5, 5), 0)
    bgra = cv2.cvtColor(c, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = m
    return bgra[y0:y1, x0:x1], (x0, y0, x1 - x0, y1 - y0)


def componer(c, tel, lineas, col, salida):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    fondo = cv2.resize(c, (W, H))
    fondo = cv2.GaussianBlur(fondo, (0, 0), 3)
    fondo = cv2.convertScaleAbs(fondo, alpha=0.55, beta=0)
    lienzo = Image.fromarray(cv2.cvtColor(fondo, cv2.COLOR_BGR2RGB)).convert('RGBA')
    tel, q = tel if isinstance(tel, tuple) else (tel, None)
    if tel:
        recorte, _ = recortar_telefono(c, tel, q)
        pieza = Image.fromarray(cv2.cvtColor(recorte, cv2.COLOR_BGRA2RGBA))
        k = (H * 0.92) / pieza.height
        pieza = pieza.resize((max(1, int(pieza.width * k)), int(pieza.height * k)), Image.LANCZOS)
        borde = pieza.split()[3].filter(ImageFilter.MaxFilter(15))  # contorno blanco tipo sticker
        px, py = W - pieza.width - 40, (H - pieza.height) // 2
        sombra = Image.new('RGBA', lienzo.size, (0, 0, 0, 0))
        sombra.paste(Image.new('RGBA', pieza.size, (0, 0, 0, 160)), (px + 14, py + 18), borde)
        lienzo = Image.alpha_composite(lienzo, sombra.filter(ImageFilter.GaussianBlur(14)))
        lienzo.paste(Image.new('RGBA', pieza.size, (255, 255, 255, 255)), (px, py), borde)
        lienzo.paste(pieza, (px, py), pieza)
        zona_texto = px - 30
    else:
        zona_texto = W - 60
    dib = ImageDraw.Draw(lienzo)
    fuente = next((f for f in FUENTES if os.path.exists(f)), None)
    y = 70
    for k, linea in enumerate([l for l in lineas if l]):
        tam = 150
        while tam > 40:
            fnt = ImageFont.truetype(fuente, tam) if fuente else ImageFont.load_default()
            if dib.textlength(linea, font=fnt) <= zona_texto - 50:
                break
            tam -= 6
        color = col['amarillo'] if k == 0 else (255, 255, 255)
        if k == 1:  # la segunda línea sobre una franja de color, como un sello
            ancho = dib.textlength(linea, font=fnt)
            dib.rounded_rectangle((40, y - 6, 40 + ancho + 40, y + tam + 18), 18, fill=col['rosa'] + (255,))
            dib.text((60, y), linea, font=fnt, fill=color)
        else:
            dib.text((50, y), linea, font=fnt, fill=color, stroke_width=max(4, tam // 14), stroke_fill=(0, 0, 0))
        y += tam + 40
    if tel:  # flecha hacia el teléfono
        x0, y0 = 70, min(H - 90, y + 10)
        x1, y1 = zona_texto - 10, H // 2 + 40
        if x1 - x0 > 120:
            dib.line((x0, y0, x1, y1), fill=col['rojo'] + (255,), width=18)
            ang = np.arctan2(y1 - y0, x1 - x0)
            p = [(x1 + 20 * np.cos(ang), y1 + 20 * np.sin(ang)),
                 (x1 - 50 * np.cos(ang - 0.5), y1 - 50 * np.sin(ang - 0.5)), (x1 - 50 * np.cos(ang + 0.5), y1 - 50 * np.sin(ang + 0.5))]
            dib.polygon(p, fill=col['rojo'] + (255,))
    lienzo.convert('RGB').save(salida, quality=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--texto', help='las dos líneas separadas por |, para las 3 opciones')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    orig = os.path.join(d, 'original.mp4')
    if not os.path.exists(orig):
        raise SystemExit('ERROR: falta tu grabación (original.mp4).')
    col = colores()
    lineas = [tuple(a.texto.split('|')[:2]) + ('',)] * 3 if a.texto else textos(d)
    print('Busco los mejores cuadros para la miniatura…', flush=True)
    cands = candidatos(d, orig)
    if not cands:
        raise SystemExit('ERROR: no encontré cuadros nítidos para la miniatura.')
    hechas = []
    cap = cv2.VideoCapture(orig)
    for k, (nombre, s, tel) in enumerate(cands, 1):
        cap.set(cv2.CAP_PROP_POS_MSEC, s * 1000)
        ok, c = cap.read()
        if not ok:
            continue
        escala = 1920 / c.shape[1]
        c = cv2.resize(c, (1920, 1080)) if c.shape[1] != 1920 else c
        if mejorar.quieres(d):
            f = os.path.join(d, f'.miniatura_{k}.png')
            cv2.imwrite(f, c)
            if mejorar.imagen(f):
                c = cv2.imread(f)
            os.remove(f)
        salida = os.path.join(d, f'miniatura_{k}.jpg')
        l = lineas[(k - 1) % len(lineas)]
        componer(c, tel, [x for x in l if x], col, salida)
        hechas.append({'archivo': os.path.basename(salida), 'de': nombre, 'segundo': round(s, 1), 'texto': [x for x in l if x],
                       'telefono': bool(tel[0]), 'escala': escala})
        print(f"· miniatura_{k}.jpg: {nombre}, cuadro de {int(s // 60)}:{int(s % 60):02d}, «{' / '.join(x for x in l if x)}»", flush=True)
    cap.release()
    json.dump({'miniaturas': hechas}, open(os.path.join(d, 'miniatura.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Listo: {len(hechas)} miniaturas para probar en YouTube (prueba A/B).', flush=True)


if __name__ == '__main__':
    main()
