"""Diagnóstico de fallos de IA (y de los demás pasos): qué pasó, dónde, y con qué evidencia.

Cada llamada a una IA se anota en diagnosticos/llamadas_<ejecución>.jsonl (sin claves ni contenido: solo datos técnicos y
un hash del pedido). Cuando un paso falla, o cuando una llamada falló aunque el paso siguió, se escribe un informe en
diagnosticos/diagnostico_<fecha>_<id>.json y .txt, con la causa CONFIRMADA solo si la API la dio explícitamente.

Clases: A rechazo por políticas · B organización o cuenta deshabilitada · C autenticación o permisos · D créditos o
facturación · E límites de solicitudes o tokens · F formato, JSON o respuesta incompleta · G error de programación ·
H red o servicio externo · I causa desconocida.
"""
import hashlib, json, os, re, time, uuid

CLASES = {
    'A': 'Rechazo por políticas del modelo',
    'B': 'Organización o cuenta deshabilitada',
    'C': 'Error de autenticación o permisos',
    'D': 'Créditos insuficientes o facturación',
    'E': 'Límites de solicitudes o tokens',
    'F': 'Error de formato, JSON o respuesta incompleta',
    'G': 'Error de programación',
    'H': 'Fallo de red o servicio externo',
    'I': 'Causa desconocida',
}
PERMANENTES = {'A', 'B', 'C', 'D'}
TIPOS_RESPUESTA = {
    'ok': 'HTTP 200 con respuesta completa', 'ok_otro_modelo': 'HTTP 200: respondió otro modelo tras un rechazo del pedido',
    'reutilizada': 'respuesta ya obtenida antes, reutilizada sin volver a pedirla',
    'rechazo_200': 'HTTP 200 con rechazo del modelo (stop_reason=refusal / refusal / content_filter)',
    'incompleta': 'HTTP 200 con respuesta incompleta (cortada por el límite de tokens)',
    'vacia': 'HTTP 200 con respuesta vacía', 'json_invalido': 'HTTP 200 con respuesta que no es JSON válido',
    'error_http': 'error HTTP de la API', 'sin_conexion': 'sin respuesta (red o servicio)',
}
RESULTADOS = {
    'completado': 'Proceso completado correctamente.',
    'completado_con_incidencias': 'Proceso completado con incidencias: terminó, pero alguna solicitud falló, fue '
                                  'rechazada o un paso opcional se saltó.',
    'interrumpido': 'Proceso interrumpido por un error.',
}  # reintentar igual no sirve: hay que cambiar algo antes

ETAPAS = {
    1: 'Análisis visual del video', 2: 'Extracción y procesamiento de fotogramas', 3: 'Transcripción del audio',
    4: 'Comprensión contextual', 5: 'Análisis y reescritura del guion', 6: 'Generación de narración con ElevenLabs',
    7: 'Sincronización de voz y video', 8: 'Cortes, montaje y exportación', 9: 'Control de calidad',
}
# qué etapa es cada función que llama a la IA (la operación)
ETAPA_FUNCION = {
    'mapa_video': 1, 'mapa_ia': 1, 'senales_auto': 1, 'senales_autor': 1, 'revisar_senales': 9, 'revisar_con_imagen': 9,
    'autorrevision': 5, 'corregir_largo': 5, 'corregir_con_respuestas': 5, 'main': 5,
    'no_importantes': 4, 'perfil_ia': 4, 'leer_modelos': 1, 'escribir_frase': 5,
}
# y cada paso de la app
ETAPA_PASO = {
    'transcribir': 3, 'guion_ia': 5, 'ia': 5, 'trailer_ia': 5, 'etiquetas_ia': 5, 'revisar_imagen': 9, 'senales_ia': 1,
    'alimentar': 4, 'acortar': 4, 'voz': 6, 'musica': 6, 'mezclar': 7, 'montaje': 8, 'insertos': 8, 'etiquetas': 8,
    'senales': 8, 'tarjetas': 8, 'capas': 8, 'testimonios': 8, 'nuevos_modelos': 8, 'trailer': 8, 'final_sin_trailer': 8,
    'exportar': 8, 'nube': 8,
}
SERVICIO_PASO = {
    'transcribir': 'ElevenLabs Scribe o Whisper', 'voz': 'ElevenLabs', 'musica': 'ElevenLabs', 'mezclar': 'FFmpeg',
    'montaje': 'FFmpeg', 'insertos': 'FFmpeg', 'etiquetas': 'Remotion', 'senales': 'Remotion', 'tarjetas': 'FFmpeg', 'capas': 'FFmpeg',
    'testimonios': 'FFmpeg', 'nuevos_modelos': 'ElevenLabs y FFmpeg', 'trailer': 'ElevenLabs, Remotion y FFmpeg',
    'final_sin_trailer': 'FFmpeg', 'exportar': 'FFmpeg',
}


def carpeta():
    """La carpeta de diagnósticos del proyecto: la app la pasa en DIAG_DIR; si no, junto al proyecto actual."""
    return os.environ.get('DIAG_DIR') or os.path.join(os.getcwd(), 'diagnosticos')


def ejecucion():
    return os.environ.get('DIAG_RUN') or 'manual'


SECRETOS = [
    (re.compile(r'sk-ant-[A-Za-z0-9_\-]{6,}'), 'sk-ant-[REDACTADO]'),
    (re.compile(r'sk-[A-Za-z0-9_\-]{12,}'), 'sk-[REDACTADO]'),
    (re.compile(r'sk_[A-Za-z0-9]{20,}'), 'sk_[REDACTADO]'),  # las de ElevenLabs
    (re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}'), r'\1[REDACTADO]'),
    (re.compile(r'(?i)(x-api-key|xi-api-key|api[_-]?key|authorization|password|contrase\w*|token)(["\']?\s*[:=]\s*["\']?)[^\s"\',}]{4,}'),
     r'\1\2[REDACTADO]'),
    (re.compile(r'AIza[0-9A-Za-z_\-]{20,}'), '[REDACTADO]'),
    (re.compile(r'[A-Za-z0-9+/]{200,}={0,2}'), '[datos binarios omitidos]'),
]


def redactar(txt, largo=2000):
    """Quita claves, tokens y datos binarios de un texto antes de guardarlo."""
    txt = str(txt if txt is not None else '')
    for patron, cambio in SECRETOS:
        txt = patron.sub(cambio, txt)
    return txt[:largo]


def huella(txt):
    """Hash corto del pedido: identifica qué pedido falló sin guardar su contenido."""
    return hashlib.sha256((txt or '').encode('utf-8', 'replace')).hexdigest()[:16]


NEGATIVAS = re.compile(r"(?i)\b(i can['’]?t|i cannot|i['’]?m (not able|unable)|i won['’]?t|no puedo (ayudar|asistir|proporcionar|crear)|"
                       r"lo siento, pero no|i['’]?m sorry, but|not able to (help|assist)|against (my|our) (guidelines|policies)|"
                       r"no me es posible)")


def parece_negativa(txt):
    """Heurística local: el texto PARECE una negativa. Nunca basta para confirmar un rechazo por políticas."""
    return bool(NEGATIVAS.search(txt or ''))


def anotar(evento):
    """Guarda una llamada (o un fallo) de la ejecución actual. Nunca debe frenar el trabajo."""
    try:
        os.makedirs(carpeta(), exist_ok=True)
        ev = {'fecha': time.strftime('%Y-%m-%d %H:%M:%S'), 'ejecucion': ejecucion(), 'paso': os.environ.get('DIAG_PASO', ''),
              **{k: (redactar(v) if isinstance(v, str) else v) for k, v in evento.items()}}
        with open(os.path.join(carpeta(), f'llamadas_{ejecucion()}.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps(ev, ensure_ascii=False) + '\n')
    except Exception:
        pass


def llamadas(d, ejec):
    try:
        with open(os.path.join(d, f'llamadas_{ejec}.jsonl'), encoding='utf-8') as f:
            return [json.loads(l) for l in f if l.strip()]
    except (OSError, ValueError):
        return []


def clasificar(ev):
    """(clase, confirmada, explicación) de UN evento de llamada o de error de un paso."""
    sr = ev.get('motivo_fin') or ''
    st = ev.get('http') or 0
    msg = ' '.join(str(ev.get(k) or '') for k in ('mensaje_api', 'tipo_error', 'mensaje')).lower()
    if ev.get('incidencia') == 'rechazo_recuperado':
        return 'A', True, ('HTTP 200: la API marcó un rechazo del modelo pedido y el servidor pasó el pedido a otro modelo, que sí '
                           f"respondió ({ev.get('motivo_cambio') or 'cambio de modelo'}). Esa solicitud siguió adelante.")
    if 400 <= st < 500 and re.search(r'content_policy|content exists risk|content_filter|safety|moderation|flagged|'
                                     r'violat\w* (our|the) (usage )?polic', msg):
        return 'A', True, (f'HTTP {st}: la API rechazó el pedido por sus políticas de contenido. No se reintenta.')
    if ev.get('rechazo_explicito') or sr in ('refusal', 'content_filter'):
        cat = ev.get('categoria_rechazo')
        return 'A', True, ('HTTP 200 (la solicitud se completó), pero la API marcó la respuesta como rechazo del modelo ('
                           + (f'categoría «{cat}»' if cat else f'motivo «{sr or "refusal"}»') + '). No es un error HTTP ni de JSON.')
    if re.search(r'(organization|organisation|account).{0,40}(disabled|deactivated|suspended|banned)|'
                 r'(disabled|deactivated|suspended).{0,40}(organization|account)', msg):
        return 'B', True, 'La API dice que la organización o la cuenta está deshabilitada.'
    if re.search(r'credit balance|insufficient_quota|billing|payment|quota_exceeded|exceeded your current quota|'
                 r'not enough credits|insufficient (credits|funds|balance)', msg) or st == 402:
        return 'D', True, 'La API dice que no hay créditos o hay un problema de facturación.'
    if st == 401 or re.search(r'authentication_error|invalid (api )?key|incorrect api key|invalid x-api-key', msg):
        return 'C', True, 'La API rechazó la clave (autenticación).'
    if st == 403 or re.search(r'permission_error|not scoped to a workspace|does not have access|permission denied', msg):
        return 'C', True, 'La clave no tiene permiso para este modelo o recurso.'
    if st == 404 or 'not_found_error' in msg or 'model_not_found' in msg:
        return 'C', True, 'La API no encontró el modelo o la dirección (modelo mal escrito o sin acceso).'
    if st == 413 or re.search(r'prompt is too long|context.length|maximum context|too many tokens|request too large|'
                              r'too many images|image.{0,20}(exceed|too large)', msg):
        return 'E', True, 'El pedido supera el límite de tamaño (tokens, contexto o imágenes) del modelo.'
    if st == 429 or 'rate_limit' in msg:
        return 'E', True, 'Demasiadas solicitudes o tokens por minuto (límite de velocidad).'
    if sr in ('max_tokens', 'length'):
        return 'E', True, 'La respuesta se cortó por el límite de tokens de salida: quedó incompleta.'
    if st in (500, 502, 503, 504, 529) or re.search(r'overloaded|internal server error|service unavailable|bad gateway', msg):
        return 'H', True, f'El servicio del proveedor falló o estaba saturado (HTTP {st or "5xx"}).'
    if ev.get('tipo') == 'red' or re.search(r'urlerror|connection|timed? ?out|winerror 100\d\d|getaddrinfo|name resolution|'
                                            r'no hay conexi', msg):
        return 'H', True, 'No hubo conexión con el servicio (red, DNS o tiempo de espera).'
    if ev.get('tipo') == 'respuesta_ilegible' or ev.get('tipo') == 'respuesta_vacia':
        if ev.get('parece_negativa'):
            return 'A', False, ('La IA contestó con texto en vez del JSON pedido y el texto PARECE una negativa, pero la API no '
                                'lo marcó como rechazo: causa no confirmada.')
        return 'F', True, ('La IA contestó, pero la respuesta ' +
                           ('vino vacía.' if ev.get('tipo') == 'respuesta_vacia' else 'no se pudo leer como JSON (formato).'))
    if ev.get('tipo') == 'programa' or re.search(r'traceback|typeerror|keyerror|attributeerror|nameerror|indexerror|'
                                                 r'valueerror|zerodivision|calledprocesserror|filenotfounderror', msg):
        return 'G', True, 'Falló el propio programa (un error en el código o en una herramienta como ffmpeg).'
    if 400 <= st < 500:
        return 'I', False, f'La API devolvió HTTP {st} sin un motivo reconocible.'
    return 'I', False, 'No hay evidencia suficiente para saber la causa.'


FALTA = {
    'A': 'La categoría del rechazo cuando la API no la da, y si el mismo pedido pasa con otro modelo del mismo proveedor.',
    'B': 'El estado de la organización en la consola del proveedor (console.anthropic.com o platform.openai.com).',
    'C': 'Qué workspace y permisos tiene la clave en la consola del proveedor.',
    'D': 'El saldo y el plan actual en la consola del proveedor.',
    'E': 'Los límites de tu plan (solicitudes y tokens por minuto) y el tamaño del pedido (imágenes y texto).',
    'F': 'El texto exacto que devolvió la IA: actívalo con «diagnostico_guardar_respuesta»: true en app/ajustes.json '
         'y repite (se guarda redactado y recortado).',
    'G': 'La pila de errores completa del registro.txt y la versión de Python y de las librerías instaladas.',
    'H': 'Si el fallo se repite y a qué hora; la página de estado del proveedor.',
    'I': 'El mensaje completo de la API y el registro.txt de esta ejecución.',
}
SOLUCION = {
    'A': 'No reintentar igual. Revisar que el pedido describa con claridad el trabajo editorial, o usar otro proveedor '
         'cuyas políticas acepten el tema. No intentar esquivar el filtro.',
    'B': 'Contactar al proveedor o revisar el estado de la cuenta. Mientras tanto, usar otro proveedor.',
    'C': 'Revisar o crear una clave nueva con permisos para este modelo (dentro de un workspace) y probarla con «Comprobar clave».',
    'D': 'Cargar saldo o revisar el método de pago en la consola del proveedor.',
    'E': 'Esperar un poco y reintentar; si es por tamaño, bajar las capturas en «⚙ Ajustes IA» o usar un modelo con más contexto.',
    'F': 'Reintentar; si se repite, probar otro modelo o revisar el texto devuelto (activando el guardado redactado).',
    'G': 'Compartir este informe y el registro.txt para corregir el código. Reintentar no lo arregla.',
    'H': 'Revisar internet y reintentar en unos minutos.',
    'I': 'Reintentar una vez y, si se repite, compartir este informe.',
}
SIMPLE = {
    'A': 'La IA se negó a hacer esta parte por sus reglas de uso.',
    'B': 'La cuenta de la IA está desactivada.',
    'C': 'La clave de la IA no sirve o no tiene permiso para este modelo.',
    'D': 'No hay saldo en la cuenta de la IA.',
    'E': 'Se pasó un límite: demasiados pedidos seguidos o un pedido demasiado grande.',
    'F': 'La IA contestó, pero la respuesta vino vacía, cortada o en un formato que la app no pudo leer.',
    'G': 'Falló la propia app (un error del programa), no la IA.',
    'H': 'Se cortó la conexión con el servicio o el servicio estaba caído.',
    'I': 'No se pudo saber la causa con los datos que hay.',
}


def _error_del_registro(texto_paso):
    """Del texto del registro de UN paso: la línea ERROR y, si hubo, la pila de errores (archivo, función, tipo)."""
    out = {}
    m = re.search(r'^ERROR:\s*(.+)$', texto_paso, re.M)
    if m:
        out['mensaje'] = m.group(1).strip()
    tb = texto_paso.rfind('Traceback (most recent call last):')
    if tb >= 0:
        pila = texto_paso[tb:].strip().splitlines()
        fin = next((k for k, l in enumerate(pila[1:], 1) if not l.startswith(' ')), len(pila) - 1)
        pila = pila[:fin + 1]
        out['pila'] = '\n'.join(pila[-14:])
        marcos = re.findall(r'File "([^"]+)", line (\d+), in (\S+)', '\n'.join(pila))
        propios = [x for x in marcos if 'site-packages' not in x[0] and 'Python3' not in x[0] and '/lib/python' not in x[0]]
        if propios:
            f, linea, fn = propios[-1]
            out['archivo'], out['linea'], out['funcion'] = os.path.basename(f), int(linea), fn
        ultima = pila[-1] if pila else ''
        out['tipo_error'] = ultima.split(':')[0].strip()
        out.setdefault('mensaje', ultima)
        out['tipo'] = 'programa'
    if 'mensaje' not in out:
        utiles = [l.strip() for l in texto_paso.splitlines() if l.strip() and not l.startswith(('✗', '▶', '·'))]
        if utiles:
            out['mensaje'] = utiles[-1]
    m = re.search(r'(?:error|HTTP|respondió(?: con error)?)\s*\(?(\d{3})\b', out.get('mensaje', ''))
    if m:
        out['http'] = int(m.group(1))
    return out


def informe(d, proyecto, paso, nombre_paso, ejec, registro, estado, proveedor='', modelo=''):
    """Escribe diagnostico_<fecha>_<id>.json y .txt para esta ejecución. Devuelve el resumen para la app, o None si no
    hay nada que informar (paso bien hecho y sin llamadas fallidas)."""
    todas = llamadas(d, ejec)
    propias = [x for x in todas if x.get('paso') == paso] or todas
    # problemas: llamadas que fallaron y las que siguieron solo porque respondió otro modelo tras un rechazo
    fallidas = [x for x in propias if not x.get('ok') or x.get('incidencia')]
    if estado == 'ok' and not fallidas:
        return None
    reg = _error_del_registro(registro or '') if estado != 'ok' else {}
    # la causa: la última llamada a la IA que falló; si no hubo, el error del paso (ElevenLabs, ffmpeg, código)
    base = dict(fallidas[-1]) if fallidas else {}
    if reg.get('tipo') == 'programa' and not (fallidas and fallidas[-1].get('tipo') != 'programa'):
        base = {**reg}
    elif not base:
        base = {**reg, 'tipo': reg.get('tipo') or 'paso'}
    clase, confirmada, explica = clasificar(base)
    # la función solo dice la etapa si es una llamada a la IA; en un error del programa «main» es cualquier paso
    de_ia = bool(fallidas) and base.get('tipo') != 'programa'
    etapa = (base.get('etapa') or (ETAPA_FUNCION.get(base.get('funcion', '')) if de_ia else None) or ETAPA_PASO.get(paso) or 5)
    ia = base.get('proveedor') or SERVICIO_PASO.get(paso) or proveedor or 'desconocido'
    ident = uuid.uuid4().hex[:8]
    datos = {
        'id': ident, 'proyecto': proyecto, 'fecha': time.strftime('%Y-%m-%d %H:%M:%S'), 'ejecucion': ejec,
        'estado': {'fallo': 'falló', 'saltado': 'se saltó (no frenó el video)', 'ok': 'terminó con llamadas fallidas o rechazadas'}[estado],
        'resultado_paso': {'fallo': 'Paso interrumpido por un error.',
                           'saltado': 'Paso no hecho; el proceso siguió sin él (incidencia, no fracaso del proyecto).',
                           'ok': 'Paso completado con incidencias: una solicitud individual falló o fue rechazada, pero el paso '
                                 'terminó (no es un fracaso del proyecto).'}[estado],
        'modelo_solicitado': base.get('modelo_solicitado') or base.get('modelo') or '',
        'modelo_respondio': base.get('modelo_respondio') or '',
        'modelo_confirmado': bool(base.get('modelo_respondio')),
        'cambio_modelo': base.get('motivo_cambio') or '', 'nota_modelo': base.get('nota_modelo') or '',
        'tipo_respuesta': TIPOS_RESPUESTA.get(base.get('tipo_respuesta'), base.get('tipo_respuesta') or ''),
        'paso': paso, 'paso_nombre': nombre_paso, 'etapa': f'{etapa}. {ETAPAS.get(etapa, "")}',
        'proveedor': ia, 'modelo': base.get('modelo') or (modelo if ia == proveedor else ''),
        'operacion': base.get('operacion') or base.get('funcion') or nombre_paso,
        'archivo': base.get('archivo') or reg.get('archivo') or '', 'funcion': base.get('funcion') or reg.get('funcion') or '',
        'linea': base.get('linea') or reg.get('linea'),
        'http': base.get('http'), 'tipo_error': base.get('tipo_error') or reg.get('tipo_error') or '',
        'mensaje_original': base.get('mensaje_api') or base.get('mensaje') or reg.get('mensaje') or '',
        'mensaje_app': reg.get('mensaje', ''), 'id_solicitud': base.get('id_solicitud') or '',
        'motivo_fin': base.get('motivo_fin') or '', 'categoria_rechazo': base.get('categoria_rechazo') or '',
        'intentos': len(propias) or 1, 'llamadas_fallidas': len(fallidas),
        'duracion_s': base.get('duracion_s'), 'pila': reg.get('pila', ''),
        'clase': clase, 'clase_nombre': CLASES[clase], 'causa_confirmada': confirmada,
        'causa': ('Confirmada: ' if confirmada else 'Causa no confirmada (probable): ') + CLASES[clase],
        'evidencias': explica, 'falta': '' if confirmada and clase not in ('A', 'F', 'G', 'I') else FALTA[clase],
        'solucion': SOLUCION[clase] if estado != 'ok' else 'Nada que hacer para este video. Para próximas veces: ' + SOLUCION[clase],
        'resumen_simple': ('El paso terminó igual. ' if estado == 'ok' else '') + SIMPLE[clase], 'reintentable': clase not in PERMANENTES and clase != 'G',
        'llamadas': propias[-30:],
    }
    if clase == 'A' and confirmada:
        datos['falta'] = (FALTA['A'] if not base.get('categoria_rechazo') else
                          'Nada esencial: la API dio la categoría. Opcional: si el mismo pedido pasa con otro proveedor.')
    datos['falta'] = datos['falta'] or 'Nada esencial: la API dio el motivo.'
    os.makedirs(d, exist_ok=True)
    nombre = f"diagnostico_{time.strftime('%Y%m%d_%H%M%S')}_{ident}"
    for ext, contenido in (('json', json.dumps(datos, ensure_ascii=False, indent=1)), ('txt', texto(datos))):
        with open(os.path.join(d, f'{nombre}.{ext}'), 'w', encoding='utf-8') as f:
            f.write(redactar(contenido, 10 ** 7))
    return {'archivo': nombre, 'etapa': datos['etapa'], 'ia': ia + (f" ({datos['modelo']})" if datos['modelo'] else ''),
            'tipo': f"{clase}. {CLASES[clase]}" + ('' if confirmada else ' (no confirmada)'), 'explicacion': datos['resumen_simple'],
            'reintentable': datos['reintentable'], 'estado': estado, 'paso': paso, 'resultado_paso': datos['resultado_paso']}


def texto(x):
    def v(k):
        return x.get(k) if x.get(k) not in (None, '') else '—'
    lineas = [
        'INFORME DE DIAGNÓSTICO DE IA', '=' * 28, '',
        f"Proyecto: {v('proyecto')}", f"Fecha: {v('fecha')}", f"ID del informe: {v('id')} · ejecución {v('ejecucion')}",
        f"Proveedor: {v('proveedor')}", f"Modelo: {v('modelo')}", f"Etapa del proceso: {v('etapa')}",
        f"Paso de la app: {v('paso_nombre')} ({v('paso')})", f"Operación: {v('operacion')}",
        f"Archivo y función: {v('archivo')} · {v('funcion')}" + (f" (línea {x['linea']})" if x.get('linea') else ''),
        f"Estado: {v('estado')}", f"Resultado del paso: {v('resultado_paso')}",
        f"Modelo solicitado: {v('modelo_solicitado')}",
        f"Modelo que respondió: {v('modelo_respondio')}" + ('' if x.get('modelo_confirmado') else ' (no confirmado por la API)'),
        f"Cambio de modelo: {x.get('cambio_modelo') or 'ninguno informado por la API'}",
        f"Tipo de respuesta: {v('tipo_respuesta')}",
        f"Código HTTP y tipo de error: {v('http')} {x.get('tipo_error') or ''}".rstrip(),
        f"Mensaje original: {v('mensaje_original')}", f"Mensaje que mostró la app: {v('mensaje_app')}",
        f"Identificador de solicitud: {v('id_solicitud')}", f"Motivo de finalización: {v('motivo_fin')}"
        + (f" · categoría {x['categoria_rechazo']}" if x.get('categoria_rechazo') else ''),
        f"Número de intentos: {v('intentos')} (fallidos: {v('llamadas_fallidas')})",
        f"Duración de la operación: {v('duracion_s')} s", '',
        'Respuesta técnica relevante:',
    ]
    for c in x.get('llamadas', [])[-12:]:
        lineas.append(f"  - {c.get('fecha')} · {c.get('operacion') or c.get('funcion')} · intento {c.get('intento', 1)} · "
                      f"{'OK' if c.get('ok') else 'FALLÓ'} · HTTP {c.get('http') or '—'} · fin {c.get('motivo_fin') or '—'} · "
                      f"{c.get('imagenes', 0)} imágenes · pedido {c.get('hash_pedido', '—')} · "
                      f"modelo {c.get('modelo_solicitado') or c.get('modelo') or '—'} → {c.get('modelo_respondio') or 'no confirmado'}"
                      + (' · ' + TIPOS_RESPUESTA.get(c.get('tipo_respuesta'), c.get('tipo_respuesta')) if c.get('tipo_respuesta') else '')
                      + (' · ' + ': '.join(x for x in (c.get('tipo_error') or c.get('tipo'), str(c.get('mensaje_api') or c.get('mensaje') or '')[:180]) if x)
                         if not c.get('ok') else '')
                      + (f" · {c['motivo_cambio']}" if c.get('motivo_cambio') else '')
                      + (f" · solicitud {c['id_solicitud']}" if c.get('id_solicitud') else ''))
    if not x.get('llamadas'):
        lineas.append('  (no hubo llamadas a la IA registradas en este paso)')
    if x.get('pila'):
        lineas += ['', 'Pila de errores (fragmento):', x['pila']]
    lineas += ['', f"Causa confirmada o probable: {x['causa']}", f"Evidencias: {x['evidencias']}",
               f"Qué información falta: {x['falta']}", f"Solución técnica recomendada: {x['solucion']}", '',
               'EN POCAS PALABRAS', '-' * 17, x['resumen_simple'] + ' ' + x['solucion'], '',
               'Este informe no incluye claves, tokens, el guion, imágenes ni audio. Los pedidos se identifican por su hash.']
    return '\n'.join(lineas) + '\n'


def resumen_ejecucion(d, proyecto, ejec, resultado, hechos, saltados, fallo, informes, motivo=''):
    """Resumen de UNA ejecución (todos sus pasos): si terminó bien, con incidencias o interrumpida, qué modelos se
    pidieron y cuáles respondieron (según la API), y qué informes de diagnóstico dejó. resumen_<fecha>_<ejec>.json/.txt"""
    todas = llamadas(d, ejec)
    modelos = {}
    for c in todas:
        k = (c.get('proveedor') or '—', c.get('modelo_solicitado') or c.get('modelo') or '—',
             c.get('modelo_respondio') or ('(no confirmado)' if c.get('ok') or 'intento' not in c else '(sin respuesta)'))
        if 'intento' not in c:  # aviso de respuesta vacía o ilegible: la llamada ya contó como bien, pero no sirvió
            if k in modelos and modelos[k]['bien']:
                modelos[k]['bien'] -= 1
                modelos[k]['fallidas'] += 1
            continue
        m = modelos.setdefault(k, {'proveedor': k[0], 'modelo_solicitado': k[1], 'modelo_respondio': k[2], 'llamadas': 0,
                                   'bien': 0, 'fallidas': 0, 'reutilizadas': 0, 'cambios_de_modelo': 0, 'rechazos_200': 0})
        m['llamadas'] += 1
        m['bien'] += bool(c.get('ok'))
        m['fallidas'] += not c.get('ok')
        m['reutilizadas'] += bool(c.get('reutilizada'))
        m['cambios_de_modelo'] += bool(c.get('cambio_modelo'))
        m['rechazos_200'] += c.get('tipo_respuesta') in ('rechazo_200', 'ok_otro_modelo')
    if not todas and resultado == 'completado' and not informes:
        return None
    datos = {'proyecto': proyecto, 'fecha': time.strftime('%Y-%m-%d %H:%M:%S'), 'ejecucion': ejec, 'resultado': resultado,
             'resultado_texto': RESULTADOS[resultado] + (f' ({motivo})' if motivo else ''), 'pasos_hechos': hechos,
             'pasos_saltados': saltados, 'paso_que_fallo': fallo or '', 'modelos': list(modelos.values()),
             'cambios_de_modelo': [{'modelo_solicitado': c.get('modelo_solicitado'), 'modelo_respondio': c.get('modelo_respondio'),
                                    'motivo': c.get('motivo_cambio'), 'id_solicitud': c.get('id_solicitud'), 'paso': c.get('paso')}
                                   for c in todas if c.get('cambio_modelo')],
             'informes': informes}
    lineas = ['RESUMEN DE LA EJECUCIÓN', '=' * 23, '', f'Proyecto: {proyecto}', f"Fecha: {datos['fecha']}", f'Ejecución: {ejec}', '',
              datos['resultado_texto'], '',
              'Pasos completados: ' + (', '.join(hechos) or '—'), 'Pasos saltados: ' + (', '.join(saltados) or '—'),
              'Paso interrumpido: ' + (fallo or '—'), '', 'Modelos (lo que pediste y lo que respondió, según la API):']
    for m in datos['modelos']:
        lineas.append(f"  - {m['proveedor']} · pedido {m['modelo_solicitado']} → respondió {m['modelo_respondio']} · "
                      f"{m['llamadas']} llamadas ({m['bien']} bien, {m['fallidas']} fallidas, {m['reutilizadas']} reutilizadas, "
                      f"{m['rechazos_200']} rechazos con HTTP 200, {m['cambios_de_modelo']} con cambio de modelo)")
    if not datos['modelos']:
        lineas.append('  (no hubo llamadas a la IA en esta ejecución)')
    if datos['cambios_de_modelo']:
        lineas += ['', 'Cambios de modelo:'] + [f"  - {c['paso'] or '—'}: {c['motivo']}" + (f" (solicitud {c['id_solicitud']})"
                                                                                            if c['id_solicitud'] else '')
                                                 for c in datos['cambios_de_modelo']]
    lineas += ['', 'Informes de diagnóstico:'] + ([f"  - {i['archivo']}.txt · {i.get('paso', '')} · {i['tipo']} · {i.get('resultado_paso', '')}"
                                                   for i in informes] or ['  (ninguno)'])
    lineas += ['', 'Este resumen no incluye claves, tokens, el guion, imágenes ni audio.']
    os.makedirs(d, exist_ok=True)
    nombre = f"resumen_{time.strftime('%Y%m%d_%H%M%S')}_{ejec[-6:]}"
    for ext, contenido in (('json', json.dumps(datos, ensure_ascii=False, indent=1)), ('txt', '\n'.join(lineas) + '\n')):
        with open(os.path.join(d, f'{nombre}.{ext}'), 'w', encoding='utf-8') as f:
            f.write(redactar(contenido, 10 ** 7))
    return {'archivo': nombre, 'resultado': resultado, 'texto': datos['resultado_texto']}
