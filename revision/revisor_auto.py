"""«✅ Revisor automático»: corre solo al terminar cada render (Shorts y videos largos), gratis y en la PC, y no deja dar
por listo un video que falle. Pedido de fabian (02/11/2026, después de un Short con subtítulos encimados, la ventana del
programa cortada justo cuando la voz decía «OKAY, Finished», 19 s de la misma pantalla al inicio y datos privados a la vista):
«¿podemos usar algún script, algoritmo, patrón para que no vuelva a suceder?».

Revisa:
  1. Subtítulos (el .ass quemado): nunca dos a la vez, una sola línea, dentro de la zona segura (en Shorts, fuera del
     ~20 % de abajo, donde van los botones de YouTube).
  2. Planos largos: en los primeros 30 s ningún plano igual más de 5 s (regla «el inicio rota escenas»).
  3. Lo que nombra la voz se ve: en el segundo en que la voz dice «OKAY», «Finished», «Erase FRP», «Omitir»…, esa palabra
     tiene que leerse en el cuadro (OCR local, sin contar la franja de los subtítulos).
  4. Duración del Short (15 s a 3 min).
  5. Datos privados (APAGADO por defecto, --privados: fabian no quiere difuminados en los Shorts): OCR + patrones (correo, IMEI de 15 dígitos, seriales/keys largas, teléfonos, montos con $) en cada
     segundo. Con --arreglar los difumina con un recuadro chico solo sobre el dato y lo anota.
  5. Voz vs imagen con IA de visión: se marca «omitido» si no hay una IA local con visión (no gasta).
Deja <video>.revision.json y <video>.revision.md al lado del video. Devuelve 1 si algo falla.

Uso: python revisor_auto.py VIDEO.mp4 [--ass subs.ass] [--short] [--arreglar]
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile

import cv2
import numpy as np

PALABRAS_PANTALLA = {'okay', 'finished', 'erase', 'omitir', 'fastboot', 'verifica', 'ajustes', 'reboot'}  # palabras completas
DUR_SHORT = (15.0, 180.0)  # un Short entre 15 s y 3 min
PRIVADO = [
    ('correo', re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')),
    ('IMEI', re.compile(r'(?<!\d)\d{15}(?!\d)')),
    ('serial/key', re.compile(r'\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{12,}\b')),
    ('teléfono', re.compile(r'\+?\d[\d\s-]{8,}\d')),
    ('monto', re.compile(r'\$\s?\d')),
]
PLANO_MAX, INICIO = 5.0, 30.0


def normal(txt):
    """Minúsculas y sin acentos, para comparar palabras («Omitir» = «omitir», «Configuración» = «configuracion»)."""
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', (txt or '').lower()) if unicodedata.category(c) != 'Mn')


def palabras(txt):
    return set(re.findall(r'[a-z0-9]{3,}', normal(txt)))


def _ocr():
    try:
        from rapidocr_onnxruntime import RapidOCR
        return RapidOCR()
    except Exception:
        return None


def tiempo_ass(s):
    h, m, x = s.split(':')
    return int(h) * 3600 + int(m) * 60 + float(x)


def leer_ass(f):
    """[(inicio, fin, texto sin etiquetas, palabra dicha)], el MarginV del estilo y si permite cortar líneas."""
    ev, margen, wrap2 = [], 0, False
    for ln in open(f, encoding='utf-8'):
        if ln.startswith('Style:'):
            margen = int(ln.strip().split(',')[21])
        elif ln.startswith('WrapStyle: 2'):
            wrap2 = True
        elif ln.startswith('Dialogue:'):
            p = ln.rstrip('\n').split(',', 9)
            txt = p[9]
            dicha = re.search(r'\{[^}]*\\c&H0000D2FF&[^}]*\}([^{]+)', txt)
            ev.append((tiempo_ass(p[1]), tiempo_ass(p[2]), re.sub(r'\{[^}]*\}', '', txt).replace('\\N', ' ').strip(),
                       dicha.group(1).strip() if dicha else ''))
    return ev, margen, wrap2


def revisar_subs(ev, margen, wrap2, alto, es_short):
    fallas = []
    for (a0, a1, t, _), (b0, _, u, _) in zip(ev, ev[1:]):
        if a1 > b0 + 0.005:
            fallas.append({'s': round(b0, 2), 'que': f'dos subtítulos a la vez: «{t}» y «{u}»'})
    for a0, _, t, _ in ev:
        if '\\N' in t or (not wrap2 and len(t) > 16):
            fallas.append({'s': round(a0, 2), 'que': f'subtítulo que puede ir en dos líneas: «{t}»'})
    if es_short and margen < alto * 0.2:
        fallas.append({'s': 0, 'que': f'subtítulos muy abajo (a {margen} px del borde): los tapan los botones de YouTube'})
    return fallas


def muestras(video, cada, hasta=None):
    """[(segundo, cuadro)] cada «cada» segundos (hasta «hasta» s, si se da) y la duración del video."""
    c = cv2.VideoCapture(video)
    dur = c.get(cv2.CAP_PROP_FRAME_COUNT) / (c.get(cv2.CAP_PROP_FPS) or 30)
    t, out = 0.0, []
    while t < min(dur, hasta or dur):
        c.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = c.read()
        if ok:
            out.append((round(t, 2), fr))
        t += cada
    return out, dur


def revisar_planos(cuadros):
    """Planos de más de PLANO_MAX s en los primeros INICIO s. Un plano sigue mientras los colores del cuadro se parecen al
    primero (histograma de tono y saturación): así cuenta como «la misma escena» la pantalla de «Verifica tu cuenta» aunque
    la cámara se mueva un poco, como lo ve fabian."""
    fallas, ini, base = [], None, None
    previo = None
    for t, fr in cuadros:
        if t > INICIO:
            break
        h = cv2.calcHist([cv2.cvtColor(cv2.resize(fr, (108, 192)), cv2.COLOR_BGR2HSV)], [0, 1], None, [30, 16], [0, 180, 0, 256])
        cv2.normalize(h, h)
        if base is None or cv2.compareHist(base, h, cv2.HISTCMP_CORREL) < 0.7:
            if ini is not None and previo - ini > PLANO_MAX:
                fallas.append({'s': ini, 'que': f'el mismo plano {previo - ini:.0f} s seguidos (máx. {PLANO_MAX:.0f} s al inicio)'})
            ini, base = t, h
        previo = t
    if ini is not None and previo is not None and previo - ini > PLANO_MAX:
        fallas.append({'s': ini, 'que': f'el mismo plano {previo - ini:.0f} s seguidos (máx. {PLANO_MAX:.0f} s al inicio)'})
    return fallas


def texto_cuadro(ocr, fr, excluir=None):
    img = fr.copy()
    if excluir:
        img[excluir[0]:excluir[1]] = 0
    r, _ = ocr(img)
    return [(b, txt) for b, txt, _ in (r or [])]


def revisar_voz_pantalla(ocr, video, ev, banda):
    """En el momento en que se dice una palabra que se ve en pantalla, esa palabra tiene que leerse en el cuadro."""
    fallas, c = [], cv2.VideoCapture(video)
    for a0, a1, _, dicha in ev:
        w = normal(dicha).strip('.,¿?¡!:;…')
        if len(w) < 3 or w not in PALABRAS_PANTALLA:  # solo palabras completas que se ven en pantalla («era» no es «erase»)
            continue
        visto = False
        for dt in (0.0, 0.4, 0.8):
            c.set(cv2.CAP_PROP_POS_MSEC, (a0 + dt) * 1000)
            ok, fr = c.read()
            if ok and any(w in palabras(txt) for _, txt in texto_cuadro(ocr, fr, banda)):
                visto = True
                break
        if not visto:
            fallas.append({'s': round(a0, 2), 'que': f'la voz dice «{dicha}» y no se lee en el cuadro (recorte o zoom equivocado)'})
    return fallas


def logos_esperados(ev):
    """[(segundo, logo)] que la voz nombra (las palabras disparadoras de mis_conocimientos/logos/logos.json), con las mismas
    reglas que los pone logos.py (de a uno, sin repetir antes de 30 s)."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    carpeta = os.path.join(raiz, 'mis_conocimientos', 'logos')
    sys.path.insert(0, os.path.join(raiz, 'logos'))
    try:
        import logos as lg
        lib = lg.para_formato([l for l in json.load(open(os.path.join(carpeta, 'logos.json'), encoding='utf-8')).get('logos', [])
                               if os.path.isfile(os.path.join(carpeta, l.get('archivo', '')))], 'short')
    except Exception:
        return [], carpeta
    texto, tiempos = '', []
    for a0, _a1, _txt, dicha in ev:  # una palabra dicha por subtítulo (estilo C): el texto hablado con su segundo
        if dicha and (not tiempos or tiempos[-1][0] != a0):
            texto += dicha + ' '
            tiempos += [(a0, None)] * (len(dicha) + 1)
    out, visto, veces = [], {}, {}
    for pos, l in sorted(lg.menciones(texto, lib), key=lambda x: x[0]):
        s = tiempos[min(pos, len(tiempos) - 1)][0]
        if s - visto.get(l['archivo'], -999) >= lg.NO_REPETIR and veces.get(l['archivo'], 0) < int(l.get('max_veces') or 99):
            visto[l['archivo']] = s
            veces[l['archivo']] = veces.get(l['archivo'], 0) + 1  # como logos.py: «Google» sale una sola vez
            out.append((s, l))
    return out, carpeta


def revisar_logos(video, ev, alto_rel=0.30):
    """Cada logo que nombra la voz tiene que verse en ese momento (se busca el PNG en el cuadro, en su tamaño de Short)."""
    esperados, carpeta = logos_esperados(ev)
    fallas, c = [], cv2.VideoCapture(video)
    import logos as lg  # logos_esperados ya dejó su carpeta en sys.path
    for s, l in esperados:
        png = cv2.imread(os.path.join(carpeta, lg.del_idioma(l, carpeta, 'es', 'short')), cv2.IMREAD_UNCHANGED)
        if png is None:
            continue
        visto = False
        for dt in (0.35, 0.6):
            c.set(cv2.CAP_PROP_POS_MSEC, (s + dt) * 1000)
            ok, fr = c.read()
            if not ok:
                continue
            h = fr.shape[0]
            pos = lg.posicion(l, 'short')
            for esc in (1.0, 0.85, 1.15):
                if pos and pos['alto'] and not lg.es_tarjeta(l):  # su lugar y tamaño propios (el play, abajo a la izquierda)
                    alto = int(h * pos['alto'] * esc)
                    ancho = int(alto * png.shape[1] / png.shape[0])
                elif lg.es_tarjeta(l):  # la tarjeta de WhatsApp va con su tamaño propio de Short (logos.TARJETA)
                    ancho, alto = (int(v * esc) for v in lg.medida_tarjeta(l, 'short', fr.shape[1], h, png.shape[1] / png.shape[0]))
                else:
                    alto = int(h * alto_rel * esc * (0.52 if png.shape[1] / png.shape[0] > 1.3 else 1))
                    ancho = int(alto * png.shape[1] / png.shape[0])
                if not lg.es_tarjeta(l) and ancho > fr.shape[1] * 0.8:  # como logos.py: las insignias anchas se achican al 80 % del ancho
                    ancho = int(fr.shape[1] * 0.8 * esc)
                    alto = int(ancho * png.shape[0] / png.shape[1])
                if ancho >= fr.shape[1] or alto < 20:
                    continue
                chico = cv2.resize(png, (ancho, alto))
                plantilla = chico[:, :, :3]
                mascara = (chico[:, :, 3] > 128).astype(np.uint8) * 255 if png.shape[2] == 4 else None
                mascara = cv2.merge([mascara] * 3) if mascara is not None else None
                zona = fr if pos else fr[: int(h * 0.7)]  # los del centro, arriba de los subtítulos; con «pos_short», en todo el cuadro
                if zona.shape[0] < alto or zona.shape[1] < ancho:
                    continue
                r = cv2.matchTemplate(zona, plantilla, cv2.TM_CCORR_NORMED, mask=mascara)
                r = np.nan_to_num(r, nan=0, posinf=0, neginf=0)
                if float(r.max()) > 0.93:
                    visto = True
                    break
            if visto:
                break
        if not visto:
            fallas.append({'s': round(s, 2), 'que': f"la voz nombra {l.get('nombre') or l['archivo']} y su logo no aparece"})
    return fallas


def buscar_privados(ocr, cuadros, banda):
    hallados = []
    for t, fr in cuadros:
        for caja, txt in texto_cuadro(ocr, fr, banda):
            for nombre, rx in PRIVADO:
                if rx.search(txt.replace(' ', '') if nombre in ('IMEI', 'serial/key') else txt):
                    xs, ys = [p[0] for p in caja], [p[1] for p in caja]
                    hallados.append({'s': t, 'que': f'{nombre} a la vista: «{txt[:40]}»',
                                     'caja': [int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))]})
                    break
    return hallados


def difuminar(video, hallados, ventana=0.6):
    """Recuadro chico difuminado solo sobre cada dato, del segundo en que se vio ±ventana. El audio no se toca."""
    c = cv2.VideoCapture(video)
    fps = c.get(cv2.CAP_PROP_FPS) or 30
    w, h = int(c.get(cv2.CAP_PROP_FRAME_WIDTH)), int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
    tmp = tempfile.mkdtemp()
    mudo = os.path.join(tmp, 'v.mp4')
    out = cv2.VideoWriter(mudo, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
    i = 0
    while True:
        ok, fr = c.read()
        if not ok:
            break
        t = i / fps
        for x in hallados:
            if abs(t - x['s']) <= ventana:
                bx, by, bw, bh = x['caja']
                mx, my = int(bw * 0.15) + 6, int(bh * 0.3) + 6
                x0, y0, x1, y1 = max(0, bx - mx), max(0, by - my), min(w, bx + bw + mx), min(h, by + bh + my)
                if x1 - x0 > 4 and y1 - y0 > 4:
                    fr[y0:y1, x0:x1] = cv2.GaussianBlur(fr[y0:y1, x0:x1], (0, 0), 14)
        out.write(fr)
        i += 1
    out.release()
    respaldo = video.replace('.mp4', '_antes_revisor.mp4')
    shutil.copy2(video, respaldo)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', mudo, '-i', respaldo, '-map', '0:v', '-map', '1:a?',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-c:a', 'copy', '-movflags', '+faststart', video],
                   check=True)
    shutil.rmtree(tmp, ignore_errors=True)



# ---------- Revisión del video LARGO (fabian 15/11/2026, después del Honor 400 Lite: imagen 5,6 s adelantada a la voz desde
# 4:37 por un bloque que salió más corto, $50 y saldos a la vista, WhatsApp después del minuto 2, «así empieza» con el
# DESPUÉS en pantalla). Todas las marcas, en la app y en la nube. ----------
MONTO = re.compile(r'(\$\s?\d[\d.,]*(?![\d.,]*[a-z]))|(\d\s?(usd|us\$)\b)', re.I)  # «$1s» de un log no es un precio
REGLA_MIN = {'whatsapp': (None, 120.0), 'comenta': (None, 120.0), 'gsmprime': (60.0, 120.0), 'xiaomiunlock': (60.0, 120.0)}
VOZ_CARTEL = [({'empieza', 'antes', 'bloqueado'}, 'despues'), ({'termina', 'despues', 'resultado', 'libre'}, 'antes')]
PPM_MAX, PAUSA_MIN, VENTANA = 130.0, 1.4, 60.0  # tus videos top y tu voz: ~105-120 palabras/min con pausas


def duraciones_flujos(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,duration:format=duration', '-of', 'json', video],
                       capture_output=True, text=True)
    j = json.loads(r.stdout or '{}')
    d = {s['codec_type']: float(s['duration']) for s in j.get('streams', []) if s.get('duration') not in (None, 'N/A')}
    return d.get('video'), d.get('audio')


def revisar_av(video):
    """Imagen y sonido tienen que durar lo mismo: si la imagen es más corta, algún tramo se cortó y TODO lo que sigue
    va adelantado a la voz (pasó con un bloque de 13,5 s que debía durar 19,2 s)."""
    v, a = duraciones_flujos(video)
    if v and a and abs(v - a) > 0.3:
        return [{'s': round(min(v, a), 1), 'que': f'la imagen dura {v:.1f} s y el sonido {a:.1f} s: un tramo salió más corto '
                                                  f'y la imagen va {abs(a - v):.1f} s desfasada de la voz desde ese tramo'}]
    return []


def revisar_bloques(info):
    """{bloque: {'D': segundos esperados, 'f': archivo}}: cada tramo armado dura lo que dice la voz (±0,1 s)."""
    fallas = []
    for b, x in info.items():
        f = x.get('f')
        if f and os.path.exists(f):
            v, _ = duraciones_flujos(f)
            if v and abs(v - x['D']) > 0.1:
                fallas.append({'s': 0, 'que': f'{b}: dura {v:.2f} s y debería {x["D"]:.2f} s (cuadros viejos o un tramo vacío)'})
    return fallas


def ev_de_palabras(ws):
    """[[palabra, ini, fin]] (tiempos de la voz, ya en el tiempo del video) -> eventos como los del .ass, una palabra cada uno."""
    return [(a, b, w, w) for w, a, b in ws]


def ev_de_srt(f):
    """Frases del .srt -> una palabra por evento, repartiendo el tiempo de la frase (sirve para las reglas de minutos)."""
    ev, bloque = [], open(f, encoding='utf-8').read().split('\n\n')
    for b in bloque:
        m = re.search(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)\s*\n(.+)', b, re.S)
        if not m:
            continue
        g = [int(x) for x in m.groups()[:8]]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000; z = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        ws = m.group(9).replace('\n', ' ').split()
        for i, w in enumerate(ws):
            t0 = a + (z - a) * i / len(ws); ev.append((t0, a + (z - a) * (i + 1) / len(ws), w, w))
    return ev


PASO = re.compile(r'^(descarg\w*|baj\w*|apag\w*|apagu\w*|conect\w*|abrimos|abre|abr[ií]s|mant[eé]n\w*|presion\w*|instal\w*|'
                  r'entramos|entra|copi\w*|pulsa\w*|toca\w*|ingres\w*|marca\w*|escrib\w*)[.,:;!?]*$', re.I)
PASO_MAX, PASO_DESDE = 90.0, 20.0  # revisión grande 15/11: el primer paso real antes del 1:30 (el inicio de 30-40 s no cuenta)


def revisar_primer_paso(ev, dur):
    """Todas las marcas: el primer paso real (descargar, apagar, conectar, abrir, entrar al modo…) antes del 1:30.
    Se mira la primera vez que la voz dice un verbo de paso después del inicio (desde los 20 s)."""
    if dur < 150:
        return []
    for a, _, w, _ in ev:
        if a >= PASO_DESDE and PASO.match(str(w).strip()):
            return [] if a <= PASO_MAX else [{'s': round(a, 1), 'que': f'el primer paso («{w}») llega en {mmss(a)}: debe empezar '
                                                                       f'antes del 1:30 (inicio de 30-40 s, lo legal en una frase)'}]
    return [{'s': 0, 'que': 'la voz no dice ningún paso (descargar, apagar, conectar, abrir…)'}]


def revisar_reglas_minuto(ev, dur):
    """Reglas fijas de TODOS los tutoriales: tarjetas de WhatsApp + invitar a comentar antes del minuto 2; páginas
    GSMPRIME.CO y XIAOMIUNLOCK.COM entre el minuto 1 y 2 (se mira lo que dice la voz)."""
    if dur < 150:
        return []
    fallas = []
    for clave, (desde, hasta) in REGLA_MIN.items():
        ts = momentos(ev, clave)
        if not ts:
            fallas.append({'s': 0, 'que': f'la voz nunca dice «{clave}» (regla de todos los tutoriales)'})
        elif not any((desde is None or t >= desde) and t <= hasta for t in ts):
            fallas.append({'s': round(ts[0], 1), 'que': f'«{clave}» sale en {mmss(ts[0])} y debe ir '
                                                     + (f'entre {mmss(desde)} y {mmss(hasta)}' if desde else f'antes de {mmss(hasta)}')})
    return fallas


def momentos(ev, clave):
    """Segundos en que la voz dice «clave», aunque venga deletreada en varias palabras («G S M Prime punto co»,
    «Xiaomi Unlock punto com», «Whats App»)."""
    ws = [(a, re.sub(r'[^a-z0-9]', '', normal(t))) for a, _, t, _ in ev]
    out = []
    for i in range(len(ws)):
        junto = ''
        for a, w in ws[i:i + 6]:
            if a - ws[i][0] > 4:  # solo palabras seguidas de la misma frase
                break
            junto += w
            if clave in junto:
                if not out or ws[i][0] - out[-1] > 3:
                    out.append(ws[i][0])
                break
            if len(junto) > len(clave) + 12:
                break
    return out


def mmss(s):
    return f'{int(s // 60)}:{int(s % 60):02d}'


def revisar_ritmo(ev):
    """La voz no puede ir «agresiva»: máx. PPM_MAX palabras por minuto hablando y, en cada minuto, al menos una pausa
    de PAUSA_MIN s (respiro con música). Solo con tiempos por palabra."""
    ws = [(a, b) for a, b, t, _ in ev if t.strip()]
    if len(ws) < 40:
        return []
    fallas = []
    fin = ws[-1][1]
    for i in range(0, int(fin // VENTANA) + 1):
        t0, t1 = i * VENTANA, min((i + 1) * VENTANA, fin)
        if t1 - t0 < 30:  # el último trozo, si es corto, no cuenta
            continue
        en = [(a, b) for a, b in ws if t0 <= a < t1]
        if len(en) < 20:
            continue
        ppm = len(en) / (t1 - t0) * 60  # con las pausas incluidas, como lo oye el espectador
        hueco = max([n[0] - p[1] for p, n in zip(en, en[1:])] or [0])
        if ppm > PPM_MAX:
            fallas.append({'s': t0, 'que': f'voz a {ppm:.0f} palabras/min en {mmss(t0)}-{mmss(t1)} (máx. {PPM_MAX:.0f}): suena apurada'})
        if hueco < PAUSA_MIN:
            fallas.append({'s': t0, 'que': f'sin ninguna pausa de {PAUSA_MIN} s entre {mmss(t0)} y {mmss(t1)}: falta un respiro'})
    return fallas


def revisar_montos(ocr, cuadros, banda):
    """Nunca precios ni saldos en pantalla ($50, $ 4535, 40 USD). No se difumina: se cambia la toma o se recorta."""
    fallas, ultimo = [], -99
    for t, fr in cuadros:
        for _, txt in texto_cuadro(ocr, fr, banda):
            if MONTO.search(txt) and t - ultimo > 3:
                fallas.append({'s': t, 'que': f'monto a la vista: «{txt.strip()[:30]}» (cambiar la toma o recortar; nunca difuminar)'})
                ultimo = t
    return fallas


def revisar_voz_cartel(ocr, video, ev, banda):
    """«Así empieza / bloqueado» no puede caer sobre el cartel DESPUÉS, ni «así termina / libre» sobre ANTES."""
    fallas, c = [], cv2.VideoCapture(video)
    for a0, _, t, _ in ev:
        w = normal(t).strip('.,¿?¡!:;…')
        for dichas, prohibido in VOZ_CARTEL:
            if w in dichas:
                c.set(cv2.CAP_PROP_POS_MSEC, (a0 + 0.2) * 1000)
                ok, fr = c.read()
                if ok and any(prohibido == normal(x).strip() for _, x in texto_cuadro(ocr, fr, banda)):
                    fallas.append({'s': round(a0, 2), 'que': f'la voz dice «{t}» y en pantalla está el cartel {prohibido.upper()}'})
    return fallas


def revisar_chasquidos(video):
    """Clics o chasquidos sueltos en el sonido (un pico de ~5 ms muy por encima de lo que lo rodea). Solo aviso."""
    try:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                             capture_output=True).stdout
    except Exception:
        return []
    x = np.frombuffer(raw, np.int16).astype(np.float32)
    if len(x) < 16000:
        return []
    d = np.abs(np.diff(x)); n = 80
    pico = d[:len(d) // n * n].reshape(-1, n).max(1)
    base = np.convolve(pico, np.ones(41) / 41, mode='same') + 50
    out, ult = [], -9
    for i in np.where(pico > base * 8)[0]:
        t = i * n / 16000
        if t - ult > 2:
            out.append({'s': round(t, 2), 'que': 'posible chasquido en el sonido', 'aviso': True}); ult = t
    return out[:10]


def revisar(video, ass=None, es_short=None, arreglar=False, privados=False, palabras_json=None, srt=None, bloques=None, noticia=False):
    c = cv2.VideoCapture(video)
    alto = int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
    es_short = (alto > c.get(cv2.CAP_PROP_FRAME_WIDTH)) if es_short is None else es_short
    c.release()
    puntos = {}
    ev, banda = [], None
    if ass and os.path.exists(ass):
        ev, margen, wrap2 = leer_ass(ass)
        puntos['subtitulos'] = revisar_subs(ev, margen, wrap2, alto, es_short)
        y = alto - margen
        banda = (max(0, y - 230), min(alto, y + 40))  # la franja de los subtítulos no cuenta para el OCR
    else:
        puntos['subtitulos'] = []
    cuadros, dur = muestras(video, 0.5, hasta=None if (es_short or privados) else INICIO + 1)
    puntos['planos'] = revisar_planos(cuadros)
    puntos['duracion'] = ([{'s': round(dur, 1), 'que': f'dura {dur:.0f} s: un Short va de {DUR_SHORT[0]:.0f} s a {DUR_SHORT[1]:.0f} s'}]
                          if es_short and not DUR_SHORT[0] <= dur <= DUR_SHORT[1] else [])
    if ev:
        puntos['logos'] = revisar_logos(video, ev)
    ocr = _ocr() if (ev or privados) else None
    if ev:
        puntos['voz_pantalla'] = (revisar_voz_pantalla(ocr, video, ev, banda) if ocr
                                  else [{'s': 0, 'que': 'sin OCR local (rapidocr): no se pudo revisar'}])
    if privados and ocr:  # apagado por defecto: fabian no quiere difuminados en los Shorts (02/11/2026)
        hallados = buscar_privados(ocr, cuadros[::2], banda)
        if hallados and arreglar:
            difuminar(video, hallados)
            for x in hallados:
                x['que'] += ' → difuminado'
            puntos['privados_arreglados'] = hallados
        else:
            puntos['privados'] = [dict(x, aviso=True) for x in hallados]
    # ---- video largo (no Shorts): sincronía, reglas de minutos, ritmo, montos, carteles, chasquidos ----
    puntos['imagen_sonido'] = revisar_av(video)
    if bloques:
        puntos['bloques'] = revisar_bloques(json.load(open(bloques, encoding='utf-8')) if isinstance(bloques, str) else bloques)
    evl = (ev_de_palabras(json.load(open(palabras_json, encoding='utf-8'))) if palabras_json and os.path.exists(palabras_json)
           else ev or (ev_de_srt(srt) if srt and os.path.exists(srt) else []))
    if not es_short and evl:
        if not noticia:
            puntos['reglas_minuto'] = revisar_reglas_minuto(evl, dur)
            puntos['primer_paso'] = revisar_primer_paso(evl, dur)
        puntos['ritmo'] = [dict(x, aviso=True) for x in revisar_ritmo(evl)] if (palabras_json or ev) else []
    if not es_short:
        ocr = ocr or _ocr()
        if ocr:
            todos, _ = muestras(video, 2.0)
            puntos['montos'] = revisar_montos(ocr, todos, banda)
            if evl:
                puntos['voz_cartel'] = revisar_voz_cartel(ocr, video, evl, banda)
    puntos['chasquidos'] = revisar_chasquidos(video)
    puntos['voz_imagen_ia'] = 'omitido (no hay IA local con visión; no gasta)'
    ok = not any([x for x in v if not x.get('aviso')] for k, v in puntos.items() if isinstance(v, list) and k not in ('privados_arreglados', 'privados'))
    informe = {'video': os.path.basename(video), 'ok': ok, 'puntos': puntos}
    base = os.path.splitext(video)[0]
    json.dump(informe, open(base + '.revision.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    nombres = {'subtitulos': 'Subtítulos', 'planos': 'Planos largos al inicio', 'voz_pantalla': 'Lo que dice la voz se ve',
               'duracion': 'Duración', 'logos': 'Logos de lo que nombra la voz',
               'privados': 'Datos privados', 'privados_arreglados': 'Datos privados difuminados por el revisor',
               'imagen_sonido': 'Imagen y sonido duran lo mismo (sin desfase)', 'bloques': 'Cada tramo dura lo que dice la voz',
               'reglas_minuto': 'WhatsApp y comentar antes de 2:00; páginas entre 1:00 y 2:00', 'primer_paso': 'Primer paso antes del 1:30', 'ritmo': 'Ritmo de la voz (aviso)',
               'montos': 'Sin precios ni saldos en pantalla', 'voz_cartel': 'ANTES/DESPUÉS coinciden con la voz', 'chasquidos': 'Chasquidos (aviso)'}
    md = [f"# Revisión automática de {informe['video']}: {'✅ todo bien' if ok else '❌ hay que corregir'}", '']
    for k, v in puntos.items():
        if isinstance(v, str):
            md.append(f'- ⚪ Voz vs imagen (IA): {v}')
            continue
        marca = 'ℹ️' if (k in ('privados_arreglados', 'privados') or all(x.get('aviso') for x in v)) and v else ('✅' if not v else '❌')
        md.append(f'- {marca} {nombres.get(k, k)}' + ('' if v else ''))
        md += [f"  - {x['s']:.1f} s: {x['que']}" for x in v]
    open(base + '.revision.md', 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    print('\n'.join(md), flush=True)
    return informe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--ass')
    ap.add_argument('--short', action='store_true')
    ap.add_argument('--arreglar', action='store_true')
    ap.add_argument('--privados', action='store_true', help='buscar datos privados (apagado: fabian no quiere difuminados)')
    ap.add_argument('--palabras', help='JSON [[palabra, ini, fin]] con los tiempos de la voz en el video')
    ap.add_argument('--srt', help='subtítulos .srt (si no hay .ass ni --palabras)')
    ap.add_argument('--bloques', help='JSON {bloque: {D, f}} para comprobar que cada tramo dura lo que dice la voz')
    ap.add_argument('--noticia', action='store_true', help='video de noticias: sin reglas de WhatsApp/páginas')
    a = ap.parse_args()
    srt = a.srt or (os.path.splitext(a.video)[0] + '.srt' if os.path.exists(os.path.splitext(a.video)[0] + '.srt') else None)
    inf = revisar(a.video, a.ass, True if a.short else None, a.arreglar, a.privados, a.palabras, srt, a.bloques, a.noticia)
    sys.exit(0 if inf['ok'] else 1)


if __name__ == '__main__':
    main()
