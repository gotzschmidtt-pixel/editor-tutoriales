"""Prueba (03/11/2026): un tramo que cruza un hueco de una grabación de cuadros variables (VFR) no puede saltar.

Con ffmpeg 9 (laptop de fabian, 9.0.2 con Intel Quick Sync), el filtro framerate dejó de rellenar ese hueco: el pedazo
V10 de test_montaje_cuadros_revision saltaba ~1,4 s en el cuadro 52 y, al pegarlo, 28 tramos quedaban corridos. El arreglo
es un «fps» después de framerate. Esta prueba arma el mismo caso con la cadena de filtros de montaje.py tal cual está.
Con un ffmpeg viejo (6.x) pasa con o sin el arreglo; por eso también se revisa que la cadena lo tenga.
"""
import os, re, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fuente = open(os.path.join(RAIZ, 'montaje', 'montaje.py'), encoding='utf-8').read()
m = re.search(r'out = f"(scale=.*?)"\n', fuente)
assert m, 'no encontré la cadena «out» de montaje.py'
cadena = m.group(1)
assert re.search(r'framerate=fps=\{FPS\},fps=\{FPS\}', cadena), f'falta «fps» después de framerate: {cadena}'
assert "out_pausa = out.replace(f'framerate=fps={FPS},', '')" in fuente, 'la pausa tiene que ir solo con «fps»'
tr = open(os.path.join(RAIZ, 'trailer', 'trailer.py'), encoding='utf-8').read()
assert 'framerate=fps=25,fps=25' in tr, 'el tráiler también corta del grabado VFR: falta «fps» después de framerate'

FPS = 30
out = (cadena.replace('{res[0]}', '640').replace('{res[1]}', '360').replace('{FPS}', str(FPS)))
d = tempfile.mkdtemp(prefix='hueco_vfr_')
orig = os.path.join(d, 'orig.mp4')
pts = "settb=1/90000,setpts='(N+0.4*sin(N/3)+if(gt(N\\,1200)\\,30\\,0))/30/TB',"  # 1 s de hueco en el cuadro 1200
subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                f'nullsrc=s=320x180:r=30:d=60,format=yuv420p,{pts}drawbox=t=fill:c=gray',
                '-fps_mode', 'vfr', '-enc_time_base', '1:90000', '-video_track_timescale', '90000', '-c:v', 'libx264',
                '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-g', '30', orig], check=True)
n = 76
pedazo = os.path.join(d, 'pedazo.mp4')
subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', '38.8', '-t', '1.77', '-i', orig, '-an', '-vf',
                f'setpts=PTS/0.7,{out},tpad=stop_mode=clone:stop_duration={n / FPS + 1:.3f}', '-frames:v', str(n),
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', pedazo], check=True)
p = sorted(float(x) for x in subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                             'packet=pts_time', '-of', 'csv=p=0', pedazo],
                                            capture_output=True, text=True).stdout.split() if x not in ('', 'N/A'))
huecos = [(k + 1, round(b - a, 3)) for k, (a, b) in enumerate(zip(p, p[1:])) if b - a > 1.5 / FPS]
assert len(p) == n, f'el pedazo tiene {len(p)} cuadros y no {n}'
assert not huecos, f'el pedazo salta: {huecos[:3]}'
assert abs((p[-1] - p[0]) - (n - 1) / FPS) < 0.002, f'dura {p[-1] - p[0]:.3f} s y no {(n - 1) / FPS:.3f} s'
# el concat: cada pedazo con su «duration» exacta (n/fps), no con el largo que guardó el .mp4 (con ffmpeg 9 y solo el procesador,
# un pedazo salía 2 ms corto y desde ahí todo quedaba corrido: laptop de fabian, 03/11/2026)
sys.path.insert(0, os.path.join(RAIZ, 'montaje'))
import montaje  # noqa: E402
lista = os.path.join(d, 'lista.txt')
montaje.lista_concat(lista, ['a.mp4', 'b.mp4'], [37, 76], 30)
assert open(lista, encoding='utf-8').read() == "file 'a.mp4'\nduration 1.233333\nfile 'b.mp4'\nduration 2.533333\n", open(lista).read()
montaje.lista_concat(lista, ['a.mp4'], [1001], 30000 / 1001)
assert open(lista, encoding='utf-8').read() == "file 'a.mp4'\nduration 33.400033\n", open(lista).read()
try:
    montaje.lista_concat(lista, ['a.mp4', 'b.mp4'], [37], 30)
    raise AssertionError('con menos cuentas que pedazos tenía que parar')
except SystemExit:
    pass
assert fuente.count('lista_concat(lista, partes, cuadros, FPS)') == 1, 'el concat final tiene que llevar los cuadros de cada pedazo'
assert fuente.count('voces, cuadros, FPS)') == 2, 'la vista en vivo también'
# y pegados de verdad: el pedazo del hueco tres veces seguidas queda parejo de punta a punta
montaje.lista_concat(lista, [pedazo] * 3, [n] * 3, FPS)
junto = os.path.join(d, 'junto.mp4')
subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', junto], check=True)
q = sorted(float(x) for x in subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                             'packet=pts_time', '-of', 'csv=p=0', junto],
                                            capture_output=True, text=True).stdout.split() if x not in ('', 'N/A'))
assert len(q) == 3 * n, f'pegados son {len(q)} cuadros y no {3 * n}'
corridos = [(k, x) for k, x in enumerate(q) if abs((x - q[0]) - k / FPS) > 0.002]
assert not corridos, f'pegados se corren: {corridos[:3]}'
version = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True).stdout.splitlines()[0]
print(f'ok: {n} cuadros parejos aunque el tramo cruza el hueco, y pegados con su duración exacta ({version})')
