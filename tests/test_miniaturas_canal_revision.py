"""Prueba de la revisión de «miniaturas como las de tu canal» (03/11/2026). SIN internet y SIN gastar (GPT simulado):
- «✅ Hacer la final» con una miniatura del canal cuyo id empieza con «-» (YouTube los tiene así): antes argparse lo tomaba
  por otra opción y la final no arrancaba;
- sin YouTube conectado, la lista sale de la página pública (las más nuevas) junto con lo guardado: antes, con un
  videos.json viejo, nunca se miraba la página y faltaban justo las miniaturas más recientes;
- «XIAOMIUNLOCK» solo (sin .com) también frena antes de gastar: es su página;
- a GPT van las mismas miniaturas del canal que «🖼 Miniatura» marca con ✓ (antes la marca salía del guion);
- entre las palabras va el logo del servicio (la G en FRP): si no está guardado, se nombra Google, no el de la marca.
Uso: python tests/test_miniaturas_canal_revision.py   (sale con 1 si algo falla)
"""
import argparse, json, os, sys, tempfile, urllib.request
import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('miniatura', 'mejoras'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
import canal_referencia as cr  # noqa: E402
import miniatura as mini  # noqa: E402
import mejoras  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def sin_red(*a, **k):  # nada de esta prueba sale a internet
    raise AssertionError('la prueba intentó usar la red de verdad')


urllib.request.urlopen = sin_red


def jpg(f):
    cv2.imwrite(f, np.zeros((72, 128, 3), np.uint8))


with tempfile.TemporaryDirectory() as tmp:
    # 1) la final con un id que empieza con «-»: el comando de la app llega entero a miniatura.py
    c = mejoras.comandos('m_miniatura_fotos', tmp, {'confirmo': 'SI', 'texto': 'HONOR|SIN CUENTA GOOGLE', 'calidad': 'media',
                                                    'idiomas': ['es'], 'refs_canal': ['-tJYN-eG1zk', 'honorFRP001']}, 'py', 'aj.json')[0]
    llego = {}
    viejo_con_fotos, viejo_argv = mini.con_fotos, sys.argv
    mini.con_fotos = lambda d, a: llego.update(a=a)
    sys.argv = ['miniatura.py'] + c[2:]
    try:
        mini.main()
    except SystemExit as e:
        ok(False, f'miniatura.py no aceptó el comando de la final ({e}): {c}')
    finally:
        mini.con_fotos, sys.argv = viejo_con_fotos, viejo_argv
    a = llego.get('a')
    ok(a is not None and a.refs_canal == '-tJYN-eG1zk,honorFRP001' and a.calidad == 'media',
       f'las referencias del borrador deberían llegar a la final: {a}')

    # 2) sin YouTube conectado: la página pública (lo más nuevo) + lo guardado (lo viejo), sin repetir
    cr._de_oauth = lambda: None
    cr.VIDEOS_CANAL = os.path.join(tmp, 'videos.json')
    json.dump({'viejo000001': {'id': 'viejo000001', 'titulo': 'Honor de enero', 'publicado': '2026-01-05', 'segundos': 600, 'vistas': 50000},
               'ambos000001': {'id': 'ambos000001', 'titulo': 'Honor de octubre', 'publicado': '2026-10-01', 'segundos': 600, 'vistas': 10}},
              open(cr.VIDEOS_CANAL, 'w', encoding='utf-8'))
    viejo_pagina = cr._de_pagina
    cr._de_pagina = lambda abrir: [{'id': 'nuevo000001', 'titulo': 'Honor de ayer', 'publicado': '2026-11-02', 'segundos': 600, 'vistas': 3},
                                   {'id': 'ambos000001', 'titulo': 'Honor de octubre', 'publicado': '2026-10-01', 'segundos': 600, 'vistas': 900}]
    vs, fuente = cr.lista_videos(sin_red)
    ids = [v['id'] for v in vs]
    ok(ids == ['nuevo000001', 'ambos000001', 'viejo000001'] and next(v for v in vs if v['id'] == 'ambos000001')['vistas'] == 900,
       f'la página (más nueva) y después lo guardado, sin repetir: {ids}')
    ok('página pública' in fuente and 'guardadas' in fuente, f'de dónde salió: {fuente}')
    cr._de_pagina = lambda abrir: None  # sin internet: queda lo guardado
    vs, fuente = cr.lista_videos(sin_red)
    ok([v['id'] for v in vs] == ['viejo000001', 'ambos000001'] and fuente == 'estadísticas guardadas del canal', f'sin la página: {fuente}')
    cr._de_pagina = viejo_pagina

    # 3) «XIAOMIUNLOCK» solo también es su página: frena antes de gastar
    for t in ('XIAOMIUNLOCK', 'Xiaomiunlock 2026'):
        try:
            mini.revisar_textos([t], 'HONOR')
            ok(False, f'«{t}» debería frenar (es su página)')
        except SystemExit as e:
            ok('No se gastó nada' in str(e), f'el aviso de «{t}»: {e}')
    try:
        mini.revisar_textos(['XIAOMI', 'UNLOCK BOOTLOADER'], 'XIAOMI')  # la marca y la palabra sueltas sí van
    except SystemExit as e:
        ok(False, f'«XIAOMI» + «UNLOCK BOOTLOADER» no es una web: {e}')

    # 4) a GPT van las que «🖼 Miniatura» marca con ✓ (el guion nombra iPhone, pero el título es de un Samsung)
    cr.CARPETA = os.path.join(tmp, 'canal')
    os.makedirs(cr.CARPETA)
    ind = {'videos': []}
    for i, t in (('samsungA001', 'Eliminar Cuenta Google Samsung A56'), ('iphoneB0001', 'Bypass Hello iPhone iOS 27'),
                 ('iphoneB0002', 'iCloud Passcode iPhone 15'), ('samsungA002', 'Samsung Galaxy FRP Android 16')):
        jpg(os.path.join(cr.CARPETA, i + '.jpg'))
        m, s = cr.etiquetar(t)
        ind['videos'].append({'id': i, 'titulo': t, 'archivo': i + '.jpg', 'marca': m, 'servicios': s, 'vistas': 100})
    cr.guardar_indice(ind)
    d = os.path.join(tmp, 'Video nuevo')
    os.makedirs(d)
    json.dump({'bloques': [{'texto': 'Este método no sirve para iPhone. Hoy quitamos la cuenta Google de un Samsung Galaxy A15.'}]},
              open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'))
    for k in ('antes', 'despues'):
        mini.guardar_img(os.path.join(d, f'foto_miniatura_{k}.jpg'), np.zeros((72, 128, 3), np.uint8))
    mini.LOGOS_DIR = os.path.join(tmp, 'logos')
    os.makedirs(mini.LOGOS_DIR)
    jpg(os.path.join(mini.LOGOS_DIR, 'honor.png'))
    prompts = []
    mini.imagen_gpt = lambda prompt, refs, **k: (prompts.append(prompt), np.zeros((864, 1536, 3), np.uint8))[1]
    ui = cr.estado(d, 'GALAXY A15 SIN CUENTA GOOGLE')['usar']
    arg = lambda **k: argparse.Namespace(**{**dict(gpt=True, texto='GALAXY A15|SIN CUENTA GOOGLE', fondo='gpt', mixta=False,
                                                   esquina_izq='PASO A PASO', esquina_der='', calidad='baja', idiomas='es', cara=False,
                                                   refs_canal=''), **k})
    mini.con_fotos(d, arg())
    hechas = json.load(open(os.path.join(d, 'miniatura_fotos.json'), encoding='utf-8'))['miniaturas']
    ok(hechas and hechas[0]['refs_canal'] == ui, f'la página marca {ui} y a GPT fueron {hechas[0]["refs_canal"] if hechas else None}')
    ok(hechas and '_baja_' in hechas[0]['archivo'] and len(hechas[0]['archivo'].split('_')[4]) == 10,
       f'el nombre lleva mes, día y hora (no se pisa con uno de otro día): {hechas[0]["archivo"] if hechas else None}')

    # 5) entre las palabras, el logo del servicio: sin google.png se nombra Google (GPT lo dibuja), no Honor
    prompts.clear()
    mini.con_fotos(d, arg(texto='HONOR|SIN CUENTA GOOGLE'))
    ok(prompts and '«HONOR» en blanco, el logo de Google y «SIN CUENTA GOOGLE»' in prompts[0],
       'sin el logo de Google guardado, entre las palabras debería ir Google')
    ok(prompts and 'el logo oficial de honor' in prompts[0], 'el logo de Honor igual va como imagen (para la esquina de arriba)')
    jpg(os.path.join(mini.LOGOS_DIR, 'ios 27.png'))
    prompts.clear()
    mini.con_fotos(d, arg(texto='BYPASS IOS 27|SIN ERRORES'))
    ok(prompts and 'el logo de ios 27 y «SIN ERRORES»' in prompts[0], 'con el logo de iOS guardado, ese va entre las palabras')

print('\n'.join(fallos) or 'ok: revisión de las miniaturas con el estilo del canal')
sys.exit(1 if fallos else 0)
