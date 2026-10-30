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
    'escritorio': '(1) fondo = SU escritorio real, el de la imagen 1, tal cual, claro y apenas desenfocado: la laptop, el cartel '
                  'negro «Frp» y la G de Google grande de 4 colores (no inventes otro fondo); ',
    'gpt': '(1) fondo generado por ti, como sus miniaturas de iPhone: oscuro azul profundo con estelas de luz de neón celeste y '
           'violeta, rayos de luz y un piso que refleja; ',
}


def miniaturas_gpt(d, refs, lineas, salida_base, marca='TU CELULAR', idiomas=('es', 'en', 'pt'), antes_desc=None, fondo='escritorio'):
    """La miniatura hecha por gpt-image-2.5-flare con tus cuadros de referencia, una por idioma. Devuelve los archivos."""
    import base64, urllib.request, uuid
    k = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')).get('ias_guion', {}).get('gpt', {}).get('clave', '')
    if not k:
        raise SystemExit('ERROR: falta la clave de OpenAI (la de GPT en «🤖 Ajustes IA») para la miniatura con GPT.')
    hechas = []
    marca_logo = marca.title() if marca != 'TU CELULAR' else 'la marca del teléfono'
    # 1 y 2: tus cuadros; 3: tu mascota; después, 3 miniaturas tuyas (las de la misma marca primero)
    refs = list(refs) + ([MASCOTA] if os.path.exists(MASCOTA) else []) + referencias_estilo(marca, 3)
    for idioma, nombre in [x for x in (('es', 'español'), ('en', 'inglés'), ('pt', 'portugués')) if x[0] in idiomas]:
        partes = [traducir(x, idioma) for x in lineas if x]
        texto = ' / '.join(f'«{x}»' for x, _ in partes)
        traduce = any(t for _, t in partes)
        prompt = ('Miniatura de YouTube 16:9 para el canal Xiaomiunlock de fabian, técnico de celulares, IDÉNTICA a SU ESTILO. '
                  f'Imagen 1: el teléfono REAL de este video ANTES: {antes_desc or "bloqueado"}; muéstralo tal cual. Imagen 2: el mismo '
                  'teléfono ya libre, en SU pantalla de inicio con las apps, igual que en la foto (DESPUÉS). Imagen 3: SU MASCOTA (el conejo Mi con casco de soldar que dice «XIAOMIUNLOCK» y '
                  'el androide verde con herramientas): va abajo a la izquierda, chica, siempre. Las demás imágenes son miniaturas '
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--texto', help='las dos líneas separadas por |, para las 3 opciones')
    ap.add_argument('--gpt', action='store_true', help='además, la miniatura de gpt-image-2.5-flare en 3 idiomas (gasta)')
    ap.add_argument('--fondos', action='store_true', help='con --gpt: dos miniaturas en español, una con tu escritorio real de fondo y otra con fondo de GPT')
    ap.add_argument('--variantes', action='store_true', help='con --gpt: una miniatura por cada ANTES (bloqueada, fastboot, Bienvenido), en español')
    ap.add_argument('--short', action='store_true', help='además, la portada vertical del Short con gpt-image-2.5-flare en 3 idiomas (gasta)')
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
