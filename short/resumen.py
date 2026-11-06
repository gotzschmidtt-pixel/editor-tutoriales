"""«📱 3 Shorts resumen» (pedido de fabian, 02/11/2026: «no has hecho un resumen del video del proceso completo para cada
uno… ¿puede la app hacer esto?»). En vez de un trozo del guion por Short, la app hace 3 Shorts de ~55-60 s que cuentan el
proceso COMPLETO, cada uno con un gancho distinto:
  1. «antes y después» (el problema y cómo terminó), 2. «en 1 minuto» (pasos numerados), 3. «¿ya probaste todo?».

Pasos (nada gasta hasta que fabian aprueba):
  1. proponer(): la IA de texto de «⚙ Ajustes IA» (centavos) lee el guion del video largo y el mapa del video y escribe los 3
     guiones, frase por frase, con la toma del grabado que muestra cada frase y los títulos/descripciones ES/EN/PT.
     Reglas de fabian: versiones de Android y MagicOS en una frase «con cualquier parche», nunca «SIN PC», máx. 3 emociones,
     cierre al tutorial completo, ~750-820 letras. Queda en shorts_resumen.json (editable en la app).
  2. costo(): letras de voz = créditos de ElevenLabs, a la vista antes de gastar.
  3. voz(): solo con confirmar=True (el SI de fabian): voz Mauricio en voz_short/S<n>F<k>.mp3.
  4. armar(): gratis. Cada frase con sus tomas en planos de ≤ 4,5 s (la ventana del programa con zoom guiado si hay
     short_encuadres.json), subtítulos estilo C +50 %, música fija, sin difuminados ni portada. Deja SHORT_RESUMEN_<n>.mp4 y
     shorts_resumen_textos.txt (una línea del video y enseguida el WhatsApp, hashtags y comentario fijado).
"""
import json, math, os, re, shutil, subprocess, sys, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'youtube'))
sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))
import reglas_titulo  # noqa: E402  lo que va y no va en los títulos (fabian, 03/11/2026)
import material_pc  # noqa: E402  la pantalla de la PC en los Shorts (fabian, 03/11/2026)
ARCHIVO = 'shorts_resumen.json'
GANCHOS = [('antes_despues', 'Antes y después: empieza diciendo que el teléfono estaba bloqueado y «mira cómo terminó»'),
           ('un_minuto', 'En 1 minuto: el proceso como pasos numerados («Paso uno… paso cuatro»)'),
           ('ya_probaste', '¿Ya probaste todo?: le habla al que ya intentó TalkBack, Bluetooth y códigos sin resultado')]
EMOCION = re.compile(r'\[[a-z ]+\]\s*')
TROZO, AIRE, RETRASO = 4.5, 0.3, 0.1
COLA_CIERRE = 2.0  # el cierre dura esto más: en el Short 2 del Honor «play» era la última palabra y el ícono duraba 0,6 s (03/11/2026)
# En los Shorts los enlaces de la descripción y de los comentarios no se pueden tocar: lo que lleva al tutorial es el
# «Video relacionado» (el enlace con ▶ que YouTube pone abajo a la izquierda; se elige al subir el Short)
FIN = {'es': 'Tutorial completo: toca el enlace con el ícono de play que aparece abajo del Short.',
       'en': 'Full tutorial: tap the link with the play icon below the Short.',
       'pt': 'Tutorial completo: toque no link com o ícone de play que aparece embaixo do Short.'}
# el cierre de TODOS los Shorts, de todas las marcas (fabian, 02/11/2026): las 3 frases rotan (Short 1 → la 1…) y, apenas la
# voz dice «play», sale el ícono de play (biblioteca de logos, solo en Shorts) con una flecha hacia el enlace de abajo
CIERRES = {'es': ['Toca el enlace con el ícono de play, aquí abajo, y mira el tutorial completo.',
                  '¿Quieres verlo paso a paso? El video completo está aquí abajo, en el enlace con el play.',
                  'Mira el tutorial completo: toca el play que aparece abajo.'],
           'en': ['Tap the link with the play icon, right down below, and watch the full tutorial.',
                  'Want to see it step by step? The full video is right down below, in the link with the play icon.',
                  'Watch the full tutorial: tap the play button down below.'],
           'pt': ['Toque no link com o ícone de play, aqui embaixo, e assista ao tutorial completo.',
                  'Quer ver passo a passo? O vídeo completo está aqui embaixo, no link com o play.',
                  'Assista ao tutorial completo: toque no play que aparece embaixo.']}
LLAMADA = re.compile(r'tutorial completo|video completo|v[ií]deo completo|en mi canal|full tutorial|full video|play', re.I)
# Antes del cierre, en TODOS los Shorts (fabian, 03/11/2026): las páginas oficiales en la voz y en pantalla («para darle más
# toque de profesionalismo», 14:09) y los testimonios del canal de WhatsApp (16:11). En los Shorts los enlaces de la
# descripción no se pueden tocar: la frase manda a la descripción del tutorial completo, al que lleva el cierre del play.
# Tienen id fijo: la misma voz sirve para los 3 Shorts (se graba una vez) y no corre los números de las otras frases.
EXTRAS = [('WEBS', {'es': 'Y visita nuestras páginas oficiales: GSM Prime punto co y Xiaomi Unlock punto com.',
                    'en': 'And visit our official websites: GSM Prime dot co and Xiaomi Unlock dot com.',
                    'pt': 'E visite nossas páginas oficiais: GSM Prime ponto co e Xiaomi Unlock ponto com.'}),
          ('TESTIMONIOS', {'es': 'En nuestro canal de WhatsApp verás testimonios de clientes reales. '
                                 'El enlace para unirte está en la descripción del tutorial completo.',
                           'en': 'On our WhatsApp channel you will see testimonials from real customers. '
                                 'The link to join is in the description of the full tutorial.',
                           'pt': 'No nosso canal do WhatsApp você vai ver depoimentos de clientes reais. '
                                 'O link para entrar está na descrição do tutorial completo.'})]
WEBS_TEXTO = 'GSMPRIME.CO • XIAOMIUNLOCK.COM'  # en pantalla desde la frase de las páginas hasta el final
ZOOM_CLAVE = 1.22  # acercamiento de la cámara en los pasos clave
WEBS_Y = 0.085  # arriba al centro: debajo de los botones de YouTube y por encima de los logos (0.15) y la miniatura (0.17)


def cierre(n, idioma='es'):
    """La frase de cierre del Short n (1, 2, 3…): rotan."""
    lista = CIERRES.get(idioma) or CIERRES['es']
    return lista[(n - 1) % len(lista)]


def ids(s, n):
    """El id de la voz de cada frase del Short n: las fijas (WEBS, TESTIMONIOS) el suyo; las otras S<n>F<k>, contando solo
    las que no son fijas (así las voces ya grabadas siguen sirviendo)."""
    out, k = [], 0
    for f in s.get('frases') or []:
        if f.get('id'):
            out.append(f['id'])
        else:
            k += 1
            out.append(f'S{n}F{k}')
    return out


def poner_extras(r, idioma='es'):
    """Las frases fijas (páginas y testimonios) justo antes del cierre de cada Short, una vez y en ese orden."""
    fijos = {i for i, _ in EXTRAS}
    for s in r.get('shorts') or []:
        frases = [f for f in s.get('frases') or [] if f.get('id') not in fijos]
        if not frases:
            continue
        ultima = frases[-1]
        # sin una toma que diga lo mismo (páginas, WhatsApp), van trozos distintos del mismo Short, repartidos y cambiando
        # cada 2-3 s (nunca la misma escena larga); si fabian les puso otras tomas, quedan las suyas
        todas = [list(t) for f in frases[:-1] for t in f.get('tomas') or [] if not material_pc.es_pc(t)] or \
            [list(t) for t in ultima.get('tomas') or [[0, 3]] if not material_pc.es_pc(t)] or [[0, 3]]
        elegir = lambda j: todas[min(len(todas) - 1, len(todas) * j // (2 * len(EXTRAS) + 1))]
        viejas = {f['id']: f for f in s.get('frases') or [] if f.get('id') in fijos}
        extras = [dict(viejas.get(i) or {'tomas': [elegir(2 * e + 1), elegir(2 * e + 2)]}, id=i, texto=t.get(idioma) or t['es'])
                  for e, (i, t) in enumerate(EXTRAS)]
        s['frases'] = frases[:-1] + extras + [ultima]
    return r


def poner_cierres(r, idioma='es'):
    """La última frase de cada Short pasa a ser su cierre fijo. Si la última ya manda al tutorial, se cambia su texto (con sus
    tomas); si no, se agrega una frase más con la última toma."""
    for n, s in enumerate(r.get('shorts') or [], 1):
        frases = s.get('frases') or []
        if not frases:
            continue
        texto = cierre(n, idioma)
        if EMOCION.sub('', frases[-1].get('texto', '')).strip() == texto:
            continue
        if LLAMADA.search(frases[-1].get('texto', '')):
            frases[-1]['texto'] = texto
        else:
            ultima = (frases[-1].get('tomas') or [[0, 3]])[-1]
            frases.append({'texto': texto, 'tomas': [list(ultima)]})
    return r
FIJADO = {'es': '📌 Tutorial completo paso a paso: (pega aquí el enlace del video largo cuando lo subas)',
          'en': '📌 Full step-by-step tutorial: (paste the long video link here once it is up)',
          'pt': '📌 Tutorial completo passo a passo: (cole aqui o link do vídeo longo quando ele estiver no ar)'}


def _llamar_ia(texto):
    sys.path.insert(0, os.path.join(RAIZ, 'ia'))
    import ia
    return ia.llamar(json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')), texto, [])


def _json(txt):
    m = re.search(r'\{.*\}', txt or '', re.S)
    return json.loads(m.group(0)) if m else {}


def letras(texto):
    return len(EMOCION.sub('', texto or '').strip())


def _marca(d):
    """La marca del proyecto (por su nombre o idea.txt); '' si no se sabe."""
    try:
        import conocimiento
        return conocimiento.marca_de_proyecto(d) or ''
    except Exception:
        return ''


def _usa_pc(d):
    """(revisión, 03/11/2026) Si el PROCESO del video usa PC (procesos_pc.json): todos menos la cuenta Mi de Xiaomi y la
    liberación de bandas de iPhone. Solo en los que usan PC está prohibido decir «sin PC»."""
    return reglas_titulo.necesita_pc(_marca(d), reglas_titulo.texto_proyecto(d))


def _modelo(d):
    try:
        return (json.load(open(os.path.join(d, 'youtube', 'metadatos.json'), encoding='utf-8')).get('modelo') or '').strip()
    except (OSError, ValueError):
        return ''


def prompt(d):
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    bloques = [{'id': b['id'], 'src': (b.get('montaje') or {}).get('src_inicio'), 'texto': b.get('texto', '')} for b in g['bloques']]
    try:
        mapa = [{'t': round(float(c.get('t') or 0)), 'pantalla': str(c.get('texto') or c.get('pantalla') or '')[:80]}
                for c in json.load(open(os.path.join(d, 'mapa_video.json'), encoding='utf-8')).get('cuadros', [])]
    except (OSError, ValueError):
        mapa = []
    modelo = _modelo(d) or os.path.basename(os.path.abspath(d))
    ganchos = '\n'.join(f'{i + 1}. {n}: {t}' for i, (n, t) in enumerate(GANCHOS))
    pc = _usa_pc(d)
    return f"""Escribe 3 guiones de YouTube Shorts (voz en off, español latino, tuteando) para el video «{modelo}».
Cada Short cuenta el proceso COMPLETO de principio a fin en 55-60 s (entre 750 y 820 letras de voz), con un gancho distinto:
{ganchos}
Reglas obligatorias de fabian:
- Una frase corta con las versiones: «Android quince, dieciséis, diecisiete o superior, y MagicOS nueve, diez u once, con cualquier parche» (adáptala a la marca si no es Honor).
- {'NUNCA digas «sin PC» (este proceso usa PC).' if pc else 'Este proceso no usa PC: decir «sin PC» se puede.'} Números escritos como se dicen. Nombra el modelo como «{modelo}».
- Máximo 3 etiquetas de emoción por guion entre corchetes en inglés ([curious], [excited], [serious]), nunca dos seguidas.
- La última frase de cada Short es EXACTAMENTE su cierre: Short 1 «{cierre(1)}», Short 2 «{cierre(2)}», Short 3 «{cierre(3)}».
- No inventes datos: usa solo lo que dice el guion del video largo.
Para cada frase da las tomas del grabado original (segundos [desde, hasta], 3-5 s cada una) que muestran EXACTAMENTE lo que dice,
usando los segundos del guion (src) y del mapa de pantallas.
Además, para cada Short: título (máx. 70 letras, sin emojis, sin < > ni comillas) y una descripción de 1-2 frases en una sola línea que diga de qué trata el video (la app pone el WhatsApp justo debajo), en es, en y pt.
{reglas_titulo.para_ia(_marca(d), reglas_titulo.texto_proyecto(d))}
GUION DEL VIDEO LARGO: {json.dumps(bloques, ensure_ascii=False)}
MAPA DE PANTALLAS (segundo, lo que se lee): {json.dumps(mapa[:150], ensure_ascii=False)}
Responde SOLO con JSON: {{"shorts": [{{"gancho": "antes_despues", "frases": [{{"texto": "…", "tomas": [[18, 22]]}}],
"titulos": {{"es": "…", "en": "…", "pt": "…"}}, "descripciones": {{"es": "…", "en": "…", "pt": "…"}}}}, …]}}"""


def validar(r, pc=True):
    """Lo que no cumple las reglas de fabian (lista de avisos); nunca deja pasar «sin PC» si el proceso usa PC (pc: _usa_pc(d))."""
    avisos = []
    for n, s in enumerate(r.get('shorts') or [], 1):
        txt = ' '.join(f.get('texto', '') for f in s.get('frases') or [] if not f.get('id'))  # sin las frases fijas
        if pc and reglas_titulo.SIN_PC.search(txt):
            avisos.append(f'Short {n}: dice «sin PC» (prohibido: este proceso usa PC)')
        if len(EMOCION.findall(txt)) > 3:
            avisos.append(f'Short {n}: más de 3 emociones')
        if 'parche' not in txt.lower():
            avisos.append(f'Short {n}: falta la frase de versiones «con cualquier parche»')
        if not 650 <= letras(txt) <= 900:
            avisos.append(f'Short {n}: {letras(txt)} letras (lo ideal, 750-820 para 55-60 s)')
        if any(not f.get('tomas') for f in s.get('frases') or []):
            avisos.append(f'Short {n}: hay frases sin toma')
        ultima = EMOCION.sub('', ((s.get('frases') or [{}])[-1]).get('texto', '')).strip()
        if ultima not in [c for v in CIERRES.values() for c in v]:
            avisos.append(f'Short {n}: la última frase no es el cierre fijo («{cierre(n)}»)')
    return avisos


def proponer(d, llamar=None):
    r = _json((llamar or _llamar_ia)(prompt(d)))
    if not r.get('shorts'):
        raise ValueError('La IA no devolvió los 3 guiones; prueba de nuevo.')
    poner_extras(poner_cierres(r))
    r['avisos'] = validar(r, _usa_pc(d))
    r['costo'] = costo(r)
    json.dump(r, open(os.path.join(d, ARCHIVO), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return r


def leer(d):
    try:
        return json.load(open(os.path.join(d, ARCHIVO), encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def guardar(d, r):
    r['avisos'], r['costo'] = validar(r, _usa_pc(d)), costo(r)
    json.dump(r, open(os.path.join(d, ARCHIVO), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return r


def costo(r):
    """{'letras': n, 'creditos': n}: ElevenLabs cobra ~1 crédito por letra (las etiquetas de emoción no se leen)."""
    voces = {}
    for n, s in enumerate(r.get('shorts') or [], 1):
        for i, f in zip(ids(s, n), s.get('frases') or []):
            voces[i] = letras(f.get('texto', ''))  # las frases fijas se graban una sola vez para los 3 Shorts
    n = sum(voces.values())
    return {'letras': n, 'creditos': n}


def voz(d, confirmar=False):
    """La voz Mauricio de las frases (GASTA ElevenLabs). Solo con confirmar=True, después del SI de fabian."""
    if not confirmar:
        raise PermissionError('La voz gasta créditos de ElevenLabs: hace falta la confirmación de fabian.')
    r = guardar(d, poner_extras(leer(d)))  # los guiones de antes del 03/11/2026 reciben las frases de páginas y testimonios
    bloques, vistos = [], set()
    for n, s in enumerate(r['shorts'], 1):
        for i, f in zip(ids(s, n), s['frases']):
            if i in vistos:
                continue  # las frases fijas: una sola voz para los 3 Shorts
            vistos.add(i)
            bloques.append({'id': i, 'texto': f['texto'], 'tipo': 'libre', 'humor': False,
                            'montaje': {'modo': 'lento', 'src_inicio': float(f['tomas'][0][0]),
                                        'src_fin': float(f['tomas'][0][0]) + 30, 'velocidad': 1.0, 'congelar_s': None}})
    g = os.path.join(d, '.shorts_resumen_guion.json')
    json.dump({'bloques': bloques}, open(g, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, os.path.join(RAIZ, 'voz', 'voz.py'), '--guion', g, '--salida', os.path.join(d, 'voz_short')],
                   check=True, cwd=d)


def banner_webs(carpeta):
    """El PNG de «GSMPRIME.CO • XIAOMIUNLOCK.COM»: una píldora blanca con letras oscuras, como las páginas de la tarjeta del
    cierre, del ancho justo para que entre en el Short."""
    from PIL import Image, ImageDraw, ImageFont
    import short
    fuente = lambda n: next((ImageFont.truetype(f, n) for f in short.FUENTES if os.path.exists(f)), ImageFont.load_default())
    dib = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    n = 60
    while n > 30 and dib.textlength(WEBS_TEXTO, font=fuente(n)) > short.SW - 180:
        n -= 2
    f = fuente(n)
    w, h = int(dib.textlength(WEBS_TEXTO, font=f) + 80), n + 44
    img = Image.new('RGBA', (w + 12, h + 12), (0, 0, 0, 0))
    d_ = ImageDraw.Draw(img)
    d_.rounded_rectangle([6, 10, w + 6, h + 10], radius=h // 2, fill=(0, 0, 0, 110))  # sombra suave
    d_.rounded_rectangle([6, 4, w + 6, h + 4], radius=h // 2, fill='white')
    d_.text((w / 2 + 6, h / 2 + 4), WEBS_TEXTO, font=f, fill=(17, 17, 17), anchor='mm')
    ruta = os.path.join(carpeta, 'webs.png')
    img.save(ruta)
    return ruta


def _sin_logo(tomas):
    """Las tomas para poner_logos: en la frase de las páginas no sale el logo de Xiaomi («Xiaomi Unlock» es el nombre de la
    página, no la marca del video); sus segundos se siguen contando."""
    return [dict(c, id='GANCHO') if c.get('id') == 'WEBS' else c for c in tomas]


def _encuadre(encuadres, s0):
    """La referencia de encuadre guiado (short_encuadres.json) cuyo rango del grabado contiene s0, si hay."""
    for conf in encuadres.values():
        rango = conf.get('rango')
        if conf.get('referencia') and rango and rango[0] <= s0 <= rango[1]:
            return conf
    return None


def trozo_pc(d, toma, desde, dur, salida, movs=None):
    """Un trozo de material.mp4 en vertical: su recorte con zoom por claves, sobre la misma imagen desenfocada de fondo."""
    import short
    import codificar
    video = os.path.join(d, material_pc.MATERIAL)
    W, H = [int(x) for x in subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                            '-of', 'csv=p=0', video], capture_output=True, text=True).stdout.strip().split(',')[:2]]
    a, b = toma['claves'][0], toma['claves'][-1]
    bw, bh = short.SW, int(short.SW / 1.1) // 2 * 2
    pw = min(W, int(H * 1.1) // 2 * 2)
    x0 = max(0, min(W - pw, int(a['cx'] * W - pw / 2)))
    z0, z1 = max(1, pw / (a['w'] * W)), max(1, pw / (b['w'] * W))
    n = max(1, round(dur * 30))
    z = f"{z0:.4f}+({z1 - z0:.4f})*min(on/{n},1)"
    cxr = (a['cx'] * W - x0) / pw
    # las flechas y círculos de esta toma (mismo dibujo que en la cámara) van pegados a la imagen ANTES del zoom: lo siguen
    ins, pre, ult = [], '', 'b'
    for sn in toma.get('senales') or []:
        mov = (movs or {}).get(material_pc.clave_senal(sn))
        off = sn['src'] - desde
        if not mov or off >= dur or off + sn.get('dur', 3) <= 0:
            continue
        ins += ['-i', mov]
        i = len(ins) // 2
        tiempo = f'setpts=PTS+{off:.3f}/TB' if off >= 0 else f'trim=start={-off:.3f},setpts=PTS-STARTPTS'
        pre += f'[{i}:v]scale={W}:-1,{tiempo}[s{i}];[{ult}][s{i}]overlay=0:0:eof_action=pass[o{i}];'
        ult = f'o{i}'
    fondo = f"[0:v]split[a][b];[a]scale={short.SW}:{short.SH}:force_original_aspect_ratio=increase,crop={short.SW}:{short.SH},gblur=sigma=30[f];"
    vf = (f"crop={pw}:{H}:{x0}:0,fps=30,zoompan=z='{z}':x='{cxr:.4f}*iw-iw/zoom/2':y='{a['cy']:.4f}*ih-ih/zoom/2':d=1:s={bw}x{bh}:fps=30[c];"
          f"[f][c]overlay=0:(H-h)/2-{int(short.SH * 0.08)},setsar=1,fps=30,format=yuv420p")
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{desde:.3f}', '-t', f'{dur:.3f}', '-i', video] + ins + [
                   '-filter_complex', f'{fondo}{pre}[{ult}]{vf}[v]', '-map', '[v]', '-t', f'{dur:.3f}', '-an',
                   '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', salida], check=True)


def armar(d, cuales=(1, 2, 3), idioma='es'):
    """Gratis (la voz ya está hecha). Deja SHORT_RESUMEN_<n>.mp4 y shorts_resumen_textos.txt. Otro idioma (en, pt): lee
    shorts_resumen_<idioma>.json y voz_short_<idioma>/ y deja SHORT_RESUMEN_<n>_<IDIOMA>.mp4, con las mismas tomas."""
    import cv2
    import short
    import codificar
    r = leer(d) if idioma == 'es' else json.load(open(os.path.join(d, f'shorts_resumen_{idioma}.json'), encoding='utf-8'))
    carpeta = 'voz_short' if idioma == 'es' else f'voz_short_{idioma}'
    sufijo = '' if idioma == 'es' else f'_{idioma.upper()}'
    orig = os.path.join(d, 'original.mp4')
    try:
        encuadres = json.load(open(os.path.join(d, 'short_encuadres.json'), encoding='utf-8'))
    except (OSError, ValueError):
        encuadres = {}
    hechos = []
    for n in cuales:  # una frase sin tomas (campo borrado) daba «division by zero» a mitad del armado
        for k, f in enumerate(r['shorts'][n - 1]['frases'], 1):
            if not f.get('tomas'):
                raise ValueError(f'Short {n}, frase {k}: no tiene tomas (escríbelas como 18-22)')
    poner_extras(r, idioma)  # después de revisar: el número de frase del aviso es el que fabian ve en la pestaña
    if idioma == 'es' and not r.get('pc_elegido') and material_pc.poner(d, r):  # si no pulsó «🖥 Poner la pantalla de la PC», se elige acá
        guardar(d, r)
    senales_src = short.senales_grabado(d)  # las flechas y círculos del video largo, en segundos de la grabación
    for n in cuales:
        s = r['shorts'][n - 1]
        cap = cv2.VideoCapture(orig)
        tmp = tempfile.mkdtemp()
        try:
            plan = []  # primero los trozos de todo el Short: así se dibujan de una vez solo las señales que caen en ellos
            # las frases fijas (páginas, testimonios) van solo si su voz ya está grabada: sin ella el Short sale como antes
            frases = [(f, i) for f, i in zip(s['frases'], ids(s, n))
                      if not f.get('id') or os.path.isfile(os.path.join(d, carpeta, f'{i}.mp3'))]
            for k, (f, bid) in enumerate(frases, 1):
                mp3 = os.path.join(d, carpeta, f'{bid}.mp3')
                largo = round(short.duracion(mp3) + AIRE, 2)
                cierre = k == len(frases) and bool(LLAMADA.search(f.get('texto', '')))
                if cierre:  # que se alcance a ver el ícono de play y la flecha al enlace después de la última palabra
                    largo = round(largo + COLA_CIERRE, 2)
                piezas, pesos = [], f.get('pesos') or [1] * len(f['tomas'])
                for tm, w in zip(f['tomas'], pesos):
                    cada = largo * w / sum(pesos)
                    m = max(1, math.ceil(cada / TROZO))
                    pc = tm if material_pc.es_pc(tm) else None
                    a = pc['src'] if pc else tm[0]
                    piezas += [(float(a) + j * cada / m, cada / m, pc) for j in range(m)]
                plan.append((k, f, bid, mp3, largo, piezas, cierre))
            # cuándo tapa el centro la tarjeta de WhatsApp: las flechas que caerían debajo no se dibujan
            ventanas, t0 = [], 0.0
            if short.hay_tarjeta():
                frases_t = []
                for k, f, bid, mp3, largo, piezas, cierre in plan:
                    frases_t.append((t0 + RETRASO, short.palabras_voz(d, bid, carpeta)))
                    t0 += largo
                ventanas = short.ventanas_tarjeta(frases_t)
            movs = material_pc.dibujar_senales(d, [pc for p_ in plan for _a, _b, pc in p_[5] if pc], tmp)
            dibujadas = short.dibujar_senales(orig, senales_src, [(a, a + b) for p_ in plan if not p_[6] for a, b, pc in p_[5] if pc is None], tmp)
            # el recorte vertical deja adentro lo que señala cada flecha o círculo (como tus marcas)
            marcas = short.marcas_autor(d) + [(c['src'] + c['dur'] / 2, c['x'], c['y']) for c in dibujadas]
            memoria = short.deteccion.Memoria(orig)
            partes, tomas = [], []
            inicio = 0.0  # segundo del Short en que empieza cada trozo
            for k, f, bid, mp3, largo, piezas, cierre in plan:
                lista = []
                for j, (s0, dur, pc) in enumerate(piezas):
                    p = os.path.join(tmp, f'v{k:02d}_{j:02d}.mp4')
                    if pc is not None:  # la pantalla de la PC, con su zoom; las flechas de la cámara no van acá
                        inicio += dur
                        trozo_pc(d, pc, s0, dur, p, movs)
                        lista.append(p)
                        continue
                    # en el cierre no van flechas ni etiquetas de la frase anterior (tapaban la flecha al enlace)
                    sus = [] if cierre else short.sin_tapar(dibujadas, s0, inicio, ventanas)
                    inicio += dur
                    # (opcional en shorts_resumen.json) tramos que se ven enteros: el cuadro grande sobre su propio fondo desenfocado
                    entero = any(x0 <= s0 <= x1 for x0, x1 in r.get('completos') or [])
                    conf = next((encuadres[c] for c, rangos in (r.get('encuadre_en') or {}).items() if c in encuadres
                                 and any(x0 <= s0 <= x1 for x0, x1 in rangos)), None) or _encuadre(encuadres, s0)
                    guiado = short.seguir_ref(cap, s0, dur, conf, d) if conf and not entero else None
                    claves, zoom, _ = guiado or (([], 1, None) if entero else short.seguir(cap, s0, dur, marcas, memoria))
                    if any(x0 <= s0 <= x1 for x0, x1 in f.get('acercar') or []) or \
                            ('acercar' not in f and material_pc.RE_ACERCAR.search(f.get('texto', ''))):
                        zoom *= ZOOM_CLAVE  # OKAY, Omitir, Ajustes: se acerca al paso clave
                    ch = round(short.H / zoom / 2) * 2
                    cw = round(ch * 9 / 16 / 2) * 2
                    cl = [(t, x - cw / 2, y - ch / 2) for t, x, y in claves]
                    vf = (f"crop={cw}:{ch}:x='{short.expr(cl, 1, 0, short.W - cw)}':y='{short.expr(cl, 2, 0, short.H - ch)}',"
                          f'scale={short.SW}:{short.SH},setsar=1,fps=30,format=yuv420p') if not entero else (
                        f'split[a][b];[a]scale={short.SW}:{short.SH}:force_original_aspect_ratio=increase,crop={short.SW}:{short.SH},'
                        f'gblur=sigma=30[f];[b]scale=-2:{int(short.SH * 0.5)},crop={short.SW}:{int(short.SH * 0.5)}[c];'
                        f'[f][c]overlay=0:(H-h)/2-{int(short.SH * 0.08)},setsar=1,fps=30,format=yuv420p')
                    ins, filtro, ult = short.con_senales(s0, dur, sus, 1)
                    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{s0:.3f}', '-t', f'{dur:.3f}', '-i', orig] + ins +
                                  ['-filter_complex', f'{filtro}[{ult}]{vf}[v]', '-map', '[v]', '-t', f'{dur:.3f}',
                                   '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', p], check=True)
                    lista.append(p)
                lf = os.path.join(tmp, f'l{k:02d}.txt')
                open(lf, 'w', encoding='utf-8').write(''.join(f"file '{p}'\n".replace('\\', '/') for p in lista))
                p = os.path.join(tmp, f'p{k:02d}.mp4')
                codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lf, '-i', mp3,
                               '-filter_complex', f'[1:a]adelay={int(RETRASO * 1000)}:all=1,apad,atrim=0:{largo:.3f},'
                               'aresample=44100,aformat=channel_layouts=stereo[a]', '-map', '0:v', '-map', '[a]', '-t', f'{largo:.3f}',
                               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-c:a', 'aac', '-b:a', '160k', p], check=True)
                partes.append(p)
                tomas.append({'id': bid, 'carpeta': carpeta, 'largo': largo, 'texto': f['texto']})
            cap.release()
            memoria.guardar()
            lista = os.path.join(tmp, 'lista.txt')
            open(lista, 'w', encoding='utf-8').write(''.join(f"file '{p}'\n".replace('\\', '/') for p in partes))
            junto = os.path.join(tmp, 'junto.mp4')
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', junto],
                           check=True)
            ass = f'short_resumen_{n}{sufijo}_subs.ass'
            open(os.path.join(d, ass), 'w', encoding='utf-8').write(short.subtitulos(d, tomas, RETRASO))
            entradas, audio = ['-i', junto], '[0:a]anull[a]'
            if os.path.exists(short.MUSICA):
                entradas += ['-stream_loop', '-1', '-i', short.MUSICA]
                audio = '[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]'
            video = f'[0:v]ass={ass}[vb]'
            if LLAMADA.search(tomas[-1]['texto']):  # el cierre: una flecha hacia el enlace ▶ de abajo mientras se dice
                desde = round(sum(x['largo'] for x in tomas[:-1]) + RETRASO + 0.3, 2)
                entradas += ['-loop', '1', '-i', short.flecha_al_enlace(tmp)]
                video = f'[0:v]ass={ass}[s];' + short.filtro_flecha(entradas.count('-i') - 1, 's', desde,
                                                                    round(sum(x['largo'] for x in tomas), 2), 'vb')
            # las páginas oficiales en pantalla (fabian, 03/11/2026) desde que la voz las nombra (o desde el cierre, si esa
            # frase no está grabada) hasta el final, arriba al centro: por encima de los logos y de la miniatura del final
            k_web = next((j for j, x in enumerate(tomas) if x['id'] == 'WEBS'), len(tomas) - 1)
            desde_web = round(sum(x['largo'] for x in tomas[:k_web]) + RETRASO, 2)
            entradas += ['-loop', '1', '-i', banner_webs(tmp)]
            video += (f";[{entradas.count('-i') - 1}:v]format=rgba,fade=t=in:st={desde_web:.2f}:d=0.3:alpha=1[web];"
                      f"[vb][web]overlay=x=(W-w)/2:y={short.SH * WEBS_Y:.0f}:shortest=1:enable='gte(t,{desde_web:.2f})'[v]")
            salida = f'SHORT_RESUMEN_{n}{sufijo}.mp4'
            codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + entradas +
                          ['-filter_complex', f'{video};{audio}', '-map', '[v]', '-map', '[a]', '-c:v', 'libx264',
                           '-preset', 'medium', '-crf', '19', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', salida],
                          check=True, cwd=d)
            short.poner_logos(d, _sin_logo(tomas), os.path.join(d, salida), RETRASO)  # logos de lo que nombra la voz
            # el último segundo con la miniatura del video largo, solo si fabian la aprobó (03/11/2026); va dentro de los 2 s
            # de cola del cierre, sin tapar el play ni su flecha. Si la última frase no es el cierre, se agrega 1 s.
            mini = short.poner_miniatura_final(d, os.path.join(d, salida), alargar=not LLAMADA.search(tomas[-1]['texto']))
            hechos.append({'archivo': salida, 'duracion': round(short.duracion(os.path.join(d, salida)), 1),
                           'miniatura_final': os.path.basename(mini) if mini else None, 'revision': _revisar(d, salida, ass)})
        finally:  # los tramos de cada Short pesan cientos de MB: no quedan en %TEMP% (con varias pruebas se llenaba el disco)
            shutil.rmtree(tmp, ignore_errors=True)
    if idioma == 'es':
        textos(d, r)
    return hechos


def _revisar(d, salida, ass):
    """«✅ Revisor automático» sobre el Short recién armado; sin ❌ graves no queda como listo."""
    sys.path.insert(0, os.path.join(RAIZ, 'revision'))
    try:
        import revisor_auto
        inf = revisor_auto.revisar(os.path.join(d, salida), os.path.join(d, ass), True)
        return {'ok': inf['ok'], 'informe': os.path.splitext(salida)[0] + '.revision.md'}
    except Exception as e:
        return {'ok': False, 'informe': None, 'error': str(e)}


def textos(d, r=None):
    """Títulos y descripciones ES/EN/PT de los Shorts: arriba la línea del video y enseguida el WhatsApp (fabian, 03/11/2026),
    después el cierre al tutorial, hashtags y comentario fijado."""
    import youtube
    r = r or leer(d)
    modelo = re.sub(r'\W', '', _modelo(d).replace('Honor', '')) or 'Honor'
    hs = {'es': f'#Honor #FRP #CuentaGoogle #{modelo}', 'en': f'#Honor #FRPBypass #GoogleAccount #{modelo}',
          'pt': f'#Honor #FRP #ContaGoogle #{modelo}'}
    out = []
    for n, s in enumerate(r.get('shorts') or [], 1):
        out.append(f'===== SHORT_RESUMEN_{n}.mp4 ({s.get("gancho", "")}) =====')
        for k in ('es', 'en', 'pt'):
            # (03/11/2026) el título con las reglas de fabian: «Sin PC» solo al inicio y solo sin PC, Honor sin «Todos los
            # Modelos», «Gratis» solo si es gratis, el año de hoy
            t = reglas_titulo.revisar_titulo((s.get('titulos') or {}).get(k, ''), _marca(d), reglas_titulo.texto_proyecto(d))[0]
            t = youtube.limpiar_yt(t)
            t = youtube.signos_es(t) if k == 'es' else t
            desc = youtube.limpiar_yt(youtube.con_contacto(f"{(s.get('descripciones') or {}).get(k, '')}\n\n{FIN[k]}\n\n{hs[k]}", k, t))
            out += [f'--- {k.upper()} ---', 'TÍTULO: ' + t, 'DESCRIPCIÓN:', desc, 'COMENTARIO FIJADO:', FIJADO[k], '']
    open(os.path.join(d, 'shorts_resumen_textos.txt'), 'w', encoding='utf-8').write('\n'.join(out))
    return '\n'.join(out)


# ------------------------------------------------------------------ la pestaña de la app («📱 3 Shorts resumen»)
ESTADO = {}  # carpeta → {'estado': 'voz'|'armando'|'listo'|'error', 'msg': …}


def _fondo(d, que, fn):
    import threading

    def correr():
        ESTADO[d] = {'estado': que, 'msg': ''}
        try:
            r = fn()
            ESTADO[d] = {'estado': 'listo', 'msg': json.dumps(r, ensure_ascii=False) if r else ''}
        except Exception as e:  # se muestra en la pestaña
            ESTADO[d] = {'estado': 'error', 'msg': str(e)[-500:]}
    threading.Thread(target=correr, daemon=True).start()


def get(h, ruta, q, d):
    if ruta == '/api/shorts_resumen/estado':
        r = leer(d)
        try:  # la miniatura que sale 1 s al final (03/11/2026); None: el Short queda como siempre
            import short
            mini = short.miniatura_aprobada(d)
        except Exception:
            mini = None
        return h.responder({'guion': r, 'costo': costo(r) if r else None, 'trabajo': ESTADO.get(d, {}),
                            'miniatura_final': os.path.basename(mini) if mini else '',
                            'hay_material': os.path.isfile(os.path.join(d, material_pc.MATERIAL)),
                            'hechos': sorted(f for f in os.listdir(d) if f.startswith('SHORT_RESUMEN_') and f.endswith('.mp4'))})
    return h.error('No existe.')


def post(h, ruta, q, largo, d):
    datos = json.loads(h.rfile.read(largo) or b'{}') if largo else {}
    try:
        if ruta == '/api/shorts_resumen/proponer':  # la IA de texto (centavos): los 3 guiones
            return h.responder(proponer(d))
        if ruta == '/api/shorts_resumen/guardar':  # lo que fabian corrigió a mano
            return h.responder(guardar(d, datos.get('guion') or {}))
        if ruta == '/api/shorts_resumen/pc':  # gratis: la pantalla de la PC según lo que dice la voz; se revisa antes de armar
            def elegir_pc():
                r = leer(d)
                n = material_pc.poner(d, r)
                guardar(d, r)
                return {'frases': n}
            _fondo(d, 'leyendo la pantalla de la PC', elegir_pc)
            return h.responder({'ok': True})
        if ruta == '/api/shorts_resumen/voz':  # GASTA ElevenLabs: solo con «confirmo»
            if not datos.get('confirmo'):
                return h.error(f"La voz gasta ~{costo(leer(d))['creditos']} créditos de ElevenLabs: confirma primero.")
            _fondo(d, 'voz', lambda: voz(d, confirmar=True))
            return h.responder({'ok': True})
        if ruta == '/api/shorts_resumen/armar':  # gratis
            _fondo(d, 'armando', lambda: armar(d))
            return h.responder({'ok': True})
    except Exception as e:
        return h.error(str(e))
    return h.error('No existe.')
