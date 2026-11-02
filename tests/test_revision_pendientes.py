"""Prueba rápida de los 3 arreglos pendientes de la revisión. Sin internet y sin gastar nada: los pasos largos van simulados,
y tus ajustes y proyectos no se tocan (todo va a una carpeta temporal).
- «✨ Agregar extras» copia el FINAL con tus arreglos a mano antes de borrarlo, y no suma otra copia en cada vuelta;
- la narración de los testimonios y la frase de «Nuevos modelos» no gastan ElevenLabs sin SI (solo se pregunta si falta
  su voz guardada; la página pregunta antes de mandar el pedido);
- guardar una lista vieja de testimonios o tarjetas (otra pestaña, el celular) no borra nada: lo quitado va a _papelera/
  y lo subido hace menos de 10 minutos no se toca.
Uso: python tests/test_revision_pendientes.py   (sale con 1 si algo falla)
"""
import http.client, http.server, io, json, os, re, shutil, subprocess, sys, tempfile, threading, time, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('app', 'testimonios', 'nuevos_modelos', 'mejoras', 'voz'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
os.environ['SIN_NAVEGADOR'] = '1'
for k in ('VOZ_ID', 'VOZ_IDIOMA', 'ELEVENLABS_API_KEY'):
    os.environ.pop(k, None)
import app  # noqa: E402
import testimonios as te  # noqa: E402
import nuevos_modelos as nm  # noqa: E402
import mejoras  # noqa: E402
import pronunciacion  # noqa: E402

PAPELERA = '_papelera'  # donde va lo que quitas de la lista de testimonios, tarjetas o pistas (app.a_papelera)

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def crear(d, nombres):
    for n in nombres:
        os.makedirs(os.path.dirname(os.path.join(d, n)), exist_ok=True)
        open(os.path.join(d, n), 'w').write('{}')


def correr(proyecto, pasos, opciones, hace_final=None, falla_despues=False):
    """Corre los pasos con los comandos simulados: no hacen nada, salvo el paso del final, que escribe FINAL.mp4 con
    `hace_final` (como si la app lo armara). Con `falla_despues`, después falla otro comando del mismo paso (como el
    revisor automático cuando hay un plano largo al inicio)."""
    viejos = (app.comandos, app.asegurar_librerias, app.asegurar_node)

    def comandos(paso, d, op):
        if paso in ('final_sin_trailer', 'trailer') and hace_final is not None:
            return [[sys.executable, '-c', f'open("FINAL.mp4", "wb").write({hace_final!r})']] + \
                ([[sys.executable, '-c', 'raise SystemExit(1)']] if falla_despues else [])
        return []
    app.comandos, app.asegurar_librerias, app.asegurar_node = comandos, (lambda *a: None), (lambda *a: None)
    try:
        app.TRABAJO.update(proyecto=proyecto)
        app.correr(proyecto, list(pasos), dict(opciones))
    finally:
        app.comandos, app.asegurar_librerias, app.asegurar_node = viejos
        app.TRABAJO.update(proyecto=None)


def falsa_eleven(respuesta):
    """ElevenLabs simulado: ningún pedido sale a internet y se ve cuántas veces se le pidió voz."""
    pedidos = []

    def abrir(req, timeout=None):
        pedidos.append(getattr(req, 'full_url', req))
        return io.BytesIO(respuesta)
    return abrir, pedidos


tmp = tempfile.mkdtemp(prefix='pendientes_')
app.AJUSTES = os.path.join(tmp, 'ajustes.json')  # nunca el app/ajustes.json de verdad
app.PROYECTOS = os.path.join(tmp, 'proyectos')
json.dump({}, open(app.AJUSTES, 'w'))
LANZADOS = []
app.correr_despierto = lambda p, pasos, datos: (LANZADOS.append((list(pasos), dict(datos))), app.TRABAJO.update(proyecto=None))
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), app.Manejador)
PUERTO = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def pedir(metodo, ruta, cuerpo=None):
    c = http.client.HTTPConnection('127.0.0.1', PUERTO, timeout=20)
    c.request(metodo, ruta, body=cuerpo, headers={'Host': f'127.0.0.1:{PUERTO}'})
    r = c.getresponse()
    return r.status, r.read()


def lanzado(espera=5):
    for _ in range(int(espera / 0.05)):
        if LANZADOS:
            return LANZADOS.pop()
        time.sleep(0.05)
    return None


try:
    # P1) «✨ Agregar extras» borra el FINAL para volver a armarlo: antes queda copiado si tiene arreglos a mano
    d = os.path.join(app.PROYECTOS, 'extras')
    crear(d, ['original.mp4', '3_voz.mp4', '4_musica.mp4', '8_testimonios.mp4'])
    open(os.path.join(d, 'FINAL.mp4'), 'wb').write(b'final con arreglos a mano')
    open(os.path.join(d, 'FINAL_EN.mp4'), 'wb').write(b'version en ingles')
    copias = lambda: sorted(f for f in os.listdir(d) if f.startswith('FINAL_antes_rehacer_'))
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True})  # el paso siguiente falla: no deja FINAL nuevo
    ok(not os.path.exists(os.path.join(d, 'FINAL.mp4')) and not os.path.exists(os.path.join(d, '8_testimonios.mp4')),
       f'«Agregar extras» debe quitar el FINAL y los extras viejos: {sorted(os.listdir(d))}')
    ok(len(copias()) == 1 and open(os.path.join(d, copias()[0]), 'rb').read() == b'final con arreglos a mano',
       f'el FINAL con arreglos a mano debe quedar copiado antes de borrarlo: {copias()}')
    ok(os.path.exists(os.path.join(d, 'FINAL_EN.mp4')) and not any('FINAL_EN' in f for f in copias()),
       f'solo se copia el FINAL que se borra (FINAL_EN.mp4 ni se toca ni se copia): {copias()}')
    # la app arma el FINAL; «Agregar extras» otra vez (o «▶ Ponerlas en el video»): ese FINAL no se copia, la app lo rehace
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True}, b'final de la app')
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True}, b'final de la app, otra vuelta')
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True}, b'final de la app, tercera vuelta')
    ok(len(copias()) == 1, f'el FINAL que armó la app y nadie tocó no se copia en cada vuelta: {copias()}')
    ok(open(os.path.join(d, 'FINAL.mp4'), 'rb').read() == b'final de la app, tercera vuelta', 'el FINAL nuevo debe quedar')
    # le haces otro arreglo a mano y vuelves a agregar extras (en el mismo minuto): se copia sin pisar la copia anterior
    open(os.path.join(d, 'FINAL.mp4'), 'wb').write(b'otro arreglo a mano, mas largo')
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True}, b'final de la app')
    contenidos = sorted(open(os.path.join(d, f), 'rb').read() for f in copias())
    ok(contenidos == [b'final con arreglos a mano', b'otro arreglo a mano, mas largo'],
       f'cada FINAL con arreglos a mano queda copiado, sin pisar el anterior: {copias()} {contenidos}')
    # el paso escribe el FINAL y después falla (el revisor marca un plano largo al inicio): ese FINAL también es de la app,
    # y las vueltas siguientes no lo copian como si fuera un arreglo a mano
    antes = copias()
    correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True}, b'final de la app, el revisor fallo', falla_despues=True)
    ok(app.FALLOS.get('extras'), 'la prueba debía simular un paso del final que falla después de escribir el FINAL')
    for k in range(3):
        correr('extras', ['final_sin_trailer'], {'_limpiar_extras': True}, b'final de la app, el revisor fallo otra vez', falla_despues=True)
    ok(copias() == antes, f'un FINAL que armó la app no se copia aunque el paso haya fallado después: {copias()}')
    # los otros botones que rearman el FINAL encima («Rehacer» de «Video final sin tráiler», la tarjeta «Etiquetas, flechas
    # y tarjetas», «▶ Armar y unir al video» del tráiler) también copian antes el FINAL con arreglos a mano
    d = os.path.join(app.PROYECTOS, 'rearmar')
    crear(d, ['original.mp4', '3_voz.mp4', '4_musica.mp4', 'trailer.json'])
    copias = lambda: sorted(f for f in os.listdir(d) if f.startswith('FINAL_antes_rehacer_'))
    contenido = lambda f: open(os.path.join(d, f), 'rb').read()
    for k, pasos in enumerate((['final_sin_trailer'], ['etiquetas', 'final_sin_trailer'], ['trailer'])):
        open(os.path.join(d, 'FINAL.mp4'), 'wb').write(b'giro y fotos a mano %d' % k)
        correr('rearmar', pasos, {}, b'final que arma la app %d' % k)
        ok(len(copias()) == k + 1 and any(contenido(f) == b'giro y fotos a mano %d' % k for f in copias())
           and contenido('FINAL.mp4') == b'final que arma la app %d' % k,
           f'{pasos}: el FINAL con arreglos a mano debe quedar copiado antes de rearmarlo: {copias()}')
        correr('rearmar', pasos, {}, b'final que arma la app, otra vez %d' % k)  # el que armó la app no se copia
        ok(len(copias()) == k + 1, f'{pasos}: el FINAL que armó la app no se copia al rearmarlo: {copias()}')
    # ya copiado y el paso falla antes de reescribirlo: al volver a pulsar no se copia otra vez (son varios GB)
    open(os.path.join(d, 'FINAL.mp4'), 'wb').write(b'otro arreglo a mano')
    correr('rearmar', ['final_sin_trailer'], {})
    correr('rearmar', ['final_sin_trailer'], {})
    ok(len(copias()) == 4 and sum(contenido(f) == b'otro arreglo a mano' for f in copias()) == 1,
       f'el FINAL ya copiado no se vuelve a copiar en cada intento: {copias()}')

    # P2) testimonios narrados y «Nuevos modelos»: su voz (ElevenLabs) no se hace sin SI, y solo se pregunta si falta
    d = os.path.join(app.PROYECTOS, 'voces')
    crear(d, ['original.mp4', '3_voz.mp4', '4_musica.mp4', 'testimonios/t1.mp4', 'testimonios/t2.mp4', 'nuevos_modelos/m.mp4'])
    texto = 'Mira lo que dice este cliente contento con su equipo'
    json.dump({'TESTIMONIOS': [{'archivo': 't1.mp4', 'texto': texto}, {'archivo': 't2.mp4', 'texto': ''}]},
              open(os.path.join(d, 'testimonios', 'testimonios.json'), 'w', encoding='utf-8'))
    json.dump({'MODELOS': [{'archivo': 'm.mp4', 'modelos': 'Honor 600, Honor 8 Lite', 'frase': ''}]},
              open(os.path.join(d, 'nuevos_modelos', 'modelos.json'), 'w', encoding='utf-8'))
    costo = lambda solo='testimonios,nuevos_modelos', extra='': json.loads(pedir('GET', f'/api/costo_extras?p=voces&solo={solo}{extra}')[1])
    c = costo()
    ok(len(c.get('gasta', [])) == 2 and c.get('letras') == len(texto) + 250,
       f'sin voces guardadas, el costo cuenta la narración del testimonio con texto y la frase de nuevos modelos: {c}')
    ok(costo('tarjetas,logos') == {'gasta': [], 'letras': 0}, 'sin testimonios ni nuevos modelos no hay voz que pagar')
    LANZADOS.clear()
    for paso, datos in (('extras', {'solo': ['testimonios']}), ('extras', {'solo': ['nuevos_modelos']}),
                        ('extras', {'solo': ['tarjetas', 'testimonios', 'nuevos_modelos']}), ('testimonios', {}), ('nuevos_modelos', {})):
        st, b = pedir('POST', f'/api/ejecutar?p=voces&paso={paso}', json.dumps(datos).encode())
        ok(st != 200 and 'SI' in b.decode('utf-8') and lanzado(0.3) is None,
           f'«{paso}» {datos} sin SI no debe arrancar (gastaría ElevenLabs): {st} {b[:200]!r}')
    st, b = pedir('POST', '/api/ejecutar?p=voces&paso=extras', json.dumps({'solo': ['testimonios', 'nuevos_modelos'], 'confirmo': 'SI'}).encode())
    r = lanzado()
    ok(r and 'testimonios' in r[0] and 'nuevos_modelos' in r[0], f'con SI, «Agregar extras» arranca: {st} {b[:200]!r} {r}')
    # la frase que escribió la app la vez anterior (nuevos_modelos.py la deja en trabajo_modelos/leido.json): se sabe su largo
    frase = 'Y ojo, que este método también sirve para los modelos más recientes, como el Honor 600 y el Honor 8 Lite.'
    os.makedirs(os.path.join(d, 'trabajo_modelos'))
    json.dump({'modelos': ['Honor 600', 'Honor 8 Lite'], 'frase': frase, 'escrita': 'app', 'idioma': 'es', 'vistos': None,
               'clip': f"m.mp4|{os.path.getsize(os.path.join(d, 'nuevos_modelos', 'm.mp4'))}"},
              open(os.path.join(d, 'trabajo_modelos', 'leido.json'), 'w', encoding='utf-8'))
    c = costo('nuevos_modelos')
    ok(c.get('letras') == len(frase), f'la frase de la vez anterior todavía sin voz cuesta su largo: {c}')
    # las voces ya hechas, tal como las guardan testimonios.py y nuevos_modelos.py (ElevenLabs simulado): no se pregunta nada
    viejo = urllib.request.urlopen
    try:
        urllib.request.urlopen, pedidos = falsa_eleven(b'mp3 falso')
        te.dur_mp3 = lambda f: 3.0
        pronunciacion.para_pedido = lambda *a, **k: {}  # el diccionario de pronunciación tampoco va a ElevenLabs
        os.environ['ELEVENLABS_API_KEY'] = 'sk-prueba'
        te.narrar(os.path.join(d, 'testimonios'), 't1', texto, '94zOad0g7T7K4oa7zhDq', 'eleven_v4', 0.5, 'es')
        urllib.request.urlopen, pedidos2 = falsa_eleven(json.dumps({'audio_base64': 'AAAA', 'alignment': {
            'characters': list('ok'), 'character_start_times_seconds': [0, 0.1], 'character_end_times_seconds': [0.1, 0.2]}}).encode())
        nm.voz(frase, os.path.join(d, 'trabajo_modelos'))
    finally:
        urllib.request.urlopen = viejo
        os.environ.pop('ELEVENLABS_API_KEY', None)
    ok(len(pedidos) == 1 and len(pedidos2) == 1, f'la prueba debía simular un pedido de voz de cada uno: {pedidos} {pedidos2}')
    c = costo()
    ok(c == {'gasta': [], 'letras': 0}, f'con las voces ya guardadas no se vuelve a pagar nada: {c}')
    st, b = pedir('POST', '/api/ejecutar?p=voces&paso=extras', json.dumps({'solo': ['testimonios', 'nuevos_modelos', 'tarjetas']}).encode())
    r = lanzado()
    ok(st == 200 and r and 'testimonios' in r[0], f'sin gasto, «Agregar extras» sigue funcionando igual (sin pedir SI): {st} {b[:200]!r} {r}')
    # cambias el texto del testimonio: su narración es nueva y vuelve a pedir SI; «▶ Ponerlas en el video» también lo ve
    json.dump({'TESTIMONIOS': [{'archivo': 't1.mp4', 'texto': texto + ' y feliz'}]},
              open(os.path.join(d, 'testimonios', 'testimonios.json'), 'w', encoding='utf-8'))
    ok(costo().get('letras') == len(texto + ' y feliz'), f'el texto cambiado se vuelve a narrar: {costo()}')
    json.dump({'solo': ['testimonios']}, open(os.path.join(d, 'vista_pendiente.json'), 'w'))
    ok(costo('etiquetas,senales', '&vista=1').get('letras') == len(texto + ' y feliz'),
       'la vista previa debe contar la narración de los extras que vuelven con las etiquetas')
    st, b = pedir('POST', '/api/ejecutar?p=voces&paso=extras', json.dumps({'solo': ['etiquetas', 'senales'], 'revisado': True, 'sin_ia': True}).encode())
    ok(st != 200 and lanzado(0.3) is None, f'«▶ Ponerlas en el video» sin SI no debe narrar el testimonio cambiado: {st} {b[:200]!r}')
    # DeepSeek: «extras testimonios --confirmo-creditos» ya tiene el sí del autor y lo manda como SI (antes la app lo frenaba)
    sys.path.insert(0, os.path.join(RAIZ, 'deepseek'))
    import video as ds  # noqa: E402
    ds.URL, ds.PROYECTOS = f'http://127.0.0.1:{PUERTO}', app.PROYECTOS
    viejo_argv, LANZADOS[:] = sys.argv, []
    try:
        for extra in (['nuevos_modelos'], []):
            sys.argv = ['video.py', 'extras', 'testimonios', *extra, '--nombre', 'voces', '--confirmo-creditos']
            try:
                with __import__('contextlib').redirect_stdout(io.StringIO()):
                    ds.main()
                fallo_ds = ''
            except SystemExit as e:
                fallo_ds = str(e)
            r = lanzado()
            ok(not fallo_ds and r and 'testimonios' in r[0] and r[1].get('confirmo') == 'SI',
               f'DeepSeek con --confirmo-creditos debe arrancar los extras con el SI del autor: {fallo_ds[:300]} {r}')
        sys.argv = ['video.py', 'extras', 'testimonios', '--nombre', 'voces']  # sin el permiso del autor no se manda nada
        try:
            ds.main()
            fallo_ds = ''
        except SystemExit as e:
            fallo_ds = str(e)
        ok('--confirmo-creditos' in fallo_ds and lanzado(0.3) is None, f'DeepSeek sin --confirmo-creditos no debe arrancar: {fallo_ds[:300]}')
    finally:
        sys.argv = viejo_argv

    # la página: «✨ Agregar extras» e «Insertar» preguntan SI antes de mandar el pedido, y sin gasto no preguntan nada
    html = open(os.path.join(RAIZ, 'app', 'index.html'), encoding='utf-8').read()
    fun = lambda n: (re.search(r'\n(async function ' + n + r'\(.*?\n\})', html, re.S) or [None, ''])[1]
    ok(fun('confirmarVocesExtras') and fun('agregarExtras') and fun('insertarExtras'), 'faltan las funciones de los extras en index.html')
    if shutil.which('node') and fun('confirmarVocesExtras'):
        js = r"""
const P = 'p', q = encodeURIComponent, salida = [];
let COSTO = null, SI = true, preguntas = 0, mandados = [];
async function api(url, op) {
  if (url.startsWith('/api/costo_extras')) { if (COSTO === 'error') throw new Error('sin conexión'); return COSTO; }
  if (url.startsWith('/api/estado')) return {archivos: {'4_musica.mp4': {}}, capas_hechas: [], pasos: []};
  if (url.startsWith('/api/ejecutar')) mandados.push(JSON.parse(op.body));
  return {};
}
function pedirSi(t) { preguntas++; return SI; }
const caja = {value: 'alta', textContent: '', className: ''}, $ = () => caja;
const document = {querySelectorAll: () => [{dataset: {extra: 'tarjetas'}}, {dataset: {extra: 'testimonios'}}]};
const dlgExtras = {close() {}}, TESTI = {TESTIMONIOS: [{}]}, MODS = {MODELOS: []}, TARJ = {}, TRAILER_DONDE = 'inicio';
function soltarVideo() {} function refrescar() {} function confirm() { return true; } function alert() {}
""" + fun('confirmarVocesExtras') + '\n' + fun('agregarExtras') + '\n' + fun('insertarExtras') + r"""
(async () => {
  for (const f of [agregarExtras, insertarExtras]) {
    for (const [costo, si] of [[{gasta: ['la narración de 1 testimonio (unos 40 créditos)'], letras: 40}, false],
                               [{gasta: ['la narración de 1 testimonio (unos 40 créditos)'], letras: 40}, true],
                               [{gasta: [], letras: 0}, true], ['error', false]]) {
      COSTO = costo; SI = si; preguntas = 0; mandados = [];
      await f();
      salida.push({f: f.name, preguntas, mandados});
    }
  }
  console.log(JSON.stringify(salida));
})();
"""
        f = os.path.join(tmp, 'extras.js')
        open(f, 'w', encoding='utf-8').write(js)
        r = subprocess.run(['node', f], capture_output=True, text=True, encoding='utf-8')
        try:
            res = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            res = None
        ok(res is not None, f'no pude probar la página con node: {r.stdout[-300:]} {r.stderr[-600:]}')
        if res:
            for nombre in ('agregarExtras', 'insertarExtras'):
                no_si, con_si, gratis, error = [x for x in res if x['f'] == nombre]
                ok(no_si['preguntas'] == 1 and not no_si['mandados'], f'{nombre}: sin SI no debe mandar el pedido: {no_si}')
                ok(con_si['preguntas'] == 1 and len(con_si['mandados']) == 1 and con_si['mandados'][0].get('confirmo') == 'SI',
                   f'{nombre}: con SI manda el pedido con el SI: {con_si}')
                ok(gratis['preguntas'] == 0 and len(gratis['mandados']) == 1 and not gratis['mandados'][0].get('confirmo'),
                   f'{nombre}: sin gasto no pregunta nada y funciona igual: {gratis}')
                ok(error['preguntas'] == 1 and not error['mandados'], f'{nombre}: si no puede revisar el costo, pregunta: {error}')

    # P2b) la frase de voz del tráiler (trailer.py la pide a ElevenLabs si cambió o nunca se hizo): tampoco sin SI
    d = os.path.join(app.PROYECTOS, 'travoz')
    crear(d, ['original.mp4', '3_voz.mp4', '4_musica.mp4'])
    frase_t = 'Así se quita la cuenta de Google en dos minutos'
    json.dump({'voz': frase_t, 'clips': []}, open(os.path.join(d, 'trailer.json'), 'w', encoding='utf-8'))
    costo_t = lambda solo='trailer': json.loads(pedir('GET', f'/api/costo_extras?p=travoz&solo={solo}')[1])
    ok(costo_t().get('letras') == len(frase_t) and len(costo_t().get('gasta', [])) == 1, f'la frase del tráiler sin hacer cuesta su largo: {costo_t()}')
    LANZADOS.clear()
    for paso, datos in (('trailer', {}), ('trailer_solo', {}), ('extras', {'solo': ['trailer']}), ('extras', {'solo': ['tarjetas', 'trailer']})):
        st, b = pedir('POST', f'/api/ejecutar?p=travoz&paso={paso}', json.dumps(datos).encode())
        ok(st != 200 and 'tráiler' in b.decode('utf-8') and lanzado(0.3) is None,
           f'«{paso}» {datos} sin SI no debe arrancar (la frase del tráiler gasta ElevenLabs): {st} {b[:200]!r}')
    st, b = pedir('POST', '/api/ejecutar?p=travoz&paso=extras', json.dumps({'solo': ['trailer'], 'confirmo': 'SI'}).encode())
    r = lanzado()
    ok(st == 200 and r and 'trailer' in r[0], f'con SI el tráiler arranca: {st} {b[:200]!r} {r}')
    # ya hecha con la misma frase (como la deja trailer.py junto a trailer.mp4): no se vuelve a pagar ni se pregunta
    open(os.path.join(d, 'trailer.voz.mp3'), 'wb').write(b'mp3')
    open(os.path.join(d, 'trailer.voz.mp3.txt'), 'w', encoding='utf-8').write(frase_t)
    ok(costo_t() == {'gasta': [], 'letras': 0}, f'la frase ya hecha no se vuelve a pagar: {costo_t()}')
    st, b = pedir('POST', '/api/ejecutar?p=travoz&paso=trailer', b'{}')
    r = lanzado()
    ok(st == 200 and r and r[0] == ['trailer'], f'sin gasto, el tráiler arranca sin pedir SI: {st} {b[:200]!r} {r}')
    # la cambias en «🎬 Tráiler» y guardas sin armarlo: «Insertar» y la tarjeta «Tráiler» vuelven a pedir SI
    json.dump({'voz': frase_t + ' y gratis', 'clips': []}, open(os.path.join(d, 'trailer.json'), 'w', encoding='utf-8'))
    st, b = pedir('POST', '/api/ejecutar?p=travoz&paso=trailer', b'{}')
    ok(st != 200 and lanzado(0.3) is None, f'la frase cambiada se vuelve a pagar: pide SI: {st} {b[:200]!r}')
    # en otro idioma la firma lleva la voz y el idioma (como trailer.py): la frase en español guardada no sirve
    json.dump({'voz': frase_t, 'clips': []}, open(os.path.join(d, 'trailer.json'), 'w', encoding='utf-8'))
    json.dump({'idioma': 'en'}, open(os.path.join(d, 'idioma_video.json'), 'w', encoding='utf-8'))
    ok(costo_t().get('letras') == len(frase_t), f'en inglés la frase en español no sirve: {costo_t()}')
    open(os.path.join(d, 'trailer.voz.mp3.txt'), 'w', encoding='utf-8').write(f"{frase_t}|{app.VOCES_DEFECTO['en']}|en")
    ok(costo_t() == {'gasta': [], 'letras': 0}, f'en inglés, con su voz ya hecha, no se paga: {costo_t()}')
    os.remove(os.path.join(d, 'idioma_video.json'))
    # sin plan propio y con IA, «Agregar extras» arma el tráiler con la IA y su frase: también cuenta
    os.remove(os.path.join(d, 'trailer.json'))
    json.dump({'modelo': 'm', 'url': 'http://127.0.0.1:9'}, open(app.AJUSTES, 'w'))
    ok(costo_t().get('letras') == 120, f'la frase que escribirá la IA cuenta (como mucho): {costo_t()}')
    ok(app.gasto_sin_confirmar(d, 'todo', ['trailer_ia', 'trailer'], {}), 'el tráiler que arma la IA con su frase debe pedir SI')
    json.dump({}, open(app.AJUSTES, 'w'))
    # «🎬 Tráiler» (trailer.html): «▶ Armar y unir al video» y «🎬 Ver solo el tráiler» piden SI antes de mandar el pedido
    html_t = open(os.path.join(RAIZ, 'app', 'trailer.html'), encoding='utf-8').read()
    fun_t = lambda n: (re.search(r'\n(async function ' + n + r'\(.*?\n\})', html_t, re.S) or [None, ''])[1]
    ok(fun_t('siVozTrailer') and fun_t('armar') and fun_t('armarSolo'), 'faltan las funciones del tráiler en trailer.html')
    if shutil.which('node') and fun_t('siVozTrailer'):
        js = r"""
const P = 'p', q = encodeURIComponent, salida = [];
let COSTO = null, RESP = 'SI', preguntas = 0, mandados = [];
const T = {voz: 'frase', clips: [{}]}, DONDE = 'inicio', sucio = false;
async function api(url, op) {
  if (url.startsWith('/api/costo_extras')) { if (COSTO === 'error') throw new Error('sin conexión'); return COSTO; }
  if (url.startsWith('/api/ejecutar')) mandados.push({paso: url.split('paso=')[1], ...JSON.parse(op.body)});
  return {};
}
function prompt() { preguntas++; return RESP; }
function confirm() { return true; } function alert() {} async function esperar() {} async function cargar() {} async function guardar() { return true; }
const caja = {className: '', textContent: ''}, $ = () => caja;
""" + fun_t('siVozTrailer') + '\n' + fun_t('armar') + '\n' + fun_t('armarSolo') + r"""
(async () => {
  for (const f of [armar, armarSolo]) {
    for (const [costo, resp] of [[{gasta: ['la frase de voz del tráiler (unos 40 créditos)'], letras: 40}, null],
                                 [{gasta: ['la frase de voz del tráiler (unos 40 créditos)'], letras: 40}, 'si'],
                                 [{gasta: [], letras: 0}, null], ['error', 'no']]) {
      COSTO = costo; RESP = resp; preguntas = 0; mandados = [];
      await f();
      salida.push({f: f.name, preguntas, mandados});
    }
  }
  console.log(JSON.stringify(salida));
})();
"""
        f = os.path.join(tmp, 'trailer.js')
        open(f, 'w', encoding='utf-8').write(js)
        r = subprocess.run(['node', f], capture_output=True, text=True, encoding='utf-8')
        try:
            res = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            res = None
        ok(res is not None, f'no pude probar trailer.html con node: {r.stdout[-300:]} {r.stderr[-600:]}')
        for nombre in ('armar', 'armarSolo') if res else ():
            cancela, con_si, gratis, error = [x for x in res if x['f'] == nombre]
            ok(cancela['preguntas'] == 1 and not cancela['mandados'], f'{nombre}: sin SI no debe mandar el pedido: {cancela}')
            ok(con_si['preguntas'] == 1 and len(con_si['mandados']) == 1 and con_si['mandados'][0].get('confirmo') == 'SI',
               f'{nombre}: con SI manda el pedido con el SI: {con_si}')
            ok(gratis['preguntas'] == 0 and len(gratis['mandados']) == 1 and not gratis['mandados'][0].get('confirmo'),
               f'{nombre}: sin gasto no pregunta nada: {gratis}')
            ok(error['preguntas'] == 1 and not error['mandados'], f'{nombre}: si no puede revisar el costo, pregunta: {error}')

    # P3) guardar una lista vieja (otra pestaña o el celular) no borra los archivos que no están en ella
    d = os.path.join(app.PROYECTOS, 'cruce')
    t = os.path.join(d, 'testimonios')
    crear(d, ['original.mp4', 'guion.json'])
    os.makedirs(t)
    for f in ('t1.mp4', 't2.mp4', 'narr_t2.mp3', 'narr_t2.json'):
        open(os.path.join(t, f), 'wb').write(f'video {f}'.encode())
    hace_rato = lambda *fs: [os.utime(os.path.join(t, f), (time.time() - 3600,) * 2) for f in fs if os.path.exists(os.path.join(t, f))]
    listar = lambda c: sorted(os.listdir(c)) if os.path.isdir(c) else []
    hace_rato('t1.mp4')  # t1 lo subiste hace rato; t2 lo acaba de subir el celular
    guardar = lambda lista, g='testimonios', ap='TESTIMONIOS': pedir(
        'POST', f'/api/pistas?p=cruce&g={g}', json.dumps({ap: [{'archivo': a} for a in lista]}).encode())
    st, b = guardar(['t1.mp4'])  # el PC guarda la lista vieja, sin t2
    ok(st == 200 and all(os.path.exists(os.path.join(t, f)) for f in ('t1.mp4', 't2.mp4', 'narr_t2.mp3')),
       f'un testimonio recién subido (otra pestaña o el celular) no se toca al guardar una lista vieja: {st} {sorted(os.listdir(t))}')
    hace_rato('t2.mp4', 'narr_t2.mp3', 'narr_t2.json')
    st, b = guardar(['t1.mp4'])  # ya pasó un rato: lo quitado sale de la lista, pero a la papelera, sin borrarse
    pap = os.path.join(t, PAPELERA)
    ok(st == 200 and not os.path.exists(os.path.join(t, 't2.mp4')) and os.path.exists(os.path.join(t, 't1.mp4')),
       f'lo que no está en la lista sale de la carpeta: {st} {b[:200]!r} {sorted(os.listdir(t))}')
    ok(os.path.isfile(os.path.join(pap, 't2.mp4')) and open(os.path.join(pap, 't2.mp4'), 'rb').read() == b'video t2.mp4'
       and os.path.exists(os.path.join(pap, 'narr_t2.mp3')), f'lo quitado debe quedar entero en _papelera/: {listar(t)}')
    open(os.path.join(t, 't2.mp4'), 'wb').write(b'otro t2')  # otro con el mismo nombre: no pisa el de la papelera
    hace_rato('t2.mp4')
    st, b = guardar(['t1.mp4'])
    ok(st == 200 and listar(pap) == ['narr_t2.json', 'narr_t2.mp3', 't2.mp4', 't2_2.mp4']
       and open(os.path.join(pap, 't2_2.mp4'), 'rb').read() == b'otro t2', f'la papelera no pisa nada: {st} {b[:200]!r} {listar(pap)}')
    ok(st == 200 and os.path.isdir(pap), f'guardar otra vez con la papelera ya hecha funciona y no la toca: {st} {b[:200]!r}')
    # la papelera no es un testimonio: ni en la lista, ni en «🎛 Audio e imagen», ni en el montaje (testimonios.py usa la lista)
    lista = json.loads(pedir('GET', '/api/pistas?p=cruce&g=testimonios')[1])
    ok(lista == {'TESTIMONIOS': [{'archivo': 't1.mp4'}]}, f'la lista de testimonios solo trae los tuyos: {lista}')
    ok(mejoras.estado(d)['testimonios'] == ['t1.mp4'], f"«🎛 Audio e imagen» lista la papelera: {mejoras.estado(d)['testimonios']}")
    # tarjetas: lo mismo, y la papelera no se copia en «💾 Guardar proyecto» ni viaja en el paquete de la nube
    tj = os.path.join(d, 'tarjetas')
    os.makedirs(tj)
    for f in ('c1.png', 'c2.png'):
        open(os.path.join(tj, f), 'wb').write(b'img')
        os.utime(os.path.join(tj, f), (time.time() - 3600,) * 2)
    st, b = guardar(['c1.png'], 'tarjetas', 'COMENTARIOS')
    ok(st == 200 and os.path.exists(os.path.join(tj, PAPELERA, 'c2.png')), f'la tarjeta quitada va a la papelera: {listar(tj)}')
    os.makedirs(os.path.join(tj, PAPELERA), exist_ok=True)  # (por si la de arriba falló: estas pruebas miran solo la carpeta)
    open(os.path.join(tj, PAPELERA, 'vieja.png'), 'wb').write(b'img')
    g = app.guardar_proyecto(d)
    copia = os.path.join(d, app.GUARDADOS, g)
    ok(os.path.exists(os.path.join(copia, 'tarjetas', 'c1.png')) and not os.path.exists(os.path.join(copia, 'tarjetas', PAPELERA)),
       'el guardado del proyecto no debe copiar la papelera')
    aj = os.path.join(tmp, 'ajustes_nube.json')
    json.dump({}, open(aj, 'w'))
    r = subprocess.run([sys.executable, os.path.join(RAIZ, 'nube', 'preparar.py'), '--proyecto', d, '--ajustes', aj, '--estilos', tmp],
                       capture_output=True, text=True)
    try:
        rutas = [x['ruta'] for x in json.load(open(os.path.join(d, 'para_claude', 'parametros.json'), encoding='utf-8'))['archivos']]
    except (OSError, ValueError, KeyError):
        rutas = None
    ok(rutas and 'testimonios/t1.mp4' in rutas and not any(PAPELERA in x for x in rutas),
       f'el paquete de la nube no lleva la papelera: {rutas} {r.stderr[-300:]}')
    # «🗑 Borrar todo» la trata como tus demás carpetas: se queda
    pedir('POST', '/api/empezar_de_nuevo?p=cruce')
    ok(os.path.exists(os.path.join(pap, 't2.mp4')) and os.path.exists(os.path.join(t, 't1.mp4'))
       and not os.path.exists(os.path.join(d, 'guion.json')), f'«Borrar todo» debe conservar la papelera: {sorted(os.listdir(d))}')
finally:
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

if fallos:
    print('FALLÓ:\n- ' + '\n- '.join(fallos))
    sys.exit(1)
print('OK: los 3 arreglos pendientes funcionan.')
