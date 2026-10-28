"""«🌐 Etiquetas en otro idioma»: las mismas etiquetas, traducidas, sin hacerlas de nuevo.

Vive en mis_proyectos/NOMBRE/etiquetas_idiomas.json:
    {"idioma": "en",                                  ← con cuál se dibujan («es» u otro vacío = las originales)
     "traducciones": {"en": {"Descarga aquí": "Download here", ...}, "pt": {...}}}
Cada texto original (título o texto de etiquetas.json, y las etiquetas de tus capturas de «Flechas y círculos») tiene su
traducción por idioma. La traduce la IA (traducir.py) o la escribes tú en la app; lo que no tenga traducción va como está.
Cambiar de idioma solo vuelve a dibujar las etiquetas: la voz, el montaje y la música no se tocan.
"""
import json, os

ARCHIVO = 'etiquetas_idiomas.json'
ORIGINAL = 'es'
NOMBRES = {'es': 'Español (original)', 'en': 'English', 'pt': 'Português', 'fr': 'Français', 'it': 'Italiano', 'de': 'Deutsch'}


def leer(d):
    try:
        x = json.load(open(os.path.join(d, ARCHIVO), encoding='utf-8'))
        if isinstance(x, dict):
            x.setdefault('idioma', ORIGINAL)
            x.setdefault('traducciones', {})
            return x
    except (OSError, ValueError):
        pass
    return {'idioma': ORIGINAL, 'traducciones': {}}


def guardar(d, datos):
    tmp = os.path.join(d, ARCHIVO + '.tmp')
    json.dump(datos, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(d, ARCHIVO))


def textos(d):
    """Todos los textos originales de las etiquetas del proyecto, sin repetir y en orden."""
    out = []
    try:
        for e in json.load(open(os.path.join(d, 'etiquetas.json'), encoding='utf-8')):
            out += [str(e.get(k) or '').strip() for k in ('titulo', 'texto')]
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    try:
        for m in json.load(open(os.path.join(d, 'marcas_senales', 'marcas.json'), encoding='utf-8')).get('MARCAS', []):
            out.append(str(m.get('etiqueta') or '').strip() if isinstance(m, dict) else '')
    except (OSError, ValueError, AttributeError):
        pass
    vistos, lista = set(), []
    for t in out:
        if t and t not in vistos:
            vistos.add(t)
            lista.append(t)
    return lista


def aplicar(items, d):
    """Las etiquetas con el título y el texto en el idioma elegido (lo que no tenga traducción queda igual)."""
    datos = leer(d)
    idioma = datos.get('idioma') or ORIGINAL
    if idioma == ORIGINAL:
        return items, idioma, 0
    tabla = datos['traducciones'].get(idioma) or {}
    faltan = 0
    out = []
    for e in items:
        e = dict(e)
        for k in ('titulo', 'texto'):
            v = str(e.get(k) or '').strip()
            if v:
                if tabla.get(v):
                    e[k] = tabla[v]
                else:
                    faltan += 1
        out.append(e)
    return out, idioma, faltan
