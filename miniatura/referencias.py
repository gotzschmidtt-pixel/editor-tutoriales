"""«🖼️ Miniaturas de referencia» (pedido de fabian, 01/11/2026: «yo subo unas miniaturas, tú las tomas de ahí, las analizas
y después pasan a GPT a generar las miniaturas»).

1. Subes miniaturas que te gustan (tuyas o de otros canales) → <proyecto>/miniatura/referencias/ (JPG, máx. 1536 px).
2. «🔍 Analizar» (la IA de texto con imágenes de la app, ia/ia.py; cuesta centavos): una RECETA por referencia y del
   conjunto — dónde y qué tan grande va la cara, emoción, cuántas palabras y cómo son las letras (placas, colores, borde),
   objeto principal, fondo, paleta, contraste y por qué da clic → miniatura/receta.json (editable en la pestaña).
   Es una fórmula, no un calco: nunca se copian caras de otras personas, logos de canales ni sus textos.
3. «💡 Ideas»: con la receta, el título del video y la guía de estilo de fabian (mis_conocimientos/miniaturas), 3-4 ideas
   (texto de 4 palabras como mucho + concepto), con su versión en inglés y portugués → miniatura/ideas.json.
4. «🎨 Generar» (GASTA: gpt-image-2.5-flare, calidad alta, ~0,28 USD por imagen): por cada idea elegida, 2 variantes por
   defecto, con las referencias como imágenes de ESTILO y, si quieres, tu cara (avatar o foto). Antes de generar la pestaña
   muestra cuántas imágenes y el costo, y pide confirmar. Sale 1280×720 JPG < 2 MB (o 1080×1920 para Shorts) en
   miniatura/generadas/, con el costo anotado en miniatura/gastos.json.
5. Cada resultado se revisa con visión: ortografía, tildes y letras deformes; si hay errores queda marcado en rojo.
6. «⭐ Usar como miniatura»: la copia al proyecto como miniatura_ref_….jpg, la deja elegida en Publicar → YouTube
   (youtube/miniatura.json) y la copia a subir_youtube/.

Uso: python miniatura/referencias.py --proyecto CARPETA analizar|ideas|generar|revisar [--ideas 1,3] [--variantes 2]
     [--formato 16x9|9x16] [--idioma es|en|pt] [--cara RUTA] [--archivo generadas/x.jpg]
     (con MINIREF_SIMULAR=1 no llama a ninguna IA: respuestas de prueba, para probar sin gastar)
"""
import argparse, base64, json, os, re, shutil, sys, time
import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIA = os.path.join(RAIZ, 'mis_conocimientos', 'miniaturas', 'ESTILO_MINIATURAS.md')
COSTO_IMAGEN = 0.28        # USD por imagen de gpt-image-2.5-flare en calidad alta (medido el 01/11/2026 con la miniatura F)
MAX_REFS_GPT = 3           # cuántas referencias de estilo van a la IA de imágenes en cada pedido
FORMATOS = {'16x9': ('1536x1024', 1280, 720), '9x16': ('1024x1536', 1080, 1920)}
REGLAS = ('Reglas fijas del canal: cara con emoción clara; UN objeto principal; sensación de peligro o urgencia sin mentir; si '
          'aparece un teléfono, va de ESPALDAS (nunca su pantalla legible); texto de 4 palabras como mucho, en MAYÚSCULAS, '
          'con tildes correctas; nada de desbloqueo, WhatsApp ni QR en videos de noticias; los logos reales de marcas los pone '
          'la app encima si la IA los deforma. Es una fórmula, no un calco: no copies caras de otras personas, logos de otros '
          'canales ni sus textos. Gustos de fabian (02/11/2026): expresión natural (ni exagerada, ni seria, ni pícara); buzo o '
          'camiseta blanco liso sin logos; un solo título; textos grandes que se lean en el celular; solo dos manos; la cámara '
          'real del modelo a la vista; las etiquetas las dibuja la IA de imágenes. Fondo (fabian, 03/11/2026: «fondos negros»): '
          'negro como su canal o el original de la foto oscurecido casi a negro; nunca claro, ni un túnel de rayos o destellos.')


def carpeta(d, *partes):
    c = os.path.join(d, 'miniatura', *partes)
    os.makedirs(c if not os.path.splitext(c)[1] else os.path.dirname(c), exist_ok=True)
    return c


def leer(f, defecto=None):
    try:
        return json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        return defecto


def guardar(f, datos):
    os.makedirs(os.path.dirname(f), exist_ok=True)
    tmp = f + '.nuevo'
    json.dump(datos, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, f)


def referencias(d):
    c = carpeta(d, 'referencias')
    return sorted(os.path.join(c, f) for f in os.listdir(c) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')))


def subir(d, nombre, datos):
    """Guarda una referencia subida (jpg/png/webp) como JPG de hasta 1536 px. Devuelve el nombre guardado."""
    img = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError('No pude abrir esa imagen. Usa JPG, PNG o WEBP.')
    k = min(1.0, 1536 / max(img.shape[:2]))
    if k < 1:
        img = cv2.resize(img, (int(img.shape[1] * k), int(img.shape[0] * k)), interpolation=cv2.INTER_AREA)
    base = re.sub(r'[^\w\-]+', '_', os.path.splitext(os.path.basename(nombre or 'ref'))[0])[:50].strip('_') or 'ref'
    c = carpeta(d, 'referencias')
    destino, n = os.path.join(c, base + '.jpg'), 2
    while os.path.exists(destino):
        destino, n = os.path.join(c, f'{base}_{n}.jpg'), n + 1
    cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 93])[1].tofile(destino)
    return os.path.basename(destino)


def borrar_ref(d, nombre):
    f = os.path.join(carpeta(d, 'referencias'), os.path.basename(nombre))
    if os.path.isfile(f):
        os.remove(f)


# ---------------------------------------------------------------- las IAs (inyectables, para probar sin gastar)

def _simulando():
    return os.environ.get('MINIREF_SIMULAR') == '1'


def llamar_ia(texto, imagenes):
    """La IA de texto con imágenes que usa la app (ia/ia.py), con imágenes activadas. Devuelve el texto de la respuesta."""
    if _simulando():
        return _respuesta_simulada(texto)
    sys.path.insert(0, os.path.join(RAIZ, 'ia'))
    import ia
    ajustes = dict(json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')), imagenes=True)
    # ia.llamar quiere (nombre, ruta) por imagen, como las capturas del guion (con rutas sueltas fallaba siempre)
    return ia.llamar(ajustes, texto, [(os.path.basename(f), f) for f in imagenes])


def imagen_ia(prompt, refs, size):
    """gpt-image-2.5-flare (calidad alta) con referencias. Devuelve la imagen BGR."""
    if _simulando():
        w, h = map(int, size.split('x'))
        img = np.full((h, w, 3), (90, 40, 20), np.uint8)
        cv2.putText(img, 'SIMULADA', (40, h // 2), cv2.FONT_HERSHEY_DUPLEX, 3, (255, 255, 255), 6)
        return img
    sys.path.insert(0, os.path.join(RAIZ, 'miniatura'))
    import miniatura
    return miniatura.imagen_gpt(prompt, refs, size=size)


def _respuesta_simulada(texto):
    if '"ortografia_ok"' in texto:
        return json.dumps({'texto_leido': 'TEXTO SIMULADO', 'ortografia_ok': True, 'letras_deformes': False, 'errores': []})
    if '"ideas"' in texto:
        return json.dumps({'ideas': [{'texto': 'NO CONTESTES', 'en': "DON'T ANSWER", 'pt': 'NÃO ATENDA', 'concepto': 'cara de alarma y teléfono de espaldas sonando', 'por_que': 'peligro inmediato'},
                                     {'texto': 'TE ROBAN LA LÍNEA', 'en': 'THEY STEAL YOUR LINE', 'pt': 'ROUBAM SUA LINHA', 'concepto': 'SIM rota', 'por_que': 'miedo a perder el número'},
                                     {'texto': 'YA NO ES MOVISTAR', 'en': 'NOT MOVISTAR ANYMORE', 'pt': 'NÃO É MAIS MOVISTAR', 'concepto': 'letrero cambiando', 'por_que': 'noticia'}]})
    return json.dumps({'referencias': [{'archivo': 'x', 'cara': 'derecha, 40 % del alto', 'emocion': 'sorpresa', 'palabras': 3,
                                        'letras': 'placa roja + placa blanca, borde negro', 'objeto': 'teléfono', 'fondo': 'ciudad azul desenfocada',
                                        'paleta': ['#E61E1E', '#FFFFFF', '#0B1630'], 'contraste': 'alto', 'por_que_clic': 'peligro + cara'}],
                       'conjunto': {'cara': 'derecha, grande', 'emocion': 'alarma', 'palabras': '2-4', 'letras': 'placas sólidas',
                                    'objeto': 'uno solo', 'fondo': 'oscuro desenfocado', 'paleta': ['#E61E1E', '#FFFFFF'], 'contraste': 'alto',
                                    'por_que_clic': 'emoción fuerte y texto corto'},
                       'resumen': 'Receta simulada: cara grande con emoción a la derecha, 2-4 palabras en placas, un objeto, fondo oscuro.'})


def _json(txt):
    sys.path.insert(0, os.path.join(RAIZ, 'ia'))
    try:
        import ia
        return ia.extraer_json(txt)
    except Exception:  # sin ia.py (pruebas) o respuesta rara: el primer {...}
        m = re.search(r'\{.*\}', txt or '', re.S)
        return json.loads(m.group(0)) if m else {}


# ---------------------------------------------------------------- 2) analizar

def analizar(d, llamar=None):
    llamar = llamar or llamar_ia
    refs = referencias(d)
    if not refs:
        raise ValueError('Primero sube al menos una miniatura de referencia.')
    nombres = [os.path.basename(r) for r in refs]
    prompt = ('Eres experto en miniaturas de YouTube que dan clic. Te paso ' + str(len(refs)) + ' miniaturas de referencia, en este '
              f'orden: {json.dumps(nombres, ensure_ascii=False)}. Analiza CADA una y luego el conjunto: posición y tamaño de la cara '
              '(o si no hay), emoción, cuántas palabras tiene el texto y cómo son las letras (placas, colores, borde, sombra, '
              'inclinación), objeto principal, fondo, paleta (3-5 colores en hex), contraste y por qué da clic. Saca la FÓRMULA, '
              'no un calco: no describas quién es la persona ni copies textos o logos de canales. Responde en español y SOLO con '
              'JSON: {"referencias": [{"archivo": "…", "cara": "…", "emocion": "…", "palabras": 0, "letras": "…", "objeto": "…", '
              '"fondo": "…", "paleta": ["#…"], "contraste": "…", "por_que_clic": "…"}], "conjunto": {"cara": "…", "emocion": "…", '
              '"palabras": "…", "letras": "…", "objeto": "…", "fondo": "…", "paleta": ["#…"], "contraste": "…", "por_que_clic": "…"}, '
              '"resumen": "3-4 frases cortas en español con la receta"}')
    r = _json(llamar(prompt, refs))
    if not isinstance(r, dict) or not r.get('conjunto'):
        raise ValueError('La IA no devolvió la receta. Vuelve a intentarlo.')
    receta = {'referencias': r.get('referencias') or [], 'conjunto': r['conjunto'], 'resumen': str(r.get('resumen') or ''),
              'archivos': nombres, 'fecha': time.strftime('%Y-%m-%d %H:%M')}
    guardar(os.path.join(carpeta(d), 'receta.json'), receta)
    return receta


def guardar_receta(d, receta):
    vieja = leer(os.path.join(carpeta(d), 'receta.json'), {}) or {}
    vieja.update({k: v for k, v in receta.items() if k in ('conjunto', 'resumen', 'referencias')})
    vieja['editada'] = time.strftime('%Y-%m-%d %H:%M')
    guardar(os.path.join(carpeta(d), 'receta.json'), vieja)
    return vieja


# ---------------------------------------------------------------- 3) ideas

def titulo_video(d):
    m = leer(os.path.join(d, 'youtube', 'metadatos.json'), {}) or {}
    t = m.get('titulo') or ''
    if not t:
        g = leer(os.path.join(d, 'guion.json'), {}) or {}
        t = g.get('video') or g.get('titulo') or ''
    texto = ' '.join(b.get('texto', '') for b in ((leer(os.path.join(d, 'guion.json'), {}) or {}).get('bloques') or [])[:6])
    return t, texto[:1500]


def ideas(d, llamar=None, n=4):
    llamar = llamar or llamar_ia
    receta = leer(os.path.join(carpeta(d), 'receta.json'))
    if not receta:
        raise ValueError('Primero «🔍 Analizar» las referencias.')
    titulo, guion = titulo_video(d)
    guia = ''
    if os.path.exists(GUIA):  # el principio (con la revisión obligatoria) y, siempre, la competencia, los gustos y los errores
        t = open(GUIA, encoding='utf-8').read()
        # (revisión, 03/11/2026) la sección «Estilo del canal para GPT» (03/11) quedó arriba y el corte de 3000 la partía a la
        # mitad: el principio llega hasta ella. Esa sección es la de «🖼 Miniatura» (tutoriales: el teléfono en la mano, de
        # frente); aquí mandan la receta de tus referencias y REGLAS (el teléfono de espaldas), así que no va
        nueva = t.find('\n## Estilo del canal para GPT')
        guia = t[:min(3000, nueva) if nueva > 0 else 3000]
        for s, largo in (('## Patrones de la competencia', 2500), ('## Gustos confirmados', 6000)):
            i = t.find(s)
            guia += '\n...\n' + t[i:i + largo] if i >= 0 else ''
    prompt = (f'Propón {n} ideas de miniatura para este video de YouTube del canal Xiaomiunlock (fabian).\nTítulo: {titulo}\n'
              f'Inicio del guion: {guion}\n\nReceta sacada de las miniaturas de referencia que le gustan:\n'
              f'{json.dumps(receta.get("conjunto"), ensure_ascii=False)}\n{receta.get("resumen", "")}\n\nGuía de estilo de fabian:\n{guia}\n\n'
              f'{REGLAS}\nCada idea: un texto de 4 palabras como mucho (MAYÚSCULAS, tildes correctas) con su traducción al inglés y '
              'al portugués de Brasil, y el concepto de la imagen en una frase. Responde SOLO con JSON: {"ideas": [{"texto": "…", '
              '"en": "…", "pt": "…", "concepto": "…", "por_que": "…"}]}')
    r = _json(llamar(prompt, []))
    lista = []
    for x in (r.get('ideas') if isinstance(r, dict) else None) or []:
        t = str(x.get('texto') or '').strip().upper()
        if not t:
            continue
        palabras = t.split()
        lista.append({'texto': ' '.join(palabras[:4]), 'en': str(x.get('en') or t).strip().upper(), 'pt': str(x.get('pt') or t).strip().upper(),
                      'concepto': str(x.get('concepto') or '')[:300], 'por_que': str(x.get('por_que') or '')[:200],
                      'largo_ok': len(palabras) <= 4})
    if not lista:
        raise ValueError('La IA no devolvió ideas. Vuelve a intentarlo.')
    guardar(os.path.join(carpeta(d), 'ideas.json'), {'ideas': lista[:n], 'titulo': titulo, 'fecha': time.strftime('%Y-%m-%d %H:%M')})
    return lista[:n]


def guardar_ideas(d, lista):
    guardar(os.path.join(carpeta(d), 'ideas.json'), {'ideas': lista, 'fecha': time.strftime('%Y-%m-%d %H:%M'), 'editadas': True})
    return lista


# ---------------------------------------------------------------- 4) generar (gasta)

def presupuesto(n_ideas, variantes=2):
    n = max(0, int(n_ideas)) * max(1, int(variantes))
    return {'imagenes': n, 'costo_usd': round(n * COSTO_IMAGEN, 2), 'por_imagen_usd': COSTO_IMAGEN,
            'texto': f'{n} imágenes con gpt-image-2.5-flare en calidad alta ≈ USD {n * COSTO_IMAGEN:.2f}'}


def prompt_imagen(receta, idea, idioma='es', formato='16x9', con_cara=False):
    texto = idea.get(idioma) if idioma != 'es' else idea['texto']
    c = receta.get('conjunto') or {}
    vertical = formato == '9x16'
    return (('Vertical 9:16 YouTube Shorts cover' if vertical else 'YouTube thumbnail, 16:9') +
            '. Use the reference thumbnails ONLY as a style formula (layout, text plates, palette, contrast, energy); do not copy '
            'their people, faces, channel logos or texts. ' +
            f'Formula from the references: face {c.get("cara", "")}; emotion {c.get("emocion", "")}; lettering {c.get("letras", "")}; '
            f'main object {c.get("objeto", "")}; background {c.get("fondo", "")}; palette {", ".join(c.get("paleta") or [])}; '
            f'contrast {c.get("contraste", "")}. ' +
            f'Concept: {idea.get("concepto", "")}. ' +
            (f'The presenter is the person in the LAST reference image (same face and beard), photorealistic, with a natural, not '
             f'exaggerated {c.get("emocion") or "surprised"} expression (no shouting), plain white sweater without logos. ' if con_cara
             else 'No real person needs to appear; if a face appears it is a generic one. ') +
            # los gustos de fabian (02/11/2026), con o sin su cara
            'Any face: natural expression, not exaggerated, no shouting, not too serious, not cheeky (no squinting, no tilted head); '
            'only two hands; one single headline. ' +
            f'Big headline text, perfectly spelled exactly as given, with correct accents: «{texto}». ' +
            ('Headline in the upper-center third, nothing important in the bottom 20 %. ' if vertical else 'Text readable at small size. ') +
            'If a phone appears it is shown from the BACK only, never a readable screen. One main object. No extra text, no watermark, '
            'no QR, no WhatsApp, no website names or URLs (nothing like .com or .co), nothing about unlocking phones, '
            'no YouTube duration badge.')


def salida_final(img, formato):
    """Recorte y escala al tamaño de YouTube, JPG < 2 MB."""
    _, W, H = FORMATOS[formato]
    h, w = img.shape[:2]
    if w / h > W / H:
        nw = int(h * W / H)
        img = img[:, (w - nw) // 2:(w - nw) // 2 + nw]
    else:
        nh = int(w * H / W)
        img = img[(h - nh) // 2:(h - nh) // 2 + nh]
    return cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)


def generar(d, elegidas, variantes=2, formato='16x9', idioma='es', cara=None, generar_img=None, llamar=None, revisar_luego=True):
    """Genera las variantes de las ideas elegidas (índices desde 1). GASTA. Devuelve la lista de resultados nuevos."""
    generar_img = generar_img or imagen_ia
    receta = leer(os.path.join(carpeta(d), 'receta.json'))
    lista = (leer(os.path.join(carpeta(d), 'ideas.json'), {}) or {}).get('ideas') or []
    if not receta or not lista:
        raise ValueError('Faltan la receta y las ideas: «🔍 Analizar» y «💡 Ideas» primero.')
    refs = referencias(d)[:MAX_REFS_GPT]
    if cara and os.path.isfile(cara):
        refs = refs + [cara]
    size = FORMATOS[formato][0]
    hechas = leer(os.path.join(carpeta(d), 'generadas.json'), []) or []
    nuevas, cobradas = [], 0
    try:
        for i in elegidas:
            idea = lista[int(i) - 1]
            for v in range(1, int(variantes) + 1):
                img = generar_img(prompt_imagen(receta, idea, idioma, formato, bool(cara)), refs, size)
                cobradas += 1
                nombre = f'idea{int(i)}_v{v}_{idioma}_{formato}_{time.strftime("%H%M%S")}.jpg'
                f = os.path.join(carpeta(d, 'generadas'), nombre)
                final = salida_final(img, formato)
                for q in (92, 85, 78, 70):  # < 2 MB, como pide YouTube
                    ok, buf = cv2.imencode('.jpg', final, [cv2.IMWRITE_JPEG_QUALITY, q])
                    if len(buf) < 2_000_000:
                        break
                buf.tofile(f)
                r = {'archivo': 'generadas/' + nombre, 'idea': int(i), 'variante': v, 'idioma': idioma, 'formato': formato,
                     'texto': idea.get(idioma) if idioma != 'es' else idea['texto'], 'costo_usd': COSTO_IMAGEN, 'fecha': time.strftime('%Y-%m-%d %H:%M')}
                if revisar_luego:
                    try:
                        r['revision'] = revisar(d, r['archivo'], r['texto'], llamar)
                    except (Exception, SystemExit) as e:  # la revisión no frena lo ya generado (y ya cobrado); la IA falla con SystemExit
                        r['revision'] = {'ok': None, 'errores': [f'no se pudo revisar: {e}'[:200]]}
                hechas.append(r)
                nuevas.append(r)
                guardar(os.path.join(carpeta(d), 'generadas.json'), hechas)
    finally:  # lo ya cobrado queda anotado aunque una imagen falle a mitad
        if cobradas:
            gastos = leer(os.path.join(carpeta(d), 'gastos.json'), []) or []
            gastos.append({'fecha': time.strftime('%Y-%m-%d %H:%M'), 'imagenes': cobradas, 'costo_usd': round(cobradas * COSTO_IMAGEN, 2),
                           'modelo': 'gpt-image-2.5-flare', 'calidad': 'high', 'simulado': _simulando()})
            guardar(os.path.join(carpeta(d), 'gastos.json'), gastos)
    return nuevas


# ---------------------------------------------------------------- 5) revisar

def revisar(d, archivo, texto_esperado, llamar=None):
    llamar = llamar or llamar_ia
    f = os.path.join(carpeta(d), archivo)
    prompt = ('Revisa el TEXTO de esta miniatura de YouTube. Debería decir exactamente: «' + str(texto_esperado) + '». Lee lo que '
              'dice de verdad, revisa ortografía y tildes, y si hay letras deformes, cortadas o inventadas. Responde SOLO con JSON: '
              '{"texto_leido": "…", "ortografia_ok": true, "letras_deformes": false, "errores": ["…"]}')
    r = _json(llamar(prompt, [f]))
    if not isinstance(r, dict):
        r = {}
    errores = [str(e) for e in (r.get('errores') or []) if str(e).strip()]
    ok = bool(r.get('ortografia_ok', False)) and not r.get('letras_deformes', True) and not errores
    return {'ok': ok, 'texto_leido': str(r.get('texto_leido') or ''), 'errores': errores}


# ---------------------------------------------------------------- 6) usar como miniatura

def usar(d, archivo):
    """La deja como miniatura elegida del proyecto (Publicar → YouTube) y la copia a subir_youtube/."""
    f = os.path.join(carpeta(d), archivo)
    if not os.path.isfile(f) or os.path.commonpath([os.path.abspath(f), os.path.abspath(carpeta(d))]) != os.path.abspath(carpeta(d)):
        raise ValueError('esa miniatura no existe')
    nombre = 'miniatura_ref_' + os.path.basename(f)
    shutil.copy2(f, os.path.join(d, nombre))
    os.makedirs(os.path.join(d, 'subir_youtube'), exist_ok=True)
    shutil.copy2(f, os.path.join(d, 'subir_youtube', nombre))
    os.makedirs(os.path.join(d, 'youtube'), exist_ok=True)
    guardar(os.path.join(d, 'youtube', 'miniatura.json'), {'archivo': nombre})
    hechas = leer(os.path.join(carpeta(d), 'generadas.json'), []) or []
    for h in hechas:
        h['elegida'] = h.get('archivo') == archivo
    guardar(os.path.join(carpeta(d), 'generadas.json'), hechas)
    return nombre


def estado(d):
    return {'referencias': [os.path.basename(r) for r in referencias(d)], 'receta': leer(os.path.join(carpeta(d), 'receta.json')),
            'ideas': (leer(os.path.join(carpeta(d), 'ideas.json'), {}) or {}).get('ideas') or [],
            'generadas': leer(os.path.join(carpeta(d), 'generadas.json'), []) or [],
            'gastos': leer(os.path.join(carpeta(d), 'gastos.json'), []) or [],
            'elegida': (leer(os.path.join(d, 'youtube', 'miniatura.json'), {}) or {}).get('archivo'),
            'caras': caras(d), 'por_imagen_usd': COSTO_IMAGEN, 'carpeta': carpeta(d)}


def caras(d):
    """Fotos de cara que se pueden pasar como referencia: los avatares del proyecto (o del proyecto hermano) y fotos subidas."""
    pat = [os.path.join(d, 'avatares', '*.png'), os.path.join(d, 'avatares', '*.jpg'), os.path.join(d, 'miniatura', 'cara*.*'),
           os.path.join(d, 'foto_*.jpg')]
    import glob
    return [os.path.relpath(f, d).replace('\\', '/') for p in pat for f in sorted(glob.glob(p))]


# ---------------------------------------------------------------- la app (rutas /api/miniref/...)

def get(h, ruta, q, d):
    if ruta == '/api/miniref/estado':
        return h.responder(estado(d))
    if ruta == '/api/miniref/imagen':  # una referencia o un resultado, para verlo en la pestaña
        f = os.path.abspath(os.path.join(carpeta(d), q.get('f', '')))
        if os.path.commonpath([f, os.path.abspath(carpeta(d))]) != os.path.abspath(carpeta(d)):
            return h.error('ruta no válida', 403)
        return h.servir(f)
    if ruta == '/api/miniref/presupuesto':
        return h.responder(presupuesto(len([x for x in q.get('ideas', '').split(',') if x.strip()]), q.get('variantes') or 2))
    return h.error('no conozco esa ruta', 404)


def _correr(h, d, *args, timeout=1800):
    """Los pasos con IA van en un proceso aparte (como «💡 Sugerir con IA»): la app no se traba mientras piensa."""
    import subprocess
    r = subprocess.run([sys.executable, os.path.abspath(__file__), '--proyecto', d, *args], capture_output=True, text=True,
                       encoding='utf-8', timeout=timeout, cwd=d, env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return h.error(((r.stderr or r.stdout).strip().splitlines() or ['sin respuesta'])[-1][:400])
    return h.responder(out) if out.get('ok') else h.error(out.get('error') or 'falló')


def post(h, ruta, q, largo, d):
    if ruta == '/api/miniref/subir':  # cuerpo = la imagen; ?nombre=
        if largo > 25 * 1024 * 1024:
            return h.error('La imagen es muy grande (máx. 25 MB).')
        try:
            return h.responder({'ok': True, 'nombre': subir(d, q.get('nombre', ''), h.rfile.read(largo))})
        except ValueError as e:
            return h.error(str(e))
    datos = json.loads(h.rfile.read(largo) or b'{}')
    if ruta == '/api/miniref/borrar':
        borrar_ref(d, datos.get('nombre', ''))
        return h.responder({'ok': True})
    if ruta == '/api/miniref/receta':  # la receta editada a mano
        return h.responder({'ok': True, 'receta': guardar_receta(d, datos.get('receta') or {})})
    if ruta == '/api/miniref/ideas_editadas':
        return h.responder({'ok': True, 'ideas': guardar_ideas(d, datos.get('ideas') or [])})
    if ruta == '/api/miniref/analizar':
        return _correr(h, d, 'analizar', timeout=900)
    if ruta == '/api/miniref/ideas':
        return _correr(h, d, 'ideas', timeout=900)
    if ruta == '/api/miniref/generar':  # GASTA: la pestaña ya mostró el costo y fabian confirmó
        if not datos.get('confirmo'):
            return h.error('Falta confirmar el costo antes de generar.')
        vari = datos.get('variantes')  # de 1 a 4, lo mismo que la pestaña mostró en el costo (vacío = 2, como antes)
        vari = min(4, max(1, int(vari) if vari not in (None, '') else 2))
        args = ['generar', '--ideas', ','.join(str(int(x)) for x in datos.get('ideas') or []), '--variantes', str(vari),
                '--formato', '9x16' if datos.get('formato') == '9x16' else '16x9', '--idioma', datos.get('idioma') if datos.get('idioma') in ('es', 'en', 'pt') else 'es']
        if datos.get('cara'):
            cara = os.path.abspath(os.path.join(d, datos['cara']))
            if os.path.commonpath([cara, os.path.abspath(d)]) == os.path.abspath(d) and os.path.isfile(cara):
                args += ['--cara', cara]
        return _correr(h, d, *args, timeout=3600)
    if ruta == '/api/miniref/revisar':
        return _correr(h, d, 'revisar', '--archivo', datos.get('archivo', ''), timeout=600)
    if ruta == '/api/miniref/usar':
        try:
            return h.responder({'ok': True, 'nombre': usar(d, datos.get('archivo', ''))})
        except ValueError as e:
            return h.error(str(e))
    return h.error('no conozco esa ruta', 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('accion', choices=['analizar', 'ideas', 'generar', 'revisar'])
    ap.add_argument('--ideas', default='1')
    ap.add_argument('--variantes', type=int, default=2)
    ap.add_argument('--formato', choices=list(FORMATOS), default='16x9')
    ap.add_argument('--idioma', choices=['es', 'en', 'pt'], default='es')
    ap.add_argument('--cara')
    ap.add_argument('--archivo')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    try:
        if a.accion == 'analizar':
            out = {'receta': analizar(d)}
        elif a.accion == 'ideas':
            out = {'ideas': ideas(d)}
        elif a.accion == 'generar':
            elegidas = [int(x) for x in a.ideas.split(',') if x.strip()]
            nuevas = generar(d, elegidas, a.variantes, a.formato, a.idioma, a.cara)
            out = {'generadas': nuevas, 'costo_usd': round(len(nuevas) * COSTO_IMAGEN, 2)}
        else:
            hechas = leer(os.path.join(carpeta(d), 'generadas.json'), []) or []
            h = next((x for x in hechas if x.get('archivo') == a.archivo), None)
            if not h:
                raise ValueError('esa miniatura no existe')
            h['revision'] = revisar(d, a.archivo, h.get('texto', ''))
            guardar(os.path.join(carpeta(d), 'generadas.json'), hechas)
            out = {'revision': h['revision']}
        print(json.dumps({'ok': True, **out}, ensure_ascii=False))
    except (ValueError, SystemExit) as e:
        print(json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
