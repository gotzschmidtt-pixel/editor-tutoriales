"""Prueba rápida de «🖼️ Miniaturas de referencia» (miniatura/referencias.py) SIN gastar: las IAs van simuladas
(MINIREF_SIMULAR=1 y funciones de prueba). Sube, analiza, propone ideas, calcula el costo, genera, revisa y elige.
Uso: python tests/test_miniaturas_referencia.py   (sale con 1 si algo falla)
"""
import json, os, sys, tempfile
import cv2
import numpy as np

os.environ['MINIREF_SIMULAR'] = '1'
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'miniatura'))
import referencias as mr  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def png(w, h, color):
    img = np.full((h, w, 3), color, np.uint8)
    return cv2.imencode('.png', img)[1].tobytes()


with tempfile.TemporaryDirectory() as d:
    json.dump({'titulo': 'Movistar se va: la historia que nadie cuenta'}, open(os.path.join(os.makedirs(os.path.join(d, 'youtube')) or d, 'youtube', 'metadatos.json'), 'w'))
    # 1) subir: se guarda como JPG de hasta 1536 px; lo que no es imagen se rechaza
    n1 = mr.subir(d, 'Olga miniatura.PNG', png(3000, 1688, (20, 30, 200)))
    n2 = mr.subir(d, 'Olga miniatura.PNG', png(640, 360, (200, 30, 20)))
    ok(n1 == 'Olga_miniatura.jpg' and n2 == 'Olga_miniatura_2.jpg', f'nombres: {n1}, {n2}')
    img = cv2.imread(os.path.join(d, 'miniatura', 'referencias', n1))
    ok(img is not None and max(img.shape[:2]) == 1536, 'la referencia grande debería quedar en 1536 px')
    try:
        mr.subir(d, 'x.png', b'no soy una imagen')
        ok(False, 'debería rechazar lo que no es imagen')
    except ValueError:
        pass

    # 2) analizar (simulado) → receta.json; editar la receta
    llamadas = []
    receta = mr.analizar(d, llamar=lambda t, imgs: (llamadas.append(len(imgs)), mr._respuesta_simulada(t))[1])
    ok(llamadas == [2], f'el análisis debería mandar las 2 referencias como imágenes: {llamadas}')
    ok(receta.get('conjunto') and receta.get('resumen'), 'falta la receta')
    mr.guardar_receta(d, {'resumen': 'editada a mano'})
    ok(mr.leer(os.path.join(d, 'miniatura', 'receta.json'))['resumen'] == 'editada a mano', 'la receta editada no se guardó')

    # 3) ideas: hasta 4 palabras, con inglés y portugués; si la IA se pasa, se recorta y se marca
    largo = lambda t, i: json.dumps({'ideas': [{'texto': 'esto tiene muchas palabras de más', 'en': 'x', 'pt': 'y', 'concepto': 'c'}]})
    l = mr.ideas(d, llamar=largo)
    ok(l[0]['texto'] == 'ESTO TIENE MUCHAS PALABRAS' and l[0]['largo_ok'] is False, f'recorte a 4 palabras: {l[0]}')
    l = mr.ideas(d)
    ok(len(l) == 3 and all(x['en'] and x['pt'] for x in l), 'ideas simuladas con traducciones')

    # 4) costo antes de generar y generar (simulado): 2 ideas × 2 variantes = 4 imágenes, 1280×720 JPG < 2 MB
    p = mr.presupuesto(2, 2)
    ok(p['imagenes'] == 4 and abs(p['costo_usd'] - 4 * mr.COSTO_IMAGEN) < 0.001, f'presupuesto: {p}')
    pedidos = []
    falsa = lambda prompt, refs, size: (pedidos.append((prompt, len(refs), size)), np.full((1024, 1536, 3), 128, np.uint8))[1]
    cara = os.path.join(d, 'cara.png')
    open(cara, 'wb').write(png(400, 400, (10, 200, 10)))
    nuevas = mr.generar(d, [1, 3], 2, '16x9', 'es', cara=cara, generar_img=falsa)
    ok(len(nuevas) == 4 and len(pedidos) == 4, f'deberían salir 4 imágenes: {len(nuevas)}')
    ok(all(r == 3 for _, r, _ in pedidos), 'cada pedido: 2 referencias de estilo + la cara')
    ok('«NO CONTESTES»' in pedidos[0][0] and 'do not copy' in pedidos[0][0], 'el prompt lleva el texto exacto y la regla de no calcar')
    for r in nuevas:
        f = os.path.join(d, 'miniatura', r['archivo'])
        im = cv2.imread(f)
        ok(im is not None and im.shape[:2] == (720, 1280) and os.path.getsize(f) < 2_000_000, f'tamaño de {r["archivo"]}')
        ok(r['revision']['ok'] is True, 'la revisión simulada debería salir bien')
    g = mr.leer(os.path.join(d, 'miniatura', 'gastos.json'))
    ok(g and g[-1]['imagenes'] == 4 and g[-1]['simulado'] is True, f'el gasto debería quedar anotado: {g}')
    v = mr.generar(d, [2], 1, '9x16', 'pt', generar_img=lambda pr, refs, size: np.zeros((1536, 1024, 3), np.uint8))
    im = cv2.imread(os.path.join(d, 'miniatura', v[0]['archivo']))
    ok(im.shape[:2] == (1920, 1080) and v[0]['texto'] == 'ROUBAM SUA LINHA', 'versión vertical en portugués')

    # 5) revisión con errores → marcada
    mal = lambda t, imgs: json.dumps({'texto_leido': 'NO CONTETES', 'ortografia_ok': False, 'letras_deformes': True, 'errores': ['falta la S']})
    rv = mr.revisar(d, nuevas[0]['archivo'], 'NO CONTESTES', llamar=mal)
    ok(rv['ok'] is False and rv['errores'], 'una miniatura con errores debería quedar marcada')

    # 6) usar como miniatura: queda elegida en YouTube y copiada a subir_youtube/; nada fuera de la carpeta
    nombre = mr.usar(d, nuevas[1]['archivo'])
    ok(json.load(open(os.path.join(d, 'youtube', 'miniatura.json')))['archivo'] == nombre, 'no quedó elegida en YouTube')
    ok(os.path.isfile(os.path.join(d, nombre)) and os.path.isfile(os.path.join(d, 'subir_youtube', nombre)), 'faltan las copias')
    try:
        mr.usar(d, '../../youtube/metadatos.json')
        ok(False, 'debería rechazar rutas fuera de miniatura/')
    except ValueError:
        pass
    e = mr.estado(d)
    ok(len(e['referencias']) == 2 and len(e['generadas']) == 5 and e['elegida'] == nombre, 'estado de la pestaña')

print('\n'.join(fallos) or 'ok: miniaturas de referencia')
sys.exit(1 if fallos else 0)
