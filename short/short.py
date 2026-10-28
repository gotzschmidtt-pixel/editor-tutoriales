"""Short vertical 9:16 (como «Auto Resaltar» + «Reencuadre automático» de Filmora), hecho con lo que la app ya sabe del video.

Uso (desde la carpeta del proyecto): python short.py --proyecto . --duracion 60

1. Elige las tomas: el gancho del inicio y los bloques del guion con tus ⭐ cortes importantes, las acciones (volumen, power,
   pegar, Connect, paso cuatro, Omitir…) y el resultado (sin candado, crear cuenta), sin la parte de promoción (comentarios,
   suscribirse, grupo, WhatsApp de soporte), hasta llenar la duración. Deja el plan con el porqué de cada toma en short.json.
2. Reencuadra a 9:16 siguiendo lo importante: tu cara si sales (cuadro completo en alto), y si no, lo que se mueve o cambia en
   la pantalla (cursor, botón, celular) con un zoom suave; donde marcaste un círculo, encuadra esa zona. Nunca acelera.
3. Voz: las mismas voces del video (voz/Lxx.mp3), así que no gasta créditos. Con --voz-nueva usa el guion propio del Short
   (short_guion.json: tomas con src_inicio, texto y por_que, escrito para el Short, con más gancho) y genera esa voz con
   ElevenLabs en voz_short/ (gasta ~1 crédito por letra; lo que no cambió se reutiliza). Subtítulos grandes y tu música fija.
Deja SHORT.mp4 en la carpeta del proyecto.
"""
import argparse, json, os, re, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
sys.path.insert(0, os.path.join(RAIZ, 'montaje'))
import codificar  # noqa: E402  con la tarjeta NVIDIA o Intel si la hay

W, H = 1920, 1080          # el original
SW, SH = 1080, 1920        # el Short
PASO_SEG = 0.5             # cada cuánto se mira dónde está lo importante
ZOOM_PANTALLA = 1.2        # sin cara: un poco más cerca de lo que se mueve (sin cortar el teléfono)
MIN_TOMA = 7.0             # con la voz nueva (frases cortas): cada toma dura al menos esto, para ver la acción entera
MUSICA = os.path.join(RAIZ, 'mis_musica', 'musica_fija.mp3')

PROMO = re.compile(r'coment|suscrib|facebook|grupo privado|soporte|asesor|testimon|capturas de whatsapp|nos vemos|abrazo|'
                   r'tiene un costo|d[oó]lares|stock|xiaomi unlock', re.I)
ACCION = re.compile(r'volumen|power|fastboot|men[uú]|peg|connect|conect|paso (uno|dos|tres|cuatro)|reinici|desconect|omitir|'
                    r'cable|serial', re.I)
RESULTADO = re.compile(r'candado (ya )?no|ya no (est|aparece)|libre|crear (nuestra|una|tu)?.{0,10}cuenta|entramos|'
                       r'[ée]xito|adentro', re.I)


def duracion(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def elegir(d, g, objetivo, dur_video):
    """Las tomas del Short, en el orden del video, con su porqué."""
    cands = []
    for k, b in enumerate(g['bloques']):
        mp3 = os.path.join(d, 'voz', f"{b['id']}.mp3")
        mo = b.get('montaje') or {}
        if not os.path.exists(mp3) or mo.get('src_inicio') is None or mo.get('modo') == 'imagen' or not b.get('texto', '').strip():
            continue
        t = b['texto']
        razones, puntos = [], 0
        if k == 0:
            razones.append('el gancho del inicio'); puntos += 100
        if PROMO.search(t) and k:
            continue  # en un Short no va la promoción: se queda en el video largo
        if mo.get('importante'):
            razones.append('tu corte importante ⭐'); puntos += 3
        if b.get('tipo') == 'critico' or mo.get('critico'):
            razones.append('paso clave'); puntos += 2
        if ACCION.search(t):
            razones.append('se ve la acción'); puntos += 2
        if RESULTADO.search(t):
            razones.append('se ve el resultado'); puntos += 3
        if not razones:
            continue
        acciones = len({m.group(0).lower()[:5] for m in ACCION.finditer(t)})
        puntos += min(acciones, 3)  # varias acciones en el mismo bloque: más paso a paso
        if k and float(mo['src_inicio']) < dur_video * 0.2:
            puntos -= 3  # el resumen del inicio: en el Short van los pasos de verdad
        cands.append({'k': k, 'id': b['id'], 'voz': round(duracion(mp3), 2), 'puntos': puntos, 'por_que': ', '.join(razones),
                      'src_inicio': float(mo['src_inicio']), 'texto': t})
    elegidas, total = [], 0.0
    for c in sorted(cands, key=lambda c: (-c['puntos'] / max(c['voz'], 6) if c['k'] else -1e9, c['k'])):  # más importancia por segundo
        if total + c['voz'] + 0.4 <= objetivo:
            elegidas.append(c); total += c['voz'] + 0.4
    if not any(RESULTADO.search(c['texto']) for c in elegidas):  # siempre termina mostrando que salió bien
        fin = [c for c in cands if RESULTADO.search(c['texto'])]
        if fin and len(elegidas) > 1:
            menos = min((c for c in elegidas if c['k']), key=lambda c: c['puntos'])
            elegidas.remove(menos); elegidas.append(fin[-1])
    return sorted(elegidas, key=lambda c: c['k'])


def voz_nueva(d):
    """Las tomas del guion propio del Short (short_guion.json), con su voz nueva generada en voz_short/."""
    try:
        sg = json.load(open(os.path.join(d, 'short_guion.json'), encoding='utf-8'))
    except (OSError, ValueError):
        raise SystemExit('ERROR: falta el guion del Short (short_guion.json). Pídeselo a Claude o a la IA de la app.')
    bloques = [{'id': x['id'], 'texto': x['texto'], 'tipo': 'libre', 'humor': False,
                'montaje': {'modo': 'lento', 'src_inicio': float(x['src_inicio']), 'src_fin': float(x['src_inicio']) + 30,
                            'velocidad': 1.0, 'congelar_s': None}} for x in sg['tomas']]
    f = os.path.join(d, '.short_voz_guion.json')
    json.dump({'bloques': bloques}, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('· voz nueva del Short con ElevenLabs (solo las frases nuevas o cambiadas gastan créditos)…', flush=True)
    subprocess.run([sys.executable, os.path.join(RAIZ, 'voz', 'voz.py'), '--guion', f, '--salida', os.path.join(d, 'voz_short')],
                   check=True, cwd=d)
    return [{'k': i, 'id': x['id'], 'voz': round(duracion(os.path.join(d, 'voz_short', f"{x['id']}.mp3")), 2), 'puntos': 0,
             'por_que': x.get('por_que', ''), 'src_inicio': float(x['src_inicio']), 'texto': x['texto'], 'carpeta': 'voz_short'}
            for i, x in enumerate(sg['tomas'])]


def marcas_autor(d):
    """[(segundo, cx, cy)] de tus círculos y flechas (para_claude_marcas.json), en píxeles del original."""
    try:
        m = json.load(open(os.path.join(d, 'para_claude_marcas.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    out = []
    for s in m.get('senales', []):
        try:
            p = [float(x) for x in str(s['segundo']).split(':')]
            t = p[0] * 60 + p[1] if len(p) == 2 else p[0]
            out.append((t, s['zona']['x'] / 100 * W, s['zona']['y'] / 100 * H))
        except (KeyError, ValueError, TypeError):
            pass
    return out


def seguir(cap, s0, largo, marcas):
    """Dónde mirar en cada momento del tramo: [(t relativo, cx, cy)] y el zoom (1 con tu cara, más cerca en pantallas)."""
    import cv2, numpy as np
    import montaje
    det = montaje.detector_caras()
    puntos, previo, caras = [], None, 0
    n = max(2, int(largo / PASO_SEG) + 1)
    for i in range(n):
        t = min(largo, i * PASO_SEG)
        cap.set(cv2.CAP_PROP_POS_MSEC, (s0 + t) * 1000)
        ok, f = cap.read()
        if not ok:
            break
        chico = cv2.resize(f, (640, 360))
        punto = None
        if det is not None:
            det.setInputSize((640, 360))
            _, cs = det.detect(chico)
            cs = [c for c in (cs if cs is not None else []) if c[2] >= 640 * 0.03]
            if cs:
                c = max(cs, key=lambda c: c[2] * c[3])
                punto = ((c[0] + c[2] / 2) * 3, (c[1] + c[3] / 2) * 3, 'cara')
                caras += 1
        gris = cv2.GaussianBlur(cv2.cvtColor(chico, cv2.COLOR_BGR2GRAY), (9, 9), 0)
        if punto is None:
            for tm, x, y in marcas:  # tu círculo manda en su segundo (±1,5 s)
                if abs(tm - (s0 + t)) <= 1.5:
                    punto = (x, y, 'marca')
            if punto is None and previo is not None:
                dif = cv2.absdiff(gris, previo)
                _, mov = cv2.threshold(dif, 18, 255, cv2.THRESH_BINARY)
                if mov.mean() > 0.4:  # algo cambió de verdad (no solo ruido)
                    m = cv2.moments(mov, True)
                    if m['m00'] > 0:
                        punto = (m['m10'] / m['m00'] * 3, m['m01'] / m['m00'] * 3, 'mov')
        previo = gris
        puntos.append((t, punto))
    con_cara = caras >= max(1, len(puntos) * 0.4)
    zoom = 1.0 if con_cara else ZOOM_PANTALLA
    # se rellenan los huecos con el último punto conocido y se suaviza (sin saltos bruscos)
    cx, cy, out = W / 2, H / 2, []
    primero = next((p for _, p in puntos if p), None)
    if primero:
        cx, cy = primero[0], primero[1]
    import statistics
    ultimos = []
    for t, p in puntos:
        if p and (not con_cara or p[2] == 'cara'):
            ultimos = (ultimos + [p])[-4:]  # la mediana de los últimos 2 s: la mano que pasa no arrastra el cuadro
            mx, my = statistics.median(q[0] for q in ultimos), statistics.median(q[1] for q in ultimos)
            dx, dy = (mx - cx) * 0.2, (my - cy) * 0.2
            cx, cy = cx + max(-50, min(50, dx)), cy + max(-40, min(40, dy))
        out.append((t, cx, cy))
    return out, zoom


def expr(claves, i_val, lo, hi):
    """Expresión de ffmpeg que va de una clave a la siguiente en línea recta (t = segundos del tramo)."""
    vals = [(t, min(max(v, lo), hi)) for t, v in ((c[0], c[i_val]) for c in claves)]
    if len(vals) == 1:
        return f'{vals[0][1]:.1f}'
    e = f'{vals[-1][1]:.1f}'
    for (t0, v0), (t1, v1) in reversed(list(zip(vals, vals[1:]))):
        e = f'if(lt(t,{t1:.2f}),{v0:.1f}+({v1 - v0:.1f})*(t-{t0:.2f})/{max(0.01, t1 - t0):.2f},{e})'
    return e


def palabras_voz(d, bid, carpeta='voz'):
    """[(inicio, fin, palabra)] de la voz de un bloque, con los tiempos por letra de ElevenLabs."""
    try:
        a = json.load(open(os.path.join(d, carpeta, f'{bid}.align.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    out, actual, ini = [], '', None
    for ch, t0, t1 in zip(a['characters'], a['character_start_times_seconds'], a['character_end_times_seconds']):
        if ch.isspace():
            if actual:
                out.append((ini, fin, actual)); actual = ''
            continue
        if not actual:
            ini = t0
        actual += ch; fin = t1
    if actual:
        out.append((ini, fin, actual))
    return out


def ass_tiempo(s):
    s = max(0.0, s)
    return f'{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}'


def subtitulos(d, tomas, retraso):
    lineas = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {SW}', f'PlayResY: {SH}', '', '[V4+ Styles]',
              'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, '
              'StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
              'Style: S,Arial Black,84,&H00FFFFFF,&H0000D2FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,7,2,2,60,60,560,1',
              '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    t0 = 0.0
    for c in tomas:
        pal = palabras_voz(d, c['id'], c.get('carpeta', 'voz'))
        for i in range(0, len(pal), 3):  # de a 3 palabras: se leen de un vistazo en el celular
            grupo = pal[i:i + 3]
            txt = ' '.join(p[2] for p in grupo).replace('{', '').replace('}', '')
            lineas.append(f'Dialogue: 0,{ass_tiempo(t0 + retraso + grupo[0][0])},{ass_tiempo(t0 + retraso + grupo[-1][1] + 0.05)},'
                          f'S,,0,0,0,,{txt.upper()}')
        t0 += c['largo']
    return '\n'.join(lineas) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--duracion', type=float, default=60)
    ap.add_argument('--salida', default='SHORT.mp4')
    ap.add_argument('--voz-nueva', action='store_true', help='voz escrita para el Short (short_guion.json), gasta ElevenLabs')
    a = ap.parse_args()
    import cv2
    d = os.path.abspath(a.proyecto)
    orig = os.path.join(d, 'original.mp4')
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    dur_video = duracion(orig)
    if a.voz_nueva:
        tomas = voz_nueva(d)
    else:
        tomas = elegir(d, g, a.duracion, dur_video)
    if not tomas:
        raise SystemExit('ERROR: no encontré tomas con voz para el Short (falta generar la voz del video).')
    print(f'Elegí {len(tomas)} tomas para un Short de {a.duracion:.0f} s:', flush=True)
    for c in tomas:
        print(f"· {c['id']} ({c['voz']:.1f} s): {c['por_que']}", flush=True)
    marcas = marcas_autor(d)
    tmp = codificar.temporal('short')
    retraso = 0.15
    cap = cv2.VideoCapture(orig)
    partes = []
    for i, c in enumerate(tomas):
        largo = round(max(c['voz'] + 0.4, MIN_TOMA if c.get('carpeta') == 'voz_short' else 0), 2)  # que se alcance a ver la acción
        s0 = min(c['src_inicio'], max(0.0, dur_video - largo - 0.1))
        claves, zoom = seguir(cap, s0, largo, marcas)
        ch = round(H / zoom / 2) * 2
        cw = round(ch * 9 / 16 / 2) * 2
        cl = [(t, x - cw / 2, y - ch / 2) for t, x, y in claves]
        c.update(largo=largo, src_inicio=round(s0, 2), zoom=zoom)
        vf = (f"crop={cw}:{ch}:x='{expr(cl, 1, 0, W - cw)}':y='{expr(cl, 2, 0, H - ch)}',"
              f'scale={SW}:{SH},setsar=1,fps=30,format=yuv420p')
        p = os.path.join(tmp, f'p{i:02d}.mp4')
        print(f"· armo {c['id']} ({'tu cara' if zoom == 1 else 'pantalla, con zoom'})…", flush=True)
        codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{s0:.3f}', '-t', f'{largo:.3f}', '-i', orig,
                       '-i', os.path.join(d, c.get('carpeta', 'voz'), f"{c['id']}.mp3"),
                       '-filter_complex', f'[0:v]{vf}[v];[1:a]adelay={int(retraso * 1000)}:all=1,apad,atrim=0:{largo:.3f},'
                       'aresample=44100,aformat=channel_layouts=stereo[a]',
                       '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19',
                       '-c:a', 'aac', '-b:a', '160k', p], check=True)
        partes.append(p)
    cap.release()
    lista = os.path.join(tmp, 'lista.txt')
    open(lista, 'w', encoding='utf-8').write(''.join(f"file '{p}'\n".replace('\\', '/') for p in partes))
    junto = os.path.join(tmp, 'junto.mp4')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', junto], check=True)
    open(os.path.join(d, 'short_subs.ass'), 'w', encoding='utf-8').write(subtitulos(d, tomas, retraso))
    entradas = ['-i', junto]
    if os.path.exists(MUSICA):
        entradas += ['-stream_loop', '-1', '-i', MUSICA]
        audio = '[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]'
    else:
        audio = '[0:a]anull[a]'
    print('· subtítulos y música…', flush=True)
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + entradas +
                  ['-filter_complex', f'[0:v]ass=short_subs.ass[v];{audio}', '-map', '[v]', '-map', '[a]',
                   '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart',
                   a.salida], check=True, cwd=d)
    total = sum(c['largo'] for c in tomas)
    json.dump({'duracion_pedida': a.duracion, 'duracion': round(total, 1), 'formato': '9:16',
               'tomas': [{k: c[k] for k in ('id', 'src_inicio', 'largo', 'zoom', 'por_que', 'texto')} for c in tomas]},
              open(os.path.join(d, 'short.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print(f'Listo {a.salida}: {total:.0f} s, {len(tomas)} tomas, 1080×1920.', flush=True)


if __name__ == '__main__':
    main()
