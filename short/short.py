"""Short vertical 9:16 (como «Auto Resaltar» + «Reencuadre automático» de Filmora), hecho con lo que la app ya sabe del video.

Uso (desde la carpeta del proyecto): python short.py --proyecto . --duracion 60

1. Elige las tomas: el gancho del inicio y los bloques del guion con tus ⭐ cortes importantes, las acciones (volumen, power,
   pegar, Connect, paso cuatro, Omitir…) y el resultado (sin candado, crear cuenta), sin la parte de promoción (comentarios,
   suscribirse, grupo, WhatsApp de soporte), hasta llenar la duración. Deja el plan con el porqué de cada toma en short.json.
2. Reencuadra a 9:16 siguiendo lo importante: tu cara si sales (cuadro completo en alto); si no, el teléfono (el detector de
   deteccion/ lo ve aunque tenga la pantalla negra) con el zoom justo para que entre entero; si no hay teléfono, lo que se
   mueve o cambia en la pantalla (cursor, botón) con un zoom suave. Donde marcaste un círculo, encuadra esa zona. Nunca acelera.
3. Voz: las mismas voces del video (voz/Lxx.mp3), así que no gasta créditos. Con --voz-nueva usa el guion propio del Short
   (short_guion.json: tomas con src_inicio, texto y por_que, escrito para el Short, con más gancho) y genera esa voz con
   ElevenLabs en voz_short/ (gasta ~1 crédito por letra; lo que no cambió se reutiliza). Subtítulos grandes y tu música fija.
4. Extras al final (short_extras.json, se eligen en el módulo): 🎥 un testimonio (tu video, ajustado a vertical), 🌐 tus
   páginas en pantalla y 📺 el cierre «mira el video completo» con tu texto y, si subiste uno, tu audio.
Deja SHORT.mp4 en la carpeta del proyecto.
"""
import argparse, json, os, re, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
sys.path.insert(0, os.path.join(RAIZ, 'montaje'))
sys.path.insert(0, os.path.join(RAIZ, 'deteccion'))
import codificar  # noqa: E402  con la tarjeta NVIDIA o Intel si la hay
import deteccion  # noqa: E402  ve el teléfono aunque tenga la pantalla negra

W, H = 1920, 1080          # el original
SW, SH = 1080, 1920        # el Short
PASO_SEG = 0.5             # cada cuánto se mira dónde está lo importante
ZOOM_PANTALLA = 1.2        # sin cara: un poco más cerca de lo que se mueve (sin cortar el teléfono)
ZOOM_TELEFONO = 1.4        # con el teléfono a la vista: lo más cerca que se acerca, siempre que el teléfono entre entero
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


FUENTES = [r'C:\Windows\Fonts\ariblk.ttf', r'C:\Windows\Fonts\arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']


def leer_extras(d):
    try:
        x = json.load(open(os.path.join(d, 'short_extras.json'), encoding='utf-8'))
        return x if isinstance(x, dict) else {}
    except (OSError, ValueError):
        return {}


def paginas_del_autor():
    """Las webs de «Mis páginas» (solo nombre y dirección; nada más de los ajustes)."""
    try:
        r = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')).get('paginas', [])
        return [str(x.get('url')).strip() for x in r if isinstance(x, dict) and str(x.get('url') or '').strip()]
    except (OSError, ValueError, AttributeError):
        return []


def parte_testimonio(d, archivo, salida):
    """Tu video de testimonio en 9:16: entero al medio y, detrás, el mismo video ampliado y borroso (sin barras negras)."""
    f = os.path.join(d, archivo)
    vf = (f'[0:v]split[a][b];[a]scale={SW}:{SH}:force_original_aspect_ratio=increase,crop={SW}:{SH},boxblur=24:2[fondo];'
          f'[b]scale={SW}:{SH}:force_original_aspect_ratio=decrease[fr];[fondo][fr]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,format=yuv420p[v]')
    tiene_audio = bool(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', f],
                                      capture_output=True, text=True).stdout.strip())
    entradas = ['-i', f] + ([] if tiene_audio else ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo'])
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + entradas +
                  ['-filter_complex', vf + f';[{0 if tiene_audio else 1}:a]aresample=44100,aformat=channel_layouts=stereo[au]',
                   '-map', '[v]', '-map', '[au]', '-shortest', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19',
                   '-c:a', 'aac', '-b:a', '160k', salida], check=True)


def parte_final(d, ultimo, cfg, paginas, salida):
    """La tarjeta del cierre: el último cuadro del Short oscurecido, con «mira el video completo» y/o tus páginas, y tu audio."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    fuente = lambda n: next((ImageFont.truetype(f, n) for f in FUENTES if os.path.exists(f)), ImageFont.load_default())
    png = salida + '.png'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-sseof', '-0.2', '-i', ultimo, '-frames:v', '1', png], check=True)
    img = Image.open(png).convert('RGB').filter(ImageFilter.GaussianBlur(18))
    img = Image.blend(img, Image.new('RGB', img.size, (8, 8, 16)), 0.55)
    dib = ImageDraw.Draw(img)

    def partir(texto, f, ancho):
        lineas, actual = [], ''
        for p in texto.split():
            prueba = (actual + ' ' + p).strip()
            if dib.textlength(prueba, font=f) <= ancho:
                actual = prueba
            else:
                lineas.append(actual); actual = p
        return lineas + ([actual] if actual else [])
    y = 560
    texto = str(cfg.get('final_texto') or '').strip() if cfg.get('final') else ''
    texto = ''.join(c for c in texto if ord(c) < 0x2190).strip()  # la letra no trae emojis (saldrían como cuadraditos)
    if texto:
        f = fuente(76)
        for ln in partir(texto, f, SW - 140):
            dib.text((SW / 2, y), ln, font=f, fill='white', anchor='mm', stroke_width=4, stroke_fill='black'); y += 100
        y += 40
    if paginas:
        f = fuente(58)
        for p in paginas:
            w = dib.textlength(p, font=f) + 80
            dib.rounded_rectangle([SW / 2 - w / 2, y - 48, SW / 2 + w / 2, y + 48], radius=48, fill='white')
            dib.text((SW / 2, y), p, font=f, fill=(17, 17, 17), anchor='mm'); y += 130
    img.save(png)
    audio = os.path.join(d, cfg['final_audio']) if cfg.get('final') and cfg.get('final_audio') and os.path.exists(os.path.join(d, cfg['final_audio'])) else None
    dur = max(3.0, (duracion(audio) + 0.6) if audio else float(cfg.get('final_dur') or 4))
    entradas = ['-loop', '1', '-t', f'{dur:.2f}', '-i', png] + (['-i', audio] if audio else ['-f', 'lavfi', '-t', f'{dur:.2f}', '-i', 'anullsrc=r=44100:cl=stereo'])
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + entradas +
                  ['-filter_complex', f"[0:v]scale={SW}:{SH},zoompan=z='min(zoom+0.0006,1.06)':d=1:s={SW}x{SH}:fps=30,format=yuv420p[v];"
                   f'[1:a]aresample=44100,aformat=channel_layouts=stereo,apad,atrim=0:{dur:.2f}[au]',
                   '-map', '[v]', '-map', '[au]', '-t', f'{dur:.2f}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19',
                   '-c:a', 'aac', '-b:a', '160k', salida], check=True)
    return dur


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


def seguir(cap, s0, largo, marcas, memoria=None):
    """Dónde mirar en cada momento del tramo: [(t relativo, cx, cy)], el zoom (1 con tu cara, más cerca en pantallas) y
    qué se sigue ('cara', 'telefono' o 'pantalla').

    Si el detector ve el teléfono en buena parte del tramo, se sigue al teléfono (aunque su pantalla esté negra, como en
    fastboot) con el zoom justo para que entre entero.

    Lo importante en un tutorial es lo que CAMBIA respecto del fondo: el teléfono en la mano, su pantalla, la ventana del
    programa. El fondo (la mesa, el cubo de Motorola, el cartel «Frp») queda igual en todo el tramo, así que se saca con la
    mediana de los cuadros; de lo que queda, se mira la zona con más detalle (letras, botones, iconos), no los guantes lisos."""
    import cv2, numpy as np
    import montaje
    det = montaje.detector_caras()
    cuadros, caras, telefonos = [], [], []
    n = max(2, int(largo / PASO_SEG) + 1)
    for i in range(n):
        t = min(largo, i * PASO_SEG)
        cap.set(cv2.CAP_PROP_POS_MSEC, (s0 + t) * 1000)
        ok, f = cap.read()
        if not ok:
            break
        chico = cv2.resize(f, (640, 360))
        cara = None
        if det is not None:
            det.setInputSize((640, 360))
            _, cs = det.detect(chico)
            cs = [c for c in (cs if cs is not None else []) if c[2] >= 640 * 0.03]
            if cs:
                c = max(cs, key=lambda c: c[2] * c[3])
                cara = ((c[0] + c[2] / 2) * 3, (c[1] + c[3] / 2) * 3)
        cuadros.append((t, cv2.GaussianBlur(cv2.cvtColor(chico, cv2.COLOR_BGR2GRAY), (5, 5), 0)))
        caras.append(cara)
        telefonos.append(deteccion.telefono(memoria.ver(s0 + t, f)) if memoria else None)
    if not cuadros:
        return [(0.0, W / 2, H / 2)], 1.0, 'pantalla'
    con_cara = sum(1 for c in caras if c) >= max(1, len(caras) * 0.4)
    con_tel = not con_cara and sum(1 for c in telefonos if c) >= max(1, len(telefonos) * 0.4)
    fondo = np.median(np.stack([g for _, g in cuadros]), axis=0).astype(np.uint8)
    puntos = []
    for (t, g), cara, tel in zip(cuadros, caras, telefonos):
        punto = (cara[0], cara[1], 'cara') if cara else None
        if punto is None:
            for tm, x, y in marcas:  # tu círculo manda en su segundo (±1,5 s)
                if abs(tm - (s0 + t)) <= 1.5:
                    punto = (x, y, 'marca')
        if punto is None and tel:  # el teléfono que ve el detector
            punto = (tel[0] + tel[2] / 2, tel[1] + tel[3] / 2, 'telefono')
        if punto is None and not con_tel:  # sin teléfono a la vista: lo que cambia en la pantalla
            bordes = cv2.dilate(cv2.Canny(g, 40, 120), np.ones((3, 3), np.uint8)).astype(np.float32)
            cambia = cv2.dilate((cv2.absdiff(g, fondo) > 18).astype(np.uint8), np.ones((15, 15), np.uint8))
            if cambia.mean() > 0.03:  # hay algo que se mueve sobre el fondo (el teléfono en la mano)
                # la pantalla encendida es lo CLARO de lo que se mueve: los guantes son negros y la mesa y la pared no se
                # mueven (quedan en el fondo). Su detalle (letras, iconos) suma un poco más.
                clara = (g > 150).astype(np.float32)
                peso = cambia * clara * (60 + bordes * 0.3)
            else:  # todo quieto (una ventana de la PC a pantalla completa): la parte con más detalle
                peso = bordes
            densidad = cv2.GaussianBlur(peso, (0, 0), 30)
            _, pico, _, (px, py) = cv2.minMaxLoc(densidad)
            if pico > 3:
                punto = (px * 3, py * 3, 'pantalla')
        puntos.append((t, punto))
    zoom = 1.0 if con_cara else ZOOM_PANTALLA
    # se suaviza (sin saltos bruscos): mediana de los últimos 2 s y un acercamiento lento
    import statistics
    if con_tel:  # el zoom justo para que el teléfono entre entero, con un poco de aire alrededor
        cajas = [c for c in telefonos if c]
        alto, ancho = statistics.median(c[3] for c in cajas), statistics.median(c[2] for c in cajas)
        zoom = round(max(1.0, min(ZOOM_TELEFONO, H / (alto * 1.15), H * 9 / 16 / (ancho * 1.1))), 2)
        cajas = []  # lo que tiene que quedar adentro en cada momento: tu cara, tu círculo o el teléfono
        for (t, _), cara, tel, (_, p) in zip(cuadros, caras, telefonos, puntos):
            if p and p[2] != 'telefono':
                lado = 300 if p[2] == 'cara' else 200
                cajas.append((t, [p[0] - lado / 2, p[1] - lado / 2, lado, lado]))
            else:
                cajas.append((t, tel))
        return contener(cajas, H / zoom * 9 / 16, H / zoom), zoom, 'telefono'
    validos = [p for _, p in puntos if p and (not con_cara or p[2] == 'cara')]
    cx, cy = (statistics.median(p[0] for p in validos), statistics.median(p[1] for p in validos)) if validos else (W / 2, H / 2)
    ultimos, out = [], []
    for t, p in puntos:
        if p and (not con_cara or p[2] == 'cara'):
            ultimos = (ultimos + [p])[-4:]
            mx, my = statistics.median(q[0] for q in ultimos), statistics.median(q[1] for q in ultimos)
            cx += max(-45, min(45, (mx - cx) * 0.25)); cy += max(-35, min(35, (my - cy) * 0.25))
        out.append((t, cx, cy))
    return out, zoom, 'cara' if con_cara else 'telefono' if con_tel else 'pantalla'


def contener(cajas, cw, ch, aire=0.04):
    """[(t, cx, cy)] del recuadro de cw×ch que deja entera cada caja [(t, [x, y, ancho, alto] o None)], moviéndose solo
    cuando la caja se saldría: así el teléfono nunca queda cortado y el cuadro no baila. Si una caja es más grande que el
    recuadro, se centra en ella."""
    conocidas = [i for i, (_, c) in enumerate(cajas) if c]
    if not conocidas:
        return [(t, W / 2, H / 2) for t, _ in cajas]
    out, cx, cy = [], None, None
    for i, (t, c) in enumerate(cajas):
        x, y, w, h = c or cajas[min(conocidas, key=lambda j: abs(j - i))][1]  # sin caja en ese momento: la más cercana
        mx, my = cw * aire, ch * aire
        lox, hix = x + w + mx - cw / 2, x - mx + cw / 2
        loy, hiy = y + h + my - ch / 2, y - my + ch / 2
        if lox > hix:  # no entra a lo ancho: al centro, sin moverse por unos píxeles de diferencia
            lox = hix = x + w / 2 if cx is None or abs(cx - x - w / 2) > cw * aire else cx
        if loy > hiy:
            loy = hiy = y + h / 2 if cy is None or abs(cy - y - h / 2) > ch * aire else cy
        if cx is None:
            cx, cy = (lox + hix) / 2, (loy + hiy) / 2
        cx, cy = min(max(cx, lox), hix), min(max(cy, loy), hiy)
        out.append((t, cx, cy))
    return out


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
    extras = leer_extras(d)
    reservado = 0.0  # lo que ocupan el testimonio y el cierre: sale de la duración que pediste
    if extras.get('testimonio') and extras.get('testimonio_archivo') and os.path.exists(os.path.join(d, extras['testimonio_archivo'])):
        reservado += duracion(os.path.join(d, extras['testimonio_archivo']))
    if extras.get('final') or extras.get('paginas'):
        reservado += float(extras.get('final_dur') or 4)
    if a.voz_nueva:
        tomas = voz_nueva(d)
    else:
        if reservado:
            print(f'· {reservado:.0f} s son del testimonio y el cierre: elijo tomas para {max(10, a.duracion - reservado):.0f} s', flush=True)
        tomas = elegir(d, g, max(10.0, a.duracion - reservado), dur_video)
    if not tomas:
        raise SystemExit('ERROR: no encontré tomas con voz para el Short (falta generar la voz del video).')
    print(f'Elegí {len(tomas)} tomas para un Short de {a.duracion:.0f} s:', flush=True)
    for c in tomas:
        print(f"· {c['id']} ({c['voz']:.1f} s): {c['por_que']}", flush=True)
    marcas = marcas_autor(d)
    memoria = deteccion.Memoria(orig)
    tmp = codificar.temporal('short')
    retraso = 0.15
    cap = cv2.VideoCapture(orig)
    partes = []
    for i, c in enumerate(tomas):
        largo = round(max(c['voz'] + 0.4, MIN_TOMA if c.get('carpeta') == 'voz_short' else 0), 2)  # que se alcance a ver la acción
        s0 = min(c['src_inicio'], max(0.0, dur_video - largo - 0.1))
        claves, zoom, encuadre = seguir(cap, s0, largo, marcas, memoria)
        ch = round(H / zoom / 2) * 2
        cw = round(ch * 9 / 16 / 2) * 2
        cl = [(t, x - cw / 2, y - ch / 2) for t, x, y in claves]
        c.update(largo=largo, src_inicio=round(s0, 2), zoom=zoom, encuadre=encuadre)
        vf = (f"crop={cw}:{ch}:x='{expr(cl, 1, 0, W - cw)}':y='{expr(cl, 2, 0, H - ch)}',"
              f'scale={SW}:{SH},setsar=1,fps=30,format=yuv420p')
        p = os.path.join(tmp, f'p{i:02d}.mp4')
        que = {'cara': 'tu cara', 'telefono': f'el teléfono, zoom ×{zoom:g}'}.get(encuadre, 'pantalla, con zoom')
        print(f"· armo {c['id']} ({que})…", flush=True)
        codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{s0:.3f}', '-t', f'{largo:.3f}', '-i', orig,
                       '-i', os.path.join(d, c.get('carpeta', 'voz'), f"{c['id']}.mp3"),
                       '-filter_complex', f'[0:v]{vf}[v];[1:a]adelay={int(retraso * 1000)}:all=1,apad,atrim=0:{largo:.3f},'
                       'aresample=44100,aformat=channel_layouts=stereo[a]',
                       '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19',
                       '-c:a', 'aac', '-b:a', '160k', p], check=True)
        partes.append(p)
    cap.release()
    memoria.guardar()
    if extras.get('testimonio') and extras.get('testimonio_archivo') and os.path.exists(os.path.join(d, extras['testimonio_archivo'])):
        print('· testimonio…', flush=True)
        p = os.path.join(tmp, 'testimonio.mp4')
        parte_testimonio(d, extras['testimonio_archivo'], p)
        partes.append(p)
    paginas = ([x.strip() for x in str(extras.get('paginas_texto') or '').split('·') if x.strip()] or paginas_del_autor()) if extras.get('paginas') else []
    if (extras.get('final') and (extras.get('final_texto') or extras.get('final_audio'))) or paginas:
        print('· cierre (ver el video completo / páginas)…', flush=True)
        p = os.path.join(tmp, 'final.mp4')
        parte_final(d, partes[-1], extras, paginas, p)
        partes.append(p)
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
    total = duracion(os.path.join(d, a.salida))  # con el testimonio y el cierre
    json.dump({'duracion_pedida': a.duracion, 'duracion': round(total, 1), 'formato': '9:16',
               'tomas': [{k: c[k] for k in ('id', 'src_inicio', 'largo', 'zoom', 'encuadre', 'por_que', 'texto')} for c in tomas]},
              open(os.path.join(d, 'short.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print(f'Listo {a.salida}: {total:.0f} s, {len(tomas)} tomas, 1080×1920.', flush=True)


if __name__ == '__main__':
    main()
