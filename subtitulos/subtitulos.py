"""«💬 Subtítulos»: subtítulos bonitos y dinámicos (palabra por palabra) en el idioma que elijas, grabados en el video
o como .srt para subir a YouTube.

Vive en mis_proyectos/NOMBRE/subtitulos.json:
    {"idioma": "en",
     "estilo": {"dinamico": true, "pos": "abajo", "altura": 8, "tam": 6, "color": "#FFFFFF", "resalte": "#FFD23F",
                "fondo": true, "fuente": "Arial Black", "palabras": 6},
     "textos": {"en": {"L01": "Is your Motorola locked…", …}}}
Los tiempos salen del guion: cada bloque empieza 0,3 s después de su inicio en el video armado y dura lo que dura su voz.
En español se usa el texto del guion tal cual; en otro idioma, la traducción (la hace la IA de Ajustes y la puedes corregir).
Dentro de cada bloque el texto se parte en frases cortas y cada palabra se resalta cuando toca (repartido por su largo).
"""
import json, os, re, subprocess, sys, threading, time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
ARCHIVO = 'subtitulos.json'
DESFASE = 0.3
# por defecto, el estilo que eligió fabian (31/10/2026, «C +50 %» de la muestra del HONOR 8 LITE): una línea corta de 2-3
# palabras, Arial Black blanca con borde negro, la palabra que se dice en amarillo y algo más grande, bien abajo al centro
ESTILO = {'dinamico': True, 'pos': 'abajo', 'altura': 10, 'tam': 10, 'color': '#FFFFFF', 'resalte': '#FFD23F', 'fondo': False,
          'fuente': 'Arial Black', 'palabras': 3, 'letras': 14}
ESTADO = {'activo': False}


def leer(d):
    try:
        x = json.load(open(os.path.join(d, ARCHIVO), encoding='utf-8'))
    except (OSError, ValueError):
        x = {}
    x.setdefault('idioma', 'en')
    x['estilo'] = {**ESTILO, **(x.get('estilo') or {})}
    x.setdefault('textos', {})
    return x


def guardar(d, datos):
    tmp = os.path.join(d, ARCHIVO + '.tmp')
    json.dump(datos, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(d, ARCHIVO))


def bloques(d):
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    return [b for b in g['bloques'] if str(b.get('texto') or '').strip() and b.get('inicio_min') is not None]


def textos(d, lang, datos=None):
    """{id: texto} en ese idioma (en español, el del guion)."""
    datos = datos or leer(d)
    tabla = datos['textos'].get(lang) or {}
    return {b['id']: (b['texto'] if lang == 'es' else tabla.get(b['id'], '')) for b in bloques(d)}


def traducir(d, lang, ajustes_f):
    """La IA de Ajustes traduce los bloques que todavía no tienen traducción. Devuelve cuántos tradujo."""
    datos = leer(d)
    tabla = datos['textos'].setdefault(lang, {})
    faltan = {b['id']: b['texto'] for b in bloques(d) if not tabla.get(b['id'])}
    if not faltan:
        return 0
    sys.path.insert(0, os.path.join(RAIZ, 'ia'))
    sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
    import ia, idiomas
    nombre = idiomas.NOMBRES.get(lang, lang)
    prompt = (f'Traduce al {nombre} (código {lang}) estos subtítulos de un video tutorial de reparación de celulares (la voz '
              'sigue en español; esto es lo que lee el espectador). Natural, claro y corto; nombres de botones, programas, '
              'modelos y webs tal cual. Responde SOLO con un objeto JSON {"L01": "traducción", …} con exactamente estas claves:\n'
              + json.dumps(faltan, ensure_ascii=False, indent=1))
    r = ia.extraer_json(ia.llamar(dict(json.load(open(ajustes_f, encoding='utf-8')), imagenes=False), prompt, []))
    n = 0
    for k, v in (r.items() if isinstance(r, dict) else []):
        if k in faltan and str(v or '').strip():
            tabla[k] = str(v).strip()
            n += 1
    guardar(d, datos)
    return n


def frases(texto, maximo, letras=0):
    """Parte el texto en frases cortas (cortando en la puntuación, cada `maximo` palabras o, con letra grande, al pasar
    de `letras` caracteres, para que la línea no se salga de la pantalla)."""
    palabras, out, act = texto.split(), [], []
    for w in palabras:
        act.append(w)
        if len(act) >= maximo or (letras and len(' '.join(act)) >= letras)                 or (re.search(r'[.!?…:;,]$', w) and len(act) >= max(2, maximo // 2)):
            out.append(act); act = []
    if act:
        out.append(act)
    return out


ORACION = re.compile(r'(?<=[.?!…])\s+')


def _alineacion(d, bid):
    """(texto, inicio de cada letra, fin de cada letra) de la voz del bloque (voz/<id>.align.json), o None."""
    try:
        al = json.load(open(os.path.join(d, 'voz', f'{bid}.align.json'), encoding='utf-8'))
        return ''.join(al['characters']), al['character_start_times_seconds'], al.get('character_end_times_seconds') or al['character_start_times_seconds']
    except (OSError, ValueError, KeyError):
        return None


def _oraciones(t):
    """[(inicio en el texto, oración)]."""
    out, pos = [], 0
    for o in ORACION.split(t.strip()):
        if o.strip():
            i = t.find(o, pos)
            out.append((i, o))
            pos = i + len(o)
    return out


def _tramos_de_voz(t, al, ini):
    """[(desde, hasta, oración)] de un texto traducido, con los tiempos de la voz (en español) que dice cada oración:
    si las dos tienen las mismas oraciones, cada una entra justo cuando la voz empieza la suya (nunca antes); si no,
    la posición en el texto traducido se lleva a la misma proporción del texto hablado y de ahí a su segundo."""
    habla, ts, te = al
    if not habla.strip():
        return None
    o_es, o_tr = _oraciones(habla), _oraciones(t)
    fin_voz = ini + te[-1]
    if len(o_es) == len(o_tr):
        empiezan = [ini + ts[min(i, len(ts) - 1)] for i, _ in o_es]
    else:
        empiezan = [ini + ts[min(len(ts) - 1, int(i / max(1, len(t)) * len(habla)))] for i, _ in o_tr]
    return [(a, (empiezan[k + 1] if k + 1 < len(empiezan) else fin_voz), o) for k, (a, (_, o)) in enumerate(zip(empiezan, o_tr))]


def eventos(d, lang, estilo, offset=0.0):
    """[(inicio, fin, [(palabra, inicio, fin)…])] de todo el video. En un idioma traducido, cada oración usa los tiempos
    de la voz que la dice (voz/<id>.align.json), así el subtítulo no se adelanta (fabian, 31/10/2026); sin alineación,
    el tiempo del bloque se reparte por letras, como antes."""
    out, tx = [], textos(d, lang)
    maximo, letras = int(estilo.get('palabras') or 6), int(estilo.get('letras') or 0)
    for b in bloques(d):
        t = tx.get(b['id'], '').strip()
        if not t:
            continue
        ini = b['inicio_min'] + DESFASE + offset
        dur = float(b.get('voz_real_s') or (b['fin_max'] - b['inicio_min'] - DESFASE))
        al = _alineacion(d, b['id']) if lang != 'es' else None
        tramos = (_tramos_de_voz(t, al, ini) if al else None) or [(ini, ini + dur, t)]
        for desde, hasta, texto in tramos:
            partes = frases(texto, maximo, letras)
            total = sum(len(''.join(p)) + len(p) for p in partes) or 1
            cur = desde
            for p in partes:
                largo = (hasta - desde) * (len(''.join(p)) + len(p)) / total
                ws, c = [], cur
                for w in p:
                    dw = largo * (len(w) + 1) / (len(''.join(p)) + len(p))
                    ws.append((w, c, c + dw)); c += dw
                out.append((cur, cur + largo, ws))
                cur += largo
    return out


def _color(hexa, alfa='00'):
    h = hexa.lstrip('#')
    return f'&H{alfa}{h[4:6]}{h[2:4]}{h[0:2]}'.upper()


def _t(s):
    s = max(0.0, s)
    return f'{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}'


def ass(d, lang, estilo, W=1920, H=1080, offset=0.0):
    e = {**ESTILO, **(estilo or {})}
    tam = round(H * float(e['tam']) / 100)
    alin = {'abajo': 2, 'medio': 5, 'arriba': 8}.get(e['pos'], 2)
    margen = round(H * float(e['altura']) / 100) if alin != 5 else 0
    borde = (3, 0) if e['fondo'] else (1, 4)  # BorderStyle 3 = caja de fondo; si no, contorno grueso
    cab = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
           "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
           f"Style: S,{e['fuente']},{tam},{_color(e['color'])},{_color(e['resalte'])},&H00000000,&H64000000,{0 if 'black' in e['fuente'].lower() else -1},0,0,0,100,100,1,0,"
           f"{borde[0]},{max(2, tam // 14) if not e['fondo'] else tam // 6},{borde[1] and 2},{alin},{W // 10},{W // 10},{margen},1\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lineas = []
    for ini, fin, ws in eventos(d, lang, e, offset):
        if e['dinamico']:  # la palabra que se dice va en el color de resalte y un poco más grande
            for k, (w, a, b) in enumerate(ws):
                txt = ' '.join((r'{\c' + _color(e['resalte']) + r'&\fscx112\fscy112}' + x + r'{\r}') if j == k else x
                               for j, (x, _, _) in enumerate(ws))
                lineas.append(f"Dialogue: 0,{_t(a)},{_t(b if k < len(ws) - 1 else fin)},S,,0,0,0,,{txt}")
        else:
            lineas.append(f"Dialogue: 0,{_t(ini)},{_t(fin)},S,,0,0,0,,{' '.join(w for w, _, _ in ws)}")
    return cab + '\n'.join(lineas) + '\n'


def srt(d, lang, offset=0.0):
    e = leer(d)['estilo']
    def ts(s):
        return f'{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d},{int(round(s % 1 * 1000)) % 1000:03d}'
    return '\n'.join(f'{k}\n{ts(a)} --> {ts(b)}\n{" ".join(w for w, _, _ in ws)}\n'
                     for k, (a, b, ws) in enumerate(eventos(d, lang, e, offset), 1))


def tamano(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', f],
                       capture_output=True, text=True)
    try:
        w, h = r.stdout.strip().split(',')[:2]
        return int(w), int(h)
    except ValueError:
        return 1920, 1080


def duracion(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def offset_de(d, fuente):
    """Si el video empieza con el tráiler (FINAL.mp4 con tráiler al inicio), los subtítulos se corren lo que dura."""
    if os.path.basename(fuente).startswith('FINAL') and os.path.exists(os.path.join(d, 'trailer.mp4')):
        try:
            if json.load(open(os.path.join(d, 'edicion.json'), encoding='utf-8')).get('trailer_donde', 'inicio') != 'inicio':
                return 0.0
        except (OSError, ValueError, AttributeError):
            pass
        return duracion(os.path.join(d, 'trailer.mp4'))
    return 0.0


def _filtro(f_ass):
    return "ass='" + f_ass.replace('\\', '/').replace(':', '\\:') + "'"


def vista_previa(d, fuente, t, salida):
    datos = leer(d)
    W, H = tamano(fuente)
    f_ass = os.path.join(d, '.subs_vista.ass')
    open(f_ass, 'w', encoding='utf-8').write(ass(d, datos['idioma'], datos['estilo'], W, H, offset_de(d, fuente)))
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-copyts', '-i', fuente, '-frames:v', '1',
                    '-vf', _filtro(f_ass) + ',scale=960:-2', '-q:v', '3', salida], check=True, cwd=d)
    return salida


FUENTES = ['FINAL.mp4', '7_tarjetas.mp4', '6_senales.mp4', '5_etiquetas.mp4', '4_musica.mp4', '3_voz.mp4']


def fuentes(d):
    """Los videos del proyecto donde se pueden grabar (el más terminado primero)."""
    return [f for f in FUENTES if os.path.exists(os.path.join(d, f))]


def grabar(d, fuente):
    """Graba los subtítulos en una copia del video (en segundo plano; avance en ESTADO)."""
    if ESTADO.get('activo'):
        raise ValueError('Ya estoy grabando subtítulos: espera a que termine.')
    datos = leer(d)
    lang = datos['idioma']
    if not any(textos(d, lang, datos).values()):
        raise ValueError('Todavía no hay subtítulos en ese idioma: tradúcelos primero.')
    W, H = tamano(fuente)
    f_ass = os.path.join(d, f'subtitulos_{lang}.ass')
    open(f_ass, 'w', encoding='utf-8').write(ass(d, lang, datos['estilo'], W, H, offset_de(d, fuente)))
    salida = os.path.join(d, os.path.splitext(os.path.basename(fuente))[0] + f'_subs_{lang}.mp4')
    total = duracion(fuente) or 1
    ESTADO.clear()
    ESTADO.update(activo=True, pct=0.0, salida=salida, error=None, inicio=time.time())

    def trabajo():
        try:
            cmd = ['ffmpeg', '-nostdin', '-hide_banner', '-y', '-i', fuente, '-vf', _filtro(f_ass), '-c:v', 'libx264', '-preset', 'medium',
                   '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', salida]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            err = []
            threading.Thread(target=lambda: err.extend(p.stderr.read().splitlines()[-6:]), daemon=True).start()
            for linea in p.stdout:
                m = re.match(r'out_time_(?:us|ms)=(\d+)', linea.strip())
                if m:
                    ESTADO['pct'] = round(min(99.0, int(m.group(1)) / 1e6 * 100 / total), 1)
            p.wait()
            if p.returncode != 0:
                raise RuntimeError(' '.join(err)[-400:] or 'ffmpeg falló')
            ESTADO.update(pct=100.0, segundos=round(time.time() - ESTADO['inicio']), tam=os.path.getsize(salida))
        except Exception as e:
            ESTADO['error'] = str(e)
        finally:
            ESTADO['activo'] = False
    threading.Thread(target=trabajo, daemon=True).start()
    return salida


if __name__ == '__main__':  # python subtitulos.py traducir --proyecto DIR --idioma en --ajustes app/ajustes.json
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('accion', choices=['traducir'])
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('--idioma', required=True)
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    a = ap.parse_args()
    n = traducir(os.path.abspath(a.proyecto), a.idioma, a.ajustes)
    print(json.dumps({'ok': True, 'traducidos': n}))
