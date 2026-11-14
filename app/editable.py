"""«📦 Guardar proyecto editable» (pedido de fabian, 14/11/2026): TODO el proyecto en un solo .zip que la app vuelve a abrir
y se sigue editando en el editor por pistas, en esta PC o en otra.

A diferencia de «💾 Guardar proyecto» (que deja fuera los videos), aquí SÍ va todo lo que hace falta para seguir editando:
el video grabado, el material extra, las voces con su alineación, el guion, etiquetas, círculos y flechas, subtítulos,
música, testimonios, tarjetas, tomas, tráiler… Lo que la app rehace sola sin gastar (los videos intermedios 1_montaje,
3_voz… y los FINAL) no va, salvo que pidas incluir el FINAL. Los videos van sin comprimir otra vez (ZIP «guardado», no
«comprimido»): es más rápido y un .mp4 no se achica.

Al abrirlo («📂 Abrir proyecto editable») queda como un proyecto más, con otro nombre si ya tienes uno igual: nunca pisa
nada. También abre una CARPETA de proyecto (por ejemplo una que te pasa Claude o que bajaste del Drive).
"""
import json, os, re, shutil, threading, time, zipfile

MANIFIESTO = 'PROYECTO_EDITABLE.json'
VERSION = 1
LEEME = 'LEEME_PROYECTO_EDITABLE.txt'
# carpetas de trabajo que se rehacen solas o son de la nube: no hacen falta para seguir editando
NO_VAN_CARPETAS = {'guardados', '.montaje_partes', 'hojas_2s', 'ia_capturas', 'para_claude', '_papelera', '__pycache__'}
SIN_COMPRIMIR = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v', '.mp3', '.m4a', '.aac', '.ogg', '.opus',
                 '.jpg', '.jpeg', '.png', '.webp', '.zip', '.gif', '.psd'}

ESTADO = {'activo': False, 'tarea': '', 'proyecto': '', 'hecho': 0, 'total': 0, 'archivo': '', 'error': '', 'resultado': None}
_CANDADO = threading.Lock()


def _no_va(nombre, generados, con_final):
    """True si ese archivo de la raíz del proyecto no entra en el paquete."""
    if nombre in (MANIFIESTO, LEEME):
        return True  # se escribe de nuevo
    if nombre.startswith('FINAL_antes_rehacer_'):
        return True  # respaldos de finales viejos
    if con_final and nombre in ('FINAL.mp4', 'FINAL_EN.mp4', 'FINAL_PT.mp4'):
        return False
    if nombre in generados or re.fullmatch(r'FINAL.*\.(mp4|srt)', nombre):
        return True
    return nombre.lower().endswith(('.tmp', '.part'))


def lista(d, generados=(), con_final=False):
    """[(ruta en disco, ruta dentro del zip)] de todo lo que va en el paquete editable de la carpeta d."""
    base = os.path.basename(os.path.normpath(d))
    generados = set(generados)
    out = []
    for raiz, carpetas, archivos in os.walk(d):
        rel = os.path.relpath(raiz, d)
        carpetas[:] = sorted(c for c in carpetas if c not in NO_VAN_CARPETAS)
        for a in sorted(archivos):
            if rel == '.' and _no_va(a, generados, con_final):
                continue
            if a.lower().endswith(('.tmp', '.part')):
                continue
            dentro = a if rel == '.' else os.path.join(rel, a).replace(os.sep, '/')
            out.append((os.path.join(raiz, a), f'{base}/{dentro}'))
    return out


def resumen(d, generados=(), con_final=False):
    """Lo que irá en el paquete, para mostrarlo antes de guardar."""
    xs = lista(d, generados, con_final)
    mb = sum(os.path.getsize(f) for f, _ in xs) / 1e6
    nombres = {os.path.basename(z) for _, z in xs}
    falta = [] if 'original.mp4' in nombres else ['original.mp4 (el video grabado)']
    if 'guion.json' not in nombres:
        falta.append('guion.json (todavía no hay guion)')
    return {'archivos': len(xs), 'mb': round(mb, 1), 'falta': falta}


def _manifiesto(d, xs, extras):
    leer = lambda f: json.load(open(os.path.join(d, f), encoding='utf-8')) if os.path.exists(os.path.join(d, f)) else None
    try:
        guion = leer('guion.json') or {}
        bloques = len(guion.get('bloques', [])) if isinstance(guion, dict) else 0
    except (OSError, ValueError):
        bloques = 0
    voz = os.path.join(d, 'voz')
    voces = len([x for x in os.listdir(voz) if x.endswith('.mp3')]) if os.path.isdir(voz) else 0
    return {'tipo': 'proyecto_editable', 'version': VERSION, 'proyecto': os.path.basename(os.path.normpath(d)),
            'fecha': time.strftime('%Y-%m-%d %H:%M:%S'), 'bloques': bloques, 'voces': voces,
            'archivos': [{'ruta': z.split('/', 1)[1], 'bytes': os.path.getsize(f)} for f, z in xs] + extras}


def _texto_leeme(nombre):
    return (f'PROYECTO EDITABLE «{nombre}»\r\n\r\n'
            'Para seguir editándolo: abre la app (Estudio) y pulsa «📂 Abrir proyecto editable», elige este .zip.\r\n'
            'Queda como un proyecto más (si ya tienes uno con el mismo nombre, se llama igual con _2, _3…).\r\n'
            'Luego «🎚 Editor por pistas» para mover o cambiar voces, etiquetas, círculos, subtítulos y música, y\r\n'
            '«▶ Hacer todo» o «🔁 Rehacer video» para armar el video otra vez. Las voces van dentro: no se pagan otra vez.\r\n\r\n'
            'No descomprimas a mano dentro de mis_proyectos: deja que la app lo abra.\r\n')


def empaquetar(d, destino, generados=(), con_final=False, extras=(), avance=None):
    """Escribe el .zip editable de la carpeta d en `destino`. `extras` = [(ruta en disco, ruta dentro del zip sin la
    carpeta del proyecto)] que viven fuera del proyecto (música fija, conocimientos). Devuelve la ruta del .zip."""
    xs = lista(d, generados, con_final)
    base = os.path.basename(os.path.normpath(d))
    otros = [(f, f'{base}/{z}') for f, z in extras if os.path.isfile(f) and f'{base}/{z}' not in {y for _, y in xs}]
    todos = xs + otros
    total = sum(os.path.getsize(f) for f, _ in todos) or 1
    hecho = 0
    tmp = destino + '.part'
    os.makedirs(os.path.dirname(os.path.abspath(destino)) or '.', exist_ok=True)
    try:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for f, dentro in todos:
                modo = zipfile.ZIP_STORED if os.path.splitext(f)[1].lower() in SIN_COMPRIMIR else zipfile.ZIP_DEFLATED
                z.write(f, dentro, compress_type=modo)
                hecho += os.path.getsize(f)
                if avance:
                    avance(hecho, total, dentro.split('/', 1)[1])
            man = _manifiesto(d, xs, [{'ruta': z2.split('/', 1)[1], 'bytes': os.path.getsize(f2), 'fuera_del_proyecto': True}
                                      for f2, z2 in otros])
            z.writestr(f'{base}/{MANIFIESTO}', json.dumps(man, ensure_ascii=False, indent=1))
            z.writestr(f'{base}/{LEEME}', _texto_leeme(base))
        os.replace(tmp, destino)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return destino


def _nombre_libre(proyectos, base):
    base = re.sub(r'^PC2_', '', re.sub(r'[^\w\- ]', '', base or '')).strip() or 'proyecto'
    nombre, k = base, 2
    while os.path.exists(os.path.join(proyectos, nombre)):  # nunca pisa un proyecto que ya tienes
        nombre, k = f'{base}_{k}', k + 1
    return nombre


def _seguro(destino, rel):
    """La ruta final dentro de `destino`, o None si se sale de la carpeta (zip malicioso o mal hecho)."""
    rel = rel.replace('\\', '/')
    if not rel or rel.startswith('/') or re.match(r'^[A-Za-z]:', rel) or '..' in rel.split('/'):
        return None
    f = os.path.realpath(os.path.join(destino, rel))
    raiz = os.path.realpath(destino)
    return f if os.path.commonpath([f, raiz]) == raiz else None


def abrir_zip(origen, proyectos, nombre_sugerido='', avance=None, exigir=True):
    """Abre un .zip de proyecto (editable, de «Guardar como» o de otra PC) como un proyecto nuevo en `proyectos`.
    Devuelve (nombre del proyecto, carpeta). Con exigir=False abre cualquier .zip (como hacía «📂 Abrir proyecto»)."""
    try:
        z = zipfile.ZipFile(origen)
    except zipfile.BadZipFile:
        raise ValueError('Ese archivo no es un .zip.')
    with z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if not infos:
            raise ValueError('El .zip está vacío.')
        nombres = [i.filename for i in infos]
        raices = {n.split('/', 1)[0] for n in nombres}
        dentro = len(raices) == 1 and all('/' in n for n in nombres)  # el zip trae la carpeta del proyecto
        base = next(iter(raices)) if dentro else os.path.splitext(os.path.basename(nombre_sugerido or origen))[0]
        rels = [n.split('/', 1)[1] if dentro else n for n in nombres]
        if exigir and not any(r in ('guion.json', 'transcripcion.json', 'original.mp4', MANIFIESTO) for r in rels):
            raise ValueError('Ese .zip no parece un proyecto de la app (no trae guion.json, transcripcion.json ni original.mp4).')
        nombre = _nombre_libre(proyectos, base)
        destino = os.path.join(proyectos, nombre)
        total = sum(i.file_size for i in infos) or 1
        hecho = 0
        os.makedirs(destino)
        try:
            for i, rel in zip(infos, rels):
                f = _seguro(destino, rel)
                if f is None:
                    continue  # una ruta que se sale de la carpeta del proyecto no se copia
                os.makedirs(os.path.dirname(f), exist_ok=True)
                with z.open(i) as a, open(f, 'wb') as b:
                    shutil.copyfileobj(a, b, 8 << 20)
                hecho += i.file_size
                if avance:
                    avance(hecho, total, rel)
        except BaseException:
            shutil.rmtree(destino, ignore_errors=True)  # a medias no sirve: no deja un proyecto roto en la lista
            raise
    return nombre, destino


def abrir_carpeta(origen, proyectos, avance=None):
    """Copia una CARPETA de proyecto (con guion.json, original.mp4…) como un proyecto nuevo. Devuelve (nombre, carpeta)."""
    origen = os.path.normpath(origen)
    if not os.path.isdir(origen):
        raise ValueError('Esa carpeta no existe.')
    if os.path.commonpath([os.path.realpath(origen), os.path.realpath(proyectos)]) == os.path.realpath(proyectos):
        raise ValueError('Esa carpeta ya está dentro de tus proyectos: elígela en la lista de arriba.')
    hay = set(os.listdir(origen))
    if not hay & {'guion.json', 'transcripcion.json', 'original.mp4', MANIFIESTO}:
        raise ValueError('Esa carpeta no parece un proyecto de la app (no trae guion.json, transcripcion.json ni original.mp4).')
    nombre = _nombre_libre(proyectos, os.path.basename(origen))
    destino = os.path.join(proyectos, nombre)
    archivos = [(os.path.join(r, a), os.path.relpath(os.path.join(r, a), origen)) for r, _, xs in os.walk(origen) for a in xs]
    total = sum(os.path.getsize(f) for f, _ in archivos) or 1
    hecho = 0
    try:
        for f, rel in archivos:
            dst = os.path.join(destino, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(f, dst)
            hecho += os.path.getsize(f)
            if avance:
                avance(hecho, total, rel.replace(os.sep, '/'))
    except BaseException:
        shutil.rmtree(destino, ignore_errors=True)
        raise
    return nombre, destino


def en_segundo_plano(tarea, proyecto, fn):
    """Corre fn(avance) en un hilo y deja el avance en ESTADO (para la barra con porcentaje). Error si ya hay otra."""
    with _CANDADO:
        if ESTADO['activo']:
            raise ValueError('Ya estoy guardando o abriendo un proyecto editable. Espera a que termine.')
        ESTADO.update(activo=True, tarea=tarea, proyecto=proyecto, hecho=0, total=0, archivo='', error='', resultado=None)

    def avance(hecho, total, archivo):
        ESTADO.update(hecho=hecho, total=total, archivo=archivo)

    def correr():
        try:
            ESTADO['resultado'] = fn(avance)
        except Exception as e:  # noqa: BLE001  el error se muestra en la página
            ESTADO['error'] = str(e) or type(e).__name__
        finally:
            ESTADO['activo'] = False

    threading.Thread(target=correr, daemon=True).start()


def estado():
    e = dict(ESTADO)
    e['porcentaje'] = round(100 * e['hecho'] / e['total']) if e['total'] else 0
    return e
