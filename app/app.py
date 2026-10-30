"""Estudio de tutoriales: la app con botones.

Abre una página en tu navegador (http://localhost:8765) con un botón por paso. Cada proyecto es una
carpeta dentro de mis_proyectos/ con nombres fijos de archivo, así cada paso sabe qué usar:

  original.mp4        video grabado            guion.json      bloques con texto y montaje
  imagen.png          imagen para bloques "imagen" (opcional)
  material.mp4        material extra para insertos (opcional)
  musica.mp3          pista de música (si falta, se genera y se guarda aquí)
  etiquetas.json  senales.json  insertos.json  trailer.json   (opcionales)
  pistas_trailer/     pistas del tráiler por fase (capturas, audios, texto) + pistas.json
  tarjetas/           imágenes de COMENTARIOS y WHATSAPP para poner encima del video + tarjetas.json
  testimonios/        videos de clientes reales que se intercalan en el tutorial + testimonios.json
  nuevos_modelos/     video corto de los modelos más recientes (la voz dice que el método sirve para ellos) + modelos.json

Uso: python app/app.py   (en Windows: doble clic en iniciar.bat)
"""
import glob, hashlib, json, mimetypes, os, re, shutil, subprocess, sys, tempfile, threading, time, urllib.parse, urllib.request, urllib.error, uuid, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'instalador'))
import guardado  # noqa: E402  todo lo que se descarga queda en descargas_app/
sys.path.insert(0, os.path.join(RAIZ, 'diagnostico'))
import diagnostico  # noqa: E402  informes locales cuando una IA o un paso no completa su trabajo
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
import codificar  # noqa: E402  codifica con la tarjeta NVIDIA si la hay, si no con el procesador
sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))
import conocimiento  # noqa: E402  «🧠 Conocimiento»: lo aprendido de todos tus videos, en mis_conocimientos/
import aprendizaje  # noqa: E402  «🧠 Lo que aprendí»: reglas sacadas de cada corrección tuya en el editor
sys.path.insert(0, os.path.join(RAIZ, 'importantes'))
import importantes  # noqa: E402  «⭐ Cortes importantes»: tramos que se ven enteros y a velocidad normal


sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
import idiomas  # noqa: E402  «🌐 Etiquetas en otro idioma»
sys.path.insert(0, os.path.join(RAIZ, 'comprimir'))
import comprimir  # noqa: E402  «🗜 Comprimir video»: misma calidad, mucho menos peso
sys.path.insert(0, os.path.join(RAIZ, 'subtitulos'))
import subtitulos  # noqa: E402  «💬 Subtítulos» dinámicos en cualquier idioma
sys.path.insert(0, os.path.join(RAIZ, 'celular'))
import celular  # noqa: E402  «📱 Usar desde el celular»: apagado por defecto, con PIN, Wi‑Fi de casa o Tailscale
import flujo  # noqa: E402  aviso al celular, «🌙 Cola de noche» y gastos del mes
sys.path.insert(0, os.path.join(RAIZ, 'youtube'))
import youtube  # noqa: E402  «▶️ YouTube»: publicar, capítulos, retención, comentarios e ideas
import canal as canal_yt  # noqa: E402  «📊 Todo tu canal»: estadísticas de todos tus videos → reglas para la IA
sys.path.insert(0, os.path.join(RAIZ, 'mejoras'))
import mejoras  # noqa: E402  «🎛 Audio e imagen»: pronunciación, sonidos, limpieza, zoom, color, pantalla, revisión, Shorts, miniatura
import recursos  # noqa: E402  «📊 Uso del PC»: procesador, RAM y gráfica mientras la app trabaja
sys.path.insert(0, os.path.join(RAIZ, 'voz'))
from texto_voz import texto_voz  # noqa: E402  el texto de un bloque tal como se mandó a ElevenLabs


def estado_subs(d):
    datos = subtitulos.leer(d)
    lang = datos['idioma']
    try:
        orig = {b['id']: b['texto'] for b in subtitulos.bloques(d)}
    except (OSError, ValueError, KeyError):
        orig = {}
    tabla = datos['textos'].get(lang) or {}
    fuentes = subtitulos.fuentes(d)
    return {'idioma': lang, 'estilo': datos['estilo'], 'fuentes': fuentes, 'hay_guion': bool(orig),
            'duraciones': {f: duracion_original(d, f) for f in fuentes},  # para que «Segundo» llegue hasta el final del video
            'filas': [{'id': k, 'orig': v, 'trad': v if lang == 'es' else tabla.get(k, '')} for k, v in orig.items()]}


# Voz por idioma del video (idioma_video.json del proyecto): Mauricio en español, Brian en inglés (elegida por el autor
# el 28/10/2026). Se cambia con «voces» en ajustes.json: {"en": "<id de voz>"}.
VOCES_DEFECTO = {'es': '94zOad0g7T7K4oa7zhDq', 'en': 'nPczCjzI2devNBz1zQrb'}
NOMBRE_VOZ = {'94zOad0g7T7K4oa7zhDq': 'Mauricio', 'nPczCjzI2devNBz1zQrb': 'Brian'}


def idioma_video(d):
    try:
        return str(json.load(open(os.path.join(d, 'idioma_video.json'), encoding='utf-8')).get('idioma') or 'es')
    except (OSError, ValueError, AttributeError):
        return 'es'


def voz_env(d):
    """La voz y el idioma de un proyecto traducido (vacío si es español: Mauricio, como siempre). Van como variables de
    entorno a todo lo que habla: voz.py, la voz nueva del Short, los testimonios narrados, nuevos modelos y el tráiler."""
    lang = idioma_video(d)
    if lang == 'es':
        return {}
    return {'VOZ_ID': (leer_ajustes().get('voces') or {}).get(lang) or VOCES_DEFECTO.get(lang) or '', 'VOZ_IDIOMA': lang}


def voz_args(d):
    """Lo que se le pasa a voz.py según el idioma del proyecto (nada si es español: Mauricio, como siempre)."""
    e = voz_env(d)
    return (['--voz', e['VOZ_ID']] if e.get('VOZ_ID') else []) + (['--idioma', e['VOZ_IDIOMA']] if e else [])


PRIVADOS = {'ajustes.json', 'ajustes.json.copia'}  # las claves no se sirven nunca


def ruta_segura(rel):
    """La ruta completa de algo DENTRO de la carpeta de la app (relativa, o completa pero adentro); None si se sale o es privado."""
    rel = urllib.parse.unquote(str(rel or '')).strip().strip('"')
    f = os.path.realpath(rel if os.path.isabs(rel) else os.path.join(RAIZ, rel))
    raiz = os.path.realpath(RAIZ)
    if os.path.commonpath([f, raiz]) != raiz or os.path.basename(f).lower() in PRIVADOS or not os.path.exists(f):
        return None
    return f


PAGINA_ABIERTO = ('<!doctype html><meta charset="utf-8"><title>Abierto</title><body style="background:#0b0e1a;color:#e8ecff;'
                  'font:16px system-ui;padding:40px">✓ Lo abrí en tu PC. Ya puedes cerrar esta pestaña.'
                  '<script>setTimeout(() => window.close(), 1200)</script></body>')


def pagina_carpeta(d):
    """Una carpeta de la app en el navegador: escuchas los audios, ves los videos e imágenes, y la abres en el Explorador."""
    import html
    if os.path.isfile(d):
        d = os.path.dirname(d)
    rel = os.path.relpath(d, RAIZ)
    enc = lambda p: urllib.parse.quote(os.path.relpath(p, RAIZ).replace('\\', '/'))
    filas = []
    for n in sorted(os.listdir(d), key=lambda x: (not os.path.isdir(os.path.join(d, x)), x.lower())):
        p = os.path.join(d, n)
        if n.lower() in PRIVADOS or n.startswith('.'):
            continue
        e, nom = os.path.splitext(n)[1].lower(), html.escape(n)
        if os.path.isdir(p):
            filas.append(f'<div class="f">📁 <a href="/carpeta?ruta={enc(p)}">{nom}</a></div>')
        elif e in ('.mp3', '.wav', '.m4a', '.ogg', '.aac'):
            filas.append(f'<div class="f">🔊 <b>{nom}</b><br><audio controls preload="none" src="/ver?ruta={enc(p)}"></audio></div>')
        elif e in ('.mp4', '.webm', '.mov', '.mkv'):
            filas.append(f'<div class="f">🎬 <b>{nom}</b> <span>({os.path.getsize(p) / 1e6:.0f} MB)</span><br>'
                         f'<video controls preload="metadata" src="/ver?ruta={enc(p)}"></video></div>')
        elif e in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
            filas.append(f'<div class="f">🖼 <b>{nom}</b><br><img src="/ver?ruta={enc(p)}"></div>')
        else:
            filas.append(f'<div class="f">📄 <a href="/ver?ruta={enc(p)}" target="_blank">{nom}</a></div>')
    arriba = '' if os.path.realpath(d) == os.path.realpath(RAIZ) else f'<a href="/carpeta?ruta={enc(os.path.dirname(d))}">⬆ Subir</a> · '
    return f"""<!doctype html><meta charset="utf-8"><title>{html.escape(os.path.basename(d))}</title>
<style>body{{background:#0b0e1a;color:#e8ecff;font:15px system-ui;padding:20px;max-width:1100px;margin:auto}}a{{color:#7cc4ff}}
.f{{background:#151a2e;border:1px solid #2a3150;border-radius:10px;padding:10px 12px;margin:8px 0}}audio{{width:100%;margin-top:6px}}
video,img{{max-width:100%;max-height:60vh;margin-top:6px;border-radius:8px}}span{{color:#9aa3c0}}
.b{{display:inline-block;background:#ff2bd6;color:#fff;padding:8px 14px;border-radius:10px;text-decoration:none}}</style>
<h2>📁 {html.escape(os.path.basename(d))}</h2><p style="color:#9aa3c0">{html.escape(d)}</p>
<p>{arriba}<a class="b" href="/abrir?ruta={enc(d)}" target="_blank">📂 Abrir en el Explorador</a></p>
{''.join(filas) or '<p>Carpeta vacía.</p>'}"""


def estado_idiomas(d, lang=''):
    """Con qué idioma se dibujan las etiquetas y la tabla original → traducción de un idioma."""
    datos = idiomas.leer(d)
    lang = (lang or (datos['idioma'] if datos['idioma'] != idiomas.ORIGINAL else 'en')).lower()
    tabla = datos['traducciones'].get(lang) or {}
    return {'idioma': datos['idioma'], 'lang': lang, 'nombres': idiomas.NOMBRES,
            'hechos': sorted(datos['traducciones']), 'filas': [{'orig': t, 'trad': tabla.get(t, '')} for t in idiomas.textos(d)]}


def para_chat(d):
    """Todo lo que marcaste en la app para un video (cortes importantes, señales dibujadas, capturas con etiqueta), en un
    texto para pegar en el chat de Claude y en para_claude_marcas.json (va también en el paquete para la nube)."""
    mm = lambda s: f'{int(float(s) // 60)}:{float(s) % 60:04.1f}'
    imp = importantes.leer(d)
    try:
        marcas = json.load(open(os.path.join(d, 'marcas_senales', 'marcas.json'), encoding='utf-8')).get('MARCAS', [])
    except (OSError, ValueError, AttributeError):
        marcas = []
    sen = [m for m in marcas if isinstance(m, dict)]
    datos = {'proyecto': os.path.basename(d), 'cortes_importantes': imp,
             'senales': [{k: m.get(k) for k in ('segundo', 'video', 'forma', 'zona', 'etiqueta', 'nota', 'tipo', 'archivo') if m.get(k)} for m in sen]}
    forma = {'circulo': 'círculo', 'flecha': 'flecha', 'caja': 'recuadro'}
    lineas = [f"MARCAS DEL AUTOR PARA EL VIDEO «{datos['proyecto']}» (hechas en la app; respétalas al armar el guion y el video)", '']
    lineas.append('⭐ CORTES IMPORTANTES (se muestran enteros y a velocidad normal, nunca acelerados ni recortados):')
    lineas += [f"- {mm(x['inicio'])} a {mm(x['fin'])} de la grabación original" + (f": {x['nota']}" if x['nota'] else '') for x in imp] or ['- (ninguno)']
    lineas += ['', '🎯 SEÑALES Y ETIQUETAS (segundo del video indicado; zona en % del cuadro: x, y = centro; w, h = tamaño):']
    for m in datos['senales']:
        partes = [f"- {m.get('segundo', '¿segundo?')}" + (f" de {m['video']}" if m.get('video') else ''),
                  forma.get(m.get('forma'), m.get('forma') or m.get('tipo') or '')]
        if m.get('zona'):
            z = m['zona']
            partes.append(f"en x {z.get('x')} %, y {z.get('y')} % (tamaño {z.get('w')} × {z.get('h')} %)")
        if m.get('etiqueta'):
            partes.append(f"etiqueta «{m['etiqueta']}»")
        if m.get('nota'):
            partes.append(f"nota: {m['nota']}")
        lineas.append(' · '.join(p for p in partes if p))
    if not datos['senales']:
        lineas.append('- (ninguna)')
    texto = '\n'.join(lineas) + '\n'
    json.dump(datos, open(os.path.join(d, 'para_claude_marcas.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(d, 'para_claude_marcas.txt'), 'w', encoding='utf-8').write(texto)
    return texto


def estado_importantes(d, aplicar=False):
    """Los cortes importantes del proyecto y cómo quedan en el guion. Con aplicar, deja a ×1 los bloques que los tocan."""
    lista, g = importantes.leer(d), None
    f = os.path.join(d, 'guion.json')
    try:
        g = json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        pass
    bloques = (g.get('bloques') if isinstance(g, dict) else g) or []
    msg = ''
    if aplicar and bloques:
        frenados = importantes.marcar(bloques, lista)
        if frenados:
            shutil.copyfile(f, f + '.antes_importantes')
            importantes.retiempos(bloques)
            json.dump(g, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            msg = f"Dejé a velocidad normal {', '.join(frenados)}. Vuelve a pulsar «▶ Hacer todo» para rearmar el video."
    afectados = [{'id': b.get('id'), 'ancla': b.get('ancla', ''), 'desde': b['montaje'].get('src_inicio'),
                  'hasta': b['montaje'].get('src_fin'), 'velocidad': b['montaje'].get('velocidad') or 1}
                 for b in bloques if isinstance(b.get('montaje'), dict) and importantes.toca(b['montaje'], lista)]
    return {'lista': lista, 'afectados': afectados, 'sin_mostrar': importantes.sin_mostrar(bloques, lista) if bloques else [],
            'hay_guion': bool(bloques), 'msg': msg}
guardado.preparar_entorno()
PROYECTOS = os.path.join(RAIZ, 'mis_proyectos')
MUSICA_FIJA = os.path.join(RAIZ, 'mis_musica', 'musica_fija.mp3')  # «📌 Usar en todos los videos»: la misma pista para todos
ESTILOS = os.path.join(RAIZ, 'mis_estilos')  # panel Alimentación: un perfil de estilo por canal, para todos los proyectos
PUERTO = int(os.environ.get('PUERTO', 8765))
PY = sys.executable
# en Windows, sin esto cada paso abre su propia ventana negra cuando la app corre sin consola (Estudio.exe)
SIN_VENTANA = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
LATIDO = [time.time()]  # última vez que la página dio señales de vida
os.makedirs(PROYECTOS, exist_ok=True)
os.makedirs(ESTILOS, exist_ok=True)

SUBIBLES = {'original': 'original.mp4', 'imagen': 'imagen.png', 'material': 'material.mp4', 'musica': 'musica.mp3'}
EDITABLES = ['idea.txt', 'acortar.json', 'guion.json', 'etiquetas.json', 'senales.json', 'insertos.json', 'trailer.json', 'referencias.json', 'preguntas_guion.json', 'preguntas_trailer.json',
             'guion_quitados.json']  # los bloques que quitaste en el editor de guion, por si te arrepientes
AJUSTES = os.path.join(AQUI, 'ajustes.json')
IMAGENES = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
VIDEOS = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'}
# grupos de archivos que se arman desde la app: carpeta, json, apartados y qué se puede subir
GRUPOS = {
    'pistas': ('pistas_trailer', 'pistas.json', ['ANTES', 'DURANTE', 'DESPUES'], IMAGENES | {'.mp3', '.wav', '.m4a', '.ogg', '.webm', '.opus', '.aac'}),
    'tarjetas': ('tarjetas', 'tarjetas.json', ['COMENTARIOS', 'WHATSAPP'], IMAGENES),
    'testimonios': ('testimonios', 'testimonios.json', ['TESTIMONIOS'], VIDEOS),
    'modelos': ('nuevos_modelos', 'modelos.json', ['MODELOS'], VIDEOS),
    'marcas': ('marcas_senales', 'marcas.json', ['MARCAS'], IMAGENES | {'.mp3', '.wav', '.m4a', '.ogg', '.webm', '.opus', '.aac'}),
}
PROVEEDORES = {
    'Claude (Anthropic)': {'url': 'https://api.anthropic.com', 'modelo': 'claude-opus-5-5', 'imagenes': True, 'tipo': 'claude'},
    'Claude · Opus 5.5 con visión': {'url': 'https://api.anthropic.com', 'modelo': 'claude-opus-5-5', 'imagenes': True, 'tipo': 'claude'},
    'Claude · Sonnet 5.5 con visión (más barata)': {'url': 'https://api.anthropic.com', 'modelo': 'claude-sonnet-5-5', 'imagenes': True,
                                                     'tipo': 'claude'},
    'OpenAI (GPT)': {'url': 'https://api.openai.com/v1', 'modelo': 'gpt-4o', 'imagenes': True},
    'OpenAI · GPT-6 con visión': {'url': 'https://api.openai.com/v1', 'modelo': 'gpt-6.1-sol', 'imagenes': True},
    'OpenAI · GPT-5 con visión': {'url': 'https://api.openai.com/v1', 'modelo': 'gpt-5', 'imagenes': True},
    'OpenAI · GPT-4.1 con visión': {'url': 'https://api.openai.com/v1', 'modelo': 'gpt-4.1', 'imagenes': True},
    'Qwen-VL multimodal (Alibaba Cloud)': {'url': 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', 'modelo': 'qwen-vl-max',
                                           'imagenes': True, 'json': False},
    'Qwen-VL multimodal (OpenRouter)': {'url': 'https://openrouter.ai/api/v1', 'modelo': 'qwen/qwen2.5-vl-72b-instruct',
                                        'imagenes': True, 'json': False},
    'DeepSeek': {'url': 'https://api.deepseek.com', 'modelo': 'deepseek-chat', 'imagenes': False},
    'DeepSeek · Flash con visión': {'url': 'https://api.deepseek.com', 'modelo': 'deepseek-flash', 'imagenes': True},
    'DeepSeek · V4 Pro': {'url': 'https://api.deepseek.com', 'modelo': 'deepseek-v4-pro', 'imagenes': False},
    'Gemini': {'url': 'https://generativelanguage.googleapis.com/v1beta/openai', 'modelo': 'gemini-2.0-flash', 'imagenes': True},
    'Ollama (en tu PC, gratis)': {'url': 'http://localhost:11434/v1', 'modelo': 'gemma3:12b', 'imagenes': True},
    'Ollama · Gemma 3 liviana (PC sencilla)': {'url': 'http://localhost:11434/v1', 'modelo': 'gemma3:4b', 'imagenes': True},
    'Ollama · Qwen 2.5 VL': {'url': 'http://localhost:11434/v1', 'modelo': 'qwen2.5vl:7b', 'imagenes': True},
    'Ollama · Qwen 3 VL (multimodal)': {'url': 'http://localhost:11434/v1', 'modelo': 'qwen3-vl:8b', 'imagenes': True},
    'LM Studio (en tu PC, gratis)': {'url': 'http://localhost:1234/v1', 'modelo': 'local-model', 'imagenes': True},
}
EJEMPLOS = {
    'guion.json': 'proyectos/pico2/guion_pico_largo.json',
    'etiquetas.json': 'etiquetas/ejemplos/pico2_etiquetas.json',
    'senales.json': 'senales/ejemplos/pico2_senales.json',
    'insertos.json': 'insertos/ejemplos/pico2_insertos.json',
    'trailer.json': 'trailer/ejemplos/pico2_trailer.json',
}


def m(*p):
    return os.path.join(RAIZ, *p)


def existe(d, f):
    return os.path.exists(os.path.join(d, f))


LARGO_VERSION = 2  # sube cuando cambia el margen de duración: los guiones revisados con el margen viejo se vuelven a medir


def edicion(d):
    """edicion.json del proyecto: volumen de la música, dónde va el tráiler…"""
    try:
        e = json.load(open(os.path.join(d, 'edicion.json'), encoding='utf-8'))
        return e if isinstance(e, dict) else {}
    except (OSError, ValueError):
        return {}


def guion_fuera_de_largo(d):
    """Un guion hecho antes del control de duración que deja el video muy lejos del largo de la grabación
    (o de «que dure unos N minutos» en la idea)."""
    try:
        g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
        if g.get('largo_revisado') == LARGO_VERSION or not existe(d, 'original.mp4'):
            return False
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                    os.path.join(d, 'original.mp4')], capture_output=True, text=True, **SIN_VENTANA).stdout)
        idea = open(os.path.join(d, 'idea.txt'), encoding='utf-8').read() if existe(d, 'idea.txt') else ''
        m = re.search(r'(\d+)\s*(?:a\s*\d+\s*)?min', idea)
        meta = int(m.group(1)) * 60 if m else dur
        t = float(g.get('duracion_s') or sum(b.get('fin_max', 0) - b.get('inicio_min', 0) for b in g.get('bloques', [])))
        return not (meta * 0.9 <= t <= meta * 1.15)
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def borrar_seguro(f, intentos=10):
    """Borra un archivo; en Windows, si el reproductor lo tiene abierto, reintenta unos segundos. Devuelve si se pudo."""
    for k in range(intentos):
        try:
            os.remove(f)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(0.5)
    return False


_DURACIONES = {}


def duracion_original(d, nombre='original.mp4'):
    """Lo que dura tu grabación (u otro video del proyecto), en caché mientras el archivo no cambie."""
    f = os.path.join(d, nombre)
    if not os.path.exists(f):
        return 0
    clave = (f, os.path.getmtime(f))
    if clave not in _DURACIONES:
        try:
            _DURACIONES[clave] = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                                      capture_output=True, text=True, **SIN_VENTANA).stdout)
        except ValueError:
            _DURACIONES[clave] = 0
        except OSError:  # sin ffprobe: la página carga igual y el paso avisa que falta ffmpeg (no se guarda, por si lo instalas)
            return 0
    return _DURACIONES[clave]


DESFASE_VOZ = 0.3  # cada bloque de voz suena 0,3 s después de su inicio_min (igual que mezclar_voz, etiquetas y señales)


def leer_srt(f):
    crudo = open(f, 'rb').read()
    try:
        texto = crudo.decode('utf-8')
    except UnicodeDecodeError:
        texto = crudo.decode('cp1252', errors='replace')
    seg = lambda x: (lambda h, m, s: int(h) * 3600 + int(m) * 60 + float(s.replace(',', '.')))(*x.strip().split(':'))
    subs = []
    for trozo in re.split(r'\n\s*\n', texto.replace('\r', '')):
        lineas = [x for x in trozo.strip().split('\n') if x.strip()]
        k = next((i for i, x in enumerate(lineas) if '-->' in x), None)
        if k is None:
            continue
        a, b = lineas[k].split('-->')
        subs.append({'ini': round(seg(a), 2), 'fin': round(seg(b), 2), 'texto': ' '.join(lineas[k + 1:])})
    return subs


def escribir_srt(f, subs):
    ts = lambda x: f'{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(round(x % 1 * 1000)) % 1000:03d}'
    open(f, 'w', encoding='utf-8').write('\n'.join(f"{k}\n{ts(float(x['ini']))} --> {ts(float(x['fin']))}\n{str(x['texto']).strip()}\n"
                                                  for k, x in enumerate(subs, 1)))


def linea_tiempo(d):
    """Todo lo del proyecto en segundos del video con voz (antes de testimonios y nuevos modelos, que meten cortes):
    para el editor por pistas."""
    if m('etiquetas') not in sys.path:
        sys.path.insert(0, m('etiquetas'))
    from etiquetas import buscar
    leer = lambda f, defecto: json.load(open(os.path.join(d, f), encoding='utf-8')) if existe(d, f) else defecto
    guion = leer('guion.json', {'bloques': []})
    bloques, inicio, alin, original = [], {}, {}, {}
    for b in guion.get('bloques', []):
        if b.get('inicio_min') is None:
            continue
        inicio[b['id']] = b['inicio_min']
        original[b['id']] = b.get('texto_original')  # versión traducida: la frase de la etiqueta sigue en español
        f_al = os.path.join(d, 'voz', f"{b['id']}.align.json")
        al = json.load(open(f_al, encoding='utf-8')) if os.path.exists(f_al) else None
        alin[b['id']] = al
        dur = (al['character_end_times_seconds'][-1] if al and al.get('character_end_times_seconds') else b.get('voz_real_s')) or 0
        bloques.append({'id': b['id'], 'texto': b.get('texto', ''), 'ini': round(b['inicio_min'] + DESFASE_VOZ, 2), 'dur': round(dur, 2),
                        'voz': existe(d, os.path.join('voz', f"{b['id']}.mp3")), 'desde': b['inicio_min'],
                        'hasta': b.get('fin_max', b['inicio_min']), 'ancla': b.get('ancla', ''), 'montaje': b.get('montaje') or {}})

    def cuando(x, retraso=0):
        if x.get('t') is not None:
            return round(float(x['t']) + retraso, 2)
        if x.get('en') is not None and x.get('bloque') in inicio:
            return round(inicio[x['bloque']] + DESFASE_VOZ + float(x['en']) + retraso, 2)
        al = alin.get(x.get('bloque'))
        t = buscar(al, x.get('frase', ''), original.get(x.get('bloque'))) if al else None
        return None if t is None else round(inicio[x['bloque']] + DESFASE_VOZ + t + retraso, 2)
    etiquetas = [{**e, '_t': cuando(e)} for e in leer('etiquetas.json', [])]
    senales = [{**x, '_t': cuando(x, x.get('retraso', 0))} for x in leer('senales.json', [])]
    base = next((v for v in ('4_musica.mp4', '3_voz.mp4', '1_montaje.mp4') if existe(d, v)), None)
    edicion = leer('edicion.json', {})
    return {'base': base, 'duracion': duracion_original(d, base) if base else 0, 'bloques': bloques,
            'etiquetas': etiquetas, 'senales': senales, 'subtitulos': leer_srt(os.path.join(d, '3_voz.srt')) if existe(d, '3_voz.srt') else [],
            'musica': {'volumen': edicion.get('musica_volumen', 0.22), 'fija': os.path.exists(MUSICA_FIJA), 'propia': existe(d, 'musica.mp3')},
            'extras': [p['id'] for p in PASOS if p['id'] in EXTRAS and (existe(d, p['produce']) or p['id'] in capas_hechas(d)) and p['produce'] != 'FINAL.mp4']
            + (['trailer'] if existe(d, 'trailer.mp4') else [])}


def capas_hechas(d):
    """Qué extras lleva el video cuando se pegaron juntos en una sola pasada (no queda un mp4 por cada uno)."""
    try:
        return json.load(open(os.path.join(d, 'capas_hechas.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []


def etiquetas_viejas(d, archivo='etiquetas.json'):
    """Si etiquetas.json (o senales.json) es de otro guion (bloques que ya no están o frases que la voz ya no dice): hay que rehacerlas."""
    import unicodedata
    n = lambda c: ' '.join(''.join(x for x in unicodedata.normalize('NFD', str(c).lower()) if unicodedata.category(x) != 'Mn').split())
    try:
        textos = {b['id']: n(b.get('texto', '')) for b in json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))['bloques']}
        lista = json.load(open(os.path.join(d, archivo), encoding='utf-8'))
    except (OSError, ValueError, KeyError, TypeError):
        return False
    # las que pusiste o moviste a mano en el editor por pistas (traen su segundo «t») no cuentan: son tuyas
    return bool(lista) and any(n(e.get('frase', '')) not in textos.get(e.get('bloque'), '') for e in lista
                               if e.get('t') is None and e.get('en') is None)


def senales_viejas(d):
    """Las flechas guardan el lugar de la pieza en el cuadro: si el video se volvió a montar después, o sus frases ya no
    están en el guion, ese lugar puede ser de otra imagen y hay que ubicarlas de nuevo."""
    s, m = os.path.join(d, 'senales.json'), os.path.join(d, '1_montaje.mp4')
    if not os.path.exists(s):
        return False
    return etiquetas_viejas(d, 'senales.json') or (os.path.exists(m) and os.path.getmtime(m) > os.path.getmtime(s))


def marcas_nuevas(d):
    """Si tus capturas o notas de «Flechas y círculos» son más nuevas que senales.json."""
    f = os.path.join(d, 'marcas_senales', 'marcas.json')
    s = os.path.join(d, 'senales.json')
    return os.path.exists(f) and (not os.path.exists(s) or os.path.getmtime(f) > os.path.getmtime(s))


def unir_videos(destino, n):
    """Une en orden los n videos subidos juntos (destino.parte01, .parte02…) en uno solo. Si son de la misma cámara se
    pegan tal cual (rápido, sin perder calidad); si no, se pasan a un mismo formato. Devuelve un resumen."""
    partes = [f'{destino}.parte{k:02d}' for k in range(1, n + 1)]
    faltan = [os.path.basename(x) for x in partes if not os.path.exists(x)]
    if faltan:
        raise RuntimeError('faltan partes: ' + ', '.join(faltan))
    lista = destino + '.lista.txt'
    with open(lista, 'w', encoding='utf-8') as f:
        f.writelines(f"file '{os.path.basename(x)}'\n" for x in partes)
    dur = lambda f: float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                         capture_output=True, text=True, **SIN_VENTANA).stdout.strip() or 0)
    suma = sum(dur(x) for x in partes)
    tmp = destino + '.unido.mp4'
    base = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.basename(lista)]
    cwd = os.path.dirname(destino)
    formato = lambda f: subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                                        'stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels',
                                        '-of', 'csv=p=0', f], capture_output=True, text=True, **SIN_VENTANA).stdout
    iguales = len({formato(x) for x in partes}) == 1  # misma cámara y mismos ajustes: se pueden pegar sin recodificar
    r = subprocess.run(base + ['-c', 'copy', '-movflags', '+faststart', os.path.basename(tmp)], cwd=cwd, capture_output=True,
                       **SIN_VENTANA) if iguales else None
    modo = 'pegados tal cual'
    if not iguales or r.returncode != 0 or abs(dur(tmp) - suma) > max(2.0, suma * 0.01):  # formatos distintos: se igualan
        r = codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + sum((['-i', os.path.basename(x)] for x in partes), []) +
                           ['-filter_complex', ''.join(f'[{k}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1,'
                                                       f'fps=30,setsar=1[v{k}];' + (f'[{k}:a]aresample=48000,aformat=channel_layouts=stereo[a{k}];' if 'audio' in formato(x)
                                                       else f'aevalsrc=0|0:s=48000:d={dur(x):.3f}[a{k}];')  # sin sonido: silencio
                                                       for k, x in enumerate(partes)) +
                            ''.join(f'[v{k}][a{k}]' for k in range(n)) + f'concat=n={n}:v=1:a=1[v][a]',
                            '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-c:a', 'aac',
                            '-b:a', '192k', '-movflags', '+faststart', os.path.basename(tmp)], cwd=cwd, capture_output=True, **SIN_VENTANA)
        modo = 'pasados a un mismo formato'
        if r.returncode != 0:
            raise RuntimeError('no pude unir los videos: ' + r.stderr.decode(errors='replace')[-300:])
    os.replace(tmp, destino)
    for x in partes + [lista]:
        os.remove(x)
    return f'{n} videos unidos en orden ({modo}), {int(suma // 60)}:{int(suma % 60):02d} en total'


def srt_de(d, video):
    """Los subtítulos que van con `video`: los pasos que meten cortes (testimonios, nuevos modelos) dejan los suyos corridos."""
    for v in ('9_modelos', '8_testimonios'):
        if video and video >= v and existe(d, v + '.srt'):
            return v + '.srt'
    return '3_voz.srt'


def trailer_pendiente(d):
    """Falta el tráiler, o cambiaste las pistas del tráiler después de armarlo: la IA lo vuelve a elegir."""
    f, t = os.path.join(d, 'pistas_trailer', 'pistas.json'), os.path.join(d, 'trailer.json')
    return not os.path.exists(t) or (os.path.exists(f) and os.path.getmtime(f) > os.path.getmtime(t))


def ultimo_video(d, hasta):
    """El video más avanzado de la cadena antes del paso `hasta`."""
    cadena = ['1_montaje.mp4', '2_insertos.mp4', '3_voz.mp4', '4_musica.mp4', '5_etiquetas.mp4', '6_senales.mp4', '7_tarjetas.mp4', '7b_logos.mp4', '8_testimonios.mp4', '9_modelos.mp4']
    previos = cadena[:cadena.index(hasta)] if hasta in cadena else cadena
    for f in reversed(previos):
        if existe(d, f):
            return f
    return None


def comandos(paso, d, op):
    """Lista de comandos (cada uno una lista de argumentos) para un paso. cwd = carpeta del proyecto."""
    if paso in mejoras.IDS:
        return mejoras.comandos(paso, d, op, PY, AJUSTES)
    g = ['--guion', 'guion.json']
    if paso == 'transcribir':
        motor = op.get('motor', 'scribe')
        return [[PY, m('transcripcion', 'transcribir.py'), '--video', 'original.mp4', '--salida', 'transcripcion', '--motor', motor]]
    if paso == 'voz':
        return [[PY, m('voz', 'voz.py')] + g + ['--salida', 'voz'] + voz_args(d)]
    if paso == 'montaje':
        c = [PY, m('montaje', 'montaje.py'), '--original', 'original.mp4'] + g + ['--salida', '1_montaje.mp4']
        if existe(d, 'imagen.png'):
            c += ['--imagen', 'imagen.png']
        if str(op.get('calidad', '1080')) in ('720', '480', '360'):
            c += ['--calidad', str(op['calidad'])]
        if edicion(d).get('estabilizar', True):  # quita el temblor de la cámara en mano: medido con tu grabación, lo baja a la mitad (el montaje tarda unas 3 veces más)
            c.append('--estabilizar')
        elif op.get('borrador'):
            c.append('--borrador')
        return [c]
    if paso == 'insertos':
        return [[PY, m('insertos', 'insertos.py')] + g + ['--voz', 'voz', '--insertos', 'insertos.json', '--video', '1_montaje.mp4', '--salida', '2_insertos.mp4']]
    if paso == 'mezclar':
        base = '2_insertos.mp4' if existe(d, '2_insertos.mp4') else '1_montaje.mp4'
        return [[PY, m('voz', 'mezclar_voz.py'), base, 'guion.json', 'voz', '3_voz.mp4']]
    if paso == 'musica':
        c = [PY, m('musica', 'musica.py'), '--video', '3_voz.mp4', '--salida', '4_musica.mp4']
        vol = (json.load(open(os.path.join(d, 'edicion.json'), encoding='utf-8')) if existe(d, 'edicion.json') else {}).get('musica_volumen')
        if vol is not None:  # el volumen que elegiste en el editor por pistas
            c += ['--volumen', f'{min(max(float(vol), 0), 1):g}']
        if os.path.exists(MUSICA_FIJA):  # la música fija manda sobre la del proyecto (no se genera otra)
            c += ['--pista', MUSICA_FIJA]
        else:
            c += ['--pista', 'musica.mp3'] if existe(d, 'musica.mp3') else ['--guardar_pista', 'musica.mp3']
        if op.get('prompt'):
            c += ['--prompt', op['prompt']]
        return [c]
    # con dos o más de etiquetas, flechas y tarjetas en la tanda, cada uno solo dibuja su capa sobre el video base y
    # el paso «capas» las pega todas en una sola codificación (antes eran hasta tres)
    capa = (lambda n: ['--capa', os.path.join(CAPAS_DIR, n + '.json')]) if op.get('_capas') else (lambda n: [])
    base = (lambda hasta: ultimo_video(d, '5_etiquetas.mp4')) if op.get('_capas') else (lambda hasta: ultimo_video(d, hasta))
    if paso == 'etiquetas':
        return [[PY, m('etiquetas', 'etiquetas.py')] + g + ['--voz', 'voz', '--etiquetas', 'etiquetas.json', '--video', base('5_etiquetas.mp4'), '--salida', '5_etiquetas.mp4'] + capa('etiquetas')]
    if paso == 'senales':
        return [[PY, m('senales', 'senales.py')] + g + ['--voz', 'voz', '--senales', 'senales.json', '--video', base('6_senales.mp4'), '--salida', '6_senales.mp4'] + capa('senales')]
    if paso == 'tarjetas':
        return [[PY, m('tarjetas', 'tarjetas.py'), '--video', base('7_tarjetas.mp4'), '--tarjetas', os.path.join('tarjetas', 'tarjetas.json'),
                 '--srt', '3_voz.srt', '--salida', '7_tarjetas.mp4'] + capa('tarjetas')]
    if paso == 'logos':  # tus logos (Android 15, 16, 17, MagicOS…) cuando la voz los nombra: mis_conocimientos/logos
        return [[PY, m('logos', 'logos.py'), '--video', base('7b_logos.mp4'), '--guion', 'guion.json', '--voz', 'voz',
                 '--logos', LOGOS_DIR, '--salida', '7b_logos.mp4'] + capa('logos')]
    if paso == 'capas':
        return [[PY, m('capas', 'capas.py'), '--video', ultimo_video(d, '5_etiquetas.mp4'), '--carpeta', CAPAS_DIR,
                 '--orden', ','.join(f"{x}:{next(p['produce'] for p in PASOS if p['id'] == x)}" for x in CAPAS)]]
    if paso == 'testimonios':
        return [[PY, m('testimonios', 'testimonios.py'), '--video', ultimo_video(d, '8_testimonios.mp4'),
                 '--testimonios', os.path.join('testimonios', 'testimonios.json'), '--srt', '3_voz.srt', '--salida', '8_testimonios.mp4']]
    if paso == 'nuevos_modelos':
        v = ultimo_video(d, '9_modelos.mp4')
        return [[PY, m('nuevos_modelos', 'nuevos_modelos.py'), '--video', v, '--modelos', os.path.join('nuevos_modelos', 'modelos.json'),
                 '--srt', srt_de(d, v), '--salida', '9_modelos.mp4', '--ajustes', AJUSTES]]
    if paso == 'trailer':
        unir = ultimo_video(d, None)  # testimonios y nuevos modelos corren los subtítulos: se usan los suyos
        srt = srt_de(d, unir)
        return [[PY, m('trailer', 'trailer.py'), '--video', 'original.mp4', '--plan', 'trailer.json', '--salida', 'trailer.mp4',
                 '--unir', unir, '--final', 'FINAL.mp4', '--srt', srt, '--donde', edicion(d).get('trailer_donde', 'inicio')]]
    if paso == 'trailer_version':  # «▶ Ver» de cada IA: su tráiler armado aparte (sin voz = gratis), para compararlos
        v = re.sub(r'[^a-z]', '', str(op.get('v') or ''))
        plan = f'trailer_{v}.json'
        if not v or not existe(d, plan):
            raise ValueError('esa propuesta del tráiler ya no está')
        if op.get('sin_voz'):
            t = json.load(open(os.path.join(d, plan), encoding='utf-8'))
            t.pop('voz', None)
            plan = f'trailer_{v}.sinvoz.json'
            json.dump(t, open(os.path.join(d, plan), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return [[PY, m('trailer', 'trailer.py'), '--video', 'original.mp4', '--plan', plan, '--salida', f'trailer_{v}.mp4']]
    if paso == 'trailer_solo':  # «🎬 Ver solo el tráiler»: antes que el video, solo con tu grabación (la voz queda para después)
        return [[PY, m('trailer', 'trailer.py'), '--video', 'original.mp4', '--plan', 'trailer.json', '--salida', 'trailer.mp4']]
    if paso == 'short':  # «📱 Short»: vertical 9:16 con lo más importante, reencuadrado y con subtítulos (sin gastar créditos)
        return [[PY, m('short', 'short.py'), '--proyecto', '.', '--duracion', str(max(10, min(180, float(op.get('duracion') or 60))))]
                + (['--voz-nueva'] if op.get('voz_nueva') else [])]
    if paso == 'trailer_ia':  # sin pistas propias la IA elige sola las mejores tomas ANTES · DURANTE · DESPUÉS
        return [[PY, m('ia', 'ia.py'), '--proyecto', '.', '--tarea', 'trailer', '--modo', 'api', '--ajustes', AJUSTES]
                + (['--varias'] if op.get('varias') else [])]
    if paso == 'etiquetas_ia':
        return [[PY, m('ia', 'ia.py'), '--proyecto', '.', '--tarea', 'etiquetas', '--modo', 'api', '--ajustes', AJUSTES]]
    if paso == 'senales_ia':
        return [[PY, m('ia', 'ia.py'), '--proyecto', '.', '--tarea', 'senales', '--modo', 'api', '--ajustes', AJUSTES,
                 '--video', ultimo_video(d, '6_senales.mp4')]]
    if paso == 'guion_ia':  # el guion sale solo del video: transcripción + capturas + idea y estilo si los hay
        return [[PY, m('ia', 'ia.py'), '--proyecto', '.', '--tarea', 'guion', '--modo', 'api', '--ajustes', AJUSTES]
                + (['--ajustar-largo'] if op.get('ajustar_largo') else []) + (['--respuestas'] if op.get('respuestas') else [])
                + (['--ajustar-humor'] if op.get('ajustar_humor') else []) + (['--combinar'] if op.get('combinar') else [])
                + (['--otro', '--pedido', str(op.get('pedido') or '')[:1000]] if op.get('otro') else [])
                + (['--ideas'] if op.get('ideas') else []) + (['--reintentar-varias'] if op.get('reintentar') else [])]
    if paso == 'revisar_imagen':  # lo que quedó del guion: cada bloque contra su imagen, después de que lo aprobaste
        return [[PY, m('ia', 'ia.py'), '--proyecto', '.', '--tarea', 'guion', '--modo', 'api', '--ajustes', AJUSTES, '--revisar-imagen']
                + (['--forzar'] if op.get('forzar') else [])]
    if paso == 'ia':
        c = [PY, m('ia', 'ia.py'), '--proyecto', '.', '--tarea', op['tarea'], '--modo', op['modo'], '--ajustes', AJUSTES]
        if op['modo'] == 'revisar':
            c += ['--entrada', 'ia_respuesta_pegada.txt']
            if op.get('editor'):  # lo escribiste tú en el editor de guion: tus palabras no se cambian, solo se avisa
                c += ['--sin-variar']
        return [c]
    if paso == 'alimentar':
        return [[PY, m('alimentacion', 'alimentacion.py'), '--estilo', carpeta_estilo(op.get('estilo')), '--ajustes', AJUSTES]]
    if paso == 'exportar':  # una o varias calidades a la vez (cada una queda como FINAL_<altura>p.mp4); y, si se pide, solo el audio en FINAL.mp3
        alturas = [int(x) for x in (op.get('alturas') or ([] if op.get('mp3') else [op.get('altura', 480)]))]
        quiere_mp3 = bool(op.get('mp3'))
        if any(h not in (1080, 720, 480, 360) for h in alturas) or (not alturas and not quiere_mp3):
            raise ValueError('calidad no válida')
        # FINAL.mp4, o el video más avanzado si no hay FINAL o si es más nuevo (extras puestos después del final)
        ultimo = ultimo_video(d, None)
        fuente = 'FINAL.mp4' if existe(d, 'FINAL.mp4') and (not ultimo or os.path.getmtime(os.path.join(d, 'FINAL.mp4'))
                                                            >= os.path.getmtime(os.path.join(d, ultimo))) else ultimo
        if not fuente:
            raise RuntimeError('Todavía no hay video armado para exportar. Pulsa «▶ Hacer todo».')
        # se escribe con otro nombre y se renombra al final: así nadie descarga un archivo a medio hacer (no se abriría)
        c = []
        for h in sorted(set(alturas), reverse=True):
            c.append([PY, m('codificar', 'codificar.py'), 'ffmpeg', '-nostdin', '-v', 'error', '-stats', '-y', '-i', fuente, '-vf', f'scale=-2:{h}', '-c:v', 'libx264',
                      '-preset', 'veryfast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-f', 'mp4',
                      f'FINAL_{h}p.mp4.parcial'])
            c.append([PY, '-c', f'import os; os.replace("FINAL_{h}p.mp4.parcial", "FINAL_{h}p.mp4")'])
        if quiere_mp3:  # solo el audio del video (voz + música), en mp3; sin recodificar el video
            c.append(['ffmpeg', '-nostdin', '-v', 'error', '-stats', '-y', '-i', fuente, '-vn', '-c:a', 'libmp3lame', '-b:a', '192k', '-f', 'mp3', 'FINAL.mp3.parcial'])
            c.append([PY, '-c', 'import os; os.replace("FINAL.mp3.parcial", "FINAL.mp3")'])
        return c
    if paso == 'nube':  # todo lo tuyo, en trozos que Claude acepta, para que arme el video en la nube
        mb = min(max(float(op.get('mb') or 300), 5), 400)
        return [[PY, m('nube', 'preparar.py'), '--proyecto', '.', '--ajustes', AJUSTES, '--estilos', ESTILOS, '--conocimientos', conocimiento.CARPETA, '--mb', f'{mb:g}']]
    if paso == 'acortar':  # quita silencios, esperas y lo que sobra de la grabación, hasta la duración pedida
        c = [PY, m('acortar', 'acortar.py'), '--proyecto', '.', '--ajustes', AJUSTES]
        if op.get('rehacer'):
            return [c + ['--rehacer']]
        return [c + ['--objetivo', f"{min(max(float(op.get('minutos') or 0), 0), 600):g}"] + ([] if op.get('ia', True) else ['--sin-ia'])]
    if paso == 'prueba':  # «Solo los bloques»: voz, montaje y voz puesta de unos pocos bloques, para revisarlos rápido
        mo = comandos('montaje', d, op)[0]
        mo[mo.index('guion.json')], mo[mo.index('1_montaje.mp4')] = PRUEBA_GUION, 'prueba_montaje.mp4'
        return [[PY, m('voz', 'voz.py'), '--guion', PRUEBA_GUION, '--salida', 'voz'] + voz_args(d), mo,
                [PY, m('voz', 'mezclar_voz.py'), 'prueba_montaje.mp4', PRUEBA_GUION, 'voz', 'prueba_bloques.mp4']]
    if paso == 'final_sin_trailer':
        return [['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', ultimo_video(d, None), '-c', 'copy', 'FINAL.mp4']]
    raise ValueError(paso)


# Qué necesita cada paso para poder correr, y qué produce
PASOS = [
    {'id': 'transcribir', 'nombre': 'Transcribir tu voz', 'necesita': ['original.mp4'], 'produce': 'transcripcion.txt', 'opcional': True},
    {'id': 'voz', 'nombre': 'Generar voz (ElevenLabs)', 'necesita': ['guion.json'], 'produce': 'voz'},
    {'id': 'montaje', 'nombre': 'Montar video', 'necesita': ['original.mp4', 'guion.json'], 'produce': '1_montaje.mp4'},
    {'id': 'insertos', 'nombre': 'Cortes y zooms con material extra', 'necesita': ['1_montaje.mp4', 'insertos.json', 'voz'], 'produce': '2_insertos.mp4', 'opcional': True, 'blando': True},
    {'id': 'mezclar', 'nombre': 'Poner la voz y subtítulos', 'necesita': ['1_montaje.mp4', 'voz'], 'produce': '3_voz.mp4'},
    {'id': 'musica', 'nombre': 'Música de fondo', 'necesita': ['3_voz.mp4'], 'produce': '4_musica.mp4'},
    {'id': 'etiquetas', 'nombre': 'Etiquetas animadas', 'necesita': ['3_voz.mp4', 'etiquetas.json'], 'produce': '5_etiquetas.mp4', 'opcional': True, 'blando': True},
    {'id': 'senales', 'nombre': 'Flechas y círculos', 'necesita': ['3_voz.mp4', 'senales.json'], 'produce': '6_senales.mp4', 'opcional': True, 'blando': True},
    {'id': 'tarjetas', 'nombre': 'Tarjetas de comentarios y WhatsApp', 'necesita': ['3_voz.mp4', 'tarjetas/tarjetas.json'], 'produce': '7_tarjetas.mp4', 'opcional': True, 'blando': True},
    {'id': 'logos', 'nombre': 'Logos (Android, MagicOS…) cuando la voz los nombra', 'necesita': ['3_voz.mp4', 'guion.json', 'voz'], 'produce': '7b_logos.mp4', 'opcional': True, 'blando': True},
    {'id': 'capas', 'nombre': 'Pegar etiquetas, flechas y tarjetas (una sola pasada)', 'necesita': [], 'produce': '', 'oculto': True, 'blando': True},
    {'id': 'testimonios', 'nombre': 'Testimonios de clientes', 'necesita': ['3_voz.mp4', 'testimonios/testimonios.json'], 'produce': '8_testimonios.mp4', 'opcional': True, 'blando': True},
    {'id': 'nuevos_modelos', 'nombre': 'Nuevos modelos', 'necesita': ['3_voz.mp4', 'nuevos_modelos/modelos.json'], 'produce': '9_modelos.mp4', 'opcional': True, 'blando': True},
    {'id': 'trailer', 'nombre': 'Tráiler ANTES · DURANTE · DESPUÉS', 'necesita': ['3_voz.mp4', 'trailer.json'], 'produce': 'FINAL.mp4', 'opcional': True, 'blando': True},
    {'id': 'final_sin_trailer', 'nombre': 'Video final sin tráiler', 'necesita': ['3_voz.mp4'], 'produce': 'FINAL.mp4', 'opcional': True},
    {'id': 'prueba', 'nombre': 'Probar solo unos bloques', 'necesita': ['original.mp4', 'guion.json'], 'produce': 'prueba_bloques.mp4', 'oculto': True},
    {'id': 'exportar', 'nombre': 'Exportar en otra calidad', 'necesita': [], 'produce': '', 'oculto': True},
    {'id': 'guion_ia', 'nombre': 'Escribir el guion con IA (desde tu video)', 'necesita': ['original.mp4'], 'produce': 'guion.json', 'oculto': True},
    {'id': 'revisar_imagen', 'nombre': 'Revisar cada bloque del guion contra su imagen', 'necesita': ['guion.json', 'original.mp4'], 'produce': 'guion.json', 'oculto': True},
    {'id': 'short', 'nombre': 'Short vertical 9:16', 'necesita': ['original.mp4', 'guion.json'], 'produce': 'SHORT.mp4', 'oculto': True},
    {'id': 'trailer_ia', 'nombre': 'Elegir las tomas del tráiler con IA', 'necesita': ['original.mp4'], 'produce': 'trailer.json', 'oculto': True, 'blando': True},
    {'id': 'trailer_version', 'nombre': 'Armar el tráiler de una IA (para compararlo)', 'necesita': ['original.mp4'], 'produce': '', 'oculto': True, 'blando': True},
    {'id': 'trailer_solo', 'nombre': 'Armar solo el tráiler (para verlo)', 'necesita': ['original.mp4', 'trailer.json'], 'produce': 'trailer.mp4', 'oculto': True, 'blando': True},
    {'id': 'etiquetas_ia', 'nombre': 'Elegir etiquetas con IA', 'necesita': ['guion.json'], 'produce': 'etiquetas.json', 'oculto': True, 'blando': True},
    {'id': 'senales_ia', 'nombre': 'Ubicar flechas y círculos con IA', 'necesita': ['guion.json', 'voz', '3_voz.mp4'], 'produce': 'senales.json', 'oculto': True, 'blando': True},
    {'id': 'ia', 'nombre': 'Parte creativa con IA', 'necesita': ['original.mp4'], 'produce': '', 'oculto': True},
    {'id': 'acortar', 'nombre': 'Acortar la grabación', 'necesita': ['original.mp4'], 'produce': 'acortado.mp4', 'oculto': True},
    {'id': 'nube', 'nombre': 'Preparar para Claude en la nube', 'necesita': ['original.mp4'], 'produce': '', 'oculto': True},
    {'id': 'alimentar', 'nombre': 'Aprender tu estilo (Alimentación)', 'necesita': [], 'produce': '', 'oculto': True},
] + mejoras.PASOS
TODO = ['voz', 'montaje', 'insertos', 'mezclar', 'musica', 'etiquetas', 'senales', 'tarjetas', 'logos', 'testimonios', 'nuevos_modelos', 'trailer']
# «▶ Hacer todo» arma primero el video (voz, cortes, subtítulos y música); los extras se agregan después con «✨ Agregar extras»,
# así si el guion no gusta no se pierde tiempo en etiquetas, flechas, testimonios, nuevos modelos ni tráiler
EXTRAS = ['etiquetas', 'senales', 'tarjetas', 'logos', 'testimonios', 'nuevos_modelos', 'trailer']
CAPAS = ['etiquetas', 'senales', 'tarjetas', 'logos']  # se pegan juntos en una sola codificación (capas/capas.py)
CAPAS_DIR = '.capas'
LOGOS_DIR = os.path.join(RAIZ, 'mis_conocimientos', 'logos')  # tus logos fijos, para todos los videos (pedido de fabian, 30/10/2026)
PRUEBA_GUION = 'guion_prueba.json'  # copia con solo los bloques a probar; guion.json no se toca


def guion_de_prueba(d, desde, hasta):
    """Escribe guion_prueba.json con los bloques de `desde` a `hasta` (ids como L23). Devuelve cuántos son."""
    datos = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    ids = [str(b.get('id', '')).upper() for b in datos['bloques']]
    desde, hasta = (str(x or '').strip().upper() for x in (desde, hasta))
    hasta = hasta or desde
    for x in (desde, hasta):
        if x not in ids:
            raise ValueError(f'no encuentro el bloque «{x}» en el guion (los bloques van de {ids[0]} a {ids[-1]})')
    i, j = sorted((ids.index(desde), ids.index(hasta)))
    datos['bloques'] = [dict(b) for b in datos['bloques'][i:j + 1]]
    json.dump(datos, open(os.path.join(d, PRUEBA_GUION), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return j - i + 1


PREPARA_EXTRA = {'etiquetas_ia': 'etiquetas', 'senales_ia': 'senales', 'trailer_ia': 'trailer'}
VIDEOS_EXTRAS = ['5_etiquetas.mp4', '6_senales.mp4', '7_tarjetas.mp4', '7b_logos.mp4', '8_testimonios.mp4', '8_testimonios.srt', '9_modelos.mp4',
                 '9_modelos.srt', 'trailer.mp4', 'capas_hechas.json']

FALLOS = {}  # proyecto -> {'paso', 'msg'} del último paso que falló
TRABAJO = {'proyecto': None, 'paso': None, 'proc': None, 'inicio': None, 'cola': [], 'plan': [], 'i': 0, 'inicio_total': None}
RESULTADO = {}  # proyecto -> cómo terminó la última tanda (para la barra de progreso)
CANDADO = threading.Lock()
# «📤 Prestar mis claves a otra PC»: se abre desde este PC por 5 minutos, para un solo pedido con el PIN de «📱 Celular»
PRESTAMO = {'hasta': 0.0, 'fallos': 0}
CLAVES = ('proveedor', 'url', 'modelo', 'clave', 'imagenes', 'tipo', 'json', 'elevenlabs', 'ias_guion')


def leer_ajustes():
    return json.load(open(AJUSTES, encoding='utf-8')) if os.path.exists(AJUSTES) else {}


def clave_eleven():
    """La clave de ElevenLabs: la guardada en la app, la variable de entorno, o la que dejó setx en Windows."""
    k = leer_ajustes().get('elevenlabs') or os.environ.get('ELEVENLABS_API_KEY')
    if not k and sys.platform == 'win32':
        try:  # setx la guarda en el registro y la ventana ya abierta no la ve
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as r:
                k = winreg.QueryValueEx(r, 'ELEVENLABS_API_KEY')[0]
        except OSError:
            pass
    return (k or '').strip()


def probar_clave(aj):
    """Hace una llamada corta al proveedor para ver si la clave sirve. No gasta tokens: solo pide la lista de modelos."""
    url = (aj.get('url') or '').strip().rstrip('/')
    clave = (aj.get('clave') or '').strip()
    if not url:
        return {'ok': False, 'mensaje': 'Falta la dirección (URL) del proveedor.'}
    es_claude = aj.get('tipo') == 'claude' or (aj.get('proveedor') or '').startswith('Claude')
    es_local = 'localhost' in url or '127.0.0.1' in url
    if es_claude:
        destino = url + '/v1/models'
        cab = {'x-api-key': clave, 'anthropic-version': '2023-06-01'}
    else:
        destino = url + '/models'
        cab = {}
        if clave:
            cab['Authorization'] = 'Bearer ' + clave
    if not clave and not es_local:
        return {'ok': False, 'mensaje': 'Falta la clave API.'}
    req = urllib.request.Request(destino, headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            cuerpo = r.read(2_000_000)
        try:  # los modelos que esa clave puede usar, tal como los lista el proveedor
            modelos = sorted({re.sub(r'^models/', '', str(x.get('id', ''))) for x in json.loads(cuerpo).get('data', []) if x.get('id')})
        except (ValueError, AttributeError):
            modelos = []
        return {'ok': True, 'mensaje': 'La clave funciona. Conexión correcta con el proveedor.', 'modelos': modelos}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return {'ok': False, 'mensaje': 'La clave no es válida o no tiene permisos (el proveedor la rechazó).'}
        if e.code == 429:
            return {'ok': False, 'mensaje': 'La clave sirve, pero el proveedor dice que no tienes saldo o hiciste muchas peticiones.'}
        if e.code == 404:
            return {'ok': False, 'mensaje': 'La dirección (URL) parece incorrecta para este proveedor.'}
        return {'ok': False, 'mensaje': f'El proveedor respondió con un error ({e.code}).'}
    except urllib.error.URLError:
        if es_local:
            return {'ok': False, 'mensaje': 'No se pudo conectar. ¿Está encendido Ollama o LM Studio en tu PC?'}
        return {'ok': False, 'mensaje': 'No se pudo conectar con el proveedor. Revisa el internet o la dirección (URL).'}
    except Exception:
        return {'ok': False, 'mensaje': 'No se pudo comprobar la clave.'}


def probar_eleven(clave):
    """¿Sirve la clave de ElevenLabs? Pide el plan y los créditos que quedan. No gasta créditos."""
    clave = (clave or '').strip()
    if not clave:
        return {'ok': False, 'mensaje': 'Falta la clave de ElevenLabs.'}

    def pedir(ruta):
        req = urllib.request.Request('https://api.elevenlabs.io' + ruta, headers={'xi-api-key': clave})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read(2_000_000) or b'{}')
    try:
        try:
            s = pedir('/v1/user/subscription')
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403):
                raise
            pedir('/v1/models')  # una clave restringida puede no leer el plan, pero sí usar la API
            return {'ok': True, 'mensaje': 'La clave funciona (no tiene permiso para mostrar el plan ni los créditos).'}
        usados, limite = s.get('character_count'), s.get('character_limit')
        plan = s.get('tier') or ''
        if isinstance(usados, int) and isinstance(limite, int):
            return {'ok': True, 'mensaje': f'La clave funciona · plan {plan} · te quedan {max(0, limite - usados):,} de {limite:,} créditos.'.replace(',', '.'),
                    'quedan': max(0, limite - usados)}
        return {'ok': True, 'mensaje': f'La clave funciona · plan {plan}.'}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return {'ok': False, 'mensaje': 'ElevenLabs rechazó la clave: no es válida o le faltan permisos.'}
        if e.code == 429:
            return {'ok': False, 'mensaje': 'La clave sirve, pero ElevenLabs dice que hiciste muchas peticiones. Prueba en un rato.'}
        return {'ok': False, 'mensaje': f'ElevenLabs respondió con un error ({e.code}).'}
    except urllib.error.URLError:
        return {'ok': False, 'mensaje': 'No se pudo conectar con ElevenLabs. Revisa el internet.'}
    except Exception:
        return {'ok': False, 'mensaje': 'No se pudo comprobar la clave.'}


def revision_imagen_pendiente(d):
    """¿El guion quedó sin revisar contra sus imágenes? (se deja para después de que lo apruebas)"""
    try:
        g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return isinstance(g, dict) and bool(g.get('revision_imagen_pendiente'))


USAN_ELEVEN = {'voz', 'prueba', 'musica', 'trailer', 'trailer_solo', 'trailer_version', 'nuevos_modelos'}


def carpeta(p):
    p = re.sub(r'[^\w\- ]', '', p or '').strip()
    if not p:
        raise ValueError('nombre de proyecto vacío')
    return os.path.join(PROYECTOS, p)


GUARDADOS = 'guardados'  # puntos de guardado del proyecto: lo hecho (guion, voces, respuestas, extras), sin los videos
NO_SE_GUARDA = {GUARDADOS, '.montaje_partes', 'hojas_2s', 'acciones', 'ia_capturas', 'para_claude', 'historial_guion'}


def _entra_en_guardado(nombre, es_carpeta):
    if nombre in NO_SE_GUARDA or nombre.startswith('.'):
        return False
    return es_carpeta or os.path.splitext(nombre)[1].lower() not in VIDEOS | {'.wav', '.npz', '.zip'}


def guardar_proyecto(d, nota=''):
    """Copia lo hecho del proyecto (guion, transcripción, voces, respuestas, tráiler, etiquetas, tus tarjetas…) a
    guardados/<fecha>. Los videos no se copian: el grabado queda en el proyecto y los armados se rehacen sin gastar,
    porque las voces van en el guardado. Devuelve el nombre del guardado."""
    nombre = time.strftime('%Y-%m-%d_%H-%M-%S') + ('_' + re.sub(r'[^\w\- ]', '', nota).strip()[:40] if nota.strip() else '')
    dst = os.path.join(d, GUARDADOS, nombre)
    os.makedirs(dst)
    for f in os.listdir(d):
        r = os.path.join(d, f)
        if not _entra_en_guardado(f, os.path.isdir(r)):
            continue
        if os.path.isdir(r):
            shutil.copytree(r, os.path.join(dst, f), ignore=lambda carp, xs: [x for x in xs if not _entra_en_guardado(x, os.path.isdir(os.path.join(carp, x)))])
        else:
            shutil.copy2(r, os.path.join(dst, f))
    return nombre


def lista_guardados(d):
    g = os.path.join(d, GUARDADOS)
    out = []
    for n in sorted(os.listdir(g), reverse=True) if os.path.isdir(g) else []:
        r = os.path.join(g, n)
        tam = sum(os.path.getsize(os.path.join(a, x)) for a, _, xs in os.walk(r) for x in xs)
        try:
            bloques = len(json.load(open(os.path.join(r, 'guion.json'), encoding='utf-8')).get('bloques', []))
        except (OSError, ValueError, AttributeError):
            bloques = 0
        voces = len([x for x in os.listdir(os.path.join(r, 'voz')) if x.endswith('.mp3')]) if os.path.isdir(os.path.join(r, 'voz')) else 0
        out.append({'nombre': n, 'mb': round(tam / 1e6, 1), 'bloques': bloques, 'voces': voces})
    return out


def volver_a_guardado(d, nombre):
    """Pone el proyecto como estaba en ese guardado. Antes guarda lo actual, por si quieres volver."""
    src = os.path.join(d, GUARDADOS, os.path.basename(nombre))
    if not nombre or not os.path.isdir(src):
        raise ValueError('no existe ese guardado')
    respaldo = guardar_proyecto(d, 'antes de volver')
    for f in os.listdir(d):  # los archivos de lo hecho se reemplazan por los del guardado; el video grabado y lo subido no
        r = os.path.join(d, f)
        if os.path.isfile(r) and _entra_en_guardado(f, False) and f not in set(SUBIBLES.values()):
            os.remove(r)
    for f in os.listdir(src):  # las carpetas se completan (no se borran: ahí están tus videos de testimonios y modelos)
        r = os.path.join(src, f)
        shutil.copytree(r, os.path.join(d, f), dirs_exist_ok=True) if os.path.isdir(r) else shutil.copy2(r, os.path.join(d, f))
    return respaldo


def elegir_video_en_la_pc(guardar=''):
    """La ventana de Windows para elegir un video de la PC (para «🗜 Comprimir video»), o con `guardar` (ruta o nombre
    sugerido) el «Guardar como…» del resultado. '' si cancelas."""
    salida = tempfile.mktemp(suffix='.txt')
    codigo = ('import os, sys, tkinter as tk\nfrom tkinter import filedialog as fd\n'
              'r = tk.Tk(); r.withdraw(); r.attributes("-topmost", True)\n'
              'g = sys.argv[2]\n'
              'f = fd.asksaveasfilename(parent=r, title="Guardar el video comprimido como", initialdir=os.path.dirname(g) or None, '
              'initialfile=os.path.basename(g), defaultextension=".mp4", filetypes=[("Video MP4", "*.mp4")]) if g else '
              'fd.askopenfilename(parent=r, title="Elegir el video a comprimir", '
              'filetypes=[("Videos", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"), ("Todos", "*.*")])\n'
              'open(sys.argv[1], "w", encoding="utf-8").write(f or "")\n')
    try:
        subprocess.run([sys.executable, '-c', codigo, salida, guardar], timeout=3600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return os.path.normpath(open(salida, encoding='utf-8').read().strip()) if os.path.getsize(salida) else ''
    except (OSError, subprocess.SubprocessError):
        raise ValueError('No se pudo abrir la ventana para elegir el video (falta tkinter en este Python).')
    finally:
        if os.path.exists(salida):
            os.remove(salida)


def elegir_en_la_pc(modo, nombre=''):
    """Abre la ventana de Windows para elegir dónde guardar (modo 'guardar') o qué archivo abrir ('abrir').
    Corre en un proceso aparte (tkinter no se lleva bien con los hilos del servidor). Devuelve la ruta o '' si cancelas."""
    salida = tempfile.mktemp(suffix='.txt')
    codigo = ('import sys, tkinter as tk\nfrom tkinter import filedialog as fd\n'
              'r = tk.Tk(); r.withdraw(); r.attributes("-topmost", True)\n'
              'f = fd.asksaveasfilename(parent=r, title="Guardar proyecto como", initialfile=sys.argv[3], defaultextension=".zip", '
              'filetypes=[("Proyecto guardado", "*.zip")]) if sys.argv[1] == "guardar" else '
              'fd.askopenfilename(parent=r, title="Abrir proyecto guardado", filetypes=[("Proyecto guardado", "*.zip")])\n'
              'open(sys.argv[2], "w", encoding="utf-8").write(f or "")\n')
    try:
        subprocess.run([sys.executable, '-c', codigo, modo, salida, nombre], timeout=3600,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return open(salida, encoding='utf-8').read().strip()
    except (OSError, subprocess.SubprocessError):
        raise ValueError('No se pudo abrir la ventana para elegir la ubicación (falta tkinter en este Python).')
    finally:
        if os.path.exists(salida):
            os.remove(salida)


def guardar_como(d, nota=''):
    """Hace un guardado normal y además lo copia como un .zip donde tú elijas (USB, otra carpeta, la nube…)."""
    import zipfile
    sugerido = os.path.basename(d) + '_' + time.strftime('%Y-%m-%d') + ('_' + re.sub(r'[^\w\- ]', '', nota).strip()[:40] if nota.strip() else '') + '.zip'
    destino = elegir_en_la_pc('guardar', sugerido)
    if not destino:
        return None
    nombre = guardar_proyecto(d, nota)
    src = os.path.join(d, GUARDADOS, nombre)
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as z:
        for a, _, xs in os.walk(src):
            for x in xs:
                z.write(os.path.join(a, x), os.path.relpath(os.path.join(a, x), src))
        if os.path.exists(MUSICA_FIJA) and not os.path.exists(os.path.join(src, 'musica.mp3')):
            # la música fija vive fuera del proyecto: va como música propia, para que en otra PC suene la misma
            z.write(MUSICA_FIJA, 'musica.mp3')
        for x in ('CONOCIMIENTO.md', 'aprendido_de_proyectos.md'):  # lo aprendido viaja con el proyecto a la otra PC
            if os.path.exists(os.path.join(conocimiento.CARPETA, x)):
                z.write(os.path.join(conocimiento.CARPETA, x), 'mis_conocimientos/' + x)
        if os.path.isdir(conocimiento.MARCAS):  # y las marcas (MOTOROLA.md, APPLE.md…)
            for x in os.listdir(conocimiento.MARCAS):
                if x.endswith('.md'):
                    z.write(os.path.join(conocimiento.MARCAS, x), 'mis_conocimientos/marcas/' + x)
    return destino


def abrir_guardado(d):
    """Trae un .zip de «Guardar como» a la lista de guardados del proyecto, para luego «↩ Volver a este»."""
    import zipfile
    origen = elegir_en_la_pc('abrir')
    if not origen:
        return None
    nombre = time.strftime('%Y-%m-%d_%H-%M-%S') + '_' + re.sub(r'[^\w\- ]', '', os.path.splitext(os.path.basename(origen))[0]).strip()[:40]
    dst = os.path.join(d, GUARDADOS, nombre)
    with zipfile.ZipFile(origen) as z:
        if 'guion.json' not in z.namelist() and 'transcripcion.json' not in z.namelist():
            raise ValueError('Ese .zip no parece un proyecto guardado con «Guardar como».')
        for m in z.infolist():  # sin rutas que salgan de la carpeta
            if m.is_dir() or os.path.isabs(m.filename) or '..' in m.filename.replace('\\', '/').split('/'):
                continue
            os.makedirs(os.path.dirname(os.path.join(dst, m.filename)), exist_ok=True)
            with z.open(m) as a, open(os.path.join(dst, m.filename), 'wb') as b:
                shutil.copyfileobj(a, b)
    otra = os.path.join(dst, 'mis_conocimientos')
    if os.path.isdir(otra):  # lo aprendido en la otra PC se suma al tuyo (no borra nada) y no queda dentro del proyecto
        conocimiento.juntar(otra)
        shutil.rmtree(otra, ignore_errors=True)
    return nombre


def carpeta_estilo(nombre):
    n = re.sub(r'[^\w\- ]', '', nombre or '').strip()
    if not n:
        raise ValueError('nombre de estilo vacío')
    return os.path.join(ESTILOS, n)


def fuentes_estilo(e):
    try:
        return json.load(open(os.path.join(e, 'fuentes.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []


def guardar_fuentes(e, lista):
    os.makedirs(e, exist_ok=True)
    json.dump(lista, open(os.path.join(e, 'fuentes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def estilos():
    out = []
    for n in sorted(os.listdir(ESTILOS)):
        e = os.path.join(ESTILOS, n)
        if os.path.isdir(e):
            hechos = {os.path.splitext(x)[0] for x in os.listdir(os.path.join(e, 'analisis'))} if os.path.isdir(os.path.join(e, 'analisis')) else set()
            fu = fuentes_estilo(e)
            try:
                catalogo = json.load(open(os.path.join(e, 'catalogo.json'), encoding='utf-8'))
            except (OSError, ValueError):
                catalogo = []
            for f in fu:
                if f['tipo'] == 'canal':  # cuántos videos del canal ya se leyeron
                    ids = [re.search(r'v=([\w-]{11})', v['url']).group(1) for v in catalogo if re.search(r'v=([\w-]{11})', v.get('url', ''))]
                    f['titulo'] = f"Canal: {f['url']}" + (f' · {len(ids)} videos' if ids else '')
                    f['leidos'] = sum(i in hechos for i in ids)
                    f['analizado'] = bool(ids) and f['leidos'] > 0
                    continue
                clave = re.search(r'(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})', f.get('url', ''))
                f['analizado'] = f['tipo'] == 'texto' or (clave.group(1) if clave else os.path.splitext(f.get('archivo', ''))[0]) in hechos
            out.append({'nombre': n, 'fuentes': fu, 'perfil': os.path.exists(os.path.join(e, 'perfil.md'))})
    return out


def registro(d):
    return os.path.join(d, 'registro.txt')


# avisos de «Revisar cada bloque contra su imagen» que dicen que la voz no va con lo que se ve
DESALINEADO = re.compile(r'la imagen no va con lo que dice|lo dices y lo haces en|parece ir (atrasada|adelantada)|'
                         r'no lo muestra ningún bloque|falta ese paso en la voz')


def avisos_de_imagen(d, nombre):
    """Los avisos de voz que no va con la imagen que dejó la última pasada de la revisión con imágenes (en el registro)."""
    try:
        texto = open(registro(d), encoding='utf-8', errors='replace').read()
    except OSError:
        return []
    seccion = texto[texto.rfind('▶ ' + nombre):] if '▶ ' + nombre in texto else ''
    return [l.strip().lstrip('·').strip() for l in seccion.splitlines() if DESALINEADO.search(l)]


RAMA_APP = 'claude/project-thread-ns2vx0'  # la rama de GitHub con la versión más nueva (se cambia con «rama_app» en ajustes.json)
NO_TOCAR = {'mis_proyectos', 'mis_estilos', 'mis_musica', 'mis_conocimientos', 'descargas_app', '.git', 'node_modules', 'trabajo', 'ffmpeg_nvidia'}  # lo tuyo: nunca se reemplaza
NO_TOCAR_ARCHIVOS = {'app/ajustes.json', 'app/ajustes.json.copia', 'app/registro_app.txt', 'Estudio.exe'}


def actualizar_app():
    """«⬇ Actualizar la app»: baja la versión nueva de GitHub y la copia ENCIMA de esta misma carpeta. Tus proyectos,
    estilos y claves no se tocan, y lo que se reemplaza queda antes en un respaldo (descargas_app/respaldo_app_*.zip)."""
    import io, zipfile
    rama = leer_ajustes().get('rama_app') or RAMA_APP
    if os.path.isdir(os.path.join(RAIZ, '.git')):
        return actualizar_git(rama)
    url = f'https://codeload.github.com/gotzschmidtt-pixel/editor-tutoriales/zip/refs/heads/{urllib.parse.quote(rama)}'
    try:
        datos = urllib.request.urlopen(url, timeout=120).read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'GitHub no encontró la versión nueva (error {e.code} en la rama «{rama}»).')
    except urllib.error.URLError as e:
        raise RuntimeError(f'No pude bajar la versión nueva: revisa tu internet ({e.reason}).')
    zf = zipfile.ZipFile(io.BytesIO(datos))
    nuevos = {}
    for n in zf.namelist():
        rel = n.split('/', 1)[1] if '/' in n else ''
        if not rel or n.endswith('/') or '..' in rel.split('/') or rel.startswith('/') or ':' in rel \
                or rel.split('/')[0] in NO_TOCAR or rel in NO_TOCAR_ARCHIVOS:
            continue
        nuevos[rel] = n
    if 'app/app.py' not in nuevos:
        raise RuntimeError('El ZIP bajado no parece ser esta app; no cambié nada.')
    cambian = []
    for rel, n in nuevos.items():
        destino = os.path.join(RAIZ, *rel.split('/'))
        contenido = zf.read(n)
        if not os.path.exists(destino) or open(destino, 'rb').read() != contenido:
            cambian.append((rel, destino, contenido))
    if not cambian:
        return {'ok': True, 'cambiados': 0, 'mensaje': 'Ya tienes la versión más nueva.'}
    carpeta_resp = os.path.join(RAIZ, 'descargas_app')
    os.makedirs(carpeta_resp, exist_ok=True)
    respaldo = os.path.join(carpeta_resp, f"respaldo_app_{time.strftime('%Y%m%d_%H%M%S')}.zip")
    with zipfile.ZipFile(respaldo, 'w', zipfile.ZIP_DEFLATED) as r:
        for rel, destino, _ in cambian:
            if os.path.exists(destino):
                r.write(destino, rel)
    for rel, destino, contenido in cambian:  # app.py al final: al cambiar, la página reinicia la app sola
        if rel != 'app/app.py':
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            escribir_bytes(destino, contenido)
    for rel, destino, contenido in cambian:
        if rel == 'app/app.py':
            escribir_bytes(destino, contenido)
    return {'ok': True, 'cambiados': len(cambian), 'respaldo': os.path.relpath(respaldo, RAIZ),
            'mensaje': f'Actualicé {len(cambian)} archivo(s) en esta misma carpeta. Tus proyectos y claves siguen igual.'}


def actualizar_git(rama):
    """«⬇ Actualizar la app» cuando la carpeta es un clon de git (como en la laptop): baja la rama de GitHub y deja la
    carpeta igual a ella. Lo que se hubiera cambiado solo en esta PC no se pierde: los commits quedan en la rama
    respaldo_app_<fecha> y los archivos tocados sin commit en un «git stash» con ese mismo nombre."""
    def git(*args):
        r = subprocess.run(['git', *args], cwd=RAIZ, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
        if r.returncode:
            raise RuntimeError(f"git {args[0]} falló: {(r.stderr or r.stdout).strip()[-300:]}")
        return r.stdout.strip()
    try:
        git('fetch', 'origin', rama)
    except FileNotFoundError:
        raise RuntimeError('Esta carpeta es un clon de git, pero git no está instalado en esta PC.')
    except RuntimeError as e:
        raise RuntimeError(f'No pude bajar la versión nueva de GitHub (revisa tu internet). {e}')
    remota = f'origin/{rama}'
    cambian = [x for x in git('diff', '--name-only', 'HEAD', remota).splitlines() if x]
    tocados = git('status', '--porcelain', '--untracked-files=no')
    if not cambian and not tocados:
        return {'ok': True, 'cambiados': 0, 'mensaje': 'Ya tienes la versión más nueva.'}
    marca = 'respaldo_app_' + time.strftime('%Y%m%d_%H%M%S')
    avisos = []
    if git('rev-list', '--count', f'{remota}..HEAD') != '0':  # commits hechos solo en esta PC
        git('branch', marca, 'HEAD')
        avisos.append(f'tus cambios de esta PC quedaron en la rama {marca}')
    if tocados:
        git('-c', 'user.name=Estudio', '-c', 'user.email=estudio@localhost', 'stash', 'push', '-m', marca)
        avisos.append(f'los archivos que habías cambiado quedaron guardados en «git stash» ({marca})')
    git('checkout', '-q', '-B', rama, remota)
    return {'ok': True, 'cambiados': len(cambian),
            'mensaje': f'Actualicé {len(cambian)} archivo(s) desde GitHub. Tus proyectos y claves siguen igual.'
                       + (' Ojo: ' + '; '.join(avisos) + '.' if avisos else '')}


def ultimo_proyecto():
    """{'nombre', 'cuando'} del proyecto con actividad más reciente (un paso, una subida, un guardado), o {} si no hay."""
    mejor = {}
    for x in os.listdir(PROYECTOS) if os.path.isdir(PROYECTOS) else []:
        d = os.path.join(PROYECTOS, x)
        if not os.path.isdir(d):
            continue
        try:
            cuando = max([os.path.getmtime(d)] + [os.path.getmtime(os.path.join(d, f)) for f in os.listdir(d)])
        except OSError:
            continue
        if cuando > mejor.get('cuando', 0):
            mejor = {'nombre': x, 'cuando': cuando}
    return mejor


def escribir_bytes(destino, contenido):
    tmp = destino + '.nuevo'
    with open(tmp, 'wb') as f:
        f.write(contenido)
    os.replace(tmp, destino)


def informe_paso(d, proyecto, paso, info, ejec, estado, log):
    """El diagnóstico de un paso (ver diagnostico/diagnostico.py). Nunca frena la app: si algo falla aquí, se sigue."""
    try:
        log.flush()
        texto = open(registro(d), encoding='utf-8', errors='replace').read().split('\n▶')[-1]
        aj = leer_ajustes()
        r = diagnostico.informe(os.path.join(d, 'diagnosticos'), proyecto, paso, info['nombre'], ejec, texto, estado,
                                proveedor=aj.get('proveedor') or '', modelo=aj.get('modelo') or '')
        if r:
            log.write(f"· diagnóstico guardado en diagnosticos/{r['archivo']}.txt ({r['tipo']})\n"); log.flush()
        return r
    except Exception as e:
        try:
            log.write(f'· no pude escribir el diagnóstico ({type(e).__name__}: {e})\n'); log.flush()
        except Exception:
            pass
        return None


VIDEOS_GENERADOS = ['1_montaje.mp4', '2_insertos.mp4', '3_voz.mp4', '3_voz.srt', '4_musica.mp4', '5_etiquetas.mp4', '6_senales.mp4', 'capas_hechas.json',
                    '7_tarjetas.mp4', '8_testimonios.mp4', '8_testimonios.srt', '9_modelos.mp4', '9_modelos.srt', 'trailer.mp4', 'FINAL.mp4', 'montaje_en_curso.mp4', 'FINAL_1080p.mp4', 'FINAL_720p.mp4', 'FINAL_480p.mp4', 'FINAL_360p.mp4',
                    'prueba_montaje.mp4', 'prueba_bloques.mp4', 'prueba_bloques.srt']
LIBRERIAS = {'numpy': 'numpy', 'cv2': 'opencv-python-headless'}  # las que usan casi todos los pasos
INICIO_APP = os.path.getmtime(__file__)  # para saber si actualizaron la app sin reiniciarla


def falta_libreria(mod, env):
    # se prueba en un proceso aparte, igual que los pasos: una instalación rota también cuenta como faltante
    return subprocess.run([PY, '-c', f'import {mod}'], capture_output=True, env=env, **SIN_VENTANA).returncode != 0


NODE = {'etiquetas': ('', 'playwright'), 'senales': ('remotion', 'remotion'), 'trailer': ('remotion', 'remotion'), 'trailer_solo': ('remotion', 'remotion'), 'trailer_version': ('remotion', 'remotion')}


def asegurar_node(paso, log, env):
    """Las etiquetas (Playwright) y las señales y el tráiler (Remotion) usan Node: si esta copia no corrió
    instalar.bat, se instala lo que falta la primera vez."""
    if paso not in NODE:
        return
    sub, modulo = NODE[paso]
    carpeta_n = os.path.join(RAIZ, sub) if sub else RAIZ
    if os.path.isdir(os.path.join(carpeta_n, 'node_modules', modulo)):
        return
    npm, npx = shutil.which('npm'), shutil.which('npx')
    if not (shutil.which('node') and npm and npx):
        raise RuntimeError('Falta Node.js, que usan las etiquetas, las flechas y el tráiler. Corre instalar.bat '
                           '(o instala Node.js LTS desde nodejs.org), reinicia la PC y vuelve a abrir la app.')
    log.write(f'\nInstalando lo de Node para {paso} (solo la primera vez, tarda unos minutos)…\n'); log.flush()
    cmds = [[npm, 'install', '--no-audit', '--no-fund']]
    if modulo == 'playwright':
        cmds.append([npx, 'playwright', 'install', 'chromium'])
    for c in cmds:
        if subprocess.run(c, cwd=carpeta_n, stdout=log, stderr=subprocess.STDOUT, env=env, **SIN_VENTANA).returncode != 0:
            raise RuntimeError(f'No pude instalar lo de Node ({" ".join(os.path.basename(x) for x in c[:2])}). '
                               f'Corre instalar.bat en {RAIZ} y vuelve a intentar.')
    log.write('✓ Listo\n'); log.flush()


def asegurar_librerias(log, env):
    """Si esta copia de la app se abrió sin correr instalar.bat, instala lo básico la primera vez."""
    libs = dict(LIBRERIAS)
    aj = leer_ajustes()
    if aj.get('tipo') == 'claude' or str(aj.get('proveedor', '')).startswith('Claude'):
        libs['anthropic'] = 'anthropic'  # Claude no habla el formato de OpenAI: usa su librería
    faltan = [pip for mod, pip in libs.items() if falta_libreria(mod, env)]
    if not faltan:
        return
    log.write(f'\nInstalando {", ".join(faltan)} (solo la primera vez, tarda un minuto)…\n'); log.flush()
    ok = guardado.instalar(faltan, mostrar=lambda x: (log.write(x + '\n'), log.flush()), python=PY)
    if not ok or any(falta_libreria(m, env) for m, p in libs.items() if p in faltan):
        raise RuntimeError(f'No pude instalar {", ".join(faltan)}. Cierra la app, corre instalar.bat en esta carpeta '
                           f'({RAIZ}) y vuelve a abrir iniciar.bat.')
    log.write('✓ Librerías instaladas\n'); log.flush()


def correr(proyecto, pasos, opciones):
    try:
        d = carpeta(proyecto)
        log = open(registro(d), 'a', encoding='utf-8')
    except Exception as e:
        FALLOS[proyecto] = {'paso': pasos[0], 'msg': f'No pude abrir el registro del proyecto: {e}'}
        with CANDADO:
            TRABAJO.update(proyecto=None, paso=None, proc=None, inicio=None)
        return
    try:  # ajustes.json roto o a medio guardar: se avisa y el proyecto queda libre (antes quedaba «ya está corriendo» para siempre)
        env = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
        if clave_eleven():
            env['ELEVENLABS_API_KEY'] = clave_eleven()
        env.update(voz_env(d))  # versión en otro idioma: el tráiler, los testimonios, nuevos modelos y el Short hablan en ese idioma
    except Exception as e:
        log.close()
        FALLOS[proyecto] = {'paso': pasos[0], 'msg': f'No pude leer tus ajustes (app/ajustes.json): {e}. Vuelve a guardar «⚙ Ajustes IA».'}
        with CANDADO:
            TRABAJO.update(proyecto=None, paso=None, proc=None, inicio=None)
        return
    paso = pasos[0]
    nombres = [next(x for x in PASOS if x['id'] == p)['nombre'] for p in pasos]
    ejec = time.strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:6]  # para el diagnóstico: qué llamadas son de esta ejecución
    env.update(DIAG_DIR=os.path.join(d, 'diagnosticos'), DIAG_RUN=ejec)
    # «Reintentar»: las respuestas que la IA ya dio en el paso que falló se reutilizan (no se vuelven a pedir ni a cobrar)
    env['REANUDAR_IA'] = '1' if opciones.get('_reanudar') else ''
    diag = None
    saltados, hechos, informes = [], [], []
    with CANDADO:
        TRABAJO.update(plan=nombres, i=0, inicio_total=time.time(), detenido=False)
    RESULTADO.pop(proyecto, None)
    try:
        FALLOS.pop(proyecto, None)
        if not shutil.which('ffmpeg'):
            raise RuntimeError('ffmpeg no está instalado o Windows no lo encuentra. Corre instalar.bat, '
                               'reinicia la PC y vuelve a abrir iniciar.bat.')
        asegurar_librerias(log, env)
        if len(pasos) > 1 and 'montaje' in pasos:
            # se rehace toda la cadena: los videos de una tanda anterior no deben colarse si un extra falla
            for viejo in VIDEOS_GENERADOS:
                if existe(d, viejo) and not borrar_seguro(os.path.join(d, viejo)):
                    log.write(f'· {viejo} está abierto en otro programa y no se pudo borrar; se reemplaza cuando toque.\n'); log.flush()
        if opciones.get('_limpiar_extras'):
            # los extras se vuelven a poner sobre el video base: uno viejo no debe quedar en el final
            for viejo in VIDEOS_EXTRAS + ['FINAL.mp4']:
                if existe(d, viejo) and not borrar_seguro(os.path.join(d, viejo)):
                    log.write(f'· {viejo} está abierto en otro programa y no se pudo borrar; se reemplaza cuando toque.\n'); log.flush()
        juntas = [x for x in pasos if x in CAPAS]
        if len(juntas) > 1:  # una sola codificación para etiquetas, flechas y tarjetas
            if 'capas' not in pasos:
                pasos.insert(pasos.index(juntas[-1]) + 1, 'capas')
            opciones['_capas'] = True
            shutil.rmtree(os.path.join(d, CAPAS_DIR), ignore_errors=True)  # capas de una tanda anterior no se cuelan
            for x in PASOS:  # los videos de cuando se hacían por separado: el nuevo los reemplaza
                if x['id'] in CAPAS and existe(d, x['produce']) and not borrar_seguro(os.path.join(d, x['produce'])):
                    log.write(f"· {x['produce']} está abierto en otro programa y no se pudo borrar.\n"); log.flush()
            with CANDADO:
                TRABAJO['plan'] = [next(x['nombre'] for x in PASOS if x['id'] == p) for p in pasos]
        for k, paso in enumerate(pasos):
            info = next(x for x in PASOS if x['id'] == paso)
            with CANDADO:
                TRABAJO['i'] = k
            falta = [n for n in info['necesita'] if not existe(d, n)]
            if falta:
                if len(pasos) > 1 and paso in TODO and info.get('opcional'):
                    log.write(f'\n— {info["nombre"]}: lo salto (falta {", ".join(falta)})\n'); log.flush()
                    saltados.append(info['nombre'])
                    if paso == 'trailer' and 'final_sin_trailer' not in pasos:  # sin tráiler, el video final igual sale
                        pasos.append('final_sin_trailer')
                        with CANDADO:
                            TRABAJO['plan'] = TRABAJO['plan'] + [next(x['nombre'] for x in PASOS if x['id'] == 'final_sin_trailer')]
                    continue
                log.write(f'\n✗ {info["nombre"]}: falta {", ".join(falta)}\n'); log.flush()
                FALLOS[proyecto] = {'paso': paso, 'msg': 'falta ' + ', '.join(falta)}
                return
            eleven = paso in USAN_ELEVEN or (paso == 'transcribir' and opciones.get('motor', 'scribe') in ('scribe', 'alinear'))
            if eleven and sys.platform == 'win32' and not env.get('ELEVENLABS_API_KEY'):
                raise RuntimeError('Falta tu clave de ElevenLabs. Pulsa el botón «🔑 Clave ElevenLabs» arriba a la derecha, '
                                   'pégala y guarda. (Para transcribir sin clave usa Whisper: «Cancelar» al preguntar.)')
            if TRABAJO.get('detenido'):  # «■ Detener» entre dos pasos: no arranca el siguiente (podía ser la voz, que gasta)
                FALLOS[proyecto] = {'paso': paso, 'msg': 'detenido por ti'}
                log.write(f'\n■ Detenido antes de «{info["nombre"]}»\n'); log.flush()
                return
            with CANDADO:
                TRABAJO.update(paso=paso, inicio=time.time())
            FALLOS.pop(proyecto, None)
            asegurar_node(paso, log, env)
            log.write(f'\n▶ {info["nombre"]}  ({time.strftime("%H:%M:%S")})\n'); log.flush()
            blando = False
            env['DIAG_PASO'] = paso
            env['CACHE_IA'] = os.path.join(d, 'cache_ia', paso)
            if not env['REANUDAR_IA']:
                shutil.rmtree(env['CACHE_IA'], ignore_errors=True)
            for c in comandos(paso, d, opciones):
                with CANDADO:  # «■ Detener» mientras se instalaba node (puede tardar minutos): el paso ya no arranca
                    parar = TRABAJO.get('detenido')
                    if not parar:
                        proc = subprocess.Popen(c, cwd=d, stdout=log, stderr=subprocess.STDOUT, env=env, **SIN_VENTANA)
                        TRABAJO['proc'] = proc
                if parar:
                    FALLOS[proyecto] = {'paso': paso, 'msg': 'detenido por ti'}
                    log.write(f'\n■ Detenido antes de «{info["nombre"]}»\n'); log.flush()
                    return
                if proc.wait() != 0 and info.get('blando') and len(pasos) > 1 and not TRABAJO.get('detenido'):
                    # un extra de la IA que no salió no frena el video: se sigue sin eso
                    log.write(f'· {info["nombre"]}: no se pudo ({causa(d)}). Sigo sin eso.\n'); log.flush()
                    informes.append(informe_paso(d, proyecto, paso, info, ejec, 'saltado', log))
                    shutil.rmtree(env['CACHE_IA'], ignore_errors=True)
                    blando = True
                    break
                if proc.returncode != 0:
                    if TRABAJO.get('detenido'):
                        log.write(f'✗ {info["nombre"]}: lo detuviste.\n'); log.flush()
                        FALLOS[proyecto] = {'paso': paso, 'msg': 'detenido por ti'}
                        return
                    log.write(f'✗ {info["nombre"]} falló (código {proc.returncode}). Revisa el mensaje de arriba.\n'); log.flush()
                    FALLOS[proyecto] = {'paso': paso, 'msg': causa(d)}
                    diag = informe_paso(d, proyecto, paso, info, ejec, 'fallo', log)
                    return
            if blando:
                saltados.append(info['nombre'])
                if paso == 'trailer':  # sin tráiler, el video final igual sale
                    pasos.append('final_sin_trailer')
                    with CANDADO:
                        TRABAJO['plan'] = TRABAJO['plan'] + [next(x['nombre'] for x in PASOS if x['id'] == 'final_sin_trailer')]
                continue
            log.write(f'✓ {info["nombre"]} listo en {int(time.time() - TRABAJO["inicio"])} s\n'); log.flush()
            informes.append(informe_paso(d, proyecto, paso, info, ejec, 'ok', log))  # solo si hubo llamadas fallidas o rechazadas
            shutil.rmtree(env['CACHE_IA'], ignore_errors=True)  # el paso terminó: sus respuestas guardadas ya no hacen falta
            hechos.append(info['nombre'])
            if paso == 'voz':  # armaste la voz: el guion quedó aprobado y sirve de ejemplo para los próximos
                try:
                    conocimiento.aprender_guion(d)
                except Exception as e:
                    log.write(f'· no pude guardar el guion como ejemplo ({type(e).__name__}: {e})\n')
            if paso == 'revisar_imagen' and k < len(pasos) - 1:
                log.flush()
                avisos = avisos_de_imagen(d, info['nombre'])
                if avisos:
                    # pedido de fabian (29/10/2026): en HONOR 8 LITE la revisión avisó bloques corridos y «Hacer todo» siguió
                    # igual con la voz (unos 12.000 créditos). Ahora se frena acá, antes de gastar, para corregirlos primero
                    log.write(f'\n⏸ Me frené antes de la voz: la revisión dejó {len(avisos)} aviso(s) de voz que no va con la '
                              'imagen. Corrige esos bloques en «📝 Ver y editar guion» y vuelve a tocar «▶ Hacer todo»: la revisión '
                              'no se repite y sigue con la voz.\n'); log.flush()
                    opciones['_pausa'], opciones['_avisos'] = 'revision', avisos
                    break
    except Exception as e:
        # sin esto el paso moría en silencio y la app volvía a «Listo para hacer» sin decir nada
        import traceback
        msg = str(e) if isinstance(e, RuntimeError) else f'{type(e).__name__}: {e}'
        if isinstance(e, FileNotFoundError):
            msg = f'Windows no encontró un programa que hace falta ({e}). Corre instalar.bat y reinicia la PC.'
        log.write(f'\nERROR: {msg}\n{traceback.format_exc()}\n✗ falló\n'); log.flush()
        FALLOS[proyecto] = {'paso': paso, 'msg': msg}
        diag = informe_paso(d, proyecto, paso, next((x for x in PASOS if x['id'] == paso), {'nombre': paso}), ejec, 'fallo', log)
    finally:
        f = FALLOS.get(proyecto)
        informes = [x for x in informes + [diag] if x]
        resultado = 'interrumpido' if f else 'completado_con_incidencias' if informes or saltados else 'completado'
        resumen = None
        try:
            resumen = diagnostico.resumen_ejecucion(os.path.join(d, 'diagnosticos'), proyecto, ejec, resultado, hechos, saltados,
                                                    next((x['nombre'] for x in PASOS if f and x['id'] == f['paso']), ''), informes,
                                                    motivo='lo detuviste' if f and f.get('msg') == 'detenido por ti' else '')
            if resumen:
                log.write(f"· {resumen['texto']} Resumen en diagnosticos/{resumen['archivo']}.txt\n")
        except Exception as e:
            log.write(f'· no pude escribir el resumen de la ejecución ({type(e).__name__}: {e})\n')
        try:  # lo que contestaste y confirmaste en este proyecto queda aprendido para los próximos videos
            conocimiento.aprender_de_proyecto(d)
        except Exception as e:
            log.write(f'· no pude anotar lo aprendido ({type(e).__name__}: {e})\n')
        log.close()
        RESULTADO[proyecto] = {'resultado': resultado, 'incidencias': informes if not f else [], 'resumen': resumen,'ok': not f, 'paso': next((x['nombre'] for x in PASOS if f and x['id'] == f['paso']), None),
                               'msg': f['msg'] if f else '', 'hechos': hechos, 'saltados': saltados, 'total': len(pasos),
                               'segundos': int(time.time() - (TRABAJO['inicio_total'] or time.time())), 'cuando': time.time(),
                               'pausa': None if f else opciones.get('_pausa'), 'seguir': opciones.get('_seguir'), 'diagnostico': diag if f else None,
                               'avisos': opciones.get('_avisos') if not f else None,
                               'repetir': {'pasos': pasos[pasos.index(f['paso']):] if f and f['paso'] in pasos else [],
                                           'opciones': opciones} if f and diag and diag.get('reintentable') else None}
        with CANDADO:
            TRABAJO.update(proyecto=None, paso=None, proc=None, inicio=None, plan=[], i=0, inicio_total=None)
        threading.Thread(target=al_terminar, args=(proyecto,), daemon=True).start()


YT = {}  # «▶️ YouTube»: avance de la subida de cada proyecto
BIBLIO = {'proc': None, 'accion': ''}  # «📚 Biblioteca de tus videos»: lo que está corriendo


def biblio_correr(accion, canal='', whisper=False):
    """Junta las transcripciones del canal o le pide a la IA que las lea, aparte (puede tardar), con su registro."""
    if BIBLIO['proc'] and BIBLIO['proc'].poll() is None:
        raise ValueError('La biblioteca ya está trabajando: espera a que termine.')
    sys.path.insert(0, m('conocimiento'))
    import biblioteca
    os.makedirs(conocimiento.CARPETA, exist_ok=True)
    c = [PY, m('conocimiento', 'biblioteca.py'), '--accion', accion, '--ajustes', AJUSTES]
    if canal:
        c += ['--canal', canal]
    if whisper:
        c.append('--whisper')
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1', PYTHONUNBUFFERED='1',
               DIAG_DIR=os.path.join(conocimiento.CARPETA, 'diagnosticos'), DIAG_RUN=time.strftime('%Y%m%d_%H%M%S_biblioteca'))
    BIBLIO.update(proc=subprocess.Popen(c, cwd=RAIZ, env=env, stdout=open(biblioteca.LOG, 'w', encoding='utf-8'),
                                        stderr=subprocess.STDOUT), accion=accion)


def biblio_semanal():
    """Una vez por semana, al abrir la app: suma las transcripciones de tus videos nuevos (gratis) y, si lo pediste,
    la IA los lee."""
    try:
        sys.path.insert(0, m('conocimiento'))
        import biblioteca
        aj = leer_ajustes()
        b = aj.get('biblioteca') or {}
        if not b.get('semanal'):
            return
        ultima = biblioteca.estado().get('ultima')
        if ultima and time.time() - time.mktime(time.strptime(ultima, '%Y-%m-%d %H:%M')) < 7 * 86400:
            return
        biblio_correr('juntar', b.get('canal', ''))
        BIBLIO['proc'].wait()
        if b.get('ia') and aj.get('modelo') and biblioteca.pendientes():
            biblio_correr('aprender')
    except Exception as e:
        print(f'· biblioteca semanal: {type(e).__name__}: {e}', flush=True)


CANAL_YT = {'corriendo': False, 'log': []}


def canal_aprender():
    """«📊 Aprender de todo mi canal»: en segundo plano (tarda unos minutos la primera vez)."""
    if CANAL_YT['corriendo']:
        return
    CANAL_YT.update(corriendo=True, log=[], error='')
    try:
        c = yt_config()
        canal_yt.aprender(c, lambda x: CANAL_YT['log'].append(x))
        if c.get('_cambio'):
            yt_guardar(c)
    except Exception as e:
        CANAL_YT['error'] = str(e)
        CANAL_YT['log'].append(f'✗ {e}')
    finally:
        CANAL_YT['corriendo'] = False


def canal_semanal():
    """Una vez por semana, al abrir la app: si YouTube está conectado, vuelve a aprender de todo el canal (gratis)."""
    try:
        if not (yt_config().get('token') or {}).get('refresh'):
            return
        a = canal_yt.ultimo()
        if a and time.time() - time.mktime(time.strptime(a['fecha'], '%Y-%m-%d %H:%M')) < 7 * 86400:
            return
        canal_aprender()
    except Exception as e:
        print(f'· canal semanal: {type(e).__name__}: {e}', flush=True)


def yt_config():
    return dict(youtube.config(leer_ajustes()))


def yt_guardar(c):
    c.pop('_cambio', None)
    aj = leer_ajustes()
    aj['youtube'] = c
    tmp = AJUSTES + '.tmp'
    json.dump(aj, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, AJUSTES)


def yt_srt_final(d):
    """Los subtítulos en español que van con FINAL.mp4 (los del tráiler ya vienen corridos)."""
    if existe(d, 'FINAL.srt') and existe(d, 'FINAL.mp4') and os.path.getmtime(os.path.join(d, 'FINAL.srt')) >= os.path.getmtime(os.path.join(d, 'FINAL.mp4')) - 5:
        return os.path.join(d, 'FINAL.srt')
    f = srt_de(d, ultimo_video(d, None))
    return os.path.join(d, f) if existe(d, f) else None


def yt_bloques(d):
    """Los bloques del guion con el segundo en que empiezan en FINAL.mp4."""
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8')) if existe(d, 'guion.json') else {'bloques': []}
    f = yt_srt_final(d)
    inicios = youtube.inicio_bloques(g.get('bloques', []), open(f, encoding='utf-8', errors='replace').read() if f else '')
    return [{'id': b['id'], 's': round(inicios[b['id']], 1), 'texto': b.get('texto', '')} for b in g.get('bloques', []) if b['id'] in inicios]


def yt_ia(d, tarea, entrada):
    os.makedirs(os.path.join(d, 'youtube'), exist_ok=True)
    json.dump(entrada, open(os.path.join(d, 'youtube', f'entrada_{tarea}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1', DIAG_DIR=os.path.join(d, 'diagnosticos'),
               DIAG_RUN=time.strftime('%Y%m%d_%H%M%S_youtube'))
    r = subprocess.run([PY, m('youtube', 'ia_youtube.py'), '--proyecto', d, '--tarea', tarea, '--ajustes', AJUSTES],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=600)
    if r.returncode:
        raise youtube.ErrorYT((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else 'la IA no contestó')
    return json.load(open(os.path.join(d, 'youtube', f'{tarea}.json'), encoding='utf-8'))


def yt_publicar(p, op):
    """Sube FINAL.mp4 con todo lo que tiene el proyecto. Lo que falla después de subir el video (subtítulos, miniatura,
    comentario) no frena el resto: queda anotado en los avisos."""
    d = carpeta(p)
    est = YT[p] = {'estado': 'subiendo', 'avance': 0, 'avisos': []}
    try:
        c = yt_config()
        meta = json.load(open(os.path.join(d, 'youtube', 'metadatos.json'), encoding='utf-8'))
        titulo = (meta.get('titulo') or (meta.get('titulos') or [{}])[meta.get('elegido') or 0].get('titulo') or '').strip()
        if not titulo:
            raise youtube.ErrorYT('Falta el título: pulsa «✨ Proponer» o escribe uno.')
        desc = meta.get('descripcion', '').strip()
        if meta.get('capitulos_texto'):
            desc += '\n\n' + meta['capitulos_texto'].strip()
        if meta.get('advertencia'):
            desc += '\n\n⚠️ ' + meta['advertencia'].strip()
        vid = youtube.subir_video(c, os.path.join(d, 'FINAL.mp4'),
                                  {'titulo': titulo, 'descripcion': desc, 'etiquetas': meta.get('etiquetas', []),
                                   'privacidad': op.get('privacidad', 'private'), 'publicar_en': op.get('publicar_en')},
                                  lambda x: est.update(avance=round(x * 100)))
        est.update(avance=100, estado='detalles', id=vid)
        json.dump({'id': vid, 'url': f'https://youtu.be/{vid}', 'titulo': titulo, 'cuando': time.strftime('%Y-%m-%d %H:%M')},
                  open(os.path.join(d, 'youtube', 'publicado.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if op.get('subtitulos', True):
            f = yt_srt_final(d)
            try:
                if f:
                    youtube.subir_subtitulos(c, vid, 'es', 'Español', open(f, encoding='utf-8', errors='replace').read())
                cortes = existe(d, '8_testimonios.mp4') or existe(d, '9_modelos.mp4')
                otros = [x for x in (subtitulos.leer(d).get('textos') or {}) if x != 'es']
                if otros and cortes:
                    est['avisos'].append('Los subtítulos en otros idiomas no se subieron: con testimonios o nuevos modelos sus tiempos no coinciden.')
                elif otros:
                    corre = duracion_original(d, 'trailer.mp4') if existe(d, 'trailer.mp4') and edicion(d).get('trailer_donde', 'inicio') == 'inicio' else 0
                    for lang in otros:
                        youtube.subir_subtitulos(c, vid, lang, lang, subtitulos.srt(d, lang, corre))
            except Exception as e:
                est['avisos'].append(f'Subtítulos: {e}')
        mini = sorted(glob.glob(os.path.join(d, 'miniatura*.jpg')) + glob.glob(os.path.join(d, 'miniatura*.png')), key=os.path.getmtime)
        if op.get('miniatura', True) and mini:
            try:
                youtube.subir_miniatura(c, vid, mini[-1])
            except Exception as e:
                est['avisos'].append(f'Miniatura: {e}')
        elif op.get('miniatura', True):
            est['avisos'].append('No había miniatura en el proyecto: súbela en esta página o ponla en YouTube Studio.')
        if op.get('comentario', True) and meta.get('comentario', '').strip():
            try:
                youtube.comentar(c, vid, meta['comentario'].strip())
                est['avisos'].append('El comentario quedó publicado: fíjalo en YouTube (⋮ → Fijar). La API no deja fijarlo.')
            except Exception as e:
                est['avisos'].append(f'Comentario: {e}')
        if c.get('_cambio'):
            yt_guardar(c)
        est['estado'] = 'listo'
        flujo.avisar(leer_ajustes(), f'▶️ {p}: subido a YouTube', f'https://youtu.be/{vid}', f'https://youtu.be/{vid}')
    except Exception as e:
        est.update(estado='fallo', msg=str(e))
        flujo.avisar(leer_ajustes(), f'▶️ {p}: no se pudo subir', str(e), url_celular(), fallo=True)


def url_celular():
    """La dirección con que el celular abre la app (Tailscale primero: anda en casa y afuera), o '' si está apagado."""
    if ESCUCHA[0] == '127.0.0.1':
        return ''
    dirs = celular.direcciones(PUERTO)
    t = [x for x in dirs if 'Tailscale' in x['tipo']] or dirs
    return t[0]['url'] + '/' if t else ''


def ocupado():
    with CANDADO:
        return bool(TRABAJO['proyecto'])


def al_terminar(proyecto):
    """Después de cada trabajo: aviso al celular y, si la «🌙 Cola» está andando, el próximo proyecto."""
    try:
        aj, r = leer_ajustes(), RESULTADO.get(proyecto)
        flujo.termino(PROYECTOS, proyecto, r)
        flujo.avisar_resultado(aj, proyecto, r, url_celular())
        time.sleep(3)  # que la página alcance a mostrar el resultado antes de arrancar otro
        avanzar_cola()
    except Exception as e:
        print(f'· aviso o cola: {type(e).__name__}: {e}', flush=True)


def avanzar_cola():
    """Arranca el próximo de la «🌙 Cola»; si ya no queda ninguno, avisa cómo salió la noche."""
    if flujo.siguiente(PROYECTOS, PUERTO, ocupado) == 'vacia':
        hechos = [x for x in flujo.leer_cola(PROYECTOS).get('items', []) if x.get('estado') in ('hecho', 'fallo')]
        ok = sum(x['estado'] == 'hecho' for x in hechos)
        flujo.avisar(leer_ajustes(), '🌙 Cola terminada', f'{ok} de {len(hechos)} proyectos salieron bien.', url_celular(), fallo=ok < len(hechos))


def ultima_linea(log):
    """Lo último que escribió el paso (también el avance de ffmpeg, que reescribe la línea con \\r)."""
    for l in reversed(re.split(r'[\r\n]+', log[-3000:])):
        l = l.strip()
        if l:
            m = re.search(r'time=(\d+:\d\d:\d\d)', l)
            return f'procesando el video… va en {m.group(1)}' if m and l.startswith('frame=') else l[:200]
    return ''


_PROMEDIOS = {}  # nombre del paso -> (cuándo se calculó, promedio en s, cuántas veces)


def promedio_paso(nombre):
    """Cuánto tarda en promedio este paso, con lo que tardó en todos tus proyectos de esta PC («✓ … listo en N s»).
    Se recalcula cada 2 minutos (la barra pregunta cada segundo)."""
    hecho = _PROMEDIOS.get(nombre)
    if hecho and time.time() - hecho[0] < 120:
        return hecho[1], hecho[2]
    veces = []
    for p in os.listdir(PROYECTOS) if os.path.isdir(PROYECTOS) else []:
        try:
            texto = open(registro(os.path.join(PROYECTOS, p)), encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        veces += [int(s) for s in re.findall(r'✓ ' + re.escape(nombre) + r' listo en (\d+) s', texto)]
    prom = round(sum(veces) / len(veces)) if veces else None
    _PROMEDIOS[nombre] = (time.time(), prom, len(veces))
    return prom, len(veces)


def avance_paso(completo, paso):
    """Lo que la barra muestra del paso en curso: su % real (las líneas «[N%]» que escriben los pasos), las últimas
    líneas del registro, cuánto tardó este mismo paso la última vez que salió bien y su promedio en todos tus proyectos
    (para estimar lo que falta)."""
    nombre = next((x['nombre'] for x in PASOS if x['id'] == paso), paso or '')
    seccion = completo[completo.rfind('\n▶'):] if '\n▶' in completo else completo[-6000:]
    pcts = re.findall(r'\[(\d{1,3})%\]', seccion)
    lineas = [l.strip() for l in re.split(r'[\r\n]+', seccion[-6000:]) if l.strip() and not l.startswith('frame=')][-12:]
    antes = re.findall(r'✓ ' + re.escape(nombre) + r' listo en (\d+) s', completo) if nombre else []
    prom, veces = promedio_paso(nombre) if nombre else (None, 0)
    return {'pct_paso': min(100, int(pcts[-1])) if pcts else None, 'ultimas': lineas,
            'antes_s': int(antes[-1]) if antes else None, 'promedio_s': prom, 'promedio_veces': veces}


def causa(d):
    """La línea que explica el error, dentro de lo último que escribió el paso."""
    lineas = open(registro(d), encoding='utf-8', errors='replace').read().split('\n▶')[-1].strip().splitlines()
    for k, l in enumerate(lineas):
        if l.startswith('ERROR:'):
            resto = [x.strip() for x in lineas[k + 1:] if x.strip() and not x.startswith('✗')]
            return ' '.join([l[6:].strip()] + resto)
    utiles = [l.strip() for l in lineas[1:] if l.strip() and not l.startswith('✗')]
    return utiles[-1] if utiles else 'sin detalle'


VOZ_VIEJA = {}  # carpeta -> (firma de guion.json y voz/, resultado): estado() se pide cada segundo


def voz_vieja(d):
    """Bloques del guion cuya voz ya hecha es de otro texto (cambiaste el guion y no volviste a «Generar voz»).
    Solo si ya hay voces: en un proyecto sin voz todavía no hay nada viejo. No llama a ElevenLabs."""
    g, v = os.path.join(d, 'guion.json'), os.path.join(d, 'voz')
    mp3 = [f for f in os.listdir(v) if f.endswith('.mp3')] if os.path.isdir(v) else []
    if not mp3 or not os.path.exists(g):
        return None
    firma = (os.path.getmtime(g), len(os.listdir(v)), max(os.path.getmtime(os.path.join(v, f)) for f in os.listdir(v)))
    if VOZ_VIEJA.get(d, (None,))[0] == firma:
        return VOZ_VIEJA[d][1]
    try:
        r = subprocess.run([PY, m('voz', 'voz.py'), '--guion', g, '--salida', v, '--costo'] + voz_args(d),
                           capture_output=True, text=True, encoding='utf-8', timeout=60, **SIN_VENTANA)
        res = json.loads(r.stdout.strip().splitlines()[-1])
        res = res if res.get('bloques') else None
    except (ValueError, IndexError, subprocess.TimeoutExpired):
        res = None
    VOZ_VIEJA[d] = (firma, res)
    return res


def costo_voz(d, desde=None, hasta=None):
    """Qué bloques generarían voz en ElevenLabs y cuántos caracteres (de L desde a L hasta, si se dan). No llama a ElevenLabs."""
    if not existe(d, 'guion.json'):
        return {'bloques': [], 'caracteres': 0}
    datos = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    if desde:
        ids = [str(b.get('id', '')).upper() for b in datos['bloques']]
        x, y = str(desde).strip().upper(), str(hasta or desde).strip().upper()
        if x in ids and y in ids:
            i, j = sorted((ids.index(x), ids.index(y)))
            datos['bloques'] = datos['bloques'][i:j + 1]
    f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, dir=d, prefix='.costo_', encoding='utf-8')
    json.dump(datos, f, ensure_ascii=False)
    f.close()
    try:
        r = subprocess.run([PY, m('voz', 'voz.py'), '--guion', f.name, '--salida', os.path.join(d, 'voz'), '--costo'] + voz_args(d),
                           capture_output=True, text=True, encoding='utf-8', timeout=60, **SIN_VENTANA)
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError, subprocess.TimeoutExpired):
        return {'bloques': [], 'caracteres': 0, 'desconocido': True}
    finally:
        os.remove(f.name)


FRASE = re.compile(r'[^.?!¿¡]*[¿¡]?[^.?!]*[.?!…]+|\S[^.?!]*$')


def frases_guion(d):
    """«🎞 Frase por frase» del editor de guion: por bloque cuya voz ya está hecha con su texto actual, cuándo dice la voz
    cada frase (segundos desde que empieza su voz). Los bloques sin voz o con el texto cambiado los estima el editor.
    Es la revisión que destapó los bloques corridos de HONOR 8 LITE (29/10/2026): ver qué se ve mientras se dice cada frase."""
    try:
        g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    out = {}
    for b in g.get('bloques', []):
        try:
            al = json.load(open(os.path.join(d, 'voz', f"{b['id']}.align.json"), encoding='utf-8'))
            txt, t0, t1 = ''.join(al['characters']), al['character_start_times_seconds'], al['character_end_times_seconds']
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if not txt.strip() or txt.strip() not in (str(b.get('texto') or '').strip(), texto_voz(b.get('texto'))):
            continue  # la voz es de otro texto: el editor estima
        out[b['id']] = {'texto': b.get('texto') or '',  # el editor usa estos tiempos solo mientras el texto siga igual
                        'frases': [{'texto': m.group().strip(), 't0': t0[m.start()], 't1': t1[min(m.end(), len(t1)) - 1]}
                                   for m in FRASE.finditer(txt) if len(m.group().strip()) > 1]}
    return out


def gasto_sin_confirmar(d, paso, pasos, datos):
    """Si el trabajo gastaría créditos de ElevenLabs (la voz del video o una música nueva) y no viene con «SI» escrito,
    el motivo para no arrancarlo; None si puede arrancar. Pedido de fabian (29/10/2026): un «▶ Hacer todo» generó la voz
    entera de HONOR 8 LITE (unos 12.000 créditos) sin que él lo hubiera ordenado; desde ahí hay que escribir SI."""
    if str(datos.get('confirmo') or '').strip().upper() in ('SI', 'SÍ'):
        return None
    gasta = []
    if 'voz' in pasos or paso == 'prueba':
        c = costo_voz(d, datos.get('desde'), datos.get('hasta')) if paso == 'prueba' else costo_voz(d)
        if c.get('desconocido'):
            gasta.append('la voz que falte (no pude calcular cuánta)')
        elif c.get('caracteres'):
            n = f"{c['caracteres']:,}".replace(',', '.')
            gasta.append(f"unos {n} créditos de voz ({len(c['bloques'])} bloque{'' if len(c['bloques']) == 1 else 's'}: {', '.join(c['bloques'])})")
    if 'musica' in pasos and not os.path.exists(MUSICA_FIJA) and not existe(d, 'musica.mp3'):
        gasta.append('una música nueva (unos 2.950 créditos)')
    if not gasta:
        return None
    return ('Esto gasta ElevenLabs: ' + ' y '.join(gasta) + '. No lo arranqué porque falta escribir SI. Recarga la página '
            '(F5) y vuelve a tocar el botón: ahora te pide escribir SI antes de gastar.')


def estado(proyecto):
    d = carpeta(proyecto)
    archivos = {}
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        q = os.path.join(d, f)
        archivos[f] = {'tam': os.path.getsize(q) if os.path.isfile(q) else len(os.listdir(q)), 'carpeta': os.path.isdir(q),
                       'fecha': os.path.getmtime(q)}
    pasos = []
    for p in PASOS:
        if p.get('oculto'):
            continue
        pasos.append({**p, 'listo': existe(d, p['produce']), 'puede': all(existe(d, n) for n in p['necesita'])})
    # etiquetas, flechas y tarjetas se muestran como un solo paso: se hacen juntos, en una sola pasada
    juntos = [p for p in pasos if p['id'] in CAPAS]
    if juntos:
        hechos = [p for p in juntos if p['listo'] or p['id'] in capas_hechas(d)]
        for p in juntos:
            p['dentro'] = True  # la lista no los muestra sueltos; «Agregar extras» sí mira cada uno
        pasos[pasos.index(juntos[0]):pasos.index(juntos[0])] = [{
            'id': 'capas_juntas', 'ids': CAPAS + ['capas'], 'nombre': 'Etiquetas, flechas y tarjetas (una sola pasada)', 'opcional': True,
            'listo': bool(hechos), 'puede': any(p['puede'] for p in juntos),
            'produce': next((p['produce'] for p in reversed(juntos) if existe(d, p['produce'])), juntos[-1]['produce']),
            'necesita': ['3_voz.mp4', 'etiquetas.json, senales.json o tarjetas']}]
    completo = open(registro(d), encoding='utf-8', errors='replace').read() if existe(d, 'registro.txt') else ''
    log = completo[-12000:]
    with CANDADO:
        t = dict(proyecto=TRABAJO['proyecto'], paso=TRABAJO['paso'],
                 segundos=int(time.time() - TRABAJO['inicio']) if TRABAJO['inicio'] else 0,
                 plan=TRABAJO['plan'], i=TRABAJO['i'],
                 total_s=int(time.time() - TRABAJO['inicio_total']) if TRABAJO['inicio_total'] else 0)
    if t['proyecto'] == proyecto:
        t['linea'] = ultima_linea(log)
        t.update(avance_paso(completo, t['paso']))
        # el video que el paso está escribiendo todavía no se puede ver (está a medias): la página no lo abre
        prod = {x['produce'] for x in PASOS if x['id'] == t['paso'] or x['nombre'] == t['paso']}
        if t['paso'] in ('trailer', 'final_sin_trailer') or prod & {'trailer.mp4'}:
            prod.add('FINAL.mp4')
        ahora = time.time()
        for f, info in archivos.items():
            if f.endswith('.mp4') and f != 'montaje_en_curso.mp4' and (f in prod or ahora - info['fecha'] < 8):
                info['en_proceso'] = True
    return {'archivos': archivos, 'capas_hechas': capas_hechas(d), 'pasos': pasos, 'registro': log, 'trabajo': t, 'fallo': FALLOS.get(proyecto),
            'resultado': RESULTADO.get(proyecto),
            'musica_fija': (leer_ajustes().get('musica_fija_de') or 'una pista guardada') if os.path.exists(MUSICA_FIJA) else '',
            'actualizada': os.path.getmtime(__file__) != INICIO_APP,
            'pagina': os.path.getmtime(os.path.join(AQUI, 'index.html')),
            'duracion_original': duracion_original(d),
            'voz_vieja': None if t['proyecto'] == proyecto else voz_vieja(d)}


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _marca(self, m, p=''):
        """Una marca de «🧠 Conocimiento»: su texto y ruta, todas las marcas y la del proyecto abierto."""
        try:
            detectada = conocimiento.marca_de_proyecto(carpeta(p)) if p else ''
        except Exception:
            detectada = ''
        m = conocimiento._nombre_marca(m or detectada or conocimiento.MARCAS_BASE[0])
        return {'marcas': conocimiento.marcas(), 'marca': m, 'texto': conocimiento.leer_marca(m),
                'ruta': conocimiento._ruta_marca(m), 'detectada': detectada}

    def responder(self, cuerpo, tipo='application/json', codigo=200):
        if not isinstance(cuerpo, (bytes, bytearray)):
            cuerpo = json.dumps(cuerpo, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(cuerpo)))
        self.send_header('Cache-Control', 'no-store')  # que el navegador no muestre una versión vieja de la app
        self.end_headers()
        self.wfile.write(cuerpo)

    def error(self, msg, codigo=400):
        self.responder({'error': msg}, codigo=codigo)

    def puerta(self):
        """«📱 Celular»: desde tu PC todo sigue igual. Desde otra dirección solo se entra con el acceso activado, desde el
        Wi‑Fi de casa o Tailscale y con el PIN. Devuelve True si ya contestó (y el pedido no sigue)."""
        ip = self.client_address[0]
        if celular.es_local(ip):
            return False
        aj = leer_ajustes()
        if not (celular.activo(aj) and celular.red_permitida(ip) and celular.host_valido(self.headers.get('Host'))):
            self.error('acceso desde otro aparato apagado', 403)
            return True
        ruta, q = self.q()
        if ruta in celular.SOLO_PC:
            self.error('esto se cambia solo en la app del PC', 403)
            return True
        if ruta in celular.LIBRES or celular.autorizado(aj, self.headers.get('Cookie')):
            return False
        if self.command == 'GET' and not ruta.startswith('/api/'):
            self.send_response(302)
            self.send_header('Location', '/celular?volver=' + urllib.parse.quote(self.path, safe=''))
            self.send_header('Content-Length', '0')
            self.end_headers()
        else:
            self.error('falta el PIN del celular: recarga la página', 401)
        return True

    def mismo_origen(self):
        """Otra página abierta en el navegador no puede borrar, detener ni cambiar tus claves."""
        origen = urllib.parse.urlparse(self.headers.get('Origin') or '').hostname
        host = (self.headers.get('Host') or '').split(':')[0]
        if celular.es_local(self.client_address[0]):
            return host in ('localhost', '127.0.0.1', '[::1]', '') and origen in (None, 'localhost', '127.0.0.1', '::1')
        return origen is None or origen == host  # el celular ya pasó por puerta(): mismo nombre que la página

    def youtube_post(self, ruta, q, largo):
        """«▶️ YouTube»: lo que cambia algo (conectar, proponer, publicar, aprender)."""
        if ruta == '/api/youtube/cliente':
            c = yt_config()
            youtube.guardar_cliente(c, self.rfile.read(min(largo, 20000)).decode('utf-8', errors='replace'))
            yt_guardar(c)
            return self.responder({'ok': True})
        if ruta == '/api/youtube/desconectar':
            c = yt_config()
            c.pop('token', None)
            yt_guardar(c)
            return self.responder({'ok': True})
        if ruta == '/api/youtube/canal':  # «📊 Aprender de todo mi canal» (en segundo plano)
            if not (yt_config().get('token') or {}).get('refresh'):
                return self.error('Primero conecta YouTube (arriba, «1 · Tu canal»).')
            threading.Thread(target=canal_aprender, daemon=True).start()
            return self.responder({'ok': True})
        if ruta == '/api/youtube/respuestas':  # «💬 Responder comentarios»: la IA propone, tú apruebas cada una
            c = yt_config()
            com = youtube.sin_responder(c, youtube.canal(c)['id'], maximo=int(json.loads(self.rfile.read(largo) or b'{}').get('maximo') or 25))
            if c.get('_cambio'):
                yt_guardar(c)
            if not com:
                return self.responder({'respuestas': [], 'comentarios': []})
            r = yt_ia(os.path.join(PROYECTOS, '.canal'), 'respuestas', {'comentarios': com})
            por_id = {x.get('id'): x for x in r.get('respuestas') or [] if isinstance(x, dict)}
            return self.responder({'comentarios': [dict(x, **{k: por_id.get(x['id'], {}).get(k) for k in ('respuesta', 'no_responder', 'duda')})
                                                   for x in com]})
        if ruta == '/api/youtube/responder':  # publicar UNA respuesta que el autor aprobó (botón «Publicar respuesta»)
            datos = json.loads(self.rfile.read(largo) or b'{}')
            c = yt_config()
            rid = youtube.responder(c, datos.get('id'), datos.get('texto'))
            if c.get('_cambio'):
                yt_guardar(c)
            return self.responder({'ok': True, 'id': rid})
        if ruta == '/api/youtube/ideas':  # temas para los próximos videos, de todo el canal
            c = yt_config()
            videos = youtube.mis_videos(c)
            com = youtube.comentarios(c, canal_id=youtube.canal(c)['id'], maximo=400)
            semillas = []
            for v in sorted(videos, key=lambda x: -x['vistas'])[:8]:
                w = ' '.join(v['titulo'].split()[:3])
                if w.lower() not in semillas:
                    semillas.append(w.lower())
            busq = {s_: youtube.sugerencias(s_) for s_ in semillas}
            if c.get('_cambio'):
                yt_guardar(c)
            d = os.path.join(PROYECTOS, '.canal')
            return self.responder(yt_ia(d, 'ideas', {'mis_videos': videos, 'comentarios': com, 'busquedas': busq}))
        d = carpeta(q['p'])
        if ruta == '/api/youtube/proponer':
            if not existe(d, 'guion.json'):
                return self.error('Este proyecto no tiene guion todavía.')
            c = yt_config()
            videos = []
            if (c.get('token') or {}).get('refresh'):
                try:
                    videos = sorted(youtube.mis_videos(c), key=lambda x: -x['vistas'])[:40]
                except youtube.ErrorYT:
                    pass
                if c.get('_cambio'):
                    yt_guardar(c)
            bloques = yt_bloques(d)
            if not bloques:  # sin video final todavía: los tiempos del guion
                g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
                bloques = [{'id': b['id'], 's': b.get('inicio_min', 0), 'texto': b.get('texto', '')} for b in g.get('bloques', [])]
            idea = open(os.path.join(d, 'idea.txt'), encoding='utf-8').read() if existe(d, 'idea.txt') else ''
            r = yt_ia(d, 'metadatos', {'bloques': bloques, 'mis_videos': videos, 'idea': idea, 'paginas': leer_ajustes().get('paginas', [])})
            r['titulo'] = ((r.get('titulos') or [{}])[r.get('elegido') or 0] or {}).get('titulo', '')
            r['capitulos_texto'] = youtube.texto_capitulos(r.get('capitulos') or [], {b['id']: b['s'] for b in bloques})
            json.dump(r, open(os.path.join(d, 'youtube', 'metadatos.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            return self.responder(r)
        if ruta == '/api/youtube/guardar':  # lo que corregiste a mano: título, descripción, capítulos, etiquetas, comentario
            nuevo = json.loads(self.rfile.read(largo) or b'{}')
            os.makedirs(os.path.join(d, 'youtube'), exist_ok=True)
            f = os.path.join(d, 'youtube', 'metadatos.json')
            viejo = json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {}
            viejo.update({k: nuevo[k] for k in ('titulo', 'descripcion', 'capitulos_texto', 'etiquetas', 'comentario', 'advertencia') if k in nuevo})
            json.dump(viejo, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            return self.responder({'ok': True})
        if ruta == '/api/youtube/miniatura':
            ext = '.png' if (self.headers.get('Content-Type') or '').endswith('png') else '.jpg'
            datos = self.rfile.read(largo)
            if len(datos) > 2 * 1024 * 1024:
                return self.error('La miniatura pesa más de 2 MB, el máximo de YouTube.')
            open(os.path.join(d, 'miniatura_subida' + ext), 'wb').write(datos)
            return self.responder({'ok': True})
        if ruta == '/api/youtube/publicar':
            if not existe(d, 'FINAL.mp4'):
                return self.error('Todavía no hay FINAL.mp4: termina el video primero.')
            if (YT.get(q['p']) or {}).get('estado') in ('subiendo', 'detalles'):
                return self.error('Ya se está subiendo.')
            if not existe(d, os.path.join('youtube', 'metadatos.json')):
                return self.error('Falta el título y la descripción: pulsa «✨ Proponer».')
            op = json.loads(self.rfile.read(largo) or b'{}')
            YT[q['p']] = {'estado': 'subiendo', 'avance': 0, 'avisos': []}
            threading.Thread(target=yt_publicar, args=(q['p'], op), daemon=True).start()
            return self.responder({'ok': True})
        if ruta == '/api/youtube/vincular':  # un video que ya subiste a mano: para aprender de su retención y comentarios
            vid = youtube.id_de(json.loads(self.rfile.read(largo) or b'{}').get('url'))
            c = yt_config()
            v = youtube.video(c, vid)
            if c.get('_cambio'):
                yt_guardar(c)
            os.makedirs(os.path.join(d, 'youtube'), exist_ok=True)
            json.dump({'id': vid, 'url': f'https://youtu.be/{vid}', 'titulo': v['titulo'], 'cuando': v['publicado'][:10]},
                      open(os.path.join(d, 'youtube', 'publicado.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            return self.responder({'ok': True, 'video': v})
        if ruta == '/api/youtube/aprender':  # retención por bloque + preguntas de los comentarios → «🧠 Conocimiento»
            f = os.path.join(d, 'youtube', 'publicado.json')
            if not os.path.exists(f):
                return self.error('Primero vincula el video de YouTube de este proyecto (o publícalo desde aquí).')
            vid = json.load(open(f, encoding='utf-8'))['id']
            c = yt_config()
            v = youtube.video(c, vid)
            curva = youtube.retencion(c, vid)
            com = youtube.comentarios(c, vid=vid, maximo=300)
            if c.get('_cambio'):
                yt_guardar(c)
            bloques = yt_bloques(d)
            por_bloque = []
            for b in bloques:
                if curva and v['segundos']:
                    x = min(curva, key=lambda f_: abs(f_['t'] - b['s'] / v['segundos']))
                    por_bloque.append({'bloque': b['id'], 'segundo': b['s'], 'texto': b['texto'][:160],
                                       'mira': round(x['mira'], 3), 'relativa': round(x['relativa'], 3)})
            if not curva:
                return self.error('YouTube todavía no tiene la retención de este video (tarda uno o dos días, y hace falta que lo vea gente).')
            r = yt_ia(d, 'aprender', {'retencion_bloques': por_bloque, 'comentarios': com})
            r['curva'], r['bloques'], r['video'] = curva, por_bloque, v
            json.dump(r, open(os.path.join(d, 'youtube', 'aprender.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            return self.responder(r)
        return self.error('no encontrado', 404)

    def q(self):
        u = urllib.parse.urlparse(self.path)
        return u.path, {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

    def do_GET(self):
        if self.puerta():
            return
        ruta, q = self.q()
        LATIDO[0] = time.time()
        try:
            if ruta == '/celular':
                return self.responder(celular.pagina_pin(q.get('volver') or '/').encode(), 'text/html; charset=utf-8')
            if ruta == '/manifest.webmanifest':
                return self.responder(json.dumps(celular.MANIFIESTO).encode(), 'application/manifest+json')
            if ruta == '/icono.png':
                return self.responder(open(os.path.join(RAIZ, 'celular', 'icono.png'), 'rb').read(), 'image/png')
            if ruta == '/youtube':  # «▶️ YouTube»: publicar, aprender de las estadísticas e ideas, en su propia pestaña
                return self.responder(open(os.path.join(AQUI, 'youtube.html'), 'rb').read(), 'text/html; charset=utf-8')
            if ruta == '/api/youtube/canal':  # cómo va «📊 Aprender de todo mi canal» y el último resultado
                return self.responder({'corriendo': CANAL_YT['corriendo'], 'log': CANAL_YT['log'][-12:], 'error': CANAL_YT.get('error', ''),
                                       'analisis': canal_yt.ultimo(), 'informe': canal_yt.INFORME})
            if ruta == '/api/youtube/estado':
                c = yt_config()
                r = {'cliente': bool(c.get('cliente')), 'conectado': bool((c.get('token') or {}).get('refresh')),
                     'redirect': f'http://127.0.0.1:{PUERTO}/api/youtube/volver', 'ia': bool(leer_ajustes().get('modelo'))}
                if r['conectado'] and q.get('canal'):
                    try:
                        r['canal'] = youtube.canal(c)
                    except youtube.ErrorYT as e:
                        r['error'] = str(e)
                    if c.get('_cambio'):
                        yt_guardar(c)
                return self.responder(r)
            if ruta == '/api/youtube/conectar':  # solo desde el PC: Google vuelve a 127.0.0.1
                c = yt_config()
                if not c.get('cliente'):
                    return self.error('Primero sube el JSON del cliente OAuth (ver la guía).')
                url = youtube.url_permiso(c, f'http://127.0.0.1:{PUERTO}/api/youtube/volver')
                yt_guardar(c)
                self.send_response(302)
                self.send_header('Location', url)
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if ruta == '/api/youtube/volver':
                c = yt_config()
                try:
                    if q.get('error'):
                        raise youtube.ErrorYT('No diste el permiso en Google (' + q['error'] + ').')
                    youtube.canjear(c, q.get('code'), q.get('state'), f'http://127.0.0.1:{PUERTO}/api/youtube/volver')
                    yt_guardar(c)
                    msg = '✅ YouTube quedó conectado. Ya puedes cerrar esta pestaña y volver a la app.'
                except youtube.ErrorYT as e:
                    yt_guardar(c)
                    msg = '❌ ' + str(e)
                return self.responder(f'<!doctype html><meta charset="utf-8"><body style="background:#06070c;color:#fff;font:20px system-ui;'
                                      f'display:grid;place-items:center;height:90vh"><p>{msg}</p><script>try{{opener&&opener.postMessage("youtube","*")}}catch(e){{}}</script>'.encode(),
                                      'text/html; charset=utf-8')
            if ruta == '/api/youtube/proyecto':
                d = carpeta(q['p'])
                leer_yt = lambda f: json.load(open(os.path.join(d, 'youtube', f), encoding='utf-8')) if existe(d, os.path.join('youtube', f)) else None
                mini = sorted(glob.glob(os.path.join(d, 'miniatura*.jpg')) + glob.glob(os.path.join(d, 'miniatura*.png')), key=os.path.getmtime)
                return self.responder({'final': existe(d, 'FINAL.mp4'), 'metadatos': leer_yt('metadatos.json'), 'publicado': leer_yt('publicado.json'),
                                       'aprender': leer_yt('aprender.json'), 'subida': YT.get(q['p']),
                                       'miniatura': os.path.basename(mini[-1]) if mini else ''})
            if ruta == '/api/biblioteca':
                sys.path.insert(0, m('conocimiento'))
                import biblioteca
                try:
                    registro_b = open(biblioteca.LOG, encoding='utf-8', errors='replace').read()[-3000:]
                except OSError:
                    registro_b = ''
                aj = leer_ajustes()
                return self.responder({**biblioteca.resumen(), 'corriendo': bool(BIBLIO['proc'] and BIBLIO['proc'].poll() is None),
                                       'accion': BIBLIO['accion'], 'registro': registro_b, 'ajustes': aj.get('biblioteca') or {},
                                       'ia': bool(aj.get('modelo')), 'youtube': bool((yt_config().get('token') or {}).get('refresh')),
                                       'precio': flujo._precio(aj.get('modelo'), aj.get('precios_ia'))})
            if ruta == '/api/youtube/ideas':
                f = os.path.join(PROYECTOS, '.canal', 'youtube', 'ideas.json')
                return self.responder(json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {})
            if ruta == '/api/avisos':
                a = flujo.avisos(leer_ajustes())
                return self.responder({'activo': bool(a.get('activo')), 'tema': a.get('tema', ''), 'servidor': a.get('servidor') or 'https://ntfy.sh'})
            if ruta == '/api/cola':
                c = flujo.leer_cola(PROYECTOS)
                return self.responder({'andando': bool(c.get('andando')), 'items': c.get('items', [])})
            if ruta == '/api/gastos':  # «💲 Gastos del mes»: ElevenLabs (exacto, de su API) y las IAs (tokens × precio aproximado)
                return self.responder(flujo.gastos_mes(PROYECTOS, leer_ajustes(), clave_eleven()))
            if ruta == '/api/celular':  # solo desde el PC (puerta() lo bloquea desde el celular)
                c = celular.config(leer_ajustes())
                return self.responder({'activo': bool(c.get('activo')), 'pin_puesto': bool(c.get('pin_hash')),
                                       'escuchando': ESCUCHA[0] != '127.0.0.1', 'puerto': PUERTO,
                                       'con_windows': os.path.exists(arranque_windows()),
                                       'direcciones': celular.direcciones(PUERTO)})
            if ruta == '/':
                return self.responder(open(os.path.join(AQUI, 'index.html'), 'rb').read(), 'text/html; charset=utf-8')
            if ruta == '/pistas':  # el editor por pistas, en su propia pestaña
                return self.responder(open(os.path.join(AQUI, 'pistas.html'), 'rb').read(), 'text/html; charset=utf-8')
            if ruta == '/api/linea':
                return self.responder(linea_tiempo(carpeta(q['p'])))
            if ruta == '/api/edicion':
                return self.responder(edicion(carpeta(q['p'])))
            if ruta == '/guion':  # el editor de guion, en su propia pestaña
                return self.responder(open(os.path.join(AQUI, 'guion.html'), 'rb').read(), 'text/html; charset=utf-8')
            if ruta == '/vista':  # «👀 Vista previa»: una diapositiva por etiqueta y círculo, para aprobar antes de ponerlos
                return self.responder(open(os.path.join(AQUI, 'vista.html'), 'rb').read(), 'text/html; charset=utf-8')
            if ruta == '/trailer':  # el módulo del tráiler, aparte del video: proponer, contestar, editar y armar
                return self.responder(open(os.path.join(AQUI, 'trailer.html'), 'rb').read(), 'text/html; charset=utf-8')
            if ruta == '/miniatura':  # «🖼 Miniatura»: tus fotos HD y la app/IA pone fondo, textos y logo
                return self.responder(open(os.path.join(AQUI, 'miniatura.html'), 'rb').read(), 'text/html; charset=utf-8')
            if ruta == '/mejoras':  # «🎛 Audio e imagen», en su propia pestaña
                return self.responder(open(os.path.join(AQUI, 'mejoras.html'), 'rb').read(), 'text/html; charset=utf-8')
            if ruta.startswith('/api/mejoras/'):
                return mejoras.get(self, ruta, q, carpeta(q['p']))
            if ruta == '/api/cuadro':  # miniatura de la grabación en un segundo (en caché)
                d = carpeta(q['p'])
                t = round(max(0.0, float(q.get('t') or 0)), 1)
                c = os.path.join(d, 'ia_capturas', 'cuadros')
                f = os.path.join(c, f'{t:.1f}.jpg')
                if not os.path.exists(f) and existe(d, 'original.mp4'):
                    os.makedirs(c, exist_ok=True)
                    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(t), '-i', os.path.join(d, 'original.mp4'),
                                    '-frames:v', '1', '-vf', 'scale=400:-2', '-q:v', '4', f], capture_output=True, **SIN_VENTANA)
                return self.servir(f)
            if ruta == '/api/latido':
                return self.responder({'ok': True})
            if ruta == '/api/proyectos':
                # las carpetas que empiezan con «_» son pruebas de Claude o DeepSeek (_prueba_…): no se muestran en la lista
                return self.responder(sorted(x for x in os.listdir(PROYECTOS) if os.path.isdir(os.path.join(PROYECTOS, x)) and not x.startswith(('_', '.'))))
            if ruta == '/api/ultimo_proyecto':  # el último proyecto trabajado: el que tiene el archivo más reciente
                return self.responder(ultimo_proyecto())
            if ruta == '/api/estado':
                return self.responder(estado(q['p']))
            if ruta == '/api/guardados':
                return self.responder({'guardados': lista_guardados(carpeta(q['p']))})
            if ruta == '/api/version_guion':  # el editor la anota al abrir: si cambió al guardar, otra pestaña o la app guardó antes
                f = os.path.join(carpeta(q['p']), q.get('f') if q.get('f') in ('etiquetas.json', 'senales.json') else 'guion.json')
                v = hashlib.sha1(open(f, 'rb').read()).hexdigest() if os.path.exists(f) else ''
                return self.responder({'v': v})
            if ruta == '/api/importantes':  # «⭐ Cortes importantes» del proyecto y los bloques del guion que los tocan
                return self.responder(estado_importantes(carpeta(q['p'])))
            if ruta == '/api/miniaturas':  # la tira de miniaturas para la línea de tiempo (una imagen; queda en caché)
                d = carpeta(q['p'])
                f = os.path.join(d, os.path.basename(q.get('f') or 'original.mp4'))
                if not os.path.isfile(f):
                    return self.error('Ese video no está en el proyecto.', 404)
                n = max(20, min(120, int(q.get('n') or 120)))  # ≤ 120 de 128 px: el navegador no dibuja imágenes de más de ~16000 px
                tira = os.path.join(d, f'.miniaturas_{os.path.splitext(os.path.basename(f))[0]}_{n}.jpg')
                if not os.path.exists(tira) or os.path.getmtime(tira) < os.path.getmtime(f):
                    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                               capture_output=True, text=True, **SIN_VENTANA).stdout or 0) or 1
                    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-skip_frame', 'nokey', '-i', f, '-vf',
                                    f'fps={n}/{dur:.3f},scale=128:72,tile={n}x1', '-frames:v', '1', '-q:v', '5', tira],
                                   timeout=600, **SIN_VENTANA)
                if not os.path.exists(tira):
                    return self.error('No pude sacar las miniaturas.')
                return self.servir(tira)
            if ruta == '/api/para_chat':  # todo lo marcado, para pegarlo en el chat de Claude (y guardado en el proyecto)
                d = carpeta(q['p'])
                texto = para_chat(d)
                rel = lambda n: '/ver?ruta=' + urllib.parse.quote(os.path.relpath(os.path.join(d, n), RAIZ).replace('\\', '/'))
                return self.responder({'texto': texto, 'txt': rel('para_claude_marcas.txt'), 'json': rel('para_claude_marcas.json'),
                                       'carpeta': '/abrir?ruta=' + urllib.parse.quote(os.path.relpath(d, RAIZ).replace('\\', '/'))})
            if ruta == '/api/etiquetas_idiomas':  # «🌐 Etiquetas en otro idioma»
                return self.responder(estado_idiomas(carpeta(q['p']), q.get('lang', '')))
            if ruta == '/api/subs':  # «💬 Subtítulos»: idioma, estilo, textos y videos donde grabarlos
                return self.responder(estado_subs(carpeta(q['p'])))
            if ruta == '/api/subs_estado':
                e = dict(subtitulos.ESTADO)
                if e.get('salida') and os.path.exists(e['salida']):
                    e['ver'] = '/ver?ruta=' + urllib.parse.quote(os.path.relpath(e['salida'], RAIZ).replace('\\', '/'))
                return self.responder(e)
            if ruta == '/api/subs_vista':  # un cuadro del video con los subtítulos encima, para ver cómo quedan
                d = carpeta(q['p'])
                f = os.path.join(d, os.path.basename(q.get('f') or ''))
                if not os.path.isfile(f):
                    return self.error('Ese video no está en el proyecto.')
                try:
                    return self.servir(subtitulos.vista_previa(d, f, float(q.get('t') or 0), os.path.join(d, '.subs_vista.jpg')))
                except subprocess.CalledProcessError:
                    return self.error('No pude dibujar la vista previa.')
            if ruta == '/api/subs_srt':  # el .srt para subir a YouTube como subtítulo aparte
                d = carpeta(q['p'])
                lang = subtitulos.leer(d)['idioma']
                cuerpo = subtitulos.srt(d, lang).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-subrip; charset=utf-8')
                self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(d)}_{lang}.srt"')
                self.send_header('Content-Length', str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
                return
            if ruta == '/api/comprimir_estado':  # «🗜 Comprimir video»: cómo va
                e = {k: v for k, v in comprimir.ESTADO.items() if k != 'pid'}
                for k in ('entrada', 'salida'):
                    f = e.get(k)
                    if f and os.path.exists(f) and os.path.commonpath([os.path.realpath(f), os.path.realpath(RAIZ)]) == os.path.realpath(RAIZ):
                        e[k + '_ver'] = '/ver?ruta=' + urllib.parse.quote(os.path.relpath(f, RAIZ).replace('\\', '/'))
                return self.responder(e)
            if ruta == '/api/recursos':  # «📊 Uso del PC»: procesador, RAM y gráfica en vivo, y qué está haciendo la app
                r = recursos.leer()
                with CANDADO:
                    r['trabajo'] = {'proyecto': TRABAJO['proyecto'], 'paso': next((x['nombre'] for x in PASOS if x['id'] == TRABAJO['paso']), TRABAJO['paso'])}
                return self.responder(r)
            if ruta == '/api/conocimiento':  # «🧠 Conocimiento»: CONOCIMIENTO.md, lo aprendido y sus rutas completas
                return self.responder(conocimiento.resumen())
            if ruta == '/aprendi':  # «🧠 Lo que aprendí», en su propia pestaña
                return self.responder(open(os.path.join(AQUI, 'aprendi.html'), 'rb').read(), 'text/html; charset=utf-8')
            if ruta == '/api/aprendizaje':  # las reglas sacadas de tus correcciones, tu perfil y lo que le llega a la IA
                return self.responder(aprendizaje.resumen())
            if ruta == '/api/conocimiento/guiones_ia':  # «📚 Guiones de las IAs»: cada módulo con sus versiones, para leerlas
                ver = lambda f: '/ver?ruta=' + urllib.parse.quote(os.path.relpath(f, RAIZ).replace('\\', '/'))
                mods = conocimiento.lista_guiones_ia()
                for m in mods:
                    for g in m['guiones']:
                        g['ver'], g['ver_json'] = ver(g['md']), ver(g['json'])
                return self.responder({'modulos': mods, 'este': conocimiento.modulo_de_proyecto(carpeta(q['p'])) if q.get('p') else ''})
            if ruta == '/api/conocimiento/marca':  # una marca (MOTOROLA, APPLE…): su texto, su ruta y la lista de marcas
                return self.responder(self._marca(q.get('m') or '', q.get('p') or ''))
            if ruta == '/api/conocimiento/bajar':  # todo en un solo archivo, para subirlo al chat de otra IA
                m = re.sub(r'[^\w\-]', '', q.get('marca') or '').upper()  # «⬇ Bajar CONOCIMIENTO HONOR»: solo lo de esa marca (y lo general)
                cuerpo = (conocimiento.texto_marca_completo(m) if m else conocimiento.texto_completo()).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/markdown; charset=utf-8')
                self.send_header('Content-Disposition', f'attachment; filename="CONOCIMIENTO{"_" + m if m else ""}.md"')
                self.send_header('Content-Length', str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
                return
            if ruta == '/api/costo_voz':  # antes de gastar: qué bloques generarían voz y cuántos caracteres (no llama a ElevenLabs)
                return self.responder(costo_voz(carpeta(q['p']), q.get('desde'), q.get('hasta')))
            if ruta == '/api/frases':  # «🎞 Frase por frase»: cuándo dice la voz real cada frase de cada bloque
                return self.responder(frases_guion(carpeta(q['p'])))
            if ruta == '/api/revision_guion':  # lo que la app corrigió del guion y la revisión de orden
                d = carpeta(q['p'])
                leer = lambda n: open(os.path.join(d, n), encoding='utf-8').read() if existe(d, n) else ''
                try:  # «3 IAs a la vez»: las versiones que hay para elegir o combinar
                    versiones = [v for v in json.loads(leer('versiones_guion.json') or '[]') if not v.get('archivo') or existe(d, v['archivo'])]
                except ValueError:
                    versiones = []
                return self.responder({'mejoras': [x for x in leer('mejoras_guion.txt').splitlines() if x.strip()],
                                       'orden': leer('revision_guion.txt').strip(), 'versiones': versiones})
            if ruta == '/api/json':
                f = q['f']
                if f not in EDITABLES:
                    return self.error('archivo no editable')
                ruta_f = os.path.join(carpeta(q['p']), f)
                if q.get('ejemplo') == '1':
                    if f not in EJEMPLOS:
                        return self.responder(b'', 'text/plain; charset=utf-8')
                    ruta_f = m(EJEMPLOS[f])
                txt = open(ruta_f, encoding='utf-8').read() if os.path.exists(ruta_f) else ''
                if q.get('ejemplo') == '1':  # los ejemplos usan rutas del proyecto de la Pico; aquí, los nombres fijos
                    txt = re.sub(r'"material": "[^"]*"', '"material": "material.mp4"', txt)
                    txt = re.sub(r'"pista": "[^"]*"', '"pista": "musica.mp3"', txt)
                return self.responder(txt.encode(), 'text/plain; charset=utf-8')
            if ruta == '/api/musica_fija':  # para escucharla desde la app
                return self.servir(MUSICA_FIJA)
            if ruta in ('/carpeta', '/ver', '/abrir'):  # links de un clic a carpetas y archivos de la app (los que Claude te pasa)
                f = ruta_segura(q.get('ruta', ''))
                if not f:
                    return self.error('Esa ruta no está dentro de la carpeta de la app (o es privada).', 404)
                if ruta == '/ver':
                    return self.servir(f)
                if ruta == '/abrir':
                    # solo muestra carpetas: un archivo (.py, .bat, .exe…) nunca se ejecuta, se abre su carpeta con él marcado.
                    # Cualquier página web puede pedirle esta dirección a tu navegador, así que no debe poder correr nada.
                    if sys.platform == 'win32':
                        if os.path.isdir(f):
                            subprocess.Popen(['explorer', f])
                        else:
                            subprocess.Popen(['explorer', '/select,', f])
                    else:
                        subprocess.Popen(['xdg-open' if sys.platform != 'darwin' else 'open', f if os.path.isdir(f) else os.path.dirname(f)])
                    return self.responder(PAGINA_ABIERTO.encode('utf-8'), 'text/html; charset=utf-8')
                return self.responder(pagina_carpeta(f).encode('utf-8'), 'text/html; charset=utf-8')
            if ruta == '/archivo':
                sub = q.get('sub') if q.get('sub') in ['ia_capturas', 'diagnosticos', 'voz', 'vista_extras'] + [g[0] for g in GRUPOS.values()] else ''
                return self.servir(os.path.join(carpeta(q['p']), sub, os.path.basename(q['f'])), q.get('nombre', ''))
            if ruta == '/api/pistas':
                sub, nombre, apartados, _ = GRUPOS[q.get('g', 'pistas')]
                try:
                    datos = json.load(open(os.path.join(carpeta(q['p']), sub, nombre), encoding='utf-8'))
                except (OSError, ValueError):
                    datos = {}
                return self.responder({x: datos.get(x, []) for x in apartados})
            if ruta == '/api/estilos':
                return self.responder({'estilos': estilos(), 'activo': leer_ajustes().get('estilo', '')})
            if ruta == '/api/estilo_perfil':
                f = os.path.join(carpeta_estilo(q['e']), 'perfil.md')
                return self.responder(open(f, 'rb').read() if os.path.exists(f) else b'', 'text/plain; charset=utf-8')
            if ruta == '/api/capturas':
                c = os.path.join(carpeta(q['p']), 'ia_capturas')
                return self.responder(sorted(os.listdir(c)) if os.path.isdir(c) else [])
            if ruta == '/api/ajustes':
                aj = leer_ajustes()
                for k in ('clave', 'elevenlabs'):
                    if aj.get(k):
                        aj[k] = '••••' + aj[k][-4:]
                for x in (aj.get('ias_guion') or {}).values():  # «3 IAs a la vez»: sus claves tampoco salen de tu PC
                    if isinstance(x, dict) and x.get('clave'):
                        x['clave'] = '••••' + x['clave'][-4:]
                k = clave_eleven()
                aj['eleven'] = ('••••' + k[-4:]) if k else ''
                aj['ruta'] = AJUSTES
                aj.pop('celular', None)  # el PIN se ve y se cambia solo en «📱 Celular»
                aj.pop('youtube', None)  # el permiso de YouTube no sale de tu PC
                return self.responder({'ajustes': aj, 'proveedores': PROVEEDORES})
        except (KeyError, ValueError) as e:
            return self.error(str(e))
        self.error('no encontrado', 404)

    def servir(self, f, nombre=''):
        if not os.path.isfile(f):
            return self.error('no existe', 404)
        tam = os.path.getsize(f)
        tipo = mimetypes.guess_type(f)[0] or 'application/octet-stream'
        if f.lower().endswith(('.md', '.txt', '.srt')):
            tipo = 'text/plain; charset=utf-8'  # el navegador lo muestra (un .md lo bajaba) y con tildes bien
        elif tipo == 'application/json':
            tipo = 'application/json; charset=utf-8'
        rango = self.headers.get('Range')
        ini, fin = 0, tam - 1
        if rango:
            a, _, b = rango.replace('bytes=', '').partition('-')
            ini = int(a) if a else 0
            fin = int(b) if b else tam - 1
        largo = fin - ini + 1
        self.send_response(206 if rango else 200)
        self.send_header('Content-Type', tipo)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(largo))
        if rango:
            self.send_header('Content-Range', f'bytes {ini}-{fin}/{tam}')
        if nombre:  # «⬇ Original / 1080p…»: se baja con el nombre del proyecto y la fecha (no «archivo.mp4» ni «FINAL.mp4»)
            limpio = re.sub(r'[^\w\-. ]', '', nombre)[:120] or os.path.basename(f)
            self.send_header('Content-Disposition', f'attachment; filename="{limpio}"; filename*=UTF-8\'\'{urllib.parse.quote(limpio)}')
        self.end_headers()
        with open(f, 'rb') as fh:
            fh.seek(ini)
            while largo > 0:
                trozo = fh.read(min(1 << 20, largo))
                if not trozo:
                    break
                try:
                    self.wfile.write(trozo)
                except (BrokenPipeError, ConnectionResetError):
                    return
                largo -= len(trozo)

    def do_POST(self):
        if self.puerta():
            return
        ruta, q = self.q()
        if not self.mismo_origen():
            return self.error('pedido rechazado: solo la propia app puede cambiar cosas', 403)
        LATIDO[0] = time.time()
        largo = int(self.headers.get('Content-Length', 0))
        try:
            if ruta == '/api/celular/entrar':  # la pantalla del PIN en el celular
                datos = urllib.parse.parse_qs(self.rfile.read(min(largo, 4096)).decode(errors='replace'))
                volver = (datos.get('volver') or ['/'])[0]
                cookie, aviso = celular.entrar(leer_ajustes(), self.client_address[0], (datos.get('pin') or [''])[0])
                if not cookie:
                    return self.responder(celular.pagina_pin(volver, aviso).encode(), 'text/html; charset=utf-8', 401)
                self.send_response(303)
                self.send_header('Set-Cookie', cookie)
                self.send_header('Location', volver if volver.startswith('/') and not volver.startswith('//') else '/')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if ruta == '/api/biblioteca':  # juntar (gratis), aprender (IA) o guardar el canal y lo semanal
                op = json.loads(self.rfile.read(largo) or b'{}')
                aj = leer_ajustes()
                b = dict(aj.get('biblioteca') or {})
                for k in ('canal', 'semanal', 'ia', 'whisper'):
                    if k in op:
                        b[k] = op[k]
                aj['biblioteca'] = b
                tmp = AJUSTES + '.tmp'
                json.dump(aj, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                os.replace(tmp, AJUSTES)
                if op.get('accion') in ('juntar', 'aprender'):
                    if op['accion'] == 'aprender' and not aj.get('modelo'):
                        return self.error('Para que la IA lea tus videos hace falta una IA en «⚙ Ajustes IA».')
                    biblio_correr(op['accion'], b.get('canal', ''), bool(b.get('whisper')))
                return self.responder({'ok': True})
            if ruta.startswith('/api/youtube/'):
                try:
                    return self.youtube_post(ruta, q, largo)
                except youtube.ErrorYT as e:
                    return self.error(str(e))
            if ruta == '/api/avisos':  # aviso al celular con ntfy: activar, tema nuevo o mandar uno de prueba
                nuevo = json.loads(self.rfile.read(largo) or b'{}')
                aj = leer_ajustes()
                a = dict(flujo.avisos(aj))
                if nuevo.get('tema_nuevo') or not a.get('tema'):
                    a['tema'] = flujo.tema_nuevo()
                if 'activo' in nuevo:
                    a['activo'] = bool(nuevo['activo'])
                aj['avisos'] = a
                tmp = AJUSTES + '.tmp'
                json.dump(aj, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                os.replace(tmp, AJUSTES)
                if nuevo.get('probar') and not flujo.avisar(aj, '🎬 Estudio', 'Así te llegan los avisos de la app.', url_celular()):
                    return self.error('No pude mandar el aviso: revisa que esté activado y que el PC tenga internet.')
                return self.responder({'ok': True, 'tema': a['tema']})
            if ruta == '/api/cola':  # «🌙 Cola de noche»: agregar, quitar, empezar, parar, limpiar lo terminado
                nuevo = json.loads(self.rfile.read(largo) or b'{}')
                acc = nuevo.get('accion')

                def cambio(c):
                    if acc == 'agregar':
                        carpeta(nuevo['p'])  # que exista
                        if any(x['p'] == nuevo['p'] and x['estado'] in ('espera', 'corriendo') for x in c['items']):
                            raise ValueError(f"«{nuevo['p']}» ya está en la cola")
                        # el «SI» que escribiste al ponerlo en la cola: de noche arranca sin volver a preguntar
                        c['items'].append({'id': uuid.uuid4().hex[:8], 'p': nuevo['p'], 'estado': 'espera',
                                           'calidad': nuevo.get('calidad') or 'alta', 'agregado': time.time(),
                                           'confirmo': 'SI' if str(nuevo.get('confirmo') or '').strip().upper() in ('SI', 'SÍ') else ''})
                    elif acc == 'quitar':
                        c['items'] = [x for x in c['items'] if x['id'] != nuevo.get('id') or x['estado'] == 'corriendo']
                    elif acc == 'limpiar':
                        c['items'] = [x for x in c['items'] if x['estado'] in ('espera', 'corriendo')]
                    elif acc in ('empezar', 'parar'):
                        c['andando'] = acc == 'empezar'
                    else:
                        raise ValueError('acción desconocida')
                c = flujo.cambiar_cola(PROYECTOS, cambio)
                if acc == 'empezar':
                    threading.Thread(target=avanzar_cola, daemon=True).start()
                return self.responder({'ok': True, 'andando': bool(c.get('andando')), 'items': c['items']})
            if ruta == '/api/aprendizaje':  # «🧠 Lo que aprendí»: aprobar, rechazar, corregir, agregar una regla o aprender del historial
                datos = json.loads(self.rfile.read(largo) or b'{}')
                try:
                    if datos.get('accion') == 'historial':
                        n = aprendizaje.aprender_historial(PROYECTOS)
                        return self.responder(dict(aprendizaje.resumen(), nuevas=n))
                    aprendizaje.cambiar(datos.get('accion', ''), datos.get('id', ''), datos.get('texto', ''))
                except ValueError as e:
                    return self.error(str(e))
                return self.responder(aprendizaje.resumen())
            if ruta == '/api/celular':  # «📱 Celular» en la app del PC: activar, apagar o cambiar el PIN
                nuevo = json.loads(self.rfile.read(largo) or b'{}')
                aj = leer_ajustes()
                c = dict(celular.config(aj))
                if nuevo.get('pin'):
                    celular.nuevo_pin(c, str(nuevo['pin']))
                if 'activo' in nuevo:
                    if nuevo['activo'] and not c.get('pin_hash'):
                        return self.error('Primero elige un PIN de al menos 6 números.')
                    c['activo'] = bool(nuevo['activo'])
                if 'con_windows' in nuevo:
                    poner_arranque(bool(nuevo['con_windows']))
                aj['celular'] = c
                tmp = AJUSTES + '.tmp'
                json.dump(aj, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                os.replace(tmp, AJUSTES)
                return self.responder({'ok': True, 'reiniciar': c.get('activo', False) != (ESCUCHA[0] != '127.0.0.1')})
            if ruta == '/api/reiniciar':  # después de actualizar la app: abre la copia nueva y cierra esta
                with CANDADO:
                    if TRABAJO['proyecto']:
                        return self.error('Hay un paso trabajando. Espera a que termine o detenlo.')
                env = dict(os.environ, SIN_NAVEGADOR='1')
                subprocess.Popen([PY, os.path.abspath(__file__)], cwd=RAIZ, env=env,
                                 **({'creationflags': subprocess.CREATE_NEW_CONSOLE} if sys.platform == 'win32' else {}))
                return self.responder({'ok': True})
            if ruta.startswith('/api/mejoras/'):
                return mejoras.post(self, ruta, q, largo, carpeta(q['p']))
            if ruta == '/api/actualizar_app':
                with CANDADO:
                    if TRABAJO['proyecto']:
                        return self.error('Hay un paso trabajando. Espera a que termine o detenlo antes de actualizar.')
                try:
                    r = actualizar_app()
                except (RuntimeError, OSError, ValueError) as e:
                    return self.error(str(e))
                try:  # tus conocimientos viajan aparte, por tu repositorio privado (si no se puede, la app igual quedó al día)
                    r['mensaje'] += '\n' + conocimiento.sincronizar(leer_ajustes().get('repo_conocimiento'))
                except Exception as e:
                    r['mensaje'] += f'\nConocimientos: {e}'
                return self.responder(r)
            if ruta == '/api/salir':
                with CANDADO:
                    if TRABAJO['proyecto']:
                        return self.error('Hay un paso trabajando. Detenlo o espera a que termine antes de salir.')
                threading.Timer(0.3, lambda: os._exit(0)).start()
                return self.responder({'ok': True})
            if ruta == '/api/proyecto':
                d = carpeta(json.loads(self.rfile.read(largo))['nombre'])
                os.makedirs(d, exist_ok=True)
                return self.responder({'ok': True, 'nombre': os.path.basename(d)})
            if ruta == '/api/subir':
                destino = os.path.join(carpeta(q['p']), SUBIBLES[q['tipo']])
                de, parte = int(q.get('de', 1)), int(q.get('parte', 1))
                if de > 1:  # varios videos: cada uno llega aparte y con el último se unen en orden
                    destino = f'{destino}.parte{parte:02d}'
                with open(destino + '.parcial', 'wb') as fh:
                    resto = largo
                    while resto > 0:
                        trozo = self.rfile.read(min(1 << 20, resto))
                        if not trozo:
                            break
                        fh.write(trozo)
                        resto -= len(trozo)
                if resto > 0:  # la subida se cortó: no se reemplaza tu video por uno a medias
                    os.remove(destino + '.parcial')
                    return self.error('La subida se cortó antes de terminar. Vuelve a subir el archivo.')
                os.replace(destino + '.parcial', destino)
                if de > 1 and parte == de:
                    try:
                        return self.responder({'ok': True, 'unido': unir_videos(os.path.join(carpeta(q['p']), SUBIBLES[q['tipo']]), de)})
                    except (RuntimeError, OSError) as e:
                        return self.error(str(e))
                return self.responder({'ok': True})
            if ruta == '/api/json':
                f = q['f']
                if f not in EDITABLES:
                    return self.error('archivo no editable')
                txt = self.rfile.read(largo).decode('utf-8')
                if f.endswith('.json'):
                    try:
                        json.loads(txt)
                    except json.JSONDecodeError as e:
                        return self.error(f'JSON con error en la línea {e.lineno}, columna {e.colno}: {e.msg}. '
                                          'Si pegaste la respuesta de una IA, usa «Revisar respuesta pegada».')
                if f in aprendizaje.MIRA and existe(carpeta(q['p']), f):  # «🧠 Lo que aprendí»: lo que cambiaste a mano
                    try:
                        aprendizaje.registrar(carpeta(q['p']), f, open(os.path.join(carpeta(q['p']), f), encoding='utf-8').read(), txt)
                    except Exception as e:
                        print(f'· no pude aprender de tu edición ({type(e).__name__}: {e})', flush=True)
                if f == 'guion.json' and existe(carpeta(q['p']), f):  # cada versión del guion queda guardada para volver atrás
                    h = os.path.join(carpeta(q['p']), 'historial_guion')
                    os.makedirs(h, exist_ok=True)
                    shutil.copy(os.path.join(carpeta(q['p']), f), os.path.join(h, time.strftime('guion_%Y%m%d_%H%M%S.json')))
                    for viejo in sorted(os.listdir(h))[:-40]:
                        os.remove(os.path.join(h, viejo))
                open(os.path.join(carpeta(q['p']), f), 'w', encoding='utf-8').write(txt)
                return self.responder({'ok': True})
            if ruta == '/api/ejecutar':
                datos = json.loads(self.rfile.read(largo) or b'{}')
                if datos.get('motor') == 'auto':  # Scribe si hay clave de ElevenLabs (unos centavos, mucho más preciso); si no, Whisper
                    datos['motor'] = 'scribe' if clave_eleven() else 'whisper'
                pasos = [q['paso']]
                if q['paso'] == 'capas_juntas':  # la tarjeta «Etiquetas, flechas y tarjetas»: los que tengan con qué, juntos
                    d0 = carpeta(q['p'])
                    pasos = [x['id'] for x in PASOS if x['id'] in CAPAS and all(existe(d0, n) for n in x['necesita'])]
                    if not pasos:
                        return self.error('Todavía no hay etiquetas, flechas ni tarjetas que poner.')
                    for x in PASOS:  # los testimonios y nuevos modelos que ya tenía van encima de las capas nuevas (si no, el
                        # final salía del 8_ o 9_ viejo, con las etiquetas de antes); sus voces guardadas no se vuelven a pagar
                        if x['id'] in ('testimonios', 'nuevos_modelos') and existe(d0, x['produce']) and all(existe(d0, n) for n in x['necesita']):
                            pasos.append(x['id'])
                    if not existe(d0, 'trailer.mp4'):  # el FINAL.mp4 (lo que se descarga) también las lleva; con tráiler, «✨ Agregar extras»
                        pasos.append('final_sin_trailer')
                extras = q['paso'] == 'extras'
                if extras:  # «✨ Agregar extras» sobre el video ya hecho: se arma igual que «Hacer todo» y se dejan solo los elegidos
                    if not existe(carpeta(q['p']), '4_musica.mp4'):
                        return self.error('Primero haz el video con «▶ Hacer todo». Después le agregas los extras.')
                    elegidos = [x for x in (datos.get('solo') or EXTRAS) if x in EXTRAS]
                    if not elegidos:
                        return self.error('Elige al menos un extra.')
                    q['paso'] = 'todo'
                if q['paso'] == 'todo':
                    pasos = list(TODO) if existe(carpeta(q['p']), 'trailer.json') else TODO[:-1] + ['final_sin_trailer']  # copia: se le agregan pasos
                aj = leer_ajustes()
                if q['paso'] == 'todo' and not extras and aj.get('modelo') and aj.get('url') and trailer_pendiente(carpeta(q['p'])):
                    # el editor por pistas puede volver a poner el tráiler; «✨ Agregar extras» usa el que armaste en «🎬 Tráiler»
                    # (la IA no lo rehace por su cuenta encima de tus cambios)
                    pasos = TODO[:-1] + ['trailer_ia', 'trailer']
                if extras and 'trailer' in elegidos and not existe(carpeta(q['p']), 'trailer.json') and aj.get('modelo') and aj.get('url'):
                    pasos = [x for x in pasos if x != 'final_sin_trailer'] + ['trailer_ia', 'trailer']  # sin plan propio, lo arma la IA
                if q['paso'] == 'todo' and aj.get('modelo') and aj.get('url'):
                    # sin etiquetas ni flechas propias, la IA las prepara solas justo antes de ponerlas
                    for paso_ia, archivo, antes in (('etiquetas_ia', 'etiquetas.json', 'etiquetas'), ('senales_ia', 'senales.json', 'senales')):
                        # guion o montaje nuevo: etiquetas y flechas nuevas (las flechas guardan el lugar en el cuadro de antes)
                        viejo = etiquetas_viejas(carpeta(q['p'])) if paso_ia == 'etiquetas_ia' else senales_viejas(carpeta(q['p']))
                        if (not existe(carpeta(q['p']), archivo) or viejo) and antes in pasos:
                            pasos.insert(pasos.index(antes), paso_ia)
                if 'senales' in pasos and 'senales_ia' not in pasos and aj.get('modelo') and aj.get('url') and marcas_nuevas(carpeta(q['p'])):
                    pasos.insert(pasos.index('senales'), 'senales_ia')  # cambiaste tus capturas o notas: se vuelven a ubicar
                if q['paso'] == 'todo' and not extras and not datos.get('sin_ia') and guion_fuera_de_largo(carpeta(q['p'])) and aj.get('modelo') and aj.get('url'):
                    # guion revisado con un margen viejo y muy corto o muy largo: la IA lo alarga o acorta (los bloques
                    # que no cambian conservan su voz) y te lo muestro antes de seguir
                    pasos = ['guion_ia']
                    datos['ajustar_largo'] = True
                    datos['_pausa'] = 'guion'
                if q['paso'] == 'guion_ia' and datos.get('respuestas'):
                    datos['_pausa'] = 'guion'  # corregido con tus respuestas: te lo muestro otra vez antes de seguir
                if q['paso'] == 'ia' and datos.get('tarea') == 'guion' and datos.get('modo') in ('api', 'revisar'):
                    # «✨ Escribir / rehacer con IA» o el guion de una IA de chat (pegado o entregado por DeepSeek): se abre la
                    # revisión con las preguntas de la IA, para que lo veas y lo edites antes de la voz
                    datos['_pausa'] = 'guion'
                if q['paso'] == 'guion_ia' and datos.get('ajustar_humor'):
                    datos['_pausa'] = 'guion'  # «🎚 Ajustar el humor»: te muestro el guion con lo que cambió
                if q['paso'] == 'guion_ia' and datos.get('combinar'):
                    datos['_pausa'] = 'guion'  # «🧩 Combinar»: te muestro el guion combinado antes de seguir
                if q['paso'] == 'guion_ia' and datos.get('reintentar'):
                    datos['_pausa'] = 'guion'  # «🔁 Reintentar las que fallaron»: te muestro las versiones para elegir o combinar
                if q['paso'] == 'guion_ia' and datos.get('ideas'):
                    datos['_pausa'] = 'guion'  # «💡 Ideas y dudas»: se abre el editor con las preguntas para contestarlas
                if q['paso'] == 'guion_ia' and datos.get('otro'):
                    datos['_pausa'] = 'guion'  # «🔄 Otro guion»: te lo muestro apenas está, antes de seguir
                if datos.get('editor'):  # guardado desde el editor de guion: ya lo estás viendo allá, no se abre otra revisión
                    datos.pop('_pausa', None)
                if datos.get('sin_ia'):  # el editor por pistas: tus etiquetas y flechas tal cual, la IA no las rehace
                    pasos = [x for x in pasos if x not in PREPARA_EXTRA or x == 'trailer_ia' and not existe(carpeta(q['p']), 'trailer.json')]
                if extras:
                    pasos = [x for x in pasos if x in elegidos or PREPARA_EXTRA.get(x) in elegidos]
                    proponer = [x for x in pasos if x in ('etiquetas_ia', 'senales_ia')]
                    if proponer and not datos.get('revisado'):
                        # la IA propone etiquetas y flechas y se para: las revisas en el editor por pistas (sí, mover, quitar)
                        # antes de ponerlas. «▶ Ponerlas así» vuelve a llamar con revisado y ya no las rehace.
                        pasos = proponer
                        datos['_pausa'] = 'extras'
                        datos['_seguir'] = {'solo': elegidos, 'calidad': datos.get('calidad')}
                    else:
                        if datos.get('revisado'):  # ya las revisaste: la IA no las vuelve a proponer encima de tus cambios
                            pasos = [x for x in pasos if x not in proponer]
                        if 'trailer' not in pasos:
                            pasos.append('final_sin_trailer')
                        datos['_limpiar_extras'] = True
                elif q['paso'] == 'todo' and 'musica' in pasos:  # solo el video; los extras van después
                    luego = set(datos.get('luego_extras') or [])  # el editor por pistas: rehace el video y vuelve a poner sus extras
                    sigue = [x for x in pasos if x in luego or PREPARA_EXTRA.get(x) in luego]
                    pasos = [x for x in pasos if x not in EXTRAS and x not in PREPARA_EXTRA and x != 'final_sin_trailer'] + sigue
                    if 'trailer' not in sigue:
                        pasos.append('final_sin_trailer')
                if q['paso'] == 'todo' and not extras and pasos[0] == 'voz' and revision_imagen_pendiente(carpeta(q['p'])) \
                        and aj.get('revisar_imagen', True) is not False:  # la casilla de «⚙ Ajustes IA» (sí, salvo que la destildes)
                    pasos.insert(0, 'revisar_imagen')  # aprobaste el guion: ahora sí se revisa cada bloque contra su imagen
                if pasos[0] == 'voz' and not existe(carpeta(q['p']), 'guion.json'):
                    # sin guion, se escribe solo a partir del MP4 (antes se transcribe si hace falta)
                    if not existe(carpeta(q['p']), 'original.mp4'):
                        return self.error('Primero sube tu video grabado (original.mp4): de ahí sale el guion.')
                    aj = leer_ajustes()
                    if not (aj.get('modelo') and aj.get('url')):
                        return self.error('Para sacar el guion solo de tu video hace falta una IA. Elige una en «⚙ Ajustes IA» '
                                          '(Claude, GPT, Qwen u Ollama gratis en tu PC) y vuelve a pulsar.')
                    previos = ['guion_ia']
                    if not existe(carpeta(q['p']), 'transcripcion.srt'):
                        previos.insert(0, 'transcribir')
                        datos.setdefault('motor', 'scribe' if clave_eleven() else 'whisper')
                    pasos = previos  # se para con el guion listo, para que lo revises antes de seguir
                    datos['_pausa'] = 'guion'
                if q['paso'] == 'ia' and datos.get('modo') == 'paquete' and not existe(carpeta(q['p']), 'transcripcion.srt'):
                    pasos = ['transcribir', 'ia']  # el paquete lleva tu transcripción
                    datos.setdefault('motor', 'scribe' if clave_eleven() else 'whisper')
                if q['paso'] == 'prueba' and not TRABAJO['proyecto']:  # con otro trabajo en curso no se pisa su copia
                    if not existe(carpeta(q['p']), 'guion.json'):
                        return self.error('Todavía no hay guion: pulsa «▶ Hacer todo» sin marcar «Solo los bloques».')
                    try:
                        guion_de_prueba(carpeta(q['p']), datos.get('desde'), datos.get('hasta'))
                    except (ValueError, KeyError, IndexError) as e:
                        return self.error(str(e))
                if any(p not in {x['id'] for x in PASOS} for p in pasos):
                    return self.error(f"no conozco el paso «{q['paso']}»")
                falta_si = gasto_sin_confirmar(carpeta(q['p']), q['paso'], pasos, datos)
                if falta_si:
                    return self.error(falta_si)
                with CANDADO:
                    if TRABAJO['proyecto']:
                        return self.error(f"ya está corriendo «{TRABAJO['paso']}» en {TRABAJO['proyecto']}")
                    TRABAJO.update(proyecto=q['p'], paso=pasos[0], inicio=time.time())
                threading.Thread(target=correr, args=(q['p'], pasos, datos), daemon=True).start()
                return self.responder({'ok': True})
            if ruta == '/api/reescribir_bloque':  # «✨ Reescribir con IA» un bloque: devuelve el texto, no guarda nada
                datos = json.loads(self.rfile.read(largo) or b'{}')
                d = carpeta(q['p'])
                if not (leer_ajustes().get('modelo') and leer_ajustes().get('url')):
                    return self.error('Elige una IA en «⚙ Ajustes IA» para reescribir con IA.')
                env = dict(os.environ, PYTHONIOENCODING='utf-8', DIAG_DIR=os.path.join(d, 'diagnosticos'), DIAG_PASO='reescribir_bloque',
                           DIAG_RUN=time.strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:6])
                r = subprocess.run([PY, m('ia', 'ia.py'), '--proyecto', d, '--tarea', 'guion', '--modo', 'api', '--ajustes', AJUSTES,
                                    '--bloque', str(datos.get('bloque', '')), '--pedido', str(datos.get('pedido') or '')[:1000]],
                                   capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=900, **SIN_VENTANA)
                linea = next((x for x in reversed(r.stdout.splitlines()) if x.startswith('BLOQUE_NUEVO ')), None)
                if r.returncode != 0 or not linea:
                    return self.error(' '.join((r.stderr or r.stdout).split())[-500:] or 'la IA no respondió')
                return self.responder(json.loads(linea[len('BLOQUE_NUEVO '):]))
            if ruta == '/api/subtitulos':  # el texto de los subtítulos corregido en el editor (los tiempos no cambian)
                subs = json.loads(self.rfile.read(largo))
                d = carpeta(q['p'])
                if not isinstance(subs, list) or not all(isinstance(x, dict) and {'ini', 'fin', 'texto'} <= set(x) for x in subs):
                    return self.error('subtítulos con formato raro')
                if existe(d, '3_voz.srt'):
                    shutil.copy(os.path.join(d, '3_voz.srt'), os.path.join(d, '3_voz.srt.anterior'))
                escribir_srt(os.path.join(d, '3_voz.srt'), subs)
                return self.responder({'ok': True})
            if ruta == '/api/edicion':  # ajustes del editor por pistas para este proyecto (volumen de la música)
                nuevo = json.loads(self.rfile.read(largo))
                d = carpeta(q['p'])
                f = os.path.join(d, 'edicion.json')
                viejo = json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {}
                if 'musica_volumen' in nuevo:
                    viejo['musica_volumen'] = min(max(float(nuevo['musica_volumen']), 0), 1)
                if isinstance(nuevo.get('estabilizar'), bool):  # «Estabilizar» junto a «Montaje»
                    viejo['estabilizar'] = nuevo['estabilizar']
                if nuevo.get('trailer_donde') in ('inicio', 'final'):  # «Material extra»: el tráiler abre o cierra el video
                    viejo['trailer_donde'] = nuevo['trailer_donde']
                if 'trailer_segundos' in nuevo:  # «🎬 Tráiler»: cuánto querés que dure (la IA arma las tomas para eso)
                    viejo['trailer_segundos'] = min(max(int(nuevo['trailer_segundos'] or 10), 5), 40)
                json.dump(viejo, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                return self.responder({'ok': True})
            if ruta == '/api/musica_fija':  # la música de este proyecto pasa a usarse en todos los videos (o se quita)
                if q.get('quitar'):
                    if os.path.exists(MUSICA_FIJA):
                        os.remove(MUSICA_FIJA)
                    return self.responder({'ok': True})
                d = carpeta(q['p'])
                if not existe(d, 'musica.mp3'):
                    return self.error('Este proyecto todavía no tiene música (musica.mp3).')
                os.makedirs(os.path.dirname(MUSICA_FIJA), exist_ok=True)
                shutil.copy(os.path.join(d, 'musica.mp3'), MUSICA_FIJA + '.nueva')
                os.replace(MUSICA_FIJA + '.nueva', MUSICA_FIJA)
                aj = leer_ajustes()
                aj['musica_fija_de'] = f"la música del proyecto «{q['p']}»"
                with open(AJUSTES + '.tmp', 'w', encoding='utf-8') as fh:  # aparte y de una vez, como en «⚙ Ajustes»: un corte no borra tus claves
                    json.dump(aj, fh, ensure_ascii=False, indent=1)
                os.replace(AJUSTES + '.tmp', AJUSTES)
                return self.responder({'ok': True})
            if ruta == '/api/elegir_version':  # «3 IAs a la vez»: esa versión pasa a ser tu guion (el actual queda de respaldo)
                d = carpeta(q['p'])
                if not existe(d, 'versiones_guion.json'):
                    return self.error('este proyecto no tiene versiones del guion de varias IAs')
                versiones = json.load(open(os.path.join(d, 'versiones_guion.json'), encoding='utf-8'))
                v = next((x for x in versiones if x.get('id') == q.get('v') and x.get('archivo')), None)
                if not v or not existe(d, v['archivo']):
                    return self.error('esa versión del guion ya no está')
                nuevo = json.load(open(os.path.join(d, v['archivo']), encoding='utf-8'))
                if existe(d, 'guion.json'):
                    actual = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
                    if isinstance(actual, dict) and isinstance(nuevo, dict) and actual.get('revision_imagen_pendiente'):
                        nuevo['revision_imagen_pendiente'] = actual['revision_imagen_pendiente']
                    os.replace(os.path.join(d, 'guion.json'), os.path.join(d, 'guion.json.anterior'))
                json.dump(nuevo, open(os.path.join(d, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                # tus respuestas no se pierden al cambiar de versión: quedan guardadas en la versión de antes (vuelven si la
                # eliges otra vez), se aprenden, y las que contestaste y no se aplicaron pasan a la nueva
                try:
                    mias = [x for x in json.load(open(os.path.join(d, 'preguntas_guion.json'), encoding='utf-8'))
                            if isinstance(x, dict) and str(x.get('respuesta') or '').strip()]
                except (OSError, ValueError, TypeError):
                    mias = []
                antes = next((x for x in versiones if x.get('elegida') and x is not v), None)
                if antes is not None and mias:
                    resp = {re.sub(r'\W+', ' ', str(x.get('pregunta') or '')).strip().lower(): x for x in mias}
                    for x in antes.get('preguntas') or []:
                        m = resp.get(re.sub(r'\W+', ' ', str(x.get('pregunta') or '')).strip().lower())
                        if m:
                            x['respuesta'], x['hecha'] = m['respuesta'], m.get('hecha', False)
                if mias:
                    try:
                        conocimiento.aprender_de_proyecto(d)
                    except Exception:
                        pass
                nuevas = [dict(x) for x in (v.get('preguntas') or [])]
                ya = {re.sub(r'\W+', ' ', str(x.get('pregunta') or '')).strip().lower() for x in nuevas}
                nuevas += [dict(x, de_version=(antes or {}).get('nombre', '')) for x in mias if not x.get('hecha')
                           and re.sub(r'\W+', ' ', str(x.get('pregunta') or '')).strip().lower() not in ya]
                json.dump(nuevas, open(os.path.join(d, 'preguntas_guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                open(os.path.join(d, 'mejoras_guion.txt'), 'w', encoding='utf-8').write(''.join(x + '\n' for x in v.get('avisos') or []))
                for x in versiones:
                    x['elegida'] = x is v
                json.dump(versiones, open(os.path.join(d, 'versiones_guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                return self.responder({'ok': True})
            if ruta == '/api/trailer_version_texto':  # los textos de la diapositiva (título y subtítulo) y la frase de voz de una IA
                d = carpeta(q['p'])
                v = re.sub(r'[^a-z]', '', q.get('v') or '')
                f = os.path.join(d, f'trailer_{v}.json')
                if not v or not os.path.exists(f):
                    return self.error('esa propuesta del tráiler ya no está')
                nuevo = json.loads(self.rfile.read(largo) or b'{}')
                t = json.load(open(f, encoding='utf-8'))
                for k in ('titulo', 'subtitulo', 'voz'):
                    if k in nuevo:
                        t[k] = str(nuevo[k] or '').strip()[:300]
                json.dump(t, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                try:  # la lista de versiones muestra el título y la voz nuevos
                    fv = os.path.join(d, 'versiones_trailer.json')
                    versiones = json.load(open(fv, encoding='utf-8'))
                    for x in versiones:
                        if x.get('id') == v:
                            x['titulo'], x['voz'] = t.get('titulo', ''), t.get('voz', '')
                            if x.get('elegida'):  # es tu tráiler: trailer.json también cambia
                                tr = json.load(open(os.path.join(d, 'trailer.json'), encoding='utf-8'))
                                tr.update({k: t.get(k, '') for k in ('titulo', 'subtitulo', 'voz')})
                                json.dump(tr, open(os.path.join(d, 'trailer.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                    json.dump(versiones, open(fv, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                except (OSError, ValueError):
                    pass
                return self.responder({'ok': True})
            if ruta == '/api/elegir_version_trailer':  # «🎬 Tráiler con varias IAs»: esa propuesta pasa a ser tu tráiler
                d = carpeta(q['p'])
                try:
                    versiones = json.load(open(os.path.join(d, 'versiones_trailer.json'), encoding='utf-8'))
                except (OSError, ValueError):
                    return self.error('este proyecto no tiene tráileres de varias IAs')
                v = next((x for x in versiones if x.get('id') == q.get('v') and x.get('archivo')), None)
                if not v or not existe(d, v['archivo']):
                    return self.error('esa propuesta del tráiler ya no está')
                if existe(d, 'trailer.json'):
                    os.replace(os.path.join(d, 'trailer.json'), os.path.join(d, 'trailer.json.anterior'))
                shutil.copyfile(os.path.join(d, v['archivo']), os.path.join(d, 'trailer.json'))
                try:  # tus respuestas a las preguntas del tráiler se conservan; se suman las de esta propuesta
                    viejas = [x for x in json.load(open(os.path.join(d, 'preguntas_trailer.json'), encoding='utf-8'))
                              if isinstance(x, dict) and str(x.get('respuesta') or '').strip()]
                except (OSError, ValueError, TypeError):
                    viejas = []
                ya = {str(x.get('pregunta')).strip().lower() for x in viejas}
                json.dump(viejas + [x for x in v.get('preguntas') or [] if str(x.get('pregunta')).strip().lower() not in ya],
                          open(os.path.join(d, 'preguntas_trailer.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                for x in versiones:
                    x['elegida'] = x is v
                json.dump(versiones, open(os.path.join(d, 'versiones_trailer.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                return self.responder({'ok': True})
            if ruta == '/api/reintentar':  # «Reintentar» del diagnóstico: desde el paso que falló, solo si tiene sentido
                rep = (RESULTADO.get(q['p']) or {}).get('repetir')
                if not rep or not rep.get('pasos'):
                    return self.error('Este fallo no se reintenta solo: hay que corregir antes lo que dice el diagnóstico.')
                with CANDADO:
                    if TRABAJO['proyecto']:
                        return self.error(f"ya está corriendo «{TRABAJO['paso']}» en {TRABAJO['proyecto']}")
                    TRABAJO.update(proyecto=q['p'], paso=rep['pasos'][0], inicio=time.time())
                threading.Thread(target=correr, args=(q['p'], list(rep['pasos']), {**rep['opciones'], '_reanudar': True, '_limpiar_extras': False}), daemon=True).start()
                return self.responder({'ok': True})
            if ruta == '/api/ajustes':
                nuevo = json.loads(self.rfile.read(largo))
                nuevo.pop('celular', None)  # eso va por /api/celular, solo desde el PC
                nuevo.pop('youtube', None)
                viejo = leer_ajustes()
                for k in ('clave', 'elevenlabs'):  # una clave enmascarada o vacía no reemplaza la guardada
                    if k in nuevo and (not nuevo[k] or nuevo[k].startswith('••••')):
                        del nuevo[k]
                if isinstance(nuevo.get('ias_guion'), dict):
                    antes = viejo.get('ias_guion') or {}
                    for ide, x in nuevo['ias_guion'].items():
                        if isinstance(x, dict) and (not x.get('clave') or str(x['clave']).startswith('••••')):
                            x['clave'] = (antes.get(ide) or {}).get('clave', '')
                if 'url' in nuevo and 'clave' not in nuevo and (nuevo['url'] or '').rstrip('/') != (viejo.get('url') or '').rstrip('/'):
                    nuevo['clave'] = ''  # cambiaste de proveedor sin pegar clave: la del anterior no se le manda al nuevo
                viejo.update(nuevo)
                tmp = AJUSTES + '.tmp'  # se escribe aparte y se cambia de una vez: un corte no deja ajustes.json roto
                json.dump(viejo, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                os.replace(tmp, AJUSTES)
                return self.responder({'ok': True})
            if ruta == '/api/claves/prestar':
                if celular.es_local(self.client_address[0]):  # en este PC: abre el préstamo 5 minutos
                    PRESTAMO.update(hasta=time.time() + 300, fallos=0)
                    return self.responder({'ok': True, 'minutos': 5, 'direcciones': celular.direcciones(PUERTO)})
                datos = json.loads(self.rfile.read(min(largo, 4096)) or b'{}')  # la otra PC (ya pasó por puerta(): red de casa o Tailscale)
                if time.time() > PRESTAMO['hasta']:
                    return self.error('En la otra PC no está abierto «📤 Prestar mis claves» (dura 5 minutos): púlsalo allá y vuelve a probar.', 403)
                aj = leer_ajustes()
                cookie, aviso = celular.entrar(aj, self.client_address[0], str(datos.get('pin') or ''))
                if not cookie:
                    PRESTAMO['fallos'] += 1
                    if PRESTAMO['fallos'] >= 3:  # 3 PIN equivocados: se cierra y hay que volver a abrirlo en el PC
                        PRESTAMO['hasta'] = 0.0
                    return self.error(aviso, 401)
                PRESTAMO['hasta'] = 0.0  # un solo uso
                return self.responder({'claves': {k: aj[k] for k in CLAVES if k in aj}})
            if ruta == '/api/claves/traer':  # «📥 Traer claves de la otra PC»: por el Wi‑Fi de casa o Tailscale, nunca por GitHub
                if not celular.es_local(self.client_address[0]):
                    return self.error('esto se hace solo en la app del PC', 403)
                datos = json.loads(self.rfile.read(largo) or b'{}')
                dire = (datos.get('direccion') or '').strip().rstrip('/')
                if '://' not in dire:
                    dire = 'http://' + dire
                u = urllib.parse.urlparse(dire)
                if u.scheme != 'http' or not u.hostname or not celular.host_valido(u.hostname):
                    return self.error('Pon la dirección de la otra PC en tu red (por ejemplo http://192.168.1.20:8765) o su nombre de Tailscale.')
                dire = f'http://{u.hostname}:{u.port or PUERTO}'
                pedido = urllib.request.Request(dire + '/api/claves/prestar', data=json.dumps({'pin': str(datos.get('pin') or '')}).encode(),
                                                headers={'Content-Type': 'application/json'}, method='POST')
                try:
                    with urllib.request.urlopen(pedido, timeout=15) as r:
                        claves = json.load(r).get('claves') or {}
                except urllib.error.HTTPError as e:
                    try:
                        msg = json.load(e).get('error')
                    except ValueError:
                        msg = ''
                    if e.code == 403 and msg == 'acceso desde otro aparato apagado':
                        msg = 'En la otra PC activa «📱 Celular» con un PIN (y reinicia la app allá).'
                    return self.error(f'La otra PC dijo: {msg or e}')
                except (urllib.error.URLError, OSError) as e:
                    return self.error(f'No encontré la app en {dire} ({e}). En la otra PC activa «📱 Celular» con un PIN, '
                                      'reinicia la app allá y revisa que las dos estén en el mismo Wi‑Fi o en Tailscale.')
                if not claves:
                    return self.error('La otra PC no tiene claves guardadas.')
                if os.path.exists(AJUSTES):
                    shutil.copy2(AJUSTES, AJUSTES + '.copia')  # las de antes, por si acaso (tampoco se sirven nunca)
                aj = leer_ajustes()
                aj.update({k: claves[k] for k in CLAVES if k in claves})
                tmp = AJUSTES + '.tmp'
                json.dump(aj, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                os.replace(tmp, AJUSTES)
                traidas = (['IA principal'] if claves.get('clave') else []) + (['ElevenLabs'] if claves.get('elevenlabs') else []) + \
                    [i for i, x in (claves.get('ias_guion') or {}).items() if isinstance(x, dict) and x.get('clave')]
                return self.responder({'ok': True, 'traidas': traidas})
            if ruta == '/api/probar_ia':  # comprueba que la clave API del proveedor funcione, sin gastar tokens
                datos = json.loads(self.rfile.read(largo) or b'{}')
                if not datos.get('clave') or str(datos.get('clave')).startswith('••••'):
                    aj = leer_ajustes()
                    guardada = ((aj.get('ias_guion') or {}).get(datos.get('ia')) or {}).get('clave') if datos.get('ia') else ''
                    # la clave principal solo sirve para el mismo proveedor (la de OpenAI no abre Gemini): si cambiaste de
                    # proveedor y todavía no pegaste su clave, la guardada no se le manda al otro
                    mismo = (aj.get('url') or '').strip().rstrip('/') == (datos.get('url') or '').strip().rstrip('/')
                    datos['clave'] = guardada or (aj.get('clave', '') if mismo else '')  # si no mandan clave nueva, prueba la guardada
                return self.responder(probar_clave(datos))
            if ruta == '/api/probar_eleven':  # comprueba la clave de ElevenLabs (la escrita o la guardada) sin gastar créditos
                datos = json.loads(self.rfile.read(largo) or b'{}')
                return self.responder(probar_eleven(datos.get('clave') or clave_eleven()))
            if ruta == '/api/pista_archivo':
                sub, _, _, extensiones = GRUPOS[q.get('g', 'pistas')]
                ext = os.path.splitext(q.get('nombre', ''))[1].lower()
                if ext not in extensiones:
                    if extensiones == VIDEOS:
                        return self.error('Solo videos (mp4, mov, mkv, webm, avi)')
                    return self.error('Solo imágenes (jpg, png, webp)' + (' o audios (mp3, wav, m4a, ogg, webm)' if ext not in IMAGENES and len(extensiones) > len(IMAGENES) else ''))
                d = os.path.join(carpeta(q['p']), sub)
                os.makedirs(d, exist_ok=True)
                nombre = uuid.uuid4().hex[:10] + ext
                with open(os.path.join(d, nombre), 'wb') as fh:
                    resto = largo
                    while resto > 0:
                        trozo = self.rfile.read(min(1 << 20, resto))
                        if not trozo:
                            break
                        fh.write(trozo)
                        resto -= len(trozo)
                return self.responder({'archivo': nombre})
            if ruta == '/api/pistas':
                sub, nombre, apartados, _ = GRUPOS[q.get('g', 'pistas')]
                datos = json.loads(self.rfile.read(largo))
                limpio = {x: [p for p in datos.get(x, []) if isinstance(p, dict)] for x in apartados}
                d = os.path.join(carpeta(q['p']), sub)
                os.makedirs(d, exist_ok=True)
                hay = any(limpio.values())
                if hay:
                    json.dump(limpio, open(os.path.join(d, nombre), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                elif os.path.exists(os.path.join(d, nombre)):  # sin nada, el paso que lo usa queda «necesita»
                    os.remove(os.path.join(d, nombre))
                usados = {os.path.basename(p.get('archivo') or '') for x in apartados for p in limpio[x]}
                # la narración guardada de cada testimonio que sigue (testimonios.py): borrarla obliga a pagarla otra vez
                narr = {'narr_' + re.sub(r'\W+', '', os.path.splitext(u)[0]) for u in usados}
                for f in os.listdir(d):  # los archivos de pistas borradas (y su transcripción en caché)
                    base = f[:-4] if f.endswith('.txt') else f
                    if f != nombre and base not in usados and os.path.splitext(f)[0] not in narr:
                        os.remove(os.path.join(d, f))
                return self.responder({'ok': True})
            if ruta == '/api/estilo':
                e = carpeta_estilo(json.loads(self.rfile.read(largo))['nombre'])
                os.makedirs(e, exist_ok=True)
                return self.responder({'ok': True, 'nombre': os.path.basename(e)})
            if ruta == '/api/estilo_link':
                e = carpeta_estilo(q['e'])
                url = self.rfile.read(largo).decode('utf-8').strip()
                lista = fuentes_estilo(e)
                for u in re.findall(r'https?://\S+', url):
                    if 'youtu' not in u:
                        return self.error(f'{u} no es un link de YouTube. Los demás videos súbelos como MP4.')
                    canal = re.search(r'youtube\.com/(@[\w.\-]+|channel/|c/|user/)|[?&]list=', u) and \
                        not re.search(r'(?:v=|youtu\.be/|shorts/)[\w-]{11}', u)
                    if not any(f.get('url') == u for f in lista):
                        lista.append({'tipo': 'canal' if canal else 'youtube', 'url': u})
                guardar_fuentes(e, lista)
                return self.responder({'ok': True})
            if ruta == '/api/estilo_subir':
                e = carpeta_estilo(q['e'])
                nombre = os.path.basename(q['nombre'])
                ext = os.path.splitext(nombre)[1].lower()
                if ext not in ('.mp4', '.mov', '.mkv', '.webm', '.m4v', '.md', '.txt'):
                    return self.error('Sube videos (mp4, mov, mkv, webm) o un perfil escrito (.md, .txt)')
                nombre = re.sub(r'[^\w\-. ]', '_', nombre)
                os.makedirs(os.path.join(e, 'videos'), exist_ok=True)
                with open(os.path.join(e, 'videos', nombre), 'wb') as fh:
                    resto = largo
                    while resto > 0:
                        trozo = self.rfile.read(min(1 << 20, resto))
                        if not trozo:
                            break
                        fh.write(trozo)
                        resto -= len(trozo)
                lista = [f for f in fuentes_estilo(e) if f.get('archivo') != nombre]
                lista.append({'tipo': 'texto' if ext in ('.md', '.txt') else 'mp4', 'archivo': nombre, 'titulo': nombre})
                guardar_fuentes(e, lista)
                return self.responder({'ok': True})
            if ruta == '/api/estilo_quitar':
                e = carpeta_estilo(q['e'])
                lista = fuentes_estilo(e)
                f = lista.pop(int(q['i']))
                guardar_fuentes(e, lista)
                clave = f.get('archivo') or ''
                m_ = re.search(r'(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})', f.get('url', ''))
                base = m_.group(1) if m_ else os.path.splitext(clave)[0]
                for sub in ('videos', 'analisis'):
                    c = os.path.join(e, sub)
                    for x in os.listdir(c) if os.path.isdir(c) else []:
                        if x == clave or (base and x.startswith(base + '.')):
                            os.remove(os.path.join(c, x))
                return self.responder({'ok': True})
            if ruta == '/api/ortografia':  # el editor de guion: tildes y ortografía con LanguageTool (gratis, en español)
                texto = json.loads(self.rfile.read(largo) or b'{}').get('texto', '')[:19000]
                cuerpo = urllib.parse.urlencode({'text': texto, 'language': 'es', 'level': 'default'}).encode()
                try:
                    r = json.load(urllib.request.urlopen(urllib.request.Request(
                        'https://api.languagetool.org/v2/check', data=cuerpo, headers={'Accept': 'application/json'}), timeout=60))
                except urllib.error.HTTPError as e:
                    return self.error(f'el corrector (languagetool.org) respondió con error {e.code}'
                                      + (': demasiados pedidos seguidos, espera un minuto' if e.code == 429 else ''))
                except (urllib.error.URLError, OSError, ValueError) as e:
                    return self.error(f'no pude conectar con el corrector (languagetool.org): {e}')
                return self.responder({'cambios': [{'desde': m['offset'], 'largo': m['length'], 'mensaje': m.get('message', ''),
                                                    'opciones': [x['value'] for x in m.get('replacements', [])[:4]],
                                                    'tipo': (m.get('rule') or {}).get('issueType', '')}
                                                   for m in r.get('matches', [])]})
            if ruta == '/api/pegar':
                cuerpo, d = self.rfile.read(largo), carpeta(q['p'])
                if b'"bloques"' in cuerpo and existe(d, 'guion.json'):  # un guion nuevo: el actual queda en el historial (no solo en .anterior)
                    h = os.path.join(d, 'historial_guion')
                    os.makedirs(h, exist_ok=True)
                    shutil.copy(os.path.join(d, 'guion.json'), os.path.join(h, time.strftime('guion_%Y%m%d_%H%M%S.json')))
                    for viejo in sorted(os.listdir(h))[:-40]:
                        os.remove(os.path.join(h, viejo))
                open(os.path.join(d, 'ia_respuesta_pegada.txt'), 'wb').write(cuerpo)
                return self.responder({'ok': True})
            if ruta == '/api/short_extras':  # «📱 Short»: qué extras van al final (testimonio, páginas, ver el video completo)
                d = carpeta(q['p'])
                x = json.loads(self.rfile.read(largo) or b'{}')
                limpio = {k: bool(x.get(k)) for k in ('testimonio', 'paginas', 'final')}
                limpio.update({k: str(x.get(k) or '')[:300] for k in ('paginas_texto', 'final_texto')})
                for k in ('testimonio_archivo', 'final_audio'):  # solo archivos subidos a short_extras/
                    v = str(x.get(k) or '')
                    limpio[k] = v if re.fullmatch(r'short_extras/[\w\-. ]+', v) and existe(d, v) else ''
                limpio['final_dur'] = max(2.0, min(15.0, float(x.get('final_dur') or 4)))
                json.dump(limpio, open(os.path.join(d, 'short_extras.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                return self.responder({'ok': True, **limpio})
            if ruta == '/api/short_extra_subir':  # sube el video de testimonio o el audio del cierre del Short
                d = carpeta(q['p'])
                tipo = q.get('tipo')
                ext = os.path.splitext(q.get('nombre') or '')[1].lower()
                if tipo not in ('testimonio', 'audio') or ext not in ((VIDEOS if tipo == 'testimonio' else {'.mp3', '.wav', '.m4a', '.ogg', '.aac', '.opus', '.webm'})):
                    return self.error('Ese tipo de archivo no sirve aquí (video para el testimonio, audio para el cierre).')
                os.makedirs(os.path.join(d, 'short_extras'), exist_ok=True)
                rel = f'short_extras/{tipo}{ext}'
                with open(os.path.join(d, rel), 'wb') as fh:
                    falta = largo
                    while falta > 0:
                        parte = self.rfile.read(min(falta, 8 << 20))
                        if not parte:
                            break
                        fh.write(parte); falta -= len(parte)
                return self.responder({'ok': True, 'archivo': rel})
            if ruta == '/api/vista_extras':  # dibuja las diapositivas de la vista previa (todas, o solo q['solo'] = «senal:2»)
                d = carpeta(q['p'])
                solo = re.sub(r'[^a-z:0-9]', '', q.get('solo', ''))
                r = subprocess.run([PY, m('vista', 'vista.py'), '--proyecto', '.'] + (['--solo', solo] if solo else []), cwd=d,
                                   capture_output=True, text=True, encoding='utf-8', errors='replace', **SIN_VENTANA)
                if r.returncode:
                    return self.error((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else 'falló la vista previa')
                return self.responder({'ok': True})
            if ruta == '/api/importar_proyecto':  # «📂 Abrir proyecto (.zip)»: un proyecto de otra PC o de «Guardar como»
                import zipfile
                tmp = tempfile.mktemp(suffix='.zip')
                try:
                    with open(tmp, 'wb') as f:  # se baja a disco por partes: un proyecto con video pesa cientos de MB
                        falta = largo
                        while falta > 0:
                            parte = self.rfile.read(min(falta, 8 << 20))
                            if not parte:
                                break
                            f.write(parte)
                            falta -= len(parte)
                    try:
                        z = zipfile.ZipFile(tmp)
                    except zipfile.BadZipFile:
                        return self.error('Ese archivo no es un .zip.')
                    with z:
                        nombres = [n for n in z.namelist() if not n.endswith('/')]
                        raices = {n.split('/', 1)[0] for n in nombres}
                        dentro = len(raices) == 1 and all('/' in n for n in nombres)  # el zip trae la carpeta del proyecto
                        base = next(iter(raices)) if dentro else os.path.splitext(q.get('nombre') or 'proyecto')[0]
                        base = re.sub(r'^PC2_', '', re.sub(r'[^\w\- ]', '', base)).strip() or 'proyecto'
                        nombre, k = base, 2
                        while os.path.exists(os.path.join(PROYECTOS, nombre)):  # nunca pisa un proyecto que ya tienes
                            nombre, k = f'{base}_{k}', k + 1
                        destino = os.path.join(PROYECTOS, nombre)
                        for n in nombres:
                            rel = n.split('/', 1)[1] if dentro else n
                            f = os.path.realpath(os.path.join(destino, rel))
                            if os.path.commonpath([f, os.path.realpath(destino)]) != os.path.realpath(destino):
                                continue  # una ruta que se sale de la carpeta del proyecto no se copia
                            os.makedirs(os.path.dirname(f), exist_ok=True)
                            with z.open(n) as a, open(f, 'wb') as b:
                                shutil.copyfileobj(a, b, 8 << 20)
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                return self.responder({'ok': True, 'proyecto': nombre, 'video': existe(destino, 'original.mp4')})
            if ruta == '/api/importar_claude':  # «📥 Importar lo de Claude»: el .zip que arma Claude en la nube para revisar aquí
                import zipfile, io
                d = carpeta(q['p'])
                try:
                    z = zipfile.ZipFile(io.BytesIO(self.rfile.read(largo)))
                except zipfile.BadZipFile:
                    return self.error('Ese archivo no es un .zip.')
                nombres = {os.path.basename(n).lower(): n for n in z.namelist() if not n.endswith('/')}
                hecho = []
                for nombre in ('etiquetas.json', 'senales.json', 'trailer.json'):  # propuestas: las revisas en el editor por pistas
                    if nombre in nombres:
                        txt = z.read(nombres[nombre]).decode('utf-8-sig')
                        try:
                            json.loads(txt)
                        except ValueError:
                            return self.error(f'{nombre} del zip tiene un error de JSON.')
                        f = os.path.join(d, nombre)
                        if os.path.exists(f):
                            shutil.copyfile(f, f + '.anterior')
                        if nombre == 'trailer.json':  # sus dudas e ideas del tráiler van aparte, como las de la IA de la app
                            t = json.loads(txt)
                            if isinstance(t, dict) and isinstance(t.get('preguntas'), list):
                                json.dump(t.pop('preguntas'), open(os.path.join(d, 'preguntas_trailer.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                                txt = json.dumps(t, ensure_ascii=False, indent=1)
                            if isinstance(t, dict) and t.get('donde') in ('inicio', 'final'):
                                ed = edicion(d)
                                ed['trailer_donde'] = t['donde']
                                json.dump(ed, open(os.path.join(d, 'edicion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                        open(f, 'w', encoding='utf-8').write(txt)
                        hecho.append(nombre)
                if 'preguntas_trailer.json' in nombres:
                    txt = z.read(nombres['preguntas_trailer.json']).decode('utf-8-sig')
                    try:
                        json.loads(txt)
                    except ValueError:
                        return self.error('preguntas_trailer.json del zip tiene un error de JSON.')
                    open(os.path.join(d, 'preguntas_trailer.json'), 'w', encoding='utf-8').write(txt)
                    hecho.append('preguntas_trailer')
                if 'ideas_trailer.md' in nombres:  # cómo haría el tráiler: ideas, guion de la voz, por qué esas tomas
                    open(os.path.join(d, 'ideas_trailer.md'), 'wb').write(z.read(nombres['ideas_trailer.md']))
                    hecho.append('ideas_trailer')
                guion = nombres.get('respuesta_guion.json') or nombres.get('guion.json')
                if guion:  # el guion pasa por la misma revisión de la app que el de DeepSeek («Revisar respuesta pegada»)
                    open(os.path.join(d, 'ia_respuesta_pegada.txt'), 'wb').write(z.read(guion))
                    hecho.append('guion')
                for nombre in ('para_claude_ideas.md', 'ideas.md', 'notas.md'):
                    if nombre in nombres:
                        open(os.path.join(d, 'ideas_de_claude.md'), 'wb').write(z.read(nombres[nombre]))
                        hecho.append('ideas')
                        break
                if not hecho:
                    return self.error('El zip no trae respuesta_guion.json, etiquetas.json, senales.json ni trailer.json.')
                return self.responder({'ok': True, 'hecho': hecho})
            if ruta == '/api/etiquetas_idiomas':  # guarda el idioma elegido y las traducciones que escribiste
                datos = json.loads(self.rfile.read(largo) or b'{}')
                d = carpeta(q['p'])
                act = idiomas.leer(d)
                lang = re.sub(r'[^a-z\-]', '', str(datos.get('lang') or '').lower())[:8]
                if datos.get('idioma'):
                    act['idioma'] = re.sub(r'[^a-z\-]', '', str(datos['idioma']).lower())[:8] or idiomas.ORIGINAL
                if lang and isinstance(datos.get('traducciones'), dict):
                    tabla = act['traducciones'].setdefault(lang, {})
                    for k, v in datos['traducciones'].items():
                        if str(v or '').strip():
                            tabla[str(k)] = str(v).strip()[:300]
                        else:
                            tabla.pop(str(k), None)
                idiomas.guardar(d, act)
                return self.responder(estado_idiomas(d, lang))
            if ruta == '/api/subs':  # guarda idioma, estilo y los textos que corregiste
                datos = json.loads(self.rfile.read(largo) or b'{}')
                d = carpeta(q['p'])
                act = subtitulos.leer(d)
                if datos.get('idioma'):
                    act['idioma'] = re.sub(r'[^a-z\-]', '', str(datos['idioma']).lower())[:8] or 'en'
                if isinstance(datos.get('estilo'), dict):
                    act['estilo'] = {**act['estilo'], **{k: v for k, v in datos['estilo'].items() if k in subtitulos.ESTILO}}
                if isinstance(datos.get('textos'), dict) and act['idioma'] != 'es':
                    tabla = act['textos'].setdefault(act['idioma'], {})
                    for k, v in datos['textos'].items():
                        tabla[str(k)] = str(v or '').strip()[:600]
                subtitulos.guardar(d, act)
                return self.responder(estado_subs(d))
            if ruta == '/api/subs_traducir':  # la IA de Ajustes traduce los bloques que faltan (un pedido de texto)
                d = carpeta(q['p'])
                lang = subtitulos.leer(d)['idioma']
                if lang == 'es':
                    return self.error('En español se usa el guion tal cual: elige otro idioma para traducir.')
                r = subprocess.run([PY, m('subtitulos', 'subtitulos.py'), 'traducir', '--proyecto', d, '--idioma', lang, '--ajustes', AJUSTES],
                                   capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900,
                                   env=dict(os.environ, PYTHONUTF8='1'), **SIN_VENTANA)
                ultima = (r.stdout.strip().splitlines() or [''])[-1]
                if r.returncode != 0 or not ultima.startswith('{'):
                    return self.error('No pude traducir: ' + ' '.join((r.stderr or r.stdout).split())[-400:])
                return self.responder({**estado_subs(d), 'msg': f"Traduje {json.loads(ultima)['traducidos']} bloque(s)."})
            if ruta == '/api/subs_grabar':  # graba los subtítulos en una copia del video (en segundo plano)
                datos = json.loads(self.rfile.read(largo) or b'{}')
                d = carpeta(q['p'])
                f = os.path.join(d, os.path.basename(str(datos.get('fuente') or '')))
                if not os.path.isfile(f):
                    return self.error('Ese video no está en el proyecto.')
                try:
                    return self.responder({'ok': True, 'salida': subtitulos.grabar(d, f)})
                except ValueError as e:
                    return self.error(str(e))
            if ruta == '/api/elegir_video':  # la ventana de Windows para elegir cualquier video de la PC
                try:
                    return self.responder({'ruta': elegir_video_en_la_pc()})
                except ValueError as e:
                    return self.error(str(e))
            if ruta == '/api/elegir_destino':  # «Guardar como…» de Windows para el video comprimido
                datos = json.loads(self.rfile.read(largo) or b'{}')
                try:
                    return self.responder({'ruta': elegir_video_en_la_pc(guardar=str(datos.get('sugerido') or 'video_comprimido.mp4'))})
                except ValueError as e:
                    return self.error(str(e))
            if ruta == '/api/comprimir':  # empieza a comprimir (en segundo plano; el avance en /api/comprimir_estado)
                datos = json.loads(self.rfile.read(largo) or b'{}')
                f = str(datos.get('entrada') or '').strip().strip('"')
                if datos.get('p') and not os.path.isabs(f):  # un archivo del proyecto (FINAL.mp4…)
                    f = os.path.join(carpeta(datos['p']), os.path.basename(f))
                try:
                    salida = comprimir.iniciar(f, str(datos.get('perfil') or 'youtube'), int(datos.get('alto') or 0), bool(datos.get('rapido')),
                                               str(datos.get('salida') or '').strip().strip('"'))
                except ValueError as e:
                    return self.error(str(e))
                return self.responder({'ok': True, 'salida': salida})
            if ruta == '/api/comprimir_cancelar':
                comprimir.cancelar()
                return self.responder({'ok': True})
            if ruta == '/api/comprimir_mostrar':  # abre el Explorador con el video comprimido marcado
                f = comprimir.ESTADO.get('salida')
                if f and os.path.exists(f) and sys.platform == 'win32':
                    subprocess.Popen(['explorer', '/select,', f])
                return self.responder({'ok': True})
            if ruta == '/api/version_idioma':  # copia el proyecto con el guion traducido (no genera voz: no gasta ElevenLabs)
                d = carpeta(q['p'])
                lang = re.sub(r'[^a-z\-]', '', q.get('lang', '').lower())[:8]
                if not lang or lang == 'es':
                    return self.error('Elige a qué idioma hacer la versión.')
                if idioma_video(d) != 'es':
                    return self.error('Este proyecto ya es una versión traducida: hazla desde el proyecto original en español.')
                r = subprocess.run([PY, m('etiquetas', 'version_idioma.py'), '--proyecto', d, '--idioma', lang, '--ajustes', AJUSTES],
                                   capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900,
                                   env=dict(os.environ, PYTHONUTF8='1'), **SIN_VENTANA)
                ultima = (r.stdout.strip().splitlines() or [''])[-1]
                if r.returncode != 0 or not ultima.startswith('{'):
                    return self.error(' '.join((r.stderr or r.stdout).split())[-500:] or 'No pude hacer la versión.')
                res = json.loads(ultima)
                voz = (leer_ajustes().get('voces') or {}).get(lang) or VOCES_DEFECTO.get(lang, '')
                return self.responder({**res, 'voz': NOMBRE_VOZ.get(voz, voz)})
            if ruta == '/api/etiquetas_traducir':  # la IA de la app traduce lo que falta (un pedido corto, solo texto)
                d = carpeta(q['p'])
                lang = re.sub(r'[^a-z\-]', '', q.get('lang', '').lower())[:8]
                if not lang or lang == idiomas.ORIGINAL:
                    return self.error('Elige a qué idioma traducir.')
                r = subprocess.run([sys.executable, os.path.join(RAIZ, 'etiquetas', 'traducir.py'), '--proyecto', d, '--idioma', lang,
                                    '--ajustes', AJUSTES] + (['--todo'] if q.get('todo') else []),
                                   capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600,
                                   env=dict(os.environ, PYTHONUTF8='1'))
                ultima = (r.stdout.strip().splitlines() or [''])[-1]
                if r.returncode != 0 or not ultima.startswith('{'):
                    return self.error('No pude traducir: ' + ' '.join((r.stderr or r.stdout).split())[-400:])
                return self.responder({**estado_idiomas(d, lang), 'msg': json.loads(ultima).get('msg', '')})
            if ruta == '/api/importantes':  # guarda los cortes importantes y deja a ×1 los bloques del guion que los tocan
                datos = json.loads(self.rfile.read(largo) or b'{}')
                d = carpeta(q['p'])
                lista = []
                for x in datos.get('lista') or []:
                    try:
                        a, b = float(x['inicio']), float(x['fin'])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if b > a:
                        lista.append({'inicio': round(a, 2), 'fin': round(b, 2), 'nota': str(x.get('nota') or '')[:200]})
                importantes.guardar(d, sorted(lista, key=lambda x: x['inicio']))
                return self.responder(estado_importantes(d, aplicar=True))
            if ruta.startswith('/api/conocimiento/'):
                datos = json.loads(self.rfile.read(largo) or b'{}')
                que = ruta.rsplit('/', 1)[1]
                try:
                    if que == 'sincronizar':  # «🔄 Sincronizar»: el repositorio privado de conocimientos, entre tus PCs
                        return self.responder({**conocimiento.resumen(), 'msg': conocimiento.sincronizar(leer_ajustes().get('repo_conocimiento'))})
                    if que == 'guardar':
                        conocimiento.escribir(conocimiento.PRINCIPAL, str(datos.get('texto') or ''))
                    elif que == 'anotar':
                        _, entro = conocimiento.anotar(str(datos.get('tipo') or 'idea'), datos.get('texto'))
                        if not entro:
                            return self.responder({**conocimiento.resumen(), 'msg': 'Esa nota ya estaba.'})
                    elif que == 'marca_guardar':
                        conocimiento.guardar_marca(datos.get('marca'), datos.get('texto'))
                        return self.responder({**self._marca(datos.get('marca'), q.get('p') or ''), 'msg': 'Guardado.'})
                    elif que == 'marca_anotar':
                        entro = conocimiento.anotar_marca(datos.get('marca'), str(datos.get('tipo') or 'texto'), datos.get('texto'),
                                                          os.path.basename(str(datos.get('archivo') or '')))
                        return self.responder({**self._marca(datos.get('marca'), q.get('p') or ''), 'msg': 'Agregado.' if entro else 'Eso ya estaba.'})
                    elif que == 'marca_url':  # un link de YouTube, un blog o una web: su texto entra a la marca
                        try:
                            titulo, texto = conocimiento.leer_url(datos.get('url'))
                        except ValueError:
                            raise
                        except Exception as e:  # sin internet, la web no deja leerla, YouTube tardó demasiado…
                            raise ValueError(f'No pude leer ese link ({e}).')
                        entro = conocimiento.anotar_marca(datos.get('marca'), 'texto', texto, f"{titulo} · {datos.get('url')}")
                        return self.responder({**self._marca(datos.get('marca'), q.get('p') or ''),
                                               'msg': (f'Agregado: «{titulo}».' + (' Ojo: YouTube no dejó bajar sus subtítulos ahora, '
                                                       'entró solo el título y la descripción; prueba de nuevo en un rato.'
                                                       if 'YouTube no dejó' in texto else '')) if entro else 'Ese link ya estaba.'})
                    elif que == 'usar':
                        conocimiento.poner_usar(datos.get('usar'))
                    elif que == 'aprender':
                        if datos.get('todos'):
                            r = conocimiento.aprender_de_todos(PROYECTOS)
                            msg = f"Aprendí de {len(r)} proyecto(s): {sum(r.values())} dato(s)." if r else 'Ningún proyecto tiene preguntas contestadas todavía.'
                        else:
                            n = conocimiento.aprender_de_proyecto(carpeta(q['p']))
                            msg = f'Aprendí {n} dato(s) de este proyecto.' if n else 'Este proyecto todavía no tiene preguntas contestadas ni datos confirmados.'
                        return self.responder({**conocimiento.resumen(), 'msg': msg})
                    elif que == 'abrir':
                        conocimiento.asegurar()
                        if sys.platform == 'win32':
                            os.startfile(conocimiento.CARPETA)
                        else:
                            subprocess.Popen(['xdg-open' if sys.platform != 'darwin' else 'open', conocimiento.CARPETA])
                    else:
                        return self.error('pedido desconocido', 404)
                except ValueError as e:
                    return self.error(str(e))
                return self.responder(conocimiento.resumen())
            if ruta == '/api/abrir_carpeta':  # abre en tu PC la carpeta del proyecto (o una de adentro, como para_claude)
                c = os.path.join(carpeta(q['p']), os.path.basename(q.get('sub', '')))
                if not os.path.isdir(c):
                    return self.error('Esa carpeta todavía no existe.')
                if sys.platform == 'win32':
                    os.startfile(c)
                else:
                    subprocess.Popen(['xdg-open' if sys.platform != 'darwin' else 'open', c])
                return self.responder({'ok': True})
            if ruta == '/api/detener':
                with CANDADO:
                    if TRABAJO['proyecto']:  # entre dos pasos no hay proceso vivo, pero el siguiente ya no arranca
                        TRABAJO['detenido'] = True
                    if TRABAJO['proc'] and TRABAJO['proc'].poll() is None:  # uno ya terminado no: su número puede ser ya de otro programa
                        if sys.platform == 'win32':  # terminate() deja vivo el ffmpeg hijo: bloquea archivos y sigue gastando
                            subprocess.run(['taskkill', '/T', '/F', '/PID', str(TRABAJO['proc'].pid)], capture_output=True, **SIN_VENTANA)
                        else:
                            TRABAJO['proc'].terminate()
                return self.responder({'ok': True})
            if ruta == '/api/actualizar':  # «Actualizar»: quita videos y fallas viejas; voces, guion y transcripción quedan
                d = carpeta(q['p'])
                with CANDADO:
                    if TRABAJO['proyecto'] == q['p']:
                        return self.error('Hay un paso trabajando en este proyecto. Detenlo primero.')
                # los extras que tenía el video, para volver a ponerlos después de rehacerlo
                extras = [p['id'] for p in PASOS if p['id'] in EXTRAS and (existe(d, p['produce']) or p['id'] in capas_hechas(d))
                          and p['produce'] != 'FINAL.mp4']
                quitados = []
                for f in os.listdir(d):
                    if (f in VIDEOS_GENERADOS or f.endswith(('.parcial', '.etiquetas_tiempos.json'))) and borrar_seguro(os.path.join(d, f)):
                        quitados.append(f)
                if existe(d, 'registro.txt'):  # el registro viejo queda aparte, para no confundir con fallas pasadas
                    os.replace(os.path.join(d, 'registro.txt'), os.path.join(d, 'registro_anterior.txt'))
                FALLOS.pop(q['p'], None); RESULTADO.pop(q['p'], None)
                return self.responder({'ok': True, 'quitados': quitados, 'extras': extras})
            if ruta == '/api/empezar_de_nuevo':  # «Borrar todo»: quita lo generado y deja lo que subiste
                d = carpeta(q['p'])
                with CANDADO:
                    if TRABAJO['proyecto'] == q['p']:
                        return self.error('Hay un paso trabajando en este proyecto. Detenlo primero.')
                quedan = set(SUBIBLES.values()) | {'idea.txt', 'referencias.json', 'referencias', 'original.nitidez.npz', 'original.miniaturas.npz', GUARDADOS} | \
                    {sub for sub, *_ in GRUPOS.values()} | \
                    {'cortes_importantes.json', 'edicion.json', 'subtitulos.json', 'etiquetas_idiomas.json',  # lo que marcaste o elegiste tú
                     'idioma_video.json'}  # una versión en inglés sigue siendo en inglés (si no, la voz volvía a Mauricio)
                borrados = 0
                for f in os.listdir(d):
                    if f in quedan:
                        continue
                    r = os.path.join(d, f)
                    shutil.rmtree(r) if os.path.isdir(r) else os.remove(r)
                    borrados += 1
                FALLOS.pop(q['p'], None); RESULTADO.pop(q['p'], None)
                return self.responder({'ok': True, 'borrados': borrados})
            if ruta in ('/api/guardar_proyecto', '/api/volver_a_guardado', '/api/guardar_como', '/api/abrir_guardado'):
                d = carpeta(q['p'])
                datos = json.loads(self.rfile.read(largo) or b'{}')
                with CANDADO:
                    if TRABAJO['proyecto'] == q['p']:
                        return self.error('Hay un paso trabajando en este proyecto. Espera a que termine o detenlo primero.')
                if ruta == '/api/guardar_proyecto':
                    return self.responder({'ok': True, 'nombre': guardar_proyecto(d, str(datos.get('nota') or ''))})
                if ruta in ('/api/guardar_como', '/api/abrir_guardado'):
                    try:
                        r = guardar_como(d, str(datos.get('nota') or '')) if ruta == '/api/guardar_como' else abrir_guardado(d)
                    except (ValueError, OSError) as e:
                        return self.error(str(e))
                    return self.responder({'ok': True, 'cancelado': not r, 'ruta': r})
                try:
                    respaldo = volver_a_guardado(d, str(datos.get('nombre') or ''))
                except ValueError as e:
                    return self.error(str(e))
                FALLOS.pop(q['p'], None); RESULTADO.pop(q['p'], None)
                return self.responder({'ok': True, 'respaldo': respaldo})
            if ruta == '/api/borrar':
                if os.path.basename(q['f']) in ('', '.', '..'):  # «.» borraba el proyecto entero
                    return self.error('nombre de archivo no válido')
                f = os.path.join(carpeta(q['p']), os.path.basename(q['f']))
                if os.path.isdir(f):
                    shutil.rmtree(f)
                elif os.path.exists(f):
                    os.remove(f)
                return self.responder({'ok': True})
            if ruta == '/api/studio':
                subprocess.Popen([shutil.which('npx') or 'npx', 'remotion', 'studio', 'src/index.ts'], cwd=m('remotion'), **SIN_VENTANA)
                return self.responder({'ok': True, 'url': 'http://localhost:3000'})
        except (KeyError, ValueError) as e:
            return self.error(str(e))
        self.error('no encontrado', 404)


class Servidor(ThreadingHTTPServer):
    # en Windows, SO_REUSEADDR deja que dos copias de la app escuchen en el mismo puerto y la vieja sigue
    # contestando: aquí el puerto es exclusivo, y si está ocupado se le pide a la otra copia que se cierre
    allow_reuse_address = sys.platform != 'win32'

    def server_bind(self):
        import socket
        if sys.platform == 'win32':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


ESCUCHA = ['127.0.0.1']  # «📱 Celular» activado: '0.0.0.0', para que el celular llegue por el Wi‑Fi o Tailscale


def abrir_servidor():
    import urllib.request
    if celular.activo(leer_ajustes()):
        ESCUCHA[0] = '0.0.0.0'
    for intento in range(20):
        try:
            return Servidor((ESCUCHA[0], PUERTO), Manejador)
        except OSError:
            if intento == 0:
                print('Ya hay otra copia de la app abierta: le pido que se cierre…', flush=True)
                try:
                    urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{PUERTO}/api/salir', data=b'', method='POST'), timeout=3)
                except Exception as e:  # la otra copia está trabajando o no contesta
                    print(f'  (contestó: {e})', flush=True)
            time.sleep(0.5)
    raise SystemExit(f'El puerto {PUERTO} sigue ocupado por otra copia de la app. Ciérrala (su ventana negra, o '
                     'Estudio.exe desde el Administrador de tareas) y vuelve a abrir iniciar.bat.')


def retomar_cola():
    """La app se cerró con la cola andando (corte de luz, reinicio): lo que estaba a medias vuelve a la fila y sigue."""
    def volver(c):
        for x in c['items']:
            if x['estado'] == 'corriendo':
                x['estado'] = 'espera'
    if flujo.leer_cola(PROYECTOS).get('items'):
        c = flujo.cambiar_cola(PROYECTOS, volver)
        if c.get('andando'):
            threading.Timer(5, avanzar_cola).start()


def arranque_windows():
    """El archivo que Windows abre al prender el PC (carpeta «Inicio» del usuario)."""
    return os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup',
                        'Estudio de tutoriales.bat')


def poner_arranque(si):
    """«Abrir la app sola al prender el PC»: así el celular la encuentra después de un reinicio o un corte de luz."""
    f = arranque_windows()
    if not si:
        if os.path.exists(f):
            os.remove(f)
        return
    with open(f, 'w', encoding='mbcs' if sys.platform == 'win32' else 'utf-8', newline='') as a:
        a.write(f'@echo off\r\ncd /d "{RAIZ}"\r\nset SIN_NAVEGADOR=1\r\nstart "Estudio" /min "{PY}" app\\app.py\r\n')


def mantener_despierto():
    """Con «📲 Celular» activado el PC no se suspende mientras la app está abierta (la pantalla sí puede apagarse).
    No cambia la configuración de energía de Windows: vale solo mientras corre la app."""
    if sys.platform == 'win32' and celular.activo(leer_ajustes()):
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        print('📲 Celular activado: el PC no se va a suspender mientras la app esté abierta.', flush=True)


def main():
    srv = abrir_servidor()
    mantener_despierto()
    retomar_cola()
    threading.Thread(target=biblio_semanal, daemon=True).start()
    threading.Thread(target=canal_semanal, daemon=True).start()
    url = f'http://localhost:{PUERTO}'
    print(f'Estudio abierto en {url}  (cierra esta ventana para salir)')
    if not os.environ.get('SIN_NAVEGADOR'):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    if os.environ.get('AUTO_SALIR'):
        threading.Thread(target=vigilar, daemon=True).start()
    srv.serve_forever()


def vigilar():
    """Con Estudio.exe no hay ventana negra que cerrar: la app se apaga sola cuando cierras su ventana."""
    while True:
        time.sleep(15)
        with CANDADO:
            ocupado = bool(TRABAJO['proyecto'])
        if not ocupado and time.time() - LATIDO[0] > 180 and not celular.activo(leer_ajustes()):  # el celular la usa de lejos
            os._exit(0)


if __name__ == '__main__':
    main()
