"""«🔊 Efectos de sonido»: un clic suave cuando tocas un botón, un «whoosh» en los cortes y un golpe en los sellos del tráiler.

Los momentos ya los sabe la app: los "eventos" del guion (cada botón que presionas, con su segundo en la grabación) y
los cortes entre bloques que saltan a otra parte del video. Se activa por proyecto (edicion.json: "sonidos": true) y lo
mezclan «Poner la voz» (voz/mezclar_voz.py) y el tráiler.

Los sonidos viven en mis_sonidos/ (los mismos para todos tus videos):
  - gratis: la app los fabrica la primera vez en tu PC (sin internet);
  - con ElevenLabs Sound Effects: «Generar con ElevenLabs» en «🎛 Audio e imagen» los crea una sola vez (unos 100
    créditos cada uno) y quedan guardados; también puedes poner los tuyos con el mismo nombre (clic.mp3, whoosh.mp3…).

Uso suelto: python sonidos.py --proyecto mis_proyectos/x            (muestra dónde iría cada sonido)
            python sonidos.py --generar eleven [--solo clic]        (crea la biblioteca con ElevenLabs)
"""
import argparse, json, os, re, subprocess, urllib.error, urllib.request, wave

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIBLIOTECA = os.path.join(RAIZ, 'mis_sonidos')
SR = 44100
DESFASE = 0.3  # el de mezclar_voz.py: el bloque empieza 0,3 s antes que su voz

# nombre: (para qué es, pedido a ElevenLabs, segundos, volumen en la mezcla)
SONIDOS = {
    'clic': ('al tocar un botón', 'soft subtle mouse click, clean UI tap, short, no reverb', 0.5, 0.6),
    'whoosh': ('en los cortes', 'quick soft whoosh transition, airy swipe, short', 0.8, 0.30),
    'sello': ('en los sellos del tráiler', 'punchy cinematic stamp impact hit, deep boom, short', 1.0, 0.55),
    'exito': ('cuando se ve el resultado', 'positive success notification chime, bright, short', 1.0, 0.35),
}
TOCA = re.compile(r'puls|presion|toc|clic|click|selecc|elig|marc|activ|desactiv|bot[oó]n|volumen|power|encend|enter|'
                  r'acept|confirm|conect|omitir|siguiente|instalar|abr[ei]', re.I)
RESULTADO = re.compile(r'listo|desbloque|ya no (pide|aparece|est)|sin cuenta|libre|[ée]xito|funcion[aó]|qued[oó]', re.I)
NO_TOCA = re.compile(r'^\s*(menciona|muestra|explica|dice|habla|cuenta|aparece|se ve)\b', re.I)  # contar no es tocar
SEPARACION = {'clic': 1.2, 'whoosh': 6.0, 'exito': 30.0}  # lo mínimo entre dos sonidos iguales, para no cansar


def _clave():
    k = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not k:
        try:
            k = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')).get('elevenlabs', '').strip()
        except (OSError, ValueError):
            k = ''
    return {'xi-api-key': k} if k else {}


def archivo(nombre):
    for ext in ('.mp3', '.wav'):
        f = os.path.join(BIBLIOTECA, nombre + ext)
        if os.path.exists(f):
            return f
    return None


def _escribir_wav(f, x):
    import numpy as np
    x = np.clip(x / max(1e-6, float(np.abs(x).max())) * 0.9, -1, 1)
    with wave.open(f, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype('<i2').tobytes())


def fabricar(nombre):
    """El sonido hecho en tu PC con numpy (gratis, sin internet). Devuelve la ruta."""
    import numpy as np
    rng = np.random.default_rng(7)
    if nombre == 'clic':  # dos chasquidos muy cortos: el de apretar y el de soltar
        n = int(SR * 0.06)
        t = np.arange(n) / SR
        golpe = lambda f0, a: a * np.sin(2 * np.pi * f0 * t) * np.exp(-t * 900) + a * 0.4 * rng.standard_normal(n) * np.exp(-t * 1500)
        x = golpe(2400, 1.0)
        x[int(SR * 0.025):] += golpe(1800, 0.5)[:n - int(SR * 0.025)]
    elif nombre == 'whoosh':  # ruido que sube y baja, filtrado cada vez más agudo
        n = int(SR * 0.55)
        t = np.arange(n) / SR
        ruido = rng.standard_normal(n)
        x = np.zeros(n)
        for k in range(8):  # tramos con un filtro distinto (paso bajo de un polo que se abre)
            a, b = k * n // 8, (k + 1) * n // 8
            alfa = 0.02 + 0.10 * k / 7
            y, prev = np.zeros(b - a), 0.0
            for i, v in enumerate(ruido[a:b]):
                prev += alfa * (v - prev); y[i] = prev
            x[a:b] = y
        x *= np.sin(np.pi * np.clip(t / t[-1], 0, 1)) ** 2
    elif nombre == 'sello':  # golpe grave con un poco de cuerpo
        n = int(SR * 0.7)
        t = np.arange(n) / SR
        f = 90 * np.exp(-t * 6) + 45
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) + 0.25 * rng.standard_normal(n) * np.exp(-t * 40)
    else:  # exito: dos notas que suben
        n = int(SR * 0.7)
        t = np.arange(n) / SR
        x = np.zeros(n)
        for k, f0 in enumerate((880, 1318.5)):
            a = int(SR * 0.12 * k)
            tt = t[:n - a]
            x[a:] += np.sin(2 * np.pi * f0 * tt) * np.exp(-tt * 6) + 0.3 * np.sin(4 * np.pi * f0 * tt) * np.exp(-tt * 9)
    os.makedirs(BIBLIOTECA, exist_ok=True)
    f = os.path.join(BIBLIOTECA, nombre + '.wav')
    _escribir_wav(f, x)
    return f


def generar_eleven(nombre, clave=None):
    """Lo crea ElevenLabs Sound Effects (una sola vez, unos 100 créditos) y lo deja en mis_sonidos/<nombre>.mp3."""
    _, pedido, dur, _ = SONIDOS[nombre]
    clave = _clave() if clave is None else clave
    req = urllib.request.Request('https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128',
                                 data=json.dumps({'text': pedido, 'duration_seconds': dur, 'prompt_influence': 0.6}).encode(),
                                 headers={'Content-Type': 'application/json', **clave})
    try:
        datos = urllib.request.urlopen(req, timeout=120).read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f'ElevenLabs no pudo crear «{nombre}»: error {e.code} {e.read()[:200]}')
    os.makedirs(BIBLIOTECA, exist_ok=True)
    f = os.path.join(BIBLIOTECA, nombre + '.mp3')
    open(f + '.nuevo', 'wb').write(datos)
    os.replace(f + '.nuevo', f)
    viejo = os.path.join(BIBLIOTECA, nombre + '.wav')
    if os.path.exists(viejo):  # el fabricado en la PC queda de lado: manda el de ElevenLabs
        os.replace(viejo, viejo + '.pc')
    return f


def asegurar(nombre):
    return archivo(nombre) or fabricar(nombre)


def activo(d):
    try:
        return bool(json.load(open(os.path.join(d, 'edicion.json'), encoding='utf-8')).get('sonidos'))
    except (OSError, ValueError, AttributeError):
        return False


def ajustes(d):
    try:
        e = json.load(open(os.path.join(d, 'edicion.json'), encoding='utf-8'))
    except (OSError, ValueError):
        e = {}
    return {'volumen': min(max(float(e.get('sonidos_volumen', 1.0)), 0.0), 2.0),
            'tipos': [t for t in e.get('sonidos_tipos', ['clic', 'whoosh', 'exito']) if t in SONIDOS]}


def a_video(bloques, s):
    """El segundo del video armado donde se ve el segundo `s` de la grabación (None si ese tramo no se usó)."""
    for b in bloques:
        mo = b.get('montaje') or {}
        if b.get('inicio_min') is None or mo.get('src_inicio') is None or not str(mo.get('modo', '')).startswith('lento'):
            continue
        s0, s1 = float(mo['src_inicio']), float(mo.get('src_fin') or mo['src_inicio'])
        if s0 <= s <= s1:
            return round(float(b['inicio_min']) + (s - s0) / float(mo.get('velocidad') or 1), 2)
    return None


def eventos_pantalla(d):
    """Los eventos que anotó la IA del guion (eventos_pantalla.txt: «2:20 pulsa Volumen más y Power…»)."""
    out = []
    try:
        for linea in open(os.path.join(d, 'eventos_pantalla.txt'), encoding='utf-8'):
            m = re.match(r'\s*(?:(\d+):)?(\d+(?:[.,]\d+)?)\s+(.*)', linea)
            if m:
                out.append({'s': int(m.group(1) or 0) * 60 + float(m.group(2).replace(',', '.')), 'evento': m.group(3).strip()})
    except OSError:
        pass
    return out


def plan(d):
    """[{'t', 'tipo', 'por_que'}] de los sonidos del video, en segundos del video armado (antes del tráiler)."""
    try:
        g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    bl = [b for b in g.get('bloques', []) if isinstance(b.get('montaje'), dict)]
    tipos = ajustes(d)['tipos']
    out = []
    if 'clic' in tipos:
        for ev in g.get('eventos') or eventos_pantalla(d):
            try:
                s = float(ev.get('s'))
            except (TypeError, ValueError, AttributeError):
                continue
            if TOCA.search(str(ev.get('evento') or '')) and not NO_TOCA.search(str(ev.get('evento') or '')):
                t = a_video(bl, s)
                if t is not None:
                    out.append({'t': t, 'tipo': 'clic', 'por_que': str(ev.get('evento'))[:80]})
    if 'whoosh' in tipos:
        for a, b in zip(bl, bl[1:]):
            ma, mb = a['montaje'], b['montaje']
            if b.get('inicio_min') is None:
                continue
            fin_a = ma.get('src_fin') if ma.get('src_fin') is not None else ma.get('src_inicio')
            salto = mb.get('modo') == 'imagen' or ma.get('modo') == 'imagen' or (
                fin_a is not None and mb.get('src_inicio') is not None and abs(float(mb['src_inicio']) - float(fin_a)) > 3)
            if salto:
                out.append({'t': max(0.0, round(float(b['inicio_min']) - 0.15, 2)), 'tipo': 'whoosh', 'por_que': f"corte a {b['id']}"})
    if 'exito' in tipos:
        for b in bl:
            if b.get('inicio_min') is not None and RESULTADO.search(str(b.get('texto') or '')) and bl.index(b) > len(bl) // 2:
                out.append({'t': round(float(b['inicio_min']) + DESFASE, 2), 'tipo': 'exito', 'por_que': f"resultado en {b['id']}"})
                break
    out.sort(key=lambda x: x['t'])
    ultimo, final = {}, []
    for x in out:  # que no se amontonen
        if x['t'] - ultimo.get(x['tipo'], -1e9) >= SEPARACION.get(x['tipo'], 1.0):
            final.append(x); ultimo[x['tipo']] = x['t']
    return final


def filtros(eventos, primera_entrada, volumen=1.0):
    """(entradas ffmpeg, filtros, etiqueta) para sumar los sonidos a una mezcla. Una entrada por tipo de sonido,
    repartida con asplit; cada copia entra con su adelay."""
    por_tipo = {}
    for e in eventos:
        por_tipo.setdefault(e['tipo'], []).append(e['t'])
    entradas, fl, labs, k = [], [], [], primera_entrada
    for tipo, ts in por_tipo.items():
        entradas += ['-i', asegurar(tipo)]
        vol = SONIDOS[tipo][3] * volumen
        fl.append(f"[{k}:a]aresample=44100,aformat=channel_layouts=stereo,volume={vol:.2f},asplit={len(ts)}" + ''.join(f'[s{k}_{j}]' for j in range(len(ts))))
        for j, t in enumerate(ts):
            fl.append(f"[s{k}_{j}]adelay={int(max(0, t) * 1000)}:all=1[sd{k}_{j}]")
            labs.append(f'[sd{k}_{j}]')
        k += 1
    if not labs:
        return [], [], None
    fl.append(''.join(labs) + f"amix=inputs={len(labs)}:normalize=0[sfx]" if len(labs) > 1 else f"{labs[0]}anull[sfx]")
    return entradas, fl, '[sfx]'


def del_trailer(clips, carpeta):
    """Los sonidos del tráiler: un golpe en cada sello (cuando empieza ANTES, DURANTE y DESPUÉS) y un whoosh en cada corte."""
    if not activo(carpeta):
        return []
    out, t, fase = [], 0.0, None
    for c in clips:
        if c.get('fase') != fase:
            out.append({'t': round(t, 2), 'tipo': 'sello'}); fase = c.get('fase')
        elif t > 0:
            out.append({'t': round(max(0, t - 0.1), 2), 'tipo': 'whoosh'})
        t += float(c.get('dur') or 0)
    return out


def superponer(wav, eventos, total, volumen=1.0):
    """Suma los sonidos a un .wav (o lo crea en silencio si no existe) sin cambiar su largo."""
    ins = ['-i', wav] if os.path.exists(wav) else ['-f', 'lavfi', '-t', f'{total:.2f}', '-i', 'anullsrc=r=48000:cl=stereo']
    e, fl, lab = filtros(eventos, 1, volumen)
    if not lab:
        return
    fl.append(f"[0:a]aformat=channel_layouts=stereo[base];[base]{lab}amix=inputs=2:normalize=0:duration=first,aresample=48000[a]")
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins + e + ['-filter_complex', ';'.join(fl), '-map', '[a]',
                    '-t', f'{total:.2f}', wav + '.sfx.wav'], check=True)
    os.replace(wav + '.sfx.wav', wav)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto')
    ap.add_argument('--generar', choices=['pc', 'eleven'])
    ap.add_argument('--solo', help='solo este sonido (clic, whoosh, sello, exito)')
    a = ap.parse_args()
    if a.generar:
        for n in ([a.solo] if a.solo else list(SONIDOS)):
            if n not in SONIDOS:
                raise SystemExit(f'no conozco el sonido «{n}»')
            f = generar_eleven(n) if a.generar == 'eleven' else fabricar(n)
            print(f'· {n} ({SONIDOS[n][0]}): {f}', flush=True)
        return
    if a.proyecto:
        p = plan(os.path.abspath(a.proyecto))
        for x in p:
            print(f"{x['t']:7.2f} s  {x['tipo']:7s} {x['por_que']}")
        print(f'{len(p)} sonidos', flush=True)


if __name__ == '__main__':
    main()
