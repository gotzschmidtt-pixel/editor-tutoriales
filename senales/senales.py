"""Flechas, círculos y recuadros animados sobre las partes importantes, en el momento en que la voz las nombra.

Cada señal se coloca en un punto del cuadro; si la cámara o la pieza se mueven, la señal
las sigue (seguimiento óptico con OpenCV). Si está sobre un teléfono, una laptop o un monitor, además queda
pegada a ese objeto (deteccion/): aunque cambie lo que muestra su pantalla, vuelve a su mismo lugar del objeto.
Si el objeto se pierde de vista, la señal se apaga antes de tiempo en vez de quedar flotando en el lugar equivocado.

Uso:
  python3 senales.py --guion guion.json --voz voz_v4 --senales senales.json \
      --video entrada.mp4 --salida salida.mp4 [--desfase 0.3] [--prueba carpeta]

senales.json: [{"bloque": "L08", "frase": "450", "tipo": "circulo", "x": 1440, "y": 712, "r": 80,
                "dur": 3, "retraso": 0, "seguir": true, "texto": "450 °C", "foco": false}]
  t: segundo exacto del video YA MONTADO (las señales de tus capturas); si está, no se busca la frase.
  src_t: segundo de la GRABACIÓN ORIGINAL (las que propone la IA mirando original.mp4): se pasa al segundo del video
         montado con los tramos del guion y se afina buscando el cuadro igual (x, y son del original).
  hueco: en flechas, a cuántos píxeles del centro queda la punta (para no tapar lo señalado).
  x, y: centro en píxeles del video (1920x1080) en el instante en que arranca la señal.
  tipo: circulo | flecha | caja (caja usa "w" y "h"; flecha usa "angulo", de dónde viene).
  retraso: segundos después de la frase (cuando el objeto aparece un poco más tarde).
--prueba guarda un cuadro por señal con la marca dibujada, para revisar posiciones sin renderizar todo.
"""
import argparse, json, os, shutil, subprocess, sys
import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
import codificar  # noqa: E402  con la tarjeta NVIDIA si la hay, si no con el procesador
from etiquetas import buscar  # noqa: E402
sys.path.insert(0, os.path.join(RAIZ, 'capas'))
import capas  # noqa: E402  con --capa: se pega junto con etiquetas y tarjetas en una sola pasada
sys.path.insert(0, os.path.join(RAIZ, 'deteccion'))
import deteccion  # noqa: E402  el teléfono, la laptop o el monitor que hay debajo de la señal

FPS = 25
MIRAR_CADA = 5   # cada cuántos cuadros de la señal se vuelve a buscar el objeto de debajo (0,2 s)
SIN_VER = 15     # si el objeto no se ve por más de esto (0,6 s), ya no se usa para corregir
CORTE = 30       # diferencia media entre dos cuadros (achicados, 0 a 255) desde la que es otra toma: la señal termina ahí


def seguir(video, t, x, y, n, radio):
    """Sigue el punto (x, y) durante n cuadros desde el segundo t. Devuelve posiciones y cuántos cuadros fueron fiables.

    Si el punto cae sobre un teléfono, una laptop o un monitor, se busca ese objeto cada 0,2 s: cuando el seguimiento
    óptico se pierde (un dedo tapa el botón) o se va con lo que cambia en la pantalla (otra pantalla, un desplazamiento),
    la señal vuelve al mismo lugar del objeto en vez de apagarse o quedar flotando."""
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    if not ok:
        return [(x, y)] * n, n
    prev = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    mask = np.zeros_like(prev)
    rr = int(max(radio * 1.6, 60))

    def puntos_en(g, px, py):
        mask[:] = 0; cv2.circle(mask, (int(px), int(py)), rr, 255, -1)
        return cv2.goodFeaturesToTrack(g, 60, 0.01, 6, mask=mask)

    p0 = puntos_en(prev, x, y)
    objeto, rescates = deteccion.debajo(deteccion.objetos(f), x, y), []
    if objeto:  # dónde queda el punto dentro del objeto (0 a 1), para volver ahí si el seguimiento se pierde
        caja, visto, cajas = objeto['caja'], 0, {0: objeto['caja']}
        rel = ((x - caja[0]) / caja[2], (y - caja[1]) / caja[3])
    pos, fiables, cx, cy = [(x, y)], n, float(x), float(y)
    vf, leidos = cap.get(cv2.CAP_PROP_FPS) or FPS, 0  # el video armado puede ir a 30 cuadros por segundo; la señal, a FPS
    for k in range(1, n):
        ok = True
        while ok and leidos < int(round(k * vf / FPS)):  # el cuadro del video que cae en el mismo momento que el de la señal
            ok, f = cap.read()
            leidos += 1
        if not ok:
            break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        if cv2.absdiff(cv2.resize(prev, (64, 36)), cv2.resize(g, (64, 36))).mean() > CORTE:
            fiables = min(fiables, k)  # cambió la toma: lo señalado ya no está ahí, la señal termina en el corte
            break
        perdido = p0 is None or len(p0) < 5
        if not perdido:
            p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, g, p0, None, winSize=(31, 31), maxLevel=4)
            bueno = st.reshape(-1) == 1
            if bueno.sum() < 5:
                perdido, p0 = True, None
            else:
                d = np.median((p1[bueno] - p0[bueno]).reshape(-1, 2), axis=0)
                cx, cy = cx + float(d[0]), cy + float(d[1])
                p0 = p1[bueno].reshape(-1, 1, 2)
                if k % 10 == 0:  # renueva puntos alrededor de la posición actual
                    nuevo = puntos_en(g, cx, cy)
                    if nuevo is not None and len(nuevo) >= 5:
                        p0 = nuevo.astype(np.float32)
        if objeto:
            if k % MIRAR_CADA == 0:
                nueva = deteccion.mismo(deteccion.objetos(f), objeto['que'], caja)
                if nueva:
                    caja, visto, cajas[k] = nueva, k, nueva
            ax, ay = caja[0] + rel[0] * caja[2], caja[1] + rel[1] * caja[3]
            lejos = ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5 > 0.12 * min(caja[2], caja[3])
            if k - visto <= SIN_VER and (perdido or lejos):  # vuelve a su lugar del objeto y sigue desde ahí
                cx, cy, perdido = ax, ay, False
                rescates.append(k)
                nuevo = puntos_en(g, cx, cy)
                p0 = nuevo.astype(np.float32) if nuevo is not None and len(nuevo) >= 5 else None
        if perdido or not (0 <= cx < g.shape[1] and 0 <= cy < g.shape[0]):
            fiables = min(fiables, k)
        pos.append((cx, cy))
        prev = g
    if rescates:  # lo rescatado, con el objeto en su lugar de ese momento (entre una búsqueda y la siguiente)
        vistas = sorted(cajas)
        for k in rescates:
            a = max([v for v in vistas if v <= k], default=vistas[0])
            b = min([v for v in vistas if v >= k], default=a)
            u = 0 if b == a or b - k > SIN_VER else (k - a) / (b - a)
            c = [cajas[a][i] + (cajas[b][i] - cajas[a][i]) * u for i in range(4)]
            pos[k] = (c[0] + rel[0] * c[2], c[1] + rel[1] * c[3])
    while len(pos) < n:
        pos.append(pos[-1])
    # suavizado para que no tiemble
    a = np.array(pos)
    k = 5
    a = np.vstack([np.convolve(np.pad(a[:, i], (k // 2, k // 2), mode='edge'), np.ones(k) / k, mode='valid') for i in range(2)]).T
    return [(round(float(p[0]), 1), round(float(p[1]), 1)) for p in a], fiables


def segundo_montado(bloques, src):
    """El segundo del video montado donde se ve el segundo `src` de la grabación (None si ningún tramo lo muestra)."""
    for b in bloques:
        mo = b.get('montaje') or {}
        a, z = mo.get('src_inicio'), mo.get('src_fin')
        if a is None or z is None or not str(mo.get('modo', 'lento')).startswith('lento') or not a - 0.05 <= src <= z + 0.05:
            continue
        return b['inicio_min'] + (src - a) / float(mo.get('velocidad') or 1)
    return None


def afinar(original, video, src, t, margen=1.5):
    """Busca cerca de t el cuadro del video montado más parecido al de la grabación en src (por si el tramo se corrió)."""
    def gris(cap, s):
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0, s) * 1000)
        ok, f = cap.read()
        if not ok:
            return None
        g = cv2.cvtColor(cv2.resize(f, (160, 90)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        return (g - g.mean()) / (g.std() + 1e-6)
    co, cv_ = cv2.VideoCapture(original), cv2.VideoCapture(video)
    ref = gris(co, src)
    if ref is None:
        return t, 0.0
    mejor, parecido = t, -1.0
    ini = max(0.0, t - margen)
    cv_.set(cv2.CAP_PROP_POS_MSEC, ini * 1000)  # se lee de corrido (saltar a cada cuadro es lentísimo en h264)
    fps = cv_.get(cv2.CAP_PROP_FPS) or 30
    cada = max(1, int(round(fps / 10)))
    for k in range(int(2 * margen * fps) + 1):
        ok, f = cv_.read()
        if not ok:
            break
        if k % cada:
            continue
        g = cv2.cvtColor(cv2.resize(f, (160, 90)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        g = (g - g.mean()) / (g.std() + 1e-6)
        p = float((g * ref).mean())
        if p > parecido:
            mejor, parecido = ini + k / fps, p
    return round(mejor, 2), parecido


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--guion', required=True)
    ap.add_argument('--voz', required=True)
    ap.add_argument('--senales', required=True)
    ap.add_argument('--video', required=True)
    ap.add_argument('--salida')
    ap.add_argument('--desfase', type=float, default=0.3)
    ap.add_argument('--prueba')
    ap.add_argument('--capa', help='solo dibuja y deja la capa en este .json; capas/capas.py la pega junto con las demás')
    a = ap.parse_args()

    bloques = json.load(open(a.guion, encoding='utf-8'))['bloques']
    inicio = {b['id']: b['inicio_min'] for b in bloques}
    texto_original = {b['id']: b.get('texto_original') for b in bloques}  # versión traducida: el texto en español de cada bloque
    original = os.path.join(os.path.dirname(os.path.abspath(a.guion)), 'original.mp4')
    tmp = codificar.temporal('senales')
    trabajos, colocadas = [], []
    for k, s in enumerate(json.load(open(a.senales, encoding='utf-8')), 1):
        s.setdefault('frase', s.get('texto') or 'tu captura')
        if s.get('src_t') is not None:  # segundo de la grabación: se pasa al del video montado y se busca el cuadro igual
            t0 = segundo_montado(bloques, float(s['src_t']))
            if t0 is None:
                print(f"AVISO: el segundo {s['src_t']} de tu grabación no sale en el video (ese tramo se recortó); salto «{s['frase']}»"); continue
            t, parecido = afinar(original, a.video, float(s['src_t']), t0) if os.path.exists(original) else (round(t0, 2), 1.0)
            if parecido < 0.6:  # no se encontró la misma imagen: mejor no poner un círculo en el lugar equivocado
                print(f"AVISO: no encontré en el video la imagen de «{s['frase']}» (parecido {parecido:.2f}); la salto"); continue
            t = round(t + s.get('retraso', 0), 2)
        elif s.get('t') is not None:  # las de tus capturas ya traen el segundo del video
            t = round(float(s['t']) + s.get('retraso', 0), 2)
        elif s.get('en') is not None and s.get('bloque') in inicio:  # puesta a mano en el editor por pistas: desde que empieza su bloque
            t = round(inicio[s['bloque']] + a.desfase + float(s['en']) + s.get('retraso', 0), 2)
        else:
            f_al = os.path.join(a.voz, str(s.get('bloque')) + '.align.json')
            if s.get('bloque') not in inicio or not os.path.exists(f_al):  # una señal vieja no frena las demás
                print(f"AVISO: el bloque {s.get('bloque')} ya no está en el guion, salto «{s['frase']}»"); continue
            al = json.load(open(f_al, encoding='utf-8'))
            t = buscar(al, s['frase'], texto_original.get(s['bloque']))
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
    env = codificar.env_temporal(os.environ, os.path.join(tmp, 'node_tmp'))
    chrome = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell'
    if os.path.exists(chrome):
        env.setdefault('REMOTION_CHROME', chrome)
    if trabajos:
        r = subprocess.run(['node', 'render_lote.mjs', os.path.join(tmp, 'trabajos.json')], cwd=os.path.join(RAIZ, 'remotion'), env=env,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        print((r.stdout or '') + (r.stderr or ''), flush=True)
        if r.returncode != 0:  # se muestra lo que dijo Remotion, no solo «returned non-zero exit status 1»
            detalle = ' '.join((r.stderr or r.stdout or '').split())[-600:]
            if 'cannot find' in detalle.lower() or 'err_module_not_found' in detalle.lower():
                detalle += ' → Faltan las piezas de Remotion: corre instalar.bat (o «npm install» dentro de la carpeta remotion).'
            raise SystemExit(f'ERROR: Remotion no pudo dibujar las flechas y círculos: {detalle}')
    tiempos = os.path.splitext(a.salida)[0] + '.senales_tiempos.json'
    if a.capa:  # se pega después junto con etiquetas y tarjetas: una sola codificación
        capas.guardar(a.capa, [{'args': ['-i', c['archivo']], 'pre': f"setpts=PTS+{c['t']}/TB", 'overlay': '0:0:eof_action=pass'}
                               for c in colocadas], borrar=tmp, crf=20)
        json.dump([{k: v for k, v in c.items() if k != 'archivo'} for c in colocadas], open(tiempos, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return

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
              open(tiempos, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
