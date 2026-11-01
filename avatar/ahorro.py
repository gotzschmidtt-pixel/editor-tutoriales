"""«🧑 Avatar (ahorro)»: en los videos con avatar, HeyGen hace solo unos tramos y el resto va con voz en off sobre material de
apoyo (pedido de fabian, 01/11/2026: «los créditos en HeyGen están algo costosos… el inicio o algunos tramos cortos en avatar
como para variar»). Gratis: no llama a HeyGen, ElevenLabs ni a ninguna IA.

Modo «ahorro» (por defecto), con el ritmo de las referencias (Olga Rendón y Danskyx, 01/11/2026):
- GANCHO SIN AVATAR: los primeros 30-60 s son voz en off con cortes cada ~2 s; el avatar entra después a presentarse.
- DOS VELOCIDADES: la voz en off cambia de imagen cada ~2 s en el primer minuto y cada ~5 s después, y cada corte cae en el
  fin de una frase cuando hay una cerca (va con lo que dice la voz). Nunca el mismo trozo dos veces seguidas.
- POCOS TRAMOS DE AVATAR Y LARGOS: 2 a 4 de 30-55 s (la presentación, los momentos con más peso y el cierre), como mucho
  ~15 % del video. Dentro de cada tramo se alterna plano abierto / acercado cada 10-20 s (gratis: el mismo clip recortado).
- PANTALLA FINAL: 10-12 s con el avatar desenfocado de fondo, para los elementos finales de YouTube.
Modo «todo»: todo el video con avatar, como antes. Cada bloque del guion puede llevar "avatar": true (todo el bloque con
avatar) o false (nunca); sin el campo, decide la app. Los ajustes se cambian en la pestaña y quedan en plan.json.

La voz es UNA sola pista (voz_completa.mp3) y manda en el montaje: los clips de HeyGen ponen solo la imagen en sus tramos, así
que no puede haber desfase de audio.

Archivos (en <proyecto>/avatar_ahorro/): plan.json · voz_completa.mp3 · avatar_NN.mp3 (cada uno < 1 min, para subir a HeyGen)
· ORDEN_AVATAR.txt · heygen/avatar_NN.mp4 (los videos que bajas de HeyGen) · AVATAR_AHORRO.mp4 (el montaje).
Uso: python avatar/ahorro.py plan|exportar|montar --proyecto CARPETA [--modo ahorro|todo]
"""
import argparse, glob, json, os, random, re, subprocess, tempfile

PAUSA = 0.4             # silencio entre bloques de voz (como al armar los bloques para HeyGen)
MAX_TRAMO = 58.0        # HeyGen: cada audio por debajo de 1 min
SEPARACION = 60.0       # entre dos tramos de avatar (para repartirlos por el video)
AJUSTES = {             # lo que se puede cambiar en la pestaña «🧑 Avatar (ahorro)»
    'gancho_s': 45,         # gancho sin avatar al inicio (30-60 s; 0 = el avatar abre el video)
    'rotar_inicio': 2.0,    # cada cuántos segundos cambia la imagen en el primer minuto
    'rotar': 5.0,           # … y después
    'tramos_avatar': 0,     # cuántos tramos con avatar (0 = la app decide: 2 a 4 según el largo)
    'tramo_s': [30, 55],    # largo de cada tramo con avatar
    'max_avatar_pct': 15,   # tope de avatar sobre el total
    'plano_s': 15,          # dentro del avatar, cambio de plano abierto / acercado cada ~15 s
    'final_s': 11,          # pantalla final con el avatar desenfocado (0 = sin pantalla final)
}
W, H, FPS = 1920, 1080, 25
CAJA = (1560, 840, 40)  # el apoyo va arriba, en una caja de 1560x840 a 40 px del borde: abajo quedan libres los subtítulos
FONDO = '0x0b1630'
ACERCADO = (1280, 720, 320, 30)  # plano acercado del avatar (×1,5): recorte de 1280x720 (cara arriba al centro) llevado a 1920x1080
LOOKS = ['frente', 'primer plano', 'lateral']
MOVIMIENTO = ('Calm, friendly news host talking to the camera. Natural small smiles, soft hand gestures, gentle nods. '
              'No exaggerated facial expressions, no puckered lips, no big laughs. Stays seated and does not touch the microphone.')
PESO = [(r'¡', 2), (r'\bojo\b|\bpilas\b|cuidado|alerta|estafa|trampa|nunca|\bno\b(?= (le |te )?(des|contestes|firmes))', 3),
        (r'\bNO\b', 2), (r'gan[óo]|perdi[óo]|demand|multa|millones|mil millones|rebaja|se va|se fue|adi[óo]s', 2),
        (r'\?', 1), (r'spoiler|imag[íi]nate|traducido|o sea', 1)]


def dur(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def ff(*a):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *a], check=True)


def ajustes(aj=None):
    out = dict(AJUSTES)
    out.update({k: v for k, v in (aj or {}).items() if k in AJUSTES and v is not None})
    return out


# ---------------------------------------------------------------- frases con tiempos (de la voz ya hecha, gratis)

def frases_de_voz(d):
    """Las oraciones de toda la voz, con su segundo en la pista completa (bloques del guion uno tras otro, PAUSA entre
    ellos). Usa voz/<id>.mp3 y voz/<id>.align.json (tiempos por carácter de ElevenLabs)."""
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    out, partes, t = [], [], 0.0
    for b in g.get('bloques', []):
        mp3 = os.path.join(d, 'voz', f"{b['id']}.mp3")
        if not os.path.exists(mp3):
            continue
        dd = dur(mp3)
        try:
            al = json.load(open(os.path.join(d, 'voz', f"{b['id']}.align.json"), encoding='utf-8'))
            ch, fin = al['characters'], al['character_end_times_seconds']
        except (OSError, ValueError, KeyError):
            ch, fin = list(b.get('texto', '')), None
        texto, ini = '', 0.0
        for k, c in enumerate(ch):
            texto += c
            ultimo = k == len(ch) - 1
            if (c in '.?!…' and (ultimo or ch[k + 1] in ' \n')) or ultimo:
                e = (fin[k] if fin else dd * (k + 1) / len(ch)) if not ultimo else dd
                if texto.strip():
                    out.append({'s': round(t + ini, 2), 'e': round(t + e, 2), 'texto': texto.strip(), 'bloque': b['id'],
                                'avatar': b.get('avatar')})
                texto, ini = '', e
        partes.append(mp3)
        t += dd + PAUSA
    return out, partes


def peso(texto):
    return sum(p for r, p in PESO if re.search(r, texto)) + (1 if len(texto.split()) <= 8 else 0)


# ---------------------------------------------------------------- elegir los tramos

def _ventana(fr, i, minimo, maximo, hacia=1):
    """Frases seguidas desde i (hacia adelante o atrás) hasta juntar al menos `minimo` s, sin pasar de `maximo` ni de
    MAX_TRAMO (el límite de HeyGen)."""
    j = i
    while True:
        a, b = (i, j) if hacia > 0 else (j, i)
        k = j + hacia
        if fr[b]['e'] - fr[a]['s'] >= minimo or not 0 <= k < len(fr):
            return a, b
        a2, b2 = (i, k) if hacia > 0 else (k, i)
        if fr[b2]['e'] - fr[a2]['s'] > min(maximo, MAX_TRAMO):
            return a, b
        j = k


def elegir(fr, modo='ahorro', aj=None):
    """Marca cada frase como avatar o voz en off y devuelve los tramos seguidos: [{tipo, i0, i1, s, e, motivo}]."""
    aj = ajustes(aj)
    n = len(fr)
    if not n:
        return []
    av = [modo == 'todo'] * n
    motivo = ['todo con avatar' if modo == 'todo' else ''] * n
    if modo != 'todo':
        total = fr[-1]['e']
        presupuesto = total * aj['max_avatar_pct'] / 100
        n_tr = int(aj['tramos_avatar']) or max(2, min(4, round(presupuesto / 40)))
        lo, hi = aj['tramo_s']
        lo = max(6.0, min(lo, presupuesto / n_tr))   # en videos cortos los tramos se achican para no pasar el tope
        hi = max(lo, min(hi, presupuesto / n_tr * 1.4))
        # el gancho va sin avatar: hasta la frase que pasa de gancho_s (sin llegar a 60 s si se puede)
        i_g = -1
        if aj['gancho_s'] > 0:
            i_g = next((k for k in range(n) if fr[k]['e'] >= aj['gancho_s']), n - 1)
            if fr[i_g]['e'] > 60 and i_g > 0:
                i_g -= 1
        usados, ocupados = 0.0, []

        def marcar(a, b, por_que):
            nonlocal usados
            for j in range(a, b + 1):
                av[j], motivo[j] = True, por_que
            usados += fr[b]['e'] - fr[a]['s']
            ocupados.append((fr[a]['s'], fr[b]['e']))

        if i_g + 1 < n:  # la presentación: el avatar entra después del gancho
            a, b = _ventana(fr, i_g + 1, lo, hi)
            marcar(a, b, 'presentación (después del gancho)' if i_g >= 0 else 'inicio')
        if n_tr >= 2:    # el cierre
            a, b = _ventana(fr, n - 1, lo, hi, hacia=-1)
            if a > i_g and not av[a]:
                marcar(a, b, 'cierre')
        quedan = n_tr - len(ocupados)
        for k in sorted(range(n), key=lambda k: (-peso(fr[k]['texto']), k)):  # los momentos con más peso
            if quedan <= 0 or peso(fr[k]['texto']) < 3:  # una pregunta corta sola no basta
                break
            if k <= i_g:
                continue
            a, b = _ventana(fr, k, lo, hi, hacia=-1)  # termina en la frase fuerte: el remate llega con la cara
            s, e = fr[a]['s'], fr[b]['e']
            if a <= i_g or usados + e - s > presupuesto * 1.1 or any(s - SEPARACION < e2 and e + SEPARACION > s2 for s2, e2 in ocupados):
                continue
            marcar(a, b, 'momento fuerte: «' + fr[k]['texto'][:60] + '»')
            quedan -= 1
        for k in range(i_g + 1):
            motivo[k] = motivo[k] or 'gancho sin avatar'
    # lo que marcaste a mano en el guion manda
    for k, f in enumerate(fr):
        if f.get('avatar') is True:
            av[k], motivo[k] = True, f'bloque {f["bloque"]} marcado con avatar'
        elif f.get('avatar') is False:
            av[k], motivo[k] = False, ''
    tramos = []
    for k in range(n):
        tipo = 'avatar' if av[k] else 'voz'
        if tramos and tramos[-1]['tipo'] == tipo and (tipo == 'voz' or fr[k]['e'] - fr[tramos[-1]['i0']]['s'] <= MAX_TRAMO):
            tramos[-1]['i1'] = k
        else:
            tramos.append({'tipo': tipo, 'i0': k, 'i1': k, 'motivo': motivo[k]})
    # una voz en off de menos de 4 s entre dos avatares se queda con avatar (cortar tan poco no luce)
    for k in range(1, len(tramos) - 1):
        t = tramos[k]
        if t['tipo'] == 'voz' and fr[t['i1']]['e'] - fr[t['i0']]['s'] < 4 and tramos[k - 1]['tipo'] == tramos[k + 1]['tipo'] == 'avatar':
            t['tipo'], t['motivo'] = 'avatar', tramos[k - 1]['motivo']
    for t in tramos:
        # cada tramo empieza donde terminó el anterior: así la imagen cubre también los silencios entre frases
        t['s'] = 0.0 if t['i0'] == 0 else fr[t['i0']]['s']
        t['e'] = fr[t['i1']]['e'] if t['i1'] == n - 1 else fr[t['i1'] + 1]['s']
        t['texto'] = ' '.join(fr[k]['texto'] for k in range(t['i0'], t['i1'] + 1))
    return tramos


def resumen(tramos, aj=None):
    aj = ajustes(aj)
    av = sum(t['e'] - t['s'] for t in tramos if t['tipo'] == 'avatar')
    vo = sum(t['e'] - t['s'] for t in tramos if t['tipo'] == 'voz')
    total = av + vo
    return {'avatar_s': round(av, 1), 'voz_s': round(vo, 1), 'total_s': round(total, 1),
            'avatar_pct': round(100 * av / total) if total else 0,
            'ahorro_pct': round(100 * (1 - av / total)) if total else 0,
            'tramos_avatar': sum(t['tipo'] == 'avatar' for t in tramos), 'final_s': aj['final_s']}


def mmss(s):
    return f'{int(s // 60)}:{int(s % 60):02d}'


def cortes(s, e, frases_s, aj=None):
    """Dónde cambia la imagen de la voz en off entre s y e: cada ~rotar_inicio s en el primer minuto y cada ~rotar s
    después, corrido al inicio de frase más cercano (si hay uno a menos de un 40 % del paso), para ir con lo que dice la voz."""
    aj = ajustes(aj)
    out, t = [s], s
    while True:
        paso = aj['rotar_inicio'] if t < 60 else aj['rotar']
        meta = t + paso
        if meta >= e - paso * 0.5:
            break
        cerca = [x for x in frases_s if abs(x - meta) <= paso * 0.4 and t + paso * 0.5 < x < e - paso * 0.5]
        t = min(cerca, key=lambda x: abs(x - meta)) if cerca else meta
        out.append(round(t, 3))
    return out + [e]


# ---------------------------------------------------------------- en el proyecto

def carpeta_ahorro(d):
    c = os.path.join(d, 'avatar_ahorro')
    os.makedirs(c, exist_ok=True)
    return c


def _guardado(d):
    try:
        return json.load(open(os.path.join(d, 'avatar_ahorro', 'plan.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def plan(d, modo=None, aj=None):
    g = _guardado(d)
    modo = modo or g.get('modo') or 'ahorro'
    aj = ajustes({**(g.get('ajustes') or {}), **(aj or {})})
    fr, _ = frases_de_voz(d)
    tramos = elegir(fr, modo, aj)
    bl = {}
    for x in fr:  # cada bloque del guion con su marca (None = lo decide la app) y su tiempo
        b = bl.setdefault(x['bloque'], {'id': x['bloque'], 'avatar': x.get('avatar'), 's': x['s'], 'e': x['e'], 'texto': ''})
        b['e'], b['texto'] = x['e'], (b['texto'] + ' ' + x['texto']).strip()
    p = {'modo': modo, 'ajustes': aj, 'tramos': tramos, 'resumen': resumen(tramos, aj), 'frases': len(fr),
         'frases_s': [x['s'] for x in fr], 'bloques': list(bl.values())}
    json.dump(p, open(os.path.join(carpeta_ahorro(d), 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return p


def voz_completa(partes, salida):
    """Une los audios de los bloques con PAUSA s de silencio entre ellos (la misma cuenta que frases_de_voz)."""
    with tempfile.TemporaryDirectory() as tmp:
        sil = os.path.join(tmp, 'sil.wav')
        ff('-f', 'lavfi', '-t', str(PAUSA), '-i', 'anullsrc=r=44100:cl=mono', sil)
        entradas, filtro = [], ''
        for k, p in enumerate(partes):
            entradas += ['-i', p] + (['-i', sil] if k < len(partes) - 1 else [])
        m = len(entradas) // 2
        filtro = ''.join(f'[{k}:a]aresample=44100,aformat=channel_layouts=mono[a{k}];' for k in range(m))
        filtro += ''.join(f'[a{k}]' for k in range(m)) + f'concat=n={m}:v=0:a=1[a]'
        ff(*entradas, '-filter_complex', filtro, '-map', '[a]', '-c:a', 'libmp3lame', '-b:a', '192k', salida)


def exportar(d, modo=None):
    """Los audios SOLO de los tramos con avatar (para subir a HeyGen) y ORDEN_AVATAR.txt. No gasta nada."""
    p = plan(d, modo)
    c = carpeta_ahorro(d)
    _, partes = frases_de_voz(d)
    vc = os.path.join(c, 'voz_completa.mp3')
    voz_completa(partes, vc)
    for f in glob.glob(os.path.join(c, 'avatar_*.mp3')):
        os.remove(f)
    r = p['resumen']
    lineas = [f'AVATAR EN MODO {p["modo"].upper()} · lo que va a HeyGen (nada se gastó al prepararlo)',
              f'Avatar: {mmss(r["avatar_s"])} ({r["avatar_pct"]} %) · voz en off: {mmss(r["voz_s"])} · '
              f'ahorro frente a todo con avatar: ~{r["ahorro_pct"]} % de los minutos de HeyGen', '',
              'En HeyGen: «Crear video» → pestaña «Audio» → sube avatar_NN.mp3 → el avatar con el look indicado → pega el',
              'movimiento en «Aplicar movimiento personalizado» («Más expresivo» APAGADO). Baja cada video como',
              'avatar_ahorro/heygen/avatar_NN.mp4 y pulsa «Montar» en la app. Los cambios de plano (abierto / acercado) y',
              'la pantalla final desenfocada los hace la app con el mismo clip: no hace falta pedirlos en HeyGen.', '']
    n = 0
    for t in p['tramos']:
        if t['tipo'] != 'avatar':
            continue
        n += 1
        t['archivo'] = f'avatar_{n:02d}.mp3'
        ff('-ss', f"{t['s']:.2f}", '-t', f"{t['e'] - t['s']:.2f}", '-i', vc, '-c:a', 'libmp3lame', '-b:a', '192k',
           os.path.join(c, t['archivo']))
        lineas += [f"{n}. {t['archivo']} · {mmss(t['s'])}–{mmss(t['e'])} ({t['e'] - t['s']:.1f} s) · {t['motivo']}",
                   f"   Look: {LOOKS[(n - 1) % len(LOOKS)]}", f'   Movimiento (EN): {MOVIMIENTO}',
                   f"   Texto: {t['texto'][:220]}", '']
    open(os.path.join(c, 'ORDEN_AVATAR.txt'), 'w', encoding='utf-8').write('\n'.join(lineas))
    json.dump(p, open(os.path.join(c, 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return p


# ---------------------------------------------------------------- montaje: avatar en sus tramos, apoyo en el resto

def apoyo_de(d):
    """El material de apoyo del proyecto: gráficas y tomas (.mp4) e imágenes (memes, capturas, fotos)."""
    pat = ['apoyo/*', 'graficos/*.mp4', 'memes/*.png', 'memes/*.jpg', 'capturas/*.jpg', 'capturas/*.png', 'ia_capturas/*.jpg']
    fs = [f for x in pat for f in sorted(glob.glob(os.path.join(d, x)))]
    return [f for f in fs if f.lower().endswith(('.mp4', '.mov', '.png', '.jpg', '.jpeg', '.webp'))
            and 'hoja' not in os.path.basename(f).lower()]


def _clip_apoyo(f, dd, salida, k, desde=0.0):
    """Un trozo de apoyo de dd s a 1920x1080, en la caja de arriba (los subtítulos van abajo): video desde `desde`, o
    imagen con un zoom suave (acerca o aleja)."""
    cw, ch, y = CAJA
    caja = f'scale={cw}:{ch}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:{y}:color={FONDO}'
    if f.lower().endswith(('.mp4', '.mov')):
        ff('-stream_loop', '-1', '-ss', f'{desde:.2f}', '-i', f, '-t', f'{dd:.3f}', '-vf', f'{caja},fps={FPS},setsar=1',
           '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', salida)
        return
    n = max(1, round(dd * FPS))
    z = f"'1+0.08*on/{n}'" if k % 2 == 0 else f"'1.08-0.08*on/{n}'"
    ff('-loop', '1', '-i', f, '-t', f'{dd:.3f}', '-vf',
       f'{caja},scale={W * 2}:{H * 2},zoompan=z={z}:x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d=1:s={W}x{H}:fps={FPS},setsar=1',
       '-frames:v', str(n), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', salida)


def _clip_avatar(f, desde, dd, salida, acercado=False):
    """dd s de la imagen del clip de HeyGen desde `desde` (si se acaba, se queda en su último cuadro), en plano abierto o
    acercado a la cara."""
    cw, ch, x, y = ACERCADO
    plano = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}' + (f',crop={cw}:{ch}:{x}:{y},scale={W}:{H}' if acercado else '')
    ff('-ss', f'{desde:.3f}', '-i', f, '-t', f'{dd:.3f}', '-vf', f'{plano},fps={FPS},setsar=1,tpad=stop_mode=clone:stop_duration={dd:.3f}',
       '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', salida)


def montar(tramos, voz, clips_avatar, apoyo, salida, aj=None, frases_s=(), semilla=7):
    """tramos: [{tipo, s, e}] sobre la pista `voz`; clips_avatar: un .mp4 por tramo con avatar, en orden. El audio es la
    voz completa, una sola vez: la imagen cambia por tramos pero el sonido no se corta (sin desfase). Al final, si
    final_s > 0, la pantalla final con el último cuadro del avatar desenfocado (sin voz)."""
    aj = ajustes(aj)
    rnd = random.Random(semilla)
    pool, ultimo, desde_de = list(apoyo), None, {}
    with tempfile.TemporaryDirectory() as tmp:
        partes, k_av, k = [], 0, 0
        nuevo = lambda: os.path.join(tmp, f'{len(partes):03d}.mp4')
        for t in tramos:
            if t['tipo'] == 'avatar':
                # plano abierto / acercado cada ~plano_s, cambiando en el inicio de una frase si hay una cerca
                pl = cortes(t['s'], t['e'], frases_s, {'rotar_inicio': aj['plano_s'], 'rotar': aj['plano_s']})
                for j, (a, b) in enumerate(zip(pl, pl[1:])):
                    p = nuevo()
                    _clip_avatar(clips_avatar[k_av], a - t['s'], b - a, p, acercado=j % 2 == 1)
                    partes.append(p)
                k_av += 1
                continue
            cs = cortes(t['s'], t['e'], frases_s, aj)
            for a, b in zip(cs, cs[1:]):
                if not pool:
                    pool = list(apoyo)
                    rnd.shuffle(pool)
                f = pool.pop(0)
                if f == ultimo and pool:  # nunca el mismo trozo dos veces seguidas
                    pool.append(f)
                    f = pool.pop(0)
                ultimo = f
                # una gráfica animada no arranca vacía: la primera vez entra ya armada (desde el 40 % de su largo); si
                # vuelve a salir, sigue desde donde quedó (otro trozo)
                if f not in desde_de:
                    largo = dur(f) if f.lower().endswith(('.mp4', '.mov')) else 0
                    desde_de[f] = largo * 0.4 if largo > (b - a) + 1 else 0.0
                desde = desde_de[f]
                desde_de[f] = desde + (b - a)
                p = nuevo()
                _clip_apoyo(f, b - a, p, k, desde)
                k += 1
                partes.append(p)
        total = tramos[-1]['e']
        if aj['final_s'] > 0 and clips_avatar:  # pantalla final: el avatar desenfocado de fondo
            png, p = os.path.join(tmp, 'final.png'), nuevo()
            ff('-sseof', '-0.2', '-i', clips_avatar[-1], '-frames:v', '1', '-vf', f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}', png)
            ff('-loop', '1', '-i', png, '-t', f"{aj['final_s']:.2f}", '-vf', f'boxblur=24:3,fps={FPS},setsar=1', '-c:v', 'libx264',
               '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', p)
            partes.append(p)
            total += aj['final_s']
        lista = os.path.join(tmp, 'lista.txt')
        open(lista, 'w', encoding='utf-8').write(''.join(f"file '{p}'\n" for p in partes))
        ff('-f', 'concat', '-safe', '0', '-i', lista, '-i', voz, '-map', '0:v', '-map', '1:a', '-af', 'apad', '-t', f'{total:.3f}',
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
           '-movflags', '+faststart', salida)


def montar_proyecto(d):
    c = carpeta_ahorro(d)
    p = json.load(open(os.path.join(c, 'plan.json'), encoding='utf-8'))
    vc = os.path.join(c, 'voz_completa.mp3')
    if not os.path.exists(vc):
        raise SystemExit('Primero «Preparar audios para HeyGen» (hace voz_completa.mp3).')
    n_av = sum(t['tipo'] == 'avatar' for t in p['tramos'])
    clips = [os.path.join(c, 'heygen', f'avatar_{n:02d}.mp4') for n in range(1, n_av + 1)]
    faltan = [os.path.basename(f) for f in clips if not os.path.exists(f)]
    if faltan:
        raise SystemExit('Faltan los videos de HeyGen en avatar_ahorro/heygen/: ' + ', '.join(faltan))
    apoyo = apoyo_de(d)
    if not apoyo:
        raise SystemExit('No hay material de apoyo (gráficas, memes, capturas o la carpeta apoyo/) para la voz en off.')
    salida = os.path.join(c, 'AVATAR_AHORRO.mp4')
    montar(p['tramos'], vc, clips, apoyo, salida, p.get('ajustes'), p.get('frases_s', []))
    return salida


# ---------------------------------------------------------------- tomas de apoyo para generar (Higgsfield, etc.)

TOMAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mis_proyectos', '_referencias', 'higgsfield',
                     'lista_tomas_apoyo.txt')


def tomas(f=TOMAS):
    """La lista de tomas de apoyo (texto plano): «nombre: prompt» por línea, secciones «A. …» y una línea «ESTILO COMÚN (…): …»
    que se pega al final de cada prompt. Devuelve {ajustes, estilo, grupos: [{titulo, tomas: [{nombre, prompt}]}]}."""
    out = {'ajustes': '', 'estilo': '', 'grupos': [], 'archivo': f}
    if not os.path.exists(f):
        return out
    for l in open(f, encoding='utf-8').read().splitlines():
        l = l.strip()
        if l.startswith('Ajustes:'):
            out['ajustes'] = l
        elif l.upper().startswith('ESTILO COM'):
            out['estilo'] = l.split(':', 1)[1].strip()
        elif re.match(r'^[A-Z]\. ', l):
            out['grupos'].append({'titulo': l, 'tomas': []})
        elif re.match(r'^[a-z_]+_\d+:', l) and out['grupos']:
            n, p = l.split(':', 1)
            out['grupos'][-1]['tomas'].append({'nombre': n, 'prompt': p.strip()})
    return out


# ---------------------------------------------------------------- la app (rutas /api/avatar/...)

def get(h, ruta, q, d):
    if ruta == '/api/avatar/plan':
        try:
            p = plan(d, q.get('modo') or None)
        except FileNotFoundError:
            return h.error('Este proyecto todavía no tiene guion con voz (voz/L01.mp3…).')
        c = os.path.join(d, 'avatar_ahorro')
        n_av = p['resumen']['tramos_avatar']
        p['heygen_listos'] = [n for n in range(1, n_av + 1) if os.path.exists(os.path.join(c, 'heygen', f'avatar_{n:02d}.mp4'))]
        p['exportado'] = os.path.exists(os.path.join(c, 'ORDEN_AVATAR.txt'))
        p['montado'] = os.path.exists(os.path.join(c, 'AVATAR_AHORRO.mp4'))
        p['carpeta'] = c
        p['por_defecto'] = AJUSTES
        return h.responder(p)
    if ruta == '/api/avatar/tomas':  # la lista de tomas de apoyo para Higgsfield, con «📋 Copiar prompt»
        return h.responder(tomas())
    return h.error('no conozco esa ruta', 404)


def post(h, ruta, q, largo, d):
    datos = json.loads(h.rfile.read(largo) or b'{}')
    if ruta == '/api/avatar/bloque':  # «avatar» sí / no / auto de un bloque del guion
        f = os.path.join(d, 'guion.json')
        g = json.load(open(f, encoding='utf-8'))
        for b in g.get('bloques', []):
            if b.get('id') == datos.get('id'):
                if datos.get('avatar') in (True, False):
                    b['avatar'] = datos['avatar']
                else:
                    b.pop('avatar', None)
        json.dump(g, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return h.responder(plan(d))
    if ruta == '/api/avatar/modo':  # «ahorro» (por defecto) o «todo» con avatar
        return h.responder(plan(d, 'todo' if datos.get('modo') == 'todo' else 'ahorro'))
    if ruta == '/api/avatar/ajustes':  # gancho, velocidades de corte, tramos, tope, cambio de plano y pantalla final
        if datos.get('restablecer'):
            p = _guardado(d)
            p['ajustes'] = dict(AJUSTES)
            json.dump(p, open(os.path.join(carpeta_ahorro(d), 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            return h.responder(plan(d))
        return h.responder(plan(d, aj=datos.get('ajustes') or {}))
    if ruta == '/api/avatar/exportar':
        return h.responder(exportar(d))
    if ruta == '/api/avatar/montar':
        try:
            return h.responder({'ok': True, 'video': montar_proyecto(d)})
        except SystemExit as e:
            return h.error(str(e))
    return h.error('no conozco esa ruta', 404)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('accion', choices=['plan', 'exportar', 'montar'])
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('--modo', choices=['ahorro', 'todo'])
    a = ap.parse_args()
    if a.accion == 'montar':
        print(montar_proyecto(a.proyecto))
    else:
        r = (plan if a.accion == 'plan' else exportar)(a.proyecto, a.modo)
        print(json.dumps(r['resumen'], ensure_ascii=False))
