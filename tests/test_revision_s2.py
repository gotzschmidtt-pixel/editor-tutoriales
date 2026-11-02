"""Prueba rápida de los arreglos de la revisión S2 (app/app.py). Sin internet y sin gastar nada: los trabajos no arrancan
de verdad y tus ajustes, claves y proyectos no se tocan (todo va a una carpeta temporal).
- la página de vuelta de YouTube no deja meter código; «Origin: null» no pasa como si fuera la app;
- «Comprobar clave» no manda la clave guardada de una IA a otra dirección;
- «▶ Hacer todo» y «📦 Exportar ZIP» transcriben con Whisper (gratis), no con Scribe;
- aprobar en la vista previa no quita tarjetas, logos, testimonios ni tráiler;
- «Borrar todo» conserva lo que subiste o ya pagaste;
- «⬇ Actualizar la app» con git no deja tus cambios escondidos si no puede actualizar.
Uso: python tests/test_revision_s2.py   (sale con 1 si algo falla)
"""
import http.client, http.server, json, os, shutil, subprocess, sys, tempfile, threading, time

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
app.MUSICA_FIJA = os.path.join(tmp, 'musica_fija.mp3')
open(app.MUSICA_FIJA, 'wb').write(b'x')
LANZADOS = []
app.correr_despierto = lambda p, pasos, datos: (LANZADOS.append((list(pasos), dict(datos))), app.TRABAJO.update(proyecto=None))
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), app.Manejador)
PUERTO = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def pedir(metodo, ruta, cuerpo=None, cab=None):
    c = http.client.HTTPConnection('127.0.0.1', PUERTO, timeout=20)
    c.request(metodo, ruta, body=cuerpo, headers={'Host': f'127.0.0.1:{PUERTO}', **(cab or {})})
    r = c.getresponse()
    return r.status, r.read()


def lanzado():
    for _ in range(100):
        if LANZADOS:
            return LANZADOS.pop()
        time.sleep(0.05)
    return None


def crear(d, nombres):
    for n in nombres:
        os.makedirs(os.path.dirname(os.path.join(d, n)), exist_ok=True)
        open(os.path.join(d, n), 'w').write('{}')


try:
    st, b = pedir('GET', '/api/youtube/volver?error=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E')
    ok(b'<img' not in b and b'&lt;img' in b, f'la vuelta de YouTube debe escapar el error: {b[:200]!r}')
    st, _ = pedir('POST', '/api/probar_ia', b'{"url": "http://127.0.0.1:1/v1"}', {'Origin': 'null'})
    ok(st == 403, f'«Origin: null» debe dar 403 (dio {st})')
    st, _ = pedir('POST', '/api/probar_ia', b'{"url": "http://127.0.0.1:1/v1"}', {'Origin': f'http://localhost:{PUERTO}'})
    ok(st == 200, f'la propia app debe pasar (dio {st})')

    vistos = []
    app.probar_clave = lambda d: (vistos.append(d.get('clave')), {'ok': True, 'mensaje': '', 'modelos': []})[1]
    json.dump({'ias_guion': {'gpt': {'clave': 'sk-GPT'}}}, open(app.AJUSTES, 'w'))
    pedir('POST', '/api/probar_ia', b'{"ia": "gpt", "url": "http://otro.example/v1", "clave": ""}')
    pedir('POST', '/api/probar_ia', b'{"ia": "gpt", "url": "https://api.openai.com/v1", "clave": ""}')
    ok(vistos == ['', 'sk-GPT'], f'la clave guardada de GPT solo va a api.openai.com: {vistos}')

    json.dump({'modelo': 'm', 'url': 'http://127.0.0.1:1', 'elevenlabs': 'sk-eleven'}, open(app.AJUSTES, 'w'))
    crear(os.path.join(app.PROYECTOS, 'nuevo'), ['original.mp4'])
    for paso, datos in (('todo', {'confirmo': 'SI'}), ('ia', {'tarea': 'guion', 'modo': 'paquete'})):
        st, b = pedir('POST', f'/api/ejecutar?p=nuevo&paso={paso}', json.dumps(datos).encode())
        r = lanzado()
        ok(r and r[0][0] == 'transcribir' and r[1].get('motor') == 'whisper', f'«{paso}» sin transcripción debe usar Whisper: {st} {b[:100]!r} {r}')

    json.dump({}, open(app.AJUSTES, 'w'))
    d = os.path.join(app.PROYECTOS, 'extras')
    crear(d, ['original.mp4', '3_voz.mp4', '4_musica.mp4', 'etiquetas.json', 'senales.json', 'trailer.json', 'guion.json', 'voz/L1.mp3',
              'tarjetas/tarjetas.json', 'testimonios/testimonios.json'])
    todos = ['etiquetas', 'senales', 'tarjetas', 'logos', 'testimonios', 'trailer']
    pedir('POST', '/api/ejecutar?p=extras&paso=extras', json.dumps({'solo': todos}).encode())
    r = lanzado()
    ok(r and r[1].get('_pausa') == 'vista' and 'testimonios' in r[0], f'debe pararse en la vista previa con el resto armado: {r}')
    pedir('POST', '/api/ejecutar?p=extras&paso=extras', json.dumps({'solo': ['etiquetas', 'senales'], 'revisado': True, 'sin_ia': True}).encode())
    r = lanzado()
    ok(r and all(x in r[0] for x in todos), f'«▶ Ponerlas en el video» debe volver a poner todos los extras: {r and r[0]}')

    d = os.path.join(app.PROYECTOS, 'borrar')
    quedan = ['original.mp4', 'short_extras/t.mp4', 'miniatura_subida.jpg', 'avatar_ahorro/heygen/avatar_01.mp4', 'apoyo/toma.mp4',
              'miniatura/referencias/r.jpg', 'inicio_fijo.json', 'prueba_inicio/x.mp4', 'difuminar_datos.json', 'difuminar_datos/c.png',
              'FINAL_antes_rehacer_1_FINAL.mp4']
    crear(d, quedan + ['guion.json', 'FINAL.mp4', 'voz/L1.mp3'])
    json.dump({'video': 'prueba_inicio/x.mp4', 'hasta': 5}, open(os.path.join(d, 'inicio_fijo.json'), 'w'))
    json.dump({'referencias': [{'imagen': 'difuminar_datos/c.png', 'zonas': []}]}, open(os.path.join(d, 'difuminar_datos.json'), 'w'))
    pedir('POST', '/api/empezar_de_nuevo?p=borrar')
    ok(all(os.path.exists(os.path.join(d, f)) for f in quedan), '«Borrar todo» borró: ' + str([f for f in quedan if not os.path.exists(os.path.join(d, f))]))
    ok(not os.path.exists(os.path.join(d, 'FINAL.mp4')) and not os.path.exists(os.path.join(d, 'guion.json')), '«Borrar todo» debe borrar lo generado')

    if shutil.which('git'):  # «⬇ Actualizar la app» en un repositorio de prueba
        def g(cwd, *a):
            return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *a], cwd=cwd, capture_output=True, text=True, check=True).stdout
        ori, clon, otro = (os.path.join(tmp, x) for x in ('ori.git', 'clon', 'otro'))
        g(tmp, 'init', '-q', '--bare', ori)
        g(tmp, 'clone', '-q', ori, otro)
        crear(otro, ['app.py'])
        g(otro, 'add', '.'); g(otro, 'commit', '-qm', 'v1'); g(otro, 'push', '-q', 'origin', 'HEAD:rama')
        g(tmp, 'clone', '-q', '-b', 'rama', ori, clon)
        crear(otro, ['nuevo.py'])
        g(otro, 'add', '.'); g(otro, 'commit', '-qm', 'v2'); g(otro, 'push', '-q', 'origin', 'HEAD:rama')
        open(os.path.join(clon, 'app.py'), 'w').write('cambio local')
        open(os.path.join(clon, 'nuevo.py'), 'w').write('mio')
        app.RAIZ = clon
        try:
            app.actualizar_git('rama')
            ok(False, 'con un archivo propio que choca, «Actualizar» debía avisar')
        except RuntimeError as e:
            ok('nuevo.py' in str(e), f'el aviso debe nombrar el archivo que choca: {e}')
        ok(open(os.path.join(clon, 'app.py')).read() == 'cambio local' and not g(clon, 'stash', 'list').strip(),
           'el cambio local no debe quedar escondido en el stash')
finally:
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión S2 (YouTube, origen, claves, Whisper, vista previa, borrar todo, actualizar)')
sys.exit(1 if fallos else 0)
