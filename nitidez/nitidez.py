"""Elige cuadros quietos y nítidos para congelar, capturar o usar en el tráiler.

Lee el video a 5 cuadros por segundo en gris y mide en cada uno:
  - nitidez: varianza del Laplaciano (borroso = valor bajo)
  - movimiento: diferencia media con el cuadro anterior y el siguiente
Un cuadro sirve si el movimiento está bajo el percentil 40 del video y su nitidez es la
mejor de la ventana. Así nunca se congela una mano moviéndose ni una toma desenfocada.

Uso:
  python3 nitidez.py --video original.mp4 --ventana 30 36           # mejor segundo entre 30 y 36
  python3 nitidez.py --video original.mp4 --plan plan.json --salida mejores.json
     plan.json: {"L05": [30, 36], "L15": [150, 158]}  ->  mejores.json: {"L05": 33.2, ...}
  python3 nitidez.py --video original.mp4 --top 8 --separacion 6     # mejores momentos de todo el video
"""
import argparse, json, os, subprocess
import numpy as np

FPS, ANCHO, ALTO = 5, 480, 270
TROZO = 150  # cuadros que se miden a la vez: la memoria queda fija aunque la grabación dure media hora


def _firma(video):
    """Tamaño y fecha del video: si subes otra grabación con el mismo nombre, la caché vieja no sirve."""
    try:
        s = os.stat(video)
        return np.array([s.st_size, s.st_mtime], np.float64)
    except OSError:
        return None


def analizar(video, cache=None):
    """Devuelve (tiempos, nitidez, movimiento). Guarda caché .npz al lado si se indica."""
    firma = _firma(video)
    if cache and os.path.exists(cache):
        with np.load(cache) as z:
            if firma is None or ('firma' in z.files and np.allclose(z['firma'], firma, rtol=0, atol=1e-3)):
                return z['t'], z['n'], z['m']
    # se lee por trozos (antes se cargaba todo el video en memoria: 16-20 GB con 30 min y la PC se quedaba sin RAM)
    p = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-i', video, '-vf', f'fps={FPS},scale={ANCHO}:{ALTO},format=gray',
                          '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    tam = ALTO * ANCHO
    ns, ds, previo = [], [], None
    try:
        while True:
            crudo = p.stdout.read(tam * TROZO)
            k = len(crudo) // tam
            if not k:
                break
            f = np.frombuffer(crudo[:k * tam], np.uint8).reshape(k, ALTO, ANCHO).astype(np.float32)
            lap = f[:, 1:-1, 2:] + f[:, 1:-1, :-2] + f[:, 2:, 1:-1] + f[:, :-2, 1:-1] - 4 * f[:, 1:-1, 1:-1]
            ns.append(lap.reshape(k, -1).var(axis=1))
            g = f if previo is None else np.concatenate([previo, f])  # con el último cuadro del trozo anterior
            if len(g) > 1:
                ds.append(np.abs(np.diff(g, axis=0)).reshape(len(g) - 1, -1).mean(axis=1))
            previo = f[-1:]
    finally:
        p.stdout.close()
        p.wait()
    if p.returncode:
        raise subprocess.CalledProcessError(p.returncode, 'ffmpeg')
    if not ns:
        raise ValueError(f'no pude leer cuadros de {os.path.basename(video)}')
    n = np.concatenate(ns)
    d = np.concatenate(ds) if ds else np.zeros(0, np.float32)
    m = np.maximum(np.r_[d[:1], d], np.r_[d, d[-1:]]) if len(d) else np.zeros(len(n), np.float32)  # peor de los dos vecinos
    t = np.arange(len(n)) / FPS
    if cache:
        np.savez(cache, t=t, n=n, m=m, **({'firma': firma} if firma is not None else {}))
    return t, n, m


def mejor(t, n, m, t0, t1, quieto=None):
    """Segundo más nítido y quieto entre t0 y t1."""
    quieto = np.percentile(m, 40) if quieto is None else quieto
    sel = (t >= t0) & (t <= t1)
    if not sel.any():
        return round(float(t0), 1)
    idx = np.where(sel)[0]
    ok = idx[m[idx] <= quieto]
    if len(ok) == 0:  # todo se mueve: el menos movido entre los nítidos
        ok = idx[n[idx] >= np.median(n[idx])]
        return round(float(t[ok[np.argmin(m[ok])]]), 1)
    return round(float(t[ok[np.argmax(n[ok])]]), 1)


def destacados(t, n, m, top=8, separacion=6.0):
    """Los momentos más nítidos y quietos del video, separados entre sí (para tráiler o miniaturas)."""
    puntaje = (n / np.median(n)) / (1 + m / np.median(m))
    elegidos = []
    for i in np.argsort(-puntaje):
        if all(abs(t[i] - e) >= separacion for e in elegidos):
            elegidos.append(float(t[i]))
        if len(elegidos) == top:
            break
    return sorted(round(e, 1) for e in elegidos)


def repartidos(t, n, m, top=14, cambios=0.3):
    """Capturas que cubren TODO el video: el video se parte en tramos iguales y de cada uno sale su cuadro
    más nítido y quieto; además, una parte (cambios) va justo después de los mayores picos de movimiento,
    que es donde pasa una acción o hay un corte. Así no se salta un tramo por ser movido o borroso."""
    total = float(t[-1])
    n_cambios = int(round(top * cambios)) if top >= 6 else 0
    n_tramos = top - n_cambios
    paso = total / n_tramos
    elegidos = [mejor(t, n, m, k * paso, (k + 1) * paso) for k in range(n_tramos)]
    if n_cambios:
        # picos de movimiento suavizados (1 s), separados entre sí y de las capturas ya elegidas
        suave = np.convolve(m, np.ones(FPS) / FPS, mode='same')
        sep = max(4.0, total / (top * 2))
        picos = []
        for i in np.argsort(-suave):
            ti = float(t[i])
            if all(abs(ti - x) >= sep for x in picos + elegidos):
                picos.append(ti)
            if len(picos) == n_cambios:
                break
        elegidos += [mejor(t, n, m, p + 0.4, min(total, p + 3)) for p in picos]
    return sorted({round(float(e), 1) for e in elegidos})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--ventana', nargs=2, type=float)
    ap.add_argument('--plan')
    ap.add_argument('--salida')
    ap.add_argument('--top', type=int)
    ap.add_argument('--separacion', type=float, default=6.0)
    a = ap.parse_args()
    t, n, m = analizar(a.video, os.path.splitext(a.video)[0] + '.nitidez.npz')
    if a.ventana:
        print(mejor(t, n, m, *a.ventana))
    if a.plan:
        res = {k: mejor(t, n, m, *v) for k, v in json.load(open(a.plan, encoding='utf-8')).items()}
        print(json.dumps(res, indent=1))
        if a.salida:
            json.dump(res, open(a.salida, 'w', encoding='utf-8'), indent=1)
    if a.top:
        print(destacados(t, n, m, a.top, a.separacion))


if __name__ == '__main__':
    main()
