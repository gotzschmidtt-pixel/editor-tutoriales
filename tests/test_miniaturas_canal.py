"""Prueba de «miniaturas como las de tu canal» (fabian, 03/11/2026: «las que estás haciendo no se parecen nada a las mías de mi
canal»). SIN internet y SIN gastar: la red de YouTube y la IA de imágenes van simuladas.
- canal_referencia lee la página pública del canal, baja las miniaturas a una carpeta de prueba (sin los Shorts y sin las
  franjas negras) y marca las recientes y las más vistas;
- elegir() da 2-3 parecidas al video (misma marca o servicio); las fijadas van primero y las quitadas nunca;
- el pedido a GPT lleva el modelo 2.5, la calidad (borrador en baja, final en media), las fotos de fabian, los logos de su
  biblioteca y las miniaturas del canal como imágenes; el prompt trae la fórmula (abajo la frase con el logo entre las
  palabras, etiquetas en las esquinas de arriba, fondo oscuro, sin webs) y que las referencias son solo de estilo;
- la app no dibuja nada encima, y la final parte de las fotos originales (no de la imagen de GPT);
- un texto con una web o «SIN PC» frena ANTES de gastar;
- «🖼 Miniatura» manda la fórmula del canal por defecto (la mixta solo si se pide) y sus rutas funcionan.
Uso: python tests/test_miniaturas_canal.py   (sale con 1 si algo falla)
"""
import argparse, base64, io, json, os, sys, tempfile, urllib.error, urllib.request
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


def jpg(w, h, color=(40, 60, 200)):
    img = np.full((h, w, 3), color, np.uint8)
    return cv2.imencode('.jpg', img)[1].tobytes()


def lockup(vid, titulo, vistas, hace, dur):
    return {'richItemRenderer': {'content': {'lockupViewModel': {
        'contentId': vid, 'contentType': 'LOCKUP_CONTENT_TYPE_VIDEO',
        'contentImage': {'thumbnailViewModel': {'overlays': [{'thumbnailBottomOverlayViewModel': {
            'badges': [{'thumbnailBadgeViewModel': {'text': dur}}]}}]}},
        'metadata': {'lockupMetadataViewModel': {'title': {'content': titulo}, 'metadata': {'contentMetadataViewModel': {
            'metadataRows': [{'metadataParts': [{'text': {'content': 'x'}, 'accessibilityLabel': vistas},
                                                {'text': {'content': hace}, 'accessibilityLabel': hace}]}]}}}}}}}}


PAGINA = '<html><script>var ytInitialData = ' + json.dumps({'contents': [
    lockup('movistar005', 'Movistar se va: la historia que nadie cuenta', '129 visualizaciones', 'hace 1 día', '15:39'),
    lockup('shortHON006', 'Honor FRP en 30 segundos', '1 mil visualizaciones', 'hace 2 días', '0:45'),
    lockup('iphoneBY003', 'Bypass Hello iOS 27 Sin Errores iPhone 11', '39 mil visualizaciones', 'hace 1 mes', '13:10'),
    lockup('xiaomiHY004', 'Eliminar Cuenta Google Xiaomi HyperOS 3', '2,7 mil visualizaciones', 'hace 1 mes', '9:55'),
    lockup('honorPAT002', 'Formatear Honor 400 Lite Patrón y Contraseña', '8,3 mil visualizaciones', 'hace 3 meses', '5:31'),
    lockup('honorFRP001', 'Quitar Cuenta Google Honor 400 con 1 Clic', '24 mil visualizaciones', 'hace 5 meses', '15:32'),
    {'videoRenderer': {'videoId': 'motoFRP0007', 'title': {'runs': [{'text': 'FRP Moto G56 Último Parche'}]},
                       'viewCountText': {'simpleText': '10.234 vistas'}, 'publishedTimeText': {'simpleText': 'hace 7 meses'},
                       'lengthText': {'simpleText': '11:27'}}},
]}) + ';</script></html>'


class Resp:
    def __init__(self, datos):
        self.datos = datos

    def read(self, *a):
        return self.datos


pedidas = []


def abrir(req, timeout=0):  # YouTube simulado
    url = req.full_url if hasattr(req, 'full_url') else req
    pedidas.append(url)
    if url == cr.CANAL:
        return Resp(PAGINA.encode('utf-8'))
    if url.startswith('https://i.ytimg.com/vi/'):
        vid, nombre = url.split('/')[-2:]
        if vid == 'honorPAT002' and nombre in ('maxresdefault.jpg', 'hq720.jpg'):  # sin la grande: la 4:3 con franjas
            raise urllib.error.HTTPError(url, 404, 'Not Found', {}, None)
        return Resp(jpg(640, 480) if vid == 'honorPAT002' else jpg(1280, 720, (20 + len(pedidas) % 200, 80, 160)))
    raise AssertionError(f'pedido a {url}: no debería salir de YouTube')


def partes(req):
    """Los campos del multipart que la app manda a OpenAI: {'model': …, 'prompt': …, 'image[]': [bytes, …]}."""
    limite = req.get_header('Content-type').split('boundary=')[1].encode()
    out = {'image[]': []}
    for p in req.data.split(b'--' + limite)[1:-1]:
        cab, _, cuerpo = p.strip(b'\r\n').partition(b'\r\n\r\n')
        nombre = cab.split(b'name="')[1].split(b'"')[0].decode()
        if nombre == 'image[]':
            out['image[]'].append(cuerpo)
        else:
            out[nombre] = cuerpo.decode('utf-8')
    return out


with tempfile.TemporaryDirectory() as tmp:
    cr.CARPETA = os.path.join(tmp, 'canal_referencia')
    cr.VIDEOS_CANAL = os.path.join(tmp, 'no_hay_videos.json')
    cr._de_oauth = lambda: None  # sin YouTube conectado: sale de la página pública

    # 1) la página pública: 7 videos, con vistas, duración y fecha
    vs = cr.leer_pagina(PAGINA)
    ok([v['id'] for v in vs][:2] == ['movistar005', 'shortHON006'] and len(vs) == 7, f'página: {[v["id"] for v in vs]}')
    moto = next((v for v in vs if v['id'] == 'motoFRP0007'), {})
    ok(moto.get('vistas') == 10234 and moto.get('segundos') == 687, f'diseño viejo de YouTube: {moto}')
    ok(next(v for v in vs if v['id'] == 'iphoneBY003')['vistas'] == 39000, 'las vistas «39 mil» deberían ser 39000')

    # 2) bajar: 4 recientes + 2 más vistas, sin el Short; la 4:3 queda en 16:9
    r = cr.bajar(recientes=4, vistas=2, abrir=abrir, avisar=lambda *a: None)
    ind = cr.leer_indice()
    ids = {v['id'] for v in ind['videos']}
    ok(r['total'] == 5 and ids == {'movistar005', 'iphoneBY003', 'xiaomiHY004', 'honorPAT002', 'honorFRP001'},
       f'deberían quedar 4 recientes + la más vista que falta: {sorted(ids)}')
    ok('shortHON006' not in ids and not any('shortHON006' in u for u in pedidas), 'los Shorts no se bajan')
    ok(all(u == cr.CANAL or u.startswith('https://i.ytimg.com/vi/') for u in pedidas), f'solo YouTube público: {pedidas}')
    for v in ind['videos']:
        im = cv2.imread(os.path.join(cr.CARPETA, v['archivo']))
        ok(im is not None and abs(im.shape[1] / im.shape[0] - 16 / 9) < 0.02, f'{v["id"]} debería quedar en 16:9: {None if im is None else im.shape}')
    frp = next(v for v in ind['videos'] if v['id'] == 'honorFRP001')
    ok(frp['mas_vista'] and not frp['reciente'] and frp['marca'] == 'HONOR' and 'frp' in frp['servicios'], f'índice: {frp}')
    ok(os.path.abspath(cr.CARPETA).startswith(os.path.abspath(tmp)), 'la caché de la prueba queda en la carpeta temporal')

    # 3) elegir: las más parecidas (Honor + FRP primero), fijadas primero, quitadas nunca
    e = [v['id'] for v in cr.elegir('HONOR', 'HONOR SIN CUENTA GOOGLE')]
    ok(len(e) == 3 and e[0] == 'honorFRP001' and 'honorPAT002' in e, f'para un Honor FRP: {e}')
    e = [v['id'] for v in cr.elegir('IPHONE', 'BYPASS iOS 27 SIN ERRORES')]
    ok(e[0] == 'iphoneBY003', f'para un iPhone: {e}')
    cr.marcar('movistar005', fijada=True)
    cr.marcar('honorFRP001', quitada=True)
    e = [v['id'] for v in cr.elegir('HONOR', 'HONOR SIN CUENTA GOOGLE')]
    ok(e[0] == 'movistar005' and 'honorFRP001' not in e, f'la fijada primero y la quitada nunca: {e}')
    cr.bajar(recientes=4, vistas=2, abrir=abrir, avisar=lambda *a: None)
    ind = cr.leer_indice()
    ok(ind['fijadas'] == ['movistar005'] and ind['quitadas'] == ['honorFRP001'], f'volver a bajar no borra lo marcado: {ind}')
    cr.marcar('movistar005', fijada=False)
    cr.marcar('honorFRP001', quitada=False)
    try:
        cr.marcar('../../x', fijada=True)
        ok(False, 'un id raro debería rechazarse')
    except ValueError:
        pass

    # 4) el pedido a GPT (simulado): modelo 2.5, calidad baja, fotos + logos + canal como imágenes, la fórmula en el prompt
    d = os.path.join(tmp, 'HONOR 400 FRP')
    os.makedirs(d)
    for k, color in (('antes', (10, 10, 120)), ('despues', (10, 120, 10))):
        mini.guardar_img(os.path.join(d, f'foto_miniatura_{k}.jpg'), np.full((1080, 1920, 3), color, np.uint8))
    logos = os.path.join(tmp, 'logos')
    os.makedirs(logos)
    for f in ('google.png', 'honor.png', 'wa.png', 'web.png'):
        cv2.imwrite(os.path.join(logos, f), np.full((200, 200, 3), 255, np.uint8))
    json.dump({'logos': [{'nombre': 'Google', 'archivo': 'google.png'}, {'nombre': 'Soporte WhatsApp', 'archivo': 'wa.png', 'tarjeta': True},
                         {'nombre': 'gsmprime.co', 'archivo': 'web.png'}]}, open(os.path.join(logos, 'logos.json'), 'w'))
    mini.LOGOS_DIR = logos
    mini.ESTILO = os.path.join(tmp, 'sin_referencias_viejas')
    mini.necesita_pc = lambda marca: True
    mini.clave_openai = lambda: 'sk-prueba'
    AJ = {}
    mini.ajustes = lambda: AJ
    pedidos = []
    salida = base64.b64encode(cv2.imencode('.png', np.full((864, 1536, 3), 30, np.uint8))[1].tobytes()).decode()
    mini.pedir_imagen = lambda req: (pedidos.append(req), {'data': [{'b64_json': salida}]})[1]

    def no_dibujar(*a, **k):
        raise AssertionError('la app no debe dibujar nada encima de la miniatura')
    for f in ('componer_mixta', 'titulo_estilizado', 'sticker', 'sello', 'pildora', 'cinta', 'titulo_gpt', 'etiqueta_gpt',
              'texto_italico', 'componer'):
        setattr(mini, f, no_dibujar)
    arg = lambda **k: argparse.Namespace(**{**dict(gpt=True, texto='HONOR|SIN CUENTA GOOGLE', fondo='gpt', mixta=False, titulo='todos',
                                                   titulo_gpt=False, esquina_izq='PASO A PASO', esquina_der='NUEVA UPDATE|EXPLICADO PASO A PASO',
                                                   calidad='baja', idiomas='es', cara=False, refs_canal=''), **k})
    try:
        mini.con_fotos(d, arg())
    except AssertionError as e:
        ok(False, str(e))
    ok(len(pedidos) == 1, f'el borrador en español: 1 imagen, no {len(pedidos)}')
    if pedidos:
        p = partes(pedidos[0])
        ok(pedidos[0].full_url == 'https://api.openai.com/v1/images/edits', 'debería ser la edición con varias imágenes')
        ok(p.get('model') == 'gpt-image-2.5-flare' and p.get('quality') == 'low' and p.get('size') == '1536x864',
           f"borrador: modelo 2.5 en calidad baja: {p.get('model')} {p.get('quality')} {p.get('size')}")
        usadas = [v['id'] for v in cr.elegir('HONOR', 'HONOR SIN CUENTA GOOGLE')]
        canal = [open(os.path.join(cr.CARPETA, f'{i}.jpg'), 'rb').read() for i in usadas]
        fotos = [open(os.path.join(d, f'foto_miniatura_{k}.jpg'), 'rb').read() for k in ('antes', 'despues')]
        logo = [open(os.path.join(logos, f), 'rb').read() for f in ('google.png', 'honor.png')]
        ok(p['image[]'] == fotos + logo + canal, f'imágenes: sus 2 fotos, el logo de Google y el de Honor, y las {len(canal)} '
           f'del canal ({len(p["image[]"])} en total)')
        pr = p.get('prompt', '')
        for regla in ('ABAJO', 'UNA sola línea', 'ENTRE las palabras', 'esquina de abajo a la derecha', 'ARRIBA', 'esquinas',
                      'inclinadas', 'neón azul', 'azul marino oscuro', 'NUNCA un fondo claro', 'páginas web', '.com, .co',
                      'SOLO como referencia de ESTILO', 'NO copies sus textos, ni sus teléfonos', 'TODO el texto lo escribes tú',
                      '«HONOR» en blanco, el logo de Google y «SIN CUENTA GOOGLE» en amarillo-naranja', '«PASO A PASO»',
                      'NUEVA UPDATE / EXPLICADO PASO A PASO', 'nunca escribas «SIN PC»', 'Máximo 2 manos', '320×180',
                      'Nada de letras 3D doradas'):
            ok(regla in pr, f'al prompt le falta: «{regla}»')
        ok('mascota' not in pr.lower() and 'claro y apenas desenfocado' not in pr, 'la fórmula vieja (mascota, fondo claro) ya no va')
    hechas = json.load(open(os.path.join(d, 'miniatura_fotos.json'), encoding='utf-8'))['miniaturas']
    h = hechas[0] if hechas else {}
    im = mini.leer_img(os.path.join(d, h.get('archivo', 'x')))
    ok(h.get('calidad') == 'baja' and h.get('idioma') == 'es' and h.get('modelo') == 'gpt-image-2.5-flare' and
       len(h.get('refs_canal') or []) == 3 and abs(h.get('costo_usd', 0) - 0.02) < 1e-9, f'lo anotado del borrador: {h}')
    ok(im is not None and im.shape[:2] == (720, 1280), 'la miniatura sale en 1280×720')

    # 5) la final aprobada: calidad media, las MISMAS referencias del canal y las fotos originales (no la imagen de GPT)
    pedidos.clear()
    mini.con_fotos(d, arg(calidad='media', idiomas='es,en,pt', refs_canal=','.join(h.get('refs_canal') or [])))
    ok(len(pedidos) == 3 and all(partes(x).get('quality') == 'medium' for x in pedidos), 'la final: 3 idiomas en calidad media')
    if pedidos and hechas:
        p = partes(pedidos[0])
        borrador = open(os.path.join(d, h['archivo']), 'rb').read()
        ok(p['image[]'][:2] == fotos and borrador not in p['image[]'], 'la final parte de sus fotos, no del borrador de GPT')
        ok(p['image[]'][-3:] == [open(os.path.join(cr.CARPETA, f'{i}.jpg'), 'rb').read() for i in h['refs_canal']],
           'la final usa las mismas miniaturas de estilo que el borrador')
        ok('in inglés' not in partes(pedidos[1])['prompt'] and 'en inglés' in partes(pedidos[1])['prompt'], 'el segundo, en inglés')
    todas = json.load(open(os.path.join(d, 'miniatura_fotos.json'), encoding='utf-8'))['miniaturas']
    ok(len(todas) == 4 and todas[-1]['archivo'] == h.get('archivo'), f'el borrador sigue en la lista después de la final: {len(todas)}')

    # 6) el modelo: el de ajustes si es de la familia 2.5 o más nuevo; si no, gpt-image-2.5-flare
    for puesto, esperado in (('gpt-image-2.5-nova', 'gpt-image-2.5-nova'), ('gpt-image-1', 'gpt-image-2.5-flare'), ('', 'gpt-image-2.5-flare')):
        AJ['modelo_imagen'] = puesto
        pedidos.clear()
        mini.imagen_gpt('x', [], calidad='alta')
        ok(partes(pedidos[0]).get('model') == esperado and partes(pedidos[0]).get('quality') == 'high', f'modelo con «{puesto}»')
    AJ.clear()

    # 7) una web o «SIN PC» frenan antes de gastar
    for texto in ('HONOR|GSMPRIME.CO', 'HONOR|SIN PC'):
        pedidos.clear()
        try:
            mini.con_fotos(d, arg(texto=texto))
            ok(False, f'«{texto}» debería frenar')
        except SystemExit as e:
            ok('No se gastó nada' in str(e), f'el aviso de «{texto}»: {e}')
        ok(not pedidos, f'con «{texto}» no se pidió ninguna imagen')

    # 8) sin miniaturas del canal guardadas: las referencias de siempre (mis_conocimientos/miniaturas/referencias)
    os.makedirs(mini.ESTILO)
    cv2.imwrite(os.path.join(mini.ESTILO, 'honor_vieja.jpg'), np.zeros((72, 128, 3), np.uint8))
    cr.CARPETA = os.path.join(tmp, 'canal_vacio')
    pedidos.clear()
    mini.miniaturas_gpt(d, [os.path.join(d, 'foto_miniatura_antes.jpg')], ['HONOR', 'SIN CUENTA GOOGLE'], os.path.join(d, 'm'), 'HONOR', idiomas=('es',))
    ok(partes(pedidos[0])['image[]'][-1] == open(os.path.join(mini.ESTILO, 'honor_vieja.jpg'), 'rb').read(), 'sin caché: las de siempre')
    cr.CARPETA = os.path.join(tmp, 'canal_referencia')

    # 9) «🖼 Miniatura» (mejoras.comandos): la fórmula del canal por defecto; la mixta solo si se pide
    c = mejoras.comandos('m_miniatura_fotos', d, {'confirmo': 'SI', 'texto': 'HONOR|SIN CUENTA GOOGLE', 'fondo': 'gpt', 'calidad': 'media',
                                                  'idiomas': ['es'], 'refs_canal': ['honorFRP001', '../../x']}, 'py', 'aj.json')[0]
    ok('--mixta' not in c and c[c.index('--calidad') + 1] == 'media' and c[c.index('--idiomas') + 1] == 'es'
       and '--refs-canal=honorFRP001' in c, f'comando de la final: {c}')
    c = mejoras.comandos('m_miniatura_fotos', d, {'confirmo': 'SI'}, 'py', 'aj.json')[0]
    ok('--mixta' not in c and c[c.index('--calidad') + 1] == 'baja' and c[c.index('--esquina-izq') + 1] == 'PASO A PASO', f'por defecto: {c}')
    c = mejoras.comandos('m_miniatura_fotos', d, {'confirmo': 'SI', 'modo': 'mixta', 'titulo': 'placa'}, 'py', 'aj.json')[0]
    ok('--mixta' in c and '--calidad' not in c, f'la mixta sigue si se pide: {c}')

    # 10) las rutas de la página
    class H:
        def __init__(self, cuerpo=b''):
            self.rfile, self.r = io.BytesIO(cuerpo), None

        def responder(self, x, *a, **k):
            self.r = ('ok', x)

        def error(self, msg, codigo=400):
            self.r = ('error', codigo, msg)

        def servir(self, f, *a):
            self.r = ('archivo', f)
    h = H()
    mejoras.get(h, '/api/mejoras/canal_ref', {'texto': 'HONOR SIN CUENTA GOOGLE'}, d)
    ok(h.r[0] == 'ok' and len(h.r[1]['videos']) == 5 and h.r[1]['usar'][0] == 'honorFRP001' and h.r[1]['marca'] == 'HONOR', f'estado: {h.r}')
    h = H()
    mejoras.get(h, '/api/mejoras/canal_ref_img', {'id': '../../../etc'}, d)
    ok(h.r[0] == 'error', 'una imagen fuera de la caché se rechaza')
    h = H()
    mejoras.get(h, '/api/mejoras/canal_ref_img', {'id': 'honorFRP001'}, d)
    ok(h.r == ('archivo', os.path.join(cr.CARPETA, 'honorFRP001.jpg')), f'imagen: {h.r}')
    cuerpo = json.dumps({'id': 'xiaomiHY004', 'fijada': True, 'texto': 'HONOR SIN CUENTA GOOGLE'}).encode()
    h = H(cuerpo)
    mejoras.post(h, '/api/mejoras/canal_ref_marcar', {}, len(cuerpo), d)
    ok(h.r[0] == 'ok' and h.r[1]['usar'][0] == 'xiaomiHY004', f'📌 desde la página: {h.r}')

print('\n'.join(fallos) or 'ok: miniaturas con el estilo del canal')
sys.exit(1 if fallos else 0)
