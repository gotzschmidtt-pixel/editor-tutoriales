"""Prueba rápida de los arreglos de la revisión X1 (seguridad y gastos). Sin internet y sin gastar nada: tus ajustes,
claves y proyectos no se tocan (todo va a una carpeta temporal).
- desde este PC, una página con otro nombre (DNS rebinding) no puede leer nada; localhost y estudio.localhost sí;
- «Borrar todo» conserva la pantalla grabada, las fotos HD de la miniatura y el inicio hecho aparte;
- guardar la lista de testimonios no borra el audio de antes (NOMBRE_sin_limpiar.mp4) de uno que sigue;
- «📤 Prestar mis claves» no deja probar más de 3 PIN aunque lleguen todos a la vez.
Uso: python tests/test_revision_x1.py   (sale con 1 si algo falla)
"""
import http.client, json, os, shutil, sys, tempfile, threading, time
from http.server import ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'app'))
os.environ['SIN_NAVEGADOR'] = '1'
import app  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


tmp = tempfile.mkdtemp(prefix='x1_')
app.AJUSTES = os.path.join(tmp, 'ajustes.json')  # nunca el app/ajustes.json de verdad
app.PROYECTOS = os.path.join(tmp, 'proyectos')
srv = ThreadingHTTPServer(('127.0.0.1', 0), app.Manejador)
PUERTO = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def pedir(metodo, ruta, cuerpo=None, host=None):
    c = http.client.HTTPConnection('127.0.0.1', PUERTO, timeout=20)
    c.request(metodo, ruta, body=cuerpo, headers={'Host': host or f'127.0.0.1:{PUERTO}'})
    r = c.getresponse()
    return r.status, r.read()


def crear(d, nombres):
    for n in nombres:
        os.makedirs(os.path.dirname(os.path.join(d, n)), exist_ok=True)
        open(os.path.join(d, n), 'w').write('{}')


try:
    # 1. el nombre (Host) con que se llama desde este PC
    crear(os.path.join(app.PROYECTOS, 'p'), ['original.mp4'])
    for host in (f'malo.example:{PUERTO}', 'malo.example', f'192.168.1.5:{PUERTO}'):
        st, _ = pedir('GET', '/archivo?p=p&f=original.mp4', host=host)
        ok(st == 403, f'con el nombre «{host}» debía dar 403 (dio {st})')
    for host in (f'localhost:{PUERTO}', f'127.0.0.1:{PUERTO}', 'estudio.localhost', f'[::1]:{PUERTO}', f'LOCALHOST:{PUERTO}'):
        st, _ = pedir('GET', '/archivo?p=p&f=original.mp4', host=host)
        ok(st != 403, f'con el nombre «{host}» la app debe abrir (dio {st})')

    # 2. «Borrar todo» conserva lo que subiste en «🎛 Audio e imagen» y el inicio hecho aparte
    d = os.path.join(app.PROYECTOS, 'borrar')
    quedan = ['original.mp4', 'pantalla_grabada.mp4', 'foto_miniatura_antes.jpg', 'foto_miniatura_despues.jpg',
              'prueba_inicio/inicio_con_logos.mp4']
    crear(d, quedan + ['guion.json', 'FINAL.mp4'])
    pedir('POST', '/api/empezar_de_nuevo?p=borrar')
    ok(all(os.path.exists(os.path.join(d, f)) for f in quedan), '«Borrar todo» borró: ' + str([f for f in quedan if not os.path.exists(os.path.join(d, f))]))
    ok(not os.path.exists(os.path.join(d, 'guion.json')), '«Borrar todo» debe borrar lo generado')

    # 3. guardar la lista de testimonios no borra el audio de antes de uno que sigue
    d = os.path.join(app.PROYECTOS, 'testi', 'testimonios')
    crear(d, ['abc.mp4', 'abc_sin_limpiar.mp4', 'abc_sin_zoom.mp4', 'xyz.mp4', 'xyz_sin_limpiar.mp4'])
    pedir('POST', '/api/pistas?p=testi&g=testimonios', json.dumps({'TESTIMONIOS': [{'archivo': 'abc.mp4', 'nota': 'nueva'}]}).encode())
    ok(all(os.path.exists(os.path.join(d, f)) for f in ('abc.mp4', 'abc_sin_limpiar.mp4', 'abc_sin_zoom.mp4')),
       'guardar los testimonios borró el audio de antes de uno que sigue: ' + str(sorted(os.listdir(d))))
    ok(not os.path.exists(os.path.join(d, 'xyz.mp4')) and not os.path.exists(os.path.join(d, 'xyz_sin_limpiar.mp4')),
       'el testimonio quitado (y su audio de antes) debía borrarse: ' + str(sorted(os.listdir(d))))

    # 4. «📤 Prestar mis claves» desde la otra PC: máximo 3 PIN, aunque lleguen todos a la vez
    app.celular.es_local = lambda ip: False  # el pedido hace de venir de la otra PC de la casa
    app.celular.red_permitida = lambda ip: True
    c = {'activo': True}
    app.celular.nuevo_pin(c, '123456')
    json.dump({'celular': c, 'elevenlabs': 'sk-eleven'}, open(app.AJUSTES, 'w'))
    revisados = []

    def lento(aj, ip, pin):
        revisados.append(pin)
        time.sleep(0.3)
        return '', 'PIN equivocado.'
    app.celular.entrar = lento
    app.PRESTAMO.update(hasta=time.time() + 300, fallos=0)
    hilos = [threading.Thread(target=pedir, args=('POST', '/api/claves/prestar', json.dumps({'pin': f'{k:06d}'}).encode(), f'192.168.1.20:{PUERTO}'))
             for k in range(30)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    ok(len(revisados) <= 3, f'con 30 PIN a la vez se revisaron {len(revisados)} (máximo 3)')
    ok(app.PRESTAMO['hasta'] == 0.0, 'tras 3 PIN equivocados el préstamo debe cerrarse')
finally:
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión X1 (nombre desde el PC, borrar todo, testimonios, prestar claves)')
sys.exit(1 if fallos else 0)
