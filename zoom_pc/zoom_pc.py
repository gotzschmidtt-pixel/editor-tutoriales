"""«🖱 Zoom automático en la PC»: en una grabación de pantalla, la imagen se acerca sola donde haces clic (como Screen Studio).

Así las ventanas del programa (Unlock Tool, 3uTools…) se leen sin pegarse a la pantalla. Gratis, en tu PC (OpenCV):
  1. Mira la grabación 10 veces por segundo. Lo chico que se mueve es el puntero; un cambio de pantalla en una zona (un
     botón que se aprieta, una ventana que se abre, un texto que aparece) cerca del puntero es un clic.
  2. En cada clic acerca la imagen a esa zona (hasta ×2,2, que entre entera la ventana o el botón), la mantiene unos
     segundos mientras sigan pasando cosas cerca y vuelve a la vista completa con un movimiento suave. Si cambia toda la
     pantalla, vuelve a la vista completa.
  3. Arma el video nuevo con el mismo audio y la misma duración (deja zoom_pc.json con cada acercamiento y su porqué).

Uso: python zoom_pc.py --entrada material.mp4 [--salida material_zoom.mp4] [--max 2.2] [--prueba carpeta]
Sin --salida reemplaza el archivo y deja el de antes como NOMBRE_sin_zoom.mp4.
"""
import argparse, json, os, subprocess
import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS_ANALISIS = 10
ANCHO_ANALISIS = 640
MANTENER = 2.6      # segundos que se queda cerca después del último cambio en esa zona
ANTES = 0.35        # empieza a acercarse un poco antes del clic
MOVER = 0.7         # segundos que tarda en acercarse, alejarse o pasar de una zona a otra
SIN_ZOOM = 0.30     # si cambia más que esto de la pantalla, es otra pantalla: vista completa


def probar(f):
    r = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                   'stream=width,height,r_frame_rate:format=duration', '-of', 'json', f],
                                  capture_output=True, text=True, check=True).stdout)
    s = r['streams'][0]
    n, d = s['r_frame_rate'].split('/')
    return int(s['width']), int(s['height']), float(n) / float(d or 1), float(r['format']['duration'])


def cuadros(f, ancho, alto, fps=None, gris=False):
    vf = (f'fps={fps},' if fps else '') + f'scale={ancho}:{alto}' + (',format=gray' if gris else '')
    p = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-i', f, '-vf', vf, '-f', 'rawvideo',
                          '-pix_fmt', 'gray' if gris else 'bgr24', '-'], stdout=subprocess.PIPE)
    tam = ancho * alto * (1 if gris else 3)
    while True:
        b = p.stdout.read(tam)
        if len(b) < tam:
            break
        yield np.frombuffer(b, np.uint8).reshape(alto, ancho) if gris else np.frombuffer(b, np.uint8).reshape(alto, ancho, 3)
    p.wait()


def puntero_amarillo(c):
    """El puntero con halo amarillo (como lo graba el autor): el centro del círculo amarillo, o None."""
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (18, 90, 170), (38, 255, 255))
    n, _, st, cen = cv2.connectedComponentsWithStats(m)
    redondos = [cen[k] for k in range(1, n) if 20 <= st[k][cv2.CC_STAT_AREA] <= 900
                and 0.6 <= st[k][cv2.CC_STAT_WIDTH] / max(1, st[k][cv2.CC_STAT_HEIGHT]) <= 1.6]
    return np.array(redondos[0]) if len(redondos) == 1 else None


def desplazamiento(a, b):
    """Cuánto se corrió la imagen entre dos cuadros (px) y qué tan seguro: un scroll no es un clic."""
    (dx, dy), conf = cv2.phaseCorrelate(a.astype(np.float32), b.astype(np.float32))
    return abs(dx) + abs(dy), conf


def eventos(f, W, H):
    """[(t, x0, y0, x1, y1, que, px, py)] en fracciones de la pantalla: lo que cambió en cada momento cerca del puntero
    (px, py: dónde estaba el puntero, o None)."""
    aw = ANCHO_ANALISIS
    ah = int(round(H * aw / W / 2)) * 2
    area = aw * ah
    previo, puntero, out = None, None, []
    nucleo = np.ones((5, 5), np.uint8)
    for i, c in enumerate(cuadros(f, aw, ah, FPS_ANALISIS)):
        t = i / FPS_ANALISIS
        g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
        amarillo = puntero_amarillo(c)
        if previo is not None:
            dif = cv2.absdiff(g, previo)
            _, m = cv2.threshold(dif, 22, 255, cv2.THRESH_BINARY)
            frac = m.mean() / 255
            if frac > 0.04:
                corrido, conf = desplazamiento(previo, g)
                if corrido > 2 and conf > 0.25:  # scroll de la página: la vista completa, sin acercar
                    out.append((t, 0, 0, 1, 1, 'pantalla', None, None))
                    previo, puntero = g, amarillo if amarillo is not None else puntero
                    continue
            if frac > SIN_ZOOM:
                out.append((t, 0, 0, 1, 1, 'pantalla', None, None))
            elif frac > 0.0004:
                m = cv2.dilate(m, nucleo, iterations=3)
                n, _, st, cen = cv2.connectedComponentsWithStats(m)
                zonas = [(st[k], cen[k]) for k in range(1, n)]
                chicas = [z for z in zonas if z[0][cv2.CC_STAT_AREA] < area * 0.004]
                grandes = [z for z in zonas if z[0][cv2.CC_STAT_AREA] >= area * 0.004]
                if amarillo is not None:
                    puntero = amarillo
                elif chicas:  # el puntero: la zona chica que se movió (la más cercana a donde estaba)
                    puntero = np.array(min(chicas, key=lambda z: 0 if puntero is None else np.hypot(*(z[1] - puntero)))[1])
                for st_k, c_k in grandes:
                    x, y, w, h = st_k[0], st_k[1], st_k[2], st_k[3]
                    if puntero is not None and amarillo is not None and np.hypot(*(c_k - puntero)) < 30 and w * h < area * 0.02:
                        continue  # es el halo del puntero que se movió, no un cambio de pantalla
                    cerca = puntero is None or (x - 40 <= puntero[0] <= x + w + 40 and y - 40 <= puntero[1] <= y + h + 40) \
                        or np.hypot(*(c_k - puntero)) < aw * 0.18
                    if cerca:
                        px, py = (puntero[0] / aw, puntero[1] / ah) if puntero is not None else (None, None)
                        out.append((t, x / aw, y / ah, (x + w) / aw, (y + h) / ah, 'clic' if puntero is not None else 'cambio', px, py))
        elif amarillo is not None:
            puntero = amarillo
        previo = g
    return out


def plan(evs, dur, maximo):
    """Tramos de zoom: [{'ini', 'fin', 'cx', 'cy', 'z', 'por_que'}], sin solaparse."""
    tramos = []
    for t, x0, y0, x1, y1, que, px, py in evs:
        if que == 'pantalla':
            if tramos and tramos[-1]['fin'] > t:
                tramos[-1]['fin'] = max(tramos[-1]['ini'] + 0.5, t)
            continue
        w, h = max(x1 - x0, 0.05), max(y1 - y0, 0.05)
        z = float(np.clip(min(1 / (w * 1.5), 1 / (h * 1.5)), 1.0, maximo))
        if z < 1.15:
            continue  # la zona ya es casi toda la pantalla: no vale la pena acercar
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if px is not None:  # lo que cambió, sin dejar afuera el puntero (es donde mira el que sigue el tutorial)
            cx, cy = min(max(cx, px - 0.35 / z), px + 0.35 / z), min(max(cy, py - 0.35 / z), py + 0.35 / z)
        u = tramos[-1] if tramos else None
        if u and t - ANTES <= u['fin'] and abs(cx - u['cx']) < 0.5 / u['z'] and abs(cy - u['cy']) < 0.5 / u['z']:
            u['fin'] = max(u['fin'], t + MANTENER)  # sigue pasando algo en la misma zona: se queda
            continue
        ini = max(0.0, t - ANTES)
        if u and ini < u['fin']:
            u['fin'] = ini  # la zona nueva manda: pasa de una a otra
        tramos.append({'ini': round(ini, 2), 'fin': round(min(dur, t + MANTENER), 2), 'cx': round(cx, 3), 'cy': round(cy, 3),
                       'z': round(z, 2), 'por_que': f'{que} en {int(t // 60)}:{t % 60:04.1f}'})
    return [x for x in tramos if x['fin'] - x['ini'] >= 0.8]


def suave(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def encuadre(tramos, t):
    """(cx, cy, z) en el segundo t, con entradas y salidas suaves."""
    vista = (0.5, 0.5, 1.0)
    for k, x in enumerate(tramos):
        if t < x['ini'] - MOVER or t > x['fin'] + MOVER:
            continue
        obj = (x['cx'], x['cy'], x['z'])
        anterior = tramos[k - 1] if k and abs(tramos[k - 1]['fin'] - x['ini']) < 0.05 else None
        if t < x['ini']:
            return vista if anterior else _mezcla(vista, obj, suave((t - (x['ini'] - MOVER)) / MOVER))
        if t <= x['fin']:
            if anterior and t < x['ini'] + MOVER:
                return _mezcla((anterior['cx'], anterior['cy'], anterior['z']), obj, suave((t - x['ini']) / MOVER))
            return obj
        siguiente = tramos[k + 1] if k + 1 < len(tramos) and abs(tramos[k + 1]['ini'] - x['fin']) < 0.05 else None
        if siguiente:
            continue
        return _mezcla(obj, vista, suave((t - x['fin']) / MOVER))
    return vista


def _mezcla(a, b, f):
    return tuple(a[i] + (b[i] - a[i]) * f for i in range(3))


def recorte(W, H, cx, cy, z):
    w, h = W / z, H / z
    x = min(max(cx * W - w / 2, 0), W - w)
    y = min(max(cy * H - h / 2, 0), H - h)
    return x, y, w, h


def aplicar(cuadro, W, H, cx, cy, z):
    if z <= 1.001:
        return cuadro
    x, y, w, h = recorte(W, H, cx, cy, z)
    # warpAffine con subpíxeles: el zoom no tiembla de a 1 píxel como un crop entero
    M = np.float32([[W / w, 0, -x * W / w], [0, H / h, -y * H / h]])
    return cv2.warpAffine(cuadro, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def armar(entrada, salida, tramos, W, H, fps):
    W2, H2 = W // 2 * 2, H // 2 * 2
    p = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W2}x{H2}',
                          '-r', f'{fps:.5f}', '-i', '-', '-i', entrada, '-map', '0:v', '-map', '1:a?', '-c:a', 'copy',
                          '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-shortest', salida],
                         stdin=subprocess.PIPE)
    for i, c in enumerate(cuadros(entrada, W2, H2)):
        p.stdin.write(aplicar(c, W2, H2, *encuadre(tramos, i / fps)).tobytes())
        if i % int(fps * 30) == 0:
            print(f'· [{int(i / fps // 60)}:{int(i / fps % 60):02d}] armando…', flush=True)
    p.stdin.close()
    if p.wait():
        raise SystemExit('ERROR: no se pudo armar el video con zoom (mira el registro).')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entrada', required=True)
    ap.add_argument('--salida')
    ap.add_argument('--max', type=float, default=2.2, help='lo más que se acerca')
    ap.add_argument('--prueba', help='carpeta: un cuadro por acercamiento, con el recorte marcado (no arma el video)')
    ap.add_argument('--deshacer', action='store_true')
    a = ap.parse_args()
    base, ext = os.path.splitext(a.entrada)
    previo = base + '_sin_zoom' + ext
    if a.deshacer:
        if os.path.exists(previo):
            os.replace(previo, a.entrada)
            print('· puse de nuevo la grabación sin zoom', flush=True)
        return
    fuente = previo if not a.salida and os.path.exists(previo) else a.entrada  # nunca un zoom sobre otro zoom
    W, H, fps, dur = probar(fuente)
    print(f'Busco los clics en {os.path.basename(fuente)} ({dur / 60:.1f} min)…', flush=True)
    tramos = plan(eventos(fuente, W, H), dur, a.max)
    print(f'{len(tramos)} acercamientos:', flush=True)
    for x in tramos:
        print(f"· {x['por_que']}: ×{x['z']} en ({x['cx']:.2f}, {x['cy']:.2f}) hasta {x['fin']:.1f} s", flush=True)
    json.dump({'fuente': os.path.basename(fuente), 'tramos': tramos}, open(os.path.join(os.path.dirname(os.path.abspath(a.entrada)), 'zoom_pc.json'), 'w',
              encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.prueba:
        os.makedirs(a.prueba, exist_ok=True)
        cap = cv2.VideoCapture(fuente)
        for k, x in enumerate(tramos, 1):
            cap.set(cv2.CAP_PROP_POS_MSEC, (x['ini'] + 0.8) * 1000)
            ok, c = cap.read()
            if ok:
                rx, ry, rw, rh = recorte(W, H, x['cx'], x['cy'], x['z'])
                cv2.rectangle(c, (int(rx), int(ry)), (int(rx + rw), int(ry + rh)), (214, 43, 255), 4)
                cv2.imwrite(os.path.join(a.prueba, f'zoom_{k:02d}.jpg'), c)
        return
    if not tramos:
        print('· no encontré clics para acercar: el video queda como está', flush=True)
        return
    destino = a.salida or base + '.zoom' + ext
    armar(fuente, destino, tramos, W, H, fps)
    if not a.salida:
        if not os.path.exists(previo):
            os.replace(a.entrada, previo)
        os.replace(destino, a.entrada)
    print(f'Listo: {a.salida or a.entrada} (el de antes quedó como {os.path.basename(previo)})' if not a.salida else f'Listo: {a.salida}', flush=True)


if __name__ == '__main__':
    main()
