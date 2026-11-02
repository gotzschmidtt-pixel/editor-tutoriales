"""Prueba rápida de los 3 arreglos pendientes de la revisión. Sin internet y sin gastar nada: los pasos largos van simulados,
y tus ajustes y proyectos no se tocan (todo va a una carpeta temporal).
- «✨ Agregar extras» copia el FINAL con tus arreglos a mano antes de borrarlo, y no suma otra copia en cada vuelta;
- la narración de los testimonios y la frase de «Nuevos modelos» no gastan ElevenLabs sin SI (solo se pregunta si falta
  su voz guardada; la página pregunta antes de mandar el pedido);
- guardar una lista vieja de testimonios o tarjetas (otra pestaña, el celular) no borra nada: lo quitado va a _papelera/
  y lo subido hace menos de 10 minutos no se toca.
Y lo que salió en la revisión 3: el FINAL abierto en otro programa se copia una sola vez por vuelta; los botones mandan SI
solo si lo escribiste (la «🌙 Cola de noche» y «↻ Reintentar» valen solo para lo aprobado); y piden SI escrito «▶ Ponerlas
en el video», el tráiler de cada IA, transcribir o alinear con ElevenLabs, limpiar la voz, los sonidos y la voz del Short.
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


def funcion(pagina, nombre):
    """El código de una función (async o no) de una página de app/."""
    html = open(os.path.join(RAIZ, 'app', pagina), encoding='utf-8').read()
    m = re.search(r'\n((?:async )?function ' + nombre + r'\(.*?\n\})', html, re.S)
    return m.group(1) if m else ''


def nodo(nombre, js):
    """Corre un trozo de la página con node (sin navegador): devuelve lo que imprime en su última línea, como JSON."""
    f = os.path.join(tmp, nombre + '.js')
    open(f, 'w', encoding='utf-8').write(js)
    r = subprocess.run(['node', f], capture_output=True, text=True, encoding='utf-8')
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        fallos.append(f'no pude probar {nombre} con node: {r.stdout[-300:]} {r.stderr[-600:]}')
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
    # el FINAL con arreglos a mano está abierto en otro programa (VLC, el celular) y Windows no deja borrarlo: «✨ Agregar
    # extras» y «▶ Hacer todo» lo copian una vez, y el paso del final ya no lo copia otra vez en la misma vuelta
    viejo_borrar, viejos_pasos = app.borrar_seguro, app.PASOS
    app.borrar_seguro = lambda f, *a, **k: False if os.path.basename(f) == 'FINAL.mp4' else viejo_borrar(f, *a, **k)
    app.PASOS = [dict(x, necesita=[]) for x in app.PASOS]  # los pasos simulados no dejan sus videos: que ninguno se salte
    try:
        for k, (pasos, op) in enumerate(((['testimonios', 'final_sin_trailer'], {'_limpiar_extras': True}),
                                         (['montaje', 'mezclar', 'musica', 'final_sin_trailer'], {}))):
            d = os.path.join(app.PROYECTOS, f'abierto{k}')
            crear(d, ['original.mp4', '3_voz.mp4', '4_musica.mp4'])
            open(os.path.join(d, 'FINAL.mp4'), 'wb').write(b'giro y fotos a mano, abierto en VLC')
            correr(f'abierto{k}', pasos, op)  # ffmpeg tampoco puede escribir el FINAL abierto: el paso del final no lo cambia
            hechas = [f for f in os.listdir(d) if f.startswith('FINAL_antes_rehacer_')]
            ok(len(hechas) == 1, f'{pasos}: el FINAL abierto en otro programa se copia una sola vez por vuelta: {hechas}')
    finally:
        app.borrar_seguro, app.PASOS = viejo_borrar, viejos_pasos

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

    # «↻ Reintentar» vuelve a usar las opciones de la vuelta que falló: si ahora hay voz que pagar (cambiaste el texto del
    # testimonio después de la falla), sin SI no arranca
    LANZADOS.clear()
    app.RESULTADO['voces'] = {'repetir': {'pasos': ['testimonios', 'final_sin_trailer'], 'opciones': {'solo': ['testimonios']}}}
    st, b = pedir('POST', '/api/reintentar?p=voces')
    ok(st != 200 and json.loads(b).get('gasta') and lanzado(0.3) is None, f'«Reintentar» sin SI no debe narrar el testimonio cambiado: {st} {b[:200]!r}')
    st, b = pedir('POST', '/api/reintentar?p=voces', json.dumps({'confirmo': 'SI'}).encode())
    r = lanzado()
    ok(st == 200 and r and r[0] == ['testimonios', 'final_sin_trailer'] and r[1].get('confirmo') == 'SI' and r[1].get('_reanudar'),
       f'«Reintentar» con SI arranca desde el paso que falló: {st} {b[:200]!r} {r}')
    ok(r and r[1].get('_aprobado') == [f'la narración de 1 testimonio (unos {len(texto + " y feliz")} créditos)'],
       f'el SI escrito al reintentar queda anotado con lo que se pagaba entonces: {r}')
    # la vuelta que falló ya traía tu SI para esa misma narración: sigue sin preguntar
    gasta_ahora = app.gastos_sin_si(d, 'testimonios', ['testimonios', 'final_sin_trailer'], {'solo': ['testimonios']})
    app.RESULTADO['voces']['repetir']['opciones'].update(confirmo='SI', _aprobado=list(gasta_ahora))
    st, b = pedir('POST', '/api/reintentar?p=voces')
    ok(st == 200 and lanzado(), f'«Reintentar» de una vuelta que ya traía tu SI no vuelve a preguntar: {st} {b[:200]!r}')
    # pero tu SI era para otra cosa (otro texto, o la vuelta arrancó con un SI que nadie escribió porque no había nada que
    # pagar): lo que ahora cambió vuelve a pedir SI
    for aprobado in ([], ['la narración de 1 testimonio (unos 12 créditos)'], None):
        app.RESULTADO['voces']['repetir']['opciones'].update(confirmo='SI', _aprobado=aprobado)
        st, b = pedir('POST', '/api/reintentar?p=voces')
        ok(st != 200 and json.loads(b).get('gasta') == gasta_ahora and lanzado(0.3) is None,
           f'«Reintentar» con un SI aprobado para otra cosa ({aprobado}) debe volver a preguntar: {st} {b[:200]!r}')
    app.RESULTADO.pop('voces', None)
    # «▶ Hacer todo», «Agregar extras»… con tu SI: queda anotado qué se pagaba al escribirlo (para «↻ Reintentar»)
    st, b = pedir('POST', '/api/ejecutar?p=voces&paso=extras', json.dumps({'solo': ['testimonios'], 'confirmo': 'SI'}).encode())
    r = lanzado()
    ok(st == 200 and r and r[1].get('_aprobado') == gasta_ahora, f'el SI escrito queda anotado con lo que se pagaba: {st} {b[:200]!r} {r}')
    # y si el texto cambia mientras el trabajo ya corre (arrancó sin SI porque no había nada que pagar), el paso se frena en
    # vez de pedirle la voz a ElevenLabs: la app marca esas vueltas con SIN_SI
    vistos = {}
    viejos = (app.comandos, app.asegurar_librerias, app.asegurar_node)
    app.comandos = lambda paso, d_, op: [[sys.executable, '-c', 'import os; open("sin_si.txt", "w").write(os.environ.get("SIN_SI", ""))']]
    app.asegurar_librerias, app.asegurar_node = (lambda *a: None), (lambda *a: None)
    try:
        for datos in ({}, {'confirmo': 'SI'}):
            app.TRABAJO.update(proyecto='voces')
            app.correr('voces', ['final_sin_trailer'], dict(datos))
            app.TRABAJO.update(proyecto=None)
            vistos[str(datos)] = open(os.path.join(d, 'sin_si.txt')).read()
    finally:
        app.comandos, app.asegurar_librerias, app.asegurar_node = viejos
    ok(vistos == {'{}': '1', "{'confirmo': 'SI'}": ''}, f'la vuelta sin SI debe ir marcada (y la que trae SI, no): {vistos}')
    viejo = urllib.request.urlopen
    try:
        urllib.request.urlopen, pedidos = falsa_eleven(b'mp3 falso')
        os.environ['SIN_SI'] = '1'
        os.environ['ELEVENLABS_API_KEY'] = 'sk-prueba'
        for nombre, hacer in (('testimonios', lambda: te.narrar(os.path.join(d, 'testimonios'), 't1', 'un texto que cambió recién',
                                                               '94zOad0g7T7K4oa7zhDq', 'eleven_v4', 0.5, 'es')),
                              ('nuevos modelos', lambda: nm.voz('una frase que cambió recién', os.path.join(d, 'trabajo_modelos')))):
            try:
                hacer()
                frenado = ''
            except SystemExit as e:
                frenado = str(e)
            except Exception as e:  # (sin el arreglo, la respuesta simulada de ElevenLabs no es un audio de verdad)
                frenado = f'{type(e).__name__}: {e}'
            ok('SI' in frenado and not pedidos, f'{nombre}: en una vuelta sin SI, la voz nueva no se pide a ElevenLabs: {frenado!r} {pedidos}')
        ok(te.narrar(os.path.join(d, 'testimonios'), 't1', texto, '94zOad0g7T7K4oa7zhDq', 'eleven_v4', 0.5, 'es')[0].endswith('narr_t1.mp3')
           and nm.voz(frase, os.path.join(d, 'trabajo_modelos'))[0].endswith('.mp3') and not pedidos,
           'la voz ya guardada se sigue usando en una vuelta sin SI')
    finally:
        urllib.request.urlopen = viejo
        os.environ.pop('SIN_SI', None)
        os.environ.pop('ELEVENLABS_API_KEY', None)
    trailer_py = open(os.path.join(RAIZ, 'trailer', 'trailer.py'), encoding='utf-8').read()
    ok(re.search(r"if previo != firma:\s*\n\s*if os\.environ\.get\('SIN_SI'\) == '1':", trailer_py),
       'trailer.py debe frenarse antes de pedir una frase nueva en una vuelta sin SI')

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
    # «↻ Reintentar» en la página: si el servidor dice que ahora hay voz que pagar, pide SI y recién ahí reintenta con SI
    ok(fun('reintentar'), 'falta reintentar() en index.html')
    if shutil.which('node') and fun('reintentar'):
        js = r"""
const P = 'p', q = encodeURIComponent, salida = [];
let SI = true, preguntas = 0, mandados = [], GASTA = true;
async function fetch(url, op) {
  const b = JSON.parse(op.body); mandados.push(b);
  const ok = !GASTA || b.confirmo === 'SI';
  return {ok, json: async () => ok ? {ok: true} : {error: 'Reintentar gasta ElevenLabs', gasta: ['la narración de 1 testimonio (unos 69 créditos)']}};
}
function pedirSi(t) { preguntas++; return SI; }
const caja = {textContent: ''}, $ = () => caja, dlgDiag = {close() { salida.push('cerrado'); }};
function refrescar() {}
""" + fun('reintentar') + r"""
(async () => {
  const res = [];
  for (const [gasta, si] of [[true, false], [true, true], [false, true]]) {
    GASTA = gasta; SI = si; preguntas = 0; mandados = []; salida.length = 0;
    await reintentar();
    res.push({preguntas, mandados: mandados.map(m => m.confirmo), cerrado: salida.length});
  }
  console.log(JSON.stringify(res));
})();
"""
        f = os.path.join(tmp, 'reintentar.js')
        open(f, 'w', encoding='utf-8').write(js)
        r = subprocess.run(['node', f], capture_output=True, text=True, encoding='utf-8')
        try:
            res = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            res = None
        ok(res == [{'preguntas': 1, 'mandados': [''], 'cerrado': 0}, {'preguntas': 1, 'mandados': ['', 'SI'], 'cerrado': 1},
                   {'preguntas': 0, 'mandados': [''], 'cerrado': 1}],
           f'«↻ Reintentar» debe pedir SI solo si hay algo que pagar: {res} {r.stderr[-600:]}')

    # P2c) «✨ Agregar extras» con etiquetas que la IA va a proponer: esa vuelta se para en la propuesta y no paga voces. No se
    # pregunta SI por nada, y los testimonios elegidos quedan anotados para «▶ Ponerlas en el video», que sí pregunta
    d = os.path.join(app.PROYECTOS, 'propone')
    crear(d, ['original.mp4', '3_voz.mp4', '4_musica.mp4', 'guion.json', 'testimonios/t1.mp4'])
    json.dump({'TESTIMONIOS': [{'archivo': 't1.mp4', 'texto': texto}]}, open(os.path.join(d, 'testimonios', 'testimonios.json'), 'w', encoding='utf-8'))
    json.dump({'modelo': 'm', 'url': 'http://127.0.0.1:9'}, open(app.AJUSTES, 'w'))  # con IA y sin etiquetas.json
    costo_p = lambda solo, extra='': json.loads(pedir('GET', f'/api/costo_extras?p=propone&solo={solo}{extra}')[1])
    ok(costo_p('etiquetas,testimonios') == {'gasta': [], 'letras': 0},
       f'la vuelta que se para en la propuesta de la IA no gasta voces: no se pregunta SI: {costo_p("etiquetas,testimonios")}')
    for extra in ('', '&revisado=1', '&sin_ia=1'):
        solo = 'testimonios' if not extra else 'etiquetas,testimonios'
        ok(costo_p(solo, extra).get('letras') == len(texto), f'{solo}{extra}: sí se pone el testimonio: cuenta su narración: {costo_p(solo, extra)}')
    LANZADOS.clear()
    st, b = pedir('POST', '/api/ejecutar?p=propone&paso=extras', json.dumps({'solo': ['etiquetas', 'testimonios']}).encode())
    r = lanzado()
    ok(st == 200 and r and 'testimonios' not in r[0] and 'etiquetas_ia' in r[0], f'la IA propone las etiquetas y se para: {st} {b[:200]!r} {r}')
    try:
        pend = json.load(open(os.path.join(d, 'vista_pendiente.json'), encoding='utf-8'))
    except (OSError, ValueError):
        pend = {}
    ok(pend.get('solo') == ['testimonios'], f'el testimonio elegido debe quedar anotado para ponerlo después: {pend}')
    ok(costo_p('etiquetas,senales', '&vista=1').get('letras') == len(texto), '«▶ Ponerlas en el video» cuenta la narración del testimonio')
    ponerlas = lambda si='': pedir('POST', '/api/ejecutar?p=propone&paso=extras', json.dumps(
        {'solo': ['etiquetas', 'senales'], 'revisado': True, 'sin_ia': True, 'confirmo': si}).encode())
    st, b = ponerlas()
    ok(st != 200 and lanzado(0.3) is None, f'«▶ Ponerlas en el video» sin SI no narra el testimonio: {st} {b[:200]!r}')
    st, b = ponerlas('SI')  # el segundo intento, con SI: el testimonio sigue en la lista de lo que vuelve
    r = lanzado()
    ok(st == 200 and r and 'testimonios' in r[0], f'«▶ Ponerlas en el video» con SI pone el testimonio elegido: {st} {b[:200]!r} {r}')
    ok(not os.path.exists(os.path.join(d, 'vista_pendiente.json')), 'al arrancar, la vista previa deja de estar pendiente')
    json.dump({}, open(app.AJUSTES, 'w'))
    # la página «👀 Vista previa»: si hay voz que pagar no dice antes «No gasta créditos»; solo pide el SI escrito
    ok(funcion('vista.html', 'poner'), 'falta poner() en vista.html')
    if shutil.which('node') and funcion('vista.html', 'poner'):
        res = nodo('vista', r"""
const P = 'p', q = encodeURIComponent;
let COSTO = null, RESP = 'SI', avisos = [], mandados = [];
async function api(url, op) {
  if (url.startsWith('/api/costo_extras')) { if (COSTO === 'error') throw new Error('sin conexión'); return COSTO; }
  if (url.startsWith('/api/ejecutar')) mandados.push(JSON.parse(op.body));
  if (url.startsWith('/api/estado')) return {trabajo: {}};
  return {};
}
function confirm(t) { avisos.push(['confirm', t]); return true; } function prompt(t) { avisos.push(['prompt', t]); return RESP; }
function alert() {} function msg() {} const caja = {disabled: false}, $ = () => caja;
globalThis.setTimeout = f => f();
""" + funcion('vista.html', 'poner') + r"""
(async () => {
  const res = [];
  for (const [costo, resp] of [[{gasta: ['la narración de 1 testimonio (unos 20 créditos)'], letras: 20}, 'SI'],
                               [{gasta: ['la narración de 1 testimonio (unos 20 créditos)'], letras: 20}, null],
                               [{gasta: [], letras: 0}, null], ['error', 'si']]) {
    COSTO = costo; RESP = resp; avisos = []; mandados = [];
    await poner();
    res.push({avisos: avisos.map(([t, x]) => t + (x.includes('No gasta') ? ':no gasta' : '')), confirmo: mandados.map(m => m.confirmo)});
  }
  console.log(JSON.stringify(res));
})();
""")
        ok(res == [{'avisos': ['prompt'], 'confirmo': ['SI']}, {'avisos': ['prompt'], 'confirmo': []},
                   {'avisos': ['confirm:no gasta'], 'confirmo': ['']}, {'avisos': ['prompt'], 'confirmo': ['SI']}],
           f'«▶ Ponerlas en el video»: con gasto, solo el SI (sin «No gasta créditos» antes); sin gasto, un Aceptar: {res}')
    ok('sin gastar créditos' not in open(os.path.join(RAIZ, 'app', 'vista.html'), encoding='utf-8').read(),
       '«▶ Ponerlas en el video» no debe decir «sin gastar créditos» si puede gastar la voz de los extras que vuelven')

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
    # «▶ Ver con voz» y «💾 Guardar y rehacer» del tráiler de cada IA: su frase (trailer_<ia>.json) tampoco se paga con un
    # solo Aceptar. El servidor dice si falta pagarla (/api/costo_paso) y la página pide SI solo entonces
    frase_ia = 'La frase nueva que propuso GPT para su tráiler'
    json.dump({'voz': frase_ia, 'clips': []}, open(os.path.join(d, 'trailer_gpt.json'), 'w', encoding='utf-8'))
    costo_v = lambda: json.loads(pedir('GET', '/api/costo_paso?p=travoz&paso=trailer_version&v=gpt')[1])
    ok(costo_v() == {'gasta': [f'la frase de voz del tráiler (unos {len(frase_ia)} créditos)']}, f'la frase de la IA sin hacer cuesta su largo: {costo_v()}')
    st, b = pedir('POST', '/api/ejecutar?p=travoz&paso=trailer_version', json.dumps({'v': 'gpt', 'sin_voz': False}).encode())
    ok(st != 200 and lanzado(0.3) is None, f'«▶ Ver con voz» sin SI no paga la frase de la IA: {st} {b[:200]!r}')
    open(os.path.join(d, 'trailer_gpt.voz.mp3'), 'wb').write(b'mp3')  # como la deja trailer.py junto a trailer_gpt.mp4
    open(os.path.join(d, 'trailer_gpt.voz.mp3.txt'), 'w', encoding='utf-8').write(frase_ia)
    ok(costo_v() == {'gasta': []}, f'la frase de la IA ya hecha no se vuelve a pagar: {costo_v()}')
    ok(funcion('trailer.html', 'verTrailerIA') and funcion('trailer.html', 'siVozTrailer'), 'falta verTrailerIA() en trailer.html')
    if shutil.which('node') and funcion('trailer.html', 'verTrailerIA'):
        res = nodo('trailer_ia', r"""
const P = 'p', q = encodeURIComponent, TEXTOS = {gpt: {voz: 'frase'}};
let COSTO = null, RESP = 'SI', avisos = [], mandados = [], costos = [];
async function api(url, op) {
  if (url.startsWith('/api/costo_')) { costos.push(url); if (COSTO === 'error') throw new Error('sin conexión'); return COSTO; }
  if (url.startsWith('/api/ejecutar')) mandados.push({paso: url.split('paso=')[1], ...JSON.parse(op.body)});
  return {};
}
function confirm(t) { avisos.push('confirm'); return true; } function prompt(t) { avisos.push('prompt'); return RESP; }
function alert() {} async function esperar() {} async function cargar() {}
const caja = {className: '', textContent: ''}, $ = () => caja;
""" + funcion('trailer.html', 'siVozTrailer') + '\n' + funcion('trailer.html', 'verTrailerIA') + r"""
(async () => {
  const res = [];
  for (const [costo, resp, sinVoz] of [[{gasta: ['la frase de voz del tráiler (unos 46 créditos)']}, 'SI', false],
                                       [{gasta: ['la frase de voz del tráiler (unos 46 créditos)']}, null, false],
                                       [{gasta: []}, null, false], ['error', 'si', false], ['error', null, true]]) {
    COSTO = costo; RESP = resp; avisos = []; mandados = []; costos = [];
    await verTrailerIA('gpt', sinVoz);
    res.push({avisos, mandados: mandados.map(m => [m.paso, m.v, m.sin_voz, m.confirmo]), costo: costos.map(u => u.includes('paso=trailer_version&v=gpt'))});
  }
  console.log(JSON.stringify(res));
})();
""")
        ok(res == [{'avisos': ['prompt'], 'mandados': [['trailer_version', 'gpt', False, 'SI']], 'costo': [True]},
                   {'avisos': ['prompt'], 'mandados': [], 'costo': [True]},
                   {'avisos': [], 'mandados': [['trailer_version', 'gpt', False, '']], 'costo': [True]},
                   {'avisos': ['prompt'], 'mandados': [['trailer_version', 'gpt', False, 'SI']], 'costo': [True]},
                   {'avisos': [], 'mandados': [['trailer_version', 'gpt', True, '']], 'costo': []}],
           f'«▶ Ver con voz» / «💾 Guardar y rehacer»: SI escrito solo si su frase falta pagar, y sin voz no pregunta: {res}')

    # P4) «🌙 Cola de noche»: el SI se guarda solo si lo escribiste, y de noche vale solo para lo que se pagaba al escribirlo
    def proyecto_cola(nombre, textos):
        d = os.path.join(app.PROYECTOS, nombre)
        crear(d, ['original.mp4', 'musica.mp3'])
        json.dump({'bloques': [{'id': f'L{k + 1}', 'texto': t} for k, t in enumerate(textos)]},
                  open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        return d
    agregar = lambda p, si: pedir('POST', '/api/cola', json.dumps({'accion': 'agregar', 'p': p, 'calidad': 'alta', 'confirmo': si}).encode())
    item = lambda p: next((x for x in app.flujo.leer_cola(app.PROYECTOS).get('items', []) if x['p'] == p), {})
    d_sin = proyecto_cola('cola_sin', [''])  # todas las voces hechas (aquí: nada que decir): la página no pregunta SI
    st, b = agregar('cola_sin', '')
    ok(st == 200 and item('cola_sin').get('confirmo') == '' and 'aprobado' not in item('cola_sin'),
       f'sin SI escrito la cola no guarda ningún SI: {st} {b[:200]!r} {item("cola_sin")}')
    d_mas = proyecto_cola('cola_mas', ['Hola, hoy quitamos la cuenta de Google'])
    gasta_mas = app.gastos_sin_si(d_mas, 'todo', ['voz', 'musica'], {})
    st, b = agregar('cola_mas', 'SI')
    ok(st == 200 and gasta_mas and item('cola_mas').get('confirmo') == 'SI' and item('cola_mas').get('aprobado') == gasta_mas,
       f'con SI la cola guarda lo que se pagaba al escribirlo: {st} {b[:200]!r} {item("cola_mas")} {gasta_mas}')
    proyecto_cola('cola_igual', ['Otro bloque que aprobaste pagar'])
    agregar('cola_igual', 'SI')
    d_viejo = proyecto_cola('cola_viejo', ['Uno puesto antes del arreglo, con un SI que nadie escribió'])
    app.flujo.cambiar_cola(app.PROYECTOS, lambda c: c['items'].insert(0, {'id': 'viejo1', 'p': 'cola_viejo', 'estado': 'espera',
                                                                         'calidad': 'alta', 'agregado': time.time(), 'confirmo': 'SI'}))
    # después reescribes bloques en «📝 Ver y editar guion» y solo guardas
    json.dump({'bloques': [{'id': 'L1', 'texto': 'Ahora este bloque sí tiene voz que pagar'}]}, open(os.path.join(d_sin, 'guion.json'), 'w', encoding='utf-8'))
    json.dump({'bloques': [{'id': 'L1', 'texto': 'Hola, hoy quitamos la cuenta de Google'}, {'id': 'L2', 'texto': 'Y otro bloque nuevo'}]},
              open(os.path.join(d_mas, 'guion.json'), 'w', encoding='utf-8'))
    LANZADOS.clear()
    app.flujo.cambiar_cola(app.PROYECTOS, lambda c: c.update(andando=True))
    sigue = app.flujo.siguiente(app.PROYECTOS, PUERTO, lambda: False)  # de noche: arranca el primero que pueda
    r = lanzado()
    ok(sigue == 'cola_igual' and r and r[1].get('confirmo') == 'SI' and not LANZADOS,
       f'de noche solo arranca el que no cambió desde tu SI: {sigue} {r} {LANZADOS}')
    for p, aviso in (('cola_viejo', 'SI'), ('cola_sin', 'SI'), ('cola_mas', 'Cambió lo que se paga')):
        ok(item(p).get('estado') == 'fallo' and aviso in item(p).get('msg', ''),
           f'«{p}» no debe gastar sin tu SI (queda como fallado, con el motivo): {item(p)}')
    app.flujo.cambiar_cola(app.PROYECTOS, lambda c: c.update(andando=False, items=[]))

    # las páginas mandan confirmo 'SI' solo si de verdad se preguntó y lo escribiste (antes iba fijo: con nada que pagar al
    # pulsar, lo que cambiaras después se pagaba sin preguntar)
    nombres = ('pedirSi', 'confirmarVoz', 'confirmarMusica', 'confirmarGuionIA', 'confirmarVocesExtras', 'ejecutar', 'probarBloques',
               'seguirTodo', 'actualizarProyecto', 'colaAgregar')
    ok(all(funcion('index.html', n) for n in nombres), f'faltan funciones en index.html: {[n for n in nombres if not funcion("index.html", n)]}')
    if shutil.which('node') and all(funcion('index.html', n) for n in nombres):
        res = nodo('si_escrito', r"""
const P = 'p', q = encodeURIComponent;
let SI_ESCRITO = false, VOZ = null, EXTRAS = null, RESP = 'SI', preguntas = 0, mandados = [];
async function api(url, op) {
  if (url.startsWith('/api/costo_voz')) return VOZ;
  if (url.startsWith('/api/costo_extras')) { mandados.push({costo: decodeURIComponent(url.split('solo=')[1] || '')}); return EXTRAS; }
  if (url.startsWith('/api/estado')) return {archivos: {'guion.json': {}, 'original.mp4': {}, 'musica.mp3': {}, '8_testimonios.mp4': {}, 'trailer.mp4': {}}};
  if (url.startsWith('/api/ajustes')) return {ajustes: {}};
  if (url.startsWith('/api/capas_por_fuera')) return {solas: [], a_mano: []};
  if (url.startsWith('/api/actualizar')) return {extras: ['testimonios', 'trailer']};
  if (url.startsWith('/api/ejecutar') || url.startsWith('/api/cola')) mandados.push({url: url.split('?')[0] + (url.match(/paso=\w+/) || [''])[0], ...JSON.parse(op.body)});
  return {items: []};
}
function prompt() { preguntas++; return RESP; }
function confirm() { return true; } function alert() {} function soltarVideo() {} function refrescar() {} function pintarCola() {}
const caja = {value: 'alta', checked: false}, $ = () => caja;
""" + '\n'.join(funcion('index.html', n) for n in nombres) + r"""
(async () => {
  const res = {};
  const botones = {todo: () => ejecutar('todo'), voz: () => ejecutar('voz'), prueba: () => probarBloques(), seguirTodo, actualizarProyecto, colaAgregar};
  for (const [nombre, f] of Object.entries(botones)) {
    for (const [caso, voz, extras, resp] of [['gratis', {bloques: [], caracteres: 0}, {gasta: [], letras: 0}, 'SI'],
                                             ['con SI', {bloques: ['L1'], caracteres: 71}, {gasta: [], letras: 0}, 'SI'],
                                             ['cancela', {bloques: ['L1'], caracteres: 71}, {gasta: [], letras: 0}, null],
                                             ['extras con SI', {bloques: [], caracteres: 0}, {gasta: ['la narración de 1 testimonio (unos 47 créditos)'], letras: 47}, 'SI']]) {
      VOZ = voz; EXTRAS = extras; RESP = resp; preguntas = 0; mandados = []; SI_ESCRITO = false;
      if (nombre === 'prueba') caja.value = 'L1';
      await f();
      caja.value = 'alta';
      res[nombre + ' ' + caso] = {preguntas, confirmo: mandados.filter(m => m.url).map(m => m.confirmo || ''), costo: mandados.filter(m => m.costo !== undefined).map(m => m.costo)};
    }
  }
  console.log(JSON.stringify(res));
})();
""")
        for nombre in ('todo', 'voz', 'prueba', 'seguirTodo', 'actualizarProyecto', 'colaAgregar') if res else ():
            gratis, con_si, cancela, extras = (res[f'{nombre} {c}'] for c in ('gratis', 'con SI', 'cancela', 'extras con SI'))
            ok(gratis['preguntas'] == 0 and gratis['confirmo'] == [''], f'{nombre}: sin nada que pagar no pregunta y no manda un SI fijo: {gratis}')
            ok(con_si['preguntas'] == 1 and con_si['confirmo'] == ['SI'], f'{nombre}: con voz que pagar manda el SI que escribiste: {con_si}')
            ok(cancela['preguntas'] == 1 and cancela['confirmo'] == [], f'{nombre}: sin SI no manda nada: {cancela}')
        if res:
            x = res['actualizarProyecto extras con SI']
            ok(x['preguntas'] == 1 and x['confirmo'] == ['SI'] and x['costo'] == ['testimonios,trailer'],
               f'«🔁 Rehacer video» pregunta también por la voz del tráiler y los testimonios que vuelven: {x}')
    # el editor por pistas y el editor de guion: lo mismo
    ok(funcion('pistas.html', 'armar') and funcion('pistas.html', 'pedirSiGasto'), 'falta armar() en pistas.html')
    if shutil.which('node') and funcion('pistas.html', 'armar'):
        res = nodo('pistas_si', r"""
const P = 'p', q = encodeURIComponent, L = {extras: ['testimonios'], etiquetas: [], senales: []};
let PENDIENTE_REHACER = true, VOZ = null, RESP = 'SI', preguntas = 0, mandados = [];
async function guardar() { return {rehacer: true}; }
async function api(url, op) {
  if (url.startsWith('/api/costo_voz')) return VOZ;
  if (url.startsWith('/api/costo_extras')) return {gasta: [], letras: 0};
  if (url.startsWith('/api/estado')) return {archivos: {'musica.mp3': {}}};
  if (url.startsWith('/api/ejecutar')) mandados.push(JSON.parse(op.body));
  return {};
}
function prompt() { preguntas++; return RESP; } function confirm() { return true; } function alert() {} function pintar() {}
const caja = {textContent: '', className: ''}, $ = () => caja;
""" + funcion('pistas.html', 'pedirSiGasto') + '\n' + funcion('pistas.html', 'armar') + r"""
(async () => {
  const res = [];
  for (const [voz, resp] of [[{bloques: [], caracteres: 0}, 'SI'], [{bloques: ['L1'], caracteres: 71}, 'SI']]) {
    VOZ = voz; RESP = resp; preguntas = 0; mandados = []; PENDIENTE_REHACER = true;
    await armar();
    res.push({preguntas, confirmo: mandados.map(m => m.confirmo)});
  }
  console.log(JSON.stringify(res));
})();
""")
        ok(res == [{'preguntas': 0, 'confirmo': ['']}, {'preguntas': 1, 'confirmo': ['SI']}],
           f'«Armar» del editor por pistas (rehacer) manda SI solo si lo escribiste: {res}')
    seguir_g = funcion('guion.html', 'seguir')
    ok("confirmo: gasta.length ? 'SI' : ''" in seguir_g and "confirmo: 'SI'" not in seguir_g,
       'el editor de guion («Seguir») manda SI solo si preguntó y lo escribiste')

    # P5) transcribir con ElevenLabs (Scribe o Forced Alignment, ~330 créditos por minuto): con SI escrito, no con un Aceptar
    d = os.path.join(app.PROYECTOS, 'transcribe')
    crear(d, ['original.mp4', 'transcripcion.txt'])
    LANZADOS.clear()
    for datos in ({'motor': 'scribe'}, {'motor': 'alinear'}):
        st, b = pedir('POST', '/api/ejecutar?p=transcribe&paso=transcribir', json.dumps(datos).encode())
        ok(st != 200 and 'ElevenLabs' in b.decode('utf-8') and lanzado(0.3) is None, f'transcribir {datos} sin SI no debe arrancar: {st} {b[:200]!r}')
    json.dump({'elevenlabs': 'sk-prueba'}, open(app.AJUSTES, 'w'))  # con clave, «auto» es Scribe: también pide SI
    st, b = pedir('POST', '/api/ejecutar?p=transcribe&paso=transcribir', json.dumps({'motor': 'auto'}).encode())
    ok(st != 200 and lanzado(0.3) is None, f'transcribir «auto» (Scribe con tu clave) sin SI no debe arrancar: {st} {b[:200]!r}')
    json.dump({}, open(app.AJUSTES, 'w'))
    for datos in ({'motor': 'scribe', 'confirmo': 'SI'}, {'motor': 'whisper'}, {}):
        st, b = pedir('POST', '/api/ejecutar?p=transcribe&paso=transcribir', json.dumps(datos).encode())
        ok(st == 200 and lanzado(), f'transcribir {datos} arranca (con SI, o con Whisper, gratis): {st} {b[:200]!r}')
    c = app.comandos('transcribir', d, {})[0]
    ok(c[c.index('--motor') + 1] == 'whisper', f'sin motor elegido se transcribe con Whisper (gratis), no con Scribe: {c}')
    viejo_dur = app.duracion_original
    app.duracion_original = lambda d_, nombre='original.mp4': 900.0  # una grabación de 15 min
    try:
        c = json.loads(pedir('GET', '/api/costo_paso?p=transcribe&paso=transcribir&motor=scribe')[1])
    finally:
        app.duracion_original = viejo_dur
    ok(c == {'gasta': ['transcribir con ElevenLabs Scribe (unos 4.950 créditos: ~330 por minuto de tu grabación)']},
       f'transcribir con Scribe dice cuántos créditos gasta: {c}')
    ok(json.loads(pedir('GET', '/api/costo_paso?p=transcribe&paso=transcribir&motor=whisper')[1]) == {'gasta': []}, 'Whisper no gasta')
    ok("{'motor': 'auto', 'confirmo': 'SI'} if a.confirmo_creditos" in open(os.path.join(RAIZ, 'deepseek', 'video.py'), encoding='utf-8').read(),
       'DeepSeek con --confirmo-creditos manda el SI del autor al transcribir con Scribe')
    if shutil.which('node') and funcion('index.html', 'ejecutar'):
        res = nodo('transcribir', r"""
const P = 'p', q = encodeURIComponent;
let SI_ESCRITO = false, ACEPTA = [], RESP = 'SI', preguntas = 0, mandados = [], costos = [];
async function api(url, op) {
  if (url.startsWith('/api/costo_paso')) { costos.push(url.split('motor=')[1]); return {gasta: ['transcribir con ElevenLabs Scribe (unos 4.950 créditos)']}; }
  if (url.startsWith('/api/estado')) return {archivos: {'transcripcion.txt': {}}};
  if (url.startsWith('/api/ejecutar')) mandados.push(JSON.parse(op.body));
  return {};
}
function prompt() { preguntas++; return RESP; } function confirm() { return ACEPTA.shift(); } function alert() {}
function refrescar() {} function soltarVideo() {}
const caja = {value: 'alta'}, $ = () => caja;
""" + funcion('index.html', 'pedirSi') + '\n' + funcion('index.html', 'ejecutar') + r"""
(async () => {
  const res = [];
  for (const [acepta, resp] of [[[false, true], 'SI'], [[false, true], null], [[true], 'si'], [[false, false], 'SI']]) {
    ACEPTA = acepta; RESP = resp; preguntas = 0; mandados = []; costos = [];
    await ejecutar('transcribir');
    res.push({preguntas, costos, mandados: mandados.map(m => [m.motor, m.confirmo || ''])});
  }
  console.log(JSON.stringify(res));
})();
""")
        ok(res == [{'preguntas': 1, 'costos': ['scribe'], 'mandados': [['scribe', 'SI']]}, {'preguntas': 1, 'costos': ['scribe'], 'mandados': []},
                   {'preguntas': 1, 'costos': ['alinear'], 'mandados': [['alinear', 'SI']]}, {'preguntas': 0, 'costos': [], 'mandados': [['whisper', '']]}],
           f'«Transcribir tu voz»: Scribe o alinear piden SI escrito con los créditos; Whisper no pregunta: {res}')

    # P6) «🎙 Limpiar la voz» con ElevenLabs, «🔊 Efectos de sonido → ✨ Con ElevenLabs» y la voz nueva del «📱 Short»: con SI escrito
    d = os.path.join(app.PROYECTOS, 'mejoras')
    crear(d, ['original.mp4', 'testimonios/t1.mp4', 'testimonios/t2.mp4'])
    json.dump({'TESTIMONIOS': [{'archivo': 't1.mp4'}, {'archivo': 't2.mp4'}]}, open(os.path.join(d, 'testimonios', 'testimonios.json'), 'w'))
    json.dump({'tomas': [{'id': 'S1', 'texto': 'Así quitas la cuenta en dos minutos', 'src_inicio': 3}]},
              open(os.path.join(d, 'short_guion.json'), 'w', encoding='utf-8'))
    LANZADOS.clear()
    gastan = (('m_limpiar', {'archivo': 'original.mp4', 'motor': 'eleven'}), ('m_limpiar', {'archivo': 'testimonios', 'motor': 'eleven'}),
              ('m_sonidos', {'motor': 'eleven', 'solo': 'clic'}), ('m_sonidos', {'motor': 'eleven'}), ('short', {'duracion': 60, 'voz_nueva': True}))
    for paso, datos in gastan:
        st, b = pedir('POST', f'/api/ejecutar?p=mejoras&paso={paso}', json.dumps(datos).encode())
        ok(st != 200 and 'ElevenLabs' in b.decode('utf-8') and lanzado(0.3) is None, f'«{paso}» {datos} sin SI no debe arrancar: {st} {b[:200]!r}')
        st, b = pedir('POST', f'/api/ejecutar?p=mejoras&paso={paso}', json.dumps({**datos, 'confirmo': 'SI'}).encode())
        ok(st == 200 and lanzado(), f'«{paso}» {datos} con SI arranca: {st} {b[:200]!r}')
    for paso, datos in (('m_limpiar', {'archivo': 'original.mp4', 'motor': 'pc'}), ('m_limpiar', {'archivo': 'original.mp4', 'motor': 'eleven', 'deshacer': True}),
                        ('m_sonidos', {'motor': 'pc'}), ('short', {'duracion': 60})):
        st, b = pedir('POST', f'/api/ejecutar?p=mejoras&paso={paso}', json.dumps(datos).encode())
        ok(st == 200 and lanzado(), f'«{paso}» {datos} no gasta ElevenLabs: arranca sin pedir SI: {st} {b[:200]!r}')
    viejo_dur = app.duracion_original
    app.duracion_original = lambda d_, nombre='original.mp4': 90.0 if nombre.startswith('testimonios') else 900.0
    try:
        costo_m = lambda extra: json.loads(pedir('GET', f'/api/costo_paso?p=mejoras&{extra}')[1])
        ok(costo_m('paso=m_limpiar&archivo=original.mp4&motor=eleven') == {'gasta': ['limpiar la voz con ElevenLabs (unos 15.000 créditos: ~1.000 por minuto de audio)']},
           f"limpiar con ElevenLabs dice cuánto gasta tu grabación: {costo_m('paso=m_limpiar&archivo=original.mp4&motor=eleven')}")
        ok(costo_m('paso=m_limpiar&archivo=testimonios&motor=eleven') == {'gasta': ['limpiar la voz con ElevenLabs (unos 3.000 créditos: ~1.000 por minuto de audio)']},
           f"«Todos los testimonios» suma los de tu lista: {costo_m('paso=m_limpiar&archivo=testimonios&motor=eleven')}")
        ok(costo_m('paso=m_sonidos&motor=eleven&solo=clic') == {'gasta': ['crear el sonido con ElevenLabs (unos 100 créditos)']}, 'un sonido de ElevenLabs')
        largo = getattr(app, 'costo_voz_short', lambda d_: {})(d).get('caracteres')  # lo que voz.py le pediría (el texto con su punto final)
        ok(largo and largo >= len('Así quitas la cuenta en dos minutos')
           and costo_m('paso=short&voz_nueva=1') == {'gasta': [f'la voz nueva del Short (unos {largo} créditos: 1 frase)']},
           f"la voz nueva del Short cuenta las frases sin hacer: {costo_m('paso=short&voz_nueva=1')}")
    finally:
        app.duracion_original = viejo_dur
    if shutil.which('node') and funcion('mejoras.html', 'siGasto'):
        res = nodo('mejoras_si', r"""
const P = 'p', q = encodeURIComponent;
let COSTO = null, RESP = 'SI', preguntas = 0, mandados = [], costos = [], MOTOR = 'eleven';
async function api(url, op) {
  if (url.startsWith('/api/costo_paso')) { costos.push(url.split('paso=')[1]); if (COSTO === 'error') throw new Error('x'); return COSTO; }
  return {};
}
function correr(paso, datos) { mandados.push([paso, datos.motor, datos.confirmo]); }
function prompt() { preguntas++; return RESP; } function confirm() { return true; } function alert() {}
const $ = s => ({'#limMotor': {value: MOTOR}, '#limArchivo': {value: 'original.mp4'}})[s];
""" + funcion('mejoras.html', 'siGasto') + '\n' + funcion('mejoras.html', 'sonCrear') + '\n' + funcion('mejoras.html', 'limpiar') + r"""
(async () => {
  const res = [];
  for (const [f, motor, costo, resp] of [[() => limpiar(), 'eleven', {gasta: ['limpiar la voz con ElevenLabs (unos 15.000 créditos)']}, 'SI'],
                                         [() => limpiar(), 'eleven', {gasta: ['limpiar la voz con ElevenLabs (unos 15.000 créditos)']}, null],
                                         [() => limpiar(), 'eleven', 'error', 'no'], [() => limpiar(), 'pc', null, null],
                                         [() => limpiar(true), 'eleven', null, null],
                                         [() => sonCrear('clic'), 'eleven', {gasta: ['crear el sonido con ElevenLabs (unos 100 créditos)']}, 'si'],
                                         [() => sonCrear('clic'), 'eleven', {gasta: ['crear el sonido con ElevenLabs (unos 100 créditos)']}, null]]) {
    MOTOR = motor; COSTO = costo; RESP = resp; preguntas = 0; mandados = []; costos = [];
    await f();
    res.push({preguntas, costos, mandados});
  }
  console.log(JSON.stringify(res));
})();
""")
        ok(res == [{'preguntas': 1, 'costos': ['m_limpiar&archivo=original.mp4&motor=eleven'], 'mandados': [['m_limpiar', 'eleven', 'SI']]},
                   {'preguntas': 1, 'costos': ['m_limpiar&archivo=original.mp4&motor=eleven'], 'mandados': []},
                   {'preguntas': 1, 'costos': ['m_limpiar&archivo=original.mp4&motor=eleven'], 'mandados': []},
                   {'preguntas': 0, 'costos': [], 'mandados': [['m_limpiar', 'pc', '']]},
                   {'preguntas': 0, 'costos': [], 'mandados': [['m_limpiar', 'eleven', '']]},
                   {'preguntas': 1, 'costos': ['m_sonidos&motor=eleven&solo=clic'], 'mandados': [['m_sonidos', 'eleven', 'SI']]},
                   {'preguntas': 1, 'costos': ['m_sonidos&motor=eleven&solo=clic'], 'mandados': []}],
           f'«🎙 Limpiar» con ElevenLabs y «✨ Con ElevenLabs» de los sonidos piden SI escrito; gratis o «Volver» no preguntan: {res}')
    else:
        ok(False, 'falta siGasto() en mejoras.html')
    if shutil.which('node') and funcion('index.html', 'shortHacer'):
        res = nodo('short_si', r"""
const P = 'p', q = encodeURIComponent;
let SI_ESCRITO = false, COSTO = null, RESP = 'SI', VOZ = true, preguntas = 0, mandados = [];
async function api(url, op) {
  if (url.startsWith('/api/costo_paso')) return COSTO;
  if (url.startsWith('/api/ejecutar')) mandados.push(JSON.parse(op.body));
  if (url.startsWith('/api/estado')) return {trabajo: {}};
  return {};
}
function prompt() { preguntas++; return RESP; } function confirm() { return true; } function alert() {}
async function sxGuardar() {} async function shortVer() {}
globalThis.setTimeout = f => f();
const caja = {className: '', textContent: '36', disabled: false}, $ = s => s === '#shortVozNueva' ? {checked: VOZ} : s === '#shortDur' ? {value: '60'} : caja;
""" + funcion('index.html', 'pedirSi') + '\n' + funcion('index.html', 'shortHacer') + r"""
(async () => {
  const res = [];
  for (const [voz, costo, resp] of [[true, {gasta: ['la voz nueva del Short (unos 36 créditos: 1 frase)']}, 'SI'],
                                    [true, {gasta: ['la voz nueva del Short (unos 36 créditos: 1 frase)']}, null],
                                    [true, {gasta: []}, null], [false, null, null]]) {
    VOZ = voz; COSTO = costo; RESP = resp; preguntas = 0; mandados = [];
    await shortHacer();
    res.push({preguntas, mandados: mandados.map(m => [m.voz_nueva, m.confirmo])});
  }
  console.log(JSON.stringify(res));
})();
""")
        ok(res == [{'preguntas': 1, 'mandados': [[True, 'SI']]}, {'preguntas': 1, 'mandados': []},
                   {'preguntas': 0, 'mandados': [[True, '']]}, {'preguntas': 0, 'mandados': [[False, '']]}],
           f'«📱 Short» con voz nueva pide SI escrito solo si hay frases que pagar: {res}')

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
    # subes un testimonio por error y lo quitas enseguida con ✕: se queda 10 minutos en la carpeta (podría venir del celular),
    # pero ya no es un testimonio del video: ni «🎛 Audio e imagen» ni su «Limpiar todos» ni el paquete de la nube lo usan
    open(os.path.join(t, 't3.mp4'), 'wb').write(b'subido por error')
    st, b = guardar(['t1.mp4'])
    ok(st == 200 and os.path.exists(os.path.join(t, 't3.mp4')), f'lo recién subido no se toca al guardar: {listar(t)}')
    limpiar = mejoras.comandos('m_limpiar', d, {'archivo': 'testimonios'}, 'py', 'aj')[0]
    ok(limpiar[limpiar.index('--entrada') + 1:limpiar.index('--motor')] == [os.path.join('testimonios', 't1.mp4')],
       f'«Limpiar la voz» de todos los testimonios solo toma los de tu lista: {limpiar}')
    # la papelera no es un testimonio: ni en la lista, ni en «🎛 Audio e imagen», ni en el montaje (testimonios.py usa la lista)
    lista = json.loads(pedir('GET', '/api/pistas?p=cruce&g=testimonios')[1])
    ok(lista == {'TESTIMONIOS': [{'archivo': 't1.mp4'}]}, f'la lista de testimonios solo trae los tuyos: {lista}')
    ok(mejoras.estado(d)['testimonios'] == ['t1.mp4'], f"«🎛 Audio e imagen» debe listar solo los testimonios de tu lista: {mejoras.estado(d)['testimonios']}")
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
    ok(rutas and 'testimonios/t3.mp4' not in rutas and 'testimonios/testimonios.json' in rutas,
       f'el paquete de la nube no lleva el testimonio que quitaste recién: {rutas}')
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
