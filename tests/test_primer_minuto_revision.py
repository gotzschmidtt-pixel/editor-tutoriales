"""Prueba de la revisión del primer minuto (03/11/2026), sin videos tuyos, sin red y sin gastar nada:
- con los puntos nuevos, una frase del DESPUÉS («libre y sin la cuenta») no cae en la pantalla bloqueada del ANTES (dice
  «cuenta»), y el después sale del final del grabado aunque a mitad del proceso haya un Ajustes más nítido;
- la marca, que sale en casi todas las pantallas, no arrastra la frase del cable a una pantalla de otro tema;
- «"tomas": 5» (o true) de la IA no tumba la revisión del guion ni el montaje;
- se avisa si un bloque del gancho trae más o menos tomas que frases (una toma caería en otra frase o no saldría nunca);
- el encargo pide cerrar cada frase del gancho con punto, ¿? o ¡! y la regla de «no anunciar el resultado» deja pasar el gancho.
Uso: python tests/test_primer_minuto_revision.py   (sale con 1 si algo falla)
"""
import json, os, shutil, subprocess, sys, tempfile

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
sys.path.insert(0, os.path.join(RAIZ, 'montaje'))
import ia  # noqa: E402
import rotar  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def voz(carpeta, bid, texto):
    """Un .align.json falso (como el de ElevenLabs) con la frase desde el segundo 0."""
    txt = texto + ' '
    json.dump({'characters': list(txt), 'character_start_times_seconds': [i * 0.06 for i in range(len(txt))]},
              open(os.path.join(carpeta, f'{bid}.align.json'), 'w', encoding='utf-8'))


def elegidos(bid, texto, cuadros, nt=None, pausa=6.0):
    voz('voz', bid, texto)
    json.dump({'cuadros': cuadros}, open('mapa_video.json', 'w', encoding='utf-8'))
    bl = [{'id': bid, 'inicio_min': 20.0, 'montaje': {'modo': 'congelar', 'src_inicio': 850.0, 'congelar_s': pausa}}]
    return [s for s, _ in rotar.planear(bl, 'mapa_video.json', 'voz', 900.0, 30, guardar_avisos=False, nt=nt).get(bid, [])]


tmp = tempfile.mkdtemp(prefix='primer_minuto_rev_')
viejo_cwd = os.getcwd()
try:
    os.makedirs(os.path.join(tmp, 'voz'))
    os.chdir(tmp)
    bloqueado = {'t': 10.0, 'texto': 'Verifica tu cuenta | Google'}

    # 1. «libre y sin la cuenta» es el DESPUÉS: nunca la pantalla bloqueada aunque diga «cuenta»
    cuadros = [bloqueado, {'t': 130.0, 'texto': 'FASTBOOT MODE | Press volume down'},
               {'t': 210.0, 'texto': 'Unlocker tool | Read Fastboot Info'}, {'t': 300.0, 'texto': 'Erase FRP By Code | OKAY'},
               {'t': 720.0, 'texto': 'Bienvenido | Ajustes'}, {'t': 800.0, 'texto': '10:45 | Ajustes | Acerca del teléfono'}]
    s = elegidos('L03', 'Así queda tu teléfono, libre y sin la cuenta.', cuadros)
    ok(s and 10.0 not in s, f'una frase del después no debería mostrar la pantalla bloqueada (10 s): {s}')
    ok(s[:1] == [800.0], f'el después debería salir de lo último del grabado (800 s), como antes: {s}')
    # al revés también: «te pide la cuenta» (antes) no se va a una pantalla del después que diga «cuenta»
    s = elegidos('L03', 'Tu teléfono te pide la cuenta de Google.',
                 [bloqueado, {'t': 820.0, 'texto': 'Ajustes | Cuentas y usuarios | Agregar cuenta'}])
    ok(s[:1] == [10.0], f'una frase del antes debería mostrar la pantalla bloqueada (10 s): {s}')

    # 2. con nitidez (montaje.py siempre la pasa): un Ajustes nítido a mitad del proceso no le gana al después del final
    cuadros = [bloqueado, {'t': 200.0, 'texto': 'Ajustes | Acerca del teléfono | Número de compilación'},
               {'t': 760.0, 'texto': 'Bienvenido | Ajustes'}, {'t': 820.0, 'texto': 'Bienvenido | Ajustes'}]
    tt = np.arange(0, 900, 0.2)
    ni, mo = np.where(tt < 400, 100.0, 20.0), np.where(tt < 400, 0.2, 3.0)  # la PC a mitad, nítida; el teléfono al final, menos
    ni[(tt >= 760) & (tt <= 767)], mo[(tt >= 760) & (tt <= 767)] = 60.0, 0.5
    s = elegidos('L03', 'Y así queda libre y funcionando.', cuadros, nt=(tt, ni, mo))
    ok(s[:1] == [760.0], f'el después debería ser el del final, y entre esos el más nítido (760 s), no el de 200 s: {s}')

    # 3. la marca sale en casi todas las pantallas: no se lleva la frase del cable a la pantalla bloqueada
    cuadros = [{'t': 10.0, 'texto': 'HONOR | Verifica tu cuenta | Google'}, {'t': 60.0, 'texto': 'USB connected | charging'},
               {'t': 210.0, 'texto': 'HONOR | Unlocker tool | Read Info'}, {'t': 300.0, 'texto': 'HONOR | Erase FRP | OKAY'},
               {'t': 420.0, 'texto': 'HONOR | Bienvenido'}, {'t': 580.0, 'texto': 'HONOR | Ajustes'}]
    s = elegidos('L04', 'Conectamos el cable a tu Honor.', cuadros)
    ok(s[:1] == [60.0], f'para «conectamos el cable a tu Honor» debería elegir la pantalla USB (60 s), no otra por decir HONOR: {s}')
    # una palabra poco común sí trae su pantalla aunque no sea del tema (lo que pidió la mejora)
    cuadros.append({'t': 470.0, 'texto': 'Configurar huella | Siguiente'})
    s = elegidos('L04', 'Conectamos el cable y saltamos la huella.', cuadros)
    ok(s[:1] == [470.0], f'«huella» sale en una sola pantalla: debería ganar esa (470 s): {s}')

    # 4. «"tomas": 5» o true de la IA no tumba nada
    for raro in (5, True, None, 'x'):
        try:
            rotar.tomas_de({'tomas': raro})
        except Exception as e:  # noqa: BLE001
            fallos.append(f'rotar.tomas_de se cae con tomas={raro!r}: {e}')
    d = os.path.join(tmp, 'proyecto')
    os.makedirs(d)
    json.dump({'cuadros': []}, open(os.path.join(d, 'mapa_video.json'), 'w', encoding='utf-8'))
    raro = {'id': 'L01', 'gancho': True, 'texto': 'Así queda libre.', 'tomas': 5,
            'montaje': {'modo': 'lento', 'src_inicio': 0.0, 'src_fin': 1.0, 'velocidad': 1.0}}
    try:
        ia.revisar_gancho(d, [raro])
    except Exception as e:  # noqa: BLE001
        fallos.append(f'la revisión del gancho se cae con "tomas": 5: {e}')
    try:
        voz('voz', 'L01', 'Así queda libre.')
        rotar.planear([dict(raro, inicio_min=0.0, fin_max=6.0, montaje=dict(raro['montaje'], modo='lento+congelar', congelar_s=5.0))],
                      'mapa_video.json', 'voz', 900.0, 30, guardar_avisos=False)
    except Exception as e:  # noqa: BLE001
        fallos.append(f'el montaje del inicio se cae con "tomas": 5: {e}')

    # 5. tomas y frases: una por frase
    b = {'id': 'L01', 'gancho': True, 'texto': 'Así queda tu Honor libre, y antes te pedía la cuenta de Google.',
         'tomas': [[600, 604], [10, 14]], 'montaje': {'modo': 'lento', 'src_inicio': 0.0, 'src_fin': 1.0, 'velocidad': 1.0}}
    av = ia.revisar_gancho(d, [b])
    ok(any(x.startswith('L01: trae 2 tomas y 1 frase') for x in av), f'debería avisar 2 tomas para 1 frase: {av}')
    b['texto'] = 'Así queda tu Honor libre. ¿Te pedía la cuenta de Google?'
    ok(not any('tomas y' in x for x in ia.revisar_gancho(d, [b])), 'con una toma por frase no debería avisar')
    b['tomas'] = [[600, 604], None]  # null: la app elige ese trozo, igual cuenta como la toma de esa frase
    ok(not any('tomas y' in x for x in ia.revisar_gancho(d, [b])), 'una toma null cuenta como la de su frase')
    sin = {k: v for k, v in b.items() if k != 'tomas'}  # sin tomas: rota como siempre, nada que avisar
    ok(not any('tomas y' in x for x in ia.revisar_gancho(d, [sin])), 'un gancho sin tomas no debería avisar tomas y frases')

    # 6. el encargo: cada frase del gancho cierra con punto, ¿? o ¡!, y la regla de no adelantar el resultado deja pasar el gancho
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=160x120:rate=5', '-t', '10', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', os.path.join(d, 'original.mp4')], check=True)
    ia.conocimiento.marca_de_proyecto = lambda d: 'HONOR'  # sin depender de tus carpetas de conocimiento
    txt = ia.encargo(d, 'guion', 'Honor 8 Lite, quitar la cuenta de Google', [])
    ini = txt[txt.find('INICIO (primer minuto)'):]
    ok('termina en punto, signo de pregunta o de exclamación' in ini, 'la sección INICIO debería pedir cerrar cada frase con punto, ¿? o ¡!')
    regla = txt[txt.find('La voz va AL MISMO TIEMPO'):]
    ok('GANCHO' in regla[:400], 'la regla de no anunciar el resultado antes de verlo debería dejar pasar el GANCHO del inicio')
finally:
    os.chdir(viejo_cwd)
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión del primer minuto (antes/después, marca, tomas raras, tomas por frase, encargo)')
sys.exit(1 if fallos else 0)
