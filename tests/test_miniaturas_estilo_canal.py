"""Prueba del estilo de su canal en lo que la app le pide a GPT (fabian, 03/11/2026, con dos capturas: «mira la primera imagen,
fondos negros, tipo de fuente, estilo» y la imagen 2, hecha con el pedido de ese día, «es algo tosca»). SIN internet y SIN
gastar: la IA de imágenes va simulada y no se genera ninguna imagen.
- el pedido trae lo nuevo (fondo NEGRO, el teléfono en la mano con guante, letras blanco + amarillo sin cromado (con el degradé suave de las suyas), la frase de abajo
  como lo más grande, las etiquetas de arriba más chicas) y no trae lo que hizo tosca la imagen 2 (rayos y destellos,
  resplandor cian, amarillo-naranja con degradado, todo «GRANDE»);
- sigue todo lo de la memoria de gustos (cara latina ficticia natural, buzo blanco sin logos, sus fotos originales, máximo 2
  manos, sin webs, ANTES = DESPUÉS de tamaño, nada abajo a la derecha, sin letras 3D doradas, los textos los hace GPT,
  borrador en baja y final en media, «SIN PC» nunca en Honor);
- la guía (sección «Estilo del canal para GPT» de ESTILO_MINIATURAS.md) va al pedido, solo sus partes «Para GPT»;
- referencias_estilo elige por marca y por vistas por día con referencias/indice.json, después por servicio, solo de fondo
  oscuro, la HD si está, nunca las capturas SI_/NO_ ni las quitadas;
- canal_referencia.elegir deja fuera las de fondo claro (salvo las fijadas) y ordena por vistas por día;
- armar_referencias arma el índice desde el export del canal (con sus barras invertidas sueltas) sin borrar nada;
- miniaturas_gpt completa con las de referencias/ cuando del canal hay menos de 2 oscuras;
- los pedidos de título y etiquetas por GPT piden letras sin cromado (el «metal» queda solo si se pide).
Uso: python tests/test_miniaturas_estilo_canal.py   (sale con 1 si algo falla)
"""
import inspect, json, os, sys, tempfile, time, urllib.request
import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'miniatura'))
import canal_referencia as cr  # noqa: E402
import miniatura as mini  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def sin_red(*a, **k):  # nada de esta prueba sale a internet ni gasta
    raise AssertionError('la prueba intentó usar la red de verdad')


urllib.request.urlopen = sin_red
mini.pedir_imagen = sin_red


def imagen(f, color=(60, 25, 10), w=320, h=180, centro=None):
    """Una miniatura falsa: fondo del color pedido (BGR) y, si se pide, un «teléfono» claro al centro."""
    img = np.full((h, w, 3), color, np.uint8)
    if centro is not None:
        img[h // 5:h * 4 // 5, w // 3:w * 2 // 3] = centro
    os.makedirs(os.path.dirname(f), exist_ok=True)
    cv2.imwrite(f, img)
    return f


OSCURO, CLARO = (60, 25, 10), (225, 230, 235)

with tempfile.TemporaryDirectory() as tmp:
    mini.necesita_pc = lambda marca, texto='': marca.upper() != 'XIAOMI'  # (marca, texto) como reglas_titulo.necesita_pc
    guia_md = os.path.join(tmp, 'ESTILO_MINIATURAS.md')
    open(guia_md, 'w', encoding='utf-8').write(
        '# Estilo\n\nintro\n\n## Estilo del canal para GPT (fabian, 03/11/2026)\n\nfabian dijo cosas.\n\n'
        '### Para GPT: así son sus miniaturas\n- **Fondo:** negro con viñeta.\n- Letra: condensada en `cursiva`.\n\n'
        '### Para GPT: lo que NO (lo que la hizo tosca)\n- Túnel de rayos láser.\n\n'
        '### Por qué salió tosca (para la app)\n- SECRETO_DE_LA_APP: esto no va a GPT.\n\n'
        '## Lo que se repite en todas\n- OTRA_SECCION\n')
    mini.GUIA_ESTILO = guia_md

    # 1) el pedido: lo nuevo sí, lo que hizo tosca la imagen 2 no
    logos = [('Google', 'g.png'), ('honor', 'h.png')]
    pedido = lambda **k: mini.prompt_canal(**{**dict(lineas=['HONOR', 'SIN CUENTA GOOGLE'], idioma='es', n_fotos=2, logos=logos,
                                                    n_estilo=3, esquinas=('PASO A PASO', 'NUEVA UPDATE|EXPLICADO PASO A PASO'),
                                                    marca='HONOR'), **k})
    pr = pedido()
    for nuevo in ('fondo NEGRO', 'NEGRO o azul noche casi negro', 'viñeta', 'SOSTENIDO por una mano con guante de nitrilo azul',
                  'Nunca teléfonos flotando', 'relleno de color pleno', 'degradé suave', 'Sin cromado (nada de franja de reflejo metálico), sin bisel',
                  'NO copies tampoco sus sellos, insignias, cintas ni años', 'ningún sello, insignia ni año que este pedido', 'Anton, Bebas Neue o Impact', 'en cursiva',
                  'Es lo MÁS GRANDE', 'MÁS CHICAS que la frase de abajo', '«SIN CUENTA GOOGLE» en amarillo.',
                  'Nada de túnel ni rayos láser', 'piso que refleja', 'Cada texto UNA sola vez', 'números de variante',
                  'la placa Raspberry Pi Pico', 'copia de ellas el fondo negro, el tipo de letra',
                  'no un render 3D de producto'):
        ok(nuevo in pr, f'al pedido le falta lo nuevo: «{nuevo}»')
    for tosco in ('rayos de luz y destellos', 'resplandor cian', 'con degradado', 'amarillo-naranja', 'azul marino',
                  'GRANDE en amarillo', 'MAYÚSCULAS y grande', 'degradados, neón, brillo', 'estelas de luz de neón',
                  'un piso que refleja;', 'claro y apenas desenfocado'):
        ok(tosco not in pr, f'el pedido todavía pide lo que hizo tosca la imagen 2: «{tosco}»')
    # la memoria de gustos (ESTILO_MINIATURAS.md) sigue igual
    for gusto in ('Parte SIEMPRE de SUS fotos', 'Máximo 2 manos', 'nada de páginas web', '.com, .co', 'esquina de abajo a la derecha',
                  'Nada de letras 3D doradas', 'TODO el texto lo escribes tú', 'del mismo tamaño', 'nunca escribas «SIN PC»',
                  'NUNCA un fondo claro', 'SOLO como referencia de ESTILO', 'NO copies sus textos, ni sus teléfonos',
                  'Sin personas: solo las manos con guante', 'ENTRE las palabras', '320×180', 'cinta roja «ANTES» ✖',
                  'verde «DESPUÉS» ✔'):
        ok(gusto in pr, f'se perdió una regla de la memoria: «{gusto}»')
    con_cara = pedido(cara=True)
    ok('hombre latino ficticio' in con_cara and 'buzo blanco liso sin logos' in con_cara and 'expresión natural' in con_cara
       and 'ni pícara' in con_cara, 'con cara: latino ficticio, natural, buzo blanco liso sin logos')
    ok('nunca escribas «SIN PC»' not in pedido(marca='XIAOMI', lineas=['XIAOMI', 'SIN CUENTA MI']), 'Xiaomi Mi Account no usa PC')
    en = pedido(idioma='en')
    ok('«BEFORE» ✖' in en and '«AFTER» ✔' in en and 'en inglés' in en, 'en inglés: BEFORE / AFTER')
    for fondo in ('gpt', 'foto', 'escritorio'):
        p = pedido(fondo=fondo)
        ok('NEGRO' in p and 'NUNCA un fondo claro' in p and 'Nada de túnel' in p, f'el fondo «{fondo}» debería ser negro y sin túnel')
    ok('oscurecido casi a NEGRO' in pedido(fondo='foto') and 'NEGRO o azul noche' not in pedido(fondo='foto'),
       'con su estudio: el real, oscurecido casi a negro')

    # 2) la guía va al pedido: solo sus partes «Para GPT», sin markdown
    g = mini.guia_estilo_gpt()
    ok('Así son sus miniaturas: Fondo: negro con viñeta. Letra: condensada en cursiva.' in g, f'la guía para GPT: {g}')
    ok('Lo que NO (lo que la hizo tosca): Túnel de rayos láser.' in g, f'lo que NO también va: {g}')
    ok('SECRETO_DE_LA_APP' not in g and 'OTRA_SECCION' not in g and '**' not in g and '`' not in g, f'solo las partes para GPT: {g}')
    ok(g in pr and 'no texto para escribir' in pr, 'la guía va dentro del pedido a GPT')
    mini.GUIA_ESTILO = os.path.join(tmp, 'no_hay.md')
    ok(mini.guia_estilo_gpt() == '' and 'fondo NEGRO' in pedido(), 'sin la guía el pedido igual trae lo esencial')
    real = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'ESTILO_MINIATURAS.md')
    if os.path.isfile(real):  # la guía de fabian (si está enlazada): su sección entra entera y sin « » (no son textos a escribir)
        mini.GUIA_ESTILO = real
        g = mini.guia_estilo_gpt()
        ok(g.startswith('Así son sus miniaturas:') and 'Lo que NO' in g and len(g) < 3500 and not g.endswith(' '),
           f'la sección de su guía para GPT ({len(g)} letras): {g[:120]}…')
        ok('«' not in g and not mini.WEB.search(g) and 'SIN PC' not in g.upper() and 'mascota' not in g.lower(),
           'la guía para GPT no trae textos entre « », webs, «SIN PC» ni la mascota')
    mini.GUIA_ESTILO = guia_md

    # 3) los otros pedidos a GPT
    for fondo, txt in mini.FONDOS_MINI.items():
        ok('claro y apenas desenfocado' not in txt and ('nunca claro' in txt or 'NEGRO' in txt), f'FONDOS_MINI «{fondo}»: {txt}')
    ok('NEGRO' in mini.FONDOS_MINI['gpt'] and 'nada de túnel' in mini.FONDOS_MINI['gpt'] and
       'estelas de luz de neón celeste y violeta' not in mini.FONDOS_MINI['gpt'], 'la escena de la mixta: fondo negro, sin túnel')
    vistos = []
    mini.imagen_gpt = lambda prompt, refs, **k: (vistos.append((prompt, list(refs))), np.zeros((40, 80, 4), np.uint8))[1]
    mini.TITULOS_REF = os.path.join(tmp, 'titulos')
    mini.titulo_gpt(['HONOR', 'SIN CUENTA GOOGLE'], 'placa_negra', os.path.join(tmp, 't.png'))
    p = vistos[-1][0]
    ok('relleno de color pleno' in p and 'sin cromado' in p and 'plateado' not in p and 'dorado' not in p and 'condensada' in p,
       f'el título de GPT: letras planas, condensadas, blanco + amarillo: {p}')
    mini.titulo_gpt(['HONOR', 'SIN CUENTA GOOGLE'], 'metal', os.path.join(tmp, 't2.png'))
    ok('dorado' in vistos[-1][0], 'el «metal» solo si se pide, como antes')
    mini.ETIQUETAS_DIR = os.path.join(tmp, 'etiquetas')
    mini.ESTILO = os.path.join(tmp, 'refs_etiqueta')
    imagen(os.path.join(mini.ESTILO, 'honor_antes_despues.jpg'))
    mini.etiqueta_gpt('ANTES', 'rojo')
    p, refs = vistos[-1]
    ok('PLANA' in p and 'relieve y brillo' not in p and not any('metal' in os.path.basename(r) for r in refs)
       and refs == [os.path.join(mini.ESTILO, 'honor_antes_despues.jpg')], f'la etiqueta de GPT: letra plana, sin el metal: {p} {refs}')
    ok('fondo de degradé vivo' in inspect.getsource(mini.portadas_short), 'las portadas de Shorts siguen con su estilo propio')
    ok(inspect.signature(mini.miniaturas_gpt).parameters['calidad'].default == 'baja' and mini.COSTO_CALIDAD['media'] < 0.1,
       'borrador en baja y la final en media')

    # 4) referencias_estilo: por marca y por vistas por día (índice), después por servicio; solo oscuras; HD; sin SI_/NO_
    E = mini.ESTILO = os.path.join(tmp, 'referencias')
    cr.CARPETA = os.path.join(tmp, 'canal_referencia')
    filas = [('honor_aaaaaaaaaa1', 'HONOR', ['frp'], 300, 20), ('honor_aaaaaaaaaa2', 'HONOR', ['frp'], 100, 25),
             ('honor_claraaaaaa3', 'HONOR', ['frp'], 900, 180), ('iphone_bbbbbbbbb1', 'IPHONE', ['icloud'], 800, 22),
             ('xiaomi_ccccccccc1', 'XIAOMI', ['frp'], 200, 30), ('xiaomi_ccccccccc2', 'XIAOMI', ['imei'], 150, 30),
             ('honor_quitadaaaa4', 'HONOR', ['frp'], 1000, 20)]
    ind = {'miniaturas': [], 'quitadas': {'quitadaaaa4': 'a ojo'}}
    for archivo, marca, servicios, vd, luz in filas:
        vid = archivo.split('_', 1)[1]
        imagen(os.path.join(E, archivo + '.jpg'))
        ind['miniaturas'].append({'id': vid, 'archivo': archivo + '.jpg', 'marca': marca, 'servicios': servicios,
                                  'vistas_dia': vd, 'luz': luz, 'titulo': archivo})
    imagen(os.path.join(E, 'SI_estilo_canal_2026-11-03.png'))
    imagen(os.path.join(E, 'NO_tosca_2026-11-03.png'))
    json.dump(ind, open(os.path.join(E, 'indice.json'), 'w', encoding='utf-8'))
    nombres = lambda rutas: [os.path.splitext(os.path.basename(r))[0] for r in rutas]
    r = nombres(mini.referencias_estilo('HONOR', 3, 'HONOR SIN CUENTA GOOGLE'))
    ok(r == ['honor_aaaaaaaaaa1', 'honor_aaaaaaaaaa2', 'xiaomi_ccccccccc1'],
       f'Honor FRP: las 2 de Honor por vistas por día (sin la clara ni la quitada) y después la de FRP: {r}')
    r = nombres(mini.referencias_estilo('MOTOROLA', 2, 'MOTO G56 SIN CUENTA GOOGLE'))
    ok(r == ['honor_aaaaaaaaaa1', 'xiaomi_ccccccccc1'], f'Motorola (sin ninguna oscura): las de FRP por vistas por día: {r}')
    r = nombres(mini.referencias_estilo('IPHONE', 2, 'BYPASS IOS 27'))
    ok(r == ['iphone_bbbbbbbbb1', 'honor_aaaaaaaaaa1'], f'iPhone: la suya y después la de más vistas por día: {r}')
    r = nombres(mini.referencias_estilo('APPLE', 1))
    ok(r == ['iphone_bbbbbbbbb1'], f'«APPLE» es iPhone: {r}')
    r = nombres(mini.referencias_estilo('HONOR', 2, 'HONOR SIN CUENTA GOOGLE', sin={'aaaaaaaaaa1'}))
    ok(r == ['honor_aaaaaaaaaa2', 'xiaomi_ccccccccc1'], f'las que ya van no se repiten: {r}')
    hd = imagen(os.path.join(cr.CARPETA, 'aaaaaaaaaa2.jpg'), w=1280, h=720)
    ok(mini.referencias_estilo('HONOR', 2, 'HONOR')[1] == hd, 'si la bajó en HD del canal, va la HD')
    cr.guardar_indice({'videos': [], 'fijadas': [], 'quitadas': ['aaaaaaaaaa1']})
    r = nombres(mini.referencias_estilo('HONOR', 1, 'HONOR'))
    ok(r == ['aaaaaaaaaa2'], f'la que quitó con 🚫 en «🖼 Miniatura» tampoco va: {r}')
    cr.guardar_indice({'videos': [], 'fijadas': [], 'quitadas': []})
    todas = mini.referencias_estilo('HONOR', 20, 'HONOR')
    ok(not any(os.path.basename(x).upper().startswith(('SI_', 'NO_')) for x in todas) and len(todas) == 5,
       f'nunca las capturas SI_/NO_, ni la clara, ni la quitada: {nombres(todas)}')
    os.remove(os.path.join(E, 'indice.json'))  # sin índice: como antes, pero nunca SI_/NO_
    r = mini.referencias_estilo('NOKIA', 20)
    ok(r and not any(os.path.basename(x).upper().startswith(('SI_', 'NO_')) for x in r), f'sin índice, sin SI_/NO_: {nombres(r)}')
    ok(nombres(mini.referencias_estilo('XIAOMI', 1)) == ['xiaomi_ccccccccc1'], 'sin índice, la misma marca primero (como antes)')
    json.dump(ind, open(os.path.join(E, 'indice.json'), 'w', encoding='utf-8'))
    os.remove(hd)

    # 5) canal_referencia.elegir: las de fondo claro no van (salvo fijadas) y, entre parecidas, más vistas por día primero
    hoy = time.time()
    fecha = lambda dias: time.strftime('%Y-%m-%d', time.localtime(hoy - dias * 86400))
    vids = [('honorVIEJA1', 'Quitar Cuenta Google Honor Magic 7 Lite', 60000, 600, OSCURO),   # 100 por día
            ('honorNUEVA1', 'Quitar Cuenta Google Honor 400 con 1 Clic', 9000, 30, OSCURO),   # 300 por día
            ('honorCLARA1', 'Quitar Cuenta Google Honor Magic 8 Lite 1 Clic', 90000, 20, CLARO),
            ('iphoneOSC01', 'Bypass Hello iOS 27 iPhone', 30000, 30, OSCURO)]
    ind_canal = {'videos': [], 'fijadas': [], 'quitadas': []}
    for vid, titulo, vistas, dias, color in vids:
        imagen(os.path.join(cr.CARPETA, vid + '.jpg'), color, 1280, 720, centro=(250, 250, 250))
        m, s = cr.etiquetar(titulo)
        ind_canal['videos'].append({'id': vid, 'titulo': titulo, 'archivo': vid + '.jpg', 'marca': m, 'servicios': s,
                                    'vistas': vistas, 'publicado': fecha(dias)})
    cr.guardar_indice(ind_canal)
    ok(cr.luz(os.path.join(cr.CARPETA, 'honorCLARA1.jpg')) > cr.LUZ_MAX >= cr.luz(os.path.join(cr.CARPETA, 'honorNUEVA1.jpg')),
       'la luz del fondo: el teléfono claro del centro no cuenta')
    e = [v['id'] for v in cr.elegir('HONOR', 'HONOR SIN CUENTA GOOGLE')]
    ok(e[:2] == ['honorNUEVA1', 'honorVIEJA1'] and 'honorCLARA1' not in e, f'oscuras y por vistas por día: {e}')
    ind_canal['fijadas'] = ['honorCLARA1']
    cr.guardar_indice(ind_canal)
    e = [v['id'] for v in cr.elegir('HONOR', 'HONOR SIN CUENTA GOOGLE')]
    ok(e[0] == 'honorCLARA1', f'una clara que fabian fijó con 📌 sí va: {e}')
    ok(abs(cr.vistas_dia({'vistas': 700, 'publicado': fecha(1)}) - 100) < 1 and cr.vistas_dia({'vistas': 365}) == 1,
       'vistas por día: mínimo 7 días; sin fecha, un año')

    # 6) armar_referencias desde el export (gratis): oscuras, largas, con marca, 10+/día, sin dos iguales, sin borrar nada
    X = os.path.join(tmp, 'youtube_datos', '2026-11-03')
    pub = lambda dias: time.strftime('%Y-%m-%dT10:00:00Z', time.localtime(time.mktime(time.strptime('2026-11-03', '%Y-%m-%d')) - dias * 86400))
    export = [('honorEXP001', 'Quitar Cuenta Google Honor con 1 Clic', 30000, 100, 900, OSCURO, 'False'),
              ('honorEXP002', 'Eliminar Cuenta Google Honor Magic 7 Lite', 5000, 100, 900, OSCURO, 'False'),
              ('honorCLARO3', 'Quitar Cuenta Google Honor 200 Lite', 90000, 100, 900, CLARO, 'False'),
              ('honorSHORT4', 'Honor FRP en 30 segundos', 90000, 100, 45, OSCURO, 'True'),
              ('noticias005', 'Movistar se va: la historia que nadie cuenta', 9000, 10, 900, OSCURO, 'False'),
              ('honorPOCAS6', 'Honor X5B FRP sin destapar', 300, 100, 900, OSCURO, 'False'),
              ('honorIGUAL7', 'Quitar Cuenta Google Honor con 1 Clic (EN)', 20000, 100, 900, OSCURO, 'False'),
              ('honorQUITA8', 'Honor Magic 8 Lite FRP', 80000, 100, 900, OSCURO, 'False')]
    lista = []
    for k, (vid, titulo, vistas, dias, seg, color, short) in enumerate(export):
        # honorIGUAL7 es la misma miniatura que honorEXP001 (el mismo video en inglés); honorEXP002 es otra
        imagen(os.path.join(X, 'thumbs', 'propios', vid + '.jpg'), color, centro=(40, 200, 40) if vid == 'honorEXP002' else (200, 200, 200))
        lista.append({'id': vid, 'titulo': titulo, 'publicado': pub(dias), 'duracion_s': str(seg), 'es_short': short,
                      'vistas': str(vistas), 'descripcion': 'RUTA_WIN'})
    texto = json.dumps(lista, ensure_ascii=False).replace('RUTA_WIN', 'C:\\Users\\PC\\Videos')
    open(os.path.join(X, 'videos.json'), 'w', encoding='utf-8').write(texto)  # con «C:\Users\PC» tal cual, como el export
    try:
        json.loads(texto)
        ok(False, 'el videos.json de prueba debería traer barras invertidas sueltas, como el export')
    except ValueError:
        pass
    D = os.path.join(tmp, 'refs_armadas')
    imagen(os.path.join(D, 'honor_de_fabian.jpg'), CLARO)
    json.dump({'quitadas': {'honorQUITA8': 'a ojo'}}, open(os.path.join(D, 'indice.json'), 'w', encoding='utf-8'))
    r = cr.armar_referencias(X, D, por_marca=4, avisar=lambda *a: None)
    ind2 = json.load(open(os.path.join(D, 'indice.json'), encoding='utf-8'))
    ids = [v['id'] for v in ind2['miniaturas']]
    ok(ids == ['honorEXP001', 'honorEXP002'], f'solo oscuras, largas, con marca, 10+ vistas/día, sin la igual ni la quitada: {ids}')
    ok(r['total'] == 2 and ind2['quitadas'] == {'honorQUITA8': 'a ojo'} and ind2['fecha'] == '2026-11-03', f'índice: {r} {ind2.get("fecha")}')
    v = ind2['miniaturas'][0]
    ok(v['archivo'] == 'honor_honorEXP001.jpg' and os.path.isfile(os.path.join(D, v['archivo'])) and v['marca'] == 'HONOR'
       and 'frp' in v['servicios'] and v['luz'] <= cr.LUZ_MAX and abs(v['vistas_dia'] - 300) < 5, f'la fila: {v}')
    ok(os.path.isfile(os.path.join(D, 'honor_de_fabian.jpg')), 'no borra las miniaturas que ya estaban')

    # 7) miniaturas_gpt: del canal hay 1 oscura → se completa con las de referencias/ (por vistas por día); nunca SI_/NO_
    d = os.path.join(tmp, 'HONOR MAGIC 8 LITE')
    fotos = [imagen(os.path.join(d, f'foto_miniatura_{k}.jpg')) for k in ('antes', 'despues')]
    mini.LOGOS_DIR = os.path.join(tmp, 'sin_logos')
    for vid in ('honorNUEVA1', 'honorVIEJA1', 'iphoneOSC01'):
        os.remove(os.path.join(cr.CARPETA, vid + '.jpg'))
    ind_canal['fijadas'] = []
    cr.guardar_indice(ind_canal)  # queda solo la clara (no va) → del canal no va ninguna
    enviados = []
    mini.imagen_gpt = lambda prompt, refs, **k: (enviados.append((prompt, list(refs))), np.zeros((864, 1536, 3), np.uint8))[1]
    mini.miniaturas_gpt(d, fotos, ['HONOR', 'SIN CUENTA GOOGLE'], os.path.join(d, 'm'), 'HONOR', idiomas=('es',))
    prompt, refs = enviados[-1]
    ok(refs[:2] == fotos and nombres(refs[2:]) == ['honor_aaaaaaaaaa1', 'honor_aaaaaaaaaa2', 'xiaomi_ccccccccc1'],
       f'sin oscuras del canal: sus fotos y 3 de referencias/ por vistas por día: {nombres(refs)}')
    ok('Imágenes 3 a 5: miniaturas de SU canal' in prompt, 'el pedido cuenta bien las imágenes de estilo')
    imagen(os.path.join(cr.CARPETA, 'honorNUEVA1.jpg'), OSCURO, 1280, 720)
    mini.miniaturas_gpt(d, fotos, ['HONOR', 'SIN CUENTA GOOGLE'], os.path.join(d, 'm'), 'HONOR', idiomas=('es',))
    refs = enviados[-1][1]
    ok(nombres(refs[2:]) == ['honorNUEVA1', 'honor_aaaaaaaaaa1', 'honor_aaaaaaaaaa2'],
       f'una oscura del canal + 2 de referencias/: {nombres(refs)}')
    ok(not any(os.path.basename(x).upper().startswith(('SI_', 'NO_')) for _, rr in enviados for x in rr),
       'las capturas SI_/NO_ nunca van a GPT')

print('\n'.join(fallos) or 'ok: miniaturas con el estilo del canal (fondo negro, letras sin cromado, referencias por vistas por día)')
sys.exit(1 if fallos else 0)
