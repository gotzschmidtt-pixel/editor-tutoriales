"""«▶️ YouTube»: tu canal conectado a la app, sin librerías extra (solo la API de Google por HTTPS).

Se conecta una vez: creas un «cliente OAuth de escritorio» gratis en Google Cloud (ver youtube/LEEME.md), lo subes a la
app y das permiso con tu cuenta. La app guarda el permiso en «youtube» de ajustes.json (nunca sale de tu PC) y con él:
- sube el video programado, con título, descripción y capítulos, etiquetas, subtítulos y miniatura;
- deja escrito un comentario (fijarlo lo haces tú en YouTube: la API no lo permite);
- baja la retención de cada video y los comentarios, para aprender y proponer ideas.
"""
import json, os, re, secrets, time, urllib.error, urllib.parse, urllib.request

AUTH = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN = 'https://oauth2.googleapis.com/token'
API = 'https://www.googleapis.com/youtube/v3'
SUBIR = 'https://www.googleapis.com/upload/youtube/v3'
ANALYTICS = 'https://youtubeanalytics.googleapis.com/v2/reports'
PERMISOS = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.force-ssl',
            'https://www.googleapis.com/auth/yt-analytics.readonly']


class ErrorYT(Exception):
    pass


def config(aj):
    c = aj.get('youtube')
    return c if isinstance(c, dict) else {}


def guardar_cliente(c, texto):
    """El JSON que baja Google Cloud («client_secret_….json»), de tipo «App de escritorio»."""
    try:
        j = json.loads(texto)
    except ValueError:
        raise ErrorYT('Ese archivo no es el JSON del cliente OAuth que baja Google Cloud.')
    x = j.get('installed') or j.get('web') or j
    if not (x.get('client_id') and x.get('client_secret')):
        raise ErrorYT('Al JSON le falta client_id o client_secret: baja el de un cliente OAuth de tipo «App de escritorio».')
    if 'web' in j:
        raise ErrorYT('Ese cliente es de tipo «Aplicación web». Crea uno de tipo «App de escritorio» (ver la guía).')
    c['cliente'] = {'client_id': x['client_id'], 'client_secret': x['client_secret']}
    c.pop('token', None)


def url_permiso(c, redirect):
    c['estado'] = secrets.token_urlsafe(16)
    q = {'client_id': c['cliente']['client_id'], 'redirect_uri': redirect, 'response_type': 'code', 'scope': ' '.join(PERMISOS),
         'access_type': 'offline', 'prompt': 'consent', 'state': c['estado'], 'include_granted_scopes': 'true'}
    return AUTH + '?' + urllib.parse.urlencode(q)


def _pedir_token(datos):
    try:
        r = urllib.request.urlopen(urllib.request.Request(TOKEN, data=urllib.parse.urlencode(datos).encode()), timeout=30)
        return json.load(r)
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode(errors='replace')
        if 'invalid_grant' in cuerpo:
            raise ErrorYT('Google ya no acepta el permiso guardado (se venció o lo quitaste). Vuelve a «Conectar YouTube».')
        raise ErrorYT(f'Google no dio el permiso ({e.code}): {cuerpo[:300]}')


def canjear(c, code, estado, redirect):
    if not estado or estado != c.pop('estado', None):
        raise ErrorYT('El permiso no vino de esta app (estado distinto). Vuelve a pulsar «Conectar YouTube».')
    t = _pedir_token({'code': code, 'client_id': c['cliente']['client_id'], 'client_secret': c['cliente']['client_secret'],
                      'redirect_uri': redirect, 'grant_type': 'authorization_code'})
    if not t.get('refresh_token'):
        raise ErrorYT('Google no mandó el permiso permanente. Quita la app en myaccount.google.com/permissions y conecta otra vez.')
    c['token'] = {'refresh': t['refresh_token'], 'acceso': t['access_token'], 'vence': time.time() + t.get('expires_in', 3600) - 60}


def acceso(c):
    t = c.get('token') or {}
    if not t.get('refresh'):
        raise ErrorYT('YouTube no está conectado: pulsa «Conectar YouTube».')
    if t.get('acceso') and t.get('vence', 0) > time.time():
        return t['acceso']
    n = _pedir_token({'refresh_token': t['refresh'], 'client_id': c['cliente']['client_id'],
                      'client_secret': c['cliente']['client_secret'], 'grant_type': 'refresh_token'})
    t.update(acceso=n['access_token'], vence=time.time() + n.get('expires_in', 3600) - 60)
    c['_cambio'] = True  # quien llamó guarda el token nuevo en ajustes.json
    return t['acceso']


def pedir(c, metodo, url, params=None, cuerpo=None, datos=None, tipo='application/json', cabeceras=None, crudo=False):
    if params:
        url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
    h = {'Authorization': 'Bearer ' + acceso(c), **(cabeceras or {})}
    if cuerpo is not None:
        datos, tipo = json.dumps(cuerpo).encode(), 'application/json; charset=UTF-8'
    if datos is not None:
        h['Content-Type'] = tipo
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=datos, method=metodo, headers=h), timeout=300)
        if crudo:
            return r
        texto = r.read()
        return json.loads(texto) if texto.strip() else {}
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode(errors='replace')
        try:
            err = json.loads(cuerpo)['error']
            motivo = (err.get('errors') or [{}])[0].get('reason', '')
            msg = err.get('message', cuerpo)
        except (ValueError, KeyError, TypeError):
            motivo, msg = '', cuerpo[:300]
        raise ErrorYT(EXPLICAR.get(motivo, f'YouTube contestó {e.code}: {msg}'))


EXPLICAR = {
    'quotaExceeded': 'Se acabó la cuota diaria de la API de YouTube (unas 6 subidas por día). Vuelve a intentar mañana.',
    'uploadLimitExceeded': 'YouTube no te deja subir más videos hoy. Prueba mañana.',
    'forbidden': 'YouTube no dio permiso para esto. Si es la miniatura: verifica tu canal con tu teléfono en youtube.com/verify.',
    'insufficientPermissions': 'Falta un permiso. Vuelve a «Conectar YouTube» y marca todas las casillas.',
    'accessNotConfigured': 'Falta activar la API en Google Cloud: «YouTube Data API v3» y «YouTube Analytics API» (ver la guía).',
    'commentsDisabled': 'Los comentarios de ese video están desactivados.',
}


def canal(c):
    r = pedir(c, 'GET', API + '/channels', {'part': 'snippet,statistics', 'mine': 'true'})
    if not r.get('items'):
        raise ErrorYT('Esa cuenta de Google no tiene canal de YouTube.')
    x = r['items'][0]
    return {'id': x['id'], 'titulo': x['snippet']['title'], 'suscriptores': x['statistics'].get('subscriberCount'),
            'videos': x['statistics'].get('videoCount')}


def subir_video(c, ruta, meta, avance=None):
    """Subida reanudable en trozos de 8 MB: un corte de internet no obliga a empezar de cero el trozo anterior."""
    estado = {'privacyStatus': meta.get('privacidad', 'private'), 'selfDeclaredMadeForKids': False}
    if meta.get('publicar_en'):  # programado: queda privado hasta esa hora y YouTube lo publica solo
        estado.update(privacyStatus='private', publishAt=meta['publicar_en'])
    cuerpo = {'snippet': {'title': meta['titulo'][:100], 'description': meta.get('descripcion', '')[:5000],
                          'tags': meta.get('etiquetas', [])[:30], 'categoryId': meta.get('categoria', '28'),
                          'defaultLanguage': 'es', 'defaultAudioLanguage': 'es'}, 'status': estado}
    largo = os.path.getsize(ruta)
    r = pedir(c, 'POST', SUBIR + '/videos', {'uploadType': 'resumable', 'part': 'snippet,status'}, cuerpo=cuerpo,
              cabeceras={'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': str(largo)}, crudo=True)
    destino, hecho, TROZO = r.headers['Location'], 0, 8 * 1024 * 1024
    with open(ruta, 'rb') as f:
        while hecho < largo:
            f.seek(hecho)
            datos = f.read(TROZO)
            fin = hecho + len(datos) - 1
            for intento in range(5):
                try:
                    q = urllib.request.Request(destino, data=datos, method='PUT', headers={
                        'Authorization': 'Bearer ' + acceso(c), 'Content-Type': 'video/mp4',
                        'Content-Range': f'bytes {hecho}-{fin}/{largo}'})
                    r = urllib.request.urlopen(q, timeout=300)
                    return json.load(r)['id']  # 200/201: era el último trozo
                except urllib.error.HTTPError as e:
                    if e.code == 308:  # trozo recibido, sigue el próximo
                        rango = e.headers.get('Range')
                        hecho = int(rango.split('-')[1]) + 1 if rango else hecho
                        break
                    if e.code < 500 or intento == 4:
                        raise ErrorYT(f'La subida se cortó ({e.code}): {e.read().decode(errors="replace")[:300]}')
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    if intento == 4:
                        raise ErrorYT('Se cortó internet durante la subida. Vuelve a pulsar «Publicar».')
                time.sleep(2 ** intento)
            if avance:
                avance(hecho / largo)
    raise ErrorYT('La subida terminó sin que YouTube diera el id del video.')


def _multipart(meta, datos, tipo):
    limite = 'estudio' + secrets.token_hex(8)
    cuerpo = (f'--{limite}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n'
              f'--{limite}\r\nContent-Type: {tipo}\r\n\r\n').encode() + datos + f'\r\n--{limite}--\r\n'.encode()
    return cuerpo, f'multipart/related; boundary={limite}'


def subir_subtitulos(c, video, idioma, nombre, srt_texto):
    cuerpo, tipo = _multipart({'snippet': {'videoId': video, 'language': idioma, 'name': nombre}}, srt_texto.encode('utf-8'),
                              'application/octet-stream')
    return pedir(c, 'POST', SUBIR + '/captions', {'uploadType': 'multipart', 'part': 'snippet'}, datos=cuerpo, tipo=tipo)


def subir_miniatura(c, video, ruta):
    tipo = 'image/png' if ruta.lower().endswith('.png') else 'image/jpeg'
    if os.path.getsize(ruta) > 2 * 1024 * 1024:
        raise ErrorYT('La miniatura pesa más de 2 MB, el máximo de YouTube.')
    return pedir(c, 'POST', SUBIR + '/thumbnails/set', {'videoId': video}, datos=open(ruta, 'rb').read(), tipo=tipo)


def comentar(c, video, texto):
    return pedir(c, 'POST', API + '/commentThreads', {'part': 'snippet'},
                 cuerpo={'snippet': {'videoId': video, 'topLevelComment': {'snippet': {'textOriginal': texto[:9000]}}}})


def id_de(url):
    m = re.search(r'(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})', url or '') or re.fullmatch(r'\s*([\w-]{11})\s*', url or '')
    if not m:
        raise ErrorYT('No reconozco ese link de YouTube.')
    return m.group(1)


def video(c, vid):
    r = pedir(c, 'GET', API + '/videos', {'part': 'snippet,contentDetails,statistics,status', 'id': vid})
    if not r.get('items'):
        raise ErrorYT('No encontré ese video (¿es de tu canal?).')
    x = r['items'][0]
    dur = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', x['contentDetails']['duration'])
    seg = sum(int(v or 0) * k for v, k in zip(dur.groups(), (3600, 60, 1))) if dur else 0
    return {'id': vid, 'titulo': x['snippet']['title'], 'publicado': x['snippet'].get('publishedAt', ''), 'segundos': seg,
            'vistas': x['statistics'].get('viewCount'), 'likes': x['statistics'].get('likeCount'),
            'comentarios': x['statistics'].get('commentCount'), 'estado': x['status'].get('privacyStatus')}


def retencion(c, vid, desde='2015-01-01'):
    """La curva de retención: cada 1 % del video, qué parte de la gente sigue mirando y cómo está frente a videos parecidos
    (relativa: 1 = normal, más = mejor). YouTube tarda uno o dos días en tenerla."""
    r = pedir(c, 'GET', ANALYTICS, {'ids': 'channel==MINE', 'startDate': desde, 'endDate': time.strftime('%Y-%m-%d'),
                                    'metrics': 'audienceWatchRatio,relativeRetentionPerformance',
                                    'dimensions': 'elapsedVideoTimeRatio', 'filters': f'video=={vid}'})
    return [{'t': f[0], 'mira': f[1], 'relativa': f[2]} for f in r.get('rows') or []]


def comentarios(c, vid=None, canal_id=None, maximo=300):
    """Los comentarios principales (sin respuestas), los más nuevos primero."""
    out, token = [], None
    while len(out) < maximo:
        p = {'part': 'snippet', 'maxResults': 100, 'order': 'time', 'textFormat': 'plainText'}
        p.update({'videoId': vid} if vid else {'allThreadsRelatedToChannelId': canal_id})
        if token:
            p['pageToken'] = token
        r = pedir(c, 'GET', API + '/commentThreads', p)
        for x in r.get('items', []):
            s = x['snippet']['topLevelComment']['snippet']
            out.append({'texto': s.get('textDisplay', '')[:600], 'likes': s.get('likeCount', 0), 'video': x['snippet'].get('videoId'),
                        'respuestas': x['snippet'].get('totalReplyCount', 0), 'fecha': s.get('publishedAt', '')[:10]})
        token = r.get('nextPageToken')
        if not token:
            break
    return out[:maximo]


def sin_responder(c, canal_id, maximo=40, revisar=300):
    """Los comentarios más nuevos del canal que nadie respondió todavía (ni tú ni otros)."""
    out, token, vistos = [], None, 0
    while len(out) < maximo and vistos < revisar:
        p = {'part': 'snippet', 'maxResults': 100, 'order': 'time', 'textFormat': 'plainText', 'allThreadsRelatedToChannelId': canal_id}
        if token:
            p['pageToken'] = token
        r = pedir(c, 'GET', API + '/commentThreads', p)
        for x in r.get('items', []):
            vistos += 1
            s = x['snippet']['topLevelComment']['snippet']
            if x['snippet'].get('totalReplyCount', 0) or s.get('authorChannelId', {}).get('value') == canal_id:
                continue
            out.append({'id': x['snippet']['topLevelComment']['id'], 'video': x['snippet'].get('videoId'),
                        'autor': s.get('authorDisplayName', ''), 'texto': s.get('textDisplay', '')[:600],
                        'fecha': s.get('publishedAt', '')[:10], 'likes': s.get('likeCount', 0)})
        token = r.get('nextPageToken')
        if not token:
            break
    return out[:maximo]


def responder(c, comentario_id, texto):
    """Publica tu respuesta a un comentario (la app lo hace solo cuando pulsas «Publicar respuesta»)."""
    texto = (texto or '').strip()
    if not texto:
        raise ErrorYT('La respuesta está vacía.')
    r = pedir(c, 'POST', API + '/comments', {'part': 'snippet'}, cuerpo={'snippet': {'parentId': comentario_id, 'textOriginal': texto[:9000]}})
    return r.get('id')


def sugerencias(consulta):
    """Lo que la gente escribe en el buscador de YouTube empezando por esa frase (gratis, sin cuota)."""
    url = 'https://suggestqueries.google.com/complete/search?' + urllib.parse.urlencode({'client': 'firefox', 'ds': 'yt', 'q': consulta, 'hl': 'es'})
    try:
        return json.loads(urllib.request.urlopen(url, timeout=10).read().decode('utf-8', errors='replace'))[1][:10]
    except Exception:
        return []


def mis_videos(c, maximo=200):
    """Los videos del canal con sus vistas (para que la IA vea qué títulos funcionaron). Gasta poca cuota (~10 unidades)."""
    r = pedir(c, 'GET', API + '/channels', {'part': 'contentDetails', 'mine': 'true'})
    lista = r['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    ids, token = [], None
    while len(ids) < maximo:
        p = {'part': 'contentDetails', 'playlistId': lista, 'maxResults': 50}
        if token:
            p['pageToken'] = token
        r = pedir(c, 'GET', API + '/playlistItems', p)
        ids += [x['contentDetails']['videoId'] for x in r.get('items', [])]
        token = r.get('nextPageToken')
        if not token:
            break
    out = []
    for i in range(0, len(ids[:maximo]), 50):
        r = pedir(c, 'GET', API + '/videos', {'part': 'snippet,statistics', 'id': ','.join(ids[i:i + 50])})
        out += [{'id': x['id'], 'titulo': x['snippet']['title'], 'vistas': int(x['statistics'].get('viewCount') or 0),
                 'publicado': x['snippet'].get('publishedAt', '')[:10]} for x in r.get('items', [])]
    return out


# ---------- capítulos: cuándo empieza cada bloque del guion en el video terminado ----------

def _normal(s):
    import unicodedata
    s = unicodedata.normalize('NFD', (s or '').lower())
    return re.sub(r'[^a-z0-9ñ ]+', ' ', ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')).split()


def leer_srt(texto):
    out = []
    for parte in re.split(r'\n\s*\n', (texto or '').replace('\r', '')):
        m = re.search(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->', parte)
        if m:
            h, mi, s, ms = map(int, m.groups())
            linea = parte[m.end():].split('\n', 1)[1] if '\n' in parte[m.end():] else ''
            out.append((h * 3600 + mi * 60 + s + ms / 1000, ' '.join(linea.split())))
    return out


def inicio_bloques(bloques, srt_texto):
    """Para cada bloque, el segundo del video final en que se empieza a decir (buscando sus primeras palabras en los
    subtítulos del video final, así sirve aunque el tráiler o los testimonios corran todo)."""
    subs = [(t, _normal(x)) for t, x in leer_srt(srt_texto)]
    out, desde = {}, 0
    for b in bloques:
        palabras = _normal(b.get('texto'))[:4]
        if not palabras:
            continue
        for k in range(desde, len(subs)):
            junto = ' '.join(sum((w for _, w in subs[k:k + 3]), []))
            if junto.startswith(' '.join(palabras)) or ' '.join(subs[k][1][:len(palabras)]) == ' '.join(palabras):
                out[b['id']] = subs[k][0]
                desde = k + 1
                break
    return out


def hms(s):
    s = int(s)
    return f'{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}' if s >= 3600 else f'{s // 60}:{s % 60:02d}'


def texto_capitulos(capitulos, inicios):
    """[{'bloque','titulo'}] → «0:00 Título» por línea, como YouTube los pide: el primero en 0:00, al menos 3 y de 10 s o más."""
    filas = sorted(((inicios[c['bloque']], c['titulo']) for c in capitulos if c.get('bloque') in inicios), key=lambda x: x[0])
    limpias = []
    for t, titulo in filas:
        if limpias and t - limpias[-1][0] < 10:
            continue
        limpias.append([t, titulo.strip()[:80]])
    if limpias:
        limpias[0][0] = 0
    return '\n'.join(f'{hms(t)} {x}' for t, x in limpias) if len(limpias) >= 3 else ''
