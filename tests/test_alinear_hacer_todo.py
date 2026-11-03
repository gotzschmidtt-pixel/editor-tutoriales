"""Prueba rápida de «Alinear cada frase con su pantalla» dentro de «▶ Hacer todo» (03/11/2026). Sin internet y sin gastar
nada: el lector de texto (OCR) va simulado sobre un video sintético de colores, y tus ajustes y proyectos no se tocan
(todo va a una carpeta temporal).
- alinear.ajustar respeta los topes de fabian: ×1 con su cara (y nada en un ⭐), ×1 en los pasos clave (03/11/2026, antes
  ×1,5: el dato nunca acelerado), ×2 en los de
  configuración, ×6 en lo demás, y nunca pisa el tramo del bloque vecino;
- alinear.py de punta a punta: deja guion.json.antes_alinear, marca "alineado" en los bloques que corrió, no toca los del
  gancho, vuelve a leer la pantalla cada 0,5 s solo cerca de las frases dudosas, y con --solo-revisar no cambia nada;
- con «Solo los bloques» (guion_prueba.json) tampoco pisa a los vecinos que están en el guion completo;
- la app: 'alinear' va entre 'voz' y 'montaje' en «Hacer todo» y en «Solo los bloques», se quita con la casilla de
  «⚙ Ajustes IA», los 2 primeros videos van en modo solo avisar (con la cuenta en ajustes.json) y el freno antes del
  montaje no vuelve a parar por las mismas frases.
Uso: python tests/test_alinear_hacer_todo.py   (sale con 1 si algo falla)
"""
import http.client, http.server, json, os, shutil, subprocess, sys, tempfile, threading, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('alinear', 'voz', 'ia', 'app', 'celular'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
os.environ['SIN_NAVEGADOR'] = '1'
for k in ('VOZ_ID', 'VOZ_IDIOMA', 'ELEVENLABS_API_KEY'):
    os.environ.pop(k, None)
import alinear  # noqa: E402
import ia  # noqa: E402
import voz  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


tmp = tempfile.mkdtemp(prefix='alinear_todo_')
try:
    # 1) los topes, con dos frases cuya pantalla está mucho más adelante (antes: ×4,29 a ×6 y 12 s estirados a 45 s)
    rev = [('frase uno', 1.0, 101.0, 'uno', 100.0), ('frase dos', 6.0, 106.0, 'dos', 130.0)]
    lo, hi = 95.0, 140.0
    for nombre, extra, tipo, tope in (('cara', {'cara': True}, None, 1.0), ('crítico', {'critico': True}, None, 1.0),
                                      ('crítico (tipo)', {}, 'critico', 1.0), ('configuración', {'paso': True}, None, 2.0),
                                      ('normal', {}, None, 6.0)):
        b = {'id': 'L09', 'montaje': {'modo': 'lento', 'src_inicio': 100.0, 'src_fin': 112.0, 'velocidad': 1.0, **extra}}
        if tipo:
            b['tipo'] = tipo
        n = alinear.ajustar(b, rev, lo, hi)
        ok(n is not None, f'{nombre}: debería correr el tramo')
        if n:
            ok(n['velocidad'] <= tope, f'{nombre}: quedó a ×{n["velocidad"]} (tope ×{tope})')
            ok(lo <= n['src_inicio'] < n['src_fin'] <= hi, f'{nombre}: pisa al vecino: {n["src_inicio"]}–{n["src_fin"]} (libre {lo}–{hi})')
            ok(n.get('alineado') is True, f'{nombre}: falta "alineado": {n}')
            ok(n['src_fin'] - n['src_inicio'] <= tope * 12.0 + 0.1, f'{nombre}: estiró el tramo de 12 s a {n["src_fin"] - n["src_inicio"]:.1f} s')
    n = alinear.ajustar({'id': 'L10', 'montaje': {'modo': 'lento', 'src_inicio': 100.0, 'src_fin': 112.0, 'velocidad': 1.0,
                                                  'cara': True}}, rev, lo, hi)
    ok(n and n['velocidad'] == 1.0, f'con su cara va a ×1, ni acelerado ni en cámara lenta: {n}')
    estrella = {'id': 'L11', 'montaje': {'modo': 'lento', 'src_inicio': 100.0, 'src_fin': 112.0, 'velocidad': 1.0, 'importante': True}}
    ok(alinear.ajustar(estrella, rev, lo, hi) is None, 'un «⭐ corte importante» no se toca')
    gancho = {'id': 'L01', 'gancho': True, 'montaje': {'modo': 'lento', 'src_inicio': 100.0, 'src_fin': 112.0, 'velocidad': 1.0}}
    ok(alinear.ajustar(gancho, rev, lo, hi) is None, 'un bloque del gancho no se toca')
    ok(alinear.TOLERA == (1.0, 1.5), f'la tolerancia es de 1 s antes y 1,5 s después: {alinear.TOLERA}')
    ok(voz.tope_velocidad({'paso': True}) == 2.0 and voz.tope_velocidad({'cara': True, 'paso': True}) == 1.0
       and voz.tope_velocidad({'critico': True}) == 1.0 and voz.tope_velocidad({}) == voz.VEL_MAX,
       'voz.tope_velocidad debe tener los topes de fabian')

    # 2) de punta a punta: un video de 70 s con 7 pantallas (cada color, un texto) y el OCR simulado
    d = os.path.join(tmp, 'proyecto')
    os.makedirs(os.path.join(d, 'voz'))
    PANTALLAS = [  # (desde, color RGB, texto que «se lee»)
        (0.0, (0, 0, 0), 'Candado bloqueado'), (7.3, (255, 0, 0), 'Pantalla principal'),
        (19.3, (0, 255, 0), 'Configuracion general'), (25.3, (0, 0, 255), 'Reiniciar dispositivo'),
        (32.3, (255, 255, 0), 'Copiando archivos'), (41.3, (255, 0, 255), 'Listo terminado'),
        (47.3, (0, 255, 255), 'Pantalla final gracias')]
    vf = ','.join(f"drawbox=x=0:y=0:w=iw:h=ih:t=fill:color=0x{r:02X}{g:02X}{b:02X}:enable='gte(t,{t0})'"
                  for t0, (r, g, b), _ in PANTALLAS[1:])
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=160x90:r=10:d=70',
                    '-vf', vf, '-c:v', 'libx264', '-g', '10', '-pix_fmt', 'yuv420p', os.path.join(d, 'original.mp4')], check=True)
    leidos = []

    def leer_textos(ocr, img):  # el OCR simulado: el texto de la pantalla del color más parecido
        b, g, r = (float(img[..., k].mean()) for k in range(3))
        leidos.append(1)
        t = min(PANTALLAS, key=lambda p: sum((x - y) ** 2 for x, y in zip(p[1], (r, g, b))))[2]
        return [(t, 0, 0, 10, 10)]
    ia.lector_ocr, ia.leer_textos = (lambda: object()), leer_textos

    def voz_de(bid, frases):
        """align.json falso: [(frase, desde, hasta)] con los tiempos repartidos letra por letra (no se llama a ElevenLabs)."""
        chars, t0s, t1s = [], [], []
        for k, (txt, a, z) in enumerate(frases):
            txt = (' ' if k else '') + txt
            for i, ch in enumerate(txt):
                chars.append(ch)
                t0s.append(round(a + (z - a) * i / len(txt), 3))
                t1s.append(round(a + (z - a) * (i + 1) / len(txt), 3))
        json.dump({'characters': chars, 'character_start_times_seconds': t0s, 'character_end_times_seconds': t1s},
                  open(os.path.join(d, 'voz', bid + '.align.json'), 'w', encoding='utf-8'))
        return ''.join(chars)

    bloques = [
        {'id': 'L01', 'gancho': True, 'texto': voz_de('L01', [('Te enseño la configuracion general del telefono.', 0, 5.0)]),
         'montaje': {'modo': 'lento', 'src_inicio': 0.0, 'src_fin': 6.0, 'velocidad': 1.0}},
        {'id': 'L02', 'texto': voz_de('L02', [('Ahora tocamos reiniciar dispositivo y esperamos un momento.', 0, 7.0)]),
         'montaje': {'modo': 'lento', 'src_inicio': 20.0, 'src_fin': 28.0, 'velocidad': 1.0}},
        {'id': 'L03', 'texto': voz_de('L03', [('Esperamos copiando archivos.', 0, 3.4), ('Ahora sale listo terminado.', 3.5, 5.5)]),
         'montaje': {'modo': 'lento', 'src_inicio': 33.0, 'src_fin': 40.0, 'velocidad': 1.0, 'paso': True}},
        {'id': 'L04', 'texto': voz_de('L04', [('Y eso es todo por hoy amigos.', 0, 4.5)]),
         'montaje': {'modo': 'lento', 'src_inicio': 56.0, 'src_fin': 62.0, 'velocidad': 1.0}}]
    original = json.dumps({'bloques': bloques}, ensure_ascii=False, indent=1)
    open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8').write(original)
    os.makedirs(os.path.join(tmp, 'prueba_y_solo'))
    for f in ('guion.json', 'original.mp4', 'voz'):  # copia para las vueltas de abajo, antes de alinear
        (shutil.copytree if f == 'voz' else shutil.copy)(os.path.join(d, f), os.path.join(tmp, 'prueba_y_solo', f))

    def alinear_main(*args):
        viejo = sys.argv
        sys.argv = ['alinear.py'] + list(args)
        try:
            alinear.main()
        finally:
            sys.argv = viejo

    alinear_main('--proyecto', d)
    g = {b['id']: b for b in json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))['bloques']}
    ok(os.path.exists(os.path.join(d, 'guion.json.antes_alinear')) and
       open(os.path.join(d, 'guion.json.antes_alinear'), encoding='utf-8').read() == original,
       'antes de escribir debe quedar guion.json.antes_alinear con el guion de antes')
    mo1, mo2, mo3, mo4 = (g[x]['montaje'] for x in ('L01', 'L02', 'L03', 'L04'))
    ok(mo1 == bloques[0]['montaje'] and 'alineado' not in mo1, f'el bloque del gancho no se toca: {mo1}')
    ok(mo2.get('alineado') is True and mo2['src_inicio'] >= 6.0 and mo2['src_fin'] <= min(33.0, mo3['src_inicio']),
       f'L02 se corre sin pisar a L01 (hasta 6 s) ni a L03 (desde 33 s): {mo2}')
    ok(abs(mo2['src_inicio'] + voz.DESFASE * mo2['velocidad'] - 26.0) <= 1.0,
       f'L02: «reiniciar dispositivo» tiene que caer donde se ve (desde 25,3 s): {mo2}')
    ok(mo3.get('alineado') is True and mo3['velocidad'] <= 2.0 and mo3['src_fin'] <= 56.0 and mo3['src_inicio'] >= mo2['src_fin'],
       f'L03 (paso de configuración) a ×2 como máximo y sin pisar a sus vecinos: {mo3}')
    ok(mo4 == bloques[3]['montaje'], f'L04 ya estaba bien: no se toca: {mo4}')
    txt = open(os.path.join(d, 'alineacion.txt'), encoding='utf-8').read()
    ok('L02: corrí el tramo' in txt and 'L03: corrí el tramo' in txt and 'L01' not in txt, f'alineacion.txt: {txt}')
    cache = json.load(open(os.path.join(d, 'ocr_pantalla.json'), encoding='utf-8'))
    finos = [float(k) for k in cache if not alinear.grueso(float(k))]
    ok(finos and all(any(abs(f - s) <= alinear.CERCA + alinear.FINO for s in (20.3, 36.8)) for f in finos),
       f'debe volver a leer cada 0,5 s solo cerca de las frases dudosas (20,3 s y 36,8 s): {sorted(finos)}')
    ok(len([k for k in cache if alinear.grueso(float(k))]) >= 35, 'la pasada de cada 2 s cubre toda la grabación')
    antes = len(leidos)
    alinear_main('--proyecto', d)  # otra vuelta: la pantalla ya está leída (caché) y lo corrido no se mueve de más
    g2 = {b['id']: b for b in json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))['bloques']}
    ok(g2['L02']['montaje']['src_inicio'] == mo2['src_inicio'] and g2['L03']['montaje']['src_inicio'] == mo3['src_inicio'],
       'una segunda vuelta no vuelve a correr los tramos ya alineados')
    ok(len(leidos) - antes <= 30, f'la segunda vuelta usa lo ya leído (leyó {len(leidos) - antes} cuadros)')

    # 3) --solo-revisar (los 2 primeros videos): no cambia nada y dice lo que haría
    d2 = os.path.join(tmp, 'prueba_y_solo')
    shutil.copy(os.path.join(d, 'ocr_pantalla.json'), d2)
    alinear_main('--proyecto', d2, '--solo-revisar')
    txt = open(os.path.join(d2, 'alineacion.txt'), encoding='utf-8').read()
    ok(open(os.path.join(d2, 'guion.json'), encoding='utf-8').read() == original and
       not os.path.exists(os.path.join(d2, 'guion.json.antes_alinear')), '--solo-revisar no debe tocar el guion')
    ok('Modo solo avisar' in txt and '(solo aviso, no lo toqué) correría el tramo' in txt and 'no se ve; aparece en' in txt,
       f'--solo-revisar debe decir qué haría y qué no cae en su pantalla: {txt}')

    # 4) «Solo los bloques»: guion_prueba.json con L02 solo; L03 (desde 33 s) está en guion.json y no se pisa
    prueba = {'bloques': [b for b in json.loads(original)['bloques'] if b['id'] == 'L02']}
    json.dump(prueba, open(os.path.join(d2, 'guion_prueba.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    alinear_main('--proyecto', d2, '--guion', 'guion_prueba.json')
    mp = json.load(open(os.path.join(d2, 'guion_prueba.json'), encoding='utf-8'))['bloques'][0]['montaje']
    ok(mp.get('alineado') and mp['src_fin'] <= 33.0, f'«Solo los bloques» no debe pisar a L03 del guion completo: {mp}')
    ok(open(os.path.join(d2, 'guion.json'), encoding='utf-8').read() == original and
       os.path.exists(os.path.join(d2, 'guion_prueba.json.antes_alinear')), '«Solo los bloques» solo cambia guion_prueba.json')

    # 5) la app
    import app  # noqa: E402
    import flujo  # noqa: E402
    ok(app.TODO.index('alinear') == app.TODO.index('voz') + 1 and app.TODO.index('montaje') == app.TODO.index('alinear') + 1,
       f"'alinear' tiene que ir entre 'voz' y 'montaje': {app.TODO}")
    app.AJUSTES = os.path.join(tmp, 'ajustes.json')  # nunca el app/ajustes.json de verdad
    app.PROYECTOS = os.path.join(tmp, 'proyectos')
    json.dump({}, open(app.AJUSTES, 'w'))
    aj = lambda: json.load(open(app.AJUSTES, encoding='utf-8'))
    solo = lambda p: '--solo-revisar' in app.comandos('alinear', os.path.join(app.PROYECTOS, p), {})[0]
    ok(solo('VIDEO A') and solo('VIDEO B') and not solo('VIDEO C') and solo('VIDEO A'),
       'los 2 primeros videos solo avisan (también al rehacerlos); el tercero ya corrige solo')
    ok(aj().get('alinear_avisados') == ['VIDEO A', 'VIDEO B'], f'la cuenta queda a la vista en ajustes.json: {aj()}')
    json.dump(dict(aj(), alinear_solo_avisar=0), open(app.AJUSTES, 'w'))
    ok(not solo('VIDEO A'), 'con «alinear_solo_avisar»: 0 corrige solo desde ya')
    json.dump(dict(aj(), alinear_solo_avisar=3), open(app.AJUSTES, 'w'))
    ok(solo('VIDEO D') and not solo('VIDEO E'), 'se puede pedir un video más en modo solo avisar')

    dp = os.path.join(app.PROYECTOS, 'bloques')
    os.makedirs(dp)
    for f in ('original.mp4', 'guion.json'):
        shutil.copy(os.path.join(d2, f), dp)
    c = app.comandos('prueba', dp, {})
    ok(len(c) == 4 and 'voz.py' in c[0][1] and 'alinear.py' in c[1][1] and c[1][c[1].index('--guion') + 1] == app.PRUEBA_GUION
       and 'montaje.py' in c[2][1], f'«Solo los bloques»: voz, alinear (con guion_prueba.json), montaje y voz puesta: {c}')
    json.dump(dict(aj(), alinear=False), open(app.AJUSTES, 'w'))
    ok(not any('alinear.py' in x[1] for x in app.comandos('prueba', dp, {})), 'con la casilla destildada no se alinea')

    LANZADOS = []
    app.correr_despierto = lambda p, pasos, datos: (LANZADOS.append((list(pasos), dict(datos))), app.TRABAJO.update(proyecto=None))
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), app.Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def hacer_todo():
        cn = http.client.HTTPConnection('127.0.0.1', srv.server_address[1], timeout=20)
        cn.request('POST', '/api/ejecutar?p=bloques&paso=todo', body=b'{"confirmo": "SI"}',
                   headers={'Host': f'127.0.0.1:{srv.server_address[1]}'})
        cn.getresponse().read()
        for _ in range(100):
            if LANZADOS:
                return LANZADOS.pop()[0]
            time.sleep(0.05)
        return []
    json.dump({}, open(app.AJUSTES, 'w'))
    p = hacer_todo()
    ok('alinear' in p and p.index('alinear') == p.index('voz') + 1 and p[p.index('alinear') + 1] == 'montaje',
       f'«▶ Hacer todo» debe alinear después de la voz y antes del montaje (casilla marcada por defecto): {p}')
    json.dump({'alinear': False}, open(app.AJUSTES, 'w'))
    p = hacer_todo()
    ok(p and 'alinear' not in p and 'montaje' in p, f'con la casilla destildada «Hacer todo» no alinea: {p}')
    srv.shutdown()

    # el freno antes del montaje: solo por frases que quedaron sin arreglar, y no otra vez por las mismas
    dc = os.path.join(app.PROYECTOS, 'freno')
    os.makedirs(os.path.join(dc, 'voz'))
    for f in ('original.mp4', 'guion.json'):
        open(os.path.join(dc, f), 'w').write('{}')
    viejos = (app.comandos, app.asegurar_librerias, app.asegurar_node)

    def vuelta(lineas):
        app.comandos = lambda paso, d_, op: ([[sys.executable, '-c', f'print({chr(10).join(lineas)!r})']] if paso == 'alinear' else [])
        app.asegurar_librerias = app.asegurar_node = (lambda *a: None)
        try:
            app.TRABAJO.update(proyecto='freno')
            app.correr('freno', ['alinear', 'montaje'], {})
        finally:
            app.comandos, app.asegurar_librerias, app.asegurar_node = viejos
            app.TRABAJO.update(proyecto=None)
        return app.RESULTADO.get('freno') or {}
    mala = '· L02: «Ahora tocamos reiniciar» nombra «reiniciar dispositivo», pero en 0:{} no se ve; aparece en 0:26.0'
    r = vuelta(['· L03: corrí el tramo a 34.5–46.5 ×2.0', mala.format('20.3')])
    ok(r.get('pausa') == 'alineacion' and r.get('avisos') and 'Montar video' not in r.get('hechos', []),
       f'con una frase sin arreglar se frena antes del montaje: {r}')
    r = vuelta([mala.format('21.0')])  # la misma frase (el segundo cambió un poco): no se vuelve a frenar
    ok(not r.get('pausa') and 'Montar video' in r.get('hechos', []), f'no debe frenar otra vez por la misma frase: {r}')
    r = vuelta(['· L03: corrí el tramo a 34.5–46.5 ×2.0'])
    ok(not r.get('pausa'), f'si todo quedó en su lugar no se frena: {r}')
    r = vuelta([mala.format('20.3').replace('L02', 'L05')])
    ok(r.get('pausa') == 'alineacion', f'una frase nueva sí vuelve a frenar: {r}')
    avisos = []
    flujo_avisar = flujo.avisar
    flujo.avisar = lambda aj_, titulo, texto, url='', fallo=False: avisos.append(texto)
    try:
        flujo.avisar_resultado({}, 'freno', {'ok': True, 'pausa': 'alineacion', 'total': 2, 'segundos': 60})
    finally:
        flujo.avisar = flujo_avisar
    ok(avisos and 'antes del montaje' in avisos[0], f'el aviso al celular dice que se frenó antes del montaje: {avisos}')

    html = open(os.path.join(RAIZ, 'app', 'index.html'), encoding='utf-8').read()
    ok('id="ajAlinear"> 📐 Alinear cada frase con su pantalla (gratis)' in html and "$('#ajAlinear').checked = a.alinear !== false" in html
       and "alinear: $('#ajAlinear').checked" in html and 'alinear_solo_avisar' in html,
       'falta la casilla «Alinear cada frase con su pantalla (gratis)» en «⚙ Ajustes IA» (marcada por defecto) o no se guarda')
    ok("r.pausa === 'alineacion'" in html, 'la página tiene que mostrar el freno antes del montaje')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: «Alinear» en «Hacer todo» (topes de fabian, vecinos, gancho, solo avisar, freno)')
sys.exit(1 if fallos else 0)
