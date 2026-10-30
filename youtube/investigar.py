"""«🔎 Investigar el tema» (pedido de fabian, 30/10/2026): antes de proponer títulos, mirar qué funciona afuera.

1. Arma las frases del tema con la marca, el modelo y el problema del video (nombre del proyecto, idea.txt y guion).
2. Google y YouTube: lo que la gente escribe en cada buscador (autocompletar, gratis, sin cuota).
3. YouTube: los videos con más vistas del tema (del último año y de siempre), con su canal, vistas, vistas por día y sus
   etiquetas. Gasta cuota de la API: unas 100 unidades por búsqueda (hace 4; tu cuota diaria es 10.000).
4. Tu canal: lo que buscaron en YouTube para llegar a tus videos (YouTube Analytics, últimos 90 días).
5. Baja las miniaturas de los 8 videos que más vistas por día juntan y la IA de «⚙ Ajustes IA» las mira junto con todo
   lo anterior: palabras clave, cómo son los títulos ganadores, qué tienen las miniaturas, qué canales compiten y qué
   oportunidad hay (un pedido a la IA con imágenes: centavos).

Deja todo en youtube/investigacion.json y las miniaturas en youtube/investigacion/. «✨ Proponer con IA» lo usa solo.

    python investigar.py --proyecto mis_proyectos/NOMBRE [--sin-ia]
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))
import youtube  # noqa: E402

PROBLEMAS = [(r'icloud|activaci[oó]n|hello', ('quitar icloud {modelo}', 'bypass icloud {marca} 2026')),
             (r'\bmdm\b', ('quitar mdm {modelo}', '{marca} mdm bypass')),
             (r'patr[oó]n|contrase[ñn]a|pin\b', ('quitar patron {modelo}', 'desbloquear {marca} olvide contraseña')),
             (r'\bfrp\b|cuenta (de )?google', ('eliminar cuenta google {marca}', 'quitar cuenta google {modelo}',
                                               '{marca} frp 2026', '{marca} frp bypass'))]


def avisar(texto):
    print(texto, flush=True)


def json_url(url, timeout=12):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}),
                                             timeout=timeout).read().decode('utf-8', errors='replace'))


def autocompletar(q, youtube_=False, hl='es'):
    """Lo que la gente escribe en el buscador (Google o YouTube) empezando por esa frase. Gratis, sin cuota."""
    p = {'client': 'firefox', 'q': q, 'hl': hl}
    if youtube_:
        p['ds'] = 'yt'
    try:
        return [x for x in json_url('https://suggestqueries.google.com/complete/search?' + urllib.parse.urlencode(p))[1][:10]]
    except Exception:
        return []


def tema(d, modelo_tuyo=''):
    """(marca, modelo, frases de búsqueda) del video."""
    import conocimiento
    nombre = os.path.basename(os.path.abspath(d))
    marca = (conocimiento.marca_de_proyecto(d) or nombre.split()[0]).lower()
    modelo = (modelo_tuyo or re.sub(r'[_\-]+', ' ', nombre)).strip().lower()  # el que escribiste, o el nombre del proyecto
    if modelo_tuyo:
        marca = modelo.split()[0]
    texto = ''
    for f in ('idea.txt',):
        try:
            texto += open(os.path.join(d, f), encoding='utf-8').read() + ' '
        except OSError:
            pass
    try:
        texto += ' '.join(str(b.get('texto') or '') for b in json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))['bloques'])
    except (OSError, ValueError, KeyError):
        pass
    # el problema que más se nombra (no el primero que aparece: un video de FRP también dice «contraseña» alguna vez)
    cuenta = [len(re.findall(rx, nombre + ' ' + texto, re.I)) * (3 if rx == PROBLEMAS[-1][0] else 1) for rx, _ in PROBLEMAS]
    frases = PROBLEMAS[max(range(len(PROBLEMAS)), key=lambda k: (cuenta[k], k))][1] if max(cuenta) else PROBLEMAS[-1][1]
    semillas = []
    for f in frases:
        s = f.format(marca=marca, modelo=modelo)
        if s not in semillas:
            semillas.append(s)
    return marca, modelo, semillas


def buscar(c, q, orden='viewCount', despues=None, n=25):
    p = {'part': 'snippet', 'q': q, 'type': 'video', 'order': orden, 'maxResults': n, 'relevanceLanguage': 'es'}
    if despues:
        p['publishedAfter'] = despues
    return [x['id']['videoId'] for x in youtube.pedir(c, 'GET', youtube.API + '/search', p).get('items', []) if x.get('id', {}).get('videoId')]


def detalles(c, ids):
    out = []
    for i in range(0, len(ids), 50):
        r = youtube.pedir(c, 'GET', youtube.API + '/videos', {'part': 'snippet,statistics,contentDetails', 'id': ','.join(ids[i:i + 50])})
        for x in r.get('items', []):
            s, st = x['snippet'], x.get('statistics', {})
            pub = s.get('publishedAt', '')[:10]
            try:
                dias = max(1.0, (time.time() - time.mktime(time.strptime(pub, '%Y-%m-%d'))) / 86400)
            except ValueError:
                dias = 365.0
            vistas = int(st.get('viewCount') or 0)
            mini = (s.get('thumbnails', {}).get('high') or s.get('thumbnails', {}).get('medium') or {}).get('url', '')
            out.append({'id': x['id'], 'titulo': s.get('title', ''), 'canal': s.get('channelTitle', ''), 'canal_id': s.get('channelId', ''),
                        'publicado': pub, 'vistas': vistas, 'por_dia': round(vistas / dias, 1), 'likes': int(st.get('likeCount') or 0),
                        'comentarios': int(st.get('commentCount') or 0), 'duracion': x.get('contentDetails', {}).get('duration', ''),
                        'etiquetas': (s.get('tags') or [])[:25], 'miniatura': mini})
    return out


def busquedas_de_mi_canal(c, dias=90):
    """Lo que buscaron en YouTube para llegar a tus videos (YouTube Analytics)."""
    hoy = lambda n: time.strftime('%Y-%m-%d', time.localtime(time.time() - n * 86400))
    try:
        r = youtube.pedir(c, 'GET', youtube.ANALYTICS, {'ids': 'channel==MINE', 'startDate': hoy(dias), 'endDate': hoy(1),
                                                           'dimensions': 'insightTrafficSourceDetail',
                                                           'filters': 'insightTrafficSourceType==YT_SEARCH', 'metrics': 'views',
                                                           'sort': '-views', 'maxResults': 25})
        return [{'busqueda': f[0], 'vistas': int(f[1])} for f in r.get('rows') or []]
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    ap.add_argument('--modelo', default='', help='el modelo a buscar (si el nombre del proyecto no es el modelo exacto)')
    ap.add_argument('--sin-ia', action='store_true', help='solo junta los datos, sin el resumen de la IA')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    aj = json.load(open(a.ajustes, encoding='utf-8'))
    marca, modelo, semillas = tema(d, a.modelo)
    avisar(f'· [5%] Tema: {", ".join(semillas)}')
    # 1. los buscadores (gratis)
    google, yt = {}, {}
    for s in semillas:
        google[s] = autocompletar(s)
        yt[s] = autocompletar(s, youtube_=True)
    avisar('· [20%] Leí lo que se escribe en Google y en YouTube sobre el tema')
    # 2. los videos que más funcionan (API de YouTube)
    c = youtube.config(aj)
    videos, mi_canal, propias = [], '', []
    if (c.get('token') or {}).get('refresh'):
        try:
            mi_canal = youtube.canal(c).get('id', '')
        except Exception:
            mi_canal = ''
        ids = []
        hace_un_ano = time.strftime('%Y-%m-%dT00:00:00Z', time.gmtime(time.time() - 365 * 86400))
        for k, (q, orden, despues) in enumerate([(semillas[0], 'viewCount', hace_un_ano), (semillas[-1], 'viewCount', hace_un_ano),
                                                 (semillas[0], 'viewCount', None), (semillas[min(1, len(semillas) - 1)], 'relevance', None)]):
            try:
                ids += [i for i in buscar(c, q, orden, despues) if i not in ids]
            except youtube.ErrorYT as e:
                avisar(f'· YouTube no dejó buscar «{q}»: {e}')
                break
            avisar(f'· [{25 + 10 * k}%] Busqué en YouTube «{q}»')
        videos = detalles(c, ids) if ids else []
        propias = busquedas_de_mi_canal(c)
    else:
        avisar('· YouTube no está conectado: solo uso los buscadores (conéctalo en «▶️ YouTube» para ver los videos que más funcionan)')
    for v in videos:
        v['tuyo'] = bool(mi_canal) and v['canal_id'] == mi_canal
    # solo los del tema: que nombren la marca o el bloqueo (la búsqueda de YouTube también trae «cómo cambiar tu contraseña»…)
    clave = re.compile(r'\b(' + re.escape(marca) + r'|frp|bypass|icloud|mdm|desbloque\w*)\b', re.I)
    del_tema = [v for v in videos if clave.search(v['titulo'])]
    videos = del_tema if len(del_tema) >= 5 else videos
    videos.sort(key=lambda v: -v['por_dia'])
    canales = {}
    for v in videos:
        x = canales.setdefault(v['canal'], {'canal': v['canal'], 'videos': 0, 'vistas': 0, 'tuyo': v['tuyo']})
        x['videos'] += 1
        x['vistas'] += v['vistas']
    canales = sorted(canales.values(), key=lambda x: -x['vistas'])[:10]
    etiquetas = {}
    for v in videos[:30]:
        for e in v['etiquetas']:
            k = e.strip().lower()
            if k:
                etiquetas[k] = etiquetas.get(k, 0) + 1
    etiquetas = [{'etiqueta': k, 'videos': n} for k, n in sorted(etiquetas.items(), key=lambda x: -x[1])[:30]]
    # 3. las miniaturas de los que más vistas por día juntan
    carpeta = os.path.join(d, 'youtube', 'investigacion')
    os.makedirs(carpeta, exist_ok=True)
    caps = []
    for v in [v for v in videos if not v['tuyo']][:8]:
        f = os.path.join(carpeta, v['id'] + '.jpg')
        try:
            if not os.path.exists(f) and v['miniatura']:
                urllib.request.urlretrieve(v['miniatura'], f)
            caps.append((f"{v['titulo']} · {v['canal']} · {v['vistas']} vistas", f))
        except Exception:
            pass
    avisar(f'· [65%] Encontré {len(videos)} videos del tema y bajé {len(caps)} miniaturas de los que más funcionan')
    datos = {'fecha': time.strftime('%Y-%m-%d %H:%M'), 'marca': marca, 'modelo': modelo, 'frases': semillas,
             'google': google, 'youtube_sugerencias': yt, 'mis_busquedas': propias, 'videos': videos[:40],
             'canales': canales, 'etiquetas': etiquetas, 'miniaturas': [os.path.basename(f) for _, f in caps]}
    # 4. lo que la IA saca de todo eso
    if not a.sin_ia and aj.get('modelo') and aj.get('url'):
        import ia
        lista = '\n'.join(f"- {v['titulo']} | {v['canal']} | {v['vistas']} vistas | {v['por_dia']} por día | {v['publicado']}"
                          + (' | (TUYO)' if v['tuyo'] else '') for v in videos[:25])
        try:  # lo que fabian ya enseñó: qué procesos necesitan PC (Honor sí): nunca prometer «SIN PC» si la necesita
            pc = json.load(open(os.path.join(RAIZ, 'mis_conocimientos', 'procesos_pc.json'), encoding='utf-8')).get(marca, True) is not False
        except (OSError, ValueError):
            pc = True
        pedido = (('OJO, REGLA DEL AUTOR: este proceso NECESITA PC. Nunca propongas «SIN PC» ni lo prometas (aunque la competencia lo use). '
                   if pc else '') +
                  f'Eres el estratega de YouTube del canal Xiaomiunlock (tutoriales de desbloqueo de celulares, en español). '
                  f'El próximo video es de: {modelo} ({", ".join(semillas)}). Estos son los datos REALES de hoy:\n\n'
                  f'VIDEOS DEL TEMA QUE MÁS FUNCIONAN (título | canal | vistas | vistas por día | fecha):\n{lista or "(no hay)"}\n\n'
                  f'LO QUE LA GENTE ESCRIBE EN YOUTUBE: {json.dumps(yt, ensure_ascii=False)}\n'
                  f'LO QUE LA GENTE ESCRIBE EN GOOGLE: {json.dumps(google, ensure_ascii=False)}\n'
                  f'LO QUE BUSCARON PARA LLEGAR A LOS VIDEOS DEL CANAL (90 días): {json.dumps(propias[:20], ensure_ascii=False)}\n'
                  f'ETIQUETAS QUE MÁS USAN ESOS VIDEOS: {json.dumps(etiquetas[:20], ensure_ascii=False)}\n\n'
                  'Las imágenes son las miniaturas de los videos que más vistas por día juntan, en el mismo orden. '
                  'Analiza todo y responde SOLO con JSON: {"palabras_clave": ["las 10 a 15 que más se buscan, en orden"], '
                  '"titulos": "cómo son los títulos que ganan (largo, palabras, año, signos) en 2 o 3 frases", '
                  '"miniaturas": "qué tienen en común las miniaturas que más funcionan (colores, texto, teléfono, caras, flechas) en 2 o 3 frases", '
                  '"competencia": "qué canales dominan y qué hacen", "oportunidad": "qué hueco hay para destacar", '
                  '"ideas_titulo": ["5 títulos para este video, de 100 letras o menos, que usen lo que funciona sin copiar"]}')
        avisar('· [75%] La IA está mirando los títulos y las miniaturas…')
        try:
            r = ia.extraer_json(ia.llamar(dict(aj, imagenes=True), pedido, caps))
            r = r if isinstance(r, dict) else {}
            if pc:  # por si igual lo propone
                for k in ('palabras_clave', 'ideas_titulo'):
                    r[k] = [x for x in (r.get(k) or []) if not re.search(r'\bsin\s*pc\b', str(x), re.I)]
            datos['resumen'] = r
        except Exception as e:
            avisar(f'· la IA no pudo hacer el resumen ({e}); quedan los datos igual')
    json.dump(datos, open(os.path.join(d, 'youtube', 'investigacion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    avisar('· [100%] Listo: investigación guardada')
    print(json.dumps({'ok': True, 'videos': len(videos), 'miniaturas': len(caps)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
