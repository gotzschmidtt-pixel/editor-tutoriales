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

Uso: python app/app.py   (en Windows: doble clic en iniciar.bat)
"""
import json, mimetypes, os, re, shutil, subprocess, sys, threading, time, urllib.parse, uuid, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PROYECTOS = os.path.join(RAIZ, 'mis_proyectos')
ESTILOS = os.path.join(RAIZ, 'mis_estilos')  # panel Alimentación: un perfil de estilo por canal, para todos los proyectos
PUERTO = int(os.environ.get('PUERTO', 8765))
PY = sys.executable
# en Windows, sin esto cada paso abre su propia ventana negra cuando la app corre sin consola (Estudio.exe)
SIN_VENTANA = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
LATIDO = [time.time()]  # última vez que la página dio señales de vida
os.makedirs(PROYECTOS, exist_ok=True)
os.makedirs(ESTILOS, exist_ok=True)

SUBIBLES = {'original': 'original.mp4', 'imagen': 'imagen.png', 'material': 'material.mp4', 'musica': 'musica.mp3'}
EDITABLES = ['idea.txt', 'guion.json', 'etiquetas.json', 'senales.json', 'insertos.json', 'trailer.json']
AJUSTES = os.path.join(AQUI, 'ajustes.json')
IMAGENES = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
# grupos de archivos que se arman desde la app: carpeta, json, apartados y qué se puede subir
GRUPOS = {
    'pistas': ('pistas_trailer', 'pistas.json', ['ANTES', 'DURANTE', 'DESPUES'], IMAGENES | {'.mp3', '.wav', '.m4a', '.ogg', '.webm', '.opus', '.aac'}),
    'tarjetas': ('tarjetas', 'tarjetas.json', ['COMENTARIOS', 'WHATSAPP'], IMAGENES),
}
PROVEEDORES = {
    'Claude (Anthropic)': {'url': 'https://api.anthropic.com', 'modelo': 'claude-opus-5-5', 'imagenes': True, 'tipo': 'claude'},
    'OpenAI (GPT)': {'url': 'https://api.openai.com/v1', 'modelo': 'gpt-4o', 'imagenes': True},
    'OpenAI · GPT-5 con visión': {'url': 'https://api.openai.com/v1', 'modelo': 'gpt-5', 'imagenes': True},
    'OpenAI · GPT-4.1 con visión': {'url': 'https://api.openai.com/v1', 'modelo': 'gpt-4.1', 'imagenes': True},
    'Qwen-VL multimodal (Alibaba Cloud)': {'url': 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', 'modelo': 'qwen-vl-max',
                                           'imagenes': True, 'json': False},
    'Qwen-VL multimodal (OpenRouter)': {'url': 'https://openrouter.ai/api/v1', 'modelo': 'qwen/qwen2.5-vl-72b-instruct',
                                        'imagenes': True, 'json': False},
    'DeepSeek': {'url': 'https://api.deepseek.com', 'modelo': 'deepseek-chat', 'imagenes': False},
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


def ultimo_video(d, hasta):
    """El video más avanzado de la cadena antes del paso `hasta`."""
    cadena = ['1_montaje.mp4', '2_insertos.mp4', '3_voz.mp4', '4_musica.mp4', '5_etiquetas.mp4', '6_senales.mp4', '7_tarjetas.mp4']
    previos = cadena[:cadena.index(hasta)] if hasta in cadena else cadena
    for f in reversed(previos):
        if existe(d, f):
            return f
    return None


def comandos(paso, d, op):
    """Lista de comandos (cada uno una lista de argumentos) para un paso. cwd = carpeta del proyecto."""
    g = ['--guion', 'guion.json']
    if paso == 'transcribir':
        motor = op.get('motor', 'scribe')
        return [[PY, m('transcripcion', 'transcribir.py'), '--video', 'original.mp4', '--salida', 'transcripcion', '--motor', motor]]
    if paso == 'voz':
        return [[PY, m('voz', 'voz.py')] + g + ['--salida', 'voz']]
    if paso == 'montaje':
        c = [PY, m('montaje', 'montaje.py'), '--original', 'original.mp4'] + g + ['--salida', '1_montaje.mp4']
        if existe(d, 'imagen.png'):
            c += ['--imagen', 'imagen.png']
        if str(op.get('calidad', '1080')) in ('720', '480', '360'):
            c += ['--calidad', str(op['calidad'])]
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
        c += ['--pista', 'musica.mp3'] if existe(d, 'musica.mp3') else ['--guardar_pista', 'musica.mp3']
        if op.get('prompt'):
            c += ['--prompt', op['prompt']]
        return [c]
    if paso == 'etiquetas':
        return [[PY, m('etiquetas', 'etiquetas.py')] + g + ['--voz', 'voz', '--etiquetas', 'etiquetas.json', '--video', ultimo_video(d, '5_etiquetas.mp4'), '--salida', '5_etiquetas.mp4']]
    if paso == 'senales':
        return [[PY, m('senales', 'senales.py')] + g + ['--voz', 'voz', '--senales', 'senales.json', '--video', ultimo_video(d, '6_senales.mp4'), '--salida', '6_senales.mp4']]
    if paso == 'tarjetas':
        return [[PY, m('tarjetas', 'tarjetas.py'), '--video', ultimo_video(d, '7_tarjetas.mp4'), '--tarjetas', os.path.join('tarjetas', 'tarjetas.json'),
                 '--srt', '3_voz.srt', '--salida', '7_tarjetas.mp4']]
    if paso == 'trailer':
        return [[PY, m('trailer', 'trailer.py'), '--video', 'original.mp4', '--plan', 'trailer.json', '--salida', 'trailer.mp4',
                 '--unir', ultimo_video(d, None), '--final', 'FINAL.mp4', '--srt', '3_voz.srt']]
    if paso == 'ia':
        c = [PY, m('ia', 'ia.py'), '--proyecto', '.', '--tarea', op['tarea'], '--modo', op['modo'], '--ajustes', AJUSTES]
        if op['modo'] == 'revisar':
            c += ['--entrada', 'ia_respuesta_pegada.txt']
        return [c]
    if paso == 'alimentar':
        return [[PY, m('alimentacion', 'alimentacion.py'), '--estilo', carpeta_estilo(op.get('estilo')), '--ajustes', AJUSTES]]
    if paso == 'exportar':
        h = int(op.get('altura', 480))
        if h not in (720, 480, 360):
            raise ValueError('calidad no válida')
        return [['ffmpeg', '-nostdin', '-v', 'error', '-stats', '-y', '-i', 'FINAL.mp4', '-vf', f'scale=-2:{h}', '-c:v', 'libx264',
                 '-preset', 'veryfast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', f'FINAL_{h}p.mp4']]
    if paso == 'final_sin_trailer':
        return [['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', ultimo_video(d, None), '-c', 'copy', 'FINAL.mp4']]
    raise ValueError(paso)


# Qué necesita cada paso para poder correr, y qué produce
PASOS = [
    {'id': 'transcribir', 'nombre': 'Transcribir tu voz', 'necesita': ['original.mp4'], 'produce': 'transcripcion.txt', 'opcional': True},
    {'id': 'voz', 'nombre': 'Generar voz (ElevenLabs)', 'necesita': ['guion.json'], 'produce': 'voz'},
    {'id': 'montaje', 'nombre': 'Montar video', 'necesita': ['original.mp4', 'guion.json'], 'produce': '1_montaje.mp4'},
    {'id': 'insertos', 'nombre': 'Cortes y zooms con material extra', 'necesita': ['1_montaje.mp4', 'insertos.json', 'voz'], 'produce': '2_insertos.mp4', 'opcional': True},
    {'id': 'mezclar', 'nombre': 'Poner la voz y subtítulos', 'necesita': ['1_montaje.mp4', 'voz'], 'produce': '3_voz.mp4'},
    {'id': 'musica', 'nombre': 'Música de fondo', 'necesita': ['3_voz.mp4'], 'produce': '4_musica.mp4'},
    {'id': 'etiquetas', 'nombre': 'Etiquetas animadas', 'necesita': ['3_voz.mp4', 'etiquetas.json'], 'produce': '5_etiquetas.mp4', 'opcional': True},
    {'id': 'senales', 'nombre': 'Flechas y círculos', 'necesita': ['3_voz.mp4', 'senales.json'], 'produce': '6_senales.mp4', 'opcional': True},
    {'id': 'tarjetas', 'nombre': 'Tarjetas de comentarios y WhatsApp', 'necesita': ['3_voz.mp4', 'tarjetas/tarjetas.json'], 'produce': '7_tarjetas.mp4', 'opcional': True},
    {'id': 'trailer', 'nombre': 'Tráiler ANTES · DURANTE · DESPUÉS', 'necesita': ['3_voz.mp4', 'trailer.json'], 'produce': 'FINAL.mp4', 'opcional': True},
    {'id': 'final_sin_trailer', 'nombre': 'Video final sin tráiler', 'necesita': ['3_voz.mp4'], 'produce': 'FINAL.mp4', 'opcional': True},
    {'id': 'exportar', 'nombre': 'Exportar en otra calidad', 'necesita': ['FINAL.mp4'], 'produce': '', 'oculto': True},
    {'id': 'ia', 'nombre': 'Parte creativa con IA', 'necesita': ['original.mp4'], 'produce': '', 'oculto': True},
    {'id': 'alimentar', 'nombre': 'Aprender tu estilo (Alimentación)', 'necesita': [], 'produce': '', 'oculto': True},
]
TODO = ['voz', 'montaje', 'insertos', 'mezclar', 'musica', 'etiquetas', 'senales', 'tarjetas', 'trailer']

FALLOS = {}  # proyecto -> {'paso', 'msg'} del último paso que falló
TRABAJO = {'proyecto': None, 'paso': None, 'proc': None, 'inicio': None, 'cola': []}
CANDADO = threading.Lock()


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


USAN_ELEVEN = {'voz', 'musica', 'trailer'}


def carpeta(p):
    p = re.sub(r'[^\w\- ]', '', p or '').strip()
    if not p:
        raise ValueError('nombre de proyecto vacío')
    return os.path.join(PROYECTOS, p)


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
            for f in fu:
                clave = re.search(r'(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})', f.get('url', ''))
                f['analizado'] = f['tipo'] == 'texto' or (clave.group(1) if clave else os.path.splitext(f.get('archivo', ''))[0]) in hechos
            out.append({'nombre': n, 'fuentes': fu, 'perfil': os.path.exists(os.path.join(e, 'perfil.md'))})
    return out


def registro(d):
    return os.path.join(d, 'registro.txt')


def correr(proyecto, pasos, opciones):
    try:
        d = carpeta(proyecto)
        log = open(registro(d), 'a', encoding='utf-8')
    except Exception as e:
        FALLOS[proyecto] = {'paso': pasos[0], 'msg': f'No pude abrir el registro del proyecto: {e}'}
        with CANDADO:
            TRABAJO.update(proyecto=None, paso=None, proc=None, inicio=None)
        return
    env = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
    if clave_eleven():
        env['ELEVENLABS_API_KEY'] = clave_eleven()
    paso = pasos[0]
    try:
        FALLOS.pop(proyecto, None)
        if not shutil.which('ffmpeg'):
            raise RuntimeError('ffmpeg no está instalado o Windows no lo encuentra. Corre instalar.bat, '
                               'reinicia la PC y vuelve a abrir iniciar.bat.')
        for paso in pasos:
            info = next(x for x in PASOS if x['id'] == paso)
            falta = [n for n in info['necesita'] if not existe(d, n)]
            if falta:
                if paso in TODO and info.get('opcional'):
                    log.write(f'\n— {info["nombre"]}: lo salto (falta {", ".join(falta)})\n'); log.flush()
                    continue
                log.write(f'\n✗ {info["nombre"]}: falta {", ".join(falta)}\n'); log.flush()
                FALLOS[proyecto] = {'paso': paso, 'msg': 'falta ' + ', '.join(falta)}
                return
            eleven = paso in USAN_ELEVEN or (paso == 'transcribir' and opciones.get('motor', 'scribe') == 'scribe')
            if eleven and sys.platform == 'win32' and not env.get('ELEVENLABS_API_KEY'):
                raise RuntimeError('Falta tu clave de ElevenLabs. Pulsa el botón «🔑 Clave ElevenLabs» arriba a la derecha, '
                                   'pégala y guarda. (Para transcribir sin clave usa Whisper: «Cancelar» al preguntar.)')
            with CANDADO:
                TRABAJO.update(paso=paso, inicio=time.time())
            FALLOS.pop(proyecto, None)
            log.write(f'\n▶ {info["nombre"]}  ({time.strftime("%H:%M:%S")})\n'); log.flush()
            for c in comandos(paso, d, opciones):
                proc = subprocess.Popen(c, cwd=d, stdout=log, stderr=subprocess.STDOUT, env=env, **SIN_VENTANA)
                with CANDADO:
                    TRABAJO['proc'] = proc
                if proc.wait() != 0:
                    log.write(f'✗ {info["nombre"]} falló (código {proc.returncode}). Revisa el mensaje de arriba.\n'); log.flush()
                    FALLOS[proyecto] = {'paso': paso, 'msg': causa(d)}
                    return
            log.write(f'✓ {info["nombre"]} listo en {int(time.time() - TRABAJO["inicio"])} s\n'); log.flush()
    except Exception as e:
        # sin esto el paso moría en silencio y la app volvía a «Listo para hacer» sin decir nada
        import traceback
        msg = str(e) if isinstance(e, RuntimeError) else f'{type(e).__name__}: {e}'
        if isinstance(e, FileNotFoundError):
            msg = f'Windows no encontró un programa que hace falta ({e}). Corre instalar.bat y reinicia la PC.'
        log.write(f'\nERROR: {msg}\n{traceback.format_exc()}\n✗ falló\n'); log.flush()
        FALLOS[proyecto] = {'paso': paso, 'msg': msg}
    finally:
        log.close()
        with CANDADO:
            TRABAJO.update(proyecto=None, paso=None, proc=None, inicio=None)


def causa(d):
    """La línea que explica el error, dentro de lo último que escribió el paso."""
    lineas = open(registro(d), encoding='utf-8', errors='replace').read().split('\n▶')[-1].strip().splitlines()
    for k, l in enumerate(lineas):
        if l.startswith('ERROR:'):
            resto = [x.strip() for x in lineas[k + 1:] if x.strip() and not x.startswith('✗')]
            return ' '.join([l[6:].strip()] + resto)
    utiles = [l.strip() for l in lineas[1:] if l.strip() and not l.startswith('✗')]
    return utiles[-1] if utiles else 'sin detalle'


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
    log = open(registro(d), encoding='utf-8', errors='replace').read()[-12000:] if existe(d, 'registro.txt') else ''
    with CANDADO:
        t = dict(proyecto=TRABAJO['proyecto'], paso=TRABAJO['paso'],
                 segundos=int(time.time() - TRABAJO['inicio']) if TRABAJO['inicio'] else 0)
    return {'archivos': archivos, 'pasos': pasos, 'registro': log, 'trabajo': t, 'fallo': FALLOS.get(proyecto)}


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

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

    def q(self):
        u = urllib.parse.urlparse(self.path)
        return u.path, {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

    def do_GET(self):
        ruta, q = self.q()
        LATIDO[0] = time.time()
        try:
            if ruta == '/':
                return self.responder(open(os.path.join(AQUI, 'index.html'), 'rb').read(), 'text/html; charset=utf-8')
            if ruta == '/api/latido':
                return self.responder({'ok': True})
            if ruta == '/api/proyectos':
                return self.responder(sorted(x for x in os.listdir(PROYECTOS) if os.path.isdir(os.path.join(PROYECTOS, x))))
            if ruta == '/api/estado':
                return self.responder(estado(q['p']))
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
            if ruta == '/archivo':
                sub = q.get('sub') if q.get('sub') in ['ia_capturas'] + [g[0] for g in GRUPOS.values()] else ''
                return self.servir(os.path.join(carpeta(q['p']), sub, os.path.basename(q['f'])))
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
                k = clave_eleven()
                aj['eleven'] = ('••••' + k[-4:]) if k else ''
                aj['ruta'] = AJUSTES
                return self.responder({'ajustes': aj, 'proveedores': PROVEEDORES})
        except (KeyError, ValueError) as e:
            return self.error(str(e))
        self.error('no encontrado', 404)

    def servir(self, f):
        if not os.path.isfile(f):
            return self.error('no existe', 404)
        tam = os.path.getsize(f)
        tipo = mimetypes.guess_type(f)[0] or 'application/octet-stream'
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
        ruta, q = self.q()
        LATIDO[0] = time.time()
        largo = int(self.headers.get('Content-Length', 0))
        try:
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
                with open(destino + '.parcial', 'wb') as fh:
                    resto = largo
                    while resto > 0:
                        trozo = self.rfile.read(min(1 << 20, resto))
                        if not trozo:
                            break
                        fh.write(trozo)
                        resto -= len(trozo)
                os.replace(destino + '.parcial', destino)
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
                open(os.path.join(carpeta(q['p']), f), 'w', encoding='utf-8').write(txt)
                return self.responder({'ok': True})
            if ruta == '/api/ejecutar':
                datos = json.loads(self.rfile.read(largo) or b'{}')
                pasos = [q['paso']]
                if q['paso'] == 'todo':
                    pasos = TODO if existe(carpeta(q['p']), 'trailer.json') else TODO[:-1] + ['final_sin_trailer']
                with CANDADO:
                    if TRABAJO['proyecto']:
                        return self.error(f"ya está corriendo «{TRABAJO['paso']}» en {TRABAJO['proyecto']}")
                    TRABAJO.update(proyecto=q['p'], paso=pasos[0], inicio=time.time())
                threading.Thread(target=correr, args=(q['p'], pasos, datos), daemon=True).start()
                return self.responder({'ok': True})
            if ruta == '/api/ajustes':
                nuevo = json.loads(self.rfile.read(largo))
                viejo = leer_ajustes()
                for k in ('clave', 'elevenlabs'):  # una clave enmascarada o vacía no reemplaza la guardada
                    if k in nuevo and (not nuevo[k] or nuevo[k].startswith('••••')):
                        del nuevo[k]
                viejo.update(nuevo)
                json.dump(viejo, open(AJUSTES, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                return self.responder({'ok': True})
            if ruta == '/api/pista_archivo':
                sub, _, _, extensiones = GRUPOS[q.get('g', 'pistas')]
                ext = os.path.splitext(q.get('nombre', ''))[1].lower()
                if ext not in extensiones:
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
                for f in os.listdir(d):  # los archivos de pistas borradas (y su transcripción en caché)
                    base = f[:-4] if f.endswith('.txt') else f
                    if f != nombre and base not in usados:
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
                    if not any(f.get('url') == u for f in lista):
                        lista.append({'tipo': 'youtube', 'url': u})
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
            if ruta == '/api/pegar':
                open(os.path.join(carpeta(q['p']), 'ia_respuesta_pegada.txt'), 'wb').write(self.rfile.read(largo))
                return self.responder({'ok': True})
            if ruta == '/api/detener':
                with CANDADO:
                    if TRABAJO['proc']:
                        TRABAJO['proc'].terminate()
                return self.responder({'ok': True})
            if ruta == '/api/borrar':
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


def main():
    srv = ThreadingHTTPServer(('127.0.0.1', PUERTO), Manejador)
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
        if not ocupado and time.time() - LATIDO[0] > 180:
            os._exit(0)


if __name__ == '__main__':
    main()
