"""Prueba rápida del primer minuto (pedido de fabian, 03/11/2026), sin videos tuyos, sin red y sin gastar nada (la IA se
simula y los videos son sintéticos de ffmpeg):
- el encargo del guion trae la sección «INICIO (primer minuto)» con el gancho, sus tomas y su orden fijo;
- los bloques del gancho ("gancho": true) no cuentan como salto atrás, escena repetida ni voz corrida, y nadie los mueve,
  pero sí se avisa si una toma tiene precio o datos personales, si se repite seguida o si el gancho dura de más;
- montaje/rotar.py pone las tomas de la IA (una por frase) y cambia la que tiene datos sensibles o repite la de antes;
- sin tomas, el gancho rota igual aunque su pausa sea corta; un guion viejo sin los campos nuevos queda como antes;
- para «entramos en modo fastboot» elige la pantalla FASTBOOT (antes salían pantallas USB), y prefiere lo nítido y quieto.
Uso: python tests/test_primer_minuto.py   (sale con 1 si algo falla)
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


def alineacion(frases, carpeta, bid):
    """Un .align.json falso (como el de ElevenLabs): cada frase empieza en su segundo."""
    chars, t0s = [], []
    for k, (s, f) in enumerate(frases):
        f = f + (' ' if k + 1 < len(frases) else '')
        chars += list(f)
        t0s += [s + 2.5 * i / len(f) for i in range(len(f))]
    json.dump({'characters': chars, 'character_start_times_seconds': t0s,
               'character_end_times_seconds': [t + 0.05 for t in t0s]}, open(os.path.join(carpeta, f'{bid}.align.json'), 'w', encoding='utf-8'))


tmp = tempfile.mkdtemp(prefix='primer_minuto_')
viejo_cwd = os.getcwd()
try:
    # 1. el encargo del guion trae la sección INICIO (en Honor, sin «sin PC» y con MagicOS)
    d = os.path.join(tmp, 'HONOR_8_LITE_prueba')
    os.makedirs(d)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=160x120:rate=5', '-t', '60', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', os.path.join(d, 'original.mp4')], check=True)
    ia.conocimiento.marca_de_proyecto = lambda d: 'HONOR'  # sin depender de tus carpetas de conocimiento
    txt = ia.encargo(d, 'guion', 'Honor 8 Lite, quitar la cuenta de Google', [])
    ok('INICIO (primer minuto)' in txt, 'el encargo del guion debería traer la sección «INICIO (primer minuto)»')
    ini = txt[txt.find('INICIO (primer minuto)'):]
    for trozo in ('"gancho": true', '"avatar": false', '"tomas"', '"por_que"', 'Android quince, dieciséis, diecisiete o superiores',
                  'cualquier parche', '«es fácil»', 'comentar', 'MagicOS', 'nunca digas «sin PC»', 'datos personales', '12 palabras'):
        ok(trozo in ini, f'la sección INICIO debería decir {trozo}')
    orden = [ini.find(x) for x in ('el resultado', 'el problema', 'las versiones', 'la herramienta y la PC', '«es fácil»', 'la invitación a comentar')]
    ok(-1 not in orden and orden == sorted(orden), f'el gancho debería ir resultado → problema → versiones → PC → fácil → comentar: {orden}')
    ia.conocimiento.marca_de_proyecto = lambda d: 'APPLE'
    ok('Android quince' not in ia.regla_inicio(d), 'en un video de Apple el gancho no debería pedir las versiones de Android')
    ia.conocimiento.marca_de_proyecto = lambda d: 'MOTOROLA'
    ok('sin PC' not in ia.regla_inicio(d) and 'MagicOS' not in ia.regla_inicio(d), 'lo de Honor solo va en Honor')

    # 2. las revisiones de orden no castigan ni mueven el gancho, pero sí revisan sus tomas
    mapa = [{'t': 5.0, 'texto': 'Verifica tu cuenta | Google'}, {'t': 15.0, 'texto': 'USB connected'},
            {'t': 25.0, 'texto': 'FASTBOOT MODE | Press volume down'}, {'t': 32.0, 'texto': 'Saldo: $ 25.00 | correo@ejemplo.com'},
            {'t': 40.0, 'texto': 'Unlocker tool | Read Fastboot Info'}, {'t': 50.0, 'texto': 'Bienvenido | Ajustes'}]
    json.dump({'cuadros': mapa}, open(os.path.join(d, 'mapa_video.json'), 'w', encoding='utf-8'))
    dichas = ('apagamos el teléfono y conectamos el cable usb al computador ' * 2).split() + \
             'con volumen menos entramos en fastboot y el programa lo detecta'.split() + \
             'y así queda el honor libre sin la cuenta de google que pedía el teléfono'.split()
    momentos = [3 + 0.5 * i for i in range(20)] + [24 + 0.5 * i for i in range(11)] + [48 + 0.4 * i for i in range(14)]
    json.dump([{'inicio': t, 'fin': t + 0.3, 'texto': w} for t, w in zip(momentos, dichas)],
              open(os.path.join(d, 'transcripcion.json'), 'w', encoding='utf-8'))

    def guion(con_gancho=True):
        def g(b):
            if not con_gancho:
                b.pop('gancho', None)
            return b
        return [g({'id': 'L01', 'gancho': True, 'texto': 'Así queda tu Honor, libre y sin la cuenta. ¿Tu teléfono te pide la cuenta de Google?',
                   'tomas': [[50, 54], [5, 9]], 'por_que': ['ya libre', 'bloqueado'],
                   'montaje': {'modo': 'lento', 'src_inicio': 0.0, 'src_fin': 1.0, 'velocidad': 1.0}}),
                g({'id': 'L02', 'gancho': True, 'texto': 'Sirve para Android quince, dieciséis, diecisiete o superiores, y cualquier parche. '
                                                        'Solo con tu PC y los botones de volumen.',
                   'tomas': [[32, 36], [33, 37]], 'montaje': {'modo': 'lento', 'src_inicio': 1.0, 'src_fin': 2.0, 'velocidad': 1.0}}),
                g({'id': 'L03', 'gancho': True, 'texto': 'Es fácil. Déjame tus dudas en los comentarios.', 'tomas': [[2, 6]],
                   'montaje': {'modo': 'lento', 'src_inicio': 2.0, 'src_fin': 22.0, 'velocidad': 1.0}}),
                {'id': 'L04', 'texto': 'Paso uno: apagamos el teléfono y conectamos el cable USB al computador.',
                 'montaje': {'modo': 'lento', 'src_inicio': 2.0, 'src_fin': 20.0, 'velocidad': 1.0}},
                {'id': 'L05', 'texto': 'Paso dos: con volumen menos entramos en modo fastboot y el programa lo detecta.',
                 'montaje': {'modo': 'lento', 'src_inicio': 20.0, 'src_fin': 45.0, 'velocidad': 1.0}}]

    def de_gancho(avisos):
        return [x for x in avisos if x.split(':')[0] in ('L01', 'L02', 'L03') and 'toma' not in x]

    sin = guion(con_gancho=False)  # el mismo guion sin marcar el gancho: así se ve que la prueba sí mide algo
    ok(ia.saltos_atras(sin) and ia.escenas_repetidas(sin), 'sin "gancho" debería avisar salto atrás y escena repetida (prueba mal armada)')
    ok(de_gancho(ia.verificar_orden(d, sin)), 'sin "gancho" la revisión del orden debería avisar algo de L01-L03 (prueba mal armada)')
    con = guion()
    ok(not ia.saltos_atras(con), f'el gancho no debería contar como salto atrás: {ia.saltos_atras(con)}')
    ok(not ia.escenas_repetidas(con), f'el gancho no debería contar como escena repetida: {ia.escenas_repetidas(con)}')
    ok(not de_gancho(ia.desfases(d, con)), f'el gancho no debería contar como voz corrida: {ia.desfases(d, con)}')
    ok(not de_gancho(ia.acciones_desfasadas(d, con)), f'el gancho no debería contar como acción desfasada: {ia.acciones_desfasadas(d, con)}')
    antes = json.dumps([b['montaje'] for b in con])
    avisos = ia.verificar_orden(d, con)
    ok(not de_gancho(avisos), f'la revisión del orden no debería castigar al gancho: {de_gancho(avisos)}')
    ok(json.dumps([b['montaje'] for b in con]) == antes, 'la revisión del orden no debería mover el gancho')
    ok(any(x.startswith('L02: la toma 1') and 'datos personales' in x for x in avisos),
       f'debería avisar la toma con saldo y correo en pantalla: {avisos}')
    ok(not any('correo@' in x or '25.00' in x for x in avisos), 'el aviso no debería copiar el dato privado a revision_guion.txt')
    ok(any(x.startswith('L02: la toma 2') and 'repite la anterior' in x for x in avisos), f'debería avisar la toma repetida seguida: {avisos}')
    ok(not any('dura unos' in x for x in avisos), 'un gancho de unos 20 s no debería avisar que dura de más')
    largo = [dict(b, texto=' '.join(['palabra'] * 70) + '.') if b.get('gancho') else b for b in guion()]
    ok(any('el gancho' in x and 'pasa de 45-60 s' in x for x in ia.revisar_gancho(d, largo)), 'un gancho de ~80 s debería avisar que pasa de 45-60 s')
    viejo = [b for b in guion(con_gancho=False)[3:]]  # guion de antes, sin campos nuevos: sin avisos del gancho
    ok(ia.revisar_gancho(d, viejo) == [], 'un guion sin gancho no debería tener avisos del gancho')

    # revisar_con_imagen: la IA (simulada) no recibe los bloques del gancho, y vuelven los avisos de sus tomas
    enviados = []

    def por_tandas(ajustes, items, tanda, pedir, que):
        enviados.extend(b['id'] for b in items)
        pedir(items, 0)  # arma el pedido de verdad (sin mandarlo)
        return [(0, items, {'revision': [{'bloque': b['id'], 'ok': False, 'segundo': 3} for b in items]})]
    ia.por_tandas = por_tandas
    con = guion()
    gancho_antes = json.dumps([b['montaje'] for b in con[:3]])
    vistos = ia.revisar_con_imagen(d, {'imagenes': True}, {'bloques': con}, mapa, con_ocr=False)
    ok(enviados == ['L04', 'L05'], f'a la revisión con imágenes solo deberían ir los bloques normales: {enviados}')
    ok(json.dumps([b['montaje'] for b in con[:3]]) == gancho_antes, 'la revisión con imágenes no debería mover el gancho')
    ok(vistos and any('datos personales' in x for x in vistos), f'la revisión con imágenes debería avisar la toma con datos: {vistos}')

    # 3. rotar.py: las tomas de la IA en la pausa del gancho, una por frase, con el filtro SENSIBLE
    r = os.path.join(tmp, 'rotar')
    os.makedirs(os.path.join(r, 'voz'))
    os.chdir(r)  # avisos_inicio.json se escribe en la carpeta del proyecto (montaje.py corre ahí)
    mapa_f = os.path.join(r, 'mapa_video.json')
    json.dump({'cuadros': [{'t': 10.0, 'texto': 'Verifica tu cuenta | Google'}, {'t': 20.0, 'texto': 'USB connected | charging'},
                           {'t': 45.0, 'texto': 'Select USB configuration'},
                           {'t': 130.0, 'texto': 'FASTBOOT MODE | PRODUCT_NAME HNR-8L | Press volume down'},
                           {'t': 210.0, 'texto': 'Unlocker tool | Read Fastboot Info'},
                           {'t': 250.0, 'texto': 'Saldo: $ 25.00 | correo@ejemplo.com'},
                           {'t': 300.0, 'texto': 'Erase FRP By Code | OKAY Finished'}, {'t': 420.0, 'texto': 'Bienvenido | Ajustes'},
                           {'t': 600.0, 'texto': '10:45 | Ajustes | Acerca del teléfono'}]}, open(mapa_f, 'w', encoding='utf-8'))
    alineacion([(0.0, 'Así queda tu Honor, libre y sin cuenta.'), (4.0, 'Te pedía la cuenta de Google.'),
                (8.0, 'Sirve para Android quince y cualquier parche.')], os.path.join(r, 'voz'), 'L01')
    alineacion([(0.0, 'Es fácil.'), (2.0, 'Déjame tus dudas abajo.')], os.path.join(r, 'voz'), 'L02')
    alineacion([(0.0, 'Paso uno: conectamos el cable.')], os.path.join(r, 'voz'), 'L03')
    bl = [{'id': 'L01', 'gancho': True, 'inicio_min': 0.0, 'fin_max': 12.0, 'tomas': [[600, 604], [250, 254], [10, 14]],
           'montaje': {'modo': 'lento+congelar', 'src_inicio': 0.0, 'src_fin': 1.0, 'velocidad': 1.0, 'congelar_s': 11.0}},
          {'id': 'L02', 'gancho': True, 'inicio_min': 12.0, 'fin_max': 17.5,  # sin tomas y con pausa corta: rota igual
           'montaje': {'modo': 'lento+congelar', 'src_inicio': 1.0, 'src_fin': 2.0, 'velocidad': 1.0, 'congelar_s': 4.5}},
          {'id': 'L03', 'inicio_min': 17.5, 'fin_max': 23.0,  # bloque de siempre con pausa corta: queda como antes
           'montaje': {'modo': 'lento+congelar', 'src_inicio': 2.0, 'src_fin': 3.0, 'velocidad': 1.0, 'congelar_s': 4.5}}]
    plan = rotar.planear(bl, mapa_f, os.path.join(r, 'voz'), 900.0, 30)
    l01 = [s for s, _ in plan.get('L01', [])]
    ok(l01[:1] == [600.0], f'la primera frase debería llevar la toma 1 de la IA (600 s): {l01}')
    ok(len(l01) == 3 and 250.0 not in l01, f'la toma con saldo y correo no debería usarse: {l01}')
    ok(l01[1:2] == [10.0], f'la frase de la cuenta de Google debería llevar la pantalla bloqueada: {l01}')
    ok(len(l01) == 3 and l01[2] != 10.0, f'la toma 3 repite el trozo de justo antes: debería cambiarse: {l01}')
    ok(sum(n for _, n in plan.get('L01', [])) == 330, 'los trozos deberían sumar justo los cuadros de la pausa')
    ok('L02' in plan, 'un bloque del gancho sin tomas y con pausa corta (4,5 s) debería rotar igual')
    ok('L03' not in plan, 'un bloque normal con pausa corta debería quedar como antes (sin rotar)')
    av = json.load(open(os.path.join(r, rotar.AVISOS), encoding='utf-8'))
    ok(any('toma 2' in x['aviso'] and 'datos personales' in x['aviso'] for x in av), f'debería avisar la toma 2 con datos: {av}')
    ok(not any('correo@' in x['aviso'] for x in av), 'el aviso del inicio no debería copiar el dato privado')
    ok(any('toma 3' in x['aviso'] and 'repite' in x['aviso'] for x in av), f'debería avisar la toma 3 repetida seguida: {av}')
    ok(not any('pasa de' in x['aviso'] for x in av), 'un gancho de 17 s no debería avisar que dura de más')
    bl[1]['fin_max'] = 75.0
    rotar.planear(bl, mapa_f, os.path.join(r, 'voz'), 900.0, 30)
    av = json.load(open(os.path.join(r, rotar.AVISOS), encoding='utf-8'))
    ok(any('el gancho' in x['aviso'] and 'pasa de 45-60 s' in x['aviso'] for x in av), f'un gancho de 75 s debería avisar: {av}')

    # 4. para «entramos en modo fastboot» elige la pantalla FASTBOOT (antes, la primera pantalla USB del grabado)
    alineacion([(0.0, 'Con volumen menos entramos en modo fastboot.')], os.path.join(r, 'voz'), 'L09')
    fb = [{'id': 'L09', 'inicio_min': 10.0, 'montaje': {'modo': 'congelar', 'src_inicio': 800.0, 'congelar_s': 6.5}}]
    plan = rotar.planear(fb, mapa_f, os.path.join(r, 'voz'), 900.0, 30, guardar_avisos=False)
    ok([s for s, _ in plan.get('L09', [])][:1] == [130.0], f'para la frase de fastboot debería elegir FASTBOOT (130 s): {plan}')

    # 5. con palabras empatadas, lo nítido y quieto, y nunca un trozo que cambia de pantalla a la mitad
    json.dump({'cuadros': [{'t': 420.0, 'texto': 'Bienvenido | Ajustes'}, {'t': 500.0, 'texto': 'Bienvenido | Ajustes'}]},
              open(mapa_f, 'w', encoding='utf-8'))
    alineacion([(0.0, 'Y ya queda libre y funcionando.')], os.path.join(r, 'voz'), 'L09')
    tt = np.arange(0, 900, 0.2)
    ni, mo = np.full(len(tt), 10.0), np.full(len(tt), 5.0)
    ni[(tt >= 420) & (tt <= 426)], mo[(tt >= 420) & (tt <= 426)] = 100.0, 0.1
    ni[(tt >= 500) & (tt <= 506)], mo[(tt >= 500) & (tt <= 506)] = 2.0, 30.0
    fb[0]['montaje']['congelar_s'] = 6.0
    sin_nt = [s for s, _ in rotar.planear(fb, mapa_f, os.path.join(r, 'voz'), 900.0, 30, guardar_avisos=False).get('L09', [])]
    con_nt = [s for s, _ in rotar.planear(fb, mapa_f, os.path.join(r, 'voz'), 900.0, 30, guardar_avisos=False, nt=(tt, ni, mo)).get('L09', [])]
    ok(sin_nt[:1] == [500.0], f'sin datos de nitidez, el después sale de lo último del grabado (como antes): {sin_nt}')
    ok(con_nt[:1] == [420.0], f'con datos de nitidez debería elegir el trozo nítido y quieto (420 s): {con_nt}')
    json.dump({'cuadros': [{'t': 420.0, 'texto': 'Bienvenido | Ajustes'}, {'t': 500.0, 'texto': 'Bienvenido | Ajustes'},
                           {'t': 502.0, 'texto': 'Cargando | Espere'}]}, open(mapa_f, 'w', encoding='utf-8'))
    cambia = [s for s, _ in rotar.planear(fb, mapa_f, os.path.join(r, 'voz'), 900.0, 30, guardar_avisos=False).get('L09', [])]
    ok(cambia[:1] == [420.0], f'un trozo que cambia de pantalla en sus 3-5 s debería perder: {cambia}')

    # 6. montaje.py de verdad (video sintético, 360p): la pausa del gancho muestra la toma de cada frase, con los cuadros justos
    m = os.path.join(tmp, 'montaje')
    os.makedirs(os.path.join(m, 'voz'))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30', '-t', '120', '-c:v', 'libx264',
                    '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', os.path.join(m, 'original.mp4')], check=True)
    json.dump({'cuadros': [{'t': 10.0, 'texto': 'Verifica tu cuenta | Google'}, {'t': 30.0, 'texto': 'FASTBOOT MODE'},
                           {'t': 60.0, 'texto': 'Unlocker tool'}, {'t': 100.0, 'texto': 'Bienvenido | Ajustes'}]},
              open(os.path.join(m, 'mapa_video.json'), 'w', encoding='utf-8'))
    frases = [(0.0, 'Así queda tu Honor, libre.'), (3.0, 'Te pedía la cuenta de Google.'), (6.0, 'Y entramos en fastboot.')]
    alineacion(frases, os.path.join(m, 'voz'), 'L01')
    json.dump({'bloques': [
        {'id': 'L01', 'gancho': True, 'texto': ' '.join(f for _, f in frases), 'inicio_min': 0.0, 'fin_max': 9.0,
         'tomas': [[100, 104], [10, 14], [30, 34]],
         'montaje': {'modo': 'lento+congelar', 'src_inicio': 0.0, 'src_fin': 1.0, 'velocidad': 1.0, 'congelar_s': 8.0, 'repetir': 'ida_vuelta'}},
        {'id': 'L02', 'texto': 'Paso uno.', 'inicio_min': 9.0, 'fin_max': 13.0,
         'montaje': {'modo': 'lento', 'src_inicio': 1.0, 'src_fin': 5.0, 'velocidad': 1.0}}]},
        open(os.path.join(m, 'guion.json'), 'w', encoding='utf-8'))
    hecho = subprocess.run([sys.executable, os.path.join(RAIZ, 'montaje', 'montaje.py'), '--original', 'original.mp4', '--guion',
                            'guion.json', '--salida', '1_montaje.mp4', '--calidad', '360'], cwd=m, capture_output=True, text=True, timeout=240)
    ok(hecho.returncode == 0, f'montaje.py falló: {hecho.stderr[-400:]}')

    def cuadro(video, s):
        crudo = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{s:.3f}', '-i', video, '-frames:v', '1', '-vf',
                                'scale=160:90,format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
        return np.frombuffer(crudo, np.uint8)[:160 * 60].astype(float)  # sin la franja de abajo (el rótulo del borrador)
    if hecho.returncode == 0:
        n = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
                            '-of', 'csv=p=0', os.path.join(m, '1_montaje.mp4')], capture_output=True, text=True).stdout.strip()
        ok(n == '390', f'el montaje debería tener 13 s justos (390 cuadros): {n}')
        orig = os.path.join(m, 'original.mp4')
        for t_armado, s_toma in ((2.0, 101.0), (4.5, 11.2), (7.5, 31.2)):  # cada frase con su toma (frases en 0,3 s, 3,3 s y 6,3 s)
            c = cuadro(os.path.join(m, '1_montaje.mp4'), t_armado)
            dif = {s: float(np.abs(c - cuadro(orig, s)).mean()) for s in (0.5, 11.2, 31.2, 101.0, s_toma)}
            ok(min(dif, key=dif.get) == s_toma, f'en {t_armado} s del montaje debería verse la toma de {s_toma} s del grabado: {dif}')
finally:
    os.chdir(viejo_cwd)
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: primer minuto (sección INICIO, gancho sin castigo, tomas de la IA, fastboot, nitidez)')
sys.exit(1 if fallos else 0)
