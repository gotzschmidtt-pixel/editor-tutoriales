"""Qué se ve en un cuadro del video, gratis y en tu PC: el teléfono (aunque tenga la pantalla negra o esté en la mano),
la laptop, el monitor, el teclado, el mouse, las manos o brazos (también con guantes) y tu cara.

Usa YOLOX, de la familia YOLO (el del OpenCV Model Zoo, licencia Apache 2.0), con el mismo OpenCV que la app ya tiene: no
instala nada más, no gasta créditos y no manda imágenes a ningún lado. La primera vez baja el modelo (35 MB) a
descargas_app/modelos y revisa que sea el archivo correcto. Si no se puede bajar, cada paso sigue como antes, sin detector.

Lo usan:
  short/short.py        el Short sigue al teléfono y elige el zoom para que entre entero
  senales/senales.py    un círculo o flecha sobre el teléfono lo sigue aunque cambie lo que muestra la pantalla
  etiquetas/etiquetas.py  las etiquetas van del lado donde no tapan el teléfono ni tu cara
  ia/ia.py              el mapa del video dice qué se ve en cada cambio de pantalla (para escribir el guion)

Prueba: python deteccion.py video.mp4 12.5 30 61   (dice lo que ve en esos segundos)
       python deteccion.py --bajar                (instalar.bat: deja el detector y el de caras en descargas_app/modelos)
"""
import hashlib, json, os, sys, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELO = os.path.join(RAIZ, 'descargas_app', 'modelos', 'object_detection_yolox_2022nov.onnx')
SHA256 = 'c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063'
URLS = ['https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx',
        'https://huggingface.co/opencv/object_detection_yolox/resolve/main/object_detection_yolox_2022nov.onnx']
LADO = 640  # el modelo mira el cuadro achicado a 640×640
# clases del modelo (COCO) que sirven en un tutorial; el control remoto casi siempre es un teléfono mal leído
QUE = {67: 'telefono', 65: 'telefono', 63: 'laptop', 62: 'monitor', 66: 'teclado', 64: 'mouse', 0: 'mano'}
NOMBRE = {'telefono': 'teléfono', 'laptop': 'laptop', 'monitor': 'monitor', 'teclado': 'teclado', 'mouse': 'mouse',
          'mano': 'manos', 'cara': 'una cara'}
PANTALLAS = ('telefono', 'laptop', 'monitor')  # lo que suele llevar un círculo encima
_RED, _ANCLAS = [], []


def _bajar():
    if os.path.exists(MODELO):
        return MODELO
    os.makedirs(os.path.dirname(MODELO), exist_ok=True)
    print('Bajo una sola vez el detector de objetos (YOLOX, 35 MB, gratis) a descargas_app\\modelos…', flush=True)
    error = None
    for url in URLS:
        try:
            datos = urllib.request.urlopen(url, timeout=120).read()
        except OSError as e:
            error = e
            continue
        if hashlib.sha256(datos).hexdigest() != SHA256:
            error = 'el archivo bajado no es el modelo esperado'
            continue
        with open(MODELO + '.tmp', 'wb') as f:
            f.write(datos)
        os.replace(MODELO + '.tmp', MODELO)
        return MODELO
    raise RuntimeError(f'no pude bajar el detector ({error})')


def disponible():
    """El detector cargado (lo baja la primera vez), o None si no se pudo: entonces cada paso sigue como antes."""
    if not _RED:
        _RED.append(None)
        try:
            import cv2, numpy as np
            _RED[0] = cv2.dnn.readNet(_bajar())
            celdas, pasos = [], []
            for s in (8, 16, 32):
                n = LADO // s
                xv, yv = np.meshgrid(np.arange(n), np.arange(n))
                celdas.append(np.stack((xv, yv), 2).reshape(-1, 2))
                pasos.append(np.full((n * n, 1), s))
            _ANCLAS.extend([np.concatenate(celdas).astype(np.float32), np.concatenate(pasos).astype(np.float32)])
        except Exception as e:  # sin detector: el Short, los círculos y las etiquetas quedan como siempre
            print(f'(sin detector de objetos: {e}; sigo como antes)', flush=True)
    return _RED[0]


def objetos(cuadro, umbral=0.35):
    """Lo que se ve en un cuadro (BGR, de cualquier tamaño): [{'que', 'conf', 'caja': [x, y, ancho, alto]}] en píxeles de
    ese cuadro, de más a menos seguro. Vacío si no hay detector."""
    red = disponible()
    if red is None or cuadro is None:
        return []
    import cv2, numpy as np
    h, w = cuadro.shape[:2]
    r = min(LADO / h, LADO / w)
    lienzo = np.full((LADO, LADO, 3), 114, np.float32)
    lienzo[:int(h * r), :int(w * r)] = cv2.resize(cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB), (int(w * r), int(h * r)))
    red.setInput(lienzo.transpose(2, 0, 1)[None])
    d = red.forward()[0]
    celdas, pasos = _ANCLAS
    puntaje = d[:, 4:5] * d[:, 5:]
    clase = puntaje.argmax(1)
    conf = puntaje.max(1)
    sirve = np.isin(clase, list(QUE)) & (conf >= umbral)
    if not sirve.any():
        return []
    d, clase, conf, celdas, pasos = d[sirve], clase[sirve], conf[sirve], celdas[sirve], pasos[sirve]
    centro = (d[:, :2] + celdas) * pasos / r
    tam = np.exp(d[:, 2:4]) * pasos / r
    cajas = np.concatenate([centro - tam / 2, tam], 1)
    ques = sorted(set(QUE.values()))
    grupo = [ques.index(QUE[int(c)]) for c in clase]  # el teléfono y el «control remoto» se comparan entre sí
    out = []
    for i in np.array(cv2.dnn.NMSBoxesBatched(cajas.tolist(), conf.tolist(), grupo, umbral, 0.5)).flatten():
        x, y, cw, ch = cajas[i]
        x0, y0 = max(0.0, x), max(0.0, y)
        x1, y1 = min(float(w), x + cw), min(float(h), y + ch)
        if x1 - x0 > 4 and y1 - y0 > 4:
            out.append({'que': QUE[int(clase[i])], 'conf': round(float(conf[i]), 2),
                        'caja': [round(x0), round(y0), round(x1 - x0), round(y1 - y0)]})
    return sorted(out, key=lambda o: -o['conf'])


def _detector_caras():
    sys.path.insert(0, os.path.join(RAIZ, 'montaje'))
    import montaje
    return montaje.detector_caras()  # el mismo del montaje (YuNet, 230 KB, lo baja la primera vez)


def caras(cuadro):
    """[x, y, ancho, alto] de las caras que se ven (de al menos ~3 % del ancho), con el detector de caras del montaje."""
    if cuadro is None:
        return []
    import cv2
    det = _detector_caras()
    if det is None:
        return []
    h, w = cuadro.shape[:2]
    k = 640 / w
    chico = cv2.resize(cuadro, (640, max(1, round(h * k))))
    det.setInputSize((chico.shape[1], chico.shape[0]))
    _, cs = det.detect(chico)
    return [[round(c[0] / k), round(c[1] / k), round(c[2] / k), round(c[3] / k)] for c in (cs if cs is not None else [])
            if c[2] >= 640 * 0.03]


def telefono(objs, minimo=0.4):
    """La caja del teléfono más seguro, o None."""
    t = [o for o in objs if o['que'] == 'telefono' and o['conf'] >= minimo]
    return t[0]['caja'] if t else None


def solape(a, b):
    """Qué parte de la caja a queda dentro de la caja b (0 a 1)."""
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return max(0, x1 - x0) * max(0, y1 - y0) / max(1, a[2] * a[3])


def debajo(objs, x, y, margen=0.08):
    """El objeto con pantalla (teléfono, laptop o monitor) que está debajo del punto (x, y): el más chico que lo contiene."""
    dentro = []
    for o in objs:
        cx, cy, cw, ch = o['caja']
        if o['que'] in PANTALLAS and o['conf'] >= 0.4 and \
                cx - cw * margen <= x <= cx + cw * (1 + margen) and cy - ch * margen <= y <= cy + ch * (1 + margen):
            dentro.append(o)
    return min(dentro, key=lambda o: o['caja'][2] * o['caja'][3]) if dentro else None


def mismo(objs, que, antes):
    """En un cuadro nuevo, el objeto de la clase `que` que sigue siendo el de la caja `antes` (o None si se perdió)."""
    mejor, cerca = None, None
    ax, ay = antes[0] + antes[2] / 2, antes[1] + antes[3] / 2
    for o in objs:
        if o['que'] != que or o['conf'] < 0.3:
            continue
        x, y, w, h = o['caja']
        dist = ((x + w / 2 - ax) ** 2 + (y + h / 2 - ay) ** 2) ** 0.5 / max(1.0, (antes[2] ** 2 + antes[3] ** 2) ** 0.5)
        if dist < 0.6 and 0.5 < (w * h) / max(1, antes[2] * antes[3]) < 2 and (cerca is None or dist < cerca):
            mejor, cerca = o['caja'], dist
    return mejor


def resumen(objs, cs=()):
    """En palabras, lo que se ve: «teléfono en la mano · laptop · una cara». Vacío si no se ve nada conocido."""
    seguros = [o for o in objs if o['conf'] >= 0.45]
    manos = [o['caja'] for o in seguros if o['que'] == 'mano']
    partes = []
    for que in ('telefono', 'laptop', 'monitor', 'teclado', 'mouse'):
        cajas = [o['caja'] for o in seguros if o['que'] == que]
        if not cajas:
            continue
        if que == 'telefono':
            partes.append('teléfono en la mano' if any(solape(c, m) > 0.05 or solape(m, c) > 0.05 for c in cajas for m in manos)
                          else 'teléfono')
        elif not (que == 'monitor' and 'laptop' in [o['que'] for o in seguros]):  # la pantalla de la laptop no es otro monitor
            partes.append(NOMBRE[que])
    if manos and not any(p.startswith('teléfono en la mano') for p in partes) and not cs:
        partes.append('manos')
    if cs:
        partes.append('una cara')
    return ' · '.join(partes)


class Memoria:
    """Lo que ya se vio en un video, guardado al lado (<video>.objetos.json) para no mirarlo dos veces: el Short y el mapa
    del guion miran los mismos segundos de original.mp4. Solo guarda cajas, nunca imágenes."""

    def __init__(self, video):
        self.archivo = os.path.splitext(video)[0] + '.objetos.json'
        try:
            st = os.stat(video)
            self.firma = f'{st.st_size}:{int(st.st_mtime)}:{os.path.basename(MODELO)}'
            datos = json.load(open(self.archivo, encoding='utf-8'))
            self.vistos = datos['t'] if datos.get('firma') == self.firma else {}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            self.vistos = {}
        self.nuevos = 0

    def ver(self, s, cuadro):
        """objetos() del cuadro del segundo s del video (de la memoria, si ya se miró)."""
        k = f'{s:.2f}'
        if k not in self.vistos:
            if disponible() is None:
                return []
            self.vistos[k] = objetos(cuadro)
            self.nuevos += 1
        return self.vistos[k]

    def guardar(self):
        if not self.nuevos or not getattr(self, 'firma', None):
            return
        try:
            with open(self.archivo + '.tmp', 'w', encoding='utf-8') as f:
                json.dump({'firma': self.firma, 't': self.vistos}, f)
            os.replace(self.archivo + '.tmp', self.archivo)
            self.nuevos = 0
        except OSError:
            pass  # sin memoria, la próxima vez se vuelve a mirar


def main():
    if sys.argv[1:] == ['--bajar']:  # instalar.bat y guardar_para_otra_pc.bat: que ya esté para usarse sin internet
        objs = disponible() is not None
        cs = _detector_caras() is not None
        print(f"Detector de objetos: {'listo' if objs else 'no se pudo bajar (se intenta de nuevo al usarlo)'}. "
              f"Detector de caras: {'listo' if cs else 'no se pudo bajar (se intenta de nuevo al usarlo)'}.")
        return
    import cv2
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    cap = cv2.VideoCapture(sys.argv[1])
    for s in sys.argv[2:]:
        cap.set(cv2.CAP_PROP_POS_MSEC, float(s) * 1000)
        ok, f = cap.read()
        if not ok:
            print(f'{s} s: no pude leer ese cuadro')
            continue
        objs = objetos(f)
        print(f"{s} s: {resumen(objs, caras(f)) or 'nada conocido'}")
        for o in objs:
            print(f"   {NOMBRE[o['que']]:9s} {o['conf']:.2f}  {o['caja']}")


if __name__ == '__main__':
    main()
