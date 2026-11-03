"""Revisión 3 de la mejora 1 (03/11/2026): un bloque que no tiene sitio no corre a los siguientes.

1) Un bloque que en el video dura menos de un cuadro (una imagen con "congelar_s": 0, un tramo de 0,01 s) no tiene sitio:
   antes se le daba 1 cuadro igual. Con dos así seguidos (o con el bloque de antes ya a un cuadro de su lugar, algo que se
   acepta al reutilizar un tramo guardado) el bloque siguiente quedaba 2 cuadros tarde y salía el aviso rojo «la imagen
   empieza 2 cuadros tarde… Vuelve a montar», que no se iba aunque volvieras a montar. Ahora un bloque sin sitio no pone
   nada y el siguiente cae en su cuadro, también al volver a montar con lo ya hecho.
2) Los bloques normales siguen igual: cada uno en su cuadro y el video dura lo del guion.
3) El aviso rojo del montaje (avisos_montaje.json) se borra con su video en «🔁 Rehacer video» y en «▶ Hacer todo»
   (app.VIDEOS_GENERADOS): antes quedaba a la vista sin video.
4) Si el primer bloque no tiene sitio, el registro del paso no trae errores de ffmpeg («No files to concat… avance.txt»):
   la vista en vivo espera al primer bloque que pone algo.
Sin internet y sin gastar nada: un video sintético en una carpeta temporal (tus proyectos no se tocan).
Uso: python tests/test_montaje_sin_sitio.py   (sale con 1 si algo falla)
"""
import ast, contextlib, glob, io, json, os, shutil, subprocess, sys, tempfile

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'montaje'))
import montaje  # noqa: E402

montaje._DETECTOR.append(None)  # sin el detector de caras (no se baja nada de internet)
FPS = 30
W, H = 640, 360  # --calidad 360
fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


# el segundo de la grabación (en centésimas, base 32) escrito en tres franjas grises: así se lee qué se ve en cada cuadro
ESCRITO = ("geq=lum='16+7*if(lt(Y\\,H/3)\\,mod(round(T*100)\\,32)\\,if(lt(Y\\,2*H/3)\\,mod(floor(round(T*100)/32)\\,32)\\,"
           "floor(round(T*100)/1024)))':cb=128:cr=128")


def que_se_ve(video):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-'],
                       capture_output=True, check=True)
    cuadros = np.frombuffer(r.stdout, np.uint8).reshape(-1, H * W * 3 // 2)[:, :H * W].reshape(-1, H, W)
    out = []
    for c in cuadros:
        ds = []
        for k in range(3):
            y = H * (2 * k + 1) // 6
            zona = c[y - H // 18:y + H // 18, 3 * W // 4:19 * W // 20].astype(float)
            v = (float(np.median(zona)) - 16) / 7
            ds.append(None if zona.std() > 6 or abs(v - round(v)) > 0.35 else int(round(v)))
        out.append(None if None in ds else (ds[0] + 32 * ds[1] + 1024 * ds[2]) / 100)
    return out


def bloque(i, modo, a=None, z=None, v=1.0, pausa=None, **extra):
    m = {'modo': modo, 'src_inicio': a, 'src_fin': z, 'velocidad': v, 'encuadre': 'fijo', 'repetir': 'ida_vuelta'}
    if pausa is not None:
        m['congelar_s'] = pausa
    m.update(extra)
    return {'id': i, 'ancla': f'bloque {i}', 'texto': '', 'montaje': m}


def tiempos(bloques):
    """inicio_min y fin_max como los pone voz.ajustar_guion (redondeados a 0,01 s)."""
    t = 0.0
    for b in bloques:
        largo = montaje.largo_tramo(b['montaje']) + (b['montaje'].get('congelar_s') or 0)
        b['inicio_min'], b['fin_max'] = round(t, 2), round(t + largo, 2)
        t += largo
    return bloques


def armar(d, bloques):
    json.dump({'bloques': bloques}, open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    antes, argv, salida = os.getcwd(), sys.argv, io.StringIO()
    os.chdir(d)
    try:
        sys.argv = ['montaje.py', '--original', 'original.mp4', '--guion', 'guion.json', '--salida', '1_montaje.mp4', '--calidad', '360']
        with contextlib.redirect_stdout(salida):
            montaje.main()
    finally:
        sys.argv = argv
        os.chdir(antes)
    return salida.getvalue()


def donde_empieza(d, bloques):
    """[(id, cuadro donde empieza en 1_montaje.mp4, cuadro de su inicio_min)] según los tramos guardados."""
    pos, filas = 0, []
    for b in bloques:
        hechos = glob.glob(os.path.join(d, montaje.PARTES, f"{b['id']}_*.json"))
        filas.append((b['id'], pos, round(b['inicio_min'] * FPS)))
        pos += sum(json.load(open(hechos[0], encoding='utf-8'))['cuadros']) if len(hechos) == 1 else 0
    return filas


tmp = tempfile.mkdtemp(prefix='montaje sin sitio ')  # con espacio, como las carpetas de fabian
try:
    d = os.path.join(tmp, 'proyecto')
    os.makedirs(d)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'nullsrc=s=320x180:r={FPS}:d=20,format=yuv420p,{ESCRITO}',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-g', '30', os.path.join(d, 'original.mp4')], check=True)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240', '-frames:v', '1',
                    os.path.join(d, 'mapa.png')], check=True)
    img = os.path.join(d, 'mapa.png')
    f_av = os.path.join(d, montaje.AVISOS_MONTAJE)

    # 1) dos imágenes sin sitio entre dos tramos, y dos tramos de 0,01 s (uno sin sitio: 2,00 → 2,01 s cae en el mismo cuadro)
    for nombre, bl in (('imágenes de 0 s', [bloque('S01', 'lento', 1.0, 3.0), bloque('S02', 'imagen', pausa=0.0, imagen=img),
                                            bloque('S03', 'imagen', pausa=0.0, imagen=img), bloque('S04', 'lento', 5.0, 7.0),
                                            bloque('S05', 'lento+congelar', 8.0, 9.5, 1.37, 0.7)]),
                       ('tramos de 0,01 s', [bloque('T01', 'lento', 1.0, 3.0), bloque('T02', 'lento', 4.0, 4.01),
                                             bloque('T03', 'lento', 5.0, 5.01), bloque('T04', 'lento', 6.0, 8.0),
                                             bloque('T05', 'lento+congelar', 8.0, 9.5, 1.37, 0.7)])):
        bl = tiempos(bl)
        esperado = round(montaje.tiempos_bloques(bl)[0][-1] * FPS)  # donde termina el último bloque (lo que mide el montaje)
        for vuelta in ('desde cero', 'con lo ya hecho'):
            log = armar(d, bl)
            filas = donde_empieza(d, bl)
            peor = max(filas, key=lambda f: abs(f[1] - f[2]))
            ok(abs(peor[1] - peor[2]) <= 1, f'1) {nombre}, {vuelta}: {peor[0]} empieza {peor[1] - peor[2]:+d} cuadros de su lugar: {filas}')
            ok('AVISO' not in log and not os.path.exists(f_av), f'1) {nombre}, {vuelta}: avisó sin motivo:\n'
               + '\n'.join(x for x in log.splitlines() if 'AVISO' in x))
            se_ve = que_se_ve(os.path.join(d, '1_montaje.mp4'))
            ok(len(se_ve) == esperado, f'1) {nombre}, {vuelta}: el montaje tiene {len(se_ve)} cuadros y el guion {esperado}')
            for b in (bl[3], bl[4]):  # los tramos de después de los bloques sin sitio: su primer cuadro es su src_inicio
                n = round(b['inicio_min'] * FPS)
                x = se_ve[n] if n < len(se_ve) else None
                ok(x is not None and abs(x - b['montaje']['src_inicio']) <= 0.06,
                   f'1) {nombre}, {vuelta}: en el cuadro {n} ({b["id"]}) se ve {x} y tendría que verse {b["montaje"]["src_inicio"]}')

    # 2) un guion normal (sin bloques sin sitio) sigue igual: cada bloque en su cuadro, sin aviso
    bl = tiempos([bloque('N01', 'congelar', 1.0, None, 1.0, 0.77), bloque('N02', 'lento', 2.0, 3.37, 1.37),
                  bloque('N03', 'imagen', pausa=0.33, imagen=img), bloque('N04', 'lento+congelar', 5.0, 7.0, 0.83, 1.11, quieto=True),
                  bloque('N05', 'lento', 9.0, 9.2, 1.0), bloque('N06', 'lento', 10.0, 13.0, 2.71)])
    log = armar(d, bl)
    filas = donde_empieza(d, bl)
    ok(all(f[1] == f[2] for f in filas), f'2) bloques fuera de su cuadro: {filas}')
    ok('AVISO' not in log and not os.path.exists(f_av), f'2) avisó sin motivo:\n{log}')
    ok(montaje.cuadros_de(os.path.join(d, '1_montaje.mp4')) == round(montaje.tiempos_bloques(bl)[0][-1] * FPS), '2) el montaje no dura lo del guion')

    # 3) «🔁 Rehacer video» y «▶ Hacer todo» borran el aviso rojo junto con el video
    arbol = ast.parse(open(os.path.join(RAIZ, 'app', 'app.py'), encoding='utf-8').read())
    generados = next(ast.literal_eval(n.value) for n in arbol.body if isinstance(n, ast.Assign)
                     and any(getattr(t, 'id', '') == 'VIDEOS_GENERADOS' for t in n.targets))
    ok(montaje.AVISOS_MONTAJE in generados and '1_montaje.mp4' in generados,
       f'3) {montaje.AVISOS_MONTAJE} no se borra con su video (VIDEOS_GENERADOS): {generados}')

    # 4) el primer bloque sin sitio: el registro del paso (como lo corre la app) no trae errores de ffmpeg de la vista en vivo
    bl = tiempos([bloque('A01', 'imagen', pausa=0.0, imagen=img), bloque('A02', 'lento', 1.0, 3.0)])
    json.dump({'bloques': bl}, open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    r = subprocess.run([sys.executable, os.path.join(RAIZ, 'montaje', 'montaje.py'), '--original', 'original.mp4', '--guion', 'guion.json',
                        '--salida', '1_montaje.mp4', '--calidad', '360'], cwd=d, capture_output=True, text=True)
    ok(r.returncode == 0, f'4) el montaje falló:\n{r.stdout}\n{r.stderr}')
    ok('avance.txt' not in r.stderr and 'No files to concat' not in r.stderr,
       f'4) con el primer bloque sin sitio, ffmpeg escribe errores en el registro:\n{r.stderr}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLAS:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('ok: un bloque sin sitio no corre a los siguientes (ni al volver a montar) y el aviso rojo se va con su video')
