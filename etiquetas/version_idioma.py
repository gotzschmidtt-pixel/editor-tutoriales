"""«🌐 Hacer versión en otro idioma»: copia el proyecto y traduce su guion, para armar el mismo video con voz en ese idioma.

Uso: python version_idioma.py --proyecto mis_proyectos/NOMBRE --idioma en [--ajustes app/ajustes.json]
Crea mis_proyectos/NOMBRE_EN con: la grabación (sin duplicar espacio si se puede), la transcripción, el mapa, los cortes
importantes, tus capturas y etiquetas, y el guion con cada bloque traducido por la IA de Ajustes (mismos tramos, mismo
montaje). Deja idioma_video.json para que la voz salga en ese idioma (inglés: Brian) y las etiquetas en ese idioma.
No genera voz ni gasta ElevenLabs: eso lo haces tú después con «▶ Hacer todo», cuando revisaste el guion traducido.
"""
import argparse, json, os, re, shutil, subprocess, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
import idiomas  # noqa: E402

# lo que NO se copia: lo armado con la voz en español (se vuelve a hacer) y lo de diagnóstico
# (las versiones del guion de cada IA y lo que se guardó para Claude están en español, y las voces guardadas son de Mauricio)
NO_COPIAR = re.compile(r'^\.|^(voz|voz_short|diagnosticos|ia_capturas|hojas_2s|acciones|prueba_ingles|referencias|cache_ia|'
                       r'trabajo_modelos|para_claude)$|'
                       r'\.(mp4|mp3|wav)$|^(registro\.txt|ia_respuesta.*|guion\.json.*|guion_.*\.json|versiones_guion\.json|'
                       r'para_claude\.zip|.*\.antes_.*|idioma_video\.json|\d_.*\.(srt|json)|guion_para_leer\.md)$')

# lo que también se lee o se oye fuera del guion: (archivo, lista dentro del archivo, campos con texto)
EXTRAS = [('trailer.json', None, ('titulo', 'subtitulo', 'voz')),
          (os.path.join('testimonios', 'testimonios.json'), 'TESTIMONIOS', ('texto',)),
          (os.path.join('nuevos_modelos', 'modelos.json'), 'MODELOS', ('frase',)),
          ('short_guion.json', 'tomas', ('texto',))]


# carpetas de pruebas, muestras y controles hechos para la versión en español: no hacen falta en la copia
NO_COPIAR_CARPETAS = {'cuadros_control', 'subtitulos_en', 'vista_extras', 'youtube', 'historial_guion'}
IMPRESCINDIBLES = {'original.mp4', 'material.mp4', 'etiquetas.json', 'senales.json', 'insertos.json', 'mapa_video.json',
                   'cortes_importantes.json', 'transcripcion.srt', 'transcripcion.txt'}


def _copiar_uno(f, g, intentos=6):
    """Copia un archivo; si Windows dice que está en uso (otro programa lo está escribiendo), reintenta unos segundos."""
    import time
    for k in range(intentos):
        try:
            if os.path.exists(g) and os.path.samefile(f, g):
                return True  # ya está (el mismo archivo enlazado de una vez anterior): copiarlo sobre sí mismo fallaba
            shutil.copy2(f, g)
            return True
        except PermissionError:
            if k == intentos - 1:
                return False
            time.sleep(1.5)


def copiar(origen, destino):
    """Copia el proyecto a la versión en otro idioma, sin lo que se rehace (videos, voces) ni pruebas y muestras.
    Un archivo en uso se reintenta; si sigue bloqueado y no hace falta, se salta y se avisa (antes fallaba todo:
    31/10/2026, «El proceso no tiene acceso al archivo porque está siendo utilizado por otro proceso»)."""
    os.makedirs(destino, exist_ok=True)
    try:  # el inicio hecho aparte (inicio_fijo.json) es un video de una subcarpeta que sí hace falta
        fijo = os.path.normpath(json.load(open(os.path.join(origen, 'inicio_fijo.json'), encoding='utf-8'))['video'])
    except (OSError, ValueError, KeyError, TypeError):
        fijo = ''
    saltados = []
    for n in os.listdir(origen):
        f, g = os.path.join(origen, n), os.path.join(destino, n)
        if n in ('original.mp4', 'material.mp4'):
            if os.path.exists(g) and os.path.samefile(f, g):
                continue
            try:
                if os.path.exists(g):
                    os.remove(g)
                os.link(f, g)  # el mismo archivo, sin ocupar el doble de espacio
                continue
            except OSError:
                pass
            if not _copiar_uno(f, g):
                raise SystemExit(f'{n} está en uso (¿se está armando algo o hay otra copia en curso?): espera a que termine y vuelve a pulsar.')
        elif NO_COPIAR.search(n) or n in NO_COPIAR_CARPETAS:
            continue
        elif os.path.isdir(f):
            for raiz, carpetas, archivos in os.walk(f):
                rel = os.path.relpath(raiz, origen)
                os.makedirs(os.path.join(destino, rel), exist_ok=True)
                for x in archivos:
                    r = os.path.normpath(os.path.join(rel, x))
                    if re.search(r'\.(mp4|mp3|wav|mov)$', x, re.I) and r != fijo:
                        continue  # videos y audios de pruebas: no (el inicio fijo, sí)
                    if not _copiar_uno(os.path.join(raiz, x), os.path.join(destino, r)):
                        saltados.append(r)
        elif not _copiar_uno(f, g):
            if n in IMPRESCINDIBLES:
                raise SystemExit(f'{n} está en uso (¿se está armando algo?): espera a que termine y vuelve a pulsar.')
            saltados.append(n)
    if saltados:
        print('Aviso: no copié estos archivos porque estaban en uso (no hacen falta para la versión): ' + ', '.join(saltados), flush=True)
    return saltados


def _items_extras(d):
    """[(clave, campo, item, ruta, datos)] de cada texto de los extras del proyecto d (tráiler, testimonios narrados,
    frase de nuevos modelos, guion del Short)."""
    out = []
    for k, (f, lista, campos) in enumerate(EXTRAS):
        ruta = os.path.join(d, f)
        try:
            datos = json.load(open(ruta, encoding='utf-8'))
        except (OSError, ValueError):
            continue
        items = (datos.get(lista) if lista else [datos]) if isinstance(datos, dict) else None
        for i, x in enumerate(items if isinstance(items, list) else []):
            for c in campos:
                if isinstance(x, dict) and str(x.get(c) or '').strip():
                    out.append((f'X{k}_{i}_{c}', c, x, ruta, datos))
    return out


def poner_extras(d, traducidos):
    """Deja en la copia d los textos de los extras traducidos (el que no vino queda como estaba). Devuelve cuántos."""
    cambiados, n = {}, 0
    for clave, c, x, ruta, datos in _items_extras(d):
        t = str(traducidos.get(clave) or '').strip()
        if t:
            x[c] = t
            cambiados[ruta] = datos
            n += 1
    for ruta, datos in cambiados.items():
        json.dump(datos, open(ruta, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return n


def traducir_guion(guion, idioma, ajustes, extras=None):
    """Traduce los bloques del guion (en su lugar) y los textos de extras {clave: texto}. Devuelve (bloques sin traducir,
    respuesta de la IA)."""
    import ia
    nombre = idiomas.NOMBRES.get(idioma, idioma)
    textos = {b['id']: b['texto'] for b in guion['bloques'] if str(b.get('texto') or '').strip()}
    prompt = (f'Traduce al {nombre} (código {idioma}) la narración de un video tutorial de YouTube de reparación de celulares. '
              'Cada bloque se lee con una voz de IA sobre el mismo tramo del video, así que: mantén el largo parecido, el tono '
              'cercano y directo del original, los chistes adaptados con naturalidad, y los nombres de botones, programas, '
              'modelos y webs tal cual (VOL +, POWER, fastboot, USB Redirector, xiaomiunlock.com…). Escribe los números y años '
              'como se dicen en ese idioma (fifteen, twenty twenty-six) para que la voz los lea bien.\n'
              + ('Las claves que empiezan con X son textos del tráiler (título, subtítulo y su voz), de los testimonios narrados, '
                 'de la frase de nuevos modelos y del Short: tradúcelos igual, con el mismo largo.\n' if extras else '')
              + 'Responde SOLO con un objeto JSON {"L01": "traducción", …} con exactamente estas claves:\n'
              + json.dumps(dict(textos, **(extras or {})), ensure_ascii=False, indent=1))
    r = ia.extraer_json(ia.llamar(dict(ajustes, imagenes=False), prompt, []))
    if not isinstance(r, dict):
        raise SystemExit('ERROR: la IA no devolvió la traducción como se le pidió (un objeto con cada bloque). Vuelve a pulsar el botón.')
    faltan = []
    for b in guion['bloques']:
        if b['id'] in textos:
            t = str((r or {}).get(b['id']) or '').strip()
            if t:
                b['texto_original'] = b['texto']
                b['texto'] = t
            else:
                faltan.append(b['id'])
        for k in ('voz_real_s', 'voz_estimada_s'):
            b.pop(k, None)
    return faltan, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('--idioma', required=True)
    ap.add_argument('--ajustes', default=os.path.join(RAIZ, 'app', 'ajustes.json'))
    a = ap.parse_args()
    origen, idioma = os.path.abspath(a.proyecto), a.idioma.strip().lower()
    destino = origen.rstrip('\\/') + '_' + idioma.upper()
    if os.path.exists(os.path.join(destino, 'guion.json')):
        raise SystemExit(f'Ya existe la versión {os.path.basename(destino)}: ábrela desde la lista de proyectos (o bórrala para rehacerla).')
    guion = json.load(open(os.path.join(origen, 'guion.json'), encoding='utf-8'))
    os.makedirs(destino, exist_ok=True)
    marca = os.path.join(destino, '.creando_version')
    try:  # dos clics seguidos: la segunda copia chocaba con la primera
        fd = os.open(marca, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        raise SystemExit(f'Ya se está creando la versión {os.path.basename(destino)} (pulsaste dos veces): espera a que termine.')
    import atexit
    atexit.register(lambda: os.path.exists(marca) and os.remove(marca))  # al terminar (bien o con error) se puede volver a pulsar
    print(f'Copio el proyecto a {os.path.basename(destino)}…', flush=True)
    copiar(origen, destino)
    print(f'La IA traduce el guion ({len(guion["bloques"])} bloques)…', flush=True)
    extras = {clave: x[c] for clave, c, x, _, _ in _items_extras(origen)}
    faltan, r = traducir_guion(guion, idioma, json.load(open(a.ajustes, encoding='utf-8')), extras)
    if extras:
        n = poner_extras(destino, r)
        print(f'Textos del tráiler, testimonios, nuevos modelos y Short traducidos: {n} de {len(extras)}.', flush=True)
    json.dump(guion, open(os.path.join(destino, 'guion.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({'idioma': idioma, 'origen': os.path.basename(origen)}, open(os.path.join(destino, 'idioma_video.json'), 'w', encoding='utf-8'))
    et = idiomas.leer(destino)
    et['idioma'] = idioma
    idiomas.guardar(destino, et)
    if [t for t in idiomas.textos(destino) if not (et['traducciones'].get(idioma) or {}).get(t)]:  # etiquetas sin traducir
        subprocess.run([sys.executable, os.path.join(AQUI, 'traducir.py'), '--proyecto', destino, '--idioma', idioma, '--ajustes', a.ajustes])
    chars = sum(len(b['texto']) for b in guion['bloques'] if str(b.get('texto') or '').strip())
    print(json.dumps({'ok': True, 'proyecto': os.path.basename(destino), 'caracteres': chars, 'sin_traducir': faltan}, ensure_ascii=False))


if __name__ == '__main__':
    main()
