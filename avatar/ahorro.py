"""«🧑 Avatar (ahorro)»: en los videos con avatar, HeyGen hace solo unos tramos y el resto va con voz en off sobre material de
apoyo (pedido de fabian, 01/11/2026: «los créditos en HeyGen están algo costosos… el inicio o algunos tramos cortos en avatar
como para variar»). Gratis: no llama a HeyGen, ElevenLabs ni a ninguna IA.

Modo «ahorro» (por defecto): con AVATAR van el inicio (20-30 s), 2 o 3 momentos fuertes de 10-15 s (revelaciones, alertas,
remates: las frases con más peso del guion) y el cierre (10-15 s). Todo lo demás es VOZ EN OFF: la misma voz sobre gráficas,
memes, capturas e imágenes del proyecto, cambiando cada ~4 s. Modo «todo»: todo el video con avatar, como antes.
Cada bloque del guion puede llevar "avatar": true (todo el bloque con avatar) o false (nunca); sin el campo, decide la app.

La voz es UNA sola pista (voz_completa.mp3) y manda en el montaje: los clips de HeyGen ponen solo la imagen en sus tramos, así
que no puede haber desfase de audio.

Archivos (en <proyecto>/avatar_ahorro/): plan.json · voz_completa.mp3 · avatar_NN.mp3 (cada uno < 1 min, para subir a HeyGen)
· ORDEN_AVATAR.txt · heygen/avatar_NN.mp4 (los videos que bajas de HeyGen) · AVATAR_AHORRO.mp4 (el montaje).
Uso: python avatar/ahorro.py plan|exportar|montar --proyecto CARPETA [--modo ahorro|todo]
"""
import argparse, glob, json, os, random, re, subprocess, tempfile

PAUSA = 0.4             # silencio entre bloques de voz (como al armar los bloques para HeyGen)
INICIO = (20.0, 30.0)   # el inicio con avatar: al menos 20 s y, si se puede, no más de 30
CIERRE = (10.0, 15.0)
FUERTE = (10.0, 15.0)
MAX_TRAMO = 58.0        # HeyGen: cada audio por debajo de 1 min
SEPARACION = 60.0       # entre dos momentos fuertes (para repartirlos por el video)
ROTAR = 4.0             # la voz en off cambia de imagen cada ~4 s (regla de no dejar escenas largas)
W, H, FPS = 1920, 1080, 25
CAJA = (1560, 840, 40)  # el apoyo va arriba, en una caja de 1560x840 a 40 px del borde: abajo quedan libres los subtítulos
FONDO = '0x0b1630'
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
    """Frases seguidas desde i (hacia adelante o atrás) hasta juntar al menos `minimo` s; para antes si la siguiente frase
    pasaría de `maximo` y ya hay `minimo`, y nunca pasa de MAX_TRAMO (el límite de HeyGen)."""
    j = i
    while True:
        a, b = (i, j) if hacia > 0 else (j, i)
        k = j + hacia
        if fr[b]['e'] - fr[a]['s'] >= minimo or not 0 <= k < len(fr):
            return a, b
        a2, b2 = (i, k) if hacia > 0 else (k, i)
        if fr[b2]['e'] - fr[a2]['s'] > MAX_TRAMO:
            return a, b
        j = k


def elegir(fr, modo='ahorro', n_fuertes=None):
    """Marca cada frase como avatar o voz en off y devuelve los tramos seguidos: [{tipo, i0, i1, s, e, motivo}]."""
    n = len(fr)
    if not n:
        return []
    av = [modo == 'todo'] * n
    motivo = ['todo con avatar' if modo == 'todo' else ''] * n
    if modo != 'todo':
        total = fr[-1]['e']
        a, b = _ventana(fr, 0, *INICIO)
        for k in range(a, b + 1):
            av[k], motivo[k] = True, 'inicio'
        a, b = _ventana(fr, n - 1, *CIERRE, hacia=-1)
        for k in range(a, b + 1):
            av[k], motivo[k] = True, 'cierre'
        if n_fuertes is None:
            n_fuertes = 2 if total < 8 * 60 else 3
        ocupados = [(fr[k]['s'], fr[k]['e']) for k in range(n) if av[k]]
        for k in sorted(range(n), key=lambda k: (-peso(fr[k]['texto']), k)):
            if n_fuertes <= 0 or peso(fr[k]['texto']) < 3:  # una pregunta corta sola no basta
                break
            # la ventana termina en la frase fuerte (el remate llega con la cara) y empieza 10-15 s antes
            a, b = _ventana(fr, k, *FUERTE, hacia=-1)
            s, e = fr[a]['s'], fr[b]['e']
            if any(s - SEPARACION < e2 and e + SEPARACION > s2 for s2, e2 in ocupados):
                continue
            for j in range(a, b + 1):
                av[j], motivo[j] = True, 'momento fuerte: «' + fr[k]['texto'][:60] + '»'
            ocupados.append((s, e))
            n_fuertes -= 1
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
        if t['tipo'] == 'voz' and fr[t['i1']]['e'] - fr[t['i0']]['s'] < ROTAR and tramos[k - 1]['tipo'] == tramos[k + 1]['tipo'] == 'avatar':
            t['tipo'], t['motivo'] = 'avatar', tramos[k - 1]['motivo']
    for t in tramos:
        # cada tramo empieza donde terminó el anterior: así la imagen cubre también los silencios entre frases
        t['s'] = 0.0 if t['i0'] == 0 else fr[t['i0']]['s']
        t['e'] = fr[t['i1']]['e'] if t['i1'] == n - 1 else fr[t['i1'] + 1]['s']
        t['texto'] = ' '.join(fr[k]['texto'] for k in range(t['i0'], t['i1'] + 1))
    return tramos


def resumen(tramos):
    av = sum(t['e'] - t['s'] for t in tramos if t['tipo'] == 'avatar')
    vo = sum(t['e'] - t['s'] for t in tramos if t['tipo'] == 'voz')
    total = av + vo
    return {'avatar_s': round(av, 1), 'voz_s': round(vo, 1), 'total_s': round(total, 1),
            'ahorro_pct': round(100 * (1 - av / total)) if total else 0,
            'tramos_avatar': sum(t['tipo'] == 'avatar' for t in tramos)}


def mmss(s):
    return f'{int(s // 60)}:{int(s % 60):02d}'


# ---------------------------------------------------------------- en el proyecto

def carpeta_ahorro(d):
    c = os.path.join(d, 'avatar_ahorro')
    os.makedirs(c, exist_ok=True)
    return c


def modo_de(d, defecto='ahorro'):
    try:
        return json.load(open(os.path.join(d, 'avatar_ahorro', 'plan.json'), encoding='utf-8')).get('modo') or defecto
    except (OSError, ValueError):
        return defecto


def plan(d, modo=None):
    modo = modo or modo_de(d)
    fr, _ = frases_de_voz(d)
    tramos = elegir(fr, modo)
    bl = {}
    for x in fr:  # cada bloque del guion con su marca (None = lo decide la app) y su tiempo
        b = bl.setdefault(x['bloque'], {'id': x['bloque'], 'avatar': x.get('avatar'), 's': x['s'], 'e': x['e'], 'texto': ''})
        b['e'], b['texto'] = x['e'], (b['texto'] + ' ' + x['texto']).strip()
    p = {'modo': modo, 'tramos': tramos, 'resumen': resumen(tramos), 'frases': len(fr), 'bloques': list(bl.values())}
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
    lineas = [f'AVATAR EN MODO {p["modo"].upper()} · lo que va a HeyGen (nada se gastó al prepararlo)',
              f'Avatar: {mmss(p["resumen"]["avatar_s"])} · voz en off: {mmss(p["resumen"]["voz_s"])} · '
              f'ahorro frente a todo con avatar: ~{p["resumen"]["ahorro_pct"]} % de los minutos de HeyGen', '',
              'En HeyGen: «Crear video» → pestaña «Audio» → sube avatar_NN.mp3 → el avatar con el look indicado → pega el',
              'movimiento en «Aplicar movimiento personalizado» («Más expresivo» APAGADO). Baja cada video como',
              'avatar_ahorro/heygen/avatar_NN.mp4 y pulsa «Montar» en la app.', '']
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


def _clip_apoyo(f, dd, salida, k):
    """Un trozo de apoyo de dd s a 1920x1080, en la caja de arriba (los subtítulos van abajo): video desde su inicio, o
    imagen con un zoom suave (acerca o aleja)."""
    cw, ch, y = CAJA
    caja = f'scale={cw}:{ch}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:{y}:color={FONDO}'
    if f.lower().endswith(('.mp4', '.mov')):
        ff('-stream_loop', '-1', '-i', f, '-t', f'{dd:.3f}', '-vf', f'{caja},fps={FPS},setsar=1',
           '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', salida)
        return
    n = max(1, round(dd * FPS))
    z = f"'1+0.08*on/{n}'" if k % 2 == 0 else f"'1.08-0.08*on/{n}'"
    ff('-loop', '1', '-i', f, '-t', f'{dd:.3f}', '-vf',
       f'{caja},scale={W * 2}:{H * 2},zoompan=z={z}:x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d=1:s={W}x{H}:fps={FPS},setsar=1',
       '-frames:v', str(n), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', salida)


def _clip_avatar(f, dd, salida):
    """La imagen del clip de HeyGen, del largo exacto del tramo (si es más corto, se queda en su último cuadro)."""
    ff('-i', f, '-t', f'{dd:.3f}', '-vf', f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,'
       f'tpad=stop_mode=clone:stop_duration={dd:.3f}', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
       '-pix_fmt', 'yuv420p', salida)


def montar(tramos, voz, clips_avatar, apoyo, salida, semilla=7):
    """tramos: [{tipo, s, e}] sobre la pista `voz`; clips_avatar: un .mp4 por tramo con avatar, en orden. El audio es la
    voz completa, una sola vez: la imagen cambia por tramos pero el sonido no se corta (sin desfase)."""
    rnd = random.Random(semilla)
    pool, ultimo = list(apoyo), None
    with tempfile.TemporaryDirectory() as tmp:
        partes, k_av, k = [], 0, 0
        for t in tramos:
            dd = t['e'] - t['s']
            if t['tipo'] == 'avatar':
                p = os.path.join(tmp, f'{len(partes):03d}.mp4')
                _clip_avatar(clips_avatar[k_av], dd, p)
                k_av += 1
                partes.append(p)
                continue
            n = max(1, round(dd / ROTAR))  # trozos de ~4 s, nunca el mismo dos veces seguidas
            for j in range(n):
                if not pool:
                    pool = list(apoyo)
                    rnd.shuffle(pool)
                f = pool.pop(0)
                if f == ultimo and pool:
                    pool.append(f)
                    f = pool.pop(0)
                ultimo = f
                p = os.path.join(tmp, f'{len(partes):03d}.mp4')
                _clip_apoyo(f, dd / n, p, k)
                k += 1
                partes.append(p)
        lista = os.path.join(tmp, 'lista.txt')
        open(lista, 'w', encoding='utf-8').write(''.join(f"file '{p}'\n" for p in partes))
        total = tramos[-1]['e']
        ff('-f', 'concat', '-safe', '0', '-i', lista, '-i', voz, '-map', '0:v', '-map', '1:a', '-t', f'{total:.3f}',
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
    montar(p['tramos'], vc, clips, apoyo, salida)
    return salida


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
        return h.responder(p)
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
