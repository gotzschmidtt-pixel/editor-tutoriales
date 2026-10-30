"""«🎛 Audio e imagen»: la página que junta las mejoras de audio e imagen (app/mejoras.html) y sus pasos.

La app (app/app.py) solo se engancha en tres lugares: agrega PASOS a los suyos, pide aquí los comandos de esos pasos y
pasa las rutas /api/mejoras/... a get() y post(). Así los módulos nuevos no tocan el resto de la app.

  🗣 Pronunciación       voz/pronunciacion.py      (lista global en mis_conocimientos/pronunciacion.json)
  😀 Voz con emoción     voz/voz.py                ("emocion" de cada bloque del guion)
  🔊 Efectos de sonido   sonidos/sonidos.py        (los mezcla «Poner la voz» y el tráiler)
  🎙 Limpiar voz         limpieza/limpiar_voz.py
  🖱 Zoom en la PC       zoom_pc/zoom_pc.py
  ✨ Mejorar imagen      mejorar/mejorar.py        (Real-ESRGAN en las pausas quietas y la miniatura)
  🎨 Color parejo        color/color.py
  📱 Pantalla derecha    pantalla/enderezar.py
  📲 Pantalla grabada    pantalla/sincronizar.py   (scrcpy o QuickTime)
  🔎 Revisar el final    revision/revisar_final.py
  📱 Varios Shorts       short/varios.py
  🖼 Miniatura           miniatura/miniatura.py
  ⚖ Avisos de cuidado    avisos/avisos_legales.py
"""
import json, os, re, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'voz'))
sys.path.insert(0, os.path.join(RAIZ, 'sonidos'))
sys.path.insert(0, os.path.join(RAIZ, 'avisos'))
import pronunciacion  # noqa: E402
import sonidos  # noqa: E402
import avisos_legales  # noqa: E402

PASOS = [
    {'id': 'm_limpiar', 'nombre': 'Limpiar la voz grabada', 'necesita': [], 'produce': '', 'oculto': True},
    {'id': 'm_zoom', 'nombre': 'Zoom automático en la grabación de la PC', 'necesita': [], 'produce': '', 'oculto': True},
    {'id': 'm_color', 'nombre': 'Color parejo y tomas oscuras', 'necesita': ['original.mp4'], 'produce': '', 'oculto': True},
    {'id': 'm_enderezar', 'nombre': 'Enderezar la pantalla del celular', 'necesita': ['original.mp4'], 'produce': 'pantalla_enderezada.mp4', 'oculto': True},
    {'id': 'm_scrcpy', 'nombre': 'Poner la pantalla grabada del celular', 'necesita': ['original.mp4', 'pantalla_grabada.mp4'],
     'produce': 'pantalla_celular.mp4', 'oculto': True},
    {'id': 'm_revisar', 'nombre': 'Revisar el video terminado', 'necesita': [], 'produce': 'revision_final.json', 'oculto': True},
    {'id': 'm_shorts', 'nombre': 'Varios Shorts', 'necesita': ['original.mp4', 'guion.json'], 'produce': 'shorts.json', 'oculto': True},
    {'id': 'm_miniatura', 'nombre': 'Miniatura automática', 'necesita': ['original.mp4'], 'produce': 'miniatura.json', 'oculto': True},
    {'id': 'm_avisos', 'nombre': 'Avisos de cuidado', 'necesita': ['guion.json'], 'produce': '', 'oculto': True},
    {'id': 'm_sonidos', 'nombre': 'Crear los efectos de sonido', 'necesita': [], 'produce': '', 'oculto': True},
    {'id': 'm_esrgan', 'nombre': 'Bajar Real-ESRGAN y probarlo', 'necesita': [], 'produce': '', 'oculto': True},
]
IDS = {p['id'] for p in PASOS}
USAN_ELEVEN = {'m_sonidos'}  # solo con «Crear con ElevenLabs»; los demás no gastan
EDITABLES = {'sonidos': bool, 'sonidos_volumen': float, 'sonidos_tipos': list, 'emocion_voz': bool, 'mejorar_imagen': bool}
ARCHIVOS_ZOOM = ('material.mp4', 'original.mp4')
RESPALDOS = {'zoom': '_sin_zoom', 'color': '_sin_color', 'limpiar': '_sin_limpiar'}
SUBIDAS = {'pantalla': 'pantalla_grabada.mp4'}


def m(*p):
    return os.path.join(RAIZ, *p)


def comandos(paso, d, op, py, ajustes):
    if paso == 'm_limpiar':
        que = op.get('archivo', 'original.mp4')
        motor = op.get('motor') if op.get('motor') in ('pc', 'ffmpeg', 'eleven') else 'pc'
        entrada = 'testimonios' if que == 'testimonios' else que if que in ('original.mp4', 'material.mp4') else None
        if not entrada:
            raise ValueError('archivo no válido')
        return [[py, m('limpieza', 'limpiar_voz.py'), '--entrada', entrada, '--motor', motor] + (['--deshacer'] if op.get('deshacer') else [])]
    if paso == 'm_zoom':
        f = op.get('archivo') if op.get('archivo') in ARCHIVOS_ZOOM else 'material.mp4'
        return [[py, m('zoom_pc', 'zoom_pc.py'), '--entrada', f, '--max', f"{min(max(float(op.get('max') or 2.2), 1.2), 3):g}"]
                + (['--deshacer'] if op.get('deshacer') else [])]
    if paso == 'm_color':
        return [[py, m('color', 'color.py'), '--entrada', 'original.mp4', '--fuerza', f"{min(max(float(op.get('fuerza') or 0.7), 0), 1):g}"]
                + (['--deshacer'] if op.get('deshacer') else [])]
    if paso == 'm_enderezar':
        return [[py, m('pantalla', 'enderezar.py'), '--proyecto', '.'] + (['--insertos'] if op.get('insertos', True) else [])]
    if paso == 'm_scrcpy':
        c = [py, m('pantalla', 'sincronizar.py'), '--proyecto', '.']
        if op.get('desfase') not in (None, ''):
            c += ['--desfase', f"{float(op['desfase']):g}"]
        return [c]
    if paso == 'm_revisar':
        return [[py, m('revision', 'revisar_final.py'), '--proyecto', '.', '--ajustes', ajustes] + ([] if op.get('ia', True) else ['--sin-ia'])]
    if paso == 'm_shorts':
        c = [py, m('short', 'varios.py'), '--proyecto', '.', '--cantidad', str(min(max(int(op.get('cantidad') or 3), 2), 5)),
             '--duracion', f"{min(max(float(op.get('duracion') or 45), 15), 180):g}"]
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(op.get('desde') or '')):
            c += ['--desde', op['desde']]
        return [c]
    if paso == 'm_miniatura':
        texto = str(op.get('texto') or '').strip()[:80]
        return [[py, m('miniatura', 'miniatura.py'), '--proyecto', '.'] + (['--texto', texto] if texto else [])
                + (['--gpt'] if op.get('gpt') and str(op.get('confirmo') or '').upper() in ('SI', 'SÍ') else [])
                + (['--variantes'] if op.get('variantes') and op.get('gpt') else [])
                + (['--short'] if op.get('short') and str(op.get('confirmo') or '').upper() in ('SI', 'SÍ') else [])]
    if paso == 'm_avisos':
        return [[py, m('avisos', 'avisos_legales.py'), '--proyecto', '.']]
    if paso == 'm_sonidos':
        c = [py, m('sonidos', 'sonidos.py'), '--generar', 'eleven' if op.get('motor') == 'eleven' else 'pc']
        if op.get('solo') in sonidos.SONIDOS:
            c += ['--solo', op['solo']]
        return [c]
    if paso == 'm_esrgan':
        return [[py, m('mejorar', 'mejorar.py'), '--bajar']]
    raise ValueError(paso)


def _leer(d, f, defecto=None):
    try:
        return json.load(open(os.path.join(d, f), encoding='utf-8'))
    except (OSError, ValueError):
        return defecto


def _escribir(f, datos):
    with open(f + '.tmp', 'w', encoding='utf-8') as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    os.replace(f + '.tmp', f)


def _fecha(d, f):
    try:
        return int(os.path.getmtime(os.path.join(d, f)))
    except OSError:
        return None


def afectados(d):
    """Bloques cuya voz ya hecha dice alguna palabra del diccionario pero se hizo sin él (o con otra forma de decirla)."""
    g = _leer(d, 'guion.json', {}) or {}
    out = []
    for b in g.get('bloques', []):
        pron = pronunciacion.firma_bloque(b.get('texto'))
        if not pron:
            continue
        meta = _leer(os.path.join(d, 'voz'), f"{b.get('id')}.voz.json")
        if os.path.exists(os.path.join(d, 'voz', f"{b.get('id')}.mp3")) and (not isinstance(meta, dict) or meta.get('pron') != pron):
            out.append({'id': b['id'], 'letras': len(str(b.get('texto') or '')), 'palabras': [p.split('=')[0] for p in pron]})
    return out


def estado(d):
    e = _leer(d, 'edicion.json', {}) or {}
    g = _leer(d, 'guion.json', {}) or {}
    arch = {}
    for f in ['original.mp4', 'material.mp4', 'pantalla_grabada.mp4', 'pantalla_enderezada.mp4', 'pantalla_celular.mp4', 'FINAL.mp4',
              'original_sin_zoom.mp4', 'material_sin_zoom.mp4', 'original_sin_color.mp4', 'original_sin_limpiar.mp4',
              'material_sin_limpiar.mp4', 'revision_final.json', 'shorts.json', 'miniatura.json', 'zoom_pc.json'] + \
             [f'SHORT_{k}.mp4' for k in range(1, 6)] + [f'miniatura_{k}.jpg' for k in range(1, 4)]:
        if os.path.exists(os.path.join(d, f)):
            arch[f] = _fecha(d, f)
    testi = os.path.join(d, 'testimonios')
    biblio = {}
    for n, (para, _, _, _) in sonidos.SONIDOS.items():
        f = sonidos.archivo(n)
        biblio[n] = {'para': para, 'hay': bool(f), 'de': ('ElevenLabs o tuyo' if f and f.endswith('.mp3') else 'hecho en tu PC') if f else None}
    plan = []
    try:
        if g:
            plan = sonidos.plan(d)
    except Exception:
        plan = []
    et = _leer(d, 'etiquetas.json', []) or []
    puestas = {x.get('bloque') for x in (et.get('etiquetas', []) if isinstance(et, dict) else et) if x.get('origen') == 'aviso_legal'}
    legales = [{'bloque': b['id'], 'tema': t, 'frase': fr, 'puesta': b['id'] in puestas} for t, b, fr in avisos_legales.revisar(g)] if g else []
    return {
        'edicion': {k: e.get(k) for k in EDITABLES},
        'pronunciacion': pronunciacion.reglas(),
        'afectados': afectados(d) if g else [],
        'bloques': [{'id': b.get('id'), 'texto': str(b.get('texto') or '')[:140], 'emocion': b.get('emocion') or ''}
                    for b in g.get('bloques', []) if str(b.get('texto') or '').strip()],
        'sonidos': biblio, 'plan_sonidos': plan[:200],
        'archivos': arch,
        'testimonios': sorted(f for f in os.listdir(testi) if f.lower().endswith(('.mp4', '.mov')) and '_sin_limpiar' not in f) if os.path.isdir(testi) else [],
        'revision': _leer(d, 'revision_final.json'), 'shorts': _leer(d, 'shorts.json'), 'miniaturas': _leer(d, 'miniatura.json'),
        'zoom': _leer(d, 'zoom_pc.json'), 'pantalla': _leer(d, 'pantalla_celular.json'),
        'legales': legales,
    }


def get(h, ruta, q, d):
    if ruta == '/api/mejoras/estado':
        return h.responder(estado(d))
    if ruta == '/api/mejoras/sonido':  # para escuchar cada sonido de la biblioteca
        f = sonidos.archivo(q.get('n', '')) if q.get('n') in sonidos.SONIDOS else None
        return h.servir(f) if f else h.error('todavía no está hecho', 404)
    return h.error('no conozco esa ruta', 404)


def post(h, ruta, q, largo, d):
    if ruta == '/api/mejoras/subir':  # la grabación de pantalla del celular (scrcpy o QuickTime)
        nombre = SUBIDAS.get(q.get('tipo'))
        if not nombre:
            return h.error('tipo de archivo no válido')
        destino = os.path.join(d, nombre)
        resto = largo
        with open(destino + '.parcial', 'wb') as fh:
            while resto > 0:
                trozo = h.rfile.read(min(1 << 20, resto))
                if not trozo:
                    break
                fh.write(trozo)
                resto -= len(trozo)
        if resto > 0:
            os.remove(destino + '.parcial')
            return h.error('La subida se cortó antes de terminar. Vuelve a subir el archivo.')
        os.replace(destino + '.parcial', destino)
        return h.responder({'ok': True})
    datos = json.loads(h.rfile.read(largo) or b'{}')
    if ruta == '/api/mejoras/pronunciacion':
        actual = pronunciacion.leer()
        actual['reglas'] = pronunciacion.limpiar(datos.get('reglas'))
        pronunciacion.guardar(actual)  # se sube a ElevenLabs la próxima vez que se genere voz (no gasta)
        return h.responder({'ok': True, 'reglas': actual['reglas'], 'afectados': afectados(d) if os.path.isdir(d) else []})
    if ruta == '/api/mejoras/rehacer_pronunciacion':
        # las voces de esos bloques quedan como «viejas»: «Generar voz» las rehace (y el costo se ve antes, como siempre)
        n = 0
        for x in afectados(d):
            f = os.path.join(d, 'voz', f"{x['id']}.voz.json")
            meta = _leer(os.path.join(d, 'voz'), f"{x['id']}.voz.json", {}) or {}
            meta['pron'] = ['(antes del diccionario)']
            _escribir(f, meta)
            n += 1
        return h.responder({'ok': True, 'bloques': n})
    if ruta == '/api/mejoras/edicion':
        f = os.path.join(d, 'edicion.json')
        e = _leer(d, 'edicion.json', {}) or {}
        for k, tipo in EDITABLES.items():
            if k not in datos:
                continue
            v = datos[k]
            if tipo is bool and isinstance(v, bool):
                e[k] = v
            elif tipo is float:
                e[k] = min(max(float(v), 0.0), 2.0)
            elif tipo is list and isinstance(v, list):
                e[k] = [x for x in v if x in sonidos.SONIDOS]
        _escribir(f, e)
        return h.responder({'ok': True})
    if ruta == '/api/mejoras/emocion':  # la emoción de cada bloque (vacío = como siempre)
        f = os.path.join(d, 'guion.json')
        g = _leer(d, 'guion.json')
        if not g:
            return h.error('Todavía no hay guion.')
        cambios = datos.get('emociones') or {}
        for b in g.get('bloques', []):
            if b.get('id') in cambios:
                v = re.sub(r'[\[\]]', '', str(cambios[b['id']] or '')).strip()[:30]
                meta = os.path.join(d, 'voz', f"{b['id']}.voz.json")
                if v != (b.get('emocion') or '') and os.path.exists(meta):  # la cambiaste vos: esa voz se rehace con «Generar voz»
                    _escribir(meta, dict(_leer(os.path.join(d, 'voz'), f"{b['id']}.voz.json", {}) or {}, rehacer_emocion=True))
                if v:
                    b['emocion'] = v
                else:
                    b.pop('emocion', None)
        _escribir(f, g)
        return h.responder({'ok': True})
    if ruta == '/api/mejoras/sonido_quitar':  # vuelve al sonido hecho en la PC
        n = datos.get('nombre')
        if n not in sonidos.SONIDOS:
            return h.error('sonido no válido')
        for ext in ('.mp3', '.wav'):
            f = os.path.join(sonidos.BIBLIOTECA, n + ext)
            if os.path.exists(f):
                os.remove(f)
        return h.responder({'ok': True})
    return h.error('no conozco esa ruta', 404)
