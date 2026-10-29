"""«📲 Pantalla grabada»: si grabas la pantalla del celular a la vez que la cámara (scrcpy en Android, QuickTime o la
grabación de pantalla en iPhone), la app pone esa pantalla nítida en los pasos donde hay que leer.

  1. Sincroniza las dos grabaciones: primero por el audio (los sonidos del celular se oyen en las dos) y, si no alcanza,
     por la imagen (cuándo se prende, se apaga o cambia la pantalla en la cámara y en la grabación).
  2. Deja pantalla_celular.mp4 en el tiempo de tu grabación (5 cuadros por segundo): la pantalla grande en el centro,
     sobre tu toma desenfocada.
  3. Agrega a insertos.json un inserto en cada paso para leer (escribir la key, un código, elegir una opción, un mensaje):
     en ese momento el video muestra la pantalla nítida. Tus insertos no se tocan.

Uso: python sincronizar.py --proyecto . [--pantalla pantalla_grabada.mp4] [--desfase 12.3] [--sin-insertos]
     --desfase: segundos de tu grabación donde empieza la grabación de pantalla (si ya lo sabes, no se calcula).
"""
import argparse, json, os, re, subprocess, sys
import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import enderezar  # noqa: E402

SR = 8000
FPS = enderezar.FPS
SALIDA = 'pantalla_celular.mp4'


def duracion(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True).stdout.strip() or 0)


def envolvente(f):
    """Cuánto cambia el sonido 100 veces por segundo (los golpes, clics y avisos), o None si no tiene audio."""
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', f, '-vn', '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'],
                       capture_output=True)
    x = np.frombuffer(r.stdout, np.int16).astype(np.float32)
    if len(x) < SR:
        return None
    paso = SR // 100
    n = len(x) // paso
    e = np.log1p(np.abs(x[:n * paso]).reshape(n, paso).mean(1))
    d = np.maximum(np.diff(e, prepend=e[0]), 0)  # solo cuando el sonido sube (un golpe), no la voz pareja
    return (d - d.mean()) / (d.std() + 1e-6)


def correlacion(a, b, hz):
    """(desfase en s de b dentro de a, qué tan claro es el pico: con ruido sale ~4; más de 8 es confiable)."""
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    c = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    c = np.concatenate([c[-(len(b) - 1):], c[:len(a)]])  # desfases de -(len(b)-1) a len(a)-1
    k = int(np.argmax(c))
    pico = (c[k] - np.median(c)) / (c.std() + 1e-6)
    return (k - (len(b) - 1)) / hz, float(pico)


def brillo_pantalla_grabada(f, hz=5):
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', f, '-vf', f'fps={hz},scale=64:64,format=gray', '-f', 'rawvideo', '-'],
                       capture_output=True)
    v = np.frombuffer(r.stdout, np.uint8).reshape(-1, 64 * 64).mean(1)
    return v


def brillo_en_camara(datos, orig):
    """El brillo de la pantalla del celular en tu grabación (5 por segundo), donde se la encontró; NaN donde no."""
    cap = cv2.VideoCapture(orig)
    out = []
    for t, q in datos:
        if q is None:
            out.append(np.nan); continue
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, c = cap.read()
        if not ok:
            out.append(np.nan); continue
        c = cv2.resize(c, (enderezar.W, enderezar.H)) if c.shape[1] != enderezar.W else c
        out.append(float(cv2.cvtColor(cv2.resize(enderezar.enderezar(c, q, 200), (32, 64)), cv2.COLOR_BGR2GRAY).mean()))
    cap.release()
    return np.array(out, np.float32)


def por_imagen(orig, pant, datos):
    cam = brillo_en_camara(datos, orig)
    gra = brillo_pantalla_grabada(pant, FPS)
    norm = lambda v: np.nan_to_num((np.diff(v, prepend=v[0]) - np.nanmean(np.diff(v))) / (np.nanstd(np.diff(v)) + 1e-6))
    return correlacion(norm(cam), norm(gra), FPS)


def componer_linea(orig, pant, desfase, datos, salida):
    """pantalla_celular.mp4: en el tiempo de tu grabación, la pantalla grabada grande sobre tu toma desenfocada."""
    W, H = enderezar.W, enderezar.H
    p = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
                          salida + '.parcial.mp4'], stdin=subprocess.PIPE)
    co, cp = cv2.VideoCapture(orig), cv2.VideoCapture(pant)
    dp = duracion(pant)
    for t, _ in datos:
        co.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, c = co.read()
        if not ok:
            break
        c = cv2.resize(c, (W, H)) if c.shape[1] != W else c
        tp = t - desfase
        if 0 <= tp <= dp:
            cp.set(cv2.CAP_PROP_POS_MSEC, tp * 1000)
            ok2, s = cp.read()
            c = enderezar.componer(c, s) if ok2 else c
        p.stdin.write(c.tobytes())
    co.release(); cp.release()
    p.stdin.close()
    if p.wait():
        raise SystemExit('ERROR: no se pudo armar la pantalla del celular.')
    os.replace(salida + '.parcial.mp4', salida)


def elegir_insertos(d, desfase, dp):
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    nuevos = []
    for b in g.get('bloques', []):
        mo = b.get('montaje') or {}
        if mo.get('src_inicio') is None or not str(b.get('texto') or '').strip():
            continue
        critico = b.get('tipo') == 'critico' or mo.get('critico')
        if not (critico or enderezar.LEER.search(b['texto'])):
            continue
        s0, s1 = float(mo['src_inicio']), float(mo.get('src_fin') or mo['src_inicio'] + 2)
        t = (s0 + s1) / 2
        if not 0 <= t - desfase <= dp:
            continue  # la grabación de pantalla no cubre este paso
        nuevos.append({'nota': 'pantalla grabada', 'origen': 'scrcpy', 'material': SALIDA, 'src_t': round(t, 2), 'bloque': b['id'],
                       'frase': enderezar.comienzo(b['texto']), 'dur': round(min(5.0, max(2.5, float(b.get('voz_real_s') or 4) * 0.6)), 1),
                       'claves': [{'t': 0, 'cx': 0.5, 'cy': 0.5, 'w': 0.98}, {'t': 3, 'cx': 0.5, 'cy': 0.5, 'w': 0.9}]})
    return nuevos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--pantalla', default='pantalla_grabada.mp4')
    ap.add_argument('--desfase', type=float)
    ap.add_argument('--sin-insertos', action='store_true')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    orig, pant = os.path.join(d, 'original.mp4'), os.path.join(d, a.pantalla)
    if not os.path.exists(pant):
        raise SystemExit('ERROR: falta la grabación de pantalla del celular (súbela en «🎛 Audio e imagen»).')
    print('Busco la pantalla del celular en tu grabación…', flush=True)
    datos = enderezar.analizar(orig)
    if a.desfase is None:
        ea, eb = envolvente(orig), envolvente(pant)
        desfase, pico, como = None, 0.0, ''
        if ea is not None and eb is not None:
            desfase, pico = correlacion(ea, eb, 100)
            como = 'por el audio'
        if desfase is None or pico < 8:
            print(f'· el audio no alcanzó para sincronizar (claridad {pico:.1f}); pruebo con la imagen', flush=True)
            d2, p2 = por_imagen(orig, pant, datos)
            if p2 > pico:
                desfase, pico, como = d2, p2, 'por la imagen'
        if desfase is None or pico < 6:
            raise SystemExit('ERROR: no pude sincronizar las dos grabaciones con seguridad. Escribe en «🎛 Audio e imagen» en qué '
                             'segundo de tu grabación empieza la grabación de pantalla y vuelve a pulsar.')
        print(f'· sincronizado {como}: la grabación de pantalla empieza en el segundo {desfase:.2f} de tu video (claridad {pico:.1f})', flush=True)
    else:
        desfase = a.desfase
    json.dump({'desfase': round(desfase, 3), 'pantalla': a.pantalla}, open(os.path.join(d, 'pantalla_celular.json'), 'w', encoding='utf-8'))
    componer_linea(orig, pant, desfase, datos, os.path.join(d, SALIDA))
    print(f'· listo {SALIDA}', flush=True)
    if not a.sin_insertos and os.path.exists(os.path.join(d, 'guion.json')):
        f = os.path.join(d, enderezar.INSERTOS)
        try:
            lista = json.load(open(f, encoding='utf-8'))
        except (OSError, ValueError):
            lista = []
        nuevos = elegir_insertos(d, desfase, duracion(pant))
        lista = [x for x in lista if x.get('origen') not in ('scrcpy', 'pantalla')] + nuevos  # la grabación nítida manda sobre la enderezada
        json.dump(lista, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'· {len(nuevos)} insertos con la pantalla grabada en {enderezar.INSERTOS}', flush=True)


if __name__ == '__main__':
    main()
