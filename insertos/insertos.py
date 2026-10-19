"""Insertos: usa material extra (grabación de pantalla, fotos, otro video) como cortes, zooms y
reemplazo de pausas congeladas, sin cambiar la duración del video.

Cada inserto tapa la imagen del video entre dos momentos de la voz y muestra un cuadro quieto del
material con un movimiento de cámara suave (paneo y zoom por claves). El audio no se toca.
El cuadro se elige con el módulo nitidez: el más quieto y nítido cerca del segundo pedido.

Uso:
  python3 insertos.py --guion guion.json --voz voz_v4 --insertos insertos.json \
      --video sin_voz.mp4 --salida con_insertos.mp4 [--desfase 0.3] [--prueba carpeta]

insertos.json: [{"material": "pantalla.mp4", "src_t": 2.6,
                 "bloque": "L15", "frase": "Descargar Files", "hasta": "Elige", "extra": 1.0,
                 "claves": [{"t": 0, "cx": 0.67, "cy": 0.39, "w": 0.45},
                            {"frase": "la Pico 2", "cx": 0.55, "cy": 0.63, "w": 0.30}]}]
  Inicio: "frase" del "bloque" (o "t" absoluto en segundos). Fin: "hasta" (frase) + "extra", o "dur".
  "exacto": true usa src_t tal cual (si el material se desplaza y el cuadro vecino muestra otra cosa).
  claves: encuadre en fracciones del material (centro cx, cy y ancho w; el alto sale de 16:9).
  Cada clave va en "t" (segundos desde el inicio del inserto) o en el momento de una "frase".
"""
import argparse, json, os, shutil, subprocess, sys, tempfile
import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
sys.path.insert(0, os.path.join(RAIZ, 'nitidez'))
from etiquetas import buscar  # noqa: E402
from nitidez import analizar, mejor  # noqa: E402

FPS, W, H = 25, 1920, 1080
FUNDIDO = 0.25


def suave(x):
    return x * x * (3 - 2 * x)


def encuadre(claves, t):
    """Encuadre en el segundo t: se queda en cada clave y, al llegar la siguiente, se mueve hacia ella en 1.2 s."""
    k = max(i for i, c in enumerate(claves) if c['t'] <= t) if t >= claves[0]['t'] else 0
    c = claves[k]
    if k == 0 or t - c['t'] >= 1.2:
        return c['cx'], c['cy'], c['w']
    a, x = claves[k - 1], suave((t - c['t']) / 1.2)
    return tuple(a[q] + (c[q] - a[q]) * x for q in ('cx', 'cy', 'w'))


def render_inserto(cuadro, claves, n, salida):
    h0, w0 = cuadro.shape[:2]
    proc = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
                             '-r', str(FPS), '-i', '-', '-vf', f'fade=in:st=0:d={FUNDIDO}:alpha=1,fade=out:st={n / FPS - FUNDIDO}:d={FUNDIDO}:alpha=1',
                             '-c:v', 'qtrle', '-pix_fmt', 'argb', salida], stdin=subprocess.PIPE)
    deriva = 0.0
    for i in range(n):
        cx, cy, w = encuadre(claves, i / FPS)
        w = w * (1 - 0.03 * i / n)  # empuje lento constante, para que nunca se vea congelado
        pw = w * w0
        ph = pw * 9 / 16
        x0 = min(max(cx * w0 - pw / 2, 0), w0 - pw)
        y0 = min(max(cy * h0 - ph / 2, 0), h0 - ph)
        M = np.float32([[W / pw, 0, -x0 * W / pw], [0, H / ph, -y0 * H / ph]])
        proc.stdin.write(cv2.warpAffine(cuadro, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE).tobytes())
    proc.stdin.close()
    proc.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--guion', required=True)
    ap.add_argument('--voz', required=True)
    ap.add_argument('--insertos', required=True)
    ap.add_argument('--video', required=True)
    ap.add_argument('--salida')
    ap.add_argument('--desfase', type=float, default=0.3)
    ap.add_argument('--prueba')
    a = ap.parse_args()

    inicio = {b['id']: b['inicio_min'] for b in json.load(open(a.guion))['bloques']}
    alin = {}

    def momento(bloque, frase):
        if bloque not in alin:
            alin[bloque] = json.load(open(os.path.join(a.voz, bloque + '.align.json')))
        t = buscar(alin[bloque], frase)
        if t is None:
            raise SystemExit(f"no encontré «{frase}» en {bloque}")
        return round(inicio[bloque] + a.desfase + t, 2)

    tmp = tempfile.mkdtemp(prefix='insertos_')
    analisis, colocados = {}, []
    for k, s in enumerate(json.load(open(a.insertos)), 1):
        t0 = s['t'] if 't' in s else momento(s['bloque'], s['frase'])
        t1 = momento(s['bloque'], s['hasta']) + s.get('extra', 0) if 'hasta' in s else t0 + s['dur']
        n = int(round((t1 - t0) * FPS))
        mat = s['material']
        if mat not in analisis:
            analisis[mat] = analizar(mat, os.path.join(tmp, f'm{len(analisis)}.npz'))
        ts = s['src_t'] if s.get('exacto') else mejor(*analisis[mat], s['src_t'] - 0.4, s['src_t'] + 0.4)
        cap = cv2.VideoCapture(mat); cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000); _, cuadro = cap.read()
        claves = []
        for c in s['claves']:
            rel = c['t'] if 't' in c else momento(s['bloque'], c['frase']) - t0
            claves.append({'t': max(0.0, rel), 'cx': c['cx'], 'cy': c['cy'], 'w': c['w']})
        claves.sort(key=lambda c: c['t'])
        print(f"{t0:7.2f}s → {t1:7.2f}s  material {ts:5.1f}s  {s.get('nota', '')}")
        if a.prueba:
            os.makedirs(a.prueba, exist_ok=True)
            for j, c in enumerate(claves):
                prueba = os.path.join(tmp, 'p.mov')
                render_inserto(cuadro, [c], 1 + int(FUNDIDO * FPS * 2), prueba)
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(FUNDIDO), '-i', prueba, '-frames:v', '1',
                                '-vf', 'scale=960:-1', os.path.join(a.prueba, f'{k:02d}_{j}.jpg')], check=True)
            continue
        salida = os.path.join(tmp, f'i{k:02d}.mov')
        render_inserto(cuadro, claves, n, salida)
        colocados.append({'t': t0, 'archivo': salida})

    if a.prueba:
        shutil.rmtree(tmp); return
    ins, filtros, ultimo = ['-i', a.video], [], '0:v'
    for k, c in enumerate(colocados, 1):
        ins += ['-i', c['archivo']]
        filtros.append(f"[{k}:v]setpts=PTS+{c['t']}/TB[i{k}];[{ultimo}][i{k}]overlay=0:0:eof_action=pass[v{k}]")
        ultimo = f'v{k}'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins +
                   ['-filter_complex', ';'.join(filtros), '-map', f'[{ultimo}]', '-map', '0:a?',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'copy', a.salida], check=True)
    shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
