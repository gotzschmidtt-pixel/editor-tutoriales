"""Las miniaturas de TU canal como referencia de estilo para GPT (pedido de fabian, 03/11/2026: «las que estás haciendo no se
parecen nada a las mías de mi canal que últimamente he generado»).

Gratis, sin IA: baja y guarda en tu PC las miniaturas más recientes y las más vistas de tu canal (i.ytimg.com es público) en
mis_conocimientos/miniaturas/canal_referencia/ (esa carpeta no va a este repo), con indice.json: título, vistas, fecha, marca
y servicio de cada una, y las que fijaste o quitaste. La lista de videos sale de:
  1. tu canal con el permiso de YouTube de la app (▶️ YouTube → Conectar), si está conectado;
  2. si no, la página pública del canal (los ~30 videos más nuevos, con sus vistas) junto con lo último que bajó
     «📊 Aprender de todo tu canal» (mis_conocimientos/youtube_canal/videos.json), para los más viejos.
Al pedir una miniatura, elegir() da 2-3, las más parecidas al video (misma marca o servicio) y, entre parecidas, las de más
vistas por día; las que fijaste (📌 en «🖼 Miniatura») van primero y las que quitaste (🚫) nunca. Desde el 03/11/2026 (fabian:
«mira la primera imagen, fondos negros») las de fondo claro no van a GPT, salvo que las fijes. GPT las usa SOLO de estilo:
nunca copia sus textos ni sus teléfonos.

Con el export del canal (youtube_datos/AAAA-MM-DD, sin internet), --referencias arma mis_conocimientos/miniaturas/referencias/:
las miniaturas de tus videos largos de fondo oscuro con más vistas por día, por marca, con su indice.json (las lee
miniatura.referencias_estilo cuando no hay miniaturas del canal guardadas). Esas del export son chicas (320×180): --bajar
también trae su versión HD a canal_referencia/ y no la borra (revisión, 03/11/2026).

Uso: python miniatura/canal_referencia.py --bajar [--recientes 18] [--vistas 12]   (imprime una línea JSON)
     python miniatura/canal_referencia.py --elegir "HONOR|SIN CUENTA GOOGLE"
     python miniatura/canal_referencia.py --referencias mis_conocimientos/youtube_datos/2026-11-03
"""
import argparse, json, math, os, re, shutil, sys, time, unicodedata, urllib.error, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'canal_referencia')
VIDEOS_CANAL = os.path.join(RAIZ, 'mis_conocimientos', 'youtube_canal', 'videos.json')  # el de «📊 Aprender de todo tu canal»
CANAL = 'https://www.youtube.com/@Xiaomiunlock/videos'
IMAGEN = 'https://i.ytimg.com/vi/{id}/{nombre}'
# de la más grande a la más chica: no todos los videos tienen maxresdefault (YouTube da 404) y las 4:3 traen franjas negras
TAMANOS = ('maxresdefault.jpg', 'hq720.jpg', 'sddefault.jpg', 'hqdefault.jpg')
CABECERAS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36',
             'Accept-Language': 'es-419,es;q=0.9'}
RECIENTES, MAS_VISTAS, USAR = 18, 12, 3
SHORT_MAX = 180  # segundos: hasta aquí es un Short (tienen otra portada, no sirven de referencia)
ID = re.compile(r'[\w-]{11}')
MARCAS = {'HONOR': r'\bhonor\b|magic ?os', 'XIAOMI': r'\bxiaomi\b(?!\s*unlock)|redmi|\bpoco\b|hyper ?os|\bmiui\b',
          'SAMSUNG': r'samsung|galaxy', 'IPHONE': r'iphone|icloud|\bios\b|\bipad\b|\bapple\b', 'MOTOROLA': r'\bmoto(rola)?\b',
          'HUAWEI': r'huawei'}
SERVICIOS = {'frp': r'\bfrp\b|cuenta (de )?google|quitar google|\bgoogle\b',
             'icloud': r'icloud|bypass|\bhello\b|passcode|activaci|no disponible',
             'patron': r'patron|contrasena|formatear|hard ?reset|\bpin\b',
             'mdm': r'\bmdm\b', 'imei': r'\bimei\b|t-?mobile',
             'herramienta': r'unlock ?tool|frp ?file|raspberry|\bpico\b'}
# (fabian, 03/11/2026: «mira la primera imagen, fondos negros») qué tan claro puede ser el FONDO de una miniatura para ir a GPT:
# la mediana de luz (0-255) del marco de afuera. Medido en sus 185 miniaturas de videos largos: las negras/azul noche dan
# 20-59 (Bypass Hello 23, ELIM. CUENTA HONOR 24) y las de estudio claro o fondo blanco 100-200 (Honor 8 Lite 181)
LUZ_MAX = 60
DIAS_MIN = 7  # vistas por día: un video de ayer cuenta como de 7 días (si no, 300 vistas en 1 día le ganan a todas)
REFERENCIAS = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'referencias')
PARECIDA = 15  # diferencia media (0-255) a 32×18 por debajo de la cual dos miniaturas son la misma (p. ej. en otro idioma)
VACIAS = set('de la el en y a con sin para por tu tus un una los las del al que o mi se es como ya no lo le su todo todos '
             'metodo nuevo nueva 2024 2025 2026 2027'.split())


def normal(t):
    """minúsculas, sin tildes ni ñ, para comparar títulos."""
    return ''.join(c for c in unicodedata.normalize('NFKD', str(t or '').lower()) if not unicodedata.combining(c))


def etiquetar(titulo):
    """(marca, [servicios]) de un título: «Quitar Cuenta Google Honor…» → ('HONOR', ['frp'])."""
    t = normal(titulo)
    marca = next((m for m, rx in MARCAS.items() if re.search(rx, t)), '')
    return marca, sorted(s for s, rx in SERVICIOS.items() if re.search(rx, t))


def palabras(t):
    return {p for p in re.findall(r'[a-z0-9]+', normal(t)) if len(p) >= 3 and p not in VACIAS}


def _gris(ruta, tam, modo=None):
    """La imagen achicada a tam (en gris, o en color con modo=cv2.IMREAD_COLOR); None si no se puede leer."""
    import cv2
    import numpy as np
    try:
        img = cv2.imdecode(np.fromfile(ruta, np.uint8), cv2.IMREAD_GRAYSCALE if modo is None else modo)  # fromfile: con tildes
    except (OSError, ValueError):
        return None
    return None if img is None else cv2.resize(img, tam, interpolation=cv2.INTER_AREA)


def luz(ruta):
    """Qué tan claro es el FONDO de una miniatura (03/11/2026): la mediana de luz (0-255) del marco de afuera, a 320×180. El
    centro, donde va el teléfono con su pantalla clara, no cuenta. None si no se puede leer."""
    import numpy as np
    g = _gris(ruta, (320, 180))
    if g is None:
        return None
    marco = np.ones(g.shape, bool)
    marco[30:150, 50:270] = False
    return round(float(np.median(g[marco])), 1)


_LUCES = {}  # (archivo, fecha) → luz: la página pregunta cuáles van a cada rato mientras escribes el título


def oscura(v):
    """True si el fondo de esa miniatura es oscuro (negro o azul noche), como las que fabian pidió copiar. Las bajadas antes
    del 03/11/2026 no traen la luz anotada: se mide una vez."""
    l = v.get('luz')
    if l is None:
        f = v.get('ruta') or os.path.join(CARPETA, v.get('archivo') or f"{v.get('id')}.jpg")
        try:
            clave = (f, os.path.getmtime(f))
        except OSError:
            return False
        if clave not in _LUCES:
            _LUCES[clave] = luz(f)
        l = _LUCES[clave]
    return l is not None and float(l) <= LUZ_MAX


def vistas_dia(v, hoy=None):
    """Las vistas por día desde que se publicó (como mínimo DIAS_MIN días; sin fecha, se cuenta un año)."""
    try:
        t = time.mktime(time.strptime(str(v.get('publicado') or '')[:10], '%Y-%m-%d'))
        dias = max(DIAS_MIN, ((hoy or time.time()) - t) / 86400)
    except (ValueError, OverflowError):
        dias = 365
    return int(v.get('vistas') or 0) / dias


# ---------------------------------------------------------------- la lista de videos del canal

def _numero(txt):
    """«17.234 visualizaciones», «2,8 mil», «2,8 K», «1,2 M» → 17234, 2800, 2800, 1200000 (0 si no hay número)."""
    t = normal(txt).replace('\xa0', ' ')
    m = re.search(r'(\d[\d.,]*)\s*(mil\b|k\b|m\b|mill)?', t)
    if not m:
        return 0
    n, mult = m.group(1).rstrip('.,'), {'mil': 1e3, 'k': 1e3, 'm': 1e6, 'mill': 1e6}.get(m.group(2) or '', 1)
    if mult == 1:
        return int(re.sub(r'[.,]', '', n) or 0)
    return int(float(n.replace('.', '').replace(',', '.') if ',' in n else n) * mult)


def _hace(txt):
    """«hace 5 días» → la fecha (AAAA-MM-DD) aproximada; '' si no se entiende."""
    m = re.search(r'(\d+)\s*(min|sem|mes|an|h|s|d|m|a)', normal(txt))  # las largas primero: «2 semanas» no es «2 s»
    if not m:
        return ''
    dias = int(m.group(1)) * {'min': 0, 'sem': 7, 'mes': 30, 'an': 365, 'h': 0, 's': 0, 'd': 1, 'm': 30, 'a': 365}[m.group(2)]
    return time.strftime('%Y-%m-%d', time.localtime(time.time() - dias * 86400))


def _segundos(txt):
    try:
        return sum(int(x) * 60 ** i for i, x in enumerate(reversed(str(txt).strip().split(':'))))
    except ValueError:
        return 0


def leer_pagina(html):
    """Los videos de la página pública del canal (ytInitialData), del más nuevo al más viejo: [{id, titulo, vistas, publicado,
    segundos}]. Sirve con el diseño nuevo de YouTube (lockupViewModel) y el viejo (videoRenderer)."""
    m = re.search(r'var ytInitialData\s*=\s*(\{.*?\});\s*</script>', html or '', re.S)
    if not m:
        return []
    try:
        datos = json.loads(m.group(1))
    except ValueError:
        return []
    out, vistos = [], set()

    def texto(x):
        if isinstance(x, dict):
            return x.get('content') or x.get('simpleText') or ''.join(r.get('text', '') for r in x.get('runs') or [])
        return str(x or '')

    def andar(x):
        if isinstance(x, list):
            for v in x:
                andar(v)
            return
        if not isinstance(x, dict):
            return
        v = None
        if isinstance(x.get('lockupViewModel'), dict) and 'VIDEO' in str(x['lockupViewModel'].get('contentType', 'VIDEO')):
            lv = x['lockupViewModel']
            md = (lv.get('metadata') or {}).get('lockupMetadataViewModel') or {}
            filas = (((md.get('metadata') or {}).get('contentMetadataViewModel') or {}).get('metadataRows') or [{}])
            partes = filas[0].get('metadataParts') or []
            insignias = [texto((b.get('thumbnailBadgeViewModel') or {}).get('text')) for o in
                         ((lv.get('contentImage') or {}).get('thumbnailViewModel') or {}).get('overlays') or []
                         for b in (o.get('thumbnailBottomOverlayViewModel') or {}).get('badges') or []]
            v = {'id': lv.get('contentId'), 'titulo': texto(md.get('title')),
                 'vistas': _numero(partes[0].get('accessibilityLabel') or texto(partes[0].get('text'))) if partes else 0,
                 'publicado': _hace(partes[1].get('accessibilityLabel') or texto(partes[1].get('text'))) if len(partes) > 1 else '',
                 'segundos': _segundos(insignias[0]) if insignias else 0}
        elif isinstance(x.get('videoRenderer'), dict):
            vr = x['videoRenderer']
            v = {'id': vr.get('videoId'), 'titulo': texto(vr.get('title')), 'vistas': _numero(texto(vr.get('viewCountText'))),
                 'publicado': _hace(texto(vr.get('publishedTimeText'))), 'segundos': _segundos(texto(vr.get('lengthText')))}
        if v and ID.fullmatch(str(v['id'] or '')) and v['id'] not in vistos:
            vistos.add(v['id'])
            out.append(v)
            return
        for y in x.values():
            andar(y)
    andar(datos)
    return out


def _de_oauth():
    """Con el permiso de YouTube de la app: todos los videos públicos con vistas, fecha y duración (cuota mínima)."""
    sys.path.insert(0, os.path.join(RAIZ, 'youtube'))
    try:
        import canal as yt_canal
        import youtube
        c = youtube.config(json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')))
        if not (c.get('token') or {}).get('refresh'):
            return None
        return list(yt_canal._videos(c, lambda *_: None).values())
    except Exception as e:  # sin permiso, sin internet o con la cuota llena: se sigue con lo que haya
        print(f'· no pude leer tu canal con el permiso de YouTube ({e}); sigo con lo guardado o la página pública', flush=True)
        return None


def _de_guardado():
    try:
        datos = json.load(open(VIDEOS_CANAL, encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return [v for v in (datos.values() if isinstance(datos, dict) else datos) if isinstance(v, dict) and v.get('id')] or None


def _de_pagina(abrir):
    try:
        html = abrir(urllib.request.Request(CANAL, headers=CABECERAS), timeout=25).read().decode('utf-8', 'replace')
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f'· no pude abrir la página de tu canal ({e})', flush=True)
        return None
    return leer_pagina(html) or None


def lista_videos(abrir=None):
    """(videos, de dónde salió la lista). Primero tu canal con OAuth; si no está conectado, la página pública (los ~30 más
    nuevos) junto con lo guardado (los más viejos y sus vistas)."""
    vs = _de_oauth()
    if vs:
        return vs, 'YouTube conectado'
    # (revisión, 03/11/2026) lo guardado puede tener semanas (el permiso de prueba vence cada 7 días y con él se dejan de
    # bajar las estadísticas): sin la página pública faltaban justo las miniaturas más nuevas, las que fabian pidió copiar
    pagina, guardado = _de_pagina(abrir or urllib.request.urlopen) or [], _de_guardado() or []
    ids = {v.get('id') for v in pagina}
    vs = pagina + [v for v in guardado if v.get('id') not in ids]
    fuente = ' + '.join(x for x, hay in (('página pública del canal', pagina), ('estadísticas guardadas del canal', guardado)) if hay)
    return vs, fuente


# ---------------------------------------------------------------- bajar las miniaturas (gratis)

def leer_indice():
    try:
        ind = json.load(open(os.path.join(CARPETA, 'indice.json'), encoding='utf-8'))
        return ind if isinstance(ind, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar_indice(ind):
    os.makedirs(CARPETA, exist_ok=True)
    f = os.path.join(CARPETA, 'indice.json')
    json.dump(ind, open(f + '.nuevo', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(f + '.nuevo', f)


def bajar_imagen(vid, destino, abrir):
    """La miniatura más grande que tenga ese video, en 16:9 (sin las franjas negras de las 4:3). True si quedó guardada."""
    import cv2
    import numpy as np
    for nombre in TAMANOS:
        try:
            datos = abrir(urllib.request.Request(IMAGEN.format(id=vid, nombre=nombre), headers=CABECERAS), timeout=25).read()
        except (urllib.error.URLError, OSError, ValueError):
            continue
        img = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
        if img is None or img.shape[0] < 150:  # la imagen gris de «no hay» de YouTube es de 120×90
            continue
        h, w = img.shape[:2]
        if w / h < 1.6:
            alto = int(w * 9 / 16)
            img = img[(h - alto) // 2:(h - alto) // 2 + alto]
        if img.shape[1] > 1280:
            img = cv2.resize(img, (1280, 720), interpolation=cv2.INTER_AREA)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(destino)  # tofile: sirve con tildes en la ruta
        return True
    return False


def bajar(recientes=RECIENTES, vistas=MAS_VISTAS, abrir=None, listar=None, avisar=print):
    """Baja (o actualiza) las miniaturas más recientes y las más vistas del último año de tu canal y, en HD, las de tu carpeta
    de referencias (referencias/indice.json). No gasta nada."""
    abrir = abrir or urllib.request.urlopen
    videos, fuente = listar() if listar else lista_videos(abrir)
    if not videos:
        raise ValueError('No pude leer la lista de videos de tu canal: conecta YouTube (▶️ YouTube → 🔑 Conectar) o revisa tu internet.')
    largos = []
    for k, v in enumerate(videos):
        if ID.fullmatch(str(v.get('id') or '')) and not 0 < int(v.get('segundos') or 0) <= SHORT_MAX:
            largos.append(dict(v, orden=k))
    # del más nuevo al más viejo (sin fecha, en el orden en que vienen: así los lista YouTube)
    nuevos = sorted(largos, key=lambda v: str(v.get('publicado') or ''), reverse=True)[:recientes]
    hace_un_anio = time.strftime('%Y-%m-%d', time.localtime(time.time() - 365 * 86400))
    del_anio = [v for v in largos if str(v.get('publicado') or '') >= hace_un_anio] or largos
    top = sorted(del_anio, key=lambda v: -int(v.get('vistas') or 0))[:vistas]
    viejo = leer_indice()
    fijadas, quitadas = list(viejo.get('fijadas') or []), list(viejo.get('quitadas') or [])
    antes = {v['id']: v for v in viejo.get('videos') or [] if isinstance(v, dict) and v.get('id')}
    ids_top = {v['id'] for v in top}
    elegidos = {}
    for v in nuevos + top:
        elegidos.setdefault(v['id'], v)
    for i in fijadas:  # las que fijaste se quedan aunque ya no estén entre las recientes ni las más vistas
        if i not in elegidos and i in antes:
            elegidos[i] = antes[i]
    # (revisión, 03/11/2026) las de referencias/indice.json (tus oscuras con más vistas por día) también se bajan en HD y no se
    # borran: si no, a GPT iban en 320×180 (las del export), donde casi no se ve el tipo de letra
    por_id = {v['id']: v for v in largos}
    for i, v in de_referencias().items():
        if i not in elegidos:
            elegidos[i] = por_id.get(i) or antes.get(i) or v
    lista, bien, mal = [], 0, 0
    for i, v in elegidos.items():
        f = os.path.join(CARPETA, f'{i}.jpg')
        if bajar_imagen(i, f, abrir):
            bien += 1
        else:
            mal += 1
            if not os.path.isfile(f):
                continue
        marca, servicios = etiquetar(v.get('titulo'))
        lista.append({'id': i, 'titulo': str(v.get('titulo') or ''), 'vistas': int(v.get('vistas') or 0),
                      'publicado': str(v.get('publicado') or ''), 'archivo': f'{i}.jpg', 'marca': marca, 'servicios': servicios,
                      'reciente': any(x['id'] == i for x in nuevos), 'mas_vista': i in ids_top, 'luz': luz(f)})
        avisar(f'· {i}: {lista[-1]["titulo"][:60]}')
    for i in antes:  # las de antes que ya no se usan se borran (las fijadas no)
        if i not in elegidos and i not in fijadas and os.path.isfile(os.path.join(CARPETA, f'{i}.jpg')):
            os.remove(os.path.join(CARPETA, f'{i}.jpg'))
    guardar_indice({'fecha': time.strftime('%Y-%m-%d %H:%M'), 'fuente': fuente, 'videos': lista, 'fijadas': fijadas,
                    'quitadas': quitadas})
    return {'ok': True, 'fuente': fuente, 'bajadas': bien, 'fallaron': mal, 'total': len(lista), 'carpeta': CARPETA}


# ---------------------------------------------------------------- cuáles van a GPT

def contexto(d=None, texto=''):
    """(marca, texto) del video: la marca del título que escribiste; si no la nombra, la del nombre del proyecto o su idea.txt."""
    extra = ''
    if d:
        try:
            extra = os.path.basename(os.path.abspath(d)) + ' ' + open(os.path.join(d, 'idea.txt'), encoding='utf-8').read()[:600]
        except OSError:
            extra = os.path.basename(os.path.abspath(d))
    marca = etiquetar(texto)[0] or etiquetar(extra)[0]
    return marca, f'{texto} {extra}'.strip()


def elegir(marca='', texto='', n=USAR, indice=None):
    """Las 2-3 miniaturas de tu canal que van a GPT como referencia de ESTILO: primero las que fijaste (📌); después las más
    parecidas a este video (misma marca, mismo servicio, palabras del título en común) y, entre parecidas, las de más vistas
    por día. Solo las de fondo oscuro (fabian, 03/11/2026: «fondos negros»), salvo las fijadas. Nunca dos casi iguales (la
    serie de «Bypass Hello» tiene varias). Devuelve los videos del índice con su 'ruta'."""
    ind = indice if indice is not None else leer_indice()
    quitadas = set(ind.get('quitadas') or [])
    fijadas = [i for i in ind.get('fijadas') or [] if i not in quitadas]
    vs = [dict(v, ruta=os.path.join(CARPETA, v.get('archivo') or f"{v.get('id')}.jpg")) for v in ind.get('videos') or []
          if isinstance(v, dict) and v.get('id') not in quitadas]
    vs = [v for v in vs if os.path.isfile(v['ruta']) and (v['id'] in fijadas or oscura(v))]
    marca = 'IPHONE' if str(marca or '').upper() == 'APPLE' else str(marca or '').upper()
    marca = marca if marca in MARCAS else (etiquetar(texto)[0] or '')
    servicios, pal = set(etiquetar(texto)[1]), palabras(texto)

    def puntaje(v):
        p = 4.0 if marca and v.get('marca') == marca else 0.0
        p += 2.0 * len(servicios & set(v.get('servicios') or []))
        p += min(2.0, 0.5 * len(pal & palabras(v.get('titulo'))))
        p += 0.6 * math.log10(1 + vistas_dia(v)) + (0.5 if v.get('reciente') else 0)  # vistas por día (03/11/2026)
        return p
    orden = sorted((v for v in vs if v['id'] in fijadas), key=lambda v: fijadas.index(v['id'])) + \
        sorted((v for v in vs if v['id'] not in fijadas), key=puntaje, reverse=True)
    out = []
    for v in orden:
        if len(out) >= n:
            break
        p = palabras(v.get('titulo'))
        casi_igual = any(len(p & palabras(o.get('titulo'))) / max(1, len(p | palabras(o.get('titulo')))) > 0.6 for o in out)
        if v['id'] in fijadas or not casi_igual:
            out.append(v)
    for v in orden:  # si las casi iguales eran las únicas, igual se completan
        if len(out) >= min(n, 2) or v in out:
            continue
        out.append(v)
    return out


def de_referencias(carpeta=None):
    """{id: fila} de mis_conocimientos/miniaturas/referencias/indice.json (el que arma --referencias), sin las quitadas."""
    try:
        ind = json.load(open(os.path.join(carpeta or REFERENCIAS, 'indice.json'), encoding='utf-8'))
        quitadas = set(ind.get('quitadas') or {})
        return {str(v['id']): v for v in ind.get('miniaturas') or [] if isinstance(v, dict) and ID.fullmatch(str(v.get('id') or ''))
                and v.get('archivo') and v['id'] not in quitadas}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def por_ids(ids, referencias=None):
    """Las mismas referencias de un borrador (para hacer su final con el mismo estilo), si siguen guardadas: las del canal y
    (revisión, 03/11/2026) las de la carpeta de referencias que completaron el borrador (la HD si está bajada)."""
    ind = leer_indice()
    vs = {v.get('id'): v for v in ind.get('videos') or [] if isinstance(v, dict)}
    refs = de_referencias(referencias)
    out = []
    for i in ids:
        if not ID.fullmatch(str(i)):
            continue
        f = os.path.join(CARPETA, f'{i}.jpg')
        chica = os.path.join(referencias or REFERENCIAS, os.path.basename(str(refs.get(i, {}).get('archivo') or '')))
        if os.path.isfile(f):
            out.append(dict(vs.get(i) or refs.get(i) or {'id': i, 'titulo': ''}, ruta=f))
        elif i in refs and os.path.isfile(chica):
            out.append(dict(refs[i], ruta=chica))
    return out


# ---------------------------------------------------------------- las de referencia, del export del canal (sin internet)

def _leer_export(f):
    """Los .json del export de YouTube traen barras invertidas sueltas (rutas de Windows en las descripciones): se leen igual.
    (revisión, 03/11/2026) primero tal cual: un export ya bien escrito («C:\\\\Users») se rompía con el arreglo. Si no se puede,
    se doblan solo las sueltas: los pares «\\\\» se dejan y «\\u» vale solo con 4 cifras hex («C:\\users» es una suelta)."""
    t = open(f, encoding='utf-8').read()
    try:
        return json.loads(t)
    except ValueError:
        return json.loads(re.sub(r'(\\\\)|\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', lambda m: m.group(1) or '\\\\', t))


def armar_referencias(export, destino=None, por_marca=4, min_vistas_dia=10, avisar=print):
    """(fabian, 03/11/2026: «mira la primera imagen, fondos negros, tipo de fuente, estilo») De la carpeta del export del canal
    (videos.json y thumbs/propios/), las miniaturas de TUS videos largos de fondo oscuro con más vistas por día, hasta
    por_marca de cada marca (con min_vistas_dia o más) y sin dos iguales (el mismo video en otro idioma). Las copia a destino
    (mis_conocimientos/miniaturas/referencias/) como <marca>_<id>.jpg y escribe indice.json, que miniatura.referencias_estilo
    lee sin internet. Las «quitadas» del índice anterior ({id: por qué}) no vuelven. No borra nada ni gasta nada."""
    import numpy as np
    destino = destino or REFERENCIAS
    videos = _leer_export(os.path.join(export, 'videos.json'))
    fecha = re.search(r'\d{4}-\d{2}-\d{2}', os.path.basename(os.path.normpath(export)))
    hoy = time.mktime(time.strptime(fecha.group(0), '%Y-%m-%d')) if fecha else time.time()
    try:
        viejo = json.load(open(os.path.join(destino, 'indice.json'), encoding='utf-8'))
    except (OSError, ValueError):
        viejo = {}
    quitadas = viejo.get('quitadas') if isinstance(viejo.get('quitadas'), dict) else {}
    cands = []
    for v in videos if isinstance(videos, list) else []:
        vid = str(v.get('id') or '')
        f = os.path.join(export, 'thumbs', 'propios', vid + '.jpg')
        try:
            segundos = int(float(v.get('duracion_s') or 0))
        except ValueError:
            segundos = 0
        if (not ID.fullmatch(vid) or vid in quitadas or str(v.get('es_short')).lower() == 'true' or segundos <= SHORT_MAX
                or not os.path.isfile(f)):
            continue
        marca, servicios = etiquetar(v.get('titulo'))
        l = luz(f)
        if not marca or l is None or l > LUZ_MAX:  # sin marca son las de noticias (Movistar): no sirven para un tutorial
            continue
        x = {'id': vid, 'titulo': str(v.get('titulo') or ''), 'marca': marca, 'servicios': servicios,
             'vistas': int(v.get('vistas') or 0), 'publicado': str(v.get('publicado') or '')[:10], 'luz': l}
        x['vistas_dia'] = round(vistas_dia(x, hoy), 1)
        if x['vistas_dia'] >= min_vistas_dia:
            cands.append((x, f))
    cands.sort(key=lambda c: -c[0]['vistas_dia'])
    elegidas, huellas, cuantas = [], [], {}
    os.makedirs(destino, exist_ok=True)
    import cv2
    for x, f in cands:
        h = _gris(f, (32, 18), cv2.IMREAD_COLOR)  # la huella, en color: en gris se confunden dos distintas
        if cuantas.get(x['marca'], 0) >= por_marca or h is None:
            continue
        if any(np.abs(h.astype(float) - o).mean() < PARECIDA for o in huellas):
            continue
        x['archivo'] = f"{x['marca'].lower()}_{x['id']}.jpg"
        shutil.copyfile(f, os.path.join(destino, x['archivo']))
        elegidas.append(x)
        huellas.append(h.astype(float))
        cuantas[x['marca']] = cuantas.get(x['marca'], 0) + 1
        avisar(f"· {x['marca']}: {x['id']} ({x['vistas_dia']} vistas/día) {x['titulo'][:55]}")
    carpeta = os.path.normpath(export)
    ind = {'fecha': time.strftime('%Y-%m-%d', time.localtime(hoy)),
           'fuente': os.path.basename(os.path.dirname(carpeta)) + '/' + os.path.basename(carpeta),
           'regla': (f'fabian 03/11/2026 («fondos negros»): videos largos (más de {SHORT_MAX} s), fondo oscuro (luz del borde '
                     f'<= {LUZ_MAX}), las de más vistas por día (desde {DIAS_MIN} días; {min_vistas_dia} o más), hasta {por_marca} por '
                     'marca y sin dos iguales'),
           'miniaturas': elegidas, 'quitadas': quitadas}
    f = os.path.join(destino, 'indice.json')
    json.dump(ind, open(f + '.nuevo', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(f + '.nuevo', f)
    return {'ok': True, 'total': len(elegidas), 'por_marca': cuantas, 'carpeta': destino}


def marcar(vid, fijada=None, quitada=None):
    """📌 fijar (va siempre primero) o 🚫 quitar (no se usa nunca) una miniatura del canal."""
    if not ID.fullmatch(str(vid or '')):
        raise ValueError('miniatura no válida')
    ind = leer_indice()
    for clave, valor in (('fijadas', fijada), ('quitadas', quitada)):
        lista = [x for x in ind.get(clave) or [] if x != vid]
        if valor:
            lista.append(vid)
        if valor is not None:
            ind[clave] = lista
    if fijada:
        ind['quitadas'] = [x for x in ind.get('quitadas') or [] if x != vid]
    if quitada:
        ind['fijadas'] = [x for x in ind.get('fijadas') or [] if x != vid]
    guardar_indice(ind)
    return ind


def estado(d=None, texto=''):
    """Lo que muestra «🖼 Miniatura»: las miniaturas guardadas del canal y cuáles se van a usar para este video."""
    ind = leer_indice()
    marca, txt = contexto(d, texto)
    usar = [v['id'] for v in elegir(marca, txt, indice=ind)]
    fijadas, quitadas = set(ind.get('fijadas') or []), set(ind.get('quitadas') or [])
    videos = [dict(v, usar=v.get('id') in usar, fijada=v.get('id') in fijadas, quitada=v.get('id') in quitadas)
              for v in ind.get('videos') or [] if isinstance(v, dict) and os.path.isfile(os.path.join(CARPETA, v.get('archivo') or ''))]
    return {'videos': videos, 'usar': usar, 'marca': marca, 'fecha': ind.get('fecha'), 'fuente': ind.get('fuente'), 'carpeta': CARPETA}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bajar', action='store_true', help='baja las miniaturas recientes y las más vistas de tu canal (gratis)')
    ap.add_argument('--recientes', type=int, default=RECIENTES)
    ap.add_argument('--vistas', type=int, default=MAS_VISTAS)
    ap.add_argument('--elegir', help='«MARCA|TEXTO»: cuáles irían a GPT para ese título')
    ap.add_argument('--referencias', help='la carpeta del export del canal (youtube_datos/AAAA-MM-DD): arma las de referencia')
    a = ap.parse_args()
    try:
        if a.referencias:
            out = armar_referencias(a.referencias, avisar=lambda *x: print(*x, file=sys.stderr))
        elif a.bajar:
            out = bajar(a.recientes, a.vistas)
        else:
            out = {'ok': True, 'usar': [{'id': v['id'], 'titulo': v.get('titulo')} for v in elegir(texto=(a.elegir or '').replace('|', ' '))]}
        print(json.dumps(out, ensure_ascii=False))
    except (ValueError, OSError) as e:
        print(json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
