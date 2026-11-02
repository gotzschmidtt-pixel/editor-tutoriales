"""Prueba rápida del inicio fijo: varias etiquetas seguidas en el tramo del inicio hecho aparte se redibujan juntas en una
pila (una debajo de la otra), como en el armado, y no una encima de la otra en el mismo lugar.
Sin internet y sin gastar nada: ffmpeg y el dibujo con Node van simulados, y todo va a una carpeta temporal (tus proyectos
no se tocan).
Uso: python tests/test_revision_pendientes_inicio.py   (sale con 1 si algo falla)
"""
import importlib.util, json, os, re, shutil, sys, tempfile, types

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('inicio_fijo', os.path.join(RAIZ, 'inicio', 'inicio_fijo.py'))
fijo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fijo)

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


# lo que se le pide a Node (cada pila de etiquetas que se dibuja) y a ffmpeg (dónde y cuándo se pega cada una)
dibujos, ffmpeg = [], []


def node_falso(cmd, **kw):
    if any(str(x).endswith('render_frames.js') for x in cmd):
        dibujos.append(json.loads(cmd[4]))  # [carpeta, duración, items, lado, recorte] después de node y el .js
    return types.SimpleNamespace(returncode=0, stdout='', stderr='')


def ff_falso(*a):
    ffmpeg.append(list(a))
    open(a[-1], 'wb').write(b'video')  # la salida temporal, que después reemplaza al FINAL


fijo.subprocess = types.SimpleNamespace(run=node_falso)
fijo.ff = ff_falso
fijo.duracion = lambda f: 100.0

TRES = (('AliExpress', 10.0), ('Mercado Libre', 11.5), ('Colombia', 13.0))  # pocos segundos entre una y otra (4 s cada una)

antes = os.getcwd()
tmp = tempfile.mkdtemp(prefix='prueba_inicio_fijo_')
try:
    d = os.path.join(tmp, 'HONOR 8 LITE')
    os.makedirs(os.path.join(d, 'prueba_inicio'))
    os.makedirs(os.path.join(d, 'vista_extras'))
    open(os.path.join(d, 'prueba_inicio', 'inicio.mp4'), 'wb').write(b'inicio')
    open(os.path.join(d, 'FINAL.mp4'), 'wb').write(b'final')
    json.dump({'video': 'prueba_inicio/inicio.mp4', 'hasta': 60}, open(os.path.join(d, 'inicio_fijo.json'), 'w'))
    json.dump([{'bloque': 'L01', 'frase': x, 'tipo': 'dato', 'titulo': None, 'texto': x, 'dur': 4} for x, _ in TRES],
              open(os.path.join(d, 'etiquetas.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump([{'clase': 'etiqueta', 'idx': i, 't': t, 'aviso': None} for i, (_, t) in enumerate(TRES)],
              open(os.path.join(d, 'vista_extras', 'lista.json'), 'w', encoding='utf-8'))
    os.chdir(d)
    sys.argv = ['inicio_fijo.py', '--entrada', 'FINAL.mp4', '--salida', 'FINAL.mp4']
    fijo.main()

    ok(len(ffmpeg) == 1, f'ffmpeg se llamó {len(ffmpeg)} veces')
    filtro = ffmpeg[0][ffmpeg[0].index('-filter_complex') + 1] if ffmpeg else ''
    pegadas = re.findall(r'setpts=PTS\+([\d.]+)/TB\[e\d+\];\[v\d+\]\[e\d+\]overlay=(\d+):(\d+)', filtro)
    ok(len(pegadas) == len(dibujos), f'{len(dibujos)} dibujos y {len(pegadas)} pegadas en el video')
    # cada etiqueta: en qué lugar de la pantalla queda (x, y de su pila y su puesto en la pila) y en qué segundo entra
    donde = {}
    for pila, (ini, x, y) in zip(dibujos, pegadas):
        for puesto, e in enumerate(pila):
            donde.setdefault(e['texto'], []).append(((int(x), int(y), puesto), round(float(ini) + float(e.get('at') or 0), 2)))
    ok(sorted(donde) == sorted(x for x, _ in TRES), f'etiquetas redibujadas: {sorted(donde)}')
    ok(all(len(v) == 1 for v in donde.values()), f'alguna etiqueta se dibuja dos veces: {donde}')
    lugares = [v[0][0] for v in donde.values()]
    ok(len(set(lugares)) == len(TRES), f'las tres etiquetas seguidas quedan en el mismo lugar, una encima de la otra: {lugares}')
    for x, t in TRES:  # y cada una sigue entrando cuando la dice la voz
        if donde.get(x):
            ok(abs(donde[x][0][1] - t) < 0.05, f'«{x}» entra en el segundo {donde[x][0][1]} y no en el {t}')
finally:
    os.chdir(antes)
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLA:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('ok: inicio fijo (tres etiquetas seguidas se redibujan juntas en una pila, sin encimarse)')
