"""ACORTAR: mira la grabación entera y quita o acelera lo que sobra, hasta la duración que pidas.

Busca, en tu PC y sin IA:
  - silencios: donde no hablas (de la transcripción; si no hay, se mide el sonido)
  - pantalla quieta: donde no cambia nada (mide el movimiento cuadro a cuadro)
  - esperas: el celular reiniciando, el logo, «cargando», «conectando», poner la clave del Wi-Fi, una barra con %…
    (por el texto que se lee en pantalla y por lo que dices)
Con IA configurada, además le pide que marque las partes no importantes (repeticiones, errores, explicaciones que
no suman), mirando la transcripción, el mapa del video y las hojas de contacto.

Qué hace con cada tramo:
  - silencio con la pantalla quieta → se corta (quedan 0,3 s a cada lado para que no salte)
  - espera (reinicio, Wi-Fi, carga) → se acelera a unos 2–3 s: se ve que pasó, sin esperar
  - silencio con movimiento → se acelera ×3 (sin sonido)
  - no importante (IA) → se corta entero, también si hablas
Si pides una duración (por ejemplo 8 min), usa primero lo más obvio y para cuando llega; si con todo no alcanza,
lo dice. Tu voz nunca se acelera.

Deja acortar.json (cada tramo, con «usar» para que lo prendas o apagues en la app) y acortado.mp4 (tu grabación ya
acortada, con tu voz). El guion con IA usa los tramos y la duración pedida para que el video dure eso.

Uso:
  python acortar.py --proyecto . --objetivo 8 [--ajustes ajustes.json] [--sin-ia]
  python acortar.py --proyecto . --rehacer      # solo vuelve a armar acortado.mp4 con lo marcado en acortar.json
"""
import argparse, json, os, re, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'nitidez'))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
import codificar  # noqa: E402  con la tarjeta NVIDIA si la hay, si no con el procesador
from nitidez import analizar  # noqa: E402

SIN_VOZ_MIN = 1.5   # un silencio más corto es respirar: no se toca
MARGEN = 0.3        # lo que queda a cada lado de un corte
ESPERA = (r'reinici|reboot|restart|apag|encend|logo|cargando|loading|espera|wi-?fi|wlan|contrase|password|clave de red|'
          r'conectando|connecting|descargando|downloading|actualizando|updating|instalando|installing|verificando|'
          r'formateando|restablec|please wait')  # sin «%»: la batería se ve en todas las pantallas
PRIORIDAD = {'espera': 1, 'silencio': 2, 'movimiento': 3, 'no_importante': 4}


def duracion(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True, check=True).stdout.strip() or 0)


def mmss(s):
    return f'{int(s // 60)}:{int(s % 60):02d}'


def leer_json(f, defecto):
    try:
        return json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        return defecto


def tramos_sin_voz(d, video, dur):
    """[(inicio, fin)] donde no hablas: entre palabras de la transcripción, o por el sonido si no hay transcripción."""
    pal = [w for w in leer_json(os.path.join(d, 'transcripcion.json'), []) if isinstance(w, dict) and 'inicio' in w]
    if pal:
        huecos, previo = [], 0.0
        for w in sorted(pal, key=lambda w: w['inicio']):
            if w['inicio'] - previo >= SIN_VOZ_MIN:
                huecos.append((previo, w['inicio']))
            previo = max(previo, w.get('fin', w['inicio'] + 0.3))
        if dur - previo >= SIN_VOZ_MIN:
            huecos.append((previo, dur))
        return huecos, pal
    print('· no hay transcripción: mido el sonido para encontrar los silencios', flush=True)
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', video, '-vn', '-af', f'silencedetect=noise=-35dB:d={SIN_VOZ_MIN}',
                        '-f', 'null', '-'], capture_output=True, text=True)
    ini = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', r.stderr)]
    fin = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', r.stderr)]
    return [(a, fin[k] if k < len(fin) else dur) for k, a in enumerate(ini)], []


def esperas(d, pal):
    """[(inicio, fin, motivo)] donde se espera algo: por lo que se lee en pantalla (mapa del video) o lo que dices."""
    mapa = (leer_json(os.path.join(d, 'mapa_video.json'), {}) or {}).get('cuadros', [])
    out = []
    for k, c in enumerate(mapa):
        visto = ' '.join(str(c.get(x) or '') for x in ('pantalla', 'accion', 'texto'))
        m = re.search(ESPERA, visto, re.I)
        if m:
            fin = mapa[k + 1]['t'] if k + 1 < len(mapa) else c['t'] + 15
            out.append((c['t'], fin, f'se ve «{m.group(0).strip()}»'))
    for i, w in enumerate(pal):  # «ahora se reinicia», «pongo la clave del wifi»: lo que viene es espera
        frase = ' '.join(x['texto'] for x in pal[i:i + 4])
        m = re.search(ESPERA, frase, re.I)
        if m and re.search(ESPERA, w['texto'], re.I):
            out.append((w['inicio'], w['inicio'] + 25, f'dices «{m.group(0).strip()}»'))
    return out


def quieto(t, mo, a, b, umbral, pico):
    """Casi todo el tramo sin movimiento y ningún cambio de pantalla en medio (si cambia algo, se acelera, no se corta)."""
    sel = (t >= a) & (t <= b)
    return bool(sel.any()) and float((mo[sel] <= umbral).mean()) >= 0.8 and float(mo[sel].max()) <= pico


def candidatos(d, video, dur):
    import numpy as np
    huecos, pal = tramos_sin_voz(d, video, dur)
    t, _, mo = analizar(video, os.path.join(d, 'original.nitidez.npz'))
    umbral = max(float(np.percentile(mo, 30)) * 1.3, 0.6)
    pico = max(float(np.percentile(mo, 90)) * 1.5, umbral * 2)
    es = esperas(d, pal)
    out = []
    for a, b in huecos:
        a2, b2 = a + MARGEN, b - MARGEN
        if b2 - a2 < SIN_VOZ_MIN - 2 * MARGEN:
            continue
        motivo = next((m for x, y, m in es if x < b2 and y > a2), None)
        largo = b2 - a2
        if motivo and largo >= 4:  # se ve que se reinició o que se conecta, en 2–3 s
            v = round(min(16, max(2, largo / 2.5)), 1)
            out.append({'inicio': a2, 'fin': b2, 'tipo': 'espera', 'motivo': f'espera ({motivo})', 'accion': 'acelerar', 'velocidad': v})
        elif quieto(t, mo, a2, b2, umbral, pico):
            out.append({'inicio': a2, 'fin': b2, 'tipo': 'silencio', 'motivo': 'silencio con la pantalla quieta', 'accion': 'cortar'})
        elif largo >= 3:
            out.append({'inicio': a2, 'fin': b2, 'tipo': 'movimiento', 'motivo': 'sin voz, pasa algo en pantalla',
                        'accion': 'acelerar', 'velocidad': 3.0})
    return out, pal


def no_importantes(d, ajustes, pal, dur, objetivo):
    """La IA marca lo que sobra (repeticiones, errores, explicaciones que no suman) mirando transcripción y video."""
    sys.path.insert(0, os.path.join(RAIZ, 'ia'))
    import ia
    try:
        mapa = ia.mapa_video(d, ajustes if ajustes.get('imagenes', True) else None)
    except Exception as e:
        print(f'· no pude armar el mapa del video ({e}); la IA mira solo la transcripción', flush=True)
        mapa = []
    try:
        caps = ia.hojas_contacto(d) if ajustes.get('imagenes', True) else []
    except Exception:
        caps = []
    trans = ia.transcripcion(d) or '(sin transcripción)'
    pedido = f"""Eres editor de videos tutoriales de YouTube. La grabación dura {mmss(dur)}{f' y el autor quiere que dure unos {mmss(objetivo)}' if objetivo else ''}.
Marca los tramos NO IMPORTANTES que se pueden cortar sin que se pierda un paso: el autor repite lo mismo, se equivoca y
vuelve a empezar, explica algo que no suma, espera sin hacer nada, busca algo en pantalla. Nunca marques un paso del
método (por ejemplo poner la key, elegir el puerto, el resultado final) ni el comienzo o el final del video.

Transcripción ([minuto:segundo] texto):
{trans}

Mapa de la grabación (lo que se ve en cada cambio de pantalla):
{ia.texto_mapa(mapa) if mapa else '(sin mapa)'}

Hojas de contacto adjuntas: {len(caps)}.
Responde SOLO con un objeto JSON {{"tramos": [{{"inicio": "m:ss", "fin": "m:ss", "motivo": "por qué sobra, corto"}}]}}."""
    r = ia.extraer_json(ia.llamar(ajustes, pedido, caps))

    def seg(x):
        x = str(x).strip()
        if ':' in x:
            m, s = x.rsplit(':', 1)
            return int(m) * 60 + float(s)
        return float(x)
    out = []
    for x in (r.get('tramos', []) if isinstance(r, dict) else []):
        try:
            a, b = seg(x['inicio']), seg(x['fin'])
        except (KeyError, ValueError, TypeError):
            continue
        for w in pal:  # que el corte no caiga a mitad de una palabra
            fin_w = w.get('fin', w['inicio'] + 0.3)
            if w['inicio'] < a < fin_w:
                a = w['inicio']
            if w['inicio'] < b < fin_w:
                b = fin_w
        if 3 <= b - a and a > 5 and b < dur - 5:
            out.append({'inicio': a, 'fin': b, 'tipo': 'no_importante', 'motivo': str(x.get('motivo') or 'no suma')[:120],
                        'accion': 'cortar'})
    print(f'La IA marcó {len(out)} tramos no importantes.', flush=True)
    return out


def ahorro(c):
    largo = c['fin'] - c['inicio']
    return largo if c['accion'] == 'cortar' else largo - largo / c['velocidad']


def sin_choques(lista):
    """Si dos tramos se pisan, el corte de la IA gana y del otro queda lo que sobra a los lados (si dura 2 s o más)."""
    out = []
    for c in sorted(lista, key=lambda c: (PRIORIDAD[c['tipo']] if c['tipo'] != 'no_importante' else 0, -ahorro(c))):
        trozos = [(c['inicio'], c['fin'])]
        for o in out:
            trozos = [x for a, b in trozos for x in ((a, min(b, o['inicio'])), (max(a, o['fin']), b)) if x[1] - x[0] > 0]
        out += [dict(c, inicio=a, fin=b) for a, b in trozos if b - a >= 2]
    return sorted(out, key=lambda c: c['inicio'])


def elegir(tramos, dur, objetivo):
    """Usa primero lo más obvio (esperas, silencios quietos…) y para al llegar a la duración pedida."""
    for c in tramos:
        c['usar'] = not objetivo
    if not objetivo:
        return
    total = dur
    for c in sorted(tramos, key=lambda c: (PRIORIDAD[c['tipo']], -ahorro(c))):
        if total <= objetivo:
            break
        falta = total - objetivo
        if ahorro(c) > falta * 1.1:  # se pasaría de corto
            if c['accion'] == 'acelerar':  # se acelera menos, justo lo que falta
                largo = c['fin'] - c['inicio']
                v = round(largo / max(largo - falta, 0.1), 2)
                if v < 1.2:
                    continue
                c['velocidad'] = v
            else:
                continue  # un corte no se achica: pruebo con los siguientes, más chicos
        c['usar'] = True
        total -= ahorro(c)


def resultado(tramos, dur):
    return dur - sum(ahorro(c) for c in tramos if c.get('usar'))


def armar(video, tramos, salida):
    """El video acortado: lo normal tal cual, los cortes fuera y lo acelerado sin sonido."""
    dur = duracion(video)
    partes, previo = [], 0.0
    for c in sorted((c for c in tramos if c.get('usar')), key=lambda c: c['inicio']):
        if c['inicio'] > previo + 0.05:
            partes.append((previo, c['inicio'], 1.0))
        if c['accion'] == 'acelerar':
            partes.append((c['inicio'], c['fin'], c['velocidad']))
        previo = max(previo, c['fin'])
    if dur > previo + 0.05:
        partes.append((previo, dur, 1.0))
    v = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                   '-of', 'json', video], capture_output=True, text=True, check=True).stdout)['streams'][0]
    W, H = v['width'] + v['width'] % 2, v['height'] + v['height'] % 2
    hay_audio = bool(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0',
                                     video], capture_output=True, text=True).stdout.strip())
    fil = []
    for k, (a, b, vel) in enumerate(partes):
        fil.append(f'[0:v]trim={a:.3f}:{b:.3f},setpts=(PTS-STARTPTS)/{vel},scale={W}:{H},fps=30,format=yuv420p,setsar=1[v{k}]')
        largo = (b - a) / vel
        if vel == 1.0 and hay_audio:
            fil.append(f'[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a{k}]')
        else:
            fil.append(f'anullsrc=r=48000:cl=stereo,atrim=0:{largo:.3f}[a{k}]')
    fil.append(''.join(f'[v{k}][a{k}]' for k in range(len(partes))) + f'concat=n={len(partes)}:v=1:a=1[v][a]')
    script = salida + '.filtro.txt'  # con cientos de tramos la línea de comandos de Windows queda corta
    open(script, 'w', encoding='utf-8').write(';\n'.join(fil))
    print(f'Armando el video acortado ({len(partes)} partes)…', flush=True)
    try:
        codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-stats', '-y', '-i', video, '-filter_complex_script', script,
                        '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac',
                        '-b:a', '160k', '-movflags', '+faststart', salida], check=True)
    finally:
        os.remove(script)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--objetivo', type=float, default=0, help='minutos que quieres que dure (0 = quitar todo lo que sobra)')
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    ap.add_argument('--sin-ia', action='store_true')
    ap.add_argument('--rehacer', action='store_true', help='solo armar acortado.mp4 con lo marcado en acortar.json')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    video = os.path.join(d, 'original.mp4')
    plan_f, salida = os.path.join(d, 'acortar.json'), os.path.join(d, 'acortado.mp4')
    dur = duracion(video)
    if a.rehacer:
        plan = leer_json(plan_f, None)
        if not plan:
            raise SystemExit('ERROR: todavía no hay tramos: pulsa «Buscar qué acortar» primero.')
    else:
        objetivo = a.objetivo * 60 if a.objetivo > 0 else 0
        if objetivo and objetivo >= dur:
            print(f'· la grabación ya dura {mmss(dur)}, menos que {mmss(objetivo)}: solo quito lo que sobra de verdad', flush=True)
            objetivo = 0
        print(f'Mirando la grabación entera ({mmss(dur)}): silencios, pantalla quieta y esperas…', flush=True)
        tramos, pal = candidatos(d, video, dur)
        aj = leer_json(a.ajustes, {})
        if not a.sin_ia and (aj.get('url') or aj.get('tipo') == 'claude'):
            print(f"Le pido a {aj.get('modelo') or 'la IA'} que marque las partes no importantes…", flush=True)
            try:
                tramos += no_importantes(d, aj, pal, dur, objetivo)
            except (SystemExit, Exception) as e:  # sin IA igual queda lo que encontró tu PC
                print(f'· la IA no pudo ({e}); sigo con lo que encontré yo', flush=True)
        tramos = sin_choques(tramos)
        elegir(tramos, dur, objetivo)
        for k, c in enumerate(tramos, 1):
            c['id'] = f'A{k:02d}'
            c['inicio'], c['fin'] = round(c['inicio'], 2), round(c['fin'], 2)
        plan = {'original_s': round(dur, 1), 'objetivo_s': round(objetivo, 1), 'tramos': tramos}
    plan['resultado_s'] = round(resultado(plan['tramos'], dur), 1)
    json.dump(plan, open(plan_f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    usados = [c for c in plan['tramos'] if c.get('usar')]
    for c in usados:
        print(f"· {mmss(c['inicio'])}–{mmss(c['fin'])} {c['motivo']}: " +
              ('se corta' if c['accion'] == 'cortar' else f"se acelera ×{c['velocidad']:g}"), flush=True)
    if plan.get('objetivo_s') and plan['resultado_s'] > plan['objetivo_s'] * 1.05:
        print(f"AVISO: quitando todo lo que sobra queda en {mmss(plan['resultado_s'])}, más que los {mmss(plan['objetivo_s'])} "
              'que pediste. Para bajar más, la IA tiene que resumir con voz en off (escribir el guion).', flush=True)
    if not usados:
        print('No encontré nada que quitar: la grabación ya va al grano.')
        return
    armar(video, plan['tramos'], salida)
    print(f"Listo acortado.mp4: de {mmss(dur)} a {mmss(plan['resultado_s'])} ({len(usados)} tramos)")


if __name__ == '__main__':
    main()
