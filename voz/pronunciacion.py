"""«🗣 Pronunciación»: cómo tiene que decir la voz tus siglas y marcas (FRP, DFU, IMEI, Xiaomi…), siempre igual.

La lista vive en mis_conocimientos/pronunciacion.json (la misma para todos tus videos) y se sube a ElevenLabs como un
diccionario de pronunciación (reglas «alias»: donde dice FRP, se lee «efe erre pe»). El guion y los subtítulos siguen
diciendo FRP: solo cambia lo que se escucha. Subirlo no gasta créditos; la voz de cada bloque se paga igual que siempre.

Lo usan voz.py (la voz del video y la del Short), el tráiler, los testimonios narrados y los nuevos modelos.
Uso suelto: python pronunciacion.py --subir   (crea o actualiza el diccionario en ElevenLabs y muestra su id)
"""
import argparse, hashlib, json, os, re, urllib.error, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVO = os.path.join(RAIZ, 'mis_conocimientos', 'pronunciacion.json')
API = 'https://api.elevenlabs.io/v1/pronunciation-dictionaries'

# para empezar: lo que más se repite en el canal (se edita en «🎛 Audio e imagen» → Pronunciación)
BASE = [
    {'palabra': 'FRP', 'decir': 'efe erre pe'},
    {'palabra': 'DFU', 'decir': 'de efe u'},
    {'palabra': 'IMEI', 'decir': 'imei'},
    {'palabra': 'ECID', 'decir': 'e sid'},
    {'palabra': 'iCloud', 'decir': 'ai claud'},
    {'palabra': 'iPhone', 'decir': 'aifon'},
    {'palabra': 'iOS', 'decir': 'ai o ese'},
    {'palabra': 'Xiaomi', 'decir': 'shaomi'},
    {'palabra': 'Huawei', 'decir': 'juawei'},
    {'palabra': 'ADB', 'decir': 'a de be'},
    {'palabra': 'USB', 'decir': 'u ese be'},
    {'palabra': 'MTK', 'decir': 'eme te ka'},
    {'palabra': 'APK', 'decir': 'a pe ka'},
    {'palabra': 'OTG', 'decir': 'o te ge'},
    {'palabra': 'Wi-Fi', 'decir': 'uai fai'},
]


def leer():
    """{'reglas': [{'palabra', 'decir'}], 'eleven': {'huella', 'id', 'version'}} (con la lista de base si no hay archivo)."""
    try:
        d = json.load(open(ARCHIVO, encoding='utf-8'))
        if isinstance(d, dict) and isinstance(d.get('reglas'), list):
            return d
    except (OSError, ValueError):
        pass
    return {'reglas': [dict(r) for r in BASE], 'eleven': {}}


def guardar(datos):
    os.makedirs(os.path.dirname(ARCHIVO), exist_ok=True)
    with open(ARCHIVO + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(ARCHIVO + '.tmp', ARCHIVO)


def limpiar(reglas):
    """Las reglas válidas, sin repetidas (la última manda), con palabra y forma de decirla cortas."""
    vistas = {}
    for r in reglas or []:
        p, s = str(r.get('palabra') or '').strip()[:60], str(r.get('decir') or '').strip()[:120]
        if p and s and p != s:
            vistas[p] = s
    return [{'palabra': p, 'decir': s} for p, s in vistas.items()]


def reglas():
    return limpiar(leer().get('reglas'))


def _variantes(p):
    """FRP, frp y Frp: ElevenLabs compara letra por letra, así que se sube cada forma en que puede venir escrita."""
    return list(dict.fromkeys([p, p.lower(), p.upper(), p[:1].upper() + p[1:].lower()]))


def aplicables(texto, lista=None):
    """Las reglas cuya palabra aparece (como palabra entera, sin importar mayúsculas) en el texto."""
    t = str(texto or '')
    return [r for r in (reglas() if lista is None else lista)
            if re.search(r'(?<![\w-])' + re.escape(r['palabra']) + r'(?![\w-])', t, re.I)]


def firma_bloque(texto, lista=None):
    """Lo que cambia la voz de un bloque: las reglas que le tocan (vacío si ninguna). Va en la firma de voz.py, así
    cambiar cómo se dice FRP rehace solo los bloques que dicen FRP."""
    return sorted(f"{r['palabra']}={r['decir']}" for r in aplicables(texto, lista))


def huella(lista):
    return hashlib.sha1(json.dumps(lista, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _pedido(url, cuerpo, clave):
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers={'Content-Type': 'application/json', **clave})
    return json.load(urllib.request.urlopen(req, timeout=60))


def localizador(clave, mostrar=print):
    """{'pronunciation_dictionary_id', 'version_id'} del diccionario en ElevenLabs al día con la lista, o None.
    Si la lista cambió desde la última vez, se sube de nuevo (no gasta créditos). Sin clave o sin internet devuelve
    None y la voz se hace igual, sin diccionario."""
    datos = leer()
    lista = limpiar(datos.get('reglas'))
    if not lista or clave is None:  # {} vale: en el entorno de Claude la clave la pone el proxy
        return None
    h = huella(lista)
    el = datos.get('eleven') or {}
    if el.get('huella') == h and el.get('id') and el.get('version'):
        return {'pronunciation_dictionary_id': el['id'], 'version_id': el['version']}
    reglas_api = [{'type': 'alias', 'string_to_replace': v, 'alias': r['decir']} for r in lista for v in _variantes(r['palabra'])]
    try:
        r = _pedido(API + '/add-from-rules', {'name': f'Estudio de tutoriales {h[:6]}', 'rules': reglas_api,
                                              'description': 'Pronunciación del canal (lo sube la app Estudio de tutoriales)'}, clave)
    except (urllib.error.URLError, OSError, ValueError) as e:
        detalle = e.read()[:200] if isinstance(e, urllib.error.HTTPError) else e
        mostrar(f'· no pude subir el diccionario de pronunciación a ElevenLabs ({detalle}); sigo sin él')
        return None
    viejo = el.get('id')
    datos['reglas'], datos['eleven'] = lista, {'huella': h, 'id': r['id'], 'version': r['version_id']}
    guardar(datos)
    mostrar(f'· diccionario de pronunciación al día en ElevenLabs ({len(lista)} palabras)')
    if viejo and viejo != r['id']:  # el anterior ya no se usa: se archiva para no llenar tu cuenta
        try:
            _pedido(f'{API}/{viejo}/archive', {}, clave)
        except (urllib.error.URLError, OSError, ValueError):
            pass
    return {'pronunciation_dictionary_id': r['id'], 'version_id': r['version_id']}


def para_pedido(texto, clave, mostrar=print):
    """Lo que se agrega al cuerpo del pedido de voz a ElevenLabs para que use el diccionario (vacío si no le toca)."""
    if not aplicables(texto):
        return {}
    loc = localizador(clave, mostrar)
    return {'pronunciation_dictionary_locators': [loc]} if loc else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--subir', action='store_true')
    a = ap.parse_args()
    if a.subir:
        k = os.environ.get('ELEVENLABS_API_KEY', '').strip()
        if not k:
            try:
                k = json.load(open(os.path.join(RAIZ, 'app', 'ajustes.json'), encoding='utf-8')).get('elevenlabs', '').strip()
            except (OSError, ValueError):
                k = ''
        print(localizador({'xi-api-key': k} if k else {}))
    else:
        for r in reglas():
            print(f"{r['palabra']} → {r['decir']}")


if __name__ == '__main__':
    main()
