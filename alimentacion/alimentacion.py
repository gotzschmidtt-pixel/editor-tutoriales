"""ALIMENTACIÓN: la app aprende tu estilo de tus propios videos.

Le das links de YouTube o MP4 de tus videos (o de un canal que te guste) y un perfil escrito a mano si
tienes uno. Por cada video: lo baja (YouTube, con yt-dlp), lo transcribe (subtítulos de YouTube si hay;
si no, Scribe o Whisper) y mide sin IA:
  - ritmo: palabras por minuto, largo de las frases, preguntas por minuto
  - estructura: cómo abre (primeros 20 s) y cómo cierra (últimos 40 s)
  - edición: cortes por minuto y si arranca con un tráiler (muchos cortes seguidos al inicio): cuánto
    dura, cuántas tomas y qué se dice en él
  - frases típicas: las que repites en varios videos
Con eso escribe perfil.md. Si tienes una IA configurada en la app, ella redacta el perfil a partir de las
medidas y las transcripciones; si no, sale un perfil con las medidas.

El perfil activo (⚙ en el panel) se suma al encargo de la IA cuando escribe el guion y arma el tráiler.

Todo vive en mis_estilos/<nombre>/: fuentes.json, videos/, analisis/<id>.json, perfil.md, perfil.json.

Uso:
  python alimentacion.py --estilo mis_estilos/mi_canal [--ajustes app/ajustes.json] [--sin-ia]
"""
import argparse, collections, json, os, re, subprocess, sys, unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'transcripcion'))
VIDEOS = ('.mp4', '.mov', '.mkv', '.webm', '.m4v')
TEXTOS = ('.md', '.txt')
VACIAS = set('''a al algo como con de del el ella ellos en es esa ese eso esta este esto hay la las le les lo los me mi muy
nada no nos o para pero por que se si sin su sus te tu un una uno y ya yo''' .split())


def ff_dur(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                       capture_output=True, text=True)
    try:
        return float(r.stdout)
    except ValueError:
        return 0.0


def normal(c):
    return ''.join(x for x in unicodedata.normalize('NFD', c.lower()) if unicodedata.category(x) != 'Mn')


def leer_fuentes(e):
    try:
        return json.load(open(os.path.join(e, 'fuentes.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []


def id_youtube(url):
    m = re.search(r'(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})', url)
    return m.group(1) if m else re.sub(r'\W', '', url)[-11:]


# ---------- conseguir el video y su texto ----------

def yt_dlp():
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print('Instalando yt-dlp para bajar videos de YouTube (una sola vez)…', flush=True)
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instalador'))
        import guardado
        guardado.instalar(['yt-dlp'], mostrar=lambda x: print(x, flush=True))
    return [sys.executable, '-m', 'yt_dlp']


def bajar(e, f):
    """Baja el video a 360p y los subtítulos en español. Devuelve (video, vtt o None, título)."""
    vid = id_youtube(f['url'])
    carpeta = os.path.join(e, 'videos')
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, vid + '.mp4')
    vtts = [x for x in os.listdir(carpeta) if x.startswith(vid + '.') and x.endswith('.vtt')]
    if not os.path.exists(destino):
        print(f'Bajando {f["url"]}…', flush=True)
        base = yt_dlp() + ['--no-playlist', '-f', 'bv*[height<=360]+ba/b[height<=360]/b', '--merge-output-format', 'mp4',
                           '--print', 'after_move:title', '-o', os.path.join(carpeta, vid + '.%(ext)s')]
        subs = ['--write-subs', '--write-auto-subs', '--sub-langs', 'es.*,es', '--sub-format', 'vtt']
        r = subprocess.run(base + subs + [f['url']], capture_output=True, text=True)
        if not os.path.exists(destino):  # a veces fallan solo los subtítulos: sin ellos, se transcribe el audio
            r = subprocess.run(base + [f['url']], capture_output=True, text=True)
        if not os.path.exists(destino):
            raise RuntimeError(f'no pude bajar {f["url"]}: {(r.stderr or r.stdout).strip()[-300:]}. Si YouTube lo bloquea, '
                               'bájalo tú y súbelo como MP4.')
        f['titulo'] = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else f.get('titulo')
        vtts = [x for x in os.listdir(carpeta) if x.startswith(vid + '.') and x.endswith('.vtt')]
    vtts.sort(key=lambda x: ('orig' not in x, len(x)))  # los subtítulos manuales antes que los automáticos
    return destino, (os.path.join(carpeta, vtts[0]) if vtts else None), f.get('titulo') or vid


def leer_vtt(f):
    """[(inicio, texto)] sin las repeticiones típicas de los subtítulos automáticos de YouTube."""
    out, visto = [], ''
    for bloque in re.split(r'\n\s*\n', open(f, encoding='utf-8', errors='replace').read()):
        m = re.search(r'(\d+):(\d\d):(\d\d)\.(\d+)\s*-->', bloque) or re.search(r'(\d\d):(\d\d)\.(\d+)\s*-->', bloque)
        if not m:
            continue
        g = m.groups()
        t = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) if len(g) == 4 else int(g[0]) * 60 + int(g[1])
        txt = re.sub(r'<[^>]+>', '', ' '.join(bloque[m.end():].split('\n')[1:])).strip()
        if txt and txt != visto and not visto.endswith(txt):
            nuevo = txt[len(visto):].strip() if txt.startswith(visto) else txt
            if nuevo:
                out.append((t, nuevo))
            visto = txt
    return out


def transcribir(video):
    import transcribir as tr
    mp3 = tr.audio(video)
    try:
        pal = tr.scribe(mp3, 'es') if tr.CLAVE else tr.whisper(mp3, 'es', 'small')
    except SystemExit as err:
        raise RuntimeError(f'no pude transcribir: {err}')
    return [(i, t) for i, _, t in tr.frases(pal)]


def cortes(video):
    """Segundos donde hay un cambio de plano (ffmpeg, escena > 0,3)."""
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', video, '-an', '-vf', "scale=320:-2,select='gt(scene,0.3)',showinfo",
                        '-f', 'null', '-'], capture_output=True, text=True)
    return [float(x) for x in re.findall(r'pts_time:([\d.]+)', r.stderr)]


# ---------- medir ----------

def trailer_inicial(cs, dur):
    """Si el video arranca con muchos cortes seguidos, eso es un tráiler: (fin, tomas) o None."""
    if not cs or dur < 60:
        return None
    ritmo = len(cs) / dur
    inicio = [c for c in cs if c < 60]
    fin = 0.0
    for c in inicio:  # el tráiler termina en el primer hueco largo sin cortes
        if c - fin > 6:
            break
        fin = c
    tomas = len([c for c in inicio if c <= fin])
    if tomas >= 4 and fin >= 4 and tomas / fin >= 2 * ritmo:
        return round(fin, 1), tomas + 1
    return None


def analizar(e, f, k):
    """Analiza una fuente (video). Guarda analisis/<id>.json y lo devuelve."""
    clave = id_youtube(f['url']) if f['tipo'] == 'youtube' else os.path.splitext(f['archivo'])[0]
    salida = os.path.join(e, 'analisis', clave + '.json')
    if os.path.exists(salida):
        return json.load(open(salida, encoding='utf-8'))
    if f['tipo'] == 'youtube':
        video, vtt, titulo = bajar(e, f)
        lineas = leer_vtt(vtt) if vtt else []
    else:
        video, titulo, lineas = os.path.join(e, 'videos', f['archivo']), f.get('titulo') or f['archivo'], []
    print(f'[{k}] {titulo}', flush=True)
    if not lineas:
        lineas = transcribir(video)
    dur = ff_dur(video) or (lineas[-1][0] + 5 if lineas else 0)
    texto = ' '.join(t for _, t in lineas)
    palabras = texto.split()
    frases = [x.strip() for x in re.split(r'(?<=[.?!¿¡])\s+', texto) if len(x.split()) >= 2]
    cs = cortes(video)
    tr = trailer_inicial(cs, dur)
    a = {
        'titulo': titulo, 'fuente': f.get('url') or f['archivo'], 'duracion_s': round(dur, 1),
        'palabras_por_min': round(len(palabras) / dur * 60, 1) if dur else 0,
        'palabras_por_frase': round(len(palabras) / max(1, len(frases)), 1) if re.search(r'[.?!]', texto) else None,
        'preguntas_por_min': round(texto.count('?') / dur * 60, 2) if dur and '?' in texto else None,
        'cortes_por_min': round(len(cs) / dur * 60, 1) if dur else 0,
        'apertura': ' '.join(t for s, t in lineas if s < 20),
        'cierre': ' '.join(t for s, t in lineas if s > dur - 40),
        'trailer': {'dura_s': tr[0], 'tomas': tr[1], 'toma_media_s': round(tr[0] / tr[1], 2),
                    'dice': ' '.join(t for s, t in lineas if s <= tr[0])} if tr else None,
        'texto': texto,
    }
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    json.dump(a, open(salida, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return a


def frases_tipicas(textos, top=25):
    """Grupos de 3 a 5 palabras que se repiten (en varios videos, o muchas veces en uno)."""
    por_video, total = collections.Counter(), collections.Counter()
    for txt in textos:
        w = re.findall(r'[a-záéíóúñü0-9]+', txt.lower())
        vistos = set()
        for n in (3, 4, 5):
            for i in range(len(w) - n + 1):
                g = tuple(w[i:i + n])
                if sum(x not in VACIAS for x in g) < 2:
                    continue
                total[g] += 1
                vistos.add(g)
        por_video.update(vistos)
    varios = len(textos) > 1
    buenas = [(g, c) for g, c in total.items() if (por_video[g] >= 2 if varios else c >= 3)]
    buenas.sort(key=lambda x: (-por_video[x[0]], -x[1], -len(x[0])))
    out = []
    for g, c in buenas:
        txt = ' '.join(g)
        if not any(txt in o for o, _ in out):  # sin repetir trozos de una frase más larga
            out.append((txt, c))
        if len(out) == top:
            break
    return out


def promedio(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def resumen(analisis, escritos):
    trs = [a['trailer'] for a in analisis if a['trailer']]
    return {
        'videos': len(analisis), 'minutos': round(sum(a['duracion_s'] for a in analisis) / 60, 1),
        'palabras_por_min': promedio([a['palabras_por_min'] for a in analisis]),
        'palabras_por_frase': promedio([a['palabras_por_frase'] for a in analisis]),
        'preguntas_por_min': promedio([a['preguntas_por_min'] for a in analisis]),
        'cortes_por_min': promedio([a['cortes_por_min'] for a in analisis]),
        'trailer': {'en_videos': len(trs), 'dura_s': promedio([t['dura_s'] for t in trs]),
                    'tomas': promedio([t['tomas'] for t in trs]), 'toma_media_s': promedio([t['toma_media_s'] for t in trs]),
                    'ejemplos': [t['dice'][:300] for t in trs[:3]]} if trs else None,
        'aperturas': [a['apertura'][:400] for a in analisis if a['apertura']][:5],
        'cierres': [a['cierre'][-400:] for a in analisis if a['cierre']][:5],
        'frases_tipicas': [f'{t} (×{c})' for t, c in frases_tipicas([a['texto'] for a in analisis])],
        'perfiles_escritos': len(escritos),
    }


def perfil_medidas(nombre, r, escritos):
    """El perfil sin IA: las medidas en limpio."""
    l = [f'# Perfil de estilo: {nombre}', '', f"Sale de {r['videos']} videos ({r['minutos']} min) medidos por la app."]
    l += ['', '## Ritmo', f"- {r['palabras_por_min']} palabras por minuto."]
    if r['palabras_por_frase']:
        l.append(f"- Frases de {r['palabras_por_frase']} palabras en promedio.")
    if r['preguntas_por_min']:
        l.append(f"- {r['preguntas_por_min']} preguntas por minuto.")
    l.append(f"- {r['cortes_por_min']} cortes de plano por minuto.")
    if r['trailer']:
        t = r['trailer']
        l += ['', '## Tráiler inicial', f"- Aparece en {t['en_videos']} de {r['videos']} videos: dura {t['dura_s']} s, "
              f"con unas {t['tomas']:.0f} tomas de {t['toma_media_s']} s."]
        l += [f'- Lo que se dice: «{x}»' for x in t['ejemplos']]
    if r['aperturas']:
        l += ['', '## Cómo abre (primeros 20 s)'] + [f'- «{x}»' for x in r['aperturas']]
    if r['cierres']:
        l += ['', '## Cómo cierra (últimos 40 s)'] + [f'- «{x}»' for x in r['cierres']]
    if r['frases_tipicas']:
        l += ['', '## Frases que repite'] + [f'- {x}' for x in r['frases_tipicas']]
    for nom, txt in escritos:
        l += ['', f'## Perfil escrito a mano ({nom})', txt.strip()]
    return '\n'.join(l) + '\n'


def perfil_ia(nombre, r, analisis, escritos, ajustes):
    sys.path.insert(0, os.path.join(RAIZ, 'ia'))
    import ia
    muestras = '\n\n'.join(f"### {a['titulo']} ({a['duracion_s'] / 60:.0f} min)\n{a['texto'][:6000]}" for a in analisis[:6])
    extra = '\n\n'.join(f'### Perfil escrito a mano: {n}\n{t[:8000]}' for n, t in escritos)
    pedido = f"""Eres editor de un canal de YouTube. Analiza el estilo de estos videos para que otro guionista y otro editor lo imiten.

Medidas hechas por la app (confiables):
{json.dumps({k: v for k, v in r.items() if k != 'ejemplos'}, ensure_ascii=False, indent=1)}

Transcripciones (recortadas):
{muestras}

{extra}

Escribe un perfil de estilo práctico en español, en Markdown, con estas secciones:
## La idea central (tono, cómo le habla al espectador, humor o no)
## Apertura (qué pasa en los primeros 15 s, con un ejemplo)
## Ritmo de frases (largo, remates, figuras que repite, con ejemplos)
## Preguntas y llamados (a comentar, a escribir, a suscribirse: cuándo y cómo)
## Transiciones entre partes
## Muletillas y frases típicas (cópialas tal cual de las transcripciones)
## Cierre
## Tráiler o gancho inicial (duración, cuántas tomas, qué muestra y qué dice; si no hay, dilo)
## Guía rápida para el guionista (8 a 12 reglas cortas)
## Qué no copiar
No inventes datos que no estén en las transcripciones o las medidas.
Responde SOLO con un objeto JSON {{"perfil": "el markdown completo"}}."""
    resp = ia.llamar(ajustes, pedido, [])
    return f'# Perfil de estilo: {nombre}\n\n' + ia.extraer_json(resp)['perfil'].strip() + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--estilo', required=True)
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    ap.add_argument('--sin-ia', action='store_true')
    a = ap.parse_args()
    e = a.estilo
    nombre = os.path.basename(os.path.normpath(e))
    fuentes = leer_fuentes(e)
    if not fuentes:
        raise SystemExit('ERROR: este estilo no tiene videos. Agrega links de YouTube o sube MP4 en el panel Alimentación.')
    analisis, escritos, fallos = [], [], []
    for k, f in enumerate(fuentes, 1):
        if f['tipo'] == 'texto':
            escritos.append((f['archivo'], open(os.path.join(e, 'videos', f['archivo']), encoding='utf-8', errors='replace').read()))
            continue
        try:
            analisis.append(analizar(e, f, k))
        except (RuntimeError, OSError, subprocess.CalledProcessError) as err:
            fallos.append(f"{f.get('url') or f.get('archivo')}: {err}")
            print(f'· lo salto: {err}', flush=True)
    json.dump(fuentes, open(os.path.join(e, 'fuentes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)  # con títulos
    if not analisis and not escritos:
        raise SystemExit('ERROR: no pude analizar ningún video.\n' + '\n'.join(fallos))
    r = resumen(analisis, escritos) if analisis else {'videos': 0, 'minutos': 0}
    json.dump(r, open(os.path.join(e, 'perfil.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    texto = None
    if not a.sin_ia:
        try:
            aj = json.load(open(a.ajustes, encoding='utf-8'))
        except (OSError, ValueError):
            aj = {}
        if aj.get('url') or aj.get('tipo') == 'claude':
            print(f"Pidiendo a {aj.get('modelo')} que redacte el perfil…", flush=True)
            try:
                texto = perfil_ia(nombre, r, analisis, escritos, aj)
            except (SystemExit, KeyError, ValueError) as err:
                print(f'· la IA no pudo redactarlo ({err}); queda el perfil con las medidas', flush=True)
    if texto is None:
        texto = perfil_medidas(nombre, r, escritos) if analisis else '\n\n'.join(t for _, t in escritos)
    open(os.path.join(e, 'perfil.md'), 'w', encoding='utf-8').write(texto)
    print(f"Perfil listo: {len(analisis)} videos analizados" + (f', {len(fallos)} con problemas' if fallos else '') +
          f" -> {os.path.join(e, 'perfil.md')}")


if __name__ == '__main__':
    main()
