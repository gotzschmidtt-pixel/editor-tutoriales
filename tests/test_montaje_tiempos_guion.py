"""Revisión de la mejora 1 (03/11/2026): el montaje solo avisa «tiempos viejos» cuando de verdad lo son.

1) Un guion de ia.py (inicio_min redondeado a 0,1 s, sin voz todavía) puede quedar justo a 0,1 s de la suma de los
   bloques; con los decimales de la PC eso pasaba por poco el margen y salía el aviso rojo sin motivo
   (L01 de 1,15 s y L02 de 3 s: inicio_min 0,0 · 1,1 · 4,2).
2) Un guion que de verdad quedó viejo sigue avisando, y el aviso no promete «no gasta»: en un bloque que todavía no
   tiene voz, «Generar voz» sí la pide a ElevenLabs.
Sin internet y sin gastar nada: un video sintético corto en una carpeta temporal (tus proyectos no se tocan).
Uso: python tests/test_montaje_tiempos_guion.py   (sale con 1 si algo falla)
"""
import contextlib, io, json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'montaje'))
import montaje  # noqa: E402

montaje._DETECTOR.append(None)  # sin el detector de caras (no se baja nada de internet)
FPS = 30
fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def lento(i, a, z):
    return {'id': i, 'ancla': f'bloque {i}', 'texto': '', 'montaje': {'modo': 'lento', 'src_inicio': a, 'src_fin': z, 'velocidad': 1.0}}


def como_ia(bloques):
    """inicio_min y fin_max como los pone ia.py (redondeados a 0,1 s)."""
    t = 0.0
    for b in bloques:
        largo = montaje.largo_tramo(b['montaje']) + (b['montaje'].get('congelar_s') or 0)
        b['inicio_min'], b['fin_max'] = round(t, 1), round(t + largo, 1)
        t += largo
    return bloques


def guion():
    return como_ia([lento('L01', 1.0, 2.15), lento('L02', 6.0, 9.0), lento('L03', 11.0, 12.0)])


# 1) el caso justo en el borde: ningún bloque «viejo»
bl = guion()
ok([b['inicio_min'] for b in bl] == [0.0, 1.1, 4.2], f'el ejemplo cambió: {[b["inicio_min"] for b in bl]}')
ok(montaje.tiempos_bloques(bl)[1] is None, f'un guion de ia.py bien hecho salió como viejo: {montaje.tiempos_bloques(bl)[1]}')
# y todos los pares de tramos de 1 a 4 s (de a 0,01 s), como los redondea ia.py
malos = []
for x in range(100, 400):
    for y in range(100, 400, 7):
        b2 = como_ia([lento('L01', 1.0, round(1.0 + x / 100, 2)), lento('L02', 6.0, round(6.0 + y / 100, 2)), lento('L03', 11.0, 12.0)])
        if montaje.tiempos_bloques(b2)[1]:
            malos.append((x / 100, y / 100))
ok(not malos, f'{len(malos)} guiones de ia.py bien hechos salieron como viejos, por ejemplo {malos[:3]}')

# 2) uno de verdad viejo (L03 corrido 0,15 s, más que el redondeo de ia.py) sí se marca
viejo = guion()
viejo[2]['inicio_min'] = round(viejo[2]['inicio_min'] + 0.15, 2)
ok(montaje.tiempos_bloques(viejo)[1] == 'L03', f'un guion viejo no se marcó: {montaje.tiempos_bloques(viejo)[1]}')


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


tmp = tempfile.mkdtemp(prefix='montaje tiempos ')  # con espacio, como las carpetas de fabian
try:
    d = os.path.join(tmp, 'mi proyecto')
    os.makedirs(d)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=size=320x180:rate={FPS}', '-t', '14',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', os.path.join(d, 'original.mp4')], check=True)
    f_av = os.path.join(d, montaje.AVISOS_MONTAJE)

    # 3) el montaje entero con ese guion: sin aviso rojo, y cada bloque en su cuadro
    log = armar(d, guion())
    ok(not os.path.exists(f_av), 'un guion de ia.py bien hecho dejó el aviso rojo: '
       + (open(f_av, encoding='utf-8').read() if os.path.exists(f_av) else ''))
    ok('AVISO montaje' not in log, f'el paso avisó sin motivo:\n{log}')

    # 4) un guion de verdad viejo deja el aviso, sin prometer que «Generar voz» no gasta
    viejo = guion()
    viejo[2]['inicio_min'] = round(viejo[2]['inicio_min'] + 1.0, 2)
    armar(d, viejo)
    avisos = json.load(open(f_av, encoding='utf-8')) if os.path.exists(f_av) else []
    texto = ' '.join(x.get('aviso', '') for x in avisos if x.get('bloque') == 'L03')
    ok(texto, f'un guion viejo no dejó su aviso: {avisos}')
    ok('no gasta' not in texto and 'todavía no la tienen' in texto, f'el aviso promete que no gasta: {texto}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLAS:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('ok: el redondeo de ia.py ya no da «tiempos viejos» sin motivo; un guion viejo sí avisa, sin prometer que no gasta')
