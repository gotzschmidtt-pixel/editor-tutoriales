"""«📊 Todo tu canal»: la app aprende de las estadísticas de TODOS tus videos (gratis, sin IA) y se lo pasa a la IA.

Con YouTube conectado baja, de cada video del canal: vistas, likes, comentarios, duración, cuánto se mira en promedio
(% y segundos), suscriptores que trajo y la curva de retención (qué parte de la gente sigue en cada 1 % del video).
Las curvas se guardan en mis_conocimientos/youtube_canal/ y solo se vuelven a bajar las de los videos de los últimos
60 días (las viejas casi no cambian). Con todo eso escribe ESTADISTICAS_CANAL.md:
  - qué videos y títulos funcionan mejor (vistas por día) y qué palabras de título se repiten en los mejores;
  - cuánta gente se va en los primeros 30 segundos y en qué parte del video suele caer la retención;
  - qué duración retiene mejor, y cómo le va a cada marca;
  - y unas reglas cortas que la IA cumple al escribir el guion, el tráiler y el título.
Se actualiza solo una vez por semana al abrir la app, o con «📊 Aprender de todo mi canal» en ▶️ YouTube.
No gasta créditos de IA: son cuentas de la PC. La cuota de YouTube que usa es mínima (Analytics tiene la suya aparte).
"""
import collections, json, math, os, re, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))
import youtube  # noqa: E402
import conocimiento  # noqa: E402

CARPETA = os.path.join(conocimiento.CARPETA, 'youtube_canal')
CURVAS = os.path.join(CARPETA, 'curvas')
DATOS = os.path.join(CARPETA, 'videos.json')
INFORME = os.path.join(conocimiento.CARPETA, 'ESTADISTICAS_CANAL.md')
SHORT_MAX = 180          # segundos: hasta aquí es un Short
DIAS_REFRESCAR = 60      # las curvas de videos más nuevos que esto se vuelven a bajar
VACIAS = set('''de la el en y a con sin para por tu tus un una los las del al que o mi se es como 2026 2025 2024 2023 -
| ya no lo le su todo todos'''.split())


def _seg(iso):
    m = re.match(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    return sum(int(v or 0) * k for v, k in zip(m.groups(), (86400, 3600, 60, 1))) if m else 0


def _videos(c, avance):
    """Todos los videos del canal con duración y contadores (Data API, ~1 unidad cada 50 videos)."""
    r = youtube.pedir(c, 'GET', youtube.API + '/channels', {'part': 'contentDetails', 'mine': 'true'})
    lista = r['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    ids, token = [], None
    while True:
        p = {'part': 'contentDetails', 'playlistId': lista, 'maxResults': 50}
        if token:
            p['pageToken'] = token
        r = youtube.pedir(c, 'GET', youtube.API + '/playlistItems', p)
        ids += [x['contentDetails']['videoId'] for x in r.get('items', [])]
        token = r.get('nextPageToken')
        if not token:
            break
    avance(f'{len(ids)} videos en el canal')
    out = {}
    for i in range(0, len(ids), 50):
        r = youtube.pedir(c, 'GET', youtube.API + '/videos', {'part': 'snippet,contentDetails,statistics,status', 'id': ','.join(ids[i:i + 50])})
        for x in r.get('items', []):
            if x['status'].get('privacyStatus') != 'public':
                continue
            st = x['statistics']
            out[x['id']] = {'id': x['id'], 'titulo': x['snippet']['title'], 'publicado': x['snippet'].get('publishedAt', '')[:10],
                            'segundos': _seg(x['contentDetails'].get('duration')), 'vistas': int(st.get('viewCount') or 0),
                            'likes': int(st.get('likeCount') or 0), 'comentarios': int(st.get('commentCount') or 0)}
    return out


def _analytics(c, videos):
    """Cuánto se mira cada video (% y segundos promedio) y cuántos suscriptores trajo. YouTube da de una vez los 200 más
    vistos; el resto se pide por lista de videos (50 por pedido)."""
    base = {'ids': 'channel==MINE', 'startDate': '2015-01-01', 'endDate': time.strftime('%Y-%m-%d'), 'dimensions': 'video',
            'metrics': 'views,averageViewDuration,averageViewPercentage,subscribersGained'}

    def poner(r):
        for vid, _, dur, pct, subs in r.get('rows') or []:
            if vid in videos:
                videos[vid].update(visto_s=round(dur), visto_pct=round(pct, 1), subs=int(subs))
    poner(youtube.pedir(c, 'GET', youtube.ANALYTICS, dict(base, sort='-views', maxResults=200)))
    faltan = [v for v in videos if 'visto_pct' not in videos[v]]
    for i in range(0, len(faltan), 50):
        poner(youtube.pedir(c, 'GET', youtube.ANALYTICS, dict(base, filters='video==' + ','.join(faltan[i:i + 50]))))


def _curvas(c, videos, avance):
    """Las curvas que faltan, varias a la vez (cada pedido a Analytics tarda unos segundos) y solo desde que se publicó
    cada video (pedir desde 2015 hacía cada pedido mucho más lento)."""
    from concurrent.futures import ThreadPoolExecutor
    os.makedirs(CURVAS, exist_ok=True)
    hoy = time.time()
    youtube.acceso(c)  # el token, una sola vez antes de abrir los hilos
    pendientes = []
    for v in videos.values():
        f = os.path.join(CURVAS, v['id'] + '.json')
        try:
            edad = (hoy - time.mktime(time.strptime(v['publicado'], '%Y-%m-%d'))) / 86400
        except ValueError:
            edad = 999
        if os.path.exists(f) and (edad > DIAS_REFRESCAR or hoy - os.path.getmtime(f) < 6 * 86400):
            continue
        if v['segundos'] <= SHORT_MAX:
            continue  # en los Shorts la retención se mide distinto: no se usa para el guion
        pendientes.append(v)
    avance(f'retención: faltan {len(pendientes)} videos…')
    hechos = [0]

    def una(v):
        try:
            curva = youtube.retencion(c, v['id'], desde=v['publicado'] or '2015-01-01')
        except youtube.ErrorYT as e:
            avance(f'· {v["titulo"][:40]}: {e}')
            return
        json.dump(curva, open(os.path.join(CURVAS, v['id'] + '.json'), 'w', encoding='utf-8'))
        hechos[0] += 1
        if hechos[0] % 10 == 0:
            avance(f'retención: {hechos[0]} de {len(pendientes)} videos…')
    with ThreadPoolExecutor(8) as hilos:
        list(hilos.map(una, pendientes))
    return hechos[0]


def leer_curva(vid):
    try:
        return json.load(open(os.path.join(CURVAS, vid + '.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []


def _en(curva, t):
    """Qué parte de la gente sigue mirando en la fracción t del video (interpolado)."""
    if not curva:
        return None
    for a, b in zip(curva, curva[1:]):
        if a['t'] <= t <= b['t']:
            return a['mira'] + (b['mira'] - a['mira']) * (t - a['t']) / ((b['t'] - a['t']) or 1)
    return curva[-1]['mira'] if t > curva[-1]['t'] else curva[0]['mira']


def _mmss(s):
    return f'{int(s) // 60}:{int(s) % 60:02d}'


def _prom(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _palabras(t):
    return [w for w in re.findall(r'[a-záéíóúñü0-9]+', t.lower()) if w not in VACIAS and len(w) > 2]


def analizar(videos):
    """Las cuentas que salen de todos tus videos (sin IA)."""
    hoy = time.time()
    largos, shorts = [], []
    for v in videos.values():
        try:
            dias = max(1.0, (hoy - time.mktime(time.strptime(v['publicado'], '%Y-%m-%d'))) / 86400)
        except ValueError:
            dias = 1.0
        v['dias'] = round(dias)
        v['por_dia'] = round(v['vistas'] / dias, 1)
        (shorts if v['segundos'] <= SHORT_MAX else largos).append(v)
    a = {'videos': len(videos), 'largos': len(largos), 'shorts': len(shorts),
         'vistas': sum(v['vistas'] for v in videos.values()), 'fecha': time.strftime('%Y-%m-%d %H:%M')}
    # para comparar justo: solo videos con al menos 14 días (los nuevos todavía no juntaron vistas)
    base = sorted([v for v in largos if v['dias'] >= 14], key=lambda v: -v['por_dia'])
    a['mejores'] = [{k: v.get(k) for k in ('titulo', 'id', 'por_dia', 'vistas', 'visto_pct', 'segundos', 'publicado')} for v in base[:10]]
    a['peores'] = [{k: v.get(k) for k in ('titulo', 'id', 'por_dia', 'vistas', 'visto_pct', 'segundos', 'publicado')} for v in base[-5:]] if len(base) > 15 else []
    a['visto_pct'] = _prom([v.get('visto_pct') for v in largos])
    # inicio: cuánta gente queda a los 30 s, en los mejores y en el resto
    def a_los(v, s):
        cur = leer_curva(v['id'])
        return _en(cur, s / v['segundos']) if cur and v['segundos'] > s * 2 else None
    cuarto = max(1, len(base) // 4)
    a['quedan_30s'] = _prom([a_los(v, 30) for v in largos])
    a['quedan_30s_mejores'] = _prom([a_los(v, 30) for v in base[:cuarto]])
    a['quedan_30s_resto'] = _prom([a_los(v, 30) for v in base[cuarto:]])
    a['quedan_60s'] = _prom([a_los(v, 60) for v in largos])
    a['curva_media'] = [round(_prom([_en(leer_curva(v['id']), t / 10) for v in largos]) or 0, 3) for t in range(11)]
    # dónde se cae: el tramo (después del inicio) donde más gente se va de golpe, en promedio
    caidas = collections.Counter()
    for v in largos:
        cur = leer_curva(v['id'])
        if len(cur) < 20:
            continue
        pasos = [(cur[i]['t'], cur[i - 3]['mira'] - cur[i]['mira']) for i in range(8, len(cur) - 3)]  # sin el 8 % del inicio ni el final
        t, caida = max(pasos, key=lambda x: x[1])
        caidas[round(t * 10) * 10] += 1
    a['caidas'] = [{'en_pct': k, 'videos': n} for k, n in caidas.most_common(4)]
    # duración: qué largo se mira más
    tramos = [(0, 300, 'menos de 5 min'), (300, 480, '5 a 8 min'), (480, 720, '8 a 12 min'), (720, 1200, '12 a 20 min'), (1200, 99999, 'más de 20 min')]
    a['duracion'] = []
    for d0, d1, nombre in tramos:
        g = [v for v in base if d0 <= v['segundos'] < d1]
        if len(g) >= 3:
            a['duracion'].append({'tramo': nombre, 'videos': len(g), 'por_dia': round(_prom([v['por_dia'] for v in g]), 1),
                                  'visto_pct': round(_prom([v.get('visto_pct') for v in g]) or 0, 1)})
    # palabras de título que más se repiten en el mejor cuarto frente al resto
    arriba, abajo = base[:cuarto], base[cuarto:]
    ca, cb = collections.Counter(), collections.Counter()
    for v in arriba:
        ca.update(set(_palabras(v['titulo'])))
    for v in abajo:
        cb.update(set(_palabras(v['titulo'])))
    lift = [(w, (ca[w] / len(arriba)) / ((cb[w] + 1) / (len(abajo) + 1))) for w in ca if ca[w] >= max(2, len(arriba) // 6)]
    a['palabras_titulo'] = [{'palabra': w, 'veces_mejores': ca[w], 'cuanto_mas': round(x, 1)} for w, x in sorted(lift, key=lambda x: -x[1])[:12] if x > 1.2]
    # por marca
    marcas = collections.defaultdict(list)
    for v in base:
        palabras = set(re.findall(r'[a-z0-9]+', v['titulo'].lower()))
        for m in conocimiento.MARCAS_BASE:
            if any(x in palabras for x in conocimiento.ALIAS.get(m, [m.lower()])):
                marcas[m].append(v)
    a['marcas'] = sorted([{'marca': m, 'videos': len(g), 'por_dia': round(_prom([v['por_dia'] for v in g]), 1),
                           'visto_pct': round(_prom([v.get('visto_pct') for v in g]) or 0, 1)} for m, g in marcas.items() if len(g) >= 2],
                         key=lambda x: -x['por_dia'])
    a['subs_mejores'] = [{'titulo': v['titulo'], 'subs': v.get('subs', 0)} for v in sorted(largos, key=lambda v: -(v.get('subs') or 0))[:5]]
    a['reglas'] = reglas(a)
    return a


def reglas(a):
    """Lo que la IA tiene que cumplir, en frases cortas y con los números de TU canal."""
    r = []
    if a.get('quedan_30s') is not None:
        se_van = round((1 - a['quedan_30s']) * 100)
        r.append(f'En los primeros 30 segundos se va el {se_van} % de la gente (promedio de tus videos). El gancho tiene que '
                 'mostrar el resultado (el teléfono ya libre) y decir en una frase qué modelo y qué problema resuelve, sin rodeos.')
        if a.get('quedan_30s_mejores') and a.get('quedan_30s_resto') and a['quedan_30s_mejores'] - a['quedan_30s_resto'] > 0.03:
            r.append(f"Tus videos que más funcionan retienen {round(a['quedan_30s_mejores'] * 100)} % a los 30 s contra "
                     f"{round(a['quedan_30s_resto'] * 100)} % del resto: el inicio es lo que más diferencia hace.")
    if a.get('caidas'):
        donde = ' y el '.join(f"{x} %" for x in sorted(x['en_pct'] for x in a['caidas'][:2]))
        r.append(f'La caída más fuerte (después del inicio) suele estar entre el {donde} del video: ahí no pongas esperas '
                 'largas ni explicaciones; adelanta lo que viene («en un momento verás…») o muestra un avance.')
    if a.get('duracion'):
        mejor = max([x for x in a['duracion'] if x['videos'] >= 10] or a['duracion'], key=lambda x: x['por_dia'])  # con pocos videos no es regla
        r.append(f"Los videos de {mejor['tramo']} son los que más vistas por día juntan en tu canal "
                 f"({mejor['por_dia']} por día, se mira el {mejor['visto_pct']} %).")
    if a.get('palabras_titulo'):
        r.append('Palabras que más aparecen en los títulos de tus mejores videos: '
                 + ', '.join(f"«{x['palabra']}»" for x in a['palabras_titulo'][:8]) + '. Úsalas en el título si son verdad para este video.')
    if a.get('marcas'):
        r.append('Marcas que mejor te van (vistas por día): ' + ', '.join(f"{x['marca']} ({x['por_dia']})" for x in a['marcas'][:4]) + '.')
    return r


def escribir_informe(a):
    L = [f"# Estadísticas de todo el canal · {a['fecha']}", '',
         f"> Las saca la app de YouTube Analytics (sin IA). {a['videos']} videos públicos ({a['largos']} largos, {a['shorts']} Shorts), "
         f"{a['vistas']:,} vistas en total.".replace(',', '.'), '', '## Reglas para la IA (con los números de este canal)']
    L += [f'- {x}' for x in a['reglas']] or ['- (faltan datos)']
    L += ['', '## Tus mejores videos (vistas por día, con al menos 14 días)']
    L += [f"- {v['titulo']} · {v['por_dia']}/día · {v['vistas']} vistas · se mira el {v.get('visto_pct') or '?'} % · {_mmss(v['segundos'])}" for v in a['mejores']]
    if a['peores']:
        L += ['', '## Los que menos funcionaron']
        L += [f"- {v['titulo']} · {v['por_dia']}/día · se mira el {v.get('visto_pct') or '?'} %" for v in a['peores']]
    L += ['', '## Retención']
    if a.get('quedan_30s') is not None:
        L.append(f"- A los 30 s queda el {round(a['quedan_30s'] * 100)} % · al minuto, el {round((a.get('quedan_60s') or 0) * 100)} %.")
    if a.get('visto_pct'):
        L.append(f"- En promedio se mira el {round(a['visto_pct'])} % de cada video largo.")
    L.append('- Curva media (0 % → 100 % del video): ' + ' · '.join(f'{round(x * 100)} %' for x in a['curva_media']))
    for x in a['caidas']:
        L.append(f"- Caída fuerte cerca del {x['en_pct']} % del video en {x['videos']} videos.")
    if a['duracion']:
        L += ['', '## Duración']
        L += [f"- {x['tramo']}: {x['videos']} videos · {x['por_dia']} vistas por día · se mira el {x['visto_pct']} %" for x in a['duracion']]
    if a['palabras_titulo']:
        L += ['', '## Palabras de título en tus mejores videos']
        L += [f"- «{x['palabra']}» · en {x['veces_mejores']} de los mejores · {x['cuanto_mas']}× más que en el resto" for x in a['palabras_titulo']]
    if a['marcas']:
        L += ['', '## Por marca']
        L += [f"- {x['marca']}: {x['videos']} videos · {x['por_dia']} vistas por día · se mira el {x['visto_pct']} %" for x in a['marcas']]
    if a['subs_mejores']:
        L += ['', '## Los que más suscriptores trajeron']
        L += [f"- {x['titulo']} · +{x['subs']}" for x in a['subs_mejores']]
    conocimiento.escribir(INFORME, '\n'.join(L) + '\n')


DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


def mejor_dia(c, dias=120):
    """Qué día de la semana se ven más tus videos (promedio de los últimos 120 días). La hora exacta YouTube no la da por
    la API: está en YouTube Studio → Estadísticas → Audiencia → «Cuándo están tus espectadores en YouTube»."""
    hasta = time.strftime('%Y-%m-%d', time.localtime(time.time() - 86400))
    desde = time.strftime('%Y-%m-%d', time.localtime(time.time() - dias * 86400))
    r = youtube.pedir(c, 'GET', youtube.ANALYTICS, {'ids': 'channel==MINE', 'startDate': desde, 'endDate': hasta,
                                                    'dimensions': 'day', 'metrics': 'views', 'sort': 'day'})
    por = collections.defaultdict(list)
    for dia, vistas in r.get('rows') or []:
        por[time.strptime(dia, '%Y-%m-%d').tm_wday].append(vistas)
    prom = {d: sum(v) / len(v) for d, v in por.items() if v}
    if not prom:
        return None
    orden = sorted(prom, key=lambda d: -prom[d])
    media = sum(prom.values()) / len(prom)
    return {'mejor': DIAS[orden[0]], 'segundo': DIAS[orden[1]] if len(orden) > 1 else '',
            'por_dia': {DIAS[d]: round(prom[d]) for d in range(7) if d in prom},
            'diferencia_pct': round((prom[orden[0]] / media - 1) * 100) if media else 0}


def aprender(c, avance=print):
    """Todo el proceso: baja lo que falta, hace las cuentas y escribe ESTADISTICAS_CANAL.md. Devuelve el análisis."""
    os.makedirs(CARPETA, exist_ok=True)
    avance('Leo la lista de videos del canal…')
    videos = _videos(c, avance)
    avance('Leo cuánto se mira cada video (YouTube Analytics)…')
    _analytics(c, videos)
    avance('Bajo las curvas de retención (solo las que faltan o son de videos nuevos)…')
    n = _curvas(c, videos, avance)
    json.dump(videos, open(DATOS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    a = analizar(videos)
    try:
        a['mejor_dia'] = mejor_dia(c)
    except youtube.ErrorYT as e:
        avance(f'· no pude leer las vistas por día: {e}')
    if a.get('mejor_dia'):
        m = a['mejor_dia']
        a['reglas'].append(f"Tu público mira más los {m['mejor']} y los {m['segundo']} ({m['diferencia_pct']} % más que el "
                           'promedio): programa los videos para publicarse el día antes o temprano ese día.')
    escribir_informe(a)
    json.dump(a, open(os.path.join(CARPETA, 'analisis.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    avance(f'Listo: {a["videos"]} videos analizados ({n} curvas nuevas). Informe en {INFORME}')
    return a


def ultimo():
    try:
        return json.load(open(os.path.join(CARPETA, 'analisis.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return None


def texto_para_ia(limite=2500):
    """Lo que se suma al pedido de la IA: las reglas con los números del canal y los títulos que mejor funcionaron."""
    a = ultimo()
    if not a or not conocimiento.usar():
        return ''
    t = ('LO QUE DICEN LAS ESTADÍSTICAS DE TODO EL CANAL DEL AUTOR (YouTube Analytics, ' + a['fecha'][:10] + '):\n'
         + '\n'.join(f'- {x}' for x in a['reglas'])
         + '\nTítulos que más vistas por día juntaron: ' + ' | '.join(v['titulo'] for v in a['mejores'][:6]))
    return t[:limite]
