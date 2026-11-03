"""Shorts (fabian, 02/11/2026):
- «¿por qué no se muestran flechas y círculos, sobre todo en Omitir?»: las del video largo se pasan a la grabación y se pegan
  ANTES del recorte vertical, en su segundo;
- «tarjetas individuales para Short y video largo, están muy pequeñas»: la tarjeta de WhatsApp tiene su tamaño por formato;
- el cierre: 3 frases que rotan, el ícono de play solo en Shorts y una flecha hacia el enlace de abajo."""
import json, os, shutil, subprocess, sys, tempfile
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for m in ('short', 'senales', 'logos'):
    sys.path.insert(0, os.path.join(RAIZ, m))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
import logos  # noqa: E402
import resumen  # noqa: E402
import senales  # noqa: E402
import short  # noqa: E402

d = tempfile.mkdtemp()

# 1. del video largo a la grabación: lo contrario de segundo_montado
bloques = [{'id': 'L1', 'inicio_min': 10.0, 'montaje': {'modo': 'lento', 'src_inicio': 100, 'src_fin': 110, 'velocidad': 2}},
           {'id': 'L2', 'inicio_min': 20.0, 'montaje': {'modo': 'congelar', 'src_inicio': 200, 'src_fin': 205}}]
assert senales.segundo_grabado(bloques, 12.0) == 104.0 and senales.segundo_montado(bloques, 104.0) == 12.0
assert senales.segundo_grabado(bloques, 21.0) is None  # un congelado no es la grabación andando
assert senales.en_el_video({'t': 30, 'retraso': 0.5}, {}, {}, d, 0.3) == (30.5, None)
assert senales.en_el_video({'en': 2, 'bloque': 'L1'}, {'L1': 10.0}, {}, d, 0.3) == (12.3, None)
assert senales.en_el_video({'bloque': 'L9', 'frase': 'Omitir'}, {'L1': 10.0}, {}, d, 0.3)[0] is None

# senales.json con src_t (la IA mirando la grabación) pasa tal cual; sin guion ni senales.json, nada
json.dump({'bloques': bloques}, open(os.path.join(d, 'guion.json'), 'w'))
json.dump([{'tipo': 'circulo', 'x': 1000, 'y': 500, 'src_t': 50, 'retraso': 0.2, 'frase': 'Omitir'},
           {'tipo': 'etiqueta', 'x': 1, 'y': 1, 'src_t': 3}], open(os.path.join(d, 'senales.json'), 'w'))
sg = short.senales_grabado(d)
assert len(sg) == 1 and sg[0]['src'] == 50.2, sg
assert short.senales_grabado(tempfile.mkdtemp()) == []

# 2. el círculo se pega sobre la grabación antes del recorte: sale en el trozo que lo contiene y en su segundo
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=gray:s=1920x1080:r=30:d=6', '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p', os.path.join(d, 'orig.mp4')], check=True)
os.makedirs(os.path.join(d, 'fr'))
for i in range(50):  # 2 s a 25 cuadros, como Remotion
    im = Image.new('RGBA', (1920, 1080), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((920, 420, 1080, 580), outline=(255, 0, 0, 255), width=14)
    im.save(os.path.join(d, 'fr', f'{i:03d}.png'))
mov = os.path.join(d, 'senal.mov')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '25', '-i', os.path.join(d, 'fr', '%03d.png'), '-c:v', 'qtrle',
                '-pix_fmt', 'argb', mov], check=True)
dib = [{'src': 2.0, 'dur': 2.0, 'archivo': mov, 'x': 1000, 'y': 500}]


def rojo_desde(s0, dur):
    ins, filtro, ult = short.con_senales(s0, dur, dib, 1)
    vf = "crop=404:720:x='800':y='140',scale=1080:1920,setsar=1,fps=30,format=yuv420p"
    p = os.path.join(d, f'trozo_{s0}.mp4')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(s0), '-t', str(dur), '-i', os.path.join(d, 'orig.mp4')] + ins +
                   ['-filter_complex', f'{filtro}[{ult}]{vf}[v]', '-map', '[v]', '-t', str(dur), '-an', p], check=True)
    cap, rojos = cv2.VideoCapture(p), []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        rojos.append(bool(((f[:, :, 2] > 180) & (f[:, :, 1] < 80)).sum()))
    return (rojos.index(True) / 30 if True in rojos else None), len(rojos)


assert short.con_senales(5.0, 1.0, dib, 1) == ([], '', '0:v')  # el trozo no la toca: el filtro de siempre
desde, n = rojo_desde(1.0, 2.0)  # empieza a la mitad del trozo
assert desde is not None and 0.9 <= desde <= 1.1 and n >= 58, (desde, n)
desde, n = rojo_desde(3.0, 1.5)  # ya había empezado: se ve desde el primer cuadro
assert desde == 0.0 and n >= 43, (desde, n)

# 3. la tarjeta de WhatsApp: más grande y con su tamaño en cada formato; el ícono de play solo en Shorts
tarjeta = {'nombre': 'Soporte WhatsApp', 'archivo': 'whatsapp.png', 'queda': 6}
play = {'nombre': 'Play', 'archivo': 'play.png', 'palabras': ['play'], 'solo_short': True}
assert logos.es_tarjeta(tarjeta) and not logos.es_tarjeta(play) and not logos.es_tarjeta({'nombre': 'Android 15', 'archivo': 'a.png'})
assert not logos.es_tarjeta(dict(tarjeta, tarjeta=False)) and logos.es_tarjeta({'archivo': 'x.png', 'tarjeta': True})
assert logos.para_formato([tarjeta, play], 'largo') == [tarjeta] and logos.para_formato([tarjeta, play], 'short') == [tarjeta, play]
ancho_l, alto_l = logos.medida_tarjeta(tarjeta, 'largo', 1920, 1080, 1.0)
ancho_s, alto_s = logos.medida_tarjeta(tarjeta, 'short', 1080, 1920, 1.0)
assert alto_l >= 1080 * 0.75 > 1080 * 0.5, alto_l           # antes: el 50 % del alto, como cualquier logo
assert ancho_s >= 1080 * 0.85 > 1080 * 0.6, ancho_s         # antes: ~560 px de 1080
assert 1920 * 0.30 + alto_s / 2 < 1920 - 700 - 126          # no pisa los subtítulos del Short
assert logos.medida_tarjeta(dict(tarjeta, alto_largo=0.5), 'largo', 1920, 1080, 1.0)[1] == 540
# se va cuando termina la frase que la nombra (no tapa la KEY que viene después), pero dura al menos 2,5 s
dichas = [(30.0, 35.8), (35.9, 42.0)]
assert logos.fin_tarjeta(35.5, 40.0, dichas) == 38.0      # «WhatsApp» al final de la frase: el mínimo para leerla
assert logos.fin_tarjeta(31.0, 35.5, dichas) == 35.5      # a mitad de frase: su tope de siempre
assert logos.fin_tarjeta(31.0, 40.0, [(30.0, 39.0)]) == 39.2  # la frase sigue: hasta que termina
assert logos.fin_tarjeta(50.0, 54.0, dichas) == 54.0      # sin frase conocida: lo de siempre
os.makedirs(os.path.join(d, 'voz'))
json.dump({'characters': list('hola'), 'character_start_times_seconds': [0, .1, .2, .3],
           'character_end_times_seconds': [.1, .2, .3, 1.4]}, open(os.path.join(d, 'voz', 'L1.align.json'), 'w'))
assert logos.frases({'bloques': [{'id': 'L1', 'inicio_min': 10.0}, {'id': 'L2', 'inicio_min': 20.0}]}, os.path.join(d, 'voz'), 0.1) == [(10.1, 11.5)]
open(os.path.join(d, 'whatsapp.png'), 'wb').write(b'x')
open(os.path.join(d, 'whatsapp_vertical.png'), 'wb').write(b'x')
t2 = dict(tarjeta, archivo_short='whatsapp_vertical.png')
assert logos.del_idioma(t2, d, 'es', 'short') == 'whatsapp_vertical.png' and logos.del_idioma(t2, d, 'es') == 'whatsapp.png'

# 4. el cierre rota y la flecha apunta al enlace de abajo, solo mientras se dice
assert [resumen.cierre(n) for n in (1, 2, 3, 4)] == resumen.CIERRES['es'] + [resumen.CIERRES['es'][0]]
assert all(len(v) == 3 for v in resumen.CIERRES.values()) and set(resumen.CIERRES) == {'es', 'en', 'pt'}
r = {'shorts': [{'frases': [{'texto': 'Hola.', 'tomas': [[1, 4]]}, {'texto': 'El tutorial completo está en mi canal.', 'tomas': [[9, 12]]}]},
                {'frases': [{'texto': 'Paso uno.', 'tomas': [[2, 5]]}]}]}
resumen.poner_cierres(r)
assert r['shorts'][0]['frases'][-1] == {'texto': resumen.cierre(1), 'tomas': [[9, 12]]} and len(r['shorts'][0]['frases']) == 2
assert r['shorts'][1]['frases'][-1] == {'texto': resumen.cierre(2), 'tomas': [[2, 5]]}
assert not any('cierre fijo' in a for a in resumen.validar(r))
assert any('cierre fijo' in a for a in resumen.validar({'shorts': [{'frases': [{'texto': 'Chao.', 'tomas': [[1, 2]]}]}]}))
assert 'comentario fijado' not in resumen.FIN['es'] and 'play' in resumen.FIN['es']
png = short.flecha_al_enlace(d)
im = np.array(Image.open(png))
ys, xs = np.nonzero(im[:, :, 3] > 128)
assert ys[xs.argmin()] > im.shape[0] * 0.6  # la punta (lo más a la izquierda) queda abajo: apunta abajo a la izquierda
fondo = os.path.join(d, 'fondo.mp4')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1080x1920:r=30:d=3', '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p', fondo], check=True)
out = os.path.join(d, 'con_flecha.mp4')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', fondo, '-loop', '1', '-i', png, '-filter_complex',
                short.filtro_flecha(1, '0:v', 1.5, 3.0, 'v'), '-map', '[v]', out], check=True)
cap = cv2.VideoCapture(out)
cuadros = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    cuadros.append(f)
assert 85 <= len(cuadros) <= 92, len(cuadros)  # la imagen fija (-loop 1) no alarga el video
assert cuadros[15].max() < 30 and cuadros[75].max() > 150  # antes del cierre no está; durante, sí
ys, xs = np.nonzero(cuadros[75].max(axis=2) > 150)
assert xs.min() < 1080 * 0.4 and ys.max() > 1920 * 0.6  # abajo a la izquierda

# 5. (03/11/2026) el ícono de play va abajo a la izquierda, junto al enlace («pos_short»); los demás, en el centro
assert logos.posicion(dict(play, pos_short={'x': 0.24, 'y': 0.84, 'alto': 0.11}), 'short') == {'x': 0.24, 'y': 0.84, 'alto': 0.11}
assert logos.posicion(dict(play, pos_short={'x': 0.24, 'y': 0.84, 'alto': 0.11}), 'largo') is None
assert logos.posicion(play, 'short') is None and logos.posicion(dict(play, pos_short={'x': 2, 'y': 0.8}), 'short') is None
assert logos.posicion(dict(play, pos_short={'y': 0.8}), 'short') == {'x': 0.5, 'y': 0.8, 'alto': None}
lib = os.path.join(d, 'lib')
os.makedirs(lib)
im = Image.new('RGBA', (300, 220), (0, 0, 0, 0))
ImageDraw.Draw(im).rounded_rectangle((0, 0, 299, 219), 40, fill=(255, 0, 0, 255))
im.save(os.path.join(lib, 'play.png'))
json.dump({'logos': [dict(play, pos_short={'x': 0.24, 'y': 0.84, 'alto': 0.11})]}, open(os.path.join(lib, 'logos.json'), 'w'))
vid = os.path.join(d, 'voz2')
os.makedirs(vid)
txt = 'toca el play'
json.dump({'characters': list(txt), 'character_start_times_seconds': [i * 0.05 for i in range(len(txt))],
           'character_end_times_seconds': [i * 0.05 + 0.05 for i in range(len(txt))]}, open(os.path.join(vid, 'B1.align.json'), 'w'))
json.dump({'bloques': [{'id': 'B1', 'texto': txt, 'inicio_min': 0.5}]}, open(os.path.join(d, 'guion_play.json'), 'w'))
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1080x1920:r=30:d=4', '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p', os.path.join(d, 'negro.mp4')], check=True)
subprocess.run([sys.executable, os.path.join(RAIZ, 'logos', 'logos.py'), '--video', os.path.join(d, 'negro.mp4'), '--guion',
                os.path.join(d, 'guion_play.json'), '--voz', vid, '--logos', lib, '--salida', os.path.join(d, 'con_play.mp4'),
                '--alto', '0.30', '--centro-y', '0.3', '--queda-max', '3', '--formato', 'short'], check=True, capture_output=True)
cap = cv2.VideoCapture(os.path.join(d, 'con_play.mp4'))
cap.set(cv2.CAP_PROP_POS_MSEC, 2000)
ok, f = cap.read()
ys, xs = np.nonzero((f[:, :, 2] > 180) & (f[:, :, 1] < 80))
assert ok and len(ys), 'el play no salió'
assert 1920 * 0.76 < ys.mean() < 1920 * 0.92 and 1080 * 0.12 < xs.mean() < 1080 * 0.36, (ys.mean(), xs.mean())  # abajo a la izquierda
assert 1920 * 0.09 < ys.max() - ys.min() < 1920 * 0.13, ys.max() - ys.min()  # con su alto propio (0,11), no el 0,30 de los logos

# 6. el cierre: las flechas que caerían debajo de la tarjeta de WhatsApp no se dibujan
frases_t = [(0.1, [(0.0, 0.4, 'Paso'), (0.5, 0.9, 'uno.')]),
            (3.1, [(0.0, 0.3, 'Escríbeme'), (0.4, 0.6, 'al'), (0.7, 1.2, 'WhatsApp'), (1.3, 1.6, 'hoy.')])]
assert short.ventanas_tarjeta(frases_t) == [(3.8, 6.3)]  # desde «WhatsApp», mínimo 2,5 s
assert short.ventanas_tarjeta([(0, [(0, 1, 'Hola'), (1, 6, 'wasap'), (6, 9, 'listo')])]) == [(1, 9.2)]  # hasta que termina la frase
assert short.ventanas_tarjeta(frases_t[:1]) == []
flechas = [{'src': 102.0, 'dur': 2.0}, {'src': 110.0, 'dur': 1.0}]
# trozo que empieza en el segundo 3 del Short y en el 100 de la grabación: la 1.ª cae en 5-7 (tapada), la 2.ª en 13-14
assert short.sin_tapar(flechas, 100.0, 3.0, [(3.8, 6.3)]) == [flechas[1]]
assert short.sin_tapar(flechas, 100.0, 3.0, []) == flechas
assert short.sin_tapar(flechas, 100.0, 10.0, [(3.8, 6.3)]) == flechas
assert resumen.COLA_CIERRE >= 1.5  # el play y la flecha al enlace se alcanzan a ver después de la última palabra
shutil.rmtree(d, ignore_errors=True)
print('ok: flechas y círculos en los Shorts, tarjeta de WhatsApp por formato, cierre con play abajo junto al enlace')
