"""Prueba rápida de los arreglos de la revisión X2 (contratos entre la página y la app). Sin internet y sin gastar nada:
tus ajustes, claves y proyectos no se tocan (todo va a una carpeta temporal).
- «🔁 Rehacer video» funciona (antes daba error 500: una variable tapaba el módulo respaldo) y copia el FINAL antes;
- «Último proyecto» no elige «.canal» ni «_prueba…» ni una carpeta con puntos o paréntesis;
- un error en un pedido GET contesta con su mensaje (antes la conexión se cortaba y la página quedaba esperando);
- sin internet, YouTube dice «Sin conexión con YouTube» en vez de quedar en «Revisando…»;
- una carpeta con puntos o paréntesis sale en la lista como aviso (no se puede elegir) y no se abre vacía.
Uso: python tests/test_revision_x2.py   (sale con 1 si algo falla)
"""
import contextlib, http.client, io, json, os, re, shutil, sys, tempfile, threading, time, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'app'))
os.environ['SIN_NAVEGADOR'] = '1'
import app  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


tmp = tempfile.mkdtemp(prefix='x2_')
app.AJUSTES = os.path.join(tmp, 'ajustes.json')  # nunca el app/ajustes.json de verdad
app.PROYECTOS = os.path.join(tmp, 'proyectos')
srv = ThreadingHTTPServer(('127.0.0.1', 0), app.Manejador)
PUERTO = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def pedir(metodo, ruta, cuerpo=None):
    c = http.client.HTTPConnection('127.0.0.1', PUERTO, timeout=20)
    c.request(metodo, ruta, body=cuerpo, headers={'Host': f'127.0.0.1:{PUERTO}'})
    r = c.getresponse()
    return r.status, r.read()


def crear(d, nombres):
    for n in nombres:
        os.makedirs(os.path.dirname(os.path.join(d, n)), exist_ok=True)
        open(os.path.join(d, n), 'w').write('{}')


try:
    # 1. «🔁 Rehacer video»: responde bien y el FINAL queda copiado antes de borrarlo
    d = os.path.join(app.PROYECTOS, 'Rehacer')
    crear(d, ['guion.json', 'FINAL.mp4'])
    st, cuerpo = pedir('POST', '/api/actualizar?p=Rehacer')
    ok(st == 200, f'«Rehacer video» debía responder 200 (dio {st}: {cuerpo[:200]!r})')
    if st == 200:
        r = json.loads(cuerpo)
        ok(r.get('copias') and all(os.path.exists(os.path.join(d, x)) for x in r['copias']), f'el FINAL no quedó copiado: {r}')
        ok(os.path.exists(os.path.join(d, 'guion.json')), '«Rehacer video» no debe borrar el guion')

    # 2. «Último proyecto»: «.canal», «_prueba» o una carpeta con paréntesis no cuentan aunque sean las más nuevas
    time.sleep(0.05)
    for x in ('.canal', '_prueba_claude', 'Samsung A15 (FRP) v1.2'):
        crear(os.path.join(app.PROYECTOS, x), ['algo.json'])
    st, cuerpo = pedir('GET', '/api/ultimo_proyecto')
    ok(st == 200 and json.loads(cuerpo).get('nombre') == 'Rehacer', f'el último proyecto debía ser «Rehacer»: {cuerpo[:200]!r}')

    # 3. un error en un GET contesta con su mensaje (no corta la conexión)
    viejo = app.ultimo_proyecto

    def sin_red():
        raise OSError('sin red')
    app.ultimo_proyecto = sin_red
    try:
        with contextlib.redirect_stderr(io.StringIO()):  # el traceback que imprime la app no ensucia la prueba
            st, cuerpo = pedir('GET', '/api/ultimo_proyecto')
        ok(st == 500 and 'sin red' in json.loads(cuerpo or b'{}').get('error', ''), f'un error en GET debía dar 500 con mensaje: {st} {cuerpo[:200]!r}')
    except (http.client.HTTPException, OSError) as e:
        ok(False, f'un error en GET cortó la conexión: {e!r}')
    finally:
        app.ultimo_proyecto = viejo

    # 4. sin internet, YouTube contesta «Sin conexión con YouTube» (pedir y el permiso)
    yt = app.youtube
    abrir = urllib.request.urlopen

    def corte(*a, **k):
        raise urllib.error.URLError(ConnectionRefusedError('sin internet'))
    urllib.request.urlopen = corte
    try:
        c = {'cliente': {'client_id': 'x', 'client_secret': 'y'}, 'token': {'refresh': 'r', 'acceso': 'a', 'vence': time.time() + 999}}
        for nombre, f in (('pedir', lambda: yt.pedir(c, 'GET', yt.API + '/channels')),
                          ('permiso', lambda: yt.acceso(dict(c, token={'refresh': 'r'})))):
            try:
                f()
                ok(False, f'{nombre}: sin internet debía fallar')
            except yt.ErrorYT as e:
                ok('Sin conexión con YouTube' in str(e), f'{nombre}: mensaje poco claro: {e}')
            except Exception as e:
                ok(False, f'{nombre}: sin internet debía dar ErrorYT (dio {e!r})')
        json.dump({'youtube': c}, open(app.AJUSTES, 'w'))
        try:
            st, cuerpo = pedir('GET', '/api/youtube/estado?canal=1')
            ok(st == 200 and 'Sin conexión' in json.loads(cuerpo or b'{}').get('error', ''), f'/api/youtube/estado sin internet: {st} {cuerpo[:200]!r}')
        except (http.client.HTTPException, OSError) as e:
            ok(False, f'/api/youtube/estado sin internet cortó la conexión: {e!r}')
    finally:
        urllib.request.urlopen = abrir

    # 5. las páginas: la lista avisa las carpetas con signos y YouTube no queda en «Revisando…»
    html = open(os.path.join(RAIZ, 'app', 'index.html'), encoding='utf-8').read()
    ok('<option disabled>⚠ ${p}: renombra la carpeta' in html, 'la lista debe avisar las carpetas con puntos o paréntesis')
    yth = open(os.path.join(RAIZ, 'app', 'youtube.html'), encoding='utf-8').read()
    m = re.search(r'async function conexion\(\) \{(.*?)\n\}', yth, re.S)
    ok(m and re.search(r"try \{ e = await api\('/api/youtube/estado", m.group(1)) and 'catch (x)' in m.group(1),
       'conexion() de youtube.html debe mostrar el error en vez de quedar en «Revisando…»')
finally:
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión X2 (rehacer video, último proyecto, errores en GET, YouTube sin internet, nombres con signos)')
sys.exit(1 if fallos else 0)
