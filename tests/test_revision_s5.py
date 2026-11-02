"""Prueba rápida de los arreglos de la revisión S5 (miniaturas y conocimiento). Sin internet y sin gastar nada: las IAs van
simuladas y tus ajustes, conocimientos y proyectos no se tocan (todo va a una carpeta temporal).
- «🔍 Analizar» y la revisión de las miniaturas le pasan las imágenes a la IA en el formato que espera (antes fallaba siempre);
- si la IA de la revisión falla, la generación sigue; si una imagen falla a mitad, lo ya cobrado queda en gastos.json;
- con «Fondo: ambos» el título de GPT se dibuja una sola vez (no una por fondo);
- las imágenes se guardan y leen aunque la ruta tenga tildes o ñ;
- corregir el texto de una etiqueta no cuenta como «la quitó»;
- el guion del mismo proyecto (con espacios en el nombre) no es ejemplo de sí mismo;
- al juntar lo de la otra PC, las notas de una sección propia que ya tienes van a esa sección y no a «Ideas».
Uso: python tests/test_revision_s5.py   (sale con 1 si algo falla)
"""
import argparse, json, os, shutil, sys, tempfile

import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('ia', 'miniatura', 'conocimiento'):
    sys.path.insert(0, os.path.join(RAIZ, sub))
os.environ.pop('MINIREF_SIMULAR', None)
os.environ.pop('CACHE_IA', None)
import ia  # noqa: E402
import miniatura as mini  # noqa: E402
import referencias as mr  # noqa: E402
import conocimiento as co  # noqa: E402
import aprendizaje  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


tmp = tempfile.mkdtemp(prefix='revision_s5_')
try:
    # 1) la IA recibe las imágenes como (nombre, ruta), como ia.llamar las lee: «for _, f in caps»
    d = os.path.join(tmp, 'proyecto ñandú')
    os.makedirs(os.path.join(tmp, 'raiz', 'app'))
    json.dump({'url': 'https://api.openai.com/v1', 'clave': 'x', 'modelo': 'prueba'},
              open(os.path.join(tmp, 'raiz', 'app', 'ajustes.json'), 'w', encoding='utf-8'))
    ref = os.path.join(mr.carpeta(d, 'referencias'), 'ref.jpg')
    cv2.imencode('.jpg', np.full((90, 160, 3), 120, np.uint8))[1].tofile(ref)
    vistas = []

    def compatible(ajustes, texto, caps, det=None):
        for _, f in caps:
            vistas.append(os.path.isfile(f))
        return mr._respuesta_simulada(texto)
    viejos = (mr.RAIZ, ia.llamar_compatible, ia.diagnostico.anotar)
    mr.RAIZ, ia.llamar_compatible, ia.diagnostico.anotar = os.path.join(tmp, 'raiz'), compatible, (lambda ev: None)
    try:
        receta = mr.analizar(d)
        ok(receta.get('conjunto') and vistas == [True], f'«🔍 Analizar» debería mandar la referencia a la IA: {vistas}')
        rv = mr.revisar(d, 'referencias/ref.jpg', 'TEXTO SIMULADO')
        ok(rv['ok'] is True and vistas == [True, True], f'la revisión debería ver la miniatura: {rv} {vistas}')
    except Exception as e:
        ok(False, f'«🔍 Analizar» o la revisión fallan con la IA de verdad: {e!r}')
    finally:
        mr.RAIZ, ia.llamar_compatible, ia.diagnostico.anotar = viejos

    # 2) la IA de la revisión falla (ErrorIA es SystemExit): la imagen ya cobrada queda y la generación sigue
    if not os.path.exists(os.path.join(mr.carpeta(d), 'receta.json')):
        mr.guardar(os.path.join(mr.carpeta(d), 'receta.json'), json.loads(mr._respuesta_simulada('receta')))
    json.dump({'ideas': [{'texto': 'NO CONTESTES', 'en': "DON'T ANSWER", 'pt': 'NÃO ATENDA', 'concepto': 'c'}]},
              open(os.path.join(mr.carpeta(d), 'ideas.json'), 'w', encoding='utf-8'))
    imagen = lambda prompt, refs, size: np.full((1024, 1536, 3), 90, np.uint8)

    def ia_caida(texto, imgs):
        raise ia.ErrorIA('ERROR: la IA no contestó', 'B')
    try:
        nuevas = mr.generar(d, [1], 2, generar_img=imagen, llamar=ia_caida)
        ok(len(nuevas) == 2 and all(r['revision']['ok'] is None for r in nuevas), f'la revisión fallida no debe cortar: {nuevas}')
    except SystemExit as e:
        ok(False, f'un fallo de la IA en la revisión cortó la generación ya pagada: {e}')
    gastos = mr.leer(os.path.join(mr.carpeta(d), 'gastos.json'), []) or []
    ok(gastos and gastos[-1]['imagenes'] == 2, f'gasto anotado: {gastos}')

    # 3) una imagen falla a mitad: lo ya cobrado queda anotado en gastos.json
    if os.path.exists(os.path.join(mr.carpeta(d), 'gastos.json')):
        os.remove(os.path.join(mr.carpeta(d), 'gastos.json'))
    hechas = []

    def falla_la_segunda(prompt, refs, size):
        if hechas:
            raise SystemExit('ERROR: OpenAI respondió 500')
        hechas.append(1)
        return np.full((1024, 1536, 3), 90, np.uint8)
    try:
        mr.generar(d, [1], 3, generar_img=falla_la_segunda, revisar_luego=False)
        ok(False, 'debería avisar del error de la imagen')
    except SystemExit:
        pass
    gastos = mr.leer(os.path.join(mr.carpeta(d), 'gastos.json'))
    ok(gastos and gastos[-1]['imagenes'] == 1, f'lo ya cobrado debería quedar en gastos.json: {gastos}')

    # 4) «🖼 Miniatura» con «Fondo: ambos» y título de GPT: 2 escenas y los títulos UNA vez (3 estilos × 3 idiomas = 9)
    d = os.path.join(tmp, 'HONOR CONTRASEÑA')
    os.makedirs(d)
    for k in ('antes', 'despues'):
        mini.guardar_img(os.path.join(d, f'foto_miniatura_{k}.jpg'), np.full((720, 1280, 3), 60, np.uint8))
    escenas, titulos = [], []
    viejos = (mini.imagen_gpt, mini.titulo_gpt, mini.etiqueta_gpt, mini.componer_mixta, mini.traducciones_titulo)
    mini.imagen_gpt = lambda prompt, refs, **k: (escenas.append(1), np.zeros((864, 1536, 3), np.uint8))[1]
    mini.titulo_gpt = lambda partes, estilo, salida: (titulos.append(os.path.basename(salida)), open(salida, 'wb').write(b'png'))
    mini.etiqueta_gpt = lambda *a, **k: None
    mini.componer_mixta = lambda escena, lineas, marca, idioma, f, estilo, png, esq: open(f, 'wb').write(b'jpg')
    mini.traducciones_titulo = lambda d_, lineas: {i: [x.upper() for x in lineas if x] for i in ('es', 'en', 'pt')}
    a = argparse.Namespace(gpt=True, texto='HONOR|SIN CUENTA GOOGLE', fondo='ambos', mixta=True, titulo='todos', titulo_gpt=True,
                           esquina_izq='NEW 2026', esquina_der='')
    try:
        mini.con_fotos(d, a)
    finally:
        mini.imagen_gpt, mini.titulo_gpt, mini.etiqueta_gpt, mini.componer_mixta, mini.traducciones_titulo = viejos
    ok(len(escenas) == 2 and len(titulos) == 9, f'con los dos fondos: 2 escenas y 9 títulos, no {len(escenas)} y {len(titulos)}')
    hechas = json.load(open(os.path.join(d, 'miniatura_fotos.json'), encoding='utf-8'))['miniaturas']
    ok(len(hechas) == 18 and all(os.path.isfile(os.path.join(d, h['archivo'])) for h in hechas), 'faltan miniaturas')

    # 5) imágenes con tildes y ñ en la ruta: se guardan y se leen
    f = os.path.join(d, 'miniatura_año_é.jpg')
    mini.guardar_img(f, np.full((20, 30, 3), 200, np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
    im = mini.leer_img(f)
    ok(im is not None and im.shape[:2] == (20, 30), 'la imagen con ñ en la ruta no se guardó o no se leyó')
    ok(mini.leer_img(os.path.join(d, 'no_existe.png')) is None, 'leer una imagen que no existe debería dar None')

    # 6) corregir el texto de una etiqueta no es quitarla; quitarla sí
    viejo = [{'bloque': 'L09', 'frase': 'entra a la página', 'titulo': 'Descarga aquí', 'texto': 'gsmprime.com'},
             {'bloque': 'L10', 'frase': 'unos pocos dólares', 'titulo': 'Tiene un costo', 'texto': 'Unos pocos dólares'}]
    nuevo = [dict(viejo[0], texto='gsmprime.co'), viejo[1]]
    ok(aprendizaje._eventos_lista(viejo, nuevo, 'etiqueta') == [], 'cambiar el texto de una etiqueta no debería contar como quitada')
    ev = aprendizaje._eventos_lista(viejo, [viejo[1]], 'etiqueta')
    ok(len(ev) == 1 and ev[0]['tipo'] == 'quito_etiqueta' and ev[0]['titulo'] == 'Descarga aquí', f'quitar sí cuenta: {ev}')

    # 7) el guion aprobado del mismo proyecto (con espacios en el nombre) no es ejemplo de sí mismo
    p = os.path.join(tmp, 'proyectos', 'HONOR 8 LITE')
    os.makedirs(p)
    ok(co._parecido(p, os.path.join(tmp, 'guiones', 'HONOR_8_LITE.md')) == -1, 'el mismo proyecto no debería ser su ejemplo')

    # 8) juntar lo de la otra PC: «## Modelos» ya existe en las dos → la nota nueva va a «Modelos», no a «Ideas»
    viejos = (co.CARPETA, co.PRINCIPAL, co.APRENDIDO, co.MARCAS, dict(co.SECCIONES))
    co.CARPETA = os.path.join(tmp, 'mis_conocimientos')
    co.PRINCIPAL, co.APRENDIDO, co.MARCAS = (os.path.join(co.CARPETA, x) for x in ('CONOCIMIENTO.md', 'aprendido_de_proyectos.md', 'marcas'))
    try:
        co.asegurar()
        open(co.PRINCIPAL, 'a', encoding='utf-8').write('\n## Modelos\n- Honor 8 Lite usa Kirin (2026-11-01)\n')
        otra = os.path.join(tmp, 'otra_pc')
        os.makedirs(otra)
        open(os.path.join(otra, 'CONOCIMIENTO.md'), 'w', encoding='utf-8').write(
            '# Conocimiento\n\n## Modelos\n- Honor 8 Lite usa Kirin (2026-11-01)\n- Moto G24 entra a Fastboot con volumen menos (2026-11-02)\n')
        co.juntar(otra)
        md = open(co.PRINCIPAL, encoding='utf-8').read()
        seccion = md.split('## Modelos', 1)[1].split('\n## ', 1)[0]
        ok('Moto G24 entra a Fastboot' in seccion and md.count('## Modelos') == 1, f'la nota debería quedar en «Modelos»:\n{md}')
    finally:
        co.CARPETA, co.PRINCIPAL, co.APRENDIDO, co.MARCAS = viejos[:4]
        co.SECCIONES.clear()
        co.SECCIONES.update(viejos[4])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión S5 (IA con imágenes, gastos, títulos con dos fondos, rutas con ñ, aprendizaje, conocimiento)')
sys.exit(1 if fallos else 0)
