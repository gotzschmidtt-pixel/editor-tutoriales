"""«🎵 Ritmo de la voz» (fabian, 14/11/2026): estilos de ritmo que se aplican a la voz YA GRABADA, sin regrabar ni gastar.

La voz de ElevenLabs (Mauricio, eleven_v4) habla a ~158 palabras por minuto y a fabian le sonaba «agresiva». Este módulo
corta la voz ya hecha en los puntos y las comas, le mete silencios como una persona real y la baja un poco de velocidad.
Cada estilo es una receta distinta, para elegir en «🎛 Audio e imagen» (edicion.json: "ritmo_voz"):

  antes       Sin pausas, como sale de ElevenLabs (~158 ppm).
  pausas_v2   Pausa de 1,0 s al final de cada frase, 0,3 s en cada coma, voz ×0,95 y 1,6 s entre párrafos (~118 ppm).
  humano      Como habla fabian (~120 ppm): frase ~0,8 s, coma solo tras ~8 palabras seguidas (~0,3 s), pausa semilarga
              ~1,4 s cada ~20 palabras, 1,6 s entre párrafos, voz ×0,97 (×0,93 en los pasos críticos: serial, KEY,
              Erase FRP; ×1,0 en los obvios: encender, conectar, esperar) y RESPIROS de 2 a 4 s donde la voz calla y
              la música sube (0,10 → 0,32): sin número fijo, uno cada ~45 s de voz como una narración humana. Todo varía un poco al azar con una semilla, para que no suene a bucle.

Estilos propios: mis_estilos/ritmos.json ({"mi_estilo": {"nombre": "...", "frase": 0.9, ...}}) con las mismas claves que
ESTILOS. Ahí va el estilo futuro calibrado con los videos más vistos del canal.

Cómo se aplica (sin regrabar):
- La voz que hizo ElevenLabs se guarda una sola vez en voz/_sin_ritmo/ (mp3 + align.json). El estilo siempre se calcula
  desde esa copia, así cambiar de estilo no suma pausas sobre pausas, y «antes» la devuelve tal cual.
- voz/<id>.mp3 y voz/<id>.align.json quedan con el ritmo (los tiempos de cada letra corridos), así subtítulos, etiquetas,
  «Alinear» y el montaje siguen a la voz nueva.
- voz/ritmo.json guarda qué estilo tiene cada bloque, la pausa de párrafo («cola») y los respiros. voz.ajustar_guion suma
  esa cola al largo de cada bloque y musica.py sube la música en los respiros.
- Un bloque puede pedir su propio respiro en guion.json: "respiro_s": 3 (0 = ninguno).
- MULTIMARCA: los pasos críticos y los momentos de respiro reconocen Honor, Huawei, Xiaomi, Samsung, Motorola, iPhone y
  lo general (MARCAS); se agregan palabras en mis_estilos/ritmo_marcas.json sin tocar el código.

Uso: python ritmo.py --proyecto CARPETA [--estilo humano] [--semilla 400]   (aplica y recalcula los tiempos del guion)
"""
import argparse, hashlib, json, os, random, re, shutil, subprocess, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
CRUDO = '_sin_ritmo'
ESTADO = 'ritmo.json'
DEFECTO = 'antes'
SEMILLA = 400
RESPIRO_CADA = 45  # segundos de voz entre respiros largos (provisorio: se calibra con narraciones humanas reales)
DESFASE, MARGEN = 0.3, 0.4  # como voz.py: entre dos voces ya hay 0,7 s de aire

BASE = {'frase': 0.0, 'coma': 0.0, 'min_coma': 0, 'larga': 0.0, 'cada': 0, 'parrafo': DESFASE + MARGEN,
        'vel': 1.0, 'vel_critico': None, 'vel_obvio': None, 'variar': False,
        'respiro_cada': 0, 'respiro_min': 2.0, 'respiro_max': 4.0, 'musica_respiro': 0.32, 'ppm': None, 'nota': ''}

ESTILOS = {
    'antes': dict(BASE, nombre='Antes (sin pausas)', ppm=158,
                  nota='La voz tal cual sale de ElevenLabs: rápida, sin pausas.'),
    'pausas_v2': dict(BASE, nombre='Pausas v2', ppm=118, frase=1.0, coma=0.3, vel=0.95, parrafo=1.6,
                      nota='Pausa en cada punto y coma, voz un poco más lenta. La que te gustó en el Honor 400 Lite («MUCHO MEJOR»).'),
    'humano': dict(BASE, nombre='Humano', ppm=120, frase=0.8, coma=0.3, min_coma=8, larga=1.4, cada=20, parrafo=1.6,
                   vel=0.97, vel_critico=0.93, vel_obvio=1.0, variar=True, respiro_cada=RESPIRO_CADA,
                   nota='Como hablas tú: tiradas de ~20 palabras, pausas variadas, más lento en serial/KEY/Erase FRP '
                        'y respiros de 2-4 s con la música arriba, tantos como una narración humana.'),
}
# lugar para el estilo calibrado con tus videos más vistos (se llena cuando se mida la retención por ritmo)
FUTUROS = {'canal': 'Calibrado con tus videos más vistos (próximamente)'}

# MULTIMARCA (fabian 14/11/2026: «que no quede solo para Honor sino multimarca»). Las palabras de todas las marcas valen
# siempre (no hace falta saber la marca del video). Se suman las tuyas en mis_estilos/ritmo_marcas.json:
#   {"MARCA": {"datos": ["palabra", ...], "modos": [...], "llega": [...], "accion_final": [...], "listo": [...]}}
MARCAS = {
    'general': {'datos': ['serial', 'key', 'keys', 'ki', 'clave', 'c[oó]digo', 'imei', 'pin', 'contrase\\w*', 'token', 'patr[oó]n'],
                'modos': ['recovery', 'modo seguro'],
                'llega': ['key', 'ki', 'c[oó]digo', 'token', 'clave', 'respuesta', 'desbloqueo'],
                'accion_final': ['reset frp', 'remove frp', 'unlock', 'desbloquear', 'flashear', 'start', 'iniciar'],
                'listo': ['no pide (ninguna )?cuenta', 'ya (puedes )?omitir', 'omitimos', 'qued[oó] libre', 'sin cuenta de google',
                          'desbloquead[oa]', 'pantalla de inicio', 'ya entra']},
    'honor': {'datos': ['erase\\s*frp', 'read\\s*fastboot'], 'modos': ['fastboot'], 'accion_final': ['erase\\s*frp']},
    'huawei': {'datos': ['erase\\s*frp', 'testpoint', 'test\\s*point'], 'modos': ['fastboot', 'upgrade mode']},
    'xiaomi': {'datos': ['mi account', 'cuenta mi', 'edl', 'test\\s*point', 'bootloader'], 'modos': ['edl', 'fastboot', 'sideload'],
               'accion_final': ['unlock', 'reset mi account', 'disable mi cloud']},
    'samsung': {'datos': ['\\*#0\\*#', 'adb', 'odin'], 'modos': ['modo descarga', 'download mode', 'modo test', 'modo prueba']},
    'motorola': {'datos': ['mtk', 'brom', 'preloader'], 'modos': ['brom', 'preloader', 'fastboot', 'bootloader']},
    'iphone': {'datos': ['ecid', 'udid', 'dfu', 'hello', 'bandas', 'jailbreak'], 'modos': ['dfu', 'recovery', 'pwndfu'],
               'accion_final': ['bypass', 'activar', 'jailbreak', 'liberar'], 'listo': ['pantalla de hello', 'ya (est[aá] )?liberado']},
}


def _marcas():
    todas = {k: {c: list(v) for c, v in d.items()} for k, d in MARCAS.items()}
    try:
        propias = json.load(open(os.path.join(RAIZ, 'mis_estilos', 'ritmo_marcas.json'), encoding='utf-8'))
    except (OSError, ValueError):
        propias = {}
    for k, d in (propias.items() if isinstance(propias, dict) else []):
        for c, v in (d.items() if isinstance(d, dict) else []):
            if c in ('datos', 'modos', 'llega', 'accion_final', 'listo') and isinstance(v, list):
                todas.setdefault(str(k).lower(), {}).setdefault(c, []).extend(re.escape(str(x)) for x in v if str(x).strip())
    return todas


def _lista(c):
    return '|'.join(sorted({x for d in _marcas().values() for x in d.get(c, [])}, key=len, reverse=True))


CRITICO_DATO = re.compile(r'\b(' + _lista('datos') + r')\b', re.I)
CRITICO_ACCION = re.compile(r'\b(cop\w+|peg\w+|campo|clic|aparece|termina en|mand\w+|escrib\w+|ingres\w+|marca\w*)\b', re.I)
OBVIO = re.compile(r'\b(enciend|encend|apag|conect|cable|esper|reinici|carg|desconect)', re.I)
# los momentos de un respiro, en el orden del proceso (fabian 14/11, para todas las marcas): entra al modo (fastboot,
# DFU, EDL, descarga, BROM…), llega la KEY/código, la acción final (Erase FRP, Unlock, Bypass…) y ya no pide cuenta
RESPIRO = [re.compile(p, re.I) for p in (
    r'\b(entramos|estamos|ya est\w+|aparece|vemos|entra|pasamos)\b[^.]{0,40}\b(' + _lista('modos') + r')\b(?!\s*(reader|info|tool))',
    r'(aqu[ií] est[aá]|ya (aparece|lleg\w*|la tenemos|tenemos|sali[oó])|obtuvimos|lleg[oó])[^.]{0,40}\b(' + _lista('llega')
    + r')\b|\b(' + _lista('llega') + r')\b[^.]{0,30}(ya aparece|lleg[oó]|lista|sali[oó])',
    r'clic en (' + _lista('accion_final') + r')|\b(' + _lista('accion_final') + r')\b[^.]{0,40}reinici',
    _lista('listo'))]


def estilos():
    """Los estilos de la app más los tuyos (mis_estilos/ritmos.json)."""
    out = {k: dict(v) for k, v in ESTILOS.items()}
    try:
        propios = json.load(open(os.path.join(RAIZ, 'mis_estilos', 'ritmos.json'), encoding='utf-8'))
    except (OSError, ValueError):
        propios = {}
    for k, v in (propios.items() if isinstance(propios, dict) else []):
        if isinstance(v, dict) and re.fullmatch(r'[\w-]{1,40}', str(k)):
            e = dict(BASE, nombre=str(k))
            e.update({c: x for c, x in v.items() if c in BASE or c == 'nombre'})
            out[k] = e
    return out


def elegido(proyecto):
    """(id, receta) del estilo del proyecto: edicion.json "ritmo_voz" (y "ritmo_semilla")."""
    try:
        e = json.load(open(os.path.join(proyecto, 'edicion.json'), encoding='utf-8'))
    except (OSError, ValueError):
        e = {}
    todos = estilos()
    k = e.get('ritmo_voz') if e.get('ritmo_voz') in todos else DEFECTO
    try:
        semilla = int(e.get('ritmo_semilla', SEMILLA))
    except (TypeError, ValueError):
        semilla = SEMILLA
    return k, todos[k], semilla


def _azar(semilla, bid):
    """Un azar fijo por bloque: cambiar un bloque no cambia las pausas de los demás."""
    return random.Random(int(hashlib.md5(f'{semilla}:{bid}'.encode()).hexdigest()[:12], 16))


def _var(r, est, x, menos, mas):
    return round(r.uniform(x - menos, x + mas), 2) if est['variar'] else x


def es_critico(b):
    mo = b.get('montaje') or {}
    t = str(b.get('texto') or '')
    return (str(b.get('tipo', '')).lower().startswith(('crit', 'clave')) or bool(mo.get('critico') or mo.get('datos'))
            or bool(CRITICO_DATO.search(t) and CRITICO_ACCION.search(t)))


def es_obvio(b):
    return not es_critico(b) and bool(OBVIO.search(str(b.get('texto') or '')))


def velocidad(b, est):
    if est.get('vel_critico') and es_critico(b):
        return est['vel_critico']
    if est.get('vel_obvio') and es_obvio(b):
        return est['vel_obvio']
    return est['vel']


def cortes(al, est, r):
    """[(segundo, pausa)] donde se corta la voz: fin de frase, coma (tras min_coma palabras) y semilarga cada ~cada palabras."""
    ch, s, e = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
    out, nw, nc = [], 0, 0
    tope = est['cada'] + (r.randint(-5, 6) if est['variar'] and est['cada'] else 0)
    for i, c in enumerate(ch[:-2]):
        if c == ' ':
            nw += 1
            nc += 1
        if ch[i + 1] != ' ' or i + 2 >= len(ch):
            continue
        if (c in '.?!:' and est['frase'] > 0 and not (i and ch[i - 1].isdigit())
                and (ch[i + 2].isupper() or ch[i + 2] in '¿¡')):
            larga = bool(est['cada']) and est['larga'] > 0 and nw >= tope
            p = _var(r, est, est['larga'], 0.3, 0.4) if larga else _var(r, est, est['frase'], 0.2, 0.25)
            out.append(((e[i] + s[i + 2]) / 2, p))
            nc = 0
            if larga:
                nw = 0
                tope = est['cada'] + (r.randint(-5, 6) if est['variar'] else 0)
        elif c in ',;' and est['coma'] > 0 and nc >= est['min_coma']:
            nc = 0
            out.append(((e[i] + s[i + 2]) / 2, _var(r, est, est['coma'], 0.1, 0.15)))
    return out


def aplicar_bloque(mp3, al, salida_mp3, salida_al, cts, vel):
    """Corta la voz en cada corte, mete el silencio y la pone a vel; corre los tiempos de cada letra igual."""
    partes, prev = [], 0.0
    for t, p in cts:
        partes.append((prev, t, p))
        prev = t
    partes.append((prev, None, 0))
    fc, lab = [], ''
    for k, (x, y, p) in enumerate(partes):
        tr = f'atrim={x:.3f}' + (f':{y:.3f}' if y else '')
        fc.append(f'[0:a]{tr},asetpts=PTS-STARTPTS' + (f',apad=pad_dur={p}' if p else '') + f'[p{k}]')
        lab += f'[p{k}]'
    fc.append(lab + f'concat=n={len(partes)}:v=0:a=1' + (f',atempo={vel}' if abs(vel - 1) > 1e-6 else '') + '[o]')
    tmp = salida_mp3 + '.tmp.mp3'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', mp3, '-filter_complex', ';'.join(fc), '-map', '[o]',
                    '-b:a', '160k', tmp], check=True)
    os.replace(tmp, salida_mp3)
    corre = lambda t: (t + sum(p for c, p in cts if t >= c)) / vel
    nuevo = dict(al)
    nuevo['character_start_times_seconds'] = [round(corre(x), 4) for x in al['character_start_times_seconds']]
    nuevo['character_end_times_seconds'] = [round(corre(x), 4) for x in al['character_end_times_seconds']]
    json.dump(nuevo, open(salida_al, 'w', encoding='utf-8'), ensure_ascii=False)


def elegir_respiros(bloques, est, semilla):
    """{id: segundos}: respiros de 2 a 4 s (distintos), sin un número fijo (fabian 14/11: «emular respiros promedio de
    narraciones humanas reales»): uno cada ~respiro_cada segundos de voz, con variación, primero en los momentos clave
    (entra al modo fastboot/DFU/EDL/descarga…, llega la KEY o el código, la acción final, ya no pide cuenta: todas las
    marcas) y el resto repartido. "respiro_s" en un bloque del guion manda (0 = ninguno)."""
    con_voz = [b for b in bloques if str(b.get('texto') or '').strip()]
    fijos = {b['id']: float(b['respiro_s']) for b in con_voz if isinstance(b.get('respiro_s'), (int, float))}
    out = {k: v for k, v in fijos.items() if v > 0}
    cada = float(est.get('respiro_cada') or 0)
    if cada <= 0 or len(con_voz) < 3:
        return out
    r = random.Random(semilla)
    pps = (est.get('ppm') or 120) / 60  # palabras por segundo del estilo
    t, ini = 0.0, []
    for b in con_voz:  # en qué segundo de voz termina cada bloque (aprox., por palabras)
        t += len(str(b['texto']).split()) / pps
        ini.append(t)
    pos = [k for k in range(1, len(con_voz) - 1) if con_voz[k]['id'] not in fijos and not con_voz[k].get('gancho')]
    elegidos = [k for k, b in enumerate(con_voz) if b['id'] in out]
    lejos = lambda k: all(abs(ini[k] - ini[j]) >= cada * 0.5 for j in elegidos)
    desde = 0
    for patron in RESPIRO:  # los momentos clave, en el orden del proceso (el «omitir» de la intro no cuenta)
        for k in pos:
            if k >= desde and patron.search(str(con_voz[k].get('texto') or '')) and lejos(k):
                elegidos.append(k)
                desde = k + 1
                break
    # el resto repartido: cuando pasó ~cada (×0,75 a ×1,3) desde el último respiro, prefiriendo un paso crítico cercano
    ultimo, falta = 0.0, cada * r.uniform(0.75, 1.3)
    for k in range(len(con_voz) - 1):
        if any(j == k for j in elegidos):
            ultimo, falta = ini[k], cada * r.uniform(0.75, 1.3)
            continue
        if ini[k] - ultimo < falta or k not in pos:
            continue
        cerca = [x for x in (k, k + 1) if x in pos and es_critico(con_voz[x]) and lejos(x)]
        x = cerca[0] if cerca else k
        if lejos(x):
            elegidos.append(x)
            ultimo, falta = ini[x], cada * r.uniform(0.75, 1.3)
    usados = set(round(v, 1) for v in out.values())
    for k in sorted(set(elegidos)):
        bid = con_voz[k]['id']
        if bid in out:
            continue
        for _ in range(20):  # distintos entre sí
            v = round(r.uniform(est['respiro_min'], est['respiro_max']), 1)
            if v not in usados:
                break
        usados.add(v)
        out[bid] = v
    return out


def _firma_crudo(carpeta, bid):
    f = os.path.join(carpeta, CRUDO, bid + '.mp3')
    try:
        st = os.stat(f)
        return f'{st.st_size}:{int(st.st_mtime)}'
    except OSError:
        return None


def _leer(f, defecto):
    try:
        return json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        return defecto


def aplicar(guion, carpeta, proyecto=None, estilo=None, semilla=None, log=print, corto=False):
    """Deja la voz de cada bloque con el ritmo elegido (desde la copia sin ritmo). Devuelve el estado (voz/ritmo.json)."""
    proyecto = proyecto or os.path.dirname(os.path.abspath(guion))
    k, est, sem = elegido(proyecto)
    est = dict(est)
    if estilo:
        k, est = estilo, estilos()[estilo]
    sem = sem if semilla is None else semilla
    if corto and k != 'antes':  # Shorts (fabian 14/11: pausas en todos los videos): pausas más cortas, sin respiros ni semilargas
        est = dict(est, frase=round(est['frase'] * 0.6, 2), coma=round(est['coma'] * 0.7, 2), larga=0.0, cada=0,
                   respiro_cada=0, parrafo=DESFASE + MARGEN, nombre=est['nombre'] + ' (Short)')
    g = _leer(guion, {}) or {}
    bloques = g.get('bloques', [])
    f_estado = os.path.join(carpeta, ESTADO)
    viejo = _leer(f_estado, {}) or {}
    previos = viejo.get('bloques', {})
    crudo = os.path.join(carpeta, CRUDO)
    respiros = elegir_respiros(bloques, est, sem) if k != 'antes' else {}
    receta = json.dumps({x: est[x] for x in BASE if x not in ('ppm', 'nota')}, sort_keys=True)
    # se suma a lo que había: «Probar solo unos bloques» (guion_prueba.json) no borra el estado de los demás bloques
    nuevo = {'estilo': k, 'nombre': est['nombre'], 'semilla': sem, 'musica_respiro': est['musica_respiro'], 'bloques': dict(previos)}
    hechos = 0
    for b in bloques:
        bid = b.get('id')
        mp3, alf = os.path.join(carpeta, f'{bid}.mp3'), os.path.join(carpeta, f'{bid}.align.json')
        if not bid or not str(b.get('texto') or '').strip() or not os.path.exists(mp3) or not os.path.exists(alf):
            continue
        prev = previos.get(bid) or {}
        # ¿la voz que hay es la que dejó el ritmo? (si no, es nueva de ElevenLabs: se guarda como la «sin ritmo»)
        procesada = bool(prev) and prev.get('mtime') == os.path.getmtime(mp3) and os.path.exists(os.path.join(crudo, bid + '.mp3'))
        if not procesada and k == 'antes':  # sin ritmo y la voz ya está tal cual: nada que copiar
            nuevo['bloques'][bid] = {'clave': None, 'mtime': os.path.getmtime(mp3), 'pausas': 0, 'vel': 1.0, 'cola': 0.0, 'respiro': 0}
            continue
        if not procesada:
            os.makedirs(crudo, exist_ok=True)
            shutil.copy2(mp3, os.path.join(crudo, bid + '.mp3'))
            shutil.copy2(alf, os.path.join(crudo, bid + '.align.json'))
        cola = max(0.0, est['parrafo'] - DESFASE - MARGEN)
        if est['variar'] and cola:
            cola = max(0.0, _var(_azar(sem, bid + ':p'), est, cola, 0.2, 0.3))
        cola = round(cola + respiros.get(bid, 0), 2)
        clave = hashlib.md5(f'{receta}|{sem}|{_firma_crudo(carpeta, bid)}'.encode()).hexdigest()[:16]
        if procesada and prev.get('clave') == clave:
            nuevo['bloques'][bid] = dict(prev, cola=cola, respiro=respiros.get(bid, 0))
            continue
        al = _leer(os.path.join(crudo, bid + '.align.json'), None)
        if not al:
            continue
        if k == 'antes':
            shutil.copy2(os.path.join(crudo, bid + '.mp3'), mp3)
            shutil.copy2(os.path.join(crudo, bid + '.align.json'), alf)
            cts, vel = [], 1.0
        else:
            cts, vel = cortes(al, est, _azar(sem, bid)), velocidad(b, est)
            aplicar_bloque(os.path.join(crudo, bid + '.mp3'), al, mp3, alf, cts, vel)
        hechos += 1
        nuevo['bloques'][bid] = {'clave': clave, 'mtime': os.path.getmtime(mp3), 'pausas': len(cts), 'vel': vel,
                                 'cola': cola, 'respiro': respiros.get(bid, 0)}
    json.dump(nuevo, open(f_estado, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if hechos:
        log(f'· ritmo «{est["nombre"]}»: {hechos} bloque(s) con el ritmo nuevo'
            + (f', {len(respiros)} respiro(s) ({", ".join(f"{x} {v:g} s" for x, v in respiros.items())})' if respiros else ''))
    return nuevo


def pausar_sin_tiempos(mp3, salida, proyecto, max_s=None, log=print):
    """Para voces sin tiempos por letra (la frase del tráiler): busca los silencios naturales entre frases (ffmpeg
    silencedetect) y los alarga con el estilo del proyecto, sin pasarse de max_s. Devuelve la ruta a usar (mp3 si es «antes»)."""
    k, est, sem = elegido(proyecto)
    if k == 'antes' or est['frase'] <= 0:
        return mp3
    r = subprocess.run(['ffmpeg', '-nostdin', '-i', mp3, '-af', 'silencedetect=noise=-32dB:d=0.12', '-f', 'null', '-'],
                       capture_output=True, text=True)
    ini = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', r.stderr)]
    fin = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', r.stderr)]
    total = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp3],
                                 capture_output=True, text=True).stdout or 0)
    huecos = [((a + b) / 2, b - a) for a, b in zip(ini, fin) if 0.3 < a and b < total - 0.3]
    rz = _azar(sem, 'trailer')
    # en el tráiler solo los huecos de fin de frase (los más largos) y pausas más cortas: es rápido a propósito
    largos = sorted(huecos, key=lambda h: -h[1])[:max(1, len(huecos) // 2)]
    cts = sorted((t, round(_var(rz, est, est['frase'] * 0.6, 0.1, 0.15), 2)) for t, _ in largos)
    vel = est['vel']
    if max_s:
        while cts and (total + sum(p for _, p in cts)) / vel > max_s:
            cts.pop(max(range(len(cts)), key=lambda i: cts[i][1]))
    if not cts and abs(vel - 1) < 1e-6:
        return mp3
    al = {'characters': [], 'character_start_times_seconds': [], 'character_end_times_seconds': []}
    aplicar_bloque(mp3, al, salida, salida + '.align.json', cts, vel if not max_s or total / vel <= max_s else 1.0)
    log(f'· ritmo «{est["nombre"]}» en el tráiler: {len(cts)} pausa(s)')
    return salida


def cola(carpeta, bid):
    """Segundos de silencio extra después de la voz del bloque (pausa de párrafo + respiro). La usa voz.ajustar_guion."""
    return float(((_leer(os.path.join(carpeta, ESTADO), {}) or {}).get('bloques', {}).get(bid) or {}).get('cola') or 0)


def tramos_respiro(guion, carpeta):
    """[(desde, hasta)] del video donde hay respiro (la voz calla), y el volumen al que sube la música ahí."""
    est = _leer(os.path.join(carpeta, ESTADO), {}) or {}
    g = _leer(guion, {}) or {}
    out = []
    for b in g.get('bloques', []):
        x = (est.get('bloques') or {}).get(b.get('id')) or {}
        if x.get('respiro') and b.get('inicio_min') is not None and b.get('voz_real_s'):
            desde = b['inicio_min'] + DESFASE + b['voz_real_s'] + 0.2
            out.append((round(desde, 2), round(desde + x['respiro'], 2)))
    return out, float(est.get('musica_respiro') or 0.32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--guion', default='guion.json')
    ap.add_argument('--estilo', choices=sorted(estilos()))
    ap.add_argument('--semilla', type=int)
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    guion, carpeta = os.path.join(d, a.guion), os.path.join(d, 'voz')
    if not os.path.exists(guion) or not os.path.isdir(carpeta):
        raise SystemExit('Primero hace falta el guion y la voz («Generar voz»).')
    est = aplicar(guion, carpeta, d, a.estilo, a.semilla, log=lambda x: print(x, flush=True))
    sys.path.insert(0, AQUI)
    import voz  # recalcula el largo de cada bloque con la voz nueva (no gasta: no pide nada a ElevenLabs)
    for x in voz.ajustar_guion(guion, carpeta):
        print('·', x, flush=True)
    print(f'Ritmo «{est["nombre"]}» aplicado. Vuelve a «Montar video» para verlo.', flush=True)


if __name__ == '__main__':
    main()
