"""Prueba rápida de los arreglos de la revisión S8b (varios). Sin internet y sin gastar nada: todo va a una carpeta
temporal (tus proyectos, tus videos y tus ajustes no se tocan).
- «Alinear» no acelera ni recorta un «⭐ corte importante»;
- «Avisos de cuidado» no borra tus etiquetas si etiquetas.json tiene un error, y su etiqueta sale (con «en»);
- la nitidez se mide por trozos (mismo resultado, memoria fija) y no usa la caché de otra grabación;
- rehacer «Color parejo» deja la voz que limpiaste y no borra un zoom puesto después;
- «Limpiar voz» con un .webm funciona y, si un testimonio falla, los demás igual se limpian;
- «Cancelar» la compresión con la gráfica no vuelve a empezar con el procesador;
- subir otra grabación borra el análisis del video viejo.
Uso: python tests/test_revision_s8b.py   (sale con 1 si algo falla)
"""
import http.client, http.server, json, os, shutil, subprocess, sys, tempfile, threading, time

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('alinear', 'nitidez', 'limpieza', 'comprimir', 'app'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
os.environ['SIN_NAVEGADOR'] = '1'
import alinear  # noqa: E402
import nitidez  # noqa: E402
import limpiar_voz  # noqa: E402
import comprimir  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def ff(*args):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + list(args), check=True)


def volumen(f):
    r = subprocess.run(['ffmpeg', '-nostdin', '-i', f, '-af', 'volumedetect', '-vn', '-f', 'null', '-'], capture_output=True, text=True)
    return float(next(x for x in r.stderr.splitlines() if 'mean_volume' in x).split()[-2])


def correr(script, *args, cwd):
    return subprocess.run([sys.executable, os.path.join(RAIZ, *script)] + list(args), cwd=cwd, capture_output=True, text=True)


tmp = tempfile.mkdtemp(prefix='s8b_')
try:
    # 1) «Alinear»: un corte importante queda entero y a ×1 (antes salía 343,4–396,7 ×1,24)
    b = {'id': 'L09', 'tipo': 'critico', 'montaje': {'modo': 'lento', 'src_inicio': 339.0, 'src_fin': 382.0, 'velocidad': 1.0,
                                                    'importante': True, 'critico': True}}
    rev = [('Wipe data', 5.3, 344.3, 'wipe data', 350.0), ('Reboot', 30.3, 369.3, 'reboot', 381.0)]
    ok(alinear.ajustar(b, rev, 330.0, 400.0) is None, 'Alinear no debe tocar el tramo de un corte importante')

    # 2) «Avisos de cuidado»: con una coma de más no se pierden tus etiquetas; la etiqueta nueva lleva «en»
    d = os.path.join(tmp, 'avisos')
    os.makedirs(d)
    json.dump({'bloques': [{'id': 'L01', 'texto': 'Hola.'}, {'id': 'L02', 'texto': 'Paso uno: quitamos la cuenta de Google.'}]},
              open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'))
    malo = '[\n {"bloque": "L01", "frase": "Hola", "texto": "a"},\n {"bloque": "L02", "frase": "Paso", "texto": "b"},\n]'
    open(os.path.join(d, 'etiquetas.json'), 'w', encoding='utf-8').write(malo)
    r = correr(('avisos', 'avisos_legales.py'), '--proyecto', '.', cwd=d)
    ok(r.returncode != 0 and open(os.path.join(d, 'etiquetas.json'), encoding='utf-8').read() == malo,
       f'con etiquetas.json roto no debe escribir nada: {r.returncode} {r.stderr[-200:]}')
    open(os.path.join(d, 'etiquetas.json'), 'w', encoding='utf-8-sig').write('[{"bloque": "L01", "frase": "Hola", "texto": "a"}]')
    r = correr(('avisos', 'avisos_legales.py'), '--proyecto', '.', cwd=d)
    et = json.load(open(os.path.join(d, 'etiquetas.json'), encoding='utf-8'))
    ok(r.returncode == 0 and len(et) == 2 and et[0]['frase'] == 'Hola' and et[1].get('en') == 0.3,
       f'el aviso debe sumarse a tus etiquetas, con «en»: {et}')

    # 3) nitidez: por trozos da lo mismo que todo junto, y otra grabación con el mismo nombre se mide de nuevo
    v = os.path.join(tmp, 'original.mp4')
    ff('-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=25:duration=6', '-c:v', 'libx264', '-preset', 'ultrafast', v)
    crudo = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', v, '-vf', f'fps={nitidez.FPS},scale={nitidez.ANCHO}:{nitidez.ALTO},'
                            'format=gray', '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    f = np.frombuffer(crudo, np.uint8).reshape(-1, nitidez.ALTO, nitidez.ANCHO).astype(np.float32)
    lap = f[:, 1:-1, 2:] + f[:, 1:-1, :-2] + f[:, 2:, 1:-1] + f[:, :-2, 1:-1] - 4 * f[:, 1:-1, 1:-1]
    n0 = lap.reshape(len(f), -1).var(axis=1)
    dd = np.abs(np.diff(f, axis=0)).reshape(len(f) - 1, -1).mean(axis=1)
    m0 = np.maximum(np.r_[dd[:1], dd], np.r_[dd, dd[-1:]])
    trozo_antes, nitidez.TROZO = nitidez.TROZO, 7
    try:
        t1, n1, m1 = nitidez.analizar(v)
    finally:
        nitidez.TROZO = trozo_antes
    ok(len(t1) == len(f) and np.allclose(n0, n1) and np.allclose(m0, m1), 'la nitidez por trozos debe dar lo mismo')
    cache = os.path.join(tmp, 'original.nitidez.npz')
    nitidez.analizar(v, cache)
    ff('-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=25:duration=12', '-c:v', 'libx264', '-preset', 'ultrafast', v + '.otra.mp4')
    os.replace(v + '.otra.mp4', v)
    t2, _, _ = nitidez.analizar(v, cache)
    ok(t2[-1] > 11, f'con otra grabación no debe usar la caché vieja (llega hasta {t2[-1]} s)')

    # 4) «Color parejo»: Color → Limpiar voz → Color otra vez deja la voz limpia; con un zoom después, no se rehace
    d = os.path.join(tmp, 'color')
    os.makedirs(d)
    ff('-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=25:duration=3', '-f', 'lavfi', '-i', 'sine=frequency=500:duration=3',
       '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', os.path.join(d, 'original.mp4'))
    r = correr(('color', 'color.py'), '--entrada', 'original.mp4', cwd=d)
    ok(r.returncode == 0, f'Color parejo falló: {r.stderr[-200:]}')
    ff('-i', os.path.join(d, 'original.mp4'), '-af', 'volume=0.001', '-c:v', 'copy', '-c:a', 'aac', os.path.join(d, 'limpio.mp4'))
    os.replace(os.path.join(d, 'limpio.mp4'), os.path.join(d, 'original.mp4'))  # como si se hubiera limpiado la voz
    limpia = volumen(os.path.join(d, 'original.mp4'))
    r = correr(('color', 'color.py'), '--entrada', 'original.mp4', '--fuerza', '0.3', cwd=d)
    ok(r.returncode == 0 and abs(volumen(os.path.join(d, 'original.mp4')) - limpia) < 3,
       'rehacer el color debe dejar la voz limpia')
    time.sleep(1.1)
    shutil.copy(os.path.join(d, 'original.mp4'), os.path.join(d, 'original_sin_zoom.mp4'))  # el zoom se puso después
    antes = os.path.getmtime(os.path.join(d, 'original.mp4'))
    r = correr(('color', 'color.py'), '--entrada', 'original.mp4', cwd=d)
    ok(r.returncode != 0 and os.path.getmtime(os.path.join(d, 'original.mp4')) == antes,
       'con un zoom puesto después del color, rehacer el color no debe borrar el zoom')

    # 5) «Limpiar voz» de testimonios: un .webm y un .mp4 se limpian, y uno roto no frena a los demás
    d = os.path.join(tmp, 'testimonios')
    os.makedirs(d)
    ff('-f', 'lavfi', '-i', 'testsrc=size=160x120:rate=25:duration=2', '-f', 'lavfi', '-i', 'anoisesrc=d=2:a=0.3',
       '-c:v', 'libvpx', '-b:v', '200k', '-c:a', 'libopus', os.path.join(d, '1a2b3c.webm'))
    ff('-f', 'lavfi', '-i', 'testsrc=size=160x120:rate=25:duration=2', '-f', 'lavfi', '-i', 'anoisesrc=d=2:a=0.3',
       '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', os.path.join(d, '9f8e7d.mp4'))
    open(os.path.join(d, '0roto.mp4'), 'wb').write(b'no es un video')
    antes = (limpiar_voz.limpiar_audio, limpiar_voz.carpeta_tmp, limpiar_voz.tiene_audio, sys.argv)
    limpiar_voz.carpeta_tmp = lambda: tmp
    limpiar_voz.tiene_audio = lambda f: True
    limpiar_voz.limpiar_audio = lambda e, wav, motor='pc': limpiar_voz.ff(['-i', e, '-vn', '-af', 'volume=0.01', '-ar', '48000',
                                                                          '-ac', '2', wav]) or 'prueba'  # sin red ni créditos
    sys.argv = ['limpiar_voz.py', '--entrada', d, '--motor', 'ffmpeg']
    try:
        try:
            limpiar_voz.main()
            salio = None
        except SystemExit as e:
            salio = str(e)
    finally:
        limpiar_voz.limpiar_audio, limpiar_voz.carpeta_tmp, limpiar_voz.tiene_audio, sys.argv = antes
    hay = sorted(os.listdir(d))
    ok(salio and '0roto.mp4' in salio, f'debe avisar cuál falló: {salio}')
    ok('1a2b3c_sin_limpiar.webm' in hay and '9f8e7d_sin_limpiar.mp4' in hay and not any('.limpio.' in x for x in hay),
       f'el .webm y el .mp4 deben quedar limpios, sin archivos a medias: {hay}')

    # 6) «Cancelar» con «Rápido con la gráfica»: no empieza otra vez con el procesador
    v = os.path.join(tmp, 'largo.mp4')
    ff('-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30:duration=90', '-c:v', 'libx264', '-preset', 'ultrafast', v)
    sal = comprimir.iniciar(v, 'youtube', 0, True)
    for _ in range(100):
        if comprimir.ESTADO.get('pid'):
            break
        time.sleep(0.05)
    time.sleep(0.4)
    comprimir.cancelar()
    for _ in range(100):
        if not comprimir.ESTADO.get('activo'):
            break
        time.sleep(0.1)
    time.sleep(0.5)
    ok(not comprimir.ESTADO.get('activo') and comprimir.ESTADO.get('error') == 'Cancelado.' and not os.path.exists(sal)
       and 'procesador' not in comprimir.ESTADO.get('perfil', ''), f'«Cancelar» debe detener la compresión: {comprimir.ESTADO}')

    # 7) subir otra grabación borra el análisis del video viejo (nitidez, miniaturas, OCR)
    import app  # noqa: E402
    app.AJUSTES = os.path.join(tmp, 'ajustes.json')  # nunca el app/ajustes.json de verdad
    app.PROYECTOS = os.path.join(tmp, 'proyectos')
    d = os.path.join(app.PROYECTOS, 'subir')
    os.makedirs(d)
    for x in ('original.nitidez.npz', 'original.miniaturas.npz', 'ocr_pantalla.json', 'guion.json'):
        open(os.path.join(d, x), 'w').write('x')
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), app.Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = http.client.HTTPConnection('127.0.0.1', srv.server_address[1], timeout=30)
        c.request('POST', '/api/subir?p=subir&tipo=original', body=b'video nuevo', headers={'Host': f'127.0.0.1:{srv.server_address[1]}'})
        st = c.getresponse().status
    finally:
        srv.shutdown()
    hay = set(os.listdir(d))
    ok(st == 200 and 'guion.json' in hay and not hay & {'original.nitidez.npz', 'original.miniaturas.npz', 'ocr_pantalla.json'},
       f'subir otra grabación debe borrar el análisis viejo: {st} {sorted(hay)}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión S8b (alinear, avisos, nitidez, color, limpiar voz, cancelar compresión, subir otra grabación)')
sys.exit(1 if fallos else 0)
