"""«🖼 Miniatura automática»: 3 opciones de miniatura de YouTube (1280×720) sacadas de tu video, para probarlas con la
prueba A/B de miniaturas de YouTube.

Gratis, en tu PC:
  1. Elige los cuadros más nítidos y quietos (nitidez/) donde el detector ve el teléfono grande: uno del PROBLEMA (la
     pantalla bloqueada, al comienzo), uno del RESULTADO (al final) y uno contigo con el teléfono si sales en cámara.
  2. Recorta el teléfono del fondo (GrabCut de OpenCV dentro de la caja del detector) y lo pone grande con un borde
     blanco tipo sticker; si en «🎛 Audio e imagen» activaste «✨ Mejorar imagen», el cuadro pasa antes por Real-ESRGAN.
  3. Pone el texto grande con tus colores (remotion/src/estilo.ts) y una flecha hacia el teléfono.
Deja miniatura_1.jpg, miniatura_2.jpg, miniatura_3.jpg y miniatura.json (de dónde sale cada una).

Con --gpt (gasta: 3 imágenes de gpt-image-2.5-flare, en calidad baja de borrador si no pides --calidad media o alta), además,
la miniatura hecha por la IA de imágenes con tus cuadros de referencia (el problema y el resultado), en español, inglés y
portugués: miniatura_gpt_es/en/pt.jpg. GPT escribe todo con la fórmula de tu canal y copia el estilo de tus miniaturas
recientes (canal_referencia.py, fabian 03/11/2026).

Uso: python miniatura.py --proyecto . [--texto "MOTOROLA|SIN CUENTA"] [--gpt] (la | parte en dos líneas; sin texto, lo arma solo)
"""
import argparse, hashlib, json, os, re, sys
import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('nitidez', 'deteccion', 'mejorar', 'pantalla'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
import deteccion  # noqa: E402
import mejorar  # noqa: E402
import enderezar  # noqa: E402  el rectángulo de la pantalla: el recorte más limpio del teléfono
from nitidez import analizar, mejor  # noqa: E402
sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))


def guardar_img(f, img, params=()):
    """Como cv2.imwrite, pero sirve en Windows con tildes o ñ en la ruta (cv2.imwrite fallaba callado y la miniatura ya
    pagada no quedaba). Si no se puede guardar, avisa en vez de seguir como si nada."""
    ok, buf = cv2.imencode(os.path.splitext(f)[1] or '.png', img, list(params))
    if not ok:
        raise SystemExit(f'ERROR: no pude guardar la imagen {f}')
    buf.tofile(f)
    return f


def leer_img(f, modo=cv2.IMREAD_COLOR):
    """Como cv2.imread (None si no se puede), pero sirve en Windows con tildes o ñ en la ruta."""
    try:
        return cv2.imdecode(np.fromfile(f, np.uint8), modo)
    except (OSError, ValueError, cv2.error):
        return None


W, H = 1280, 720
FUENTES = ['C:/Windows/Fonts/impact.ttf', 'C:/Windows/Fonts/ariblk.ttf', 'C:/Windows/Fonts/arialbd.ttf',
           '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf', '/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf',
           '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
MARCAS = {'MOTOROLA': r'\bmoto(rola)?\b', 'IPHONE': r'iphone|icloud|\bios\b', 'SAMSUNG': r'samsung|galaxy', 'XIAOMI': r'\bxiaomi\b(?!\s*unlock)|redmi|\bpoco\b',
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
    try:  # la marca del proyecto (su nombre o idea.txt) manda sobre lo que se nombra en el guion
        import conocimiento
        marca = (conocimiento.marca_de_proyecto(d) or '').upper()
    except Exception:
        marca = ''
    if marca not in MARCAS:
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


# las frases de la miniatura en inglés y portugués (pedido de fabian, 30/10/2026: todo texto en 3 idiomas)
TRADUCE = {'SIN CUENTA GOOGLE': ('NO GOOGLE ACCOUNT', 'SEM CONTA GOOGLE'), 'SIN ICLOUD': ('NO ICLOUD', 'SEM ICLOUD'),
           'ADIÓS MDM': ('BYE BYE MDM', 'ADEUS MDM'), 'BYPASS FÁCIL': ('EASY BYPASS', 'BYPASS FÁCIL'),
           'PASO A PASO': ('STEP BY STEP', 'PASSO A PASSO'), 'EN 1 CLIC': ('IN 1 CLICK', 'EM 1 CLIQUE'),
           '¡FUNCIONA!': ('IT WORKS!', 'FUNCIONA!'), 'TU CELULAR': ('YOUR PHONE', 'SEU CELULAR')}


def traducir(linea, idioma):
    """La línea en inglés o portugués si es una de las frases conocidas; si no, la IA de imágenes la traduce."""
    if idioma == 'es':
        return linea, False
    for es, (en, pt) in TRADUCE.items():
        if linea.strip().upper() == es:
            return (en if idioma == 'en' else pt), False
    return linea, True


ANTES_DESPUES = {'es': ('ANTES', 'DESPUÉS'), 'en': ('BEFORE', 'AFTER'), 'pt': ('ANTES', 'DEPOIS')}
def necesita_pc(marca):
    """True salvo que fabian haya marcado que esa marca no necesita PC (mis_conocimientos/procesos_pc.json)."""
    try:
        datos = json.load(open(os.path.join(RAIZ, 'mis_conocimientos', 'procesos_pc.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return True
    return datos.get(marca.lower(), True) is not False


PILDORAS_PC = {'es': '«TODOS LOS MODELOS» (ícono de teléfono) y «EN MINUTOS» (ícono de reloj)',
               'en': '«ALL MODELS» (ícono de teléfono) y «IN MINUTES» (ícono de reloj)',
               'pt': '«TODOS OS MODELOS» (ícono de teléfono) y «EM MINUTOS» (ícono de reloj)'}
PILDORAS = {'es': '«SIN PC» (ícono de computadora tachada) y «TODOS LOS MODELOS» (ícono de teléfono)',
            'en': '«NO PC» (ícono de computadora tachada) y «ALL MODELS» (ícono de teléfono)',
            'pt': '«SEM PC» (ícono de computadora tachada) y «TODOS OS MODELOS» (ícono de teléfono)'}
MASCOTA = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'mascota_xiaomiunlock.png')
ESTILO = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'referencias')  # miniaturas de fabian (ESTILO_MINIATURAS.md)


def referencias_estilo(marca, n=2):
    """Las miniaturas de fabian que muestran su estilo: las de la misma marca primero."""
    try:
        todas = sorted(f for f in os.listdir(ESTILO) if f.lower().endswith(('.jpg', '.png')))
    except OSError:
        return []
    suyas = [f for f in todas if f.lower().startswith(marca.lower()[:4])] + [f for f in todas if not f.lower().startswith(marca.lower()[:4])]
    return [os.path.join(ESTILO, f) for f in suyas[:n]]


# los momentos de tu video que sirven para la miniatura (pedido de fabian, 30/10/2026): varias opciones de ANTES y el
# DESPUÉS en la pantalla de inicio. Primero lo que se lee en la pantalla (mapa_video.json), si no, lo que dice el guion
CLAVES = {
    'verifica': (r'verifica tu cuenta|this device is locked|dispositivo est[aá] bloqueado|iphone no disponible|bloqueo de activaci',
                 r'verifica|bloquead|locked|no disponible|cuenta de google'),
    'fastboot': (r'fastboot ?& ?rescue|fastboot mode|recovery mode|modo download|\bdfu\b', r'fastboot|recovery|\bdfu\b|download'),
    'bienvenido': (r'\bbienvenido\b', r'bienvenid|welcome|idioma'),  # «Welcome» sale en la web: solo el del teléfono
    'inicio': (r'agregar ciudad|my ?honor|play ?store|tienda de apps', r'pantalla (principal|de inicio)|ya funcionando|home'),
}
NOMBRE_ANTES = {'verifica': 'la pantalla bloqueada («Verifica tu cuenta»)', 'fastboot': 'el teléfono en modo FASTBOOT',
                'bienvenido': 'el teléfono recién formateado en «Bienvenido»'}


def cuadros_clave(d, nt):
    """{'verifica': s, 'fastboot': s, 'bienvenido': s, 'inicio': s} con los que encuentre (el segundo más nítido cerca)."""
    try:
        mapa = json.load(open(os.path.join(d, 'mapa_video.json'), encoding='utf-8')).get('cuadros', [])
    except (OSError, ValueError):
        mapa = []
    try:
        bloques = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8')).get('bloques', [])
    except (OSError, ValueError):
        bloques = []
    total = float(nt[0][-1]) if len(nt[0]) else 60.0
    out = {}
    for clave, (rx_pantalla, rx_guion) in CLAVES.items():
        # en el mapa: el texto de la pantalla del teléfono (sin el programa de la PC, que también dice «fastboot»)
        vistos = [x['t'] for x in mapa if re.search(rx_pantalla, str(x.get('texto', '')), re.I)
                  and not re.search(r'easy-?unlocker|read ?fastboot|xiaomiunlock\.com|place ?a ?new|all models|sign in|order',
                                    str(x.get('texto', '')), re.I)]
        if clave == 'inicio':
            vistos = [s for s in vistos if s > total * 0.6]
        s = (vistos[-1] if clave == 'inicio' else vistos[0]) if vistos else None
        if s is None:  # si no, el bloque del guion que lo nombra
            for b in (reversed(bloques) if clave == 'inicio' else bloques):
                txt = ' '.join(str(b.get(k) or '') for k in ('ancla', 've_inicio', 've_fin'))
                mo = b.get('montaje') or {}
                if re.search(rx_guion, txt, re.I) and mo.get('src_inicio') is not None:
                    fin = mo.get('src_fin') or mo['src_inicio'] + 3
                    s = mo['src_inicio'] + 0.4 * (fin - mo['src_inicio'])
                    break
        if s is not None:
            out[clave] = mejor(*nt, max(0, s - 1.5), min(total, s + 1.5))
    return out


def pedir_imagen(req, intentos=4):
    """El pedido a la IA de imágenes; si OpenAI dice «demasiados pedidos» (429) o falla un momento, espera y reintenta."""
    import time, urllib.error, urllib.request
    for k in range(intentos):
        try:
            return json.load(urllib.request.urlopen(req, timeout=400))
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode(errors='replace')
            if 'insufficient_quota' in cuerpo or 'credit_balance' in cuerpo:  # sin saldo: reintentar no sirve
                raise SystemExit('ERROR: tu cuenta de OpenAI se quedó sin saldo para imágenes. Cárgalo en '
                                 'https://platform.openai.com/settings/organization/billing/ y vuelve a tocar el botón.')
            if e.code not in (429, 500, 502, 503) or k == intentos - 1:
                raise SystemExit(f'ERROR: la IA de imágenes respondió {e.code}: {cuerpo[:200]}')
            espera = 20 * (k + 1)
            print(f'· OpenAI pide esperar (error {e.code}); reintento en {espera} s…', flush=True)
            time.sleep(espera)


# el modelo y la calidad de las miniaturas (fabian, 03/11/2026): los borradores en BAJA (~0,02 USD), la final aprobada en
# MEDIA (~0,07 USD) y alta solo si la pide. El modelo: gpt-image-2.5-flare, o uno más nuevo de la familia 2.5 que pongas en
# app/ajustes.json como "modelo_imagen" (otro que no sea de esa familia no se usa)
MODELO_IMAGEN = 'gpt-image-2.5-flare'
CALIDADES = {'baja': 'low', 'media': 'medium', 'alta': 'high'}
COSTO_CALIDAD = {'baja': 0.02, 'media': 0.07, 'alta': 0.28}  # USD por imagen 16:9


def ajustes():
    try:
        return json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def modelo_imagen(aj=None):
    m = str((aj if aj is not None else ajustes()).get('modelo_imagen') or '').strip()
    return m if re.fullmatch(r'gpt-image-(2\.[5-9]|[3-9])([.\-][\w.\-]*)?', m) else MODELO_IMAGEN


def clave_openai():
    """La clave de OpenAI: la de GPT en «🤖 Ajustes IA»."""
    return str(((ajustes().get('ias_guion') or {}).get('gpt') or {}).get('clave') or '')


FONDOS_MINI = {  # pedido de fabian (30/10/2026): probar los dos y quedarse con el que más le guste
    'escritorio': '(1) fondo = SU escritorio real, el que se ve alrededor del teléfono en las fotos de su video, tal cual, claro y apenas desenfocado: la laptop, el cartel '
                  'negro «Frp» y la G de Google grande de 4 colores (no inventes otro fondo); ',
    'foto': '(1) fondo = el fondo REAL de sus fotos HD, tal cual, claro y apenas desenfocado (no inventes otro fondo); ',
    'gpt': '(1) fondo generado por ti, como sus miniaturas de iPhone: oscuro azul profundo con estelas de luz de neón celeste y '
           'violeta, rayos de luz y un piso que refleja; ',
}


# la fórmula de las miniaturas de fabian (analizada el 02/11/2026 en las de su canal que más rinden; pedido del 03/11/2026:
# «las que estás haciendo no se parecen nada a las mías»). TODO lo escribe GPT: la app no dibuja nada encima
FONDOS_CANAL = {
    'gpt': 'azul marino oscuro con neón azul y cian, rayos de luz y destellos, como en sus miniaturas',
    'foto': 'el fondo REAL de sus fotos (su estudio), oscurecido y con contraste, con un toque de neón azul y cian',
    'escritorio': 'SU escritorio real, el que se ve alrededor del teléfono en sus fotos, oscurecido y con contraste, con un toque '
                  'de neón azul y cian',
}
WEB = re.compile(r'\.(com|co|net|org|io)\b|gsmprime|xiaomiunlock|www\.', re.I)  # «XIAOMIUNLOCK» solo también es su página


def revisar_textos(textos, marca):
    """Antes de gastar: nada de páginas web (fabian, 02/11/2026) ni «SIN PC» en las marcas que usan PC (Honor)."""
    for t in textos:
        if WEB.search(t):
            raise SystemExit(f'ERROR: «{t}» lleva una página web y las miniaturas van sin webs (fabian, 02/11/2026). Quítala. '
                             'No se gastó nada.')
        if re.search(r'\b(SIN|NO|SEM) PC\b', t, re.I) and necesita_pc(marca):
            raise SystemExit(f'ERROR: «{t}»: este proceso usa PC, nunca «SIN PC» («PC BÁSICA ✓» sí). No se gastó nada.')


def logos_miniatura(marca, texto, n=2):
    """[(nombre, archivo)]: logos oficiales de tu biblioteca (mis_conocimientos/logos) para la miniatura. Primero el que va
    ENTRE las palabras del título (Google en FRP, iOS en iPhone, o el que nombre el título) y después el de la marca. Nunca
    tarjetas ni webs."""
    import unicodedata
    norma = lambda t: ''.join(c for c in unicodedata.normalize('NFKD', str(t or '').lower()) if not unicodedata.combining(c))
    simple = lambda t: re.sub(r'[^a-z0-9]+', ' ', norma(t)).strip()
    try:
        lib = json.load(open(os.path.join(LOGOS_DIR, 'logos.json'), encoding='utf-8')).get('logos') or []
    except (OSError, ValueError, AttributeError):
        lib = []
    cands = [(str(l.get('nombre') or os.path.splitext(l['archivo'])[0]), os.path.join(LOGOS_DIR, l['archivo'])) for l in lib
             if isinstance(l, dict) and l.get('archivo') and not l.get('tarjeta') and not l.get('solo_short')]
    try:
        cands += [(os.path.splitext(f)[0].replace('_', ' '), os.path.join(LOGOS_DIR, f)) for f in sorted(os.listdir(LOGOS_DIR))
                  if f.lower().endswith('.png')]
    except OSError:
        pass
    cands = [(nm, f) for nm, f in cands if os.path.isfile(f) and not re.search(
        r'whats|wasap|soporte|tarjeta|contacto|play|web|gsmprime|xiaomiunlock|\.com|\.co\b', norma(nm + ' ' + os.path.basename(f)))]
    t = f' {simple(texto)} '
    out = []

    def poner(cumple):
        for nm, f in cands:
            if len(out) < n and f not in [x[1] for x in out] and cumple(simple(nm)):
                out.append((nm, f))
                return
    if re.search(r' (frp|google) ', t):
        poner(lambda nm: re.search(r'\bgoogle\b', nm))
    elif re.search(r' (iphone|icloud|ios) ', t):
        poner(lambda nm: re.search(r'\bios\b', nm))
    poner(lambda nm: len(nm) > 2 and f' {nm} ' in t and nm != simple(marca))  # el que nombra el título («iOS 27», «Android 15»)
    if marca and marca != 'TU CELULAR':
        poner(lambda nm: nm == simple(marca))
    return out


def prompt_canal(lineas, idioma, n_fotos=2, n_extras=0, logos=(), n_estilo=0, fondo='gpt', antes_desc=None,
                 esquinas=('PASO A PASO', ''), cara=False, marca='TU CELULAR'):
    """El pedido a GPT para que la miniatura salga como las del canal de fabian: su fórmula, con el texto en el idioma pedido."""
    nombre = {'es': 'español', 'en': 'inglés', 'pt': 'portugués'}[idioma]
    textos = [traducir(x.strip(), idioma) for x in lineas if x and x.strip()] or [('PASO A PASO', False)]
    izq, der = [traducir(x.strip(), idioma) if x and x.strip() else ('', False) for x in (list(esquinas) + ['', ''])[:2]]
    traduce = any(t for _, t in textos + [izq, der])
    lin = lambda x: ' / '.join(p.strip() for p in x.split('|') if p.strip())  # «NUEVA UPDATE|EXPLICADO PASO A PASO»: 2 líneas
    i = n_fotos + n_extras
    p = ['Miniatura de YouTube 16:9 para el canal Xiaomiunlock de fabian (técnico que desbloquea celulares), hecha IGUAL que las '
         'miniaturas recientes de SU canal: la misma fórmula, las mismas letras, los mismos efectos y el mismo tipo de fondo.',
         f'Imagen 1: SU foto real del teléfono de este video ANTES ({antes_desc or "bloqueado"}).'
         + (' Imagen 2: el mismo teléfono ya libre, en su pantalla de inicio (DESPUÉS).' if n_fotos > 1 else '')
         + (f' Imágenes {n_fotos + 1} a {i}: más fotos reales del mismo teléfono.' if n_extras > 1 else
            f' Imagen {i}: otra foto real del mismo teléfono.' if n_extras else '')
         + ' Parte SIEMPRE de SUS fotos: el teléfono, su pantalla y lo que se lee en ella salen de ahí, tal cual (no inventes otro '
           'modelo, otra cámara ni otra pantalla).']
    for k, (nm, _) in enumerate(logos):
        p.append(f'Imagen {i + k + 1}: el logo oficial de {nm}: cópialo exacto, sin redibujarlo ni cambiarle los colores.')
    i += len(logos)
    if n_estilo:
        p.append(f'Imágenes {i + 1} a {i + n_estilo}: miniaturas de SU canal, SOLO como referencia de ESTILO (reparto, tipo de '
                 'letra, borde, sombra, degradados, neón, brillo y fondo): NO copies sus textos, ni sus teléfonos, ni sus '
                 'pantallas, ni sus logos, ni la duración de YouTube.')
    # (revisión, 03/11/2026) entre las palabras va el logo del SERVICIO (la G en FRP, iOS en iPhone), como en «ELIM. CUENTA [G]
    # HONOR»; si ese logo no está guardado, GPT lo dibuja (antes iba el de la marca, que ya está escrita en la frase)
    unido = ' '.join(lineas)
    servicio = 'Google' if re.search(r'frp|google', unido, re.I) else 'iOS' if re.search(r'iphone|icloud|\bios\b', unido, re.I) else ''
    suyo = next((nm for nm, _ in logos if servicio and re.search(rf'\b{servicio}\b', nm, re.I)), '')
    entre = (f'de {suyo}' if suyo else f'de {servicio}' if servicio else f'de {logos[0][0]}' if logos else
             f'de {marca.title()}' if marca != 'TU CELULAR' else 'de la marca')
    if len(textos) > 1:
        frase = (f'«{textos[0][0]}» en blanco, el logo {entre} y «{" ".join(x for x, _ in textos[1:])}» en amarillo-naranja con '
                 'degradado')
    else:
        frase = f'«{textos[0][0]}»: las primeras palabras en blanco, el logo {entre} y la última en amarillo-naranja con degradado'
    p.append('FÓRMULA OBLIGATORIA, todo junto:')
    p.append(f'(1) ABAJO, la frase principal en UNA sola línea a todo el ancho, en {nombre}: {frase}. El logo va ENTRE las '
             'palabras (como «ELIM. CUENTA [G] HONOR» o «BYPASS iOS [27] SIN ERRORES»). Letra muy gruesa, condensada y en '
             'cursiva, con borde negro grueso y sombra; si hace falta contraste, sobre una placa negra con borde de neón celeste. '
             'La frase termina ANTES de la esquina de abajo a la derecha: deja libre ese rincón (ahí YouTube pone la duración).')
    p.append('(2) ARRIBA, en las dos esquinas, etiquetas inclinadas unos 5° (una hacia cada lado), de 1 o 2 líneas: '
             + (f'arriba a la izquierda «{lin(izq[0])}» GRANDE en amarillo con degradado (o en una cinta); ' if izq[0] else
                'arriba a la izquierda nada de texto; ')
             + (f'arriba a la derecha «{lin(der[0])}» en 2 o 3 líneas blancas dentro de un recuadro redondeado negro con borde de '
                'neón azul.' if der[0] else 'arriba a la derecha un recuadro redondeado negro con borde de neón azul, solo con el '
                'logo de la marca (sin texto).'))
    p.append('(3) AL CENTRO el teléfono real GRANDE, con la pantalla legible, con un filo de luz blanco-celeste en el contorno y '
             'resplandor cian; sostenido con guante negro o azul. Si sirve, los 2 teléfonos: ANTES y DESPUÉS. Máximo 2 manos en '
             'toda la imagen. '
             + ('A un costado, un hombre latino ficticio (no es nadie real, siempre el mismo), de expresión natural (ni exagerada, '
                'ni seria, ni pícara), con buzo blanco liso sin logos.' if cara else 'Sin personas: solo las manos con guante.'))
    p.append(f'(4) FONDO: {FONDOS_CANAL.get(fondo, FONDOS_CANAL["gpt"])}. NUNCA un fondo claro ni blanco.')
    p.append('(5) TODO el texto lo escribes tú, perfectamente escrito, con tildes, en MAYÚSCULAS y grande: que se lea en el '
             'celular a 320×180. Un solo título del modelo. Ningún otro texto: nada de páginas web ni direcciones (.com, .co, '
             'gsmprime, xiaomiunlock), nada de marcas de agua. Nada de letras 3D doradas o metálicas ni sellos dorados.'
             + (' Este proceso usa PC: nunca escribas «SIN PC» (si hace falta, «PC BÁSICA ✓»).' if necesita_pc(marca) else ''))
    if traduce:
        p.append(f'Los textos entre « » van en {nombre}: tradúcelos cortos y naturales (marcas, modelos y versiones quedan igual).')
    p.append('Todo el diseño completo dentro de la imagen 16:9, sin cortar nada en los bordes.')
    return ' '.join(p)


def miniaturas_gpt(d, refs, lineas, salida_base, marca='TU CELULAR', idiomas=('es', 'en', 'pt'), antes_desc=None, fondo='gpt',
                   extras=(), calidad='baja', esquinas=('PASO A PASO', ''), cara=False, refs_canal=None, info=None):
    """La miniatura hecha TODA por GPT (textos incluidos) con la fórmula del canal de fabian, una por idioma: tus fotos, los
    logos oficiales de tu biblioteca y 2-3 miniaturas de tu canal como referencia de ESTILO (canal_referencia.py; sin ellas,
    las de mis_conocimientos/miniaturas/referencias). Borrador en baja; la final, en media. Devuelve los archivos.
    refs_canal: los ids de las miniaturas del canal de un borrador, para que su final salga con el mismo estilo."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import canal_referencia
    lineas = [x.strip() for x in lineas if x and x.strip()]
    revisar_textos(lineas + [x for x in esquinas if x], marca)
    texto = ' '.join(lineas)
    logos = logos_miniatura(marca, texto)
    # las del borrador; si ya no están, se eligen otra vez con la misma cuenta que «🖼 Miniatura» (las marcadas con ✓): antes
    # la marca salía de otro lado (el guion) y a GPT podían ir otras (revisión, 03/11/2026)
    canal = ((canal_referencia.por_ids(refs_canal) if refs_canal else []) or
             canal_referencia.elegir(*canal_referencia.contexto(d, texto)))
    estilo = [v['ruta'] for v in canal] or referencias_estilo(marca, 3)
    fotos = list(refs)
    imagenes = fotos + list(extras) + [f for _, f in logos] + estilo
    if canal:
        print('· estilo de tu canal: ' + ' | '.join(str(v.get('titulo') or v['id'])[:45] for v in canal), flush=True)
    if info is not None:
        info.update(modelo=modelo_imagen(), calidad=calidad, refs_canal=[v['id'] for v in canal], logos=[nm for nm, _ in logos],
                    costo_usd=COSTO_CALIDAD.get(calidad, COSTO_CALIDAD['alta']))
    hechas = []
    for idioma, nombre in [x for x in (('es', 'español'), ('en', 'inglés'), ('pt', 'portugués')) if x[0] in idiomas]:
        prompt = prompt_canal(lineas, idioma, n_fotos=len(fotos), n_extras=len(extras), logos=logos, n_estilo=len(estilo),
                              fondo=fondo, antes_desc=antes_desc, esquinas=esquinas, cara=cara, marca=marca)
        print(f'· la IA de imágenes hace la miniatura en {nombre} (calidad {calidad})…', flush=True)
        img = imagen_gpt(prompt, imagenes, size='1536x864', calidad=calidad)
        h, w = img.shape[:2]
        alto = min(h, int(w * 9 / 16))  # ya viene en 16:9 (1536x864): no se corta nada
        img = cv2.resize(img[(h - alto) // 2:(h - alto) // 2 + alto], (W, H), interpolation=cv2.INTER_AREA)
        f = f'{salida_base}_{idioma}.jpg'
        guardar_img(f, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        hechas.append(os.path.basename(f))
        print(f'· {os.path.basename(f)} lista', flush=True)
    return hechas


# MIXTA (idea aceptada por fabian, 30/10/2026): GPT pinta solo la escena (fondo, manos, teléfonos, flecha, candado,
# mascota) SIN NINGÚN texto, y la app pone encima los textos, el sello, las píldoras y el logo oficial guardado. Así no
# salen letras mal escritas ni logos inventados, y una sola escena sirve para los 3 idiomas (gasta 1 imagen, no 3)
SELLO = {'es': ('MÉTODO', 'GARANTIZADO', '2026'), 'en': ('GUARANTEED', 'METHOD', '2026'), 'pt': ('MÉTODO', 'GARANTIDO', '2026')}
PILDORAS_MIXTA = {True: {'es': (('TODOS LOS', 'MODELOS', 'tel'), ('EN', 'MINUTOS', 'reloj')),
                         'en': (('ALL', 'MODELS', 'tel'), ('IN', 'MINUTES', 'reloj')),
                         'pt': (('TODOS OS', 'MODELOS', 'tel'), ('EM', 'MINUTOS', 'reloj'))},
                  False: {'es': (('SIN', 'PC', 'pc'), ('TODOS LOS', 'MODELOS', 'tel')),
                          'en': (('NO', 'PC', 'pc'), ('ALL', 'MODELS', 'tel')),
                          'pt': (('SEM', 'PC', 'pc'), ('TODOS OS', 'MODELOS', 'tel'))}}
LOGOS_DIR = os.path.join(RAIZ, 'mis_conocimientos', 'logos')


def imagen_gpt(prompt, refs, size='1536x864', transparente=False, calidad='alta'):
    """Un pedido a gpt-image-2.5-flare (o el modelo 2.5 de ajustes.json, modelo_imagen()) con imágenes de referencia;
    devuelve la imagen (BGR, o BGRA si es transparente). calidad: baja (borrador), media (final) o alta."""
    import base64, urllib.request, uuid
    k = clave_openai()
    if not k:
        raise SystemExit('ERROR: falta la clave de OpenAI (la de GPT en «🤖 Ajustes IA») para la miniatura con GPT.')
    b = uuid.uuid4().hex
    cuerpo = b''
    campos = {'model': modelo_imagen(), 'prompt': prompt, 'size': size, 'quality': CALIDADES.get(calidad, 'high'), 'output_format': 'png'}
    if transparente:
        campos['background'] = 'transparent'
    for campo, v in campos.items():
        cuerpo += f'--{b}\r\nContent-Disposition: form-data; name="{campo}"\r\n\r\n{v}\r\n'.encode()
    for i, r in enumerate(refs):
        tipo = 'image/jpeg' if r.lower().endswith('.jpg') else 'image/png'
        cuerpo += (f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="ref{i}{os.path.splitext(r)[1]}"\r\n'
                   f'Content-Type: {tipo}\r\n\r\n').encode() + open(r, 'rb').read() + b'\r\n'
    cuerpo += f'--{b}--\r\n'.encode()
    req = urllib.request.Request('https://api.openai.com/v1/images/edits', data=cuerpo,
                                 headers={'Authorization': 'Bearer ' + k, 'Content-Type': f'multipart/form-data; boundary={b}'})
    r = pedir_imagen(req)
    return cv2.imdecode(np.frombuffer(base64.b64decode(r['data'][0]['b64_json']), np.uint8),
                        cv2.IMREAD_UNCHANGED if transparente else cv2.IMREAD_COLOR)


def fuente(tam, cual=0):
    from PIL import ImageFont
    f = next((x for x in FUENTES[cual:] if os.path.exists(x)), None)
    return ImageFont.truetype(f, tam) if f else ImageFont.load_default()


def texto_italico(linea, tam, relleno=(255, 255, 255), borde=8, ancho_max=None):
    """El texto grueso, blanco con borde negro, inclinado como itálica y con sombra (capa RGBA recortada)."""
    from PIL import Image, ImageDraw, ImageFilter
    while True:
        fnt = fuente(tam)
        caja = ImageDraw.Draw(Image.new('RGBA', (1, 1))).textbbox((0, 0), linea, font=fnt, stroke_width=borde)
        w, h = caja[2] - caja[0], caja[3] - caja[1]
        if not ancho_max or w + 0.22 * h <= ancho_max or tam < 30:
            break
        tam -= 4
    pad = 30
    capa = Image.new('RGBA', (int(w + 0.22 * h) + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    dib = ImageDraw.Draw(capa)
    dib.text((pad - caja[0] + 10, pad - caja[1] + 10), linea, font=fnt, fill=(0, 0, 0, 170), stroke_width=borde, stroke_fill=(0, 0, 0, 170))
    capa = capa.filter(ImageFilter.GaussianBlur(6))
    ImageDraw.Draw(capa).text((pad - caja[0], pad - caja[1]), linea, font=fnt, fill=relleno, stroke_width=borde, stroke_fill=(0, 0, 0))
    k = 0.22  # arriba se corre a la derecha: itálica
    return capa.transform(capa.size, Image.AFFINE, (1, k, -k * capa.height, 0, 1, 0), Image.BICUBIC)


def cinta(texto, color, tam=58, angulo=6):
    """Etiqueta de color inclinada con letra blanca gruesa (NEW 2026, ANTES, DESPUÉS)."""
    from PIL import Image, ImageDraw
    fnt = fuente(tam)
    caja = ImageDraw.Draw(Image.new('RGBA', (1, 1))).textbbox((0, 0), texto, font=fnt, stroke_width=3)
    w, h = caja[2] - caja[0] + 50, caja[3] - caja[1] + 26
    capa = Image.new('RGBA', (w + 12, h + 12), (0, 0, 0, 0))
    dib = ImageDraw.Draw(capa)
    dib.rounded_rectangle((8, 8, w + 8, h + 8), 10, fill=(0, 0, 0, 150))
    dib.rounded_rectangle((0, 0, w, h), 10, fill=color + (255,), outline=(255, 255, 255, 255), width=4)
    dib.text((25 - caja[0], 13 - caja[1]), texto, font=fnt, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
    return capa.rotate(angulo, expand=True, resample=Image.BICUBIC)


def sello(r, lineas):
    """El sello dorado redondo con estrellas (MÉTODO GARANTIZADO 2026)."""
    from PIL import Image, ImageDraw, ImageFilter
    S = 2 * r + 30
    c = S / 2
    capa = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    dib = ImageDraw.Draw(capa)
    dib.ellipse((c - r + 8, c - r + 12, c + r + 8, c + r + 12), fill=(0, 0, 0, 140))
    capa = capa.filter(ImageFilter.GaussianBlur(8))
    dib = ImageDraw.Draw(capa)
    pts = [(c + (r if i % 2 == 0 else r * 0.93) * np.cos(np.pi * i / 36), c + (r if i % 2 == 0 else r * 0.93) * np.sin(np.pi * i / 36)) for i in range(72)]
    dib.polygon(pts, fill=(176, 122, 18))
    for q, col in ((0.88, (250, 205, 80)), (0.80, (190, 135, 25)), (0.76, (18, 18, 18))):
        dib.ellipse((c - r * q, c - r * q, c + r * q, c + r * q), fill=col)
    dib.ellipse((c - r * 0.70, c - r * 0.70, c + r * 0.70, c + r * 0.70), outline=(235, 190, 70), width=3)
    def estrella(x, y, s):
        dib.polygon([(x + (s if i % 2 == 0 else s * 0.42) * np.cos(-np.pi / 2 + np.pi * i / 5),
                      y + (s if i % 2 == 0 else s * 0.42) * np.sin(-np.pi / 2 + np.pi * i / 5)) for i in range(10)], fill=(250, 210, 90))
    for dx in (-r * 0.22, 0, r * 0.22):
        estrella(c + dx, c - r * 0.55 + (0 if dx == 0 else r * 0.04), r * (0.09 if dx == 0 else 0.07))
        estrella(c + dx, c + r * 0.56 - (0 if dx == 0 else r * 0.04), r * (0.09 if dx == 0 else 0.07))
    tams = (int(r * 0.30), int(r * 0.30), int(r * 0.46))
    ys = (c - r * 0.36, c - r * 0.06, c + r * 0.22)
    for linea, tam, y in zip(lineas, tams, ys):
        while tam > 10 and dib.textlength(linea, font=fuente(tam)) > r * 1.3:
            tam -= 2
        fnt = fuente(tam)
        dib.text((c, y + tam / 2), linea, font=fnt, fill=(250, 210, 90), anchor='mm')
    return capa


def icono(tipo, d):
    """Ícono redondo de las píldoras: teléfono (azul), reloj (rojo) o PC tachada (rojo)."""
    from PIL import Image, ImageDraw
    capa = Image.new('RGBA', (d, d), (0, 0, 0, 0))
    dib = ImageDraw.Draw(capa)
    dib.ellipse((0, 0, d - 1, d - 1), fill=(24, 110, 235) if tipo == 'tel' else (225, 40, 40))
    blanco, g = (255, 255, 255), max(3, d // 14)
    if tipo == 'tel':
        dib.rounded_rectangle((d * 0.34, d * 0.2, d * 0.66, d * 0.8), d // 12, outline=blanco, width=g)
        dib.line((d * 0.45, d * 0.71, d * 0.55, d * 0.71), fill=blanco, width=g)
    elif tipo == 'reloj':
        dib.ellipse((d * 0.2, d * 0.2, d * 0.8, d * 0.8), outline=blanco, width=g)
        dib.line((d / 2, d / 2, d / 2, d * 0.31), fill=blanco, width=g)
        dib.line((d / 2, d / 2, d * 0.64, d * 0.56), fill=blanco, width=g)
    else:
        dib.rectangle((d * 0.24, d * 0.28, d * 0.76, d * 0.62), outline=blanco, width=g)
        dib.line((d * 0.4, d * 0.72, d * 0.6, d * 0.72), fill=blanco, width=g)
        dib.line((d * 0.2, d * 0.8, d * 0.8, d * 0.2), fill=blanco, width=g + 1)
    return capa


def pildora(arriba, abajo, tipo, alto=60):
    from PIL import Image, ImageDraw
    fnt = fuente(int(alto * 0.36), 1)
    dib = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    w = int(max(dib.textlength(arriba, font=fnt), dib.textlength(abajo, font=fnt))) + alto + 34
    capa = Image.new('RGBA', (w + 8, alto + 8), (0, 0, 0, 0))
    dib = ImageDraw.Draw(capa)
    dib.rounded_rectangle((6, 7, w + 6, alto + 7), alto // 2, fill=(0, 0, 0, 120))
    dib.rounded_rectangle((0, 0, w, alto), alto // 2, fill=(255, 255, 255, 255))
    ic = icono(tipo, alto - 10)
    capa.paste(ic, (5, 5), ic)
    x = alto + 12
    dib.text((x, alto * 0.30), arriba, font=fnt, fill=(15, 15, 15), anchor='lm')
    dib.text((x, alto * 0.70), abajo, font=fnt, fill=(15, 15, 15), anchor='lm')
    return capa


def logo_marca(marca):
    """El logo oficial guardado de la marca (mis_conocimientos/logos), o None."""
    from PIL import Image
    f = os.path.join(LOGOS_DIR, marca.lower().replace(' ', '_') + '.png')
    return Image.open(f).convert('RGBA') if os.path.exists(f) else None


# los títulos con los estilos que le gustan a fabian (mis_conocimientos/miniaturas/titulos, 30/10/2026): nunca planos,
# siempre degradé, borde grueso, relieve, brillo y la palabra clave en amarillo/dorado
TITULO_ESTILOS = {
    'placa': {'fuente': ['C:/Windows/Fonts/seguibli.ttf', 'C:/Windows/Fonts/ariblk.ttf'], 'italica': 0.0, 'borde': 9, 'relieve': 4,
              'oscuro': (10, 26, 80), 'claro': ((255, 255, 255), (222, 230, 246)), 'clave': ((255, 238, 96), (255, 190, 0))},
    'pincel': {'fuente': ['C:/Windows/Fonts/impact.ttf'], 'italica': 0.12, 'borde': 8, 'relieve': 3,
               'oscuro': (0, 0, 0), 'claro': ((255, 255, 255), (230, 230, 230)), 'clave': ((255, 240, 90), (255, 196, 0))},
    'metal': {'fuente': ['C:/Windows/Fonts/impact.ttf'], 'italica': 0.10, 'borde': 10, 'relieve': 11,
              'oscuro': (28, 16, 6), 'claro': ((255, 255, 255), (165, 176, 198)), 'clave': ((255, 242, 120), (240, 128, 0))},
}


def letras(texto, fnt, relleno, oscuro, borde, relieve):
    """Una palabra «de miniatura»: degradé de arriba abajo, borde grueso, relieve 3D hacia abajo, brillo arriba y sombra."""
    from PIL import Image, ImageDraw, ImageFilter, ImageChops
    caja = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), texto, font=fnt, stroke_width=borde)
    pad = borde + relieve + 24
    S = (caja[2] - caja[0] + 2 * pad, caja[3] - caja[1] + 2 * pad)
    o = (pad - caja[0], pad - caja[1])
    m_txt, m_borde = Image.new('L', S, 0), Image.new('L', S, 0)
    ImageDraw.Draw(m_txt).text(o, texto, font=fnt, fill=255)
    ImageDraw.Draw(m_borde).text(o, texto, font=fnt, fill=255, stroke_width=borde, stroke_fill=255)
    capa = Image.new('RGBA', S, (0, 0, 0, 0))
    sombra = Image.new('RGBA', S, (0, 0, 0, 0))
    sombra.paste((0, 0, 0, 190), (8, relieve + 10), m_borde)
    capa.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(9)))
    hondo = tuple(max(0, int(c * 0.55)) for c in relleno[1])  # el costado del relieve: el color de la letra, oscuro
    for k in range(relieve, 0, -1):
        capa.paste(hondo if k > 2 else oscuro, (0, k), m_borde)
    capa.paste(oscuro, (0, 0), m_borde)
    y0, y1 = o[1] + fnt.getbbox(texto)[1], o[1] + fnt.getbbox(texto)[3]
    u = np.clip((np.arange(S[1]) - y0) / max(1, y1 - y0), 0, 1)[:, None, None]
    grad = ((1 - u) * np.array(relleno[0]) + u * np.array(relleno[1])).astype(np.uint8)
    grad = np.repeat(grad, S[0], axis=1)
    capa.paste(Image.fromarray(grad, 'RGB'), (0, 0), m_txt)
    brillo = np.clip(1 - (np.arange(S[1]) - y0) / max(1, 0.5 * (y1 - y0)), 0, 1) * 120  # reflejo en la mitad de arriba
    banda = Image.fromarray(np.repeat(brillo[:, None], S[0], axis=1).astype(np.uint8), 'L')
    capa.paste((255, 255, 255), (0, 0), ImageChops.multiply(m_txt, banda))
    return capa


def titulo_estilizado(partes, estilo, ancho_max, alto_max=150):
    """El título en una fila: [(texto, es_clave), …] con el estilo elegido, sobre su placa, pincelada o halo."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    e = TITULO_ESTILOS.get(estilo, TITULO_ESTILOS['placa'])
    ruta = next((f for f in e['fuente'] + FUENTES if os.path.exists(f)), None)
    tam = alto_max
    while True:
        fnt = ImageFont.truetype(ruta, tam) if ruta else ImageFont.load_default()
        piezas = [letras(x, fnt, e['clave'] if clave else e['claro'], e['oscuro'], max(4, int(e['borde'] * tam / 120)),
                         max(2, int(e['relieve'] * tam / 120))) for x, clave in partes if x]
        recorte = 2 * (max(4, int(e['borde'] * tam / 120)) + max(2, int(e['relieve'] * tam / 120)) + 24) - int(tam * 0.18)
        ancho = sum(p.width for p in piezas) - recorte * (len(piezas) - 1)
        if ancho * (1 + e['italica'] * 0.6) <= ancho_max - (110 if estilo != 'metal' else 20) or tam < 40:
            break
        tam -= 4
    alto = max(p.height for p in piezas)
    fila = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
    x = 0
    for p in piezas:
        fila.alpha_composite(p, (x, alto - p.height))
        x += p.width - recorte
    if e['italica']:
        k = e['italica']
        fila = fila.transform((int(fila.width + k * fila.height), fila.height), Image.AFFINE, (1, k, -k * fila.height, 0, 1, 0), Image.BICUBIC)
    # lo que va detrás de las letras
    pad_x, pad_y = (60, 6) if estilo != 'metal' else (30, 0)
    W2, H2 = fila.width + 2 * pad_x, fila.height + 2 * pad_y
    fondo = Image.new('RGBA', (W2 + 60, H2 + 60), (0, 0, 0, 0))
    ox, oy = 30, 30
    m = Image.new('L', fondo.size, 0)
    dib = ImageDraw.Draw(m)
    if estilo == 'placa':  # placa azul brillante con borde de luz (como «iPhone No disponible»)
        caja = (ox + 20, oy + int(tam * 0.22), ox + W2 - 20, oy + H2 - int(tam * 0.18))
        dib.rounded_rectangle(caja, int(tam * 0.35), fill=255)
        luz = Image.new('RGBA', fondo.size, (0, 0, 0, 0))
        luz.paste((90, 210, 255, 230), (0, 0), m)
        fondo.alpha_composite(luz.filter(ImageFilter.GaussianBlur(14)))
        u = np.clip((np.arange(fondo.size[1]) - caja[1]) / max(1, caja[3] - caja[1]), 0, 1)[:, None, None]
        g = ((1 - u) * np.array([60, 140, 255]) + u * np.array([12, 52, 190])).astype(np.uint8)
        fondo.paste(Image.fromarray(np.repeat(g, fondo.size[0], axis=1), 'RGB'), (0, 0), m)
        ImageDraw.Draw(fondo).rounded_rectangle(caja, int(tam * 0.35), outline=(190, 240, 255), width=5)
        brillo = Image.new('L', fondo.size, 0)
        ImageDraw.Draw(brillo).rounded_rectangle((caja[0] + 8, caja[1] + 6, caja[2] - 8, (caja[1] + caja[3]) // 2), int(tam * 0.3), fill=60)
        fondo.paste((255, 255, 255), (0, 0), brillo)
    elif estilo == 'pincel':  # pincelada de verde a azul con bordes rotos (como «ELIM. PATRON HONOR 400 LITE»)
        rng = np.random.default_rng(7)
        y_a, y_b = oy + int(tam * 0.18), oy + H2 - int(tam * 0.12)
        arriba = [(ox + x, y_a + rng.integers(-6, 7)) for x in range(0, W2, 24)]
        abajo = [(ox + x, y_b + rng.integers(-6, 7)) for x in range(W2, -1, -24)]
        izq = [(ox - rng.integers(0, 30), y) for y in range(y_b, y_a, -10)]
        der = [(ox + W2 + rng.integers(0, 30), y) for y in range(y_a, y_b, 10)]
        dib.polygon(arriba + der + abajo + izq, fill=255)
        u = np.linspace(0, 1, fondo.size[0])[None, :, None]
        g = ((1 - u) * np.array([70, 225, 60]) + u * np.array([28, 70, 235])).astype(np.uint8)
        capa = Image.fromarray(np.repeat(g, fondo.size[1], axis=0), 'RGB')
        rayas = ImageDraw.Draw(capa)
        for _ in range(40):  # las marcas del pincel
            y = int(rng.integers(y_a, y_b))
            rayas.line((ox + int(rng.integers(0, W2 // 3)), y, ox + int(rng.integers(W2 // 2, W2)), y), fill=(255, 255, 255) if rng.random() < .5 else (0, 40, 90), width=1)
        sombra = Image.new('RGBA', fondo.size, (0, 0, 0, 0))
        sombra.paste((0, 0, 0, 150), (6, 10), m)
        fondo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(10)))
        fondo.paste(capa, (0, 0), m)
    else:  # metal 3D sobre un halo oscuro (como «BYPASS iOS SIN ERRORES»)
        dib.rounded_rectangle((ox + 30, oy + 20, ox + W2 - 30, oy + H2 - 10), 40, fill=200)
        halo = Image.new('RGBA', fondo.size, (0, 0, 0, 0))
        halo.paste((8, 18, 70, 255), (0, 0), m)
        fondo.alpha_composite(halo.filter(ImageFilter.GaussianBlur(26)))
    fondo.alpha_composite(fila, (ox + pad_x, oy + pad_y))
    return fondo


def componer_mixta(escena, lineas, marca, idioma, salida, estilo='placa', titulo_png=None, esquinas=('NEW 2026', '')):
    """Pone encima de la escena de GPT todo lo escrito y los logos, en el idioma pedido."""
    from PIL import Image, ImageDraw
    lienzo = Image.fromarray(cv2.cvtColor(cv2.resize(escena, (W, H), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)).convert('RGBA')
    def pega(capa, x, y):  # sin salirse del lienzo
        x, y = int(x), int(y)
        capa = capa.crop((max(0, -x), max(0, -y), min(capa.width, W - x), min(capa.height, H - y)))
        lienzo.alpha_composite(capa, (max(0, x), max(0, y)))
    # abajo, el título con uno de tus estilos: la marca en blanco/plateado y el problema en amarillo/dorado
    partes = [(x, k > 0) for k, (x, _) in enumerate(traducir(l, idioma) for l in lineas if l)]
    if titulo_png and os.path.exists(titulo_png):  # el que dibujó GPT con tu estilo, recortado y a lo ancho de abajo
        capa = Image.open(titulo_png).convert('RGBA')
        caja = capa.getchannel('A').point(lambda v: 255 if v > 60 else 0).getbbox()  # sin el borde casi invisible
        capa = capa.crop(caja or (0, 0, capa.width, capa.height))
        k = min((W - 30) / capa.width, 235 / capa.height)
        capa = capa.resize((int(capa.width * k), int(capa.height * k)), Image.LANCZOS)
        pega(capa, (W - capa.width) / 2, H - capa.height - 10)
    else:
        capa = titulo_estilizado(partes, estilo, W - 20)
        pega(capa, (W - capa.width) / 2, H - capa.height + 18)
    # arriba: los textos cortos de las esquinas (NEW 2026…) y las etiquetas ANTES / DESPUÉS sobre cada teléfono
    izq, der = (list(esquinas) + ['', ''])[:2]
    if izq:
        pega(sticker(izq.upper(), 'rojo', 82, 10), 8, 6)
    alto_der = 0
    if der:
        c = sticker(der.upper(), 'azul', 74, -8)
        pega(c, W - c.width - 6, 4)
        alto_der = c.height - 6
    antes, despues = ANTES_DESPUES[idioma]
    for txt, col, cx in ((antes, 'rojo', 0.31), (despues, 'verde', 0.61)):
        c = sticker(txt, col, 96, 5)
        pega(c, W * cx - c.width / 2, 8)
    # la columna derecha: logo oficial, sello y las dos píldoras
    logo = logo_marca(marca)
    if logo is not None:
        k = min(230 / logo.width, (110 if not alto_der else 64) / logo.height)  # con texto en la esquina, el logo va debajo y más chico
        logo = logo.resize((int(logo.width * k), int(logo.height * k)), Image.LANCZOS)
        pega(logo, W - logo.width - 14, 14 + alto_der)
    s = sello(108 if not alto_der else 96, SELLO[idioma])
    pega(s, W - s.width - 10, max(H * 0.205, 14 + alto_der + 62))
    y = H * 0.545
    for arriba, abajo, tipo in PILDORAS_MIXTA[necesita_pc(marca)][idioma]:
        p = pildora(arriba, abajo, tipo, 62)
        pega(p, W - p.width - 16, y)
        y += p.height + 10
    lienzo.convert('RGB').save(salida, quality=92)


TITULOS_REF = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'titulos')  # los títulos que le gustan (ESTILO_TITULOS.md)
TITULO_GPT = {
    'placa': (['placa_iphone_no_disponible.png'], 'una placa azul brillante redondeada con borde de luz celeste y reflejo arriba, '
              'detrás de las letras; letra muy gruesa, redondeada e itálica, con borde azul oscuro y sombra'),
    # otros colores de placa (fabian, 30/10/2026: la azul se pierde sobre su escritorio claro)
    'placa_negra': (['placa_iphone_no_disponible.png'], 'la MISMA placa redondeada pero NEGRA brillante (negro azulado, '
                    'reflejo arriba) con un borde de neón celeste que brilla, detrás de las letras; letra muy gruesa, redondeada '
                    'e itálica, con borde oscuro y sombra'),
    'placa_roja': (['placa_iphone_no_disponible.png'], 'la MISMA placa redondeada pero ROJA brillante (rojo vivo arriba, '
                   'rojo oscuro abajo) con un borde de luz blanca, detrás de las letras; letra muy gruesa, redondeada e '
                   'itálica, con borde oscuro y sombra'),
    'placa_violeta': (['placa_iphone_no_disponible.png'], 'la MISMA placa redondeada pero VIOLETA a MAGENTA brillante con '
                      'un borde de luz rosa, detrás de las letras; letra muy gruesa, redondeada e itálica, con borde oscuro y sombra'),
    'pincel': (['pincel_elim_patron_honor.png'], 'una pincelada pintada a mano de verde a azul, con bordes rotos, a todo el ancho detrás '
               'de las letras; letra condensada muy gruesa con borde negro'),
    'metal': (['metal_bypass_ios.png', 'metal_quitar_google.png'], 'letras 3D enormes con relieve y brillo, la parte clave en '
              'dorado (amarillo a naranja) y la marca en plateado, borde oscuro grueso y un halo azul oscuro detrás'),
}


def titulo_gpt(partes, estilo, salida):
    """GPT 2.5 dibuja SOLO el título (fondo transparente) copiando uno de tus estilos. Guarda el PNG en salida."""
    refs, como = TITULO_GPT.get(estilo, TITULO_GPT['placa'])
    refs = [os.path.join(TITULOS_REF, f) for f in refs if os.path.exists(os.path.join(TITULOS_REF, f))]
    blanco, clave = (partes + [''])[:2]
    prompt = ('Diseña SOLO el título de una miniatura de YouTube, sobre fondo TRANSPARENTE: nada más (sin teléfonos, sin '
              'personas, sin fondo, sin marco de imagen). Copia EXACTAMENTE el estilo de las letras y de lo que va detrás de '
              f'ellas de la(s) imagen(es) de referencia (no su texto): {como}. El texto, en UNA sola fila y perfectamente '
              f'escrito, son estas palabras exactas y ninguna más: «{blanco}» en blanco/plateado'
              + (f' y «{clave}» en amarillo/dorado' if clave else '') +
              '. Letras enormes que ocupen casi todo el ancho, con volumen, brillo, borde grueso y sombra. Centrado y '
              'completo, sin cortar nada en los bordes.')
    img = imagen_gpt(prompt, refs, size='1536x1024', transparente=True)
    if img.ndim == 3 and img.shape[2] == 3:  # por si no vino transparente
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    guardar_img(salida, img)
    return salida


# las etiquetas de arriba (NEW 2026, ANTES, DESPUÉS, BEFORE…) dibujadas por GPT 2.5 una sola vez y guardadas para todos
# los videos (fabian, 30/10/2026: las que dibuja la app se ven genéricas)
ETIQUETAS_DIR = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'etiquetas')
COLORES_ETIQUETA = {'rojo': ((226, 30, 36), 'roja (rojo vivo arriba, rojo oscuro abajo)'),
                    'verde': ((34, 168, 64), 'verde (verde vivo arriba, verde oscuro abajo)'),
                    'azul': ((24, 104, 235), 'azul eléctrico (celeste arriba, azul oscuro abajo)'),
                    'naranja': ((245, 140, 20), 'naranja (amarillo anaranjado arriba, naranja oscuro abajo)')}


def archivo_etiqueta(texto, color):
    import unicodedata
    slug = re.sub(r'[^a-z0-9]+', '_', unicodedata.normalize('NFKD', texto.lower()).encode('ascii', 'ignore').decode()).strip('_')
    return os.path.join(ETIQUETAS_DIR, f'{slug or "etiqueta"}_{color}.png')


def etiqueta_gpt(texto, color):
    """La etiqueta dibujada por GPT 2.5 (fondo transparente). Si ya está guardada no gasta nada. Devuelve el archivo."""
    f = archivo_etiqueta(texto, color)
    if os.path.exists(f):
        return f
    refs = [os.path.join(ESTILO, x) for x in ('honor_antes_despues.jpg', 'samsung_a56_antes_despues.jpg')]
    refs = [x for x in refs if os.path.exists(x)] + [os.path.join(TITULOS_REF, 'metal_bypass_ios.png')]
    prompt = ('Diseña SOLO una etiqueta (sticker) para una miniatura de YouTube, sobre fondo TRANSPARENTE: nada más, sin '
              'teléfonos ni fondo. Estilo premium como las etiquetas «ANTES/DESPUÉS» y los títulos de las imágenes de '
              f'referencia: una placa {COLORES_ETIQUETA[color][1]} levemente inclinada, con volumen 3D, brillo arriba, borde '
              'blanco grueso y sombra suave; encima, el texto en letra muy gruesa y condensada, blanca, con borde oscuro, '
              f'relieve y brillo. El texto exacto, perfectamente escrito y nada más: «{texto}». Centrada y completa, sin cortar.')
    print(f'· GPT dibuja la etiqueta «{texto}» ({color}); queda guardada para siempre…', flush=True)
    img = imagen_gpt(prompt, [x for x in refs if os.path.exists(x)], size='1536x1024', transparente=True)
    if img.ndim == 3 and img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    a = img[..., 3] > 60
    ys, xs = np.where(a)
    if len(xs):
        img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    os.makedirs(ETIQUETAS_DIR, exist_ok=True)
    guardar_img(f, img)
    return f


def sticker(texto, color, alto, angulo):
    """La etiqueta de GPT si ya está guardada; si no, la que dibuja la app."""
    from PIL import Image
    f = archivo_etiqueta(texto, color)
    if os.path.exists(f):
        im = Image.open(f).convert('RGBA')
        k = alto / im.height
        return im.resize((max(1, int(im.width * k)), alto), Image.LANCZOS)
    return cinta(texto, COLORES_ETIQUETA[color][0], int(alto * 0.62) if len(texto) <= 10 else int(alto * 0.5), angulo)


def traducciones_titulo(d, lineas):
    """{'es': [...], 'en': [...], 'pt': [...]}: la traducción que dio la IA al sugerir ese título, las frases conocidas, o se
    la pide a la IA (un pedido corto de texto) y la guarda para la próxima."""
    import subprocess
    es = [x.strip() for x in lineas if x and x.strip()]
    f = os.path.join(d, 'titulos_miniatura_ia.json')
    try:
        datos = json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        datos = {'titulos': []}
    for t in datos.get('titulos', []) + datos.get('traducidos', []):
        if [x.upper() for x in t.get('es', [])] == [x.upper() for x in es] and t.get('en') and t.get('pt'):
            return {'es': es, 'en': t['en'], 'pt': t['pt']}
    sueltas = {str(t.get('es', '')).upper(): t for t in datos.get('esquinas', []) if isinstance(t, dict)}  # las de las esquinas
    if es and all(x.upper() in sueltas for x in es):
        return {'es': es, **{i: [sueltas[x.upper()].get(i) or x for x in es] for i in ('en', 'pt')}}
    out = {'es': es, **{i: [traducir(x, i)[0] for x in es] for i in ('en', 'pt')}}
    if not any(traducir(x, 'en')[1] and x.upper() not in MARCAS and not re.fullmatch(r'(NEW\s*)?(20\d\d)?|[\d%+.\s]+', x.upper()) for x in es):
        return out
    try:  # una frase tuya que no conozco: la traduce la IA de la app
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'titulos.py'), '--proyecto', d,
                            '--traducir', '|'.join(es)], capture_output=True, text=True, encoding='utf-8', timeout=300)
        t = json.loads(r.stdout.strip().splitlines()[-1])['titulo']
        out.update(en=t['en'], pt=t['pt'])
        datos.setdefault('traducidos', []).append(t)
        json.dump(datos, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"· título traducido: {' / '.join(t['en'])} · {' / '.join(t['pt'])}", flush=True)
    except Exception as e:
        print(f'· no pude traducir el título con la IA ({e}): en inglés y portugués queda en español', flush=True)
    return out


def miniaturas_mixtas(d, refs, lineas, salida_base, marca='TU CELULAR', idiomas=('es', 'en', 'pt'), antes_desc=None, fondo='escritorio', extras=(), estilos=('placa',), titulo_por_gpt=False, escena=None, esquinas=('NEW 2026', ''), base_titulo=None):
    """Una escena de GPT sin texto y, encima, lo escrito por la app en cada idioma. Devuelve los archivos.
    base_titulo: dónde se guarda el título de GPT, sin el fondo en el nombre (con «Los dos» fondos se dibuja una sola vez)."""
    refs = list(refs) + ([MASCOTA] if os.path.exists(MASCOTA) else []) + list(extras) + referencias_estilo(marca, 2)
    fondo_txt = FONDOS_MINI.get(fondo, FONDOS_MINI['escritorio']).replace('(1) fondo', 'FONDO')
    prompt = ('Escena para una miniatura de YouTube 16:9 del canal Xiaomiunlock, al estilo de las miniaturas de las últimas '
              'imágenes (solo el estilo de la escena: sin su texto). ' + fondo_txt +
              f'Imagen 1: el teléfono REAL de este video ANTES: {antes_desc or "bloqueado"}; Imagen 2: el mismo teléfono ya libre '
              'en SU pantalla de inicio (DESPUÉS). Pon los dos teléfonos reales grandes, de frente, sostenidos con guante negro, '
              'con la pantalla copiada tal cual de las fotos y bien legible: el de ANTES centrado al 31 % del ancho y el de '
              'DESPUÉS al 61 %, los dos desde el 15 % hasta el 85 % del alto. Entre los dos, una flecha gruesa curva amarilla '
              'del de ANTES al de DESPUÉS y, debajo, un candado abierto azul con la G de Google. Imagen 3: SU MASCOTA (el conejo '
              'Mi con casco de soldar y el androide verde con herramientas), a la izquierda abajo, entre el 45 % y el 82 % del '
              'alto, sin tapar el teléfono. '
              + (f'Imágenes 4 a {3 + len(extras)}: más fotos HD reales del mismo teléfono, para copiarlo fiel. ' if extras else '') +
              'MUY IMPORTANTE: NO escribas ningún texto, letra, número, logo, sello, etiqueta, '
              'píldora ni marca de agua fuera de las pantallas de los teléfonos: los pondré yo después. Deja LIBRE (solo fondo) '
              'la franja derecha (del 79 % al 100 % del ancho) y la franja de arriba a la izquierda (hasta el 20 % del ancho y '
              'el 14 % del alto). Colores saturados, mucho contraste, bien iluminado. Todo dentro de la imagen 16:9.')
    if escena is None:
        print('· la IA de imágenes hace la escena (sin texto)…', flush=True)
        escena = imagen_gpt(prompt, refs)
        guardar_img(f'{salida_base}_escena.png', escena)
    hechas = []
    tr = traducciones_titulo(d, lineas)
    llenas = [x for x in esquinas if x]  # las esquinas también van traducidas
    tr_esq = traducciones_titulo(d, llenas) if llenas else {}
    esq = {i: [(tr_esq.get(i) or llenas)[llenas.index(x)] if x else '' for x in esquinas] for i in idiomas}
    for estilo in estilos:
        for idioma in idiomas:
            f = f'{salida_base}_{estilo}_{idioma}.jpg' if len(estilos) > 1 else f'{salida_base}_{idioma}.jpg'
            png = None
            if titulo_por_gpt:  # el título lo dibuja GPT 2.5 con tu estilo (1 imagen por estilo e idioma)
                # con una huella del texto: si cambias el título se dibuja el nuevo (antes salía el viejo guardado)
                huella = hashlib.md5('|'.join(str(x) for x in tr.get(idioma, lineas)).encode('utf-8')).hexdigest()[:8]
                png = f'{base_titulo or salida_base}_titulo_{estilo}_{idioma}_{huella}.png'
                if not os.path.exists(png):
                    print(f'· GPT dibuja el título «{" ".join(tr.get(idioma, lineas))}» ({estilo})…', flush=True)
                    titulo_gpt(tr.get(idioma, lineas), estilo, png)
            if titulo_por_gpt:  # las etiquetas de arriba también de GPT (solo la primera vez: después quedan guardadas)
                for txt, col in zip(ANTES_DESPUES[idioma] + tuple(x.upper() for x in esq[idioma]), ('rojo', 'verde', 'rojo', 'azul')):
                    if txt:
                        etiqueta_gpt(txt, col)
            componer_mixta(escena, tr.get(idioma, lineas), marca, idioma, f, estilo, png, esq[idioma])
            hechas.append(os.path.basename(f))
            print(f'· {os.path.basename(f)} lista', flush=True)
    return hechas


SHORTS = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'shorts')  # portadas de Shorts de fabian (ESTILO_SHORTS.md)
PROMESA = {'es': 'EN INSTANTES - DE RAÍZ', 'en': 'IN SECONDS - PERMANENT', 'pt': 'EM INSTANTES - DE RAIZ'}
SIN_PC = {'es': 'SIN PC', 'en': 'NO PC', 'pt': 'SEM PC'}


def vista_grilla(img, salida):
    """Cómo se ve la portada en la grilla de Shorts del canal (medido el 02/11/2026 con la de Movistar): YouTube muestra solo
    el centro 2:3, 1080×1620, y se pierden ~150 px arriba y abajo. Al lado, la portada entera con la zona segura marcada
    (sin texto en el 12 % de arriba ni en el 15 % de abajo, donde además va la interfaz del Short)."""
    h, w = img.shape[:2]
    corte = (h - w * 3 // 2) // 2
    grilla = img[corte:h - corte]
    marcada = img.copy()
    capa = marcada.copy()
    cv2.rectangle(capa, (0, 0), (w, int(h * 0.12)), (0, 0, 255), -1)
    cv2.rectangle(capa, (0, int(h * 0.85)), (w, h), (0, 0, 255), -1)
    marcada = cv2.addWeighted(capa, 0.35, marcada, 0.65, 0)
    alto = 960
    lado = [cv2.resize(x, (int(x.shape[1] * alto / x.shape[0]), alto)) for x in (marcada, grilla)]
    guardar_img(salida, np.hstack(lado), [cv2.IMWRITE_JPEG_QUALITY, 88])


def borde_texto_arriba(img, ocr=None):
    """El y más alto donde hay texto en la portada (OCR local); None si no se puede leer."""
    try:
        if ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            ocr = RapidOCR()
        r, _ = ocr(img)
    except Exception:
        return None
    ys = [min(p[1] for p in caja) for caja, txt, conf in (r or []) if len(txt.strip()) >= 3 and conf > 0.5]
    return int(min(ys)) if ys else None


def ajustar_grilla(img, arriba=220, abajo=0.80):
    """Fabian, 02/11/2026: en la grilla de Shorts el título no se puede cortar. Si el texto empieza más arriba que «arriba»
    px (de 1920), baja el contenido y, si hace falta para que lo de abajo no caiga en el 20 % de los botones, lo achica un
    poco. La franja que queda arriba se rellena con la misma imagen estirada y desenfocada (sin bandas ni costuras).
    Devuelve (imagen, cambió)."""
    h, w = img.shape[:2]
    y0 = borde_texto_arriba(img)
    if y0 is None or y0 >= arriba:
        return img, False
    bajar = arriba - y0 + 10
    escala = max(0.85, min(1.0, (h * abajo - (arriba - y0)) / (h * abajo)))
    nw, nh = int(w * escala) // 2 * 2, int(h * escala) // 2 * 2
    fondo = cv2.GaussianBlur(cv2.resize(img, (w, h)), (0, 0), 40)
    chico = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    x = (w - nw) // 2
    y = min(bajar, h - 1)
    lienzo = fondo.copy()
    alto = min(nh, h - y)
    # fundido suave en los bordes del contenido: sin costuras
    mascara = np.zeros((alto, nw), np.float32)
    mascara[:] = 1.0
    borde = 24
    for i in range(borde):
        v = (i + 1) / borde
        mascara[i, :] = np.minimum(mascara[i, :], v)
        mascara[:, i] = np.minimum(mascara[:, i], v)
        mascara[:, nw - 1 - i] = np.minimum(mascara[:, nw - 1 - i], v)
    m3 = mascara[..., None]
    zona = lienzo[y:y + alto, x:x + nw].astype(np.float32)
    lienzo[y:y + alto, x:x + nw] = (chico[:alto].astype(np.float32) * m3 + zona * (1 - m3)).astype(np.uint8)
    return lienzo, True


def portadas_short(d, refs, lineas, salida_base, marca='TU CELULAR', idiomas=('es', 'en', 'pt')):
    """La portada vertical (9:16) del Short con el estilo de fabian, una por idioma. Devuelve los archivos."""
    import base64, urllib.request, uuid
    k = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')).get('ias_guion', {}).get('gpt', {}).get('clave', '')
    if not k:
        raise SystemExit('ERROR: falta la clave de OpenAI (la de GPT en «🤖 Ajustes IA») para la portada del Short.')
    try:
        suyas = sorted(f for f in os.listdir(SHORTS) if f.lower().endswith(('.jpg', '.png')))
    except OSError:
        suyas = []
    suyas = [f for f in suyas if f.lower().startswith(marca.lower()[:4])] + [f for f in suyas if not f.lower().startswith(marca.lower()[:4])]
    imgs = list(refs[:1]) + ([MASCOTA] if os.path.exists(MASCOTA) else []) + [os.path.join(SHORTS, f) for f in suyas[:3]]
    marca_logo = marca.title() if marca != 'TU CELULAR' else 'la marca del teléfono'
    hechas = []
    for idioma, nombre in [x for x in (('es', 'español'), ('en', 'inglés'), ('pt', 'portugués')) if x[0] in idiomas]:
        partes = [traducir(x, idioma) for x in lineas if x]
        texto = ' / '.join(f'«{x}»' for x, _ in partes)
        traduce = any(t for _, t in partes)
        # «SIN PC» solo si fabian marcó que esa marca no necesita PC (Honor sí la necesita)
        pildora = (f'una píldora blanca «{SIN_PC[idioma]}» con una laptop. ' if not necesita_pc(marca)
                   else 'una píldora blanca «' + PILDORAS_PC[idioma].split('»')[0].strip('«') + '». ')
        prompt = ('Portada VERTICAL 9:16 de un YouTube Short del canal Xiaomiunlock de fabian, IDÉNTICA a SU ESTILO. Imagen 1: el '
                  'teléfono REAL de este video con la pantalla bloqueada. Imagen 2: SU MASCOTA (el conejo con casco «XIAOMIUNLOCK»): '
                  'chica en una esquina de abajo. Las demás son portadas suyas: cópiales el estilo (no su texto ni su teléfono). '
                  'OBLIGATORIO: fondo de degradé vivo (violeta, naranja, celeste); el teléfono real ENORME ocupando el centro, con '
                  'la pantalla bloqueada bien legible y una flecha roja curva hacia ella; ARRIBA el título en una o dos franjas '
                  'oscuras redondeadas, letra blanca muy gruesa, condensada e itálica, perfectamente escrita, en '
                  f'{nombre}: {texto}' + (f' (tradúcelo al {nombre}, corto y natural)' if traduce else '') +
                  f'; al lado del título el logo de {marca_logo} en un cuadrado; más abajo (por ENCIMA del 15 % final) una franja azul con «{PROMESA[idioma]}» y '
                  + pildora +
                  'Letras grandes que se lean en el celular. Ningún otro texto, ningún logo ni persona inventados. Todo completo '
                  'dentro de la imagen vertical, sin cortar nada. ZONA VISIBLE (fabian, 02/11/2026): en la grilla de Shorts YouTube '
                  'muestra solo el centro 2:3 (se pierde ~8 % arriba y abajo) y abajo la interfaz tapa más: NINGÚN texto en el 12 % '
                  'de arriba ni en el 15 % de abajo, ni pegado al borde derecho; el título empieza a ~12 % del alto.')
        b = uuid.uuid4().hex
        cuerpo = b''
        for campo, v in {'model': 'gpt-image-2.5-flare', 'prompt': prompt, 'size': '864x1536', 'quality': 'high', 'output_format': 'png'}.items():
            cuerpo += f'--{b}\r\nContent-Disposition: form-data; name="{campo}"\r\n\r\n{v}\r\n'.encode()
        for i, r in enumerate(imgs):
            tipo = 'image/jpeg' if r.lower().endswith('.jpg') else 'image/png'
            cuerpo += (f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="ref{i}{os.path.splitext(r)[1]}"\r\n'
                       f'Content-Type: {tipo}\r\n\r\n').encode() + open(r, 'rb').read() + b'\r\n'
        cuerpo += f'--{b}--\r\n'.encode()
        req = urllib.request.Request('https://api.openai.com/v1/images/edits', data=cuerpo,
                                     headers={'Authorization': 'Bearer ' + k, 'Content-Type': f'multipart/form-data; boundary={b}'})
        print(f'· la IA de imágenes hace la portada del Short en {nombre}…', flush=True)
        r = pedir_imagen(req)
        img = cv2.imdecode(np.frombuffer(base64.b64decode(r['data'][0]['b64_json']), np.uint8), cv2.IMREAD_COLOR)
        f = f'{salida_base}_{idioma}.jpg'
        img = cv2.resize(img, (1080, 1920), interpolation=cv2.INTER_CUBIC)
        img, _ = ajustar_grilla(img)  # que la grilla de Shorts no corte el título
        guardar_img(f, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        vista_grilla(img, f'{salida_base}_{idioma}_vista_grilla.jpg')
        hechas.append(os.path.basename(f))
        print(f'· {os.path.basename(f)} lista', flush=True)
    return hechas


FOTOS = ('antes', 'despues', 'extra1', 'extra2')  # las fotos HD que subes en «🖼 Miniatura» (foto_miniatura_*.jpg)


def estilos_titulo(a):
    if a.titulo == 'placas':  # las 4 placas, para ver cuál contrasta mejor
        return ('placa', 'placa_negra', 'placa_roja', 'placa_violeta')
    return ('placa_negra', 'placa', 'metal') if a.titulo == 'todos' else (a.titulo,)  # los favoritos de fabian (30/10/2026)


def momentos_miniatura(d):
    """Los segundos de tu video que sirven de ANTES (verifica, fastboot, bienvenido) y de DESPUÉS (inicio). Se guardan en
    momentos_miniatura.json para no volver a buscarlos."""
    f = os.path.join(d, 'momentos_miniatura.json')
    try:
        return json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        pass
    orig = os.path.join(d, 'original.mp4')
    if not os.path.exists(orig):
        return {}
    nt = analizar(orig, os.path.splitext(orig)[0] + '.nitidez.npz')
    total = float(nt[0][-1]) if len(nt[0]) else 60.0
    mo = cuadros_clave(d, nt)
    if not any(k in mo for k in ('verifica', 'fastboot', 'bienvenido')):
        mo['verifica'] = mejor(*nt, total * 0.02, total * 0.15)
    mo.setdefault('inicio', mejor(*nt, total * 0.975, total * 0.998))
    mo = {k: round(float(v), 1) for k, v in mo.items()}
    json.dump(mo, open(f, 'w', encoding='utf-8'), indent=1)
    return mo


def con_fotos(d, a):
    """El módulo «🖼 Miniatura» (pedido de fabian, 30/10/2026): tus fotos HD en vez de los cuadros del video. Desde el
    03/11/2026 GPT hace todo (textos incluidos) con la fórmula de su canal; con --mixta, como antes, la app pone los textos."""
    fotos = {k: os.path.join(d, f'foto_miniatura_{k}.jpg') for k in FOTOS if os.path.exists(os.path.join(d, f'foto_miniatura_{k}.jpg'))}
    if not a.gpt:
        raise SystemExit('ERROR: la miniatura con tus fotos la hace GPT: escribe SI para confirmar el gasto.')
    temporales = []
    orig = os.path.join(d, 'original.mp4')
    for k, claves, que in (('antes', ('verifica', 'fastboot', 'bienvenido'), 'el teléfono bloqueado'), ('despues', ('inicio',), 'el teléfono ya libre')):
        if k in fotos:
            continue
        mo = momentos_miniatura(d)  # sin tu foto: el mejor cuadro de tu video
        s = next((mo[c] for c in claves if c in mo), None)
        ok = False
        if s is not None and os.path.exists(orig):
            cap = cv2.VideoCapture(orig)
            cap.set(cv2.CAP_PROP_POS_MSEC, s * 1000)
            ok, c = cap.read()
            cap.release()
        if not ok:
            raise SystemExit(f'ERROR: falta la foto del {k.upper()} ({que}) y no la encontré en tu video. Súbela en «🖼 Miniatura».')
        fotos[k] = os.path.join(d, f'.ref_miniatura_{k}.png')
        temporales.append(fotos[k])
        guardar_img(fotos[k], c)
        print(f'· sin foto del {k.upper()}: uso tu video en {int(s // 60)}:{int(s % 60):02d}', flush=True)
    lineas = list(a.texto.split('|')[:2]) if a.texto else list(textos(d)[0])
    extras = [fotos[k] for k in FOTOS[2:] if k in fotos]
    marca = next((x.strip().upper() for x in lineas if x.strip().upper() in MARCAS), textos(d)[0][0])  # para el logo oficial
    hechas = []
    import time
    calidad = getattr(a, 'calidad', None) or 'baja'
    idiomas = tuple(x for x in str(getattr(a, 'idiomas', None) or 'es,en,pt').split(',') if x in ('es', 'en', 'pt')) or ('es', 'en', 'pt')
    try:
        for fondo in (('foto', 'gpt') if a.fondo == 'ambos' else (a.fondo,)):
            if not a.mixta:  # (fabian, 03/11/2026) todo GPT con la fórmula de su canal: borrador en baja y la final en media
                info = {}
                # con la fecha: solo con la hora, un borrador de otro día a la misma hora pisaba al de antes (revisión, 03/11/2026)
                base = os.path.join(d, f"miniatura_canal_{fondo}_{calidad}_{time.strftime('%m%d%H%M%S')}")
                for f in miniaturas_gpt(d, [fotos['antes'], fotos['despues']], lineas, base, marca, idiomas=idiomas,
                                        antes_desc='tal como está en la foto HD', fondo=fondo, extras=extras, calidad=calidad,
                                        esquinas=(a.esquina_izq, a.esquina_der), cara=bool(getattr(a, 'cara', False)),
                                        refs_canal=[x for x in str(getattr(a, 'refs_canal', None) or '').split(',') if x], info=info):
                    hechas.append({'archivo': f, 'de': f"tus fotos · como tu canal · {'borrador' if calidad == 'baja' else 'final'} en "
                                                        f"calidad {calidad} · fondo {'de tus fotos' if fondo == 'foto' else 'azul con neón'}",
                                   'texto': [x for x in lineas if x], 'idioma': f.rsplit('_', 1)[1][:2], 'fondo': fondo,
                                   'calidad': calidad, 'esquinas': [a.esquina_izq, a.esquina_der], 'cara': bool(getattr(a, 'cara', False)),
                                   'modelo': info.get('modelo'), 'refs_canal': info.get('refs_canal'), 'costo_usd': info.get('costo_usd')})
                continue
            hacer = (lambda *x, **k: miniaturas_mixtas(*x, estilos=estilos_titulo(a), titulo_por_gpt=a.titulo_gpt,
                                                      esquinas=(a.esquina_izq, a.esquina_der),
                                                      base_titulo=os.path.join(d, 'miniatura_fotos_mixta'), **k))
            base = os.path.join(d, f"miniatura_fotos_mixta_{fondo}")
            for f in hacer(d, [fotos['antes'], fotos['despues']], lineas, base, marca, antes_desc='tal como está en la foto HD',
                           fondo=fondo, extras=extras):
                hechas.append({'archivo': f, 'de': f"tus fotos · mixta · fondo {'de tus fotos' if fondo == 'foto' else 'de GPT'}",
                               'texto': [x for x in lineas if x]})
    finally:
        for f in temporales:
            os.remove(f)
    try:  # los borradores de antes no se pierden al hacer la final (fabian los compara)
        antes = json.load(open(os.path.join(d, 'miniatura_fotos.json'), encoding='utf-8')).get('miniaturas') or []
    except (OSError, ValueError, AttributeError):
        antes = []
    nuevas = {h['archivo'] for h in hechas}
    todas = hechas + [h for h in antes if isinstance(h, dict) and h.get('archivo') not in nuevas
                      and os.path.isfile(os.path.join(d, str(h.get('archivo'))))]
    json.dump({'miniaturas': todas[:60]}, open(os.path.join(d, 'miniatura_fotos.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Listo: {len(hechas)} miniaturas con tus fotos.', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--texto', help='las dos líneas separadas por |, para las 3 opciones')
    ap.add_argument('--gpt', action='store_true', help='además, la miniatura de gpt-image-2.5-flare en 3 idiomas (gasta)')
    ap.add_argument('--momentos', action='store_true', help='solo busca en el video los cuadros de ANTES y DESPUÉS (gratis)')
    ap.add_argument('--fotos', action='store_true', help='con --gpt: usa tus fotos HD (foto_miniatura_*.jpg) en vez de los cuadros del video')
    ap.add_argument('--fondo', choices=('foto', 'gpt', 'ambos'), default='foto', help='con --fotos: el fondo de tus fotos, uno de GPT o los dos')
    ap.add_argument('--titulo', choices=('placa', 'placa_negra', 'placa_roja', 'placa_violeta', 'pincel', 'metal', 'todos', 'placas'), default='todos', help='con --mixta: el estilo del título (todos = los dos que le gustan a fabian: placa y metal)')
    ap.add_argument('--titulo-gpt', action='store_true', help='con --mixta: el título lo dibuja GPT 2.5 con tu estilo (1 imagen por estilo e idioma)')
    ap.add_argument('--esquina-izq', default='NEW 2026', help='con --mixta: texto corto arriba a la izquierda (vacío = nada)')
    ap.add_argument('--esquina-der', default='', help='con --mixta: texto corto arriba a la derecha (el logo baja un poco)')
    ap.add_argument('--mixta', action='store_true', help='con --gpt: GPT hace solo la escena y la app pone textos y logos (1 imagen para los 3 idiomas)')
    ap.add_argument('--fondos', action='store_true', help='con --gpt: dos miniaturas en español, una con tu escritorio real de fondo y otra con fondo de GPT')
    ap.add_argument('--variantes', action='store_true', help='con --gpt: una miniatura por cada ANTES (bloqueada, fastboot, Bienvenido), en español')
    ap.add_argument('--short', action='store_true', help='además, la portada vertical del Short con gpt-image-2.5-flare en 3 idiomas (gasta)')
    # (fabian, 03/11/2026) la miniatura de GPT con la fórmula de su canal: borrador en baja y la final aprobada en media
    ap.add_argument('--calidad', choices=tuple(CALIDADES), default='baja', help='baja = borrador (~0,02 USD), media = final (~0,07 USD), alta solo si la pides')
    ap.add_argument('--idiomas', default='es,en,pt', help='con --fotos sin --mixta: los idiomas, separados por coma')
    ap.add_argument('--cara', action='store_true', help='con --fotos sin --mixta: un hombre latino ficticio a un costado, buzo blanco liso')
    ap.add_argument('--refs-canal', default='', help='con --fotos sin --mixta: los ids de las miniaturas del canal de un borrador (su final)')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    if a.momentos:
        print(json.dumps(momentos_miniatura(d)), flush=True)
        return
    if a.fotos:
        return con_fotos(d, a)
    orig = os.path.join(d, 'original.mp4')
    if not os.path.exists(orig):
        raise SystemExit('ERROR: falta tu grabación (original.mp4).')
    col = colores()
    lineas = [tuple(a.texto.split('|')[:2]) + ('',)] * 3 if a.texto else textos(d)
    # la marca para el logo oficial (como en «🖼 Miniatura»): la del título si es una marca; si no, la del proyecto
    marca = next((x.strip().upper() for x in lineas[0] if x and x.strip().upper() in MARCAS), textos(d)[0][0])
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
            guardar_img(f, c)
            if mejorar.imagen(f):
                c = leer_img(f)
            os.remove(f)
        salida = os.path.join(d, f'miniatura_{k}.jpg')
        l = lineas[(k - 1) % len(lineas)]
        componer(c, tel, [x for x in l if x], col, salida)
        hechas.append({'archivo': os.path.basename(salida), 'de': nombre, 'segundo': round(s, 1), 'texto': [x for x in l if x],
                       'telefono': bool(tel[0]), 'escala': escala})
        print(f"· miniatura_{k}.jpg: {nombre}, cuadro de {int(s // 60)}:{int(s % 60):02d}, «{' / '.join(x for x in l if x)}»", flush=True)
    cap.release()
    if (a.gpt or a.short) and hechas:  # referencias: el cuadro del problema y el del resultado (los mismos que eligió para las suyas)
        refs = []
        cap = cv2.VideoCapture(orig)
        # el ANTES (la pantalla bloqueada, el fastboot o «Bienvenido») y el DESPUÉS en la pantalla de inicio
        nt = analizar(orig, os.path.splitext(orig)[0] + '.nitidez.npz')
        total = float(nt[0][-1]) if len(nt[0]) else 60.0
        clave = cuadros_clave(d, nt)
        print('· momentos para la miniatura: ' + ', '.join(f'{k} {int(s // 60)}:{int(s % 60):02d}' for k, s in clave.items()), flush=True)
        antes = [k for k in ('verifica', 'fastboot', 'bienvenido') if k in clave] or ['verifica']
        clave.setdefault('verifica', mejor(*nt, total * 0.02, total * 0.15))
        clave.setdefault('inicio', mejor(*nt, total * 0.975, total * 0.998))
        for k in set(antes + ['inicio']):
            cap.set(cv2.CAP_PROP_POS_MSEC, clave[k] * 1000)
            ok, c = cap.read()
            if ok:
                refs.append(os.path.join(d, f'.ref_miniatura_{k}.png'))
                guardar_img(refs[-1], cv2.resize(c, (1280, 720)))
        ref = {os.path.basename(r)[len('.ref_miniatura_'):-4]: r for r in refs}
        cap.release()
        try:
            if a.gpt and a.variantes:  # una por cada ANTES, en español, para elegir la mejor
                for k in antes:
                    for f in miniaturas_gpt(d, [ref[k], ref['inicio']], list(lineas[0]), os.path.join(d, f'miniatura_gpt_{k}'), marca,
                                            idiomas=('es',), antes_desc=NOMBRE_ANTES.get(k), calidad=a.calidad):
                        hechas.append({'archivo': f, 'de': f'gpt-image-2.5-flare · ANTES: {k}', 'segundo': round(clave[k], 1), 'texto': [x for x in lineas[0] if x]})
            elif a.gpt and a.mixta:  # GPT hace la escena y la app escribe encima (con --fondos, las dos escenas)
                for fondo in (('escritorio', 'gpt') if a.fondos else ('escritorio',)):
                    base = os.path.join(d, f'miniatura_mixta_{fondo}' if a.fondos else 'miniatura_mixta')
                    for f in miniaturas_mixtas(d, [ref[antes[0]], ref['inicio']], list(lineas[0]), base, marca,
                                               antes_desc=NOMBRE_ANTES.get(antes[0]), fondo=fondo, estilos=estilos_titulo(a), titulo_por_gpt=a.titulo_gpt,
                                               esquinas=(a.esquina_izq, a.esquina_der), base_titulo=os.path.join(d, 'miniatura_mixta')):
                        hechas.append({'archivo': f, 'de': f'mixta: escena de GPT ({fondo}) + textos de la app', 'segundo': round(clave[antes[0]], 1), 'texto': [x for x in lineas[0] if x]})
            elif a.gpt and a.fondos:  # la misma miniatura con los dos fondos, para comparar
                for fondo in ('escritorio', 'gpt'):
                    for f in miniaturas_gpt(d, [ref[antes[0]], ref['inicio']], list(lineas[0]), os.path.join(d, f'miniatura_gpt_fondo_{fondo}'),
                                            marca, idiomas=('es',), antes_desc=NOMBRE_ANTES.get(antes[0]), fondo=fondo, calidad=a.calidad):
                        hechas.append({'archivo': f, 'de': f'gpt-image-2.5-flare · fondo {fondo}', 'segundo': round(clave[antes[0]], 1), 'texto': [x for x in lineas[0] if x]})
            elif a.gpt:
                for f in miniaturas_gpt(d, [ref[antes[0]], ref['inicio']], list(lineas[0]), os.path.join(d, 'miniatura_gpt'), marca,
                                        antes_desc=NOMBRE_ANTES.get(antes[0]), calidad=a.calidad):
                    hechas.append({'archivo': f, 'de': 'gpt-image-2.5-flare', 'segundo': round(clave[antes[0]], 1), 'texto': [x for x in lineas[0] if x]})
            if a.short:  # la portada del Short: vertical, con el estilo de sus Shorts
                for f in portadas_short(d, [ref[antes[0]]], list(lineas[0]), os.path.join(d, 'portada_short'), marca):
                    hechas.append({'archivo': f, 'de': 'portada del Short (gpt-image-2.5-flare)', 'segundo': round(cands[0][1], 1), 'texto': [x for x in lineas[0] if x]})
        finally:
            for f in refs:
                os.remove(f)
    json.dump({'miniaturas': hechas}, open(os.path.join(d, 'miniatura.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Listo: {len(hechas)} miniaturas para probar en YouTube (prueba A/B).', flush=True)


if __name__ == '__main__':
    main()
