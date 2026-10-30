"""«🖼 Miniatura automática»: 3 opciones de miniatura de YouTube (1280×720) sacadas de tu video, para probarlas con la
prueba A/B de miniaturas de YouTube.

Gratis, en tu PC:
  1. Elige los cuadros más nítidos y quietos (nitidez/) donde el detector ve el teléfono grande: uno del PROBLEMA (la
     pantalla bloqueada, al comienzo), uno del RESULTADO (al final) y uno contigo con el teléfono si sales en cámara.
  2. Recorta el teléfono del fondo (GrabCut de OpenCV dentro de la caja del detector) y lo pone grande con un borde
     blanco tipo sticker; si en «🎛 Audio e imagen» activaste «✨ Mejorar imagen», el cuadro pasa antes por Real-ESRGAN.
  3. Pone el texto grande con tus colores (remotion/src/estilo.ts) y una flecha hacia el teléfono.
Deja miniatura_1.jpg, miniatura_2.jpg, miniatura_3.jpg y miniatura.json (de dónde sale cada una).

Con --gpt (gasta: 3 imágenes de gpt-image-2.5-flare en calidad alta), además, la miniatura hecha por la IA de imágenes con tus
cuadros de referencia (el problema y el resultado), en español, inglés y portugués: miniatura_gpt_es/en/pt.jpg.

Uso: python miniatura.py --proyecto . [--texto "MOTOROLA|SIN CUENTA"] [--gpt] (la | parte en dos líneas; sin texto, lo arma solo)
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
from nitidez import analizar, mejor  # noqa: E402
sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))

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


FONDOS_MINI = {  # pedido de fabian (30/10/2026): probar los dos y quedarse con el que más le guste
    'escritorio': '(1) fondo = SU escritorio real, el que se ve alrededor del teléfono en las fotos de su video, tal cual, claro y apenas desenfocado: la laptop, el cartel '
                  'negro «Frp» y la G de Google grande de 4 colores (no inventes otro fondo); ',
    'foto': '(1) fondo = el fondo REAL de sus fotos HD, tal cual, claro y apenas desenfocado (no inventes otro fondo); ',
    'gpt': '(1) fondo generado por ti, como sus miniaturas de iPhone: oscuro azul profundo con estelas de luz de neón celeste y '
           'violeta, rayos de luz y un piso que refleja; ',
}


def miniaturas_gpt(d, refs, lineas, salida_base, marca='TU CELULAR', idiomas=('es', 'en', 'pt'), antes_desc=None, fondo='escritorio', extras=()):
    """La miniatura hecha por gpt-image-2.5-flare con tus cuadros de referencia, una por idioma. Devuelve los archivos."""
    import base64, urllib.request, uuid
    k = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')).get('ias_guion', {}).get('gpt', {}).get('clave', '')
    if not k:
        raise SystemExit('ERROR: falta la clave de OpenAI (la de GPT en «🤖 Ajustes IA») para la miniatura con GPT.')
    hechas = []
    marca_logo = marca.title() if marca != 'TU CELULAR' else 'la marca del teléfono'
    # 1 y 2: tus cuadros; 3: tu mascota; después, 3 miniaturas tuyas (las de la misma marca primero)
    refs = list(refs) + ([MASCOTA] if os.path.exists(MASCOTA) else []) + list(extras) + referencias_estilo(marca, 3)
    for idioma, nombre in [x for x in (('es', 'español'), ('en', 'inglés'), ('pt', 'portugués')) if x[0] in idiomas]:
        partes = [traducir(x, idioma) for x in lineas if x]
        texto = ' / '.join(f'«{x}»' for x, _ in partes)
        traduce = any(t for _, t in partes)
        prompt = ('Miniatura de YouTube 16:9 para el canal Xiaomiunlock de fabian, técnico de celulares, IDÉNTICA a SU ESTILO. '
                  f'Imagen 1: el teléfono REAL de este video ANTES: {antes_desc or "bloqueado"}; muéstralo tal cual. Imagen 2: el mismo '
                  'teléfono ya libre, en SU pantalla de inicio con las apps, igual que en la foto (DESPUÉS). Imagen 3: SU MASCOTA (el conejo Mi con casco de soldar que dice «XIAOMIUNLOCK» y '
                  'el androide verde con herramientas): va abajo a la izquierda, chica, siempre. '
                  + (f'Imágenes 4 a {3 + len(extras)}: más fotos HD reales del mismo teléfono, para copiarlo fiel. ' if extras else '') +
                  'Las demás imágenes son miniaturas '
                  'suyas: cópiales el estilo (no su texto, ni su teléfono, ni el reloj de duración de YouTube). OBLIGATORIO, todo junto: '
                  + FONDOS_MINI.get(fondo, FONDOS_MINI['escritorio']) +
                  '(2) los dos teléfonos reales grandes, de frente, sostenidos con guante negro, la pantalla bien legible; '
                  f'(3) etiqueta inclinada roja «{ANTES_DESPUES[idioma][0]}» arriba del bloqueado y verde «{ANTES_DESPUES[idioma][1]}» '
                  'arriba del libre, letra gruesa blanca con borde; (4) flecha gruesa curva amarilla del bloqueado al libre; '
                  '(5) candado abierto con la G de Google entre los dos; '
                  f'(6) arriba a la derecha el logo de {marca_logo} en un cuadrado blanco redondeado; arriba a la izquierda una cinta '
                  'roja inclinada «NEW 2026»; (7) un sello redondo dorado «MÉTODO GARANTIZADO 2026» a la derecha; '
                  f'(8) dos píldoras blancas con ícono al costado: {(PILDORAS_PC if necesita_pc(marca) else PILDORAS)[idioma]}; '
                  '(9) abajo una franja inclinada amarilla y celeste a todo el ancho con el texto GRANDE en mayúsculas, tipografía muy '
                  f'gruesa condensada e itálica, blanco con borde negro y sombra, perfectamente escrito, en {nombre}: {texto}'
                  + (f' (tradúcelo al {nombre}, corto y natural)' if traduce else '') +
                  '. Colores saturados, mucho contraste, nada oscuro ni de ciencia ficción. Ningún otro texto, ningún logo ni persona '
                  'inventados. Todo el diseño completo dentro de la imagen 16:9, sin cortar nada en los bordes.')
        b = uuid.uuid4().hex
        cuerpo = b''
        for campo, v in {'model': 'gpt-image-2.5-flare', 'prompt': prompt, 'size': '1536x864', 'quality': 'high', 'output_format': 'png'}.items():
            cuerpo += f'--{b}\r\nContent-Disposition: form-data; name="{campo}"\r\n\r\n{v}\r\n'.encode()
        for i, r in enumerate(refs):
            cuerpo += (f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="ref{i}{os.path.splitext(r)[1]}"\r\nContent-Type: {'image/jpeg' if r.lower().endswith('.jpg') else 'image/png'}\r\n\r\n'.encode()
                       + open(r, 'rb').read() + b'\r\n')
        cuerpo += f'--{b}--\r\n'.encode()
        req = urllib.request.Request('https://api.openai.com/v1/images/edits', data=cuerpo,
                                     headers={'Authorization': 'Bearer ' + k, 'Content-Type': f'multipart/form-data; boundary={b}'})
        print(f'· la IA de imágenes hace la miniatura en {nombre}…', flush=True)
        r = pedir_imagen(req)
        img = cv2.imdecode(np.frombuffer(base64.b64decode(r['data'][0]['b64_json']), np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]
        alto = min(h, int(w * 9 / 16))  # ya viene en 16:9 (1536x864): no se corta nada
        img = cv2.resize(img[(h - alto) // 2:(h - alto) // 2 + alto], (W, H), interpolation=cv2.INTER_AREA)
        f = f'{salida_base}_{idioma}.jpg'
        cv2.imwrite(f, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
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


def imagen_gpt(prompt, refs, size='1536x864', transparente=False):
    """Un pedido a gpt-image-2.5-flare con imágenes de referencia; devuelve la imagen (BGR, o BGRA si es transparente)."""
    import base64, urllib.request, uuid
    k = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')).get('ias_guion', {}).get('gpt', {}).get('clave', '')
    if not k:
        raise SystemExit('ERROR: falta la clave de OpenAI (la de GPT en «🤖 Ajustes IA») para la miniatura con GPT.')
    b = uuid.uuid4().hex
    cuerpo = b''
    campos = {'model': 'gpt-image-2.5-flare', 'prompt': prompt, 'size': size, 'quality': 'high', 'output_format': 'png'}
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
    cv2.imwrite(salida, img)
    return salida


# las etiquetas de arriba (NEW 2026, ANTES, DESPUÉS, BEFORE…) dibujadas por GPT 2.5 una sola vez y guardadas para todos
# los videos (fabian, 30/10/2026: las que dibuja la app se ven genéricas)
ETIQUETAS_DIR = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'etiquetas')
COLORES_ETIQUETA = {'rojo': ((226, 30, 36), 'roja (rojo vivo arriba, rojo oscuro abajo)'),
                    'verde': ((34, 168, 64), 'verde (verde vivo arriba, verde oscuro abajo)'),
                    'azul': ((24, 104, 235), 'azul eléctrico (celeste arriba, azul oscuro abajo)')}


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
    cv2.imwrite(f, img)
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


def miniaturas_mixtas(d, refs, lineas, salida_base, marca='TU CELULAR', idiomas=('es', 'en', 'pt'), antes_desc=None, fondo='escritorio', extras=(), estilos=('placa',), titulo_por_gpt=False, escena=None, esquinas=('NEW 2026', '')):
    """Una escena de GPT sin texto y, encima, lo escrito por la app en cada idioma. Devuelve los archivos."""
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
        cv2.imwrite(f'{salida_base}_escena.png', escena)
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
                png = f'{salida_base}_titulo_{estilo}_{idioma}.png'
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
                  f'; al lado del título el logo de {marca_logo} en un cuadrado; ABAJO una franja azul con «{PROMESA[idioma]}» y '
                  + pildora +
                  'Letras grandes que se lean en el celular. Ningún otro texto, ningún logo ni persona inventados. Todo completo '
                  'dentro de la imagen vertical, sin cortar nada.')
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
        cv2.imwrite(f, cv2.resize(img, (1080, 1920), interpolation=cv2.INTER_CUBIC), [cv2.IMWRITE_JPEG_QUALITY, 92])
        hechas.append(os.path.basename(f))
        print(f'· {os.path.basename(f)} lista', flush=True)
    return hechas


FOTOS = ('antes', 'despues', 'extra1', 'extra2')  # las fotos HD que subes en «🖼 Miniatura» (foto_miniatura_*.jpg)


def estilos_titulo(a):
    return ('placa', 'metal') if a.titulo == 'todos' else (a.titulo,)  # los dos que eligió fabian (30/10/2026)


def con_fotos(d, a):
    """El módulo «🖼 Miniatura» (pedido de fabian, 30/10/2026): tus fotos HD en vez de los cuadros del video; GPT y la app
    ponen fondo, textos, sello, píldoras y logo."""
    fotos = {k: os.path.join(d, f'foto_miniatura_{k}.jpg') for k in FOTOS if os.path.exists(os.path.join(d, f'foto_miniatura_{k}.jpg'))}
    if 'antes' not in fotos:
        raise SystemExit('ERROR: falta la foto del ANTES (el teléfono bloqueado). Súbela en «🖼 Miniatura».')
    if not a.gpt:
        raise SystemExit('ERROR: la miniatura con tus fotos la hace GPT: escribe SI para confirmar el gasto.')
    temporal = None
    if 'despues' not in fotos:  # sin foto del DESPUÉS: la pantalla de inicio del final de tu video
        orig = os.path.join(d, 'original.mp4')
        if not os.path.exists(orig):
            raise SystemExit('ERROR: falta la foto del DESPUÉS (el teléfono ya libre). Súbela en «🖼 Miniatura».')
        nt = analizar(orig, os.path.splitext(orig)[0] + '.nitidez.npz')
        total = float(nt[0][-1]) if len(nt[0]) else 60.0
        s = cuadros_clave(d, nt).get('inicio') or mejor(*nt, total * 0.975, total * 0.998)
        cap = cv2.VideoCapture(orig)
        cap.set(cv2.CAP_PROP_POS_MSEC, s * 1000)
        ok, c = cap.read()
        cap.release()
        if not ok:
            raise SystemExit('ERROR: falta la foto del DESPUÉS (el teléfono ya libre). Súbela en «🖼 Miniatura».')
        temporal = fotos['despues'] = os.path.join(d, '.ref_miniatura_inicio.png')
        cv2.imwrite(temporal, c)
        print(f'· sin foto del DESPUÉS: uso tu video en {int(s // 60)}:{int(s % 60):02d}', flush=True)
    lineas = list(a.texto.split('|')[:2]) if a.texto else list(textos(d)[0])
    extras = [fotos[k] for k in FOTOS[2:] if k in fotos]
    marca = next((x.strip().upper() for x in lineas if x.strip().upper() in MARCAS), textos(d)[0][0])  # para el logo oficial
    hechas = []
    try:
        for fondo in (('foto', 'gpt') if a.fondo == 'ambos' else (a.fondo,)):
            hacer = (lambda *x, **k: miniaturas_mixtas(*x, estilos=estilos_titulo(a), titulo_por_gpt=a.titulo_gpt,
                                                      esquinas=(a.esquina_izq, a.esquina_der), **k)) if a.mixta else miniaturas_gpt
            base = os.path.join(d, f"miniatura_fotos_{'mixta' if a.mixta else 'gpt'}_{fondo}")
            for f in hacer(d, [fotos['antes'], fotos['despues']], lineas, base, marca, antes_desc='tal como está en la foto HD',
                           fondo=fondo, extras=extras):
                hechas.append({'archivo': f, 'de': f"tus fotos · {'mixta' if a.mixta else 'todo GPT'} · fondo {'de tus fotos' if fondo == 'foto' else 'de GPT'}",
                               'texto': [x for x in lineas if x]})
    finally:
        if temporal:
            os.remove(temporal)
    json.dump({'miniaturas': hechas}, open(os.path.join(d, 'miniatura_fotos.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Listo: {len(hechas)} miniaturas con tus fotos.', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--texto', help='las dos líneas separadas por |, para las 3 opciones')
    ap.add_argument('--gpt', action='store_true', help='además, la miniatura de gpt-image-2.5-flare en 3 idiomas (gasta)')
    ap.add_argument('--fotos', action='store_true', help='con --gpt: usa tus fotos HD (foto_miniatura_*.jpg) en vez de los cuadros del video')
    ap.add_argument('--fondo', choices=('foto', 'gpt', 'ambos'), default='foto', help='con --fotos: el fondo de tus fotos, uno de GPT o los dos')
    ap.add_argument('--titulo', choices=('placa', 'pincel', 'metal', 'todos'), default='todos', help='con --mixta: el estilo del título (todos = los dos que le gustan a fabian: placa y metal)')
    ap.add_argument('--titulo-gpt', action='store_true', help='con --mixta: el título lo dibuja GPT 2.5 con tu estilo (1 imagen por estilo e idioma)')
    ap.add_argument('--esquina-izq', default='NEW 2026', help='con --mixta: texto corto arriba a la izquierda (vacío = nada)')
    ap.add_argument('--esquina-der', default='', help='con --mixta: texto corto arriba a la derecha (el logo baja un poco)')
    ap.add_argument('--mixta', action='store_true', help='con --gpt: GPT hace solo la escena y la app pone textos y logos (1 imagen para los 3 idiomas)')
    ap.add_argument('--fondos', action='store_true', help='con --gpt: dos miniaturas en español, una con tu escritorio real de fondo y otra con fondo de GPT')
    ap.add_argument('--variantes', action='store_true', help='con --gpt: una miniatura por cada ANTES (bloqueada, fastboot, Bienvenido), en español')
    ap.add_argument('--short', action='store_true', help='además, la portada vertical del Short con gpt-image-2.5-flare en 3 idiomas (gasta)')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    if a.fotos:
        return con_fotos(d, a)
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
                cv2.imwrite(refs[-1], cv2.resize(c, (1280, 720)))
        ref = {os.path.basename(r)[len('.ref_miniatura_'):-4]: r for r in refs}
        cap.release()
        try:
            if a.gpt and a.variantes:  # una por cada ANTES, en español, para elegir la mejor
                for k in antes:
                    for f in miniaturas_gpt(d, [ref[k], ref['inicio']], list(lineas[0]), os.path.join(d, f'miniatura_gpt_{k}'), lineas[0][0],
                                            idiomas=('es',), antes_desc=NOMBRE_ANTES.get(k)):
                        hechas.append({'archivo': f, 'de': f'gpt-image-2.5-flare · ANTES: {k}', 'segundo': round(clave[k], 1), 'texto': [x for x in lineas[0] if x]})
            elif a.gpt and a.mixta:  # GPT hace la escena y la app escribe encima (con --fondos, las dos escenas)
                for fondo in (('escritorio', 'gpt') if a.fondos else ('escritorio',)):
                    base = os.path.join(d, f'miniatura_mixta_{fondo}' if a.fondos else 'miniatura_mixta')
                    for f in miniaturas_mixtas(d, [ref[antes[0]], ref['inicio']], list(lineas[0]), base, lineas[0][0],
                                               antes_desc=NOMBRE_ANTES.get(antes[0]), fondo=fondo, estilos=estilos_titulo(a), titulo_por_gpt=a.titulo_gpt,
                                               esquinas=(a.esquina_izq, a.esquina_der)):
                        hechas.append({'archivo': f, 'de': f'mixta: escena de GPT ({fondo}) + textos de la app', 'segundo': round(clave[antes[0]], 1), 'texto': [x for x in lineas[0] if x]})
            elif a.gpt and a.fondos:  # la misma miniatura con los dos fondos, para comparar
                for fondo in ('escritorio', 'gpt'):
                    for f in miniaturas_gpt(d, [ref[antes[0]], ref['inicio']], list(lineas[0]), os.path.join(d, f'miniatura_gpt_fondo_{fondo}'),
                                            lineas[0][0], idiomas=('es',), antes_desc=NOMBRE_ANTES.get(antes[0]), fondo=fondo):
                        hechas.append({'archivo': f, 'de': f'gpt-image-2.5-flare · fondo {fondo}', 'segundo': round(clave[antes[0]], 1), 'texto': [x for x in lineas[0] if x]})
            elif a.gpt:
                for f in miniaturas_gpt(d, [ref[antes[0]], ref['inicio']], list(lineas[0]), os.path.join(d, 'miniatura_gpt'), lineas[0][0],
                                        antes_desc=NOMBRE_ANTES.get(antes[0])):
                    hechas.append({'archivo': f, 'de': 'gpt-image-2.5-flare', 'segundo': round(clave[antes[0]], 1), 'texto': [x for x in lineas[0] if x]})
            if a.short:  # la portada del Short: vertical, con el estilo de sus Shorts
                for f in portadas_short(d, [ref[antes[0]]], list(lineas[0]), os.path.join(d, 'portada_short'), lineas[0][0]):
                    hechas.append({'archivo': f, 'de': 'portada del Short (gpt-image-2.5-flare)', 'segundo': round(cands[0][1], 1), 'texto': [x for x in lineas[0] if x]})
        finally:
            for f in refs:
                os.remove(f)
    json.dump({'miniaturas': hechas}, open(os.path.join(d, 'miniatura.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Listo: {len(hechas)} miniaturas para probar en YouTube (prueba A/B).', flush=True)


if __name__ == '__main__':
    main()
