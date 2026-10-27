"""Lo que la app va aprendiendo de todos tus videos: procesos, guiones, preguntas, dudas e ideas.

Vive en mis_conocimientos/ (al lado de mis_proyectos, y «Actualizar la app» no la toca):
- CONOCIMIENTO.md: tu archivo. Lo lees y lo editas tú, y lo lee cualquier IA (Claude, DeepSeek, ChatGPT…).
  Las notas rápidas de la app («➕ Anotar») entran en su sección.
- aprendido_de_proyectos.md: lo llena la app sola, una sección por proyecto, con las preguntas de la IA que
  contestaste y los datos que confirmaste. Si vuelves a aprender de un proyecto, su sección se reemplaza (no se duplica).
- config.json: {"usar": true|false}, si la app se lo pasa a la IA cuando escribe.

La app se lo pasa a la IA al escribir el guion, el tráiler y las etiquetas, y en «💡 Ideas y dudas» (para que no
pregunte lo que ya sabes). No guarda claves, ni el guion completo, ni fotogramas ni audio: solo texto que tú
contestaste o anotaste.
"""
import json, os, re, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, 'mis_conocimientos')
PRINCIPAL = os.path.join(CARPETA, 'CONOCIMIENTO.md')
APRENDIDO = os.path.join(CARPETA, 'aprendido_de_proyectos.md')
CONFIG = os.path.join(CARPETA, 'config.json')

SECCIONES = {'proceso': 'Procesos', 'guion': 'Guiones', 'pregunta': 'Preguntas', 'duda': 'Dudas', 'idea': 'Ideas'}

PLANTILLA = """# Conocimiento del canal

> Para cualquier IA (Claude, DeepSeek, ChatGPT…) que escriba guiones, etiquetas o tráileres para este canal:
> lee esto antes de empezar. Son datos y decisiones que el autor ya confirmó en videos anteriores; úsalos y no
> los vuelvas a preguntar. Si algo de aquí no coincide con lo que se ve o se dice en el video nuevo, manda el video
> nuevo y pregúntale al autor. No inventes datos que no estén aquí ni en el video.

## Procesos
<!-- Cómo se hace cada cosa: DFU, Recovery, ECID, Boot Ramdisk, FRP… con sus pasos y avisos. -->

## Guiones
<!-- Reglas del guion que ya aprendimos: qué gusta, qué no, cómo abrir y cerrar. -->

## Preguntas
<!-- Preguntas que la IA suele hacer, con su respuesta. -->

## Dudas
<!-- Cosas que todavía no están claras. -->

## Ideas
<!-- Ideas para próximos videos o para mejorar la app. -->
"""


def asegurar():
    os.makedirs(CARPETA, exist_ok=True)
    if not os.path.exists(PRINCIPAL):
        open(PRINCIPAL, 'w', encoding='utf-8').write(PLANTILLA)


def leer(f):
    try:
        return open(f, encoding='utf-8').read()
    except OSError:
        return ''


def escribir(f, texto):
    asegurar()
    tmp = f + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(texto)
    os.replace(tmp, f)


def usar():
    try:
        return bool(json.load(open(CONFIG, encoding='utf-8')).get('usar', True))
    except (OSError, ValueError, AttributeError):
        return True


def poner_usar(si):
    asegurar()
    json.dump({'usar': bool(si)}, open(CONFIG, 'w', encoding='utf-8'))


def _normal(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip().lower()


def anotar(tipo, texto, texto_md=None, fecha=None):
    """Una nota rápida en su sección de CONOCIMIENTO.md («- texto (fecha)»). No repite una nota que ya está."""
    texto = re.sub(r'\s+', ' ', str(texto or '')).strip()
    if not texto:
        raise ValueError('La nota está vacía.')
    asegurar()
    md = leer(PRINCIPAL) if texto_md is None else texto_md
    if _normal(texto) in _normal(md):
        return md, False
    titulo = SECCIONES.get(tipo, 'Ideas')
    linea = f'- {texto} ({fecha or time.strftime("%Y-%m-%d")})'
    lineas = md.rstrip('\n').split('\n')
    i = next((k for k, x in enumerate(lineas) if x.strip().lower() == f'## {titulo.lower()}'), None)
    if i is None:
        lineas += ['', f'## {titulo}', linea]
    else:
        fin = next((k for k in range(i + 1, len(lineas)) if lineas[k].startswith('## ')), len(lineas))
        while fin > i + 1 and not lineas[fin - 1].strip():
            fin -= 1
        lineas.insert(fin, linea)
    md = '\n'.join(lineas) + '\n'
    if texto_md is None:
        escribir(PRINCIPAL, md)
    return md, True


def _secciones_aprendido(md):
    """{nombre del proyecto: texto de su sección} en el orden del archivo."""
    out, actual = {}, None
    for x in md.split('\n'):
        if x.startswith('## '):
            actual = x[3:].split(' · ')[0].strip()
            out[actual] = [x]
        elif actual:
            out[actual].append(x)
    return {k: '\n'.join(v).rstrip() for k, v in out.items()}


def _cabecera_aprendido():
    return ('# Aprendido de los proyectos\n\n'
            '> Lo llena la app sola: en cada proyecto, las preguntas de la IA que el autor contestó y los datos que confirmó.\n'
            '> Son datos confirmados por el autor para ESE video; en otro video pueden cambiar (otro modelo, otra versión).\n')


def _json(f):
    try:
        x = json.load(open(f, encoding='utf-8'))
        return x if isinstance(x, list) else []
    except (OSError, ValueError):
        return []


def aprender_de_proyecto(d):
    """Junta lo que contestaste y confirmaste en un proyecto y lo deja en aprendido_de_proyectos.md. Devuelve cuántos datos."""
    nombre = os.path.basename(os.path.abspath(d))
    lineas = []
    for archivo, que in (('preguntas_guion.json', 'Guion'), ('preguntas_trailer.json', 'Tráiler')):
        for x in _json(os.path.join(d, archivo)):
            if not isinstance(x, dict):
                continue
            resp = re.sub(r'\s+', ' ', str(x.get('respuesta') or '')).strip()
            preg = re.sub(r'\s+', ' ', str(x.get('pregunta') or '')).strip()
            if resp and preg:
                tipo = 'idea' if x.get('tipo') == 'mejora' else 'dato'
                lineas.append(f'- {que}, {tipo}: {preg} → {resp}')
    idea = leer(os.path.join(d, 'idea.txt'))
    if 'Datos confirmados por el autor:' in idea:  # lo que corregir_con_respuestas dejó como confirmado
        for x in idea.split('Datos confirmados por el autor:', 1)[1].split('\n'):
            x = x.strip()
            if x.startswith('- ') and not any(_normal(x[2:]) in _normal(y) for y in lineas):
                lineas.append(f'- Confirmado: {x[2:]}')
    if not lineas:
        return 0
    asegurar()
    secs = _secciones_aprendido(leer(APRENDIDO))
    secs.pop(nombre, None)
    nueva = f'## {nombre} · {time.strftime("%Y-%m-%d")}\n' + '\n'.join(lineas)
    escribir(APRENDIDO, _cabecera_aprendido() + '\n' + '\n\n'.join([nueva] + list(secs.values())) + '\n')  # el más nuevo arriba
    return len(lineas)


def aprender_de_todos(carpeta_proyectos):
    total = {}
    for n in sorted(os.listdir(carpeta_proyectos)) if os.path.isdir(carpeta_proyectos) else []:
        d = os.path.join(carpeta_proyectos, n)
        if os.path.isdir(d):
            k = aprender_de_proyecto(d)
            if k:
                total[n] = k
    return total


def _sin_comentarios(md):
    return re.sub(r'\n{3,}', '\n\n', re.sub(r'<!--.*?-->', '', md, flags=re.S)).strip()


def texto_completo():
    """CONOCIMIENTO.md y lo aprendido de los proyectos, en un solo texto (lo que se baja para otra IA)."""
    asegurar()
    partes = [_sin_comentarios(leer(PRINCIPAL))]
    ap = _sin_comentarios(leer(APRENDIDO))
    if ap:
        partes.append(ap)
    return '\n\n'.join(p for p in partes if p) + '\n'


def texto_para_ia(limite=12000):
    """Lo que va dentro del pedido a la IA. Vacío si lo apagaste o si todavía no hay nada aprendido."""
    if not usar() or not os.path.exists(PRINCIPAL):
        return ''
    t = texto_completo()
    if _normal(_sin_comentarios(PLANTILLA)) == _normal(t):
        return ''  # solo la plantilla, sin nada tuyo todavía
    return t if len(t) <= limite else t[:limite].rsplit('\n', 1)[0] + '\n[… sigue en mis_conocimientos/CONOCIMIENTO.md]'


def resumen():
    asegurar()
    md, ap = leer(PRINCIPAL), leer(APRENDIDO)
    notas, actual = {}, None
    for x in md.split('\n'):
        if x.startswith('## '):
            actual = x[3:].strip()
            notas.setdefault(actual, 0)
        elif actual and x.strip().startswith('- '):
            notas[actual] += 1
    return {'carpeta': CARPETA, 'principal': PRINCIPAL, 'aprendido_ruta': APRENDIDO, 'texto': md, 'aprendido': ap,
            'notas': notas, 'proyectos': len(_secciones_aprendido(ap)), 'usar': usar()}


def juntar(otra_carpeta):
    """Trae lo de otra PC (la carpeta mis_conocimientos que venía en un .zip de «Guardar como») sin borrar lo tuyo:
    cada nota que no tengas entra en su sección, y cada proyecto que no tengas en lo aprendido. Devuelve cuántas cosas entraron."""
    asegurar()
    nuevas = 0
    otro = leer(os.path.join(otra_carpeta, 'CONOCIMIENTO.md'))
    if otro:
        md, seccion = leer(PRINCIPAL), 'Ideas'
        tipo_de = {v.lower(): k for k, v in SECCIONES.items()}
        for x in otro.split('\n'):
            if x.startswith('## '):
                seccion = x[3:].strip()
                if seccion.lower() not in tipo_de and f'## {seccion}'.lower() not in md.lower():
                    md = md.rstrip('\n') + f'\n\n## {seccion}\n'
                    SECCIONES.setdefault(seccion.lower(), seccion)
                    tipo_de[seccion.lower()] = seccion.lower()
            elif x.strip().startswith('- '):
                f = re.search(r' \((\d{4}-\d{2}-\d{2})\)$', x.strip())
                nota = x.strip()[2:f.start() if f else None].strip()
                if _normal(nota) not in _normal(md):
                    md, entro = anotar(tipo_de.get(seccion.lower(), 'idea'), nota, md, f.group(1) if f else None)
                    nuevas += entro
        escribir(PRINCIPAL, md)
    otras = _secciones_aprendido(leer(os.path.join(otra_carpeta, 'aprendido_de_proyectos.md')))
    if otras:
        mias = _secciones_aprendido(leer(APRENDIDO))
        faltan = {k: v for k, v in otras.items() if k not in mias}
        if faltan:
            escribir(APRENDIDO, _cabecera_aprendido() + '\n' + '\n\n'.join(list(mias.values()) + list(faltan.values())) + '\n')
            nuevas += len(faltan)
    return nuevas
