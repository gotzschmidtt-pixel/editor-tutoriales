"""Revisión 2 de la mejora 1 (03/11/2026): la imagen de cada bloque cae en su cuadro también en los casos de borde.

Se usa una grabación sintética con el segundo escrito en la imagen (tres franjas grises), así se puede leer qué momento
de la grabación se ve en cada cuadro del montaje:
1) Un tramo «lento+congelar» con "congelar_s": 0 (así deja «Alinear» los tramos que corre) ya no arma una «pausa» de
   1 cuadro cuando el redondeo de los tiempos deja uno suelto: ese cuadro lo pone el tramo. Con pausa de verdad, sí la hay.
2) Un tramo que pasa del final de la grabación (o una grabación de pantalla del teléfono, que no guarda cuadros mientras
   la pantalla está quieta) repite su último cuadro hasta su largo: antes, con un tope de 2 s, los bloques siguientes
   quedaban 3 s antes de su voz.
3) «Probar solo unos bloques» con un tramo guardado que no cae en su cuadro (uno hecho en otra prueba, en otro lugar del
   video): se rehace solo para la prueba, sin el aviso de «la imagen empieza 2 cuadros antes» y sin pisar lo guardado del
   video entero.
4) Un video largo (64 bloques) de una grabación con cuadros a destiempo (VFR) y un hueco: el montaje dura lo del guion,
   las marcas de tiempo no saltan y el primer cuadro de cada tramo es su src_inicio.
Sin internet y sin gastar nada: todo va a una carpeta temporal (tus proyectos no se tocan).
Uso: python tests/test_montaje_cuadros_revision.py   (sale con 1 si algo falla)
"""
import contextlib, glob, io, json, os, random, shutil, subprocess, sys, tempfile

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


# el segundo de la grabación (en centésimas, base 32) escrito en tres franjas grises
ESCRITO = ("geq=lum='16+7*if(lt(Y\\,H/3)\\,mod(round(T*100)\\,32)\\,if(lt(Y\\,2*H/3)\\,mod(floor(round(T*100)/32)\\,32)\\,"
           "floor(round(T*100)/1024)))':cb=128:cr=128")


def grabacion(destino, dur, vfr=False, hasta=None):
    """30 cps; vfr: cuadros a destiempo (±0,4 de cuadro) y un hueco de 1 s a los 40 s, como un teléfono que se traba."""
    pts = "settb=1/90000,setpts='(N+0.4*sin(N/3)+if(gt(N\\,1200)\\,30\\,0))/30/TB'," if vfr else ''
    extra = ['-fps_mode', 'vfr', '-enc_time_base', '1:90000', '-video_track_timescale', '90000'] if vfr else []
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'nullsrc=s=320x180:r=30:d={dur},format=yuv420p,{pts}{ESCRITO}']
                   + extra + ['-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-g', '30', destino], check=True)


def que_se_ve(video):
    """[segundo de la grabación que se ve en cada cuadro] (None donde no se lee: una imagen, un cuadro mezclado)."""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-'],
                       capture_output=True, check=True)
    cuadros = np.frombuffer(r.stdout, np.uint8).reshape(-1, H * W * 3 // 2)[:, :H * W].reshape(-1, H, W)
    out = []
    for c in cuadros:
        ds = []
        for k in range(3):
            y = H * (2 * k + 1) // 6
            zona = c[y - H // 18:y + H // 18, 3 * W // 4:19 * W // 20].astype(float)  # a la derecha: el rótulo va a la izquierda
            v = (float(np.median(zona)) - 16) / 7
            ds.append(None if zona.std() > 6 or abs(v - round(v)) > 0.35 else int(round(v)))
        out.append(None if None in ds else (ds[0] + 32 * ds[1] + 1024 * ds[2]) / 100)
    return out


def marcas(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time', '-of', 'csv=p=0', video],
                       capture_output=True, text=True, check=True)
    return sorted(float(x) for x in r.stdout.split() if x.strip() not in ('', 'N/A'))


def bloque(i, modo, a, z=None, v=1.0, pausa=None, **extra):
    m = {'modo': modo, 'src_inicio': a, 'src_fin': z, 'velocidad': v, 'encuadre': 'fijo'}
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


def armar(d, bloques, guion='guion.json', video='1_montaje.mp4'):
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


def guardado(d, bid):
    hechos = glob.glob(os.path.join(d, montaje.PARTES, f'{bid}_*.json'))
    return (hechos[0], json.load(open(hechos[0], encoding='utf-8'))) if len(hechos) == 1 else (None, None)


def mal_puestos(bloques, se_ve, tol=0.06):
    """Los tramos cuyo primer cuadro (el de su inicio_min) no muestra su src_inicio."""
    malos = []
    for b in bloques:
        m = b['montaje']
        if m['modo'].startswith('lento'):
            n = round(b['inicio_min'] * FPS)
            x = se_ve[n] if n < len(se_ve) else None
            if x is None or abs(x - m['src_inicio']) > tol:
                malos.append((b['id'], n, x, m['src_inicio']))
    return malos


tmp = tempfile.mkdtemp(prefix='montaje cuadros ')  # con espacio, como las carpetas de fabian
try:
    d = os.path.join(tmp, 'corto')
    os.makedirs(d)
    grabacion(os.path.join(d, 'original.mp4'), 60)

    # 1) «congelar_s»: 0 tras «Alinear»: 0,01 s de redondeo dejan un cuadro suelto entre el tramo y el bloque siguiente
    bl = tiempos([bloque('L01', 'lento', 0.0, 1.29), bloque('L02', 'lento+congelar', 10.0, 13.46, 1.37, 0, alineado=True),
                  bloque('L03', 'lento+congelar', 30.0, 32.0, 1.0, 0.5), bloque('L04', 'lento', 40.0, 42.0)])
    ini = montaje.tiempos_bloques(bl)[0]
    ok(round(ini[2] * FPS) - round((ini[1] + montaje.largo_tramo(bl[1]['montaje'])) * FPS) == 1,
       'el ejemplo ya no deja un cuadro suelto tras L02 (prueba mal armada)')
    log = armar(d, bl)
    ok(len((guardado(d, 'L02')[1] or {}).get('cuadros', [])) == 1, f'L02 («congelar_s»: 0) armó una pausa: {guardado(d, "L02")[1]}')
    ok(len((guardado(d, 'L03')[1] or {}).get('cuadros', [])) == 2, f'L03 (0,5 s de pausa) quedó sin pausa: {guardado(d, "L03")[1]}')
    se_ve = que_se_ve(os.path.join(d, '1_montaje.mp4'))
    ok(len(se_ve) == round(bl[-1]['fin_max'] * FPS), f'1) el montaje tiene {len(se_ve)} cuadros y el guion {round(bl[-1]["fin_max"] * FPS)}')
    ok(not mal_puestos(bl, se_ve), f'1) bloques fuera de su cuadro: {mal_puestos(bl, se_ve)}')
    ok('AVISO' not in log, f'1) avisó sin motivo:\n{log}')

    # 2) un tramo que pasa 5 s del final de la grabación (60 s)
    bl = tiempos([bloque('F01', 'lento', 50.0, 65.0), bloque('F02', 'lento', 2.0, 4.0), bloque('F03', 'lento', 5.0, 7.0)])
    log = armar(d, bl)
    se_ve = que_se_ve(os.path.join(d, '1_montaje.mp4'))
    ok(not mal_puestos(bl, se_ve), f'2) tras un tramo que pasa del final, bloques fuera de su cuadro: {mal_puestos(bl, se_ve)}\n{log}')
    ok('AVISO' not in log, f'2) avisó:\n{log}')

    # 3) «Probar solo unos bloques» con un tramo guardado que no cae en su cuadro (3 cuadros de menos, como uno hecho en otra
    #    prueba en otro lugar del video): se rehace solo para la prueba, sin aviso y sin pisar lo guardado
    bl = tiempos([bloque(f'P{k:02d}', 'lento+congelar' if k % 3 == 0 else 'lento', 3.0 * k, 3.0 * k + 1.73 + 0.11 * k,
                         (1.0, 1.37, 2.0)[k % 3], 0.61 if k % 3 == 0 else None) for k in range(1, 9)])
    armar(d, bl)
    f_info, info = guardado(d, 'P04')
    parte = os.path.join(d, montaje.PARTES, info['partes'][-1])
    corto = parte + '.corto.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', parte, '-frames:v', str(info['cuadros'][-1] - 3), '-c:v', 'libx264',
                    '-preset', 'ultrafast', corto], check=True)
    os.replace(corto, parte)
    info['cuadros'][-1] -= 3
    json.dump(info, open(f_info, 'w', encoding='utf-8'))
    antes = {f: os.path.getmtime(f) for f in glob.glob(os.path.join(d, montaje.PARTES, '*'))}
    prueba = tiempos([json.loads(json.dumps(b)) for b in bl[2:7]])
    log = armar(d, prueba, 'guion_prueba.json', 'prueba_montaje.mp4')
    ok('P04 · lo ya hecho no cae en su cuadro' in log and 'P05 ok (ya estaba hecho' in log, f'3) la prueba no rehízo P04:\n{log}')
    ok('AVISO' not in log, f'3) la prueba avisó sin motivo:\n{log}')
    se_ve = que_se_ve(os.path.join(d, 'prueba_montaje.mp4'))
    ok(not mal_puestos(prueba, se_ve), f'3) en la prueba, bloques fuera de su cuadro: {mal_puestos(prueba, se_ve)}')
    despues = {f: os.path.getmtime(f) for f in glob.glob(os.path.join(d, montaje.PARTES, '*'))}
    ok(despues == antes, f'3) la prueba pisó lo guardado del video entero: {sorted(set(despues.items()) ^ set(antes.items()))}')
    # y el video entero rehace solo P04
    log = armar(d, bl)
    rehechos = [x.split()[0] for x in log.splitlines() if x.endswith(' ok') or ' ok ·' in x]
    ok(rehechos == ['P04'], f'3) el video entero rehízo {rehechos}:\n{log}')

    # 4) video largo de una grabación VFR: 64 bloques de todos los modos
    d = os.path.join(tmp, 'largo')
    os.makedirs(d)
    grabacion(os.path.join(d, 'original.mp4'), 330, vfr=True)
    ok(montaje.cuadros_por_segundo(os.path.join(d, 'original.mp4')) == FPS, 'la grabación VFR no se toma como de 30 cps')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240', '-frames:v', '1',
                    os.path.join(d, 'mapa.png')], check=True)
    rnd, bl, s = random.Random(7), [], 1.0
    for k in range(1, 65):
        modo = rnd.choice(['lento'] * 4 + ['lento+congelar'] * 3 + ['congelar', 'imagen'])
        largo = round(rnd.uniform(1.2, 7.0), 2)
        m = bloque(f'V{k:02d}', modo, round(s, 2), round(s + largo, 2) if modo.startswith('lento') else None,
                   rnd.choice([1.0, 1.0, 1.5, 2.0, 4.0, 0.7, 1.37]),
                   round(rnd.uniform(0.4, 4.0), 2) if modo != 'lento' else None)
        m['montaje'].pop('encuadre')  # aquí sí cambian de encuadre las tomas largas
        if modo == 'imagen':
            m['montaje']['imagen'] = os.path.join(d, 'mapa.png')
        elif modo == 'lento+congelar':
            m['montaje'].update(rnd.choice([{}, {}, {'quieto': True}, {'repetir': 'adelante'}, {'congelar_s': 0, 'alineado': True}]))
        bl.append(m)
        s += (largo if modo.startswith('lento') else 0) + rnd.uniform(0.3, 1.5)
    bl = tiempos(bl)
    log = armar(d, bl)
    salida = os.path.join(d, '1_montaje.mp4')
    p = marcas(salida)
    esperado = round(bl[-1]['fin_max'] * FPS)
    print(f'4) {len(bl)} bloques, {bl[-1]["fin_max"]:.1f} s: {len(p)} cuadros (guion {esperado})')
    ok(len(p) == esperado, f'4) el montaje largo tiene {len(p)} cuadros y el guion {esperado}')
    saltos = [(n, x) for n, x in enumerate(p) if abs(x - n / FPS) > 0.002]
    ok(not saltos, f'4) las marcas de tiempo del montaje saltan (la imagen se correría al reproducir): {saltos[:5]}')
    malos = mal_puestos(bl, que_se_ve(salida))
    ok(not malos, f'4) {len(malos)} tramos no empiezan en su cuadro: {malos[:5]}')
    ok('AVISO' not in log and not os.path.exists(os.path.join(d, montaje.AVISOS_MONTAJE)), f'4) avisó sin motivo:\n{log}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLAS:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('ok: sin pausas de 1 cuadro, los tramos cortos se rellenan, la prueba rehace sin pisar y 64 bloques VFR caen en su cuadro')
