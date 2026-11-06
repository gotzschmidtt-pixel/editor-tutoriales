"""Prueba de la mejora 1 (fabian, 03/11/2026): la imagen del montaje ya no se atrasa respecto de la voz.

Antes cada tramo «lento» salía casi un cuadro más largo de lo calculado y la diferencia se sumaba (+0,7 s a los 4 min):
Mauricio decía «pulsamos» y el clic llegaba un segundo después. Ahora cada bloque empieza en el cuadro de su inicio_min
(donde ya caen la voz, los subtítulos, las etiquetas y los clics). Aquí se arma un guion de 13 bloques (tramos a varias
velocidades, pausas en movimiento, quieta, con «cara», la rotación del inicio, una imagen y encuadres) con videos
sintéticos de 60 y 30 cuadros por segundo, y se mide en qué cuadro empieza cada bloque.
También: al cambiar un bloque, los tramos guardados de los demás se reutilizan sin correrse; un guion con los tiempos
viejos deja el aviso en avisos_montaje.json (lo muestra la vista previa) y la revisión con ffprobe avisa si no coincide.
Sin internet y sin gastar nada: todo va a una carpeta temporal (tus proyectos no se tocan).
Uso: python tests/test_imagen_sin_atraso.py   (sale con 1 si algo falla)
"""
import contextlib, glob, io, json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'montaje'))
import montaje  # noqa: E402

montaje._DETECTOR.append(None)  # sin el detector de caras (no se baja nada de internet): las pausas van de ida y vuelta
FPS = 30
fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def cuadros(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries',
                        'stream=nb_read_packets', '-of', 'csv=p=0', f], capture_output=True, text=True, check=True)
    return int(r.stdout.strip())


def bloque(i, modo, a=None, z=None, v=1.0, pausa=None, **extra):
    m = {'modo': modo, 'src_inicio': a, 'src_fin': z, 'velocidad': v}
    if pausa is not None:
        m['congelar_s'] = pausa
    m.update(extra)
    return {'id': i, 'ancla': f'bloque {i}', 'texto': '', 'montaje': m}


def guion():
    return [bloque('L01', 'lento', 1.0, 3.37, 1.0),
            bloque('L02', 'lento+congelar', 3.5, 7.13, 1.37, 1.29),
            bloque('L03', 'lento', 8.0, 15.55, 2.0),
            bloque('L04', 'lento+congelar', 16.0, 19.9, 0.7, 7.0),  # pausa larga del inicio: rota trozos del grabado
            bloque('L05', 'lento', 21.0, 33.3, 3.1),
            bloque('L06', 'congelar', 35.0, None, 1.0, 2.21),
            bloque('L07', 'lento', 36.0, 52.71, 1.0),  # más de 15 s de la misma toma: cambia el encuadre
            bloque('L08', 'lento+congelar', 53.0, 57.77, 1.8, 0.53),
            bloque('L09', 'lento', 58.0, 61.1, 0.5),
            bloque('L10', 'lento+congelar', 62.0, 66.66, 1.0, 3.3, quieto=True),
            bloque('L11', 'lento', 67.0, 80.9, 1.37),
            bloque('L12', 'imagen', 81.0, None, 1.0, 1.77, imagen='mapa.png'),
            bloque('L13', 'lento+congelar', 82.0, 95.43, 1.0, 2.07, repetir='adelante')]


def tiempos(bloques):
    """inicio_min y fin_max como los pone voz.ajustar_guion (redondeados a 0,01 s)."""
    t = 0.0
    for b in bloques:
        m = b['montaje']
        largo = ((m['src_fin'] - m['src_inicio']) / m['velocidad'] if m['modo'].startswith('lento') else 0) + (m.get('congelar_s') or 0)
        b['inicio_min'], b['fin_max'] = round(t, 2), round(t + largo, 2)
        t += largo
    return bloques


def armar(d, bloques, guion='guion.json', video='1_montaje.mp4'):
    """Arma el video (1_montaje.mp4, o la prueba de unos bloques) y devuelve lo que escribió el paso."""
    json.dump({'bloques': bloques}, open(os.path.join(d, guion), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    antes, argv, salida = os.getcwd(), sys.argv, io.StringIO()
    os.chdir(d)
    try:
        sys.argv = ['montaje.py', '--original', 'original.mp4', '--guion', guion, '--salida', video, '--calidad', '360']
        with contextlib.redirect_stdout(salida):
            montaje.main()
    finally:
        sys.argv = argv
        os.chdir(antes)
    return salida.getvalue()


def medir(d, bloques):
    """[(id, cuadro donde empieza en 1_montaje.mp4, cuadro donde tendría que empezar)] y los cuadros del video entero."""
    cache, pos, filas = os.path.join(d, montaje.PARTES), 0, []
    for b in bloques:
        hechos = glob.glob(os.path.join(cache, f"{b['id']}_*.json"))
        if len(hechos) != 1:
            raise RuntimeError(f"{b['id']}: {len(hechos)} tramos guardados")
        filas.append((b['id'], pos, round(b['inicio_min'] * FPS)))
        pos += sum(cuadros(os.path.join(cache, p)) for p in json.load(open(hechos[0], encoding='utf-8'))['partes'])
    return filas, pos


tmp = tempfile.mkdtemp(prefix='imagen_sin_atraso_')
try:
    for fps_src in (60, 30):
        d = os.path.join(tmp, f'p{fps_src}')
        os.makedirs(d)
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=size=320x180:rate={fps_src}', '-t', '100',
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', os.path.join(d, 'original.mp4')], check=True)
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240', '-frames:v', '1',
                        os.path.join(d, 'mapa.png')], check=True)
        json.dump({'cuadros': [{'t': t, 'texto': 'verifica tu cuenta de google'} for t in (40, 50, 60, 70, 85)]},
                  open(os.path.join(d, 'mapa_video.json'), 'w', encoding='utf-8'))
        bl = tiempos(guion())
        for b in bl:
            if b['montaje'].get('imagen'):
                b['montaje']['imagen'] = os.path.join(d, 'mapa.png')

        # 1) armado desde cero: ningún bloque corrido más de 1 cuadro, y el video dura lo que dice el guion
        armar(d, bl)
        filas, total = medir(d, bl)
        peor = max(filas, key=lambda f: abs(f[1] - f[2]))
        print(f'{fps_src} cps: el bloque más corrido es {peor[0]} ({peor[1] - peor[2]:+d} cuadros); total {total} cuadros, '
              f'guion {round(bl[-1]["fin_max"] * FPS)}')
        ok(abs(peor[1] - peor[2]) <= 1, f'{fps_src} cps: {peor[0]} empieza {peor[1] - peor[2]:+d} cuadros corrido: {filas}')
        real = cuadros(os.path.join(d, '1_montaje.mp4'))
        ok(abs(real - round(bl[-1]['fin_max'] * FPS)) <= 1, f'{fps_src} cps: 1_montaje.mp4 tiene {real} cuadros y el guion dice {round(bl[-1]["fin_max"] * FPS)}')
        ok(real == total, f'{fps_src} cps: al unir los tramos se perdieron cuadros ({total} → {real})')
        ok(not os.path.exists(os.path.join(d, montaje.AVISOS_MONTAJE)), f'{fps_src} cps: dejó un aviso sin motivo: '
           + (open(os.path.join(d, montaje.AVISOS_MONTAJE), encoding='utf-8').read() if os.path.exists(os.path.join(d, montaje.AVISOS_MONTAJE)) else ''))
        ok(all(json.load(open(f, encoding='utf-8')).get('cuadros') for f in glob.glob(os.path.join(d, montaje.PARTES, '*.json'))),
           f'{fps_src} cps: los tramos guardados no anotan sus cuadros')

        # 2) cambias la pausa de un bloque del medio (un largo que no es un número entero de cuadros): los demás bloques se
        #    reutilizan y ninguno queda corrido
        #    (los que cambian de encuadre se rehacen igual que antes: su encuadre depende del minuto del video)
        guardados = set(os.listdir(os.path.join(d, montaje.PARTES)))
        bl[5]['montaje']['congelar_s'] = 2.6234
        bl = tiempos(bl)
        log = armar(d, bl)
        filas, total = medir(d, bl)
        peor = max(filas, key=lambda f: abs(f[1] - f[2]))
        ok(abs(peor[1] - peor[2]) <= 1, f'{fps_src} cps, con un bloque cambiado: {peor[0]} empieza {peor[1] - peor[2]:+d} cuadros corrido')
        rehechos = sorted({x.split('_')[0] for x in set(os.listdir(os.path.join(d, montaje.PARTES))) - guardados if x.endswith('.json')})
        print(f'{fps_src} cps: con L06 cambiado se rearmaron {rehechos}; el más corrido es {peor[0]} ({peor[1] - peor[2]:+d})')
        ok('L06' in rehechos and not set(rehechos) & {'L01', 'L02', 'L03', 'L04', 'L05'}, f'{fps_src} cps: al cambiar L06 se rearmaron {rehechos}')
        ok('no cae en su cuadro' not in log, f'{fps_src} cps: un cambio en L06 obligó a rehacer bloques por los cuadros:\n{log}')
        ok(cuadros(os.path.join(d, '1_montaje.mp4')) - round(bl[-1]['fin_max'] * FPS) in (-1, 0, 1), f'{fps_src} cps: con L06 cambiado no dura lo del guion')

        # 2b) un tramo guardado que quedó más corto (5 cuadros menos) ya no cae en su cuadro: se rehace solo ese
        info_f = glob.glob(os.path.join(d, montaje.PARTES, 'L03_*.json'))[0]
        info = json.load(open(info_f, encoding='utf-8'))
        parte = os.path.join(d, montaje.PARTES, info['partes'][-1])
        corto = parte + '.corto.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', parte, '-frames:v', str(info['cuadros'][-1] - 5), '-c:v', 'libx264',
                        '-preset', 'ultrafast', corto], check=True)
        os.replace(corto, parte)
        info['cuadros'][-1] -= 5
        json.dump(info, open(info_f, 'w', encoding='utf-8'))
        log = armar(d, bl)
        ok('L03 · lo ya hecho no cae en su cuadro' in log and 'L04 ok (ya estaba hecho' in log, f'{fps_src} cps: el tramo corto no se rehízo:\n{log}')
        filas, total = medir(d, bl)
        peor = max(filas, key=lambda f: abs(f[1] - f[2]))
        ok(abs(peor[1] - peor[2]) <= 1, f'{fps_src} cps, tras el tramo corto: {peor[0]} empieza {peor[1] - peor[2]:+d} cuadros corrido')

        # 2c) «Probar solo unos bloques» (L01 y L03, con sus tiempos desde cero): usa lo ya hecho tal cual, sin rehacerlo
        #     (pisaría los tramos del video entero), y no toca el aviso del video entero
        open(os.path.join(d, montaje.AVISOS_MONTAJE), 'w').write('[{"aviso": "de antes"}]')
        log = armar(d, tiempos([json.loads(json.dumps(bl[0])), json.loads(json.dumps(bl[2]))]), 'guion_prueba.json', 'prueba_montaje.mp4')
        ok('L01 ok (ya estaba hecho' in log and 'L03 ok (ya estaba hecho' in log and 'no cae en su cuadro' not in log,
           f'{fps_src} cps: la prueba rehízo bloques:\n{log}')
        ok(open(os.path.join(d, montaje.AVISOS_MONTAJE)).read() == '[{"aviso": "de antes"}]', f'{fps_src} cps: la prueba tocó el aviso')
        os.remove(os.path.join(d, montaje.AVISOS_MONTAJE))

        # 3) un guion con los tiempos viejos (cambiaste un tramo después de la voz): se avisa en avisos_montaje.json
        viejo = json.loads(json.dumps(bl))
        for b in viejo[8:]:
            b['inicio_min'] = round(b['inicio_min'] - 2.0, 2)
        armar(d, viejo)
        f_av = os.path.join(d, montaje.AVISOS_MONTAJE)
        avisos = json.load(open(f_av, encoding='utf-8')) if os.path.exists(f_av) else []
        ok(any(x.get('bloque') == 'L09' and x.get('aviso') for x in avisos), f'{fps_src} cps: sin aviso por los tiempos viejos: {avisos}')
        # y al arreglarlo, el aviso se va solo
        armar(d, bl)
        ok(not os.path.exists(f_av), f'{fps_src} cps: el aviso quedó aunque el guion ya está bien')

    # 4) la revisión con ffprobe: un video que no dura lo que dice el guion deja un aviso; uno justo, no
    f = os.path.join(tmp, 'dos_s.mp4')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=64x36:r=30:d=2',
                    '-c:v', 'libx264', f], check=True)
    ok(montaje.revisar_cuadros(f, 60, 30)[1] is None, 'un video justo (2 s = 60 cuadros) dio aviso')
    ok(montaje.revisar_cuadros(f, 61, 30)[1] is None, 'un cuadro de diferencia ya dio aviso')
    av = montaje.revisar_cuadros(f, 75, 30)[1]
    ok(av and '0,50 s' in av, f'un video medio segundo más corto que el guion no avisó bien: {av}')

    # 5) la vista previa muestra los avisos del montaje junto a los del inicio
    html = open(os.path.join(RAIZ, 'app', 'vista.html'), encoding='utf-8').read()
    ok(montaje.AVISOS_MONTAJE in html, 'la vista previa no lee avisos_montaje.json')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLAS:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('ok: cada bloque empieza en su cuadro (±1), los tramos guardados no se corren y el desfase se avisa')
