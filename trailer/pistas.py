"""Pistas del autor para el tráiler ANTES · DURANTE · DESPUÉS.

En la app, cada fase del tráiler recibe pistas: capturas (con o sin segundo), audios (una nota de voz
o un trozo del video) y texto. Son orientativas: aquí se traducen a segundos candidatos del video
original para que la IA elija tomas en esos momentos o en otros parecidos.

  captura con segundo  -> ese segundo
  captura sin segundo  -> los momentos del video que más se le parecen (comparando miniaturas)
  audio                -> se transcribe y se busca lo que dice en la transcripción del video
  texto                -> segundos escritos («1:25», «85 s») y frases que se dicen en el video

Todo vive en <proyecto>/pistas_trailer/: pistas.json y los archivos subidos.

Uso (para revisar qué entiende la app de tus pistas):
  python pistas.py --proyecto mis_proyectos/x
"""
import argparse, json, os, re, subprocess, sys, unicodedata
import numpy as np

CARPETA = 'pistas_trailer'
FASES = ['ANTES', 'DURANTE', 'DESPUES']
NOMBRE = {'ANTES': 'ANTES', 'DURANTE': 'DURANTE', 'DESPUES': 'DESPUÉS'}
IMAGENES = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')
AUDIOS = ('.mp3', '.wav', '.m4a', '.ogg', '.webm', '.opus', '.aac')
MINI_W, MINI_H = 64, 36
CERCA = 20  # segundos: un clip a menos de esto de un candidato "respeta" la pista
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def vacio():
    return {f: [] for f in FASES}


def leer(d):
    f = os.path.join(d, CARPETA, 'pistas.json')
    try:
        datos = json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        return vacio()
    return {fase: [p for p in datos.get(fase, []) if isinstance(p, dict)] for fase in FASES}


def hay(pistas):
    return any(pistas[f] for f in FASES)


def segundos(txt):
    """«1:25» -> 85, «1:02:03» -> 3723, «85», «85.5 s» -> 85.5. None si no hay número."""
    if txt is None or txt == '':
        return None
    if isinstance(txt, (int, float)):
        return float(txt)
    txt = str(txt).strip().replace(',', '.')
    m = re.fullmatch(r'(?:(\d+):)?(\d+):(\d{1,2}(?:\.\d+)?)', txt)
    if m:
        h, mi, s = m.groups()
        return int(h or 0) * 3600 + int(mi) * 60 + float(s)
    m = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(?:s|seg|segundos?)?', txt)
    return float(m.group(1)) if m else None


def tiempos_en_texto(txt):
    """Los segundos escritos dentro de un texto libre: «en el 2:10», «a los 95 s», «minuto 3»."""
    out = []
    for m in re.finditer(r'\b(?:(\d+):)?(\d{1,2}):(\d{2})\b', txt):
        out.append(int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3)))
    for m in re.finditer(r'\b(\d+(?:[.,]\d+)?)\s*(?:s|seg|segundos?)\b', txt, re.I):
        out.append(float(m.group(1).replace(',', '.')))
    for m in re.finditer(r'\bminuto\s+(\d+)\b', txt, re.I):
        out.append(int(m.group(1)) * 60)
    return out


def normal(c):
    return ''.join(x for x in unicodedata.normalize('NFD', c.lower()) if unicodedata.category(x) != 'Mn')


def palabras_clave(txt):
    return sorted({w for w in re.findall(r'[a-z0-9ñ]+', normal(txt)) if len(w) >= 4})


# ---------- capturas: buscar en el video los momentos que más se parecen ----------

def _gris(crudo, n):
    f = np.frombuffer(crudo, np.uint8)[:n * MINI_W * MINI_H].reshape(n, -1).astype(np.float32)
    f -= f.mean(axis=1, keepdims=True)
    return f / (np.linalg.norm(f, axis=1, keepdims=True) + 1e-6)


def _mini(entrada, extra):
    vf = f'scale={MINI_W}:{MINI_H},format=gray'
    return subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', entrada] + extra + ['-vf', vf, '-f', 'rawvideo', '-'],
                          capture_output=True, check=True).stdout


def miniaturas(d):
    """Una miniatura gris por segundo del original (en caché, se hace una sola vez)."""
    orig = os.path.join(d, 'original.mp4')
    cache = os.path.join(d, 'original.miniaturas.npz')
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(orig):
        z = np.load(cache)
        return z['t'], z['f']
    print('Comparando tus capturas con el video (la primera vez tarda un poco)…', flush=True)
    crudo = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', orig, '-vf', f'fps=1,scale={MINI_W}:{MINI_H},format=gray',
                            '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    n = len(crudo) // (MINI_W * MINI_H)
    f = _gris(crudo, n)
    t = np.arange(n, dtype=np.float32) + 0.5
    np.savez(cache, t=t, f=f)
    return t, f


def parecidos(d, imagen, top=3, separacion=8):
    """[(segundo, parecido 0..1)] de los momentos del video más parecidos a la imagen."""
    t, f = miniaturas(d)
    if not len(t):
        return []
    q = _gris(_mini(imagen, ['-frames:v', '1']), 1)[0]
    s = f @ q
    mejor = float(s.max())
    if mejor < 0.35:  # no se parece a nada: probablemente es una foto de otra cosa
        return []
    out = []
    for i in np.argsort(-s):
        if s[i] < max(0.35, mejor * 0.75):
            break
        if all(abs(t[i] - x) >= separacion for x, _ in out):
            out.append((round(float(t[i]), 1), round(float(s[i]), 2)))
        if len(out) == top:
            break
    return out


# ---------- audio y texto: buscar lo que se dice en la transcripción ----------

def transcribir_audio(d, archivo):
    """Texto de un audio de pista (en caché junto al archivo). Scribe si hay clave, si no Whisper."""
    f = os.path.join(d, CARPETA, archivo)
    cache = f + '.txt'
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(f):
        return open(cache, encoding='utf-8').read().strip()
    sys.path.insert(0, os.path.join(RAIZ, 'transcripcion'))
    import transcribir as tr
    mp3 = tr.audio(f)
    try:
        pal = tr.scribe(mp3, 'es') if tr.CLAVE else tr.whisper(mp3, 'es', 'small')
    except SystemExit as e:
        print(f'· no pude transcribir el audio {archivo}: {e}', flush=True)
        return ''
    txt = ' '.join(w['texto'] for w in pal).strip()
    open(cache, 'w', encoding='utf-8').write(txt)
    return txt


def palabras_video(d):
    f = os.path.join(d, 'transcripcion.json')
    try:
        return json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        return []


def dicho(palabras, txt, top=2, ventana=12.0):
    """[(segundo, coincidencia 0..1)] donde la transcripción del video dice algo parecido a txt."""
    clave = palabras_clave(txt)
    if not clave or not palabras:
        return []
    raices = {w[:5] for w in clave}
    norm = [(w['inicio'], normal(w['texto'])[:5]) for w in palabras]
    puntos = []
    for i, (t0, _) in enumerate(norm):
        k, vistas = i, {}
        while k < len(norm) and norm[k][0] <= t0 + ventana:
            if norm[k][1] in raices:
                vistas.setdefault(norm[k][1], norm[k][0])
            k += 1
        if vistas:  # el centro de las palabras que coinciden, no el de la ventana
            puntos.append((len(vistas) / len(raices), sum(vistas.values()) / len(vistas), len(vistas)))
    minimo = 1 if len(raices) == 1 else 2
    out = []
    for frac, t, n in sorted(puntos, reverse=True):
        if n < minimo or frac < 0.4:
            break
        if all(abs(t - x) >= ventana for x, _ in out):
            out.append((round(t, 1), round(frac, 2)))
        if len(out) == top:
            break
    return out


# ---------- todo junto ----------

def analizar(d, dur=None):
    """Cada pista con su descripción y sus segundos candidatos. {fase: [{n, tipo, desc, candidatos, imagen}]}"""
    pistas = leer(d)
    palabras = None
    res = {f: [] for f in FASES}
    for fase in FASES:
        for k, p in enumerate(pistas[fase], 1):
            tipo = p.get('tipo', 'texto')
            nota = (p.get('nota') or p.get('texto') or '').strip()
            s = segundos(p.get('segundo'))
            cand, partes, imagen = [], [], None
            if s is not None:
                cand.append((s, 'el autor marcó este segundo'))
            arch = os.path.join(d, CARPETA, os.path.basename(p.get('archivo') or ''))
            if tipo == 'captura' and os.path.isfile(arch):
                imagen = arch
                partes.append('captura adjunta')
                if s is None:
                    try:
                        cand += [(x, f'se parece {round(v * 100)} %') for x, v in parecidos(d, arch)]
                    except subprocess.CalledProcessError:
                        partes.append('no pude leer la imagen')
            if nota:
                partes.append(f'el autor escribe: «{nota}»')
            buscar = nota
            if tipo == 'audio' and os.path.isfile(arch):
                txt = transcribir_audio(d, os.path.basename(arch))
                partes.append(f'audio que dice: «{txt}»' if txt else 'audio sin voz que se entienda')
                buscar = (buscar + ' ' + txt).strip()
            if buscar:
                cand += [(x, 'segundo escrito en la pista') for x in tiempos_en_texto(buscar)]
                if palabras is None:
                    palabras = palabras_video(d)
                cand += [(x, f'se dice algo parecido, {round(v * 100)} %') for x, v in dicho(palabras, buscar)]
            if dur:
                cand = [(min(max(x, 0), dur - 0.5), por) for x, por in cand]
            vistos, unicos = [], []
            for x, por in cand:
                if all(abs(x - y) >= 3 for y in vistos):
                    vistos.append(x); unicos.append((round(x, 1), por))
            res[fase].append({'n': k, 'tipo': tipo, 'desc': ', '.join(partes) or tipo, 'candidatos': unicos, 'imagen': imagen})
    return res


def texto_prompt(an):
    """La parte del encargo a la IA que cuenta las pistas."""
    lineas = []
    for fase in FASES:
        if not an[fase]:
            continue
        lineas.append(f'{NOMBRE[fase]}:')
        for p in an[fase]:
            c = '; '.join(f'segundo {x:.1f} ({por})' for x, por in p['candidatos']) or 'sin segundo claro: búscalo tú en las capturas y la transcripción'
            lineas.append(f'- Pista {p["n"]} ({p["desc"]}). Dónde mirar: {c}')
    if not lineas:
        return ''
    return ('Pistas del autor para elegir los tramos (son orientativas, no cortes exactos). Para cada fase con pistas,\n'
            'prefiere clips cuya ventana caiga en esos segundos o cerca, o en momentos que muestren algo parecido.\n'
            'Si una pista no calza con nada del video, elige igual lo mejor de esa fase.\n' + '\n'.join(lineas))


def revisar_clips(an, clips):
    """Avisos cuando la IA ignoró las pistas de una fase."""
    avisos = []
    for fase in FASES:
        cand = [x for p in an[fase] for x, _ in p['candidatos']]
        if not cand:
            continue
        mios = [c for c in clips if c.get('fase') in (fase, NOMBRE[fase])]
        if not mios:
            avisos.append(f'{NOMBRE[fase]}: diste pistas pero la IA no puso ningún clip de esta fase')
            continue
        if not any(min(abs(x - (c['ventana'][0] + c['ventana'][1]) / 2) for x in cand) <= CERCA for c in mios):
            avisos.append(f'{NOMBRE[fase]}: ningún clip quedó cerca de tus pistas ({", ".join(f"{x:.0f} s" for x in cand)}). '
                          'Revisa trailer.json o pídelo otra vez')
    return avisos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True)
    a = ap.parse_args()
    an = analizar(a.proyecto)
    print(texto_prompt(an) or 'No hay pistas en este proyecto.')


if __name__ == '__main__':
    main()
