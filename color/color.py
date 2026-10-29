"""«🎨 Color parejo»: todas las tomas del mismo tono y brillo, y las tomas oscuras aclaradas.

Cuando grabas con luz de ventana, unas tomas salen azuladas y otras amarillas, o más oscuras cuando pasa una nube. Esto
lo corrige en tu PC (gratis, OpenCV), antes del montaje:
  1. Mide 2 veces por segundo el color medio de lo que no es negro ni blanco quemado (balance de blancos) y el brillo.
  2. Calcula para cada momento cuánto subir o bajar cada color para que el blanco se vea blanco, y el brillo para que
     todas las tomas queden parejas; en las tomas oscuras levanta las sombras (sin quemar las pantallas). Los cambios
     son suaves en el tiempo, para que no se note que se corrige.
  3. Arma el video con esa corrección, el mismo audio y la misma duración.

Uso: python color.py --entrada original.mp4 [--salida corregido.mp4] [--fuerza 0.7] [--prueba carpeta]
Sin --salida reemplaza el archivo y deja el de antes como NOMBRE_sin_color.mp4 (los tiempos no cambian: el guion sirve igual).
"""
import argparse, json, os, subprocess
import cv2
import numpy as np

FPS_ANALISIS = 2
SUAVE_S = 3.0        # segundos de suavizado de la corrección
BRILLO_META = 118.0  # brillo medio buscado (0-255)


def probar(f):
    r = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                   'stream=width,height,r_frame_rate:format=duration', '-of', 'json', f],
                                  capture_output=True, text=True, check=True).stdout)
    s = r['streams'][0]
    n, d = s['r_frame_rate'].split('/')
    return int(s['width']), int(s['height']), float(n) / float(d or 1), float(r['format']['duration'])


def cuadros(f, ancho, alto, fps=None):
    vf = (f'fps={fps},' if fps else '') + f'scale={ancho}:{alto}'
    p = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-i', f, '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
                         stdout=subprocess.PIPE)
    tam = ancho * alto * 3
    while True:
        b = p.stdout.read(tam)
        if len(b) < tam:
            break
        yield np.frombuffer(b, np.uint8).reshape(alto, ancho, 3)
    p.wait()


def medir(f, W, H):
    """Por cada medio segundo: (media B, G, R de los grises de la escena, brillo mediano, percentil 95)."""
    aw, ah = 320, int(round(H * 320 / W / 2)) * 2
    out = []
    for c in cuadros(f, aw, ah, FPS_ANALISIS):
        x = c.reshape(-1, 3).astype(np.float32)
        lum = x @ np.array([0.114, 0.587, 0.299], np.float32)
        sat = x.max(1) - x.min(1)
        # gray-world solo con lo que es casi gris (paredes, mesa, papel): ignora la pantalla de colores y lo quemado
        sirve = (lum > 40) & (lum < 235) & (sat < 60)
        if sirve.sum() < len(x) * 0.05:
            sirve = (lum > 30) & (lum < 240)
        m = x[sirve].mean(0) if sirve.any() else np.array([128, 128, 128], np.float32)
        out.append([*m, float(np.median(lum)), float(np.percentile(lum, 95))])
    return np.array(out, np.float32)


def suavizar(v, n):
    if len(v) < 3 or n < 2:
        return v
    k = np.ones(n) / n
    pad = np.pad(v, ((n // 2, n - 1 - n // 2), (0, 0)), mode='edge')
    return np.stack([np.convolve(pad[:, j], k, mode='valid') for j in range(v.shape[1])], 1)


def correcciones(med, fuerza):
    """Por cada medio segundo: (ganancia B, G, R, gamma)."""
    gris = med[:, :3].mean(1, keepdims=True)
    g = (gris / np.maximum(med[:, :3], 1)) ** fuerza          # que lo gris quede gris
    g = np.clip(g, 0.8, 1.25)
    brillo = np.clip(med[:, 3], 1, 255)
    meta = np.clip(np.median(brillo), BRILLO_META - 15, BRILLO_META + 15)
    k = np.clip((meta / brillo) ** (0.6 * fuerza), 0.85, 1.6)  # brillo parejo entre tomas
    alto = med[:, 4]
    k = np.minimum(k, np.maximum(1.0, 250 / np.maximum(alto, 1)))  # sin quemar lo más claro (la pantalla del celular)
    gamma = np.where(brillo < 80, np.clip(0.75 + brillo / 320, 0.75, 1.0), 1.0)  # tomas oscuras: levanta las sombras
    c = np.concatenate([g * k[:, None], gamma[:, None]], 1)
    return suavizar(c, int(SUAVE_S * FPS_ANALISIS))


def luts(c):
    x = np.arange(256, dtype=np.float32) / 255
    base = x ** c[3]
    return [np.clip(base * 255 * c[j], 0, 255).astype(np.uint8) for j in range(3)]


def aplicar(cuadro, c):
    b, g, r = cv2.split(cuadro)
    lb, lg, lr = luts(c)
    return cv2.merge([cv2.LUT(b, lb), cv2.LUT(g, lg), cv2.LUT(r, lr)])


def corr_en(cs, t):
    i = t * FPS_ANALISIS
    k = int(min(max(i, 0), len(cs) - 1))
    k2 = min(k + 1, len(cs) - 1)
    f = min(max(i - k, 0), 1)
    return cs[k] * (1 - f) + cs[k2] * f


def armar(entrada, salida, cs, W, H, fps):
    W2, H2 = W // 2 * 2, H // 2 * 2
    p = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W2}x{H2}',
                          '-r', f'{fps:.5f}', '-i', '-', '-i', entrada, '-map', '0:v', '-map', '1:a?', '-c:a', 'copy',
                          '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-shortest', salida],
                         stdin=subprocess.PIPE)
    for i, c in enumerate(cuadros(entrada, W2, H2)):
        p.stdin.write(aplicar(c, corr_en(cs, i / fps)).tobytes())
        if i % int(fps * 60) == 0:
            print(f'· [{int(i / fps // 60)}:{int(i / fps % 60):02d}] corrigiendo color…', flush=True)
    p.stdin.close()
    if p.wait():
        raise SystemExit('ERROR: no se pudo armar el video con el color corregido (mira el registro).')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entrada', required=True)
    ap.add_argument('--salida')
    ap.add_argument('--fuerza', type=float, default=0.7, help='0 = nada, 1 = todo el balance de blancos')
    ap.add_argument('--prueba', help='carpeta: antes y después de 6 momentos (no arma el video)')
    ap.add_argument('--deshacer', action='store_true')
    a = ap.parse_args()
    base, ext = os.path.splitext(a.entrada)
    previo = base + '_sin_color' + ext
    if a.deshacer:
        if os.path.exists(previo):
            os.replace(previo, a.entrada)
            print('· puse de nuevo la grabación sin corregir', flush=True)
        return
    fuente = previo if not a.salida and os.path.exists(previo) else a.entrada  # siempre desde la grabación sin tocar
    W, H, fps, dur = probar(fuente)
    print(f'Mido el color de {os.path.basename(fuente)} ({dur / 60:.1f} min)…', flush=True)
    med = medir(fuente, W, H)
    cs = correcciones(med, min(max(a.fuerza, 0), 1))
    oscuras = int((med[:, 3] < 80).sum() / FPS_ANALISIS)
    calido = float(np.median(med[:, 2] / np.maximum(med[:, 0], 1)))
    print(f"· tono medio: {'cálido (amarillento)' if calido > 1.08 else 'frío (azulado)' if calido < 0.93 else 'neutro'}; "
          f"{oscuras} s de tomas oscuras; ganancia de brillo entre ×{cs[:, :3].mean(1).min():.2f} y ×{cs[:, :3].mean(1).max():.2f}", flush=True)
    if a.prueba:
        os.makedirs(a.prueba, exist_ok=True)
        cap = cv2.VideoCapture(fuente)
        for k, t in enumerate(np.linspace(dur * 0.05, dur * 0.95, 6), 1):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, c = cap.read()
            if ok:
                c = cv2.resize(c, (640, int(640 * c.shape[0] / c.shape[1])))
                cv2.imwrite(os.path.join(a.prueba, f'color_{k}.jpg'), np.hstack([c, aplicar(c, corr_en(cs, t))]))
        return
    destino = a.salida or base + '.color' + ext
    armar(fuente, destino, cs, W, H, fps)
    if not a.salida:
        if not os.path.exists(previo):
            os.replace(a.entrada, previo)
        os.replace(destino, a.entrada)
        print(f'Listo: {a.entrada} (el de antes quedó como {os.path.basename(previo)})', flush=True)
    else:
        print(f'Listo: {a.salida}', flush=True)


if __name__ == '__main__':
    main()
