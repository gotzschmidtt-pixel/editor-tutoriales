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
        lib = [l for l in json.load(open(os.path.join(carpeta, 'logos.json'), encoding='utf-8')).get('logos', [])
               if os.path.isfile(os.path.join(carpeta, l.get('archivo', '')))]
    except Exception:
        return [], carpeta
    texto, tiempos = '', []
    for a0, _a1, _txt, dicha in ev:  # una palabra dicha por subtítulo (estilo C): el texto hablado con su segundo
        if dicha and (not tiempos or tiempos[-1][0] != a0):
            texto += dicha + ' '
            tiempos += [(a0, None)] * (len(dicha) + 1)
    out, visto = [], {}
    for pos, l in sorted(lg.menciones(texto, lib), key=lambda x: x[0]):
        s = tiempos[min(pos, len(tiempos) - 1)][0]
        if s - visto.get(l['archivo'], -999) >= lg.NO_REPETIR:
            visto[l['archivo']] = s
            out.append((s, l))
    return out, carpeta


def revisar_logos(video, ev, alto_rel=0.30):
    """Cada logo que nombra la voz tiene que verse en ese momento (se busca el PNG en el cuadro, en su tamaño de Short)."""
    esperados, carpeta = logos_esperados(ev)
    fallas, c = [], cv2.VideoCapture(video)
    for s, l in esperados:
        png = cv2.imread(os.path.join(carpeta, l['archivo']), cv2.IMREAD_UNCHANGED)
        if png is None:
            continue
        visto = False
        for dt in (0.35, 0.6):
            c.set(cv2.CAP_PROP_POS_MSEC, (s + dt) * 1000)
            ok, fr = c.read()
            if not ok:
                continue
            h = fr.shape[0]
            for esc in (1.0, 0.85, 1.15):
                alto = int(h * alto_rel * esc * (0.52 if png.shape[1] / png.shape[0] > 1.3 else 1))
                ancho = int(alto * png.shape[1] / png.shape[0])
                if ancho >= fr.shape[1] or alto < 20:
                    continue
                chico = cv2.resize(png, (ancho, alto))
                plantilla = chico[:, :, :3]
                mascara = (chico[:, :, 3] > 128).astype(np.uint8) * 255 if png.shape[2] == 4 else None
                mascara = cv2.merge([mascara] * 3) if mascara is not None else None
                r = cv2.matchTemplate(fr[: int(h * 0.7)], plantilla, cv2.TM_CCORR_NORMED, mask=mascara)
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


def revisar(video, ass=None, es_short=None, arreglar=False, privados=False):
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
    puntos['voz_imagen_ia'] = 'omitido (no hay IA local con visión; no gasta)'
    ok = not any(v for k, v in puntos.items() if isinstance(v, list) and k not in ('privados_arreglados', 'privados'))
    informe = {'video': os.path.basename(video), 'ok': ok, 'puntos': puntos}
    base = os.path.splitext(video)[0]
    json.dump(informe, open(base + '.revision.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    nombres = {'subtitulos': 'Subtítulos', 'planos': 'Planos largos al inicio', 'voz_pantalla': 'Lo que dice la voz se ve',
               'duracion': 'Duración', 'logos': 'Logos de lo que nombra la voz',
               'privados': 'Datos privados', 'privados_arreglados': 'Datos privados difuminados por el revisor'}
    md = [f"# Revisión automática de {informe['video']}: {'✅ todo bien' if ok else '❌ hay que corregir'}", '']
    for k, v in puntos.items():
        if isinstance(v, str):
            md.append(f'- ⚪ Voz vs imagen (IA): {v}')
            continue
        marca = 'ℹ️' if k in ('privados_arreglados', 'privados') and v else ('✅' if not v else '❌')
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
    a = ap.parse_args()
    inf = revisar(a.video, a.ass, True if a.short else None, a.arreglar, a.privados)
    sys.exit(0 if inf['ok'] else 1)


if __name__ == '__main__':
    main()
