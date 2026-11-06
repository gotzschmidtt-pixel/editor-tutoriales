"""Prueba rápida de los arreglos de la revisión S7b (celular e instalación). Sin internet y sin gastar nada: todo va a una
carpeta temporal (tus proyectos, tus ajustes y el arranque de Windows de verdad no se tocan).
- muchos PIN a la vez no se saltan el límite de 5 intentos;
- después del PIN el celular solo vuelve a una página de la app («/\\sitio-falso.com» va a «/»);
- la dirección del Wi‑Fi de verdad sale antes que la de WSL o Docker;
- dos toques a «▶ Empezar» en la cola no marcan el segundo proyecto como fallado;
- el arranque de Windows se escribe en UTF‑8 con «chcp 65001» (carpetas con tildes o ñ).
Uso: python tests/test_revision_s7b.py   (sale con 1 si algo falla)
"""
import http.server, json, os, shutil, socket, sys, tempfile, threading, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('celular', 'app'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
os.environ['SIN_NAVEGADOR'] = '1'
import celular  # noqa: E402
import flujo  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


class Falso(http.server.BaseHTTPRequestHandler):
    """Hace de /api/ejecutar: el primero arranca (y el PC queda ocupado), los demás «ya está corriendo»."""
    ocupado = []

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        time.sleep(0.3)  # la red lenta del celular: el segundo toque llega mientras arranca el primero
        if Falso.ocupado:
            cuerpo, codigo = {'error': f'ya está corriendo «Hacer todo» en {Falso.ocupado[0]}'}, 400
        else:
            Falso.ocupado.append(self.path)
            cuerpo, codigo = {'ok': True}, 200
        b = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


tmp = tempfile.mkdtemp(prefix='s7b_')
try:
    # 1. el límite de 5 PIN vale aunque lleguen todos a la vez
    c = {'activo': True}
    celular.nuevo_pin(c, '123456')
    aj = {'celular': c}
    revisados = []
    hash_real = celular._hash

    def contando(pin, sal):
        revisados.append(pin)
        return hash_real(pin, sal)
    celular._hash = contando
    hilos = [threading.Thread(target=celular.entrar, args=(aj, '192.168.1.66', f'{k:06d}')) for k in range(40)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    ok(len(revisados) <= celular.INTENTOS, f'con 40 PIN a la vez se revisaron {len(revisados)} (máximo 5)')
    cookie, aviso = celular.entrar(aj, '192.168.1.66', '123456')
    ok(not cookie and 'Demasiados' in aviso, f'bloqueado, el PIN bueno no debe entrar: {aviso!r}')
    cookie, aviso = celular.entrar(aj, '192.168.1.77', '123456')
    ok(cookie and not aviso and '192.168.1.77' not in celular._FALLOS, f'el PIN bueno desde otra dirección: {aviso!r}')
    celular._FALLOS['192.168.1.66'][1] -= celular.ESPERA + 1  # pasaron los 5 minutos
    cookie, aviso = celular.entrar(aj, '192.168.1.66', '123456')
    ok(cookie and not aviso, f'pasados 5 minutos el PIN bueno entra: {aviso!r}')
    celular._hash = hash_real

    # 2. a dónde vuelve después del PIN
    for volver, queda in [('/\\sitio-falso.com/', '/'), ('\\\\sitio-falso.com', '/'), ('//sitio-falso.com', '/'),
                          ('/\t/sitio-falso.com', '/'), ('/\r\nSet-Cookie: x=1', '/'), ('https://sitio-falso.com', '/'),
                          ('', '/'), (None, '/'), ('/', '/'), ('/editor.html?p=HONOR%208', '/editor.html?p=HONOR%208')]:
        ok(celular.volver_seguro(volver) == queda, f'volver {volver!r} → {celular.volver_seguro(volver)!r} (debe ser {queda!r})')
    ok('sitio-falso' not in celular.pagina_pin('/\\sitio-falso.com/'), 'la pantalla del PIN guarda «/\\sitio-falso.com»')

    # 3. primero la IP del Wi‑Fi de verdad, no la de WSL o Docker
    class Udp:
        def __init__(self, *a):
            pass

        def connect(self, x):
            pass

        def getsockname(self):
            return ('192.168.1.20', 5000)

        def close(self):
            pass
    gai, sock = socket.getaddrinfo, socket.socket
    socket.getaddrinfo = lambda *a, **k: [(2, 1, 6, '', ('172.29.64.1', 0)), (2, 1, 6, '', ('192.168.1.20', 0)),
                                          (2, 1, 6, '', ('100.101.102.103', 0))]
    socket.socket = Udp
    try:
        d = celular.direcciones(8765)
    finally:
        socket.getaddrinfo, socket.socket = gai, sock
    ok(d and d[0]['url'] == 'http://192.168.1.20:8765', f'la primera dirección debe ser la del Wi‑Fi: {d}')
    ok(any('Tailscale' in x['tipo'] for x in d), f'falta la de Tailscale: {d}')

    # 4. dos toques a «▶ Empezar»: el segundo proyecto sigue esperando
    import app  # noqa: E402
    app.AJUSTES = os.path.join(tmp, 'ajustes.json')  # nunca el app/ajustes.json de verdad
    app.PROYECTOS = os.path.join(tmp, 'proyectos')
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Falso)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    app.PUERTO = srv.server_address[1]
    app.ocupado = lambda: bool(Falso.ocupado)
    flujo.guardar_cola(app.PROYECTOS, {'andando': True, 'items': [
        {'id': 'a1', 'p': 'HONOR', 'estado': 'espera'}, {'id': 'b2', 'p': 'MOTOROLA', 'estado': 'espera'}]})
    try:
        hilos = [threading.Thread(target=app.avanzar_cola) for _ in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(20)
        estados = {x['p']: x['estado'] for x in flujo.leer_cola(app.PROYECTOS)['items']}
        ok(estados == {'HONOR': 'corriendo', 'MOTOROLA': 'espera'}, f'dos toques a «Empezar»: {estados}')
        # y si el PC se ocupó con otro trabajo justo antes de arrancar, el proyecto vuelve a la fila (no «fallo»)
        flujo.siguiente(app.PROYECTOS, app.PUERTO, lambda: False)
        estados = {x['p']: x['estado'] for x in flujo.leer_cola(app.PROYECTOS)['items']}
        ok(estados == {'HONOR': 'corriendo', 'MOTOROLA': 'espera'}, f'PC ocupado justo antes: {estados}')
    finally:
        srv.shutdown()

    # 5. el arranque de Windows con tildes o ñ
    ini = os.path.join(tmp, 'Estudio de tutoriales.bat')
    raiz, app.arranque_windows = app.RAIZ, lambda: ini
    app.RAIZ = r'C:\Users\José\Diseño\editor-tutoriales'
    try:
        app.poner_arranque(True)
    finally:
        app.RAIZ = raiz
    b = open(ini, 'rb').read()
    ok(b.startswith(b'@echo off\r\nchcp 65001 >nul\r\n') and 'José\\Diseño'.encode('utf-8') in b,
       f'el arranque debe ir en UTF‑8 con chcp 65001: {b[:120]!r}')
    app.poner_arranque(False)
    ok(not os.path.exists(ini), 'quitar el arranque no borró el archivo')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLA:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('OK: revisión S7b (PIN, volver, direcciones, cola y arranque)')
