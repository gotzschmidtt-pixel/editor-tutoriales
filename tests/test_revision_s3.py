"""Prueba rápida de los arreglos de la revisión S3 (lo que hace el servidor para app/index.html). Sin internet y sin gastar
nada: nada arranca de verdad y tus ajustes, conocimientos y proyectos no se tocan (todo va a una carpeta temporal).
- «+ Marca» con el nombre de una marca que ya existe no deja vacío su archivo;
- «🗑 Borrar todo» conserva FINAL_EN.mp4, sigue aunque un archivo esté abierto y avisa cuál quedó;
- la app no se reinicia, no se actualiza ni se cierra mientras sube a YouTube o comprime un video.
Uso: python tests/test_revision_s3.py   (sale con 1 si algo falla)
"""
import http.client, http.server, json, os, shutil, sys, tempfile, threading

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'app'))
os.environ['SIN_NAVEGADOR'] = '1'
import app  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


tmp = tempfile.mkdtemp()
app.AJUSTES = os.path.join(tmp, 'ajustes.json')  # nunca el app/ajustes.json de verdad
app.PROYECTOS = os.path.join(tmp, 'proyectos')
co = app.conocimiento  # nunca tu mis_conocimientos de verdad
co.CARPETA = os.path.join(tmp, 'mis_conocimientos')
co.PRINCIPAL = os.path.join(co.CARPETA, 'CONOCIMIENTO.md')
co.APRENDIDO = os.path.join(co.CARPETA, 'aprendido_de_proyectos.md')
co.MARCAS = os.path.join(co.CARPETA, 'marcas')
LANZADOS = []
app.subprocess.Popen, popen_antes = (lambda *a, **k: LANZADOS.append(a)), app.subprocess.Popen  # /api/reiniciar no abre otra copia
TIMERS = []
app.threading.Timer, timer_antes = (lambda *a, **k: TIMERS.append(a) or type('T', (), {'start': lambda s: None})()), app.threading.Timer
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), app.Manejador)
PUERTO = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def pedir(metodo, ruta, cuerpo=None):
    c = http.client.HTTPConnection('127.0.0.1', PUERTO, timeout=30)
    c.request(metodo, ruta, body=cuerpo, headers={'Host': f'127.0.0.1:{PUERTO}'})
    r = c.getresponse()
    return r.status, r.read()


try:
    # «+ Marca» con «motorola» cuando MOTOROLA.md ya tiene meses de notas
    os.makedirs(co.MARCAS)
    texto = '# MOTOROLA\n\n## Conocimiento (textos)\nDFU: soltar Power a los 3 s\n' * 40
    open(os.path.join(co.MARCAS, 'MOTOROLA.md'), 'w', encoding='utf-8').write(texto)
    st, b = pedir('POST', '/api/conocimiento/marca_guardar', json.dumps({'marca': 'motorola', 'texto': '', 'nuevo': True}).encode())
    ok(st == 200 and open(os.path.join(co.MARCAS, 'MOTOROLA.md'), encoding='utf-8').read() == texto,
       f'«+ Marca» de una que ya existe no debe vaciarla: {st} {b[:120]!r}')
    st, b = pedir('POST', '/api/conocimiento/marca_guardar', json.dumps({'marca': 'oppo', 'texto': '', 'nuevo': True}).encode())
    ok(st == 200 and os.path.exists(os.path.join(co.MARCAS, 'OPPO.md')), f'«+ Marca» nueva debe crear su archivo: {st} {b[:120]!r}')
    st, _ = pedir('POST', '/api/conocimiento/marca_guardar', json.dumps({'marca': 'MOTOROLA', 'texto': 'editado a mano'}).encode())
    ok(open(os.path.join(co.MARCAS, 'MOTOROLA.md'), encoding='utf-8').read() == 'editado a mano',
       '«💾 Guardar cambios de la marca» debe seguir guardando')

    # «🗑 Borrar todo»: la versión en inglés queda, y un archivo abierto no corta el resto
    d = os.path.join(app.PROYECTOS, 'borrar')
    os.makedirs(os.path.join(d, 'voz'))
    for f in ('original.mp4', 'FINAL_EN.mp4', 'FINAL.mp4', 'guion.json', 'zz_ultimo.json', 'voz/L1.mp3'):
        open(os.path.join(d, f), 'w').write('x')
    borrar_antes = app.borrar_seguro
    app.borrar_seguro = lambda f, intentos=10: False if os.path.basename(f) == 'FINAL.mp4' else borrar_antes(f, 1)  # «WinError 32»
    try:
        st, b = pedir('POST', '/api/empezar_de_nuevo?p=borrar')
    finally:
        app.borrar_seguro = borrar_antes
    r = json.loads(b or b'{}')
    ok(st == 200 and r.get('quedaron') == ['FINAL.mp4'], f'«Borrar todo» debe avisar qué quedó abierto: {st} {b[:200]!r}')
    ok(os.path.exists(os.path.join(d, 'FINAL_EN.mp4')) and os.path.exists(os.path.join(d, 'original.mp4')),
       '«Borrar todo» debe conservar FINAL_EN.mp4 y tu video')
    ok(not any(os.path.exists(os.path.join(d, f)) for f in ('guion.json', 'zz_ultimo.json', 'voz')),
       '«Borrar todo» debe seguir borrando lo demás aunque un archivo esté abierto')

    # mientras sube a YouTube o comprime: ni reiniciar, ni actualizar, ni cerrar
    app.actualizar_app, act_antes = (lambda: LANZADOS.append('actualizar') or {'mensaje': 'x'}), app.actualizar_app
    for estado in ({'yt': 'subiendo'}, {'yt': 'detalles'}, {'comprimir': True}):
        app.YT.clear()
        app.comprimir.ESTADO['activo'] = bool(estado.get('comprimir'))
        if estado.get('yt'):
            app.YT['MOTOROLA_FRP'] = {'estado': estado['yt'], 'avance': 40, 'avisos': []}
        for ruta in ('/api/reiniciar', '/api/actualizar_app', '/api/salir'):
            LANZADOS.clear(); TIMERS.clear()
            st, b = pedir('POST', ruta, b'{}')
            ok(st >= 400 and not LANZADOS and not TIMERS, f'{ruta} con {estado} debe esperar: {st} {b[:120]!r}')
    app.YT.clear(); app.comprimir.ESTADO['activo'] = False
    LANZADOS.clear()
    st, _ = pedir('POST', '/api/reiniciar', b'{}')
    ok(st == 200 and len(LANZADOS) == 1, f'sin nada corriendo, «reiniciar» debe abrir la copia nueva ({st}, {LANZADOS})')
    app.actualizar_app = act_antes
finally:
    app.subprocess.Popen, app.threading.Timer = popen_antes, timer_antes
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión S3 (marca existente, borrar todo, no reiniciar con subidas o compresión)')
sys.exit(1 if fallos else 0)
