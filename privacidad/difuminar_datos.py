"""Difumina datos personales que se ven en pantalla (correo, teléfono, nombre y saldo de la cuenta…) siguiéndolos aunque la
cámara se mueva o haya zoom. Pedido de fabian (31/10/2026): los videos son públicos y en el HONOR 8 LITE se leían el
correo, el teléfono y el saldo en la cabecera de la web del pedido, grabada con la cámara y en el material extra.

Cómo: una o más imágenes de referencia (la cabecera de la página tal como se ve en un cuadro) con los recuadros de los
datos marcados. En cada cuadro de los tramos indicados se buscan los puntos de la referencia (SIFT de OpenCV) y, si
coinciden suficientes, se calcula dónde quedó la página (homografía) y se difuminan sus recuadros, aunque esté torcida,
más chica o más grande. Una búsqueda por texto daba falsos positivos; esta no (31/10/2026: con la cabecera, 85 a 548
coincidencias; sin ella, menos de 30). El audio no se toca.

El proyecto lo activa con difuminar_datos.json:
  {"referencias": [{"imagen": "difuminar_datos/cabecera.png", "zonas": [[x, y, ancho, alto], ...]}, ...],
   "tramos": [[315, 446], [543, 630]], "minimo": 50}
El paso «Video final sin tráiler» lo corre solo después del inicio fijo (así no se pierde al rehacer el final).

Uso (desde la carpeta del proyecto): python difuminar_datos.py --entrada FINAL.mp4 --salida FINAL.mp4
"""
import argparse, json, os, shutil, subprocess, tempfile

import cv2
import numpy as np

REDUCE = 0.8          # se busca sobre el cuadro algo achicado (a 0,6 la cabecera lejana ya no se encontraba)
MARGEN = 0.15         # cuánto más grande que el dato es el difuminado
GUARDA = 8            # cuadros que el difuminado sigue en su lugar si en uno no se encuentra (que no parpadee)


def dimensiones(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate',
                        '-of', 'json', f], capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)['streams'][0]
    n, d = s['r_frame_rate'].split('/')
    return s['width'], s['height'], float(n) / float(d)


def difuminar(img, x0, y0, x1, y1):
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return
    zona = img[y0:y1, x0:x1]
    chico = cv2.resize(zona, (max(1, (x1 - x0) // 12), max(1, (y1 - y0) // 12)), interpolation=cv2.INTER_AREA)
    img[y0:y1, x0:x1] = cv2.GaussianBlur(cv2.resize(chico, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR), (0, 0), 6)


class Referencia:
    """Una cabecera de referencia: sus puntos SIFT y los recuadros de datos; recuerda la última posición encontrada."""

    def __init__(self, sift, imagen, zonas, minimo):
        g = cv2.cvtColor(cv2.imread(imagen), cv2.COLOR_BGR2GRAY)
        self.kp, self.des = sift.detectAndCompute(g, None)
        self.zonas, self.minimo = zonas, minimo
        self.ultima, self.perdido = None, GUARDA + 1

    def recuadros(self, kp2, des2, bf):
        H = None
        if self.des is not None and des2 is not None and len(kp2) >= 8:
            mt = [p[0] for p in bf.knnMatch(self.des, des2, k=2) if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
            if len(mt) >= self.minimo:
                src = np.float32([self.kp[m.queryIdx].pt for m in mt])
                dst = np.float32([kp2[m.trainIdx].pt for m in mt]) / REDUCE
                H, msk = cv2.findHomography(src, dst, cv2.RANSAC, 6)
                if H is None or msk.sum() < self.minimo:
                    H = None
                else:
                    det = np.linalg.det(H[:2, :2])
                    H = H if 0.04 < det < 25 else None  # una homografía absurda (página volteada o diminuta) no vale
        if H is not None:
            self.ultima, self.perdido = H, 0
        else:
            self.perdido += 1
        if self.ultima is None or self.perdido > GUARDA:
            return []
        cajas = []
        for x, y, w, h in self.zonas:
            mx, my = w * MARGEN, h * MARGEN * 2
            pts = np.float32([[x - mx, y - my], [x + w + mx, y - my], [x + w + mx, y + h + my], [x - mx, y + h + my]]).reshape(-1, 1, 2)
            q = cv2.perspectiveTransform(pts, self.ultima).reshape(-1, 2)
            cajas.append((q[:, 0].min(), q[:, 1].min(), q[:, 0].max(), q[:, 1].max()))
        return cajas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entrada', required=True)
    ap.add_argument('--salida', required=True)
    a = ap.parse_args()
    if not os.path.exists('difuminar_datos.json'):
        if os.path.abspath(a.entrada) != os.path.abspath(a.salida):
            shutil.copyfile(a.entrada, a.salida)
        return print('Sin datos que difuminar (no hay difuminar_datos.json).')
    conf = json.load(open('difuminar_datos.json', encoding='utf-8'))
    refs_conf = [r for r in conf.get('referencias', []) if os.path.exists(r['imagen'])]
    if not refs_conf:
        raise SystemExit('ERROR: difuminar_datos.json no tiene referencias que existan en el proyecto.')
    tramos = [(float(x), float(y)) for x, y in conf.get('tramos') or [[0, 1e9]]]
    minimo = int(conf.get('minimo', 50))
    W, H, fps = dimensiones(a.entrada)
    sift, bf = cv2.SIFT_create(3000), cv2.BFMatcher()
    tmp = tempfile.mkdtemp(prefix='.datos_tmp_', dir=os.getcwd())
    salida_tmp = os.path.join(tmp, 'salida.mp4')
    lee = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-i', a.entrada, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
                           stdout=subprocess.PIPE)
    escribe = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
                                '-r', f'{fps}', '-i', '-', '-i', a.entrada, '-map', '0:v', '-map', '1:a', '-c:v', 'libx264',
                                '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart',
                                salida_tmp], stdin=subprocess.PIPE)
    tam, n, puestos, refs, dentro_antes = W * H * 3, 0, 0, [], False
    try:
        while True:
            buf = lee.stdout.read(tam)
            if len(buf) < tam:
                break
            t = n / fps
            dentro = any(x <= t <= y for x, y in tramos)
            if dentro:
                if not dentro_antes:  # cada tramo empieza a buscar de cero
                    refs = [Referencia(sift, r['imagen'], r['zonas'], minimo) for r in refs_conf]
                img = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
                gris = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None, fx=REDUCE, fy=REDUCE, interpolation=cv2.INTER_AREA)
                kp2, des2 = sift.detectAndCompute(gris, None)
                cajas = [c for r in refs for c in r.recuadros(kp2, des2, bf)]
                for c in cajas:
                    difuminar(img, *c)
                puestos += bool(cajas)
                buf = img.tobytes()
            dentro_antes = dentro
            escribe.stdin.write(buf)
            n += 1
            if n % 1500 == 0:
                print(f'… {t / 60:.1f} min ({puestos} cuadros con datos difuminados)', flush=True)
        escribe.stdin.close()
        if escribe.wait() != 0:
            raise SystemExit('ERROR: no pude codificar el video con los datos difuminados.')
        lee.wait()
        os.replace(salida_tmp, a.salida)
        print(f'Datos personales difuminados en {puestos} cuadros -> {a.salida}')
    finally:
        if lee.poll() is None:
            lee.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
