"""«📱 Pantalla derecha»: encuentra la pantalla del celular en tu grabación con cámara y la endereza, como una captura.

Gratis, en tu PC (OpenCV + el detector de objetos de deteccion/):
  1. Cinco veces por segundo busca el teléfono (detector YOLOX) y, dentro, el rectángulo de la pantalla encendida (el
     borde de la zona que brilla, con 4 esquinas). Las esquinas se suavizan en el tiempo para que no tiemble.
  2. Endereza ese rectángulo (perspectiva), le sube un poco el contraste para leer bien con reflejos y lo pone grande en
     el centro, sobre tu misma toma desenfocada. Queda pantalla_enderezada.mp4 (5 cuadros por segundo, misma duración
     que la grabación; donde no encontró pantalla, va la toma tal cual).
  3. Con --insertos agrega a insertos.json un inserto en cada paso clave (escribir la key, un código, elegir una opción)
     donde la pantalla se ve chica o torcida: en ese momento el video muestra la pantalla derecha.

Uso: python enderezar.py --proyecto . [--insertos] [--prueba carpeta]
"""
import argparse, json, os, re, subprocess, sys
import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'deteccion'))
import deteccion  # noqa: E402  ve el teléfono aunque tenga la pantalla negra

FPS = 5
W, H = 1920, 1080
SALIDA = 'pantalla_enderezada.mp4'
INSERTOS = 'insertos.json'
LEER = re.compile(r'\b(key|clave|c[oó]digo|pin|contrase|escrib|peg[ao]|ingres|imei|versi[oó]n|ajustes|configuraci|'
                  r'selecciona|elige|opci[oó]n|men[uú]|pantalla|aparece|dice|mensaje|aviso)', re.I)


def ordenar(p):
    """Esquinas en orden: arriba-izq, arriba-der, abajo-der, abajo-izq."""
    p = np.array(p, np.float32).reshape(4, 2)
    s, d = p.sum(1), np.diff(p, axis=1).ravel()
    return np.array([p[np.argmin(s)], p[np.argmin(d)], p[np.argmax(s)], p[np.argmax(d)]], np.float32)


def cuadrilateros(gris, minimo):
    """Candidatos de 4 esquinas en una imagen en gris: por brillo (la pantalla encendida) y por bordes."""
    out = []
    suave = cv2.GaussianBlur(gris, (5, 5), 0)
    _, brillo = cv2.threshold(suave, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    brillo = cv2.morphologyEx(brillo, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    bordes = cv2.dilate(cv2.Canny(suave, 40, 120), np.ones((3, 3), np.uint8))
    for m in (brillo, bordes):
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL if m is brillo else cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for c in sorted(cs, key=cv2.contourArea, reverse=True)[:6]:
            a = cv2.contourArea(c)
            if a < minimo:
                break
            hull = cv2.convexHull(c)
            for eps in (0.02, 0.035, 0.05):
                q = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
                if len(q) == 4:
                    out.append((ordenar(q), a))
                    break
            else:
                r = cv2.minAreaRect(c)  # pantalla con una esquina tapada por el dedo: el rectángulo que la contiene
                if a / max(1.0, r[1][0] * r[1][1]) > 0.8:
                    out.append((ordenar(cv2.boxPoints(r)), a))
    return out


def lados(q):
    w = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    h = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    return w, h


def pantalla(cuadro, tel=None):
    """Las 4 esquinas de la pantalla (en píxeles del cuadro) o None. `tel`: caja del teléfono [x, y, w, h] si se sabe."""
    h0, w0 = cuadro.shape[:2]
    if not tel and deteccion.disponible() is not None:
        return None  # el detector no ve un teléfono: lo rectangular que hay es la PC o una ventana, no la pantalla del celular
    if tel:
        x, y, w, h = tel
        mx, my = w * 0.08, h * 0.05
        x0, y0, x1, y1 = int(max(0, x - mx)), int(max(0, y - my)), int(min(w0, x + w + mx)), int(min(h0, y + h + my))
    else:
        x0, y0, x1, y1 = 0, 0, w0, h0
    roi = cv2.cvtColor(cuadro[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    if roi.size == 0:
        return None
    area_roi = roi.shape[0] * roi.shape[1]
    mejor, puntos = None, -1
    for q, a in cuadrilateros(roi, area_roi * (0.25 if tel else 0.03)):
        w, h = lados(q)
        if min(w, h) < 40:
            continue
        prop = max(w, h) / min(w, h)
        if not 1.5 <= prop <= 2.5:  # un teléfono: entre 3:2 y 20:9 aprox., en vertical o acostado
            continue
        rect = a / max(1.0, w * h)
        p = a * rect * (1.3 if roi[np.clip(int(q[:, 1].mean()), 0, roi.shape[0] - 1), np.clip(int(q[:, 0].mean()), 0, roi.shape[1] - 1)] > 60 else 1)
        if rect > 0.75 and p > puntos:
            mejor, puntos = q, p
    return None if mejor is None else mejor + np.array([x0, y0], np.float32)


def enderezar(cuadro, q, alto=1000):
    w, h = lados(q)
    if w > h:  # acostado: se deja acostado
        ow, oh = int(alto * 16 / 9 * 0.9), int(alto * 16 / 9 * 0.9 * h / w)
    else:
        oh, ow = alto, int(alto * w / h)
    M = cv2.getPerspectiveTransform(q, np.float32([[0, 0], [ow, 0], [ow, oh], [0, oh]]))
    plano = cv2.warpPerspective(cuadro, M, (ow, oh), flags=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(plano, cv2.COLOR_BGR2LAB)  # algo más de contraste local: se lee mejor con reflejos
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(6, 6)).apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def componer(cuadro, plano):
    fondo = cv2.GaussianBlur(cv2.resize(cuadro, (W // 4, H // 4)), (0, 0), 6)
    fondo = (cv2.resize(fondo, (W, H)) * 0.45).astype(np.uint8)
    ph, pw = plano.shape[:2]
    k = min((H - 60) / ph, (W - 120) / pw)
    plano = cv2.resize(plano, (int(pw * k), int(ph * k)), interpolation=cv2.INTER_CUBIC)
    ph, pw = plano.shape[:2]
    x, y = (W - pw) // 2, (H - ph) // 2
    sombra = np.zeros((H, W), np.uint8)
    cv2.rectangle(sombra, (x + 10, y + 14), (x + pw + 10, y + ph + 14), 255, -1)
    sombra = cv2.GaussianBlur(sombra, (0, 0), 14)
    fondo = (fondo * (1 - sombra[:, :, None] / 255 * 0.6)).astype(np.uint8)
    fondo[y:y + ph, x:x + pw] = plano
    return fondo


def analizar(orig):
    """[(t, esquinas o None)] cinco veces por segundo, con las esquinas suavizadas."""
    cap = cv2.VideoCapture(orig)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    paso = max(1, int(round(fps / FPS)))
    crudo, i = [], 0
    while i < n:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, c = cap.read()
        if not ok:
            break
        c = cv2.resize(c, (W, H)) if c.shape[1] != W else c
        tel = deteccion.telefono(deteccion.objetos(c))
        crudo.append((i / fps, pantalla(c, tel)))
        if len(crudo) % (FPS * 30) == 0:
            print(f'· [{int(i / fps // 60)}:{int(i / fps % 60):02d}] buscando la pantalla…', flush=True)
        i += paso
    cap.release()
    out = []
    for k, (t, q) in enumerate(crudo):  # mediana con los vecinos: sin temblor y sin saltos sueltos
        vec = [x for _, x in crudo[max(0, k - 2):k + 3] if x is not None]
        out.append((t, np.median(np.stack(vec), 0).astype(np.float32) if q is not None and len(vec) >= 3 else None))
    return out


def armar(orig, datos, salida):
    p = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
                          salida + '.parcial.mp4'], stdin=subprocess.PIPE)
    cap = cv2.VideoCapture(orig)
    for t, q in datos:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, c = cap.read()
        if not ok:
            break
        c = cv2.resize(c, (W, H)) if c.shape[1] != W else c
        p.stdin.write((componer(c, enderezar(c, q)) if q is not None else c).tobytes())
    cap.release()
    p.stdin.close()
    if p.wait():
        raise SystemExit('ERROR: no se pudo armar la pantalla enderezada.')
    os.replace(salida + '.parcial.mp4', salida)


def elegir_insertos(d, datos):
    """Un inserto por paso clave donde la pantalla se ve chica (menos de un tercio del alto) o torcida."""
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    hay = {round(t * FPS): q for t, q in datos}
    nuevos = []
    for b in g.get('bloques', []):
        mo = b.get('montaje') or {}
        if mo.get('src_inicio') is None or not str(b.get('texto') or '').strip():
            continue
        critico = b.get('tipo') == 'critico' or mo.get('critico')
        if not (critico or LEER.search(b['texto'])):
            continue
        s0, s1 = float(mo['src_inicio']), float(mo.get('src_fin') or mo['src_inicio'] + 2)
        cands = [(t, q) for t, q in ((k / FPS, hay.get(k)) for k in range(int(s0 * FPS), int(s1 * FPS) + 1)) if q is not None]
        if not cands:
            continue
        t, q = cands[len(cands) // 2]
        w, h = lados(q)
        torcida = abs(np.degrees(np.arctan2(q[1][1] - q[0][1], q[1][0] - q[0][0]))) > 6
        if max(w, h) > H * 0.75 and not torcida:
            continue  # ya se ve grande y derecha
        palabras = re.findall(r"[\wáéíóúñü']+", b['texto'])
        nuevos.append({'nota': 'pantalla derecha', 'origen': 'pantalla', 'material': SALIDA, 'src_t': round(t, 2), 'bloque': b['id'],
                       'frase': ' '.join(palabras[:3]), 'dur': round(min(4.5, max(2.5, float(b.get('voz_real_s') or 4) * 0.5)), 1),
                       'claves': [{'t': 0, 'cx': 0.5, 'cy': 0.5, 'w': 0.98}, {'t': 2.5, 'cx': 0.5, 'cy': 0.5, 'w': 0.9}]})
        if len(nuevos) >= 8 and not critico:
            break
    return nuevos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--video', default='original.mp4')
    ap.add_argument('--insertos', action='store_true', help='agrega insertos en los pasos clave (los de antes de este módulo no se tocan)')
    ap.add_argument('--prueba', help='carpeta: 6 cuadros con la pantalla marcada y enderezada (no arma el video)')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    orig = os.path.join(d, a.video)
    if a.prueba:
        os.makedirs(a.prueba, exist_ok=True)
        cap = cv2.VideoCapture(orig)
        dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30)
        for k, t in enumerate(np.linspace(dur * 0.1, dur * 0.9, 6), 1):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, c = cap.read()
            if not ok:
                continue
            c = cv2.resize(c, (W, H))
            q = pantalla(c, deteccion.telefono(deteccion.objetos(c)))
            marcado = c.copy()
            if q is not None:
                cv2.polylines(marcado, [q.astype(np.int32)], True, (214, 43, 255), 5)
            fila = [cv2.resize(marcado, (640, 360)), cv2.resize(componer(c, enderezar(c, q)) if q is not None else c, (640, 360))]
            cv2.imwrite(os.path.join(a.prueba, f'pantalla_{k}.jpg'), np.hstack(fila))
        return
    print('Busco la pantalla del celular en tu grabación…', flush=True)
    datos = analizar(orig)
    con = sum(q is not None for _, q in datos)
    print(f'· pantalla encontrada en {con * 100 // max(1, len(datos))} % de los momentos', flush=True)
    armar(orig, datos, os.path.join(d, SALIDA))
    print(f'· listo {SALIDA}', flush=True)
    if a.insertos and os.path.exists(os.path.join(d, 'guion.json')):
        f = os.path.join(d, INSERTOS)
        try:
            lista = json.load(open(f, encoding='utf-8'))
        except (OSError, ValueError):
            lista = []
        lista = [x for x in lista if x.get('origen') != 'pantalla'] + elegir_insertos(d, datos)  # los tuyos no se tocan
        json.dump(lista, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"· {sum(x.get('origen') == 'pantalla' for x in lista)} insertos con la pantalla derecha en {INSERTOS}", flush=True)


if __name__ == '__main__':
    main()
