"""Flechas, círculos y recuadros animados sobre las partes importantes, en el momento en que la voz las nombra.

Cada señal se coloca en un punto del cuadro; si la cámara o la pieza se mueven, la señal
las sigue (seguimiento óptico con OpenCV). Si el objeto se pierde de vista, la señal se apaga
antes de tiempo en vez de quedar flotando en el lugar equivocado.

Uso:
  python3 senales.py --guion guion.json --voz voz_v4 --senales senales.json \
      --video entrada.mp4 --salida salida.mp4 [--desfase 0.3] [--prueba carpeta]

senales.json: [{"bloque": "L08", "frase": "450", "tipo": "circulo", "x": 1440, "y": 712, "r": 80,
                "dur": 3, "retraso": 0, "seguir": true, "texto": "450 °C", "foco": false}]
  t: segundo exacto del video (las señales de tus capturas); si está, no se busca la frase.
  hueco: en flechas, a cuántos píxeles del centro queda la punta (para no tapar lo señalado).
  x, y: centro en píxeles del video (1920x1080) en el instante en que arranca la señal.
  tipo: circulo | flecha | caja (caja usa "w" y "h"; flecha usa "angulo", de dónde viene).
  retraso: segundos después de la frase (cuando el objeto aparece un poco más tarde).
--prueba guarda un cuadro por señal con la marca dibujada, para revisar posiciones sin renderizar todo.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile
import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
import codificar  # noqa: E402  con la tarjeta NVIDIA si la hay, si no con el procesador
from etiquetas import buscar  # noqa: E402

FPS = 25


def seguir(video, t, x, y, n, radio):
    """Sigue el punto (x, y) durante n cuadros desde el segundo t. Devuelve posiciones y cuántos cuadros fueron fiables."""
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    if not ok:
        return [(x, y)] * n, n
    prev = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    mask = np.zeros_like(prev)
    rr = int(max(radio * 1.6, 60))
    cv2.circle(mask, (int(x), int(y)), rr, 255, -1)
    p0 = cv2.goodFeaturesToTrack(prev, 60, 0.01, 6, mask=mask)
    pos, fiables, cx, cy = [(x, y)], n, float(x), float(y)
    for k in range(1, n):
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        if p0 is None or len(p0) < 5:
            fiables = min(fiables, k); pos.append((cx, cy)); prev = g; continue
        p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, g, p0, None, winSize=(31, 31), maxLevel=4)
        bueno = st.reshape(-1) == 1
        if bueno.sum() < 5:
            fiables = min(fiables, k); pos.append((cx, cy)); prev = g; p0 = None; continue
        d = np.median((p1[bueno] - p0[bueno]).reshape(-1, 2), axis=0)
        cx, cy = cx + float(d[0]), cy + float(d[1])
        if not (0 <= cx < g.shape[1] and 0 <= cy < g.shape[0]):
            fiables = min(fiables, k)
        pos.append((cx, cy))
        p0 = p1[bueno].reshape(-1, 1, 2)
        if k % 10 == 0:  # renueva puntos alrededor de la posición actual
            mask[:] = 0; cv2.circle(mask, (int(cx), int(cy)), rr, 255, -1)
            nuevo = cv2.goodFeaturesToTrack(g, 60, 0.01, 6, mask=mask)
            if nuevo is not None and len(nuevo) >= 5:
                p0 = nuevo.astype(np.float32)
        prev = g
    while len(pos) < n:
        pos.append(pos[-1])
    # suavizado para que no tiemble
    a = np.array(pos)
    k = 5
    a = np.vstack([np.convolve(np.pad(a[:, i], (k // 2, k // 2), mode='edge'), np.ones(k) / k, mode='valid') for i in range(2)]).T
    return [(round(float(p[0]), 1), round(float(p[1]), 1)) for p in a], fiables


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--guion', required=True)
    ap.add_argument('--voz', required=True)
    ap.add_argument('--senales', required=True)
    ap.add_argument('--video', required=True)
    ap.add_argument('--salida')
    ap.add_argument('--desfase', type=float, default=0.3)
    ap.add_argument('--prueba')
    a = ap.parse_args()

    inicio = {b['id']: b['inicio_min'] for b in json.load(open(a.guion, encoding='utf-8'))['bloques']}
    tmp = tempfile.mkdtemp(prefix='senales_')
    trabajos, colocadas = [], []
    for k, s in enumerate(json.load(open(a.senales, encoding='utf-8')), 1):
        s.setdefault('frase', s.get('texto') or 'tu captura')
        if s.get('t') is not None:  # las de tus capturas ya traen el segundo del video
            t = round(float(s['t']) + s.get('retraso', 0), 2)
        elif s.get('en') is not None and s.get('bloque') in inicio:  # puesta a mano en el editor por pistas: desde que empieza su bloque
            t = round(inicio[s['bloque']] + a.desfase + float(s['en']) + s.get('retraso', 0), 2)
        else:
            al = json.load(open(os.path.join(a.voz, s['bloque'] + '.align.json'), encoding='utf-8'))
            t = buscar(al, s['frase'])
            if t is None:
                print(f"AVISO: no encontré «{s['frase']}» en {s['bloque']}, la salto"); continue
            t = round(inicio[s['bloque']] + a.desfase + t + s.get('retraso', 0), 2)
        n = int(round(s.get('dur', 3) * FPS))
        radio = s.get('r', max(s.get('w', 160), s.get('h', 80)) / 2)
        if s.get('seguir', True):
            pts, fiables = seguir(a.video, t, s['x'], s['y'], n, radio)
            if fiables < n:  # se perdió: la señal dura solo lo fiable (mínimo 1 s)
                n = max(fiables, FPS); pts = pts[:n]
        else:
            pts = [(s['x'], s['y'])] * n
        props = {k2: s[k2] for k2 in ('tipo', 'r', 'w', 'h', 'color', 'texto', 'foco', 'angulo', 'hueco') if k2 in s}
        props['puntos'] = pts
        salida = os.path.join(tmp, f's{k:02d}.mov')
        trabajos.append({'id': 'Senal', 'props': props, 'salida': salida, 'alfa': True})
        colocadas.append({'t': t, 'archivo': salida, 'frase': s['frase'], 'dur': round(n / FPS, 2), 'tipo': s['tipo']})
        print(f"{t:7.2f}s  {s['tipo']:8s} {s['frase']}  ({n / FPS:.1f}s)")
        if a.prueba:
            os.makedirs(a.prueba, exist_ok=True)
            mitad = min(len(pts) - 1, int(0.6 * FPS))
            cap = cv2.VideoCapture(a.video); cap.set(cv2.CAP_PROP_POS_MSEC, (t + mitad / FPS) * 1000); _, f = cap.read()
            x, y = map(int, pts[mitad])
            cv2.circle(f, (x, y), int(radio), (63, 210, 255), 6)
            cv2.imwrite(os.path.join(a.prueba, f"{k:02d}_{s.get('bloque') or 'tuya'}.jpg"), cv2.resize(f, (960, 540)))

    if a.prueba and not a.salida:
        return
    json.dump(trabajos, open(os.path.join(tmp, 'trabajos.json'), 'w', encoding='utf-8'))
    env = dict(os.environ)
    chrome = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell'
    if os.path.exists(chrome):
        env.setdefault('REMOTION_CHROME', chrome)
    subprocess.run(['node', 'render_lote.mjs', os.path.join(tmp, 'trabajos.json')], cwd=os.path.join(RAIZ, 'remotion'), env=env, check=True)

    ins, filtros, ultimo = ['-i', a.video], [], '0:v'
    for k, c in enumerate(colocadas, 1):
        ins += ['-i', c['archivo']]
        filtros.append(f"[{k}:v]setpts=PTS+{c['t']}/TB[s{k}];[{ultimo}][s{k}]overlay=0:0:eof_action=pass[v{k}]")
        ultimo = f'v{k}'
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins +
                   ['-filter_complex', ';'.join(filtros), '-map', f'[{ultimo}]', '-map', '0:a?',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'copy', a.salida], check=True)
    shutil.rmtree(tmp)
    json.dump([{k: v for k, v in c.items() if k != 'archivo'} for c in colocadas],
              open(os.path.splitext(a.salida)[0] + '.senales_tiempos.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
