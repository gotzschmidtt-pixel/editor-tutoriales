"""El segundo con la miniatura del video largo al final de cada Short (fabian, 03/11/2026: «SÍ, PERO SOLO SI APRUEBO LA
MINIATURA»). Sin gastar nada (videos de prueba hechos con ffmpeg):
- sin miniatura aprobada (o solo elegida para YouTube) el Short no se toca;
- «✅ Apruebo esta miniatura» (app.yt_aprobar_miniatura) la marca en youtube/miniatura.json; si la miniatura se rehace o
  se elige otra, la aprobación ya no vale;
- va arriba al centro, sin tapar el ícono de play de abajo a la izquierda (logos.json «pos_short») ni su flecha;
- en los 3 Shorts resumen va encima del último segundo (la cola del cierre, el largo no cambia); en el Short normal se
  agrega 1 s; y el cierre sigue siendo una de las 3 frases del play.
Uso: python tests/test_short_miniatura_final.py"""
import inspect, json, os, shutil, subprocess, sys, tempfile, time
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for m_ in ('short', 'logos', 'app'):
    sys.path.insert(0, os.path.join(RAIZ, m_))
os.environ['SIN_NAVEGADOR'] = '1'
import cv2  # noqa: E402
from PIL import Image  # noqa: E402
import logos  # noqa: E402
import resumen  # noqa: E402
import short  # noqa: E402
import app  # noqa: E402

d = tempfile.mkdtemp()
try:
    app.AJUSTES = os.path.join(d, 'ajustes.json')  # nunca el app/ajustes.json de verdad
    v = os.path.join(d, 'SHORT_RESUMEN_1.mp4')

    def hacer_video():
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=gray:s=1080x1920:r=30:d=3',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3', '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', v], check=True)

    def cuadro(t):
        cap = cv2.VideoCapture(v)
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        cap.release()
        assert ok, t
        return f

    hacer_video()
    antes = open(v, 'rb').read()
    Image.new('RGB', (1280, 720), (230, 20, 20)).save(os.path.join(d, 'miniatura_1.jpg'), quality=95)

    # 1) sin miniatura aprobada no se agrega nada (tampoco si solo está elegida para YouTube)
    assert short.miniatura_aprobada(d) is None and short.poner_miniatura_final(d, v) is None
    app.yt_elegir_miniatura(d, 'miniatura_1.jpg')
    assert short.miniatura_aprobada(d) is None and short.poner_miniatura_final(d, v, alargar=True) is None
    assert open(v, 'rb').read() == antes

    # 2) aprobada desde la app: vale; rehecha con el mismo nombre o elegida otra: hay que volver a aprobarla
    app.yt_aprobar_miniatura(d, 'miniatura_1.jpg')
    assert short.miniatura_aprobada(d) == os.path.join(d, 'miniatura_1.jpg')
    m = json.load(open(os.path.join(d, 'youtube', 'miniatura.json'), encoding='utf-8'))
    assert m['aprobada'] is True and m['archivo'] == 'miniatura_1.jpg' and m.get('aprobada_el')
    os.utime(os.path.join(d, 'miniatura_1.jpg'), (time.time() + 60, time.time() + 60))  # la rehízo
    assert short.miniatura_aprobada(d) is None
    app.yt_aprobar_miniatura(d, 'miniatura_1.jpg')
    assert short.miniatura_aprobada(d)
    app.yt_aprobar_miniatura(d, 'miniatura_1.jpg', False)  # ↺ Quitar aprobación: sigue elegida para YouTube, pero no sale
    assert short.miniatura_aprobada(d) is None and app.yt_miniatura(d) == os.path.join(d, 'miniatura_1.jpg')
    app.yt_aprobar_miniatura(d, 'miniatura_1.jpg')
    app.yt_elegir_miniatura(d, 'miniatura_1.jpg')  # elegir (otra o la misma) borra la aprobación
    assert short.miniatura_aprobada(d) is None
    app.yt_aprobar_miniatura(d, 'miniatura_1.jpg')

    # 3) dónde va: arriba al centro, sin tapar el play (abajo a la izquierda) ni la flecha que le apunta ni los subtítulos
    def cruza(a, b):
        return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
    try:
        lib = json.load(open(os.path.join(RAIZ, 'mis_conocimientos', 'logos', 'logos.json'), encoding='utf-8')).get('logos', [])
    except (OSError, ValueError):
        lib = []
    pos = next((logos.posicion(x, 'short') for x in lib if logos.posicion(x, 'short')), None) or {'x': 0.24, 'y': 0.84, 'alto': 0.11}
    alto_play = short.SH * (pos['alto'] or 0.11)
    play = (short.SW * pos['x'] - alto_play, short.SH * pos['y'] - alto_play / 2, 2 * alto_play, alto_play)  # hasta 2:1 de ancho
    fw, fh = Image.open(short.flecha_al_enlace(d)).size  # filtro_flecha: x = 0.17·W + rebote, y = 0.78·H − alto − rebote
    flecha = (short.SW * 0.17, short.SH * 0.78 - fh - 22, fw + 22, fh + 22)
    subs = (0, short.SH - 700 - 170, short.SW, 170)  # estilo C del Short: abajo al centro con MarginV 700
    for rel in (16 / 9, 4 / 3, 9 / 16):
        caja = short.caja_miniatura_final(rel)
        assert not cruza(caja, play) and not cruza(caja, flecha) and not cruza(caja, subs), (rel, caja)
        assert caja[0] >= 0 and caja[0] + caja[2] <= short.SW and caja[2] % 2 == 0 and caja[3] % 2 == 0
    x, y, w, h = short.caja_miniatura_final()

    # 4) Shorts resumen: encima del último segundo, el largo no cambia; el play y su flecha quedan a la vista
    largo = short.duracion(v)
    assert short.poner_miniatura_final(d, v) == os.path.join(d, 'miniatura_1.jpg')
    assert abs(short.duracion(v) - largo) < 0.1, short.duracion(v)
    roja = lambda f, px, py: f[py, px][2] > 180 and f[py, px][1] < 80
    assert roja(cuadro(largo - 0.3), x + w // 2, y + h // 2)  # la miniatura en el último segundo
    assert not roja(cuadro(1.0), x + w // 2, y + h // 2)  # antes, no
    final = cuadro(largo - 0.3)
    assert not roja(final, int(short.SW * pos['x']), int(short.SH * pos['y']))  # el play, libre
    assert not roja(final, int(flecha[0] + fw / 2), int(flecha[1] + fh / 2))  # la flecha, libre

    # 5) Short normal: 1 s más con el último cuadro quieto y la miniatura (con audio hasta el final)
    hacer_video()
    assert short.poner_miniatura_final(d, v, alargar=True)
    assert abs(short.duracion(v) - (largo + short.MINI_FINAL_S)) < 0.15, short.duracion(v)
    assert roja(cuadro(largo + 0.6), x + w // 2, y + h // 2) and not roja(cuadro(largo - 0.5), x + w // 2, y + h // 2)
    a = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=duration', '-of', 'csv=p=0', v],
                       capture_output=True, text=True).stdout.strip()
    assert a and float(a) > largo + 0.8, a

    # 5b) una miniatura aprobada que no se puede abrir no tumba el Short: queda como estaba
    open(os.path.join(d, 'miniatura_rota.jpg'), 'wb').write(b'no es una imagen')
    app.yt_aprobar_miniatura(d, 'miniatura_rota.jpg')
    hecho = open(v, 'rb').read()
    assert short.poner_miniatura_final(d, v, alargar=True) is None and open(v, 'rb').read() == hecho
    assert not os.path.exists(os.path.splitext(v)[0] + '_con_miniatura.mp4')

    # 6) los dos armados la usan, y el cierre sigue siendo una de las 3 frases del play (con 2 s de cola, más que el segundo)
    assert 'poner_miniatura_final' in inspect.getsource(resumen.armar) and 'poner_miniatura_final' in inspect.getsource(short.main)
    assert resumen.COLA_CIERRE >= short.MINI_FINAL_S
    r = resumen.poner_cierres({'shorts': [{'frases': [{'texto': 'Hola.', 'tomas': [[1, 3]]}]}]})
    assert r['shorts'][0]['frases'][-1]['texto'] == resumen.cierre(1) and 'play' in resumen.cierre(1)
    print('ok: 1 s con la miniatura aprobada al final de los Shorts (y nada sin aprobar)')
finally:
    shutil.rmtree(d, ignore_errors=True)
