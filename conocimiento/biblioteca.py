"""«📚 Biblioteca de tus videos»: la transcripción de cada video de tu canal, el diccionario del canal y lo que la IA
aprende de ellos. Todo vive en mis_conocimientos/ (al actualizar la app no se toca):

  transcripciones/<id>.txt  un video por archivo: título, link, fecha y lo que dices
  diccionario.json          modelos, herramientas, siglas y webs, escritos como los escribes tú (y en cuántos videos salen)
  DICCIONARIO.md            el mismo diccionario para leerlo o corregirlo a mano
  .biblioteca.json          qué videos ya están y cuáles ya leyó la IA

    python biblioteca.py --accion juntar   [--canal URL] [--whisper]   (gratis: subtítulos de YouTube; Whisper si no hay)
    python biblioteca.py --accion aprender --ajustes app/ajustes.json  (la IA lee los nuevos: procesos, preguntas, términos)

Lo usan: la transcripción (Scribe y Whisper escriben bien tus palabras), el guion y el tráiler (el diccionario y tus
videos parecidos al nuevo), y «🧠 Conocimiento» (procesos y preguntas que aprende la IA).
"""
import argparse, collections, glob, json, math, os, re, subprocess, sys, tempfile, time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import conocimiento  # noqa: E402

CARPETA = os.path.join(conocimiento.CARPETA, 'transcripciones')
DICC = os.path.join(conocimiento.CARPETA, 'diccionario.json')
DICC_MD = os.path.join(conocimiento.CARPETA, 'DICCIONARIO.md')
ESTADO = os.path.join(conocimiento.CARPETA, '.biblioteca.json')
LOG = os.path.join(conocimiento.CARPETA, '.biblioteca_log.txt')
VACIAS = set('''a al algo ahi ahora asi bien como con cual de del desde donde el ella en entonces es esa ese eso esta este esto
hay hasta la las le les lo los me mas mi muy nada no nos o otra otro para pero por porque que se si sin solo su sus te tambien
tiene todo tu un una uno va vamos y ya yo aqui vez van ver hacer puede'''.split())


def log(x):
    print(x, flush=True)


def estado():
    try:
        return json.load(open(ESTADO, encoding='utf-8'))
    except (OSError, ValueError):
        return {'videos': {}, 'aprendidos': []}


def guardar_estado(e):
    os.makedirs(conocimiento.CARPETA, exist_ok=True)
    json.dump(e, open(ESTADO + '.tmp', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(ESTADO + '.tmp', ESTADO)


def guardar_transcripcion(vid, titulo, url, fecha, texto, origen):
    os.makedirs(CARPETA, exist_ok=True)
    cab = f'TÍTULO: {titulo}\nLINK: {url}\nFECHA: {fecha or "?"}\nORIGEN: {origen}\n\n'
    open(os.path.join(CARPETA, vid + '.txt'), 'w', encoding='utf-8').write(cab + texto.strip() + '\n')


def leer_transcripcion(vid):
    t = open(os.path.join(CARPETA, vid + '.txt'), encoding='utf-8').read()
    cab, _, cuerpo = t.partition('\n\n')
    datos = dict(x.split(': ', 1) for x in cab.splitlines() if ': ' in x)
    return datos, cuerpo


def transcripciones():
    out = []
    for f in sorted(glob.glob(os.path.join(CARPETA, '*.txt'))):
        try:
            d, cuerpo = leer_transcripcion(os.path.splitext(os.path.basename(f))[0])
            out.append({'id': os.path.splitext(os.path.basename(f))[0], 'titulo': d.get('TÍTULO', ''), 'url': d.get('LINK', ''),
                        'fecha': d.get('FECHA', ''), 'texto': cuerpo})
        except OSError:
            pass
    return out


# ---------- juntar: las transcripciones de todo el canal ----------

def _alimentacion():
    sys.path.insert(0, os.path.join(RAIZ, 'alimentacion'))
    import alimentacion
    return alimentacion


def desde_alimentacion(e):
    """Lo que «📚 Alimentación» ya leyó (mis_estilos/*/analisis/*.json) no se vuelve a bajar."""
    n = 0
    for f in glob.glob(os.path.join(RAIZ, 'mis_estilos', '*', 'analisis', '*.json')):
        try:
            a = json.load(open(f, encoding='utf-8'))
        except (OSError, ValueError):
            continue
        m = re.search(r'(?:v=|youtu\.be/|shorts/)([\w-]{11})', a.get('fuente') or '')
        if not m or not (a.get('texto') or '').strip() or m.group(1) in e['videos']:
            continue
        vid = m.group(1)
        guardar_transcripcion(vid, a.get('titulo', vid), f'https://youtu.be/{vid}', '', a['texto'], 'alimentación')
        e['videos'][vid] = {'titulo': a.get('titulo', vid), 'origen': 'alimentación'}
        n += 1
    return n


def lista_canal(canal):
    """Los videos del canal: con YouTube conectado, por la API (todos); si no, con yt-dlp desde el link del canal."""
    try:
        sys.path.insert(0, os.path.join(RAIZ, 'youtube'))
        import youtube
        aj = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8'))
        c = youtube.config(aj)
        if (c.get('token') or {}).get('refresh'):
            vs = youtube.mis_videos(c, maximo=2000)
            return [{'id': v['id'], 'titulo': v['titulo'], 'fecha': v['publicado']} for v in vs]
    except Exception as x:
        log(f'· no pude listar con la API de YouTube ({x}); pruebo con el link del canal')
    if not canal:
        raise RuntimeError('Conecta YouTube en «▶️ YouTube» o escribe el link de tu canal (youtube.com/@tucanal).')
    al = _alimentacion()
    return [{'id': al.id_youtube(v['url']), 'titulo': v['titulo'], 'fecha': ''} for v in al.videos_del_canal(canal, 5000)]


def subtitulos_youtube(vid, carpeta):
    """Solo los subtítulos en español (los tuyos o los automáticos), sin bajar el video."""
    al = _alimentacion()
    subprocess.run(al.yt_dlp() + ['--skip-download', '--write-subs', '--write-auto-subs', '--sub-langs', 'es.*,es', '--sub-format', 'vtt',
                                  '--sleep-requests', '1', '-o', os.path.join(carpeta, vid + '.%(ext)s'), f'https://www.youtube.com/watch?v={vid}'],
                   capture_output=True, text=True)
    vtts = sorted((x for x in os.listdir(carpeta) if x.startswith(vid + '.') and x.endswith('.vtt')), key=lambda x: ('orig' not in x, len(x)))
    return ' '.join(t for _, t in al.leer_vtt(os.path.join(carpeta, vtts[0]))) if vtts else ''


def whisper_youtube(vid, carpeta):
    """Sin subtítulos: baja solo el audio y lo transcribe Whisper en tu PC (gratis, unos minutos por video)."""
    al = _alimentacion()
    destino = os.path.join(carpeta, vid + '.m4a')
    subprocess.run(al.yt_dlp() + ['-f', 'ba[ext=m4a]/ba', '-o', destino, f'https://www.youtube.com/watch?v={vid}'], capture_output=True, text=True)
    if not os.path.exists(destino):
        return ''
    sys.path.insert(0, os.path.join(RAIZ, 'transcripcion'))
    import transcribir as tr
    try:
        pal = tr.whisper(tr.audio(destino), 'es', 'small')
    except SystemExit:
        return ''
    return ' '.join(t for _, _, t in tr.frases(pal))


def juntar(canal='', usar_whisper=False):
    e = estado()
    n = desde_alimentacion(e)
    if n:
        log(f'· {n} transcripciones de «📚 Alimentación»')
    guardar_estado(e)
    videos = lista_canal(canal)
    faltan = [v for v in videos if v['id'] not in e['videos'] or (usar_whisper and e['videos'][v['id']].get('origen') == 'sin subtítulos')]
    log(f'Tu canal tiene {len(videos)} videos; faltan {len(faltan)} en la biblioteca.')
    with tempfile.TemporaryDirectory() as tmp:
        for k, v in enumerate(faltan, 1):
            texto, origen = subtitulos_youtube(v['id'], tmp), 'subtítulos de YouTube'
            if not texto and usar_whisper:
                log(f'[{k}/{len(faltan)}] {v["titulo"]}: sin subtítulos, lo transcribe Whisper…')
                texto, origen = whisper_youtube(v['id'], tmp), 'Whisper'
            if texto:
                guardar_transcripcion(v['id'], v['titulo'], f'https://youtu.be/{v["id"]}', v.get('fecha', ''), texto, origen)
                log(f'[{k}/{len(faltan)}] ✓ {v["titulo"]}')
            else:
                origen = 'sin subtítulos'
                log(f'[{k}/{len(faltan)}] · {v["titulo"]}: sin subtítulos' + ('' if usar_whisper else ' (marca «Whisper» para transcribirlo)'))
            e['videos'][v['id']] = {'titulo': v['titulo'], 'fecha': v.get('fecha', ''), 'origen': origen}
            if k % 10 == 0:
                guardar_estado(e)
    e['ultima'] = time.strftime('%Y-%m-%d %H:%M')
    guardar_estado(e)
    diccionario_sin_ia()
    log(f'✓ Biblioteca: {len(transcripciones())} videos transcritos.')


# ---------- diccionario ----------

def leer_diccionario():
    try:
        return json.load(open(DICC, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def guardar_diccionario(d):
    os.makedirs(conocimiento.CARPETA, exist_ok=True)
    json.dump(d, open(DICC + '.tmp', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(DICC + '.tmp', DICC)
    filas = sorted(d.values(), key=lambda x: (x.get('tipo') == 'detectado', -x.get('videos', 0), x['termino'].lower()))
    md = ['# Diccionario del canal', '', '> Cómo se escribe cada nombre en tus videos. Lo usan la transcripción, el guion y la voz.',
          '> Corrige aquí: la app respeta lo que escribas en «escritura» de diccionario.json.', '']
    for tipo in ('modelo', 'herramienta', 'sigla', 'web', 'proceso', 'otro', 'detectado'):
        xs = [x for x in filas if x.get('tipo', 'otro') == tipo]
        if xs:
            md += [f'## {tipo.capitalize()}s' if tipo != 'detectado' else '## Detectados sin IA (por revisar)', '']
            md += [f"- **{x['termino']}**" + (f" — {x['nota']}" if x.get('nota') else '') + f" ({x.get('videos', 0)} videos)" for x in xs]
            md.append('')
    open(DICC_MD, 'w', encoding='utf-8').write('\n'.join(md))


def diccionario_sin_ia():
    """Gratis: las palabras con mayúsculas o números que repites en varios videos (FRP, G24, UnlockTool, 3uTools…)."""
    en_videos = collections.Counter()
    forma = {}
    for t in transcripciones():
        vistos = set()
        for w in re.findall(r'\b(?=\w*[A-Z0-9])[\w.\-]*[A-Za-z][\w.\-]*\b', t['texto']):
            w = w.strip('.-')
            if len(w) < 2 or w.lower() in VACIAS or (w[0].isupper() and w[1:].islower() and len(w) < 5):
                continue  # «Hola», «Ahora»: mayúscula de comienzo de frase
            k = w.lower()
            if k not in vistos:
                vistos.add(k)
                en_videos[k] += 1
                forma.setdefault(k, collections.Counter())[w] += 1
    d = leer_diccionario()
    for k, n in en_videos.items():
        if n < 2:
            continue
        if k in d:
            d[k]['videos'] = max(d[k].get('videos', 0), n)
        else:
            d[k] = {'termino': forma[k].most_common(1)[0][0], 'tipo': 'detectado', 'videos': n}
    guardar_diccionario(d)
    return d


def terminos(n=200, sin_detectados=False):
    d = leer_diccionario()
    xs = sorted(d.values(), key=lambda x: (x.get('tipo') == 'detectado', -x.get('videos', 0)))
    return [x.get('escritura') or x['termino'] for x in xs if not (sin_detectados and x.get('tipo') == 'detectado')][:n]


# ---------- aprender: la IA lee los videos nuevos ----------

PEDIDO = """Lees transcripciones de videos de un canal de tutoriales de reparación y desbloqueo de celulares. Saca solo lo que
se DICE en ellas, sin inventar. Contesta SOLO con este JSON:
{"terminos": [{"termino": "como se escribe bien (UnlockTool, 3uTools, Moto G24, xiaomiunlock.com)", "tipo": "modelo|herramienta|sigla|web|proceso|otro",
               "nota": "qué es, en pocas palabras", "oido_como": "cómo lo escribió mal la transcripción, si pasó"}],
 "procesos": [{"nombre": "Modo DFU en iPhone 11", "pasos": "los pasos en una o dos líneas", "video": "título"}],
 "preguntas": [{"pregunta": "lo que el autor dice que la gente pregunta o una duda que aclara", "respuesta": "lo que dice"}]}

TRANSCRIPCIONES:
"""


def lotes(videos, largo=60000):
    lote, n = [], 0
    for v in videos:
        txt = f"\n### {v['titulo']}\n{v['texto'][:20000]}\n"
        if lote and n + len(txt) > largo:
            yield lote
            lote, n = [], 0
        lote.append((v, txt))
        n += len(txt)
    if lote:
        yield lote


def pendientes():
    hechos = set(estado().get('aprendidos', []))
    return [t for t in transcripciones() if t['id'] not in hechos]


def aprender(ajustes_f):
    sys.path.insert(0, os.path.join(RAIZ, 'ia'))
    import ia
    aj = json.load(open(ajustes_f, encoding='utf-8'))
    if not (aj.get('modelo') and aj.get('url')):
        raise SystemExit('ERROR: hace falta una IA en «⚙ Ajustes IA».')
    vs = pendientes()
    ias = ias_que_aprenden(ia, aj)
    log(f'{" + ".join(n for n, _ in ias)} leen {len(vs)} videos nuevos ({sum(len(v["texto"]) for v in vs):,} letras).'.replace(',', '.'))
    d = leer_diccionario()
    notas = 0
    for k, lote in enumerate(lotes(vs), 1):
        log(f'[{k}] {len(lote)} videos…')
        if not ias:
            log('· ninguna IA puede seguir (clave, permiso o saldo): los videos que faltan quedan para la próxima vez.')
            break
        respuestas = pedir_a_todas(ia, ias, PEDIDO + ''.join(t for _, t in lote))
        for nombre, r in respuestas:
            notas += sumar(d, r, nombre if len(ias) > 1 else '')
        if not respuestas:  # ninguna contestó: este grupo no cuenta como leído y se vuelve a intentar la próxima vez
            continue
        guardar_diccionario(d)
        e = estado()
        e['aprendidos'] = sorted(set(e.get('aprendidos', [])) | {v['id'] for v, _ in lote})
        guardar_estado(e)
    textos = [t['texto'].lower() for t in transcripciones()]
    for x in d.values():  # en cuántos videos se nombra cada término
        k = x['termino'].lower()
        x['videos'] = sum(k in t for t in textos) or x.get('videos', 0)
    guardar_diccionario(d)
    log(f'✓ Diccionario: {len(d)} términos. {notas} notas nuevas en «🧠 Conocimiento».')


def ias_que_aprenden(ia, aj):
    """[(nombre, ajustes)]: tu IA principal y, con «🧠 Aprender con varias IAs a la vez», también GPT, Claude, Gemini y
    DeepSeek si tienen clave y modelo en «⚙ Ajustes IA». Cada una gasta lo suyo."""
    out = [(aj.get('proveedor') or 'IA principal', aj)]
    if aj.get('aprender_varias'):
        for ide, a2 in ia.ias_del_guion({**aj, 'tres_ia': True}):
            if (a2.get('url'), a2.get('modelo')) != (aj.get('url'), aj.get('modelo')):
                out.append((ia.IAS_GUION[ide][0], a2))
    return out


def pedir_a_todas(ia, ias, texto):
    """El mismo pedido a cada IA a la vez; devuelve [(nombre, respuesta)] de las que contestaron."""
    from concurrent.futures import ThreadPoolExecutor

    def una(par):
        nombre, aj2 = par
        try:
            return nombre, ia.extraer_json(ia.llamar(aj2, texto, []))
        except (Exception, SystemExit) as x:  # una IA que falla (o corta su respuesta) no frena a las otras
            log(f'· {nombre} no pudo con este grupo: {x}')
            if getattr(x, 'permanente', False):  # clave, permiso, saldo o política: no se le vuelve a pedir en esta lectura
                log(f'· {nombre} queda fuera hasta la próxima lectura (el error no se arregla repitiendo).')
                ias.remove(par)
            return nombre, None
    with ThreadPoolExecutor(len(ias)) as hilos:
        return [(n, r) for n, r in hilos.map(una, list(ias)) if isinstance(r, dict)]


def sumar(d, r, quien=''):
    """Lo que contestó una IA: términos al diccionario, procesos y preguntas a «🧠 Conocimiento» (sin repetir)."""
    notas = 0
    firma = f' [{quien}]' if quien else ''
    md = conocimiento.leer(conocimiento.VIDEOS) or conocimiento.PLANTILLA_VIDEOS  # aparte de tu CONOCIMIENTO.md
    for t in (r.get('terminos') or []) if isinstance(r, dict) else []:
        nombre = (t.get('termino') or '').strip()
        if not nombre or len(nombre) > 60:
            continue
        x = d.setdefault(nombre.lower(), {'termino': nombre, 'videos': 0})
        if x.get('tipo') in (None, 'detectado'):
            x.update(termino=nombre, tipo=t.get('tipo') or 'otro')
        if t.get('nota') and not x.get('nota'):
            x['nota'] = t['nota'][:160]
        if t.get('oido_como'):
            x.setdefault('oido_como', [])
            if t['oido_como'] not in x['oido_como']:
                x['oido_como'].append(t['oido_como'][:60])
    for p in (r.get('procesos') or []) if isinstance(r, dict) else []:
        if p.get('nombre') and p.get('pasos'):
            md, n = conocimiento.anotar('proceso', f"{p['nombre']}: {p['pasos']} (video «{p.get('video', '')}»){firma}", md)
            notas += n
    for p in (r.get('preguntas') or []) if isinstance(r, dict) else []:
        if p.get('pregunta'):
            md, n = conocimiento.anotar('pregunta', p['pregunta'] + (f" → {p['respuesta']}" if p.get('respuesta') else '') + firma, md)
            notas += n
    conocimiento.escribir(conocimiento.VIDEOS, md)
    return notas


# ---------- usar: tus videos parecidos al nuevo ----------

def _palabras(t):
    import unicodedata
    t = unicodedata.normalize('NFD', t.lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return [w for w in re.findall(r'[a-z0-9]{3,}', t) if w not in VACIAS]


def parecidos(texto, n=2):
    """Tus videos que más se parecen a este texto (palabras raras en común pesan más)."""
    ts = transcripciones()
    if not ts or not texto.strip():
        return []
    docs = [collections.Counter(_palabras(t['titulo'] + ' ' + t['titulo'] + ' ' + t['texto'])) for t in ts]
    df = collections.Counter(w for d in docs for w in d)
    q = collections.Counter(_palabras(texto))
    idf = {w: math.log(len(ts) / df[w]) for w in q if df.get(w)}
    puntos = []
    for t, d in zip(ts, docs):
        s = sum(idf[w] * min(q[w], 3) * math.log(1 + d[w]) for w in idf if w in d) / math.sqrt(1 + sum(d.values()) / 500)
        puntos.append((s, t))
    puntos.sort(key=lambda x: -x[0])
    return [t for s, t in puntos[:n] if s > 0]


def texto_para_ia(d=None, limite=4000):
    """Lo que se suma al pedido de la IA: el diccionario y, para un proyecto, tus 2 videos más parecidos."""
    partes = []
    ts = terminos(120)
    if ts:
        partes.append('DICCIONARIO DEL CANAL (escribe estos nombres exactamente así): ' + ', '.join(ts))
    if d:
        consulta = ''
        for f in ('idea.txt', 'transcripcion.txt'):
            try:
                consulta += open(os.path.join(d, f), encoding='utf-8').read()[:4000] + '\n'
            except OSError:
                pass
        for t in parecidos(consulta):
            partes.append(f"UN VIDEO TUYO PARECIDO («{t['titulo']}», {t['url']}). Cómo lo explicaste (úsalo para el estilo y los "
                          f"datos que ya confirmaste; no copies frases enteras):\n{t['texto'][:limite // 2]}")
    return '\n\n'.join(partes)[:limite + 1500]


def resumen():
    e, d = estado(), leer_diccionario()
    ts = transcripciones()
    return {'videos': len(ts), 'sin_subtitulos': sum(1 for v in e['videos'].values() if v.get('origen') == 'sin subtítulos'),
            'pendientes_ia': len(pendientes()), 'letras_pendientes': sum(len(t['texto']) for t in pendientes()),
            'terminos': len(d), 'terminos_ia': sum(1 for x in d.values() if x.get('tipo') != 'detectado'), 'ultima': e.get('ultima', ''),
            'ruta': conocimiento.CARPETA}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--accion', required=True, choices=['juntar', 'aprender', 'diccionario'])
    ap.add_argument('--canal', default='')
    ap.add_argument('--whisper', action='store_true')
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    a = ap.parse_args()
    try:
        if a.accion == 'juntar':
            juntar(a.canal, a.whisper)
        elif a.accion == 'aprender':
            aprender(a.ajustes)
        else:
            diccionario_sin_ia()
    except RuntimeError as e:
        sys.exit(f'✗ {e}')


if __name__ == '__main__':
    main()
