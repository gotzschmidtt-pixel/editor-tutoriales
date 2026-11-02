"""NUBE: prepara un proyecto para que Claude lo haga en la nube.

Junta en para_claude/ todo lo que subiste y elegiste en la app (video grabado, material extra, imagen, música, tu idea,
referencias, pistas del tráiler, tarjetas, marcas, testimonios, tu estilo, lo aprendido de cada marca y los ajustes SIN
ninguna clave) y parte los archivos grandes en trozos de un tamaño que Claude acepta. Los trozos quedan en tu PC;
parametros.json dice qué es cada uno (con su huella sha256), así se vuelve a armar el archivo idéntico aunque los nombres cambien al subirlos.

Uso: python preparar.py --proyecto . --ajustes ../../app/ajustes.json --estilos ../../mis_estilos --mb 300
"""
import argparse, hashlib, json, os, re, shutil, time

# lo que subes o eliges tú (lo que la app genera no hace falta: se rehace allá)
ARCHIVOS = ['original.mp4', 'material.mp4', 'imagen.png', 'musica.mp3', 'idea.txt', 'referencias.json', 'guion.json',
            'etiquetas.json', 'senales.json', 'insertos.json', 'trailer.json', 'preguntas_guion.json',
            'transcripcion.json', 'transcripcion.srt', 'transcripcion.txt',
            # lo que marcaste en la app: cortes importantes, señales, subtítulos e idiomas (Claude lo respeta en la nube)
            'cortes_importantes.json', 'para_claude_marcas.json', 'para_claude_marcas.txt', 'subtitulos.json',
            'etiquetas_idiomas.json', 'idioma_video.json',
            # lo que la app ya miró del video: mapa de escenas, guion para leer y mejoras (así Claude no lo rehace)
            'mapa_video.json', 'guion_para_leer.md', 'mejoras_guion.txt']
CARPETAS = ['referencias', 'pistas_trailer', 'tarjetas', 'marcas_senales', 'testimonios', 'nuevos_modelos',
            'hojas_2s', 'ia_capturas', 'acciones']  # hojas de contacto, capturas de la IA y capturas de cada acción
SECRETOS = ('clave', 'key', 'token', 'secret', 'password', 'contrase', 'elevenlabs', 'pin_hash', 'tema')  # nunca viajan, estén donde estén
NO_VIAJAN = ('celular', 'avisos', 'youtube')  # PIN del celular (sal y huella), tema de avisos y cuenta de YouTube: se quedan en la PC
SALIDA = 'para_claude'
# las carpetas con lista (como GRUPOS en app.py): un archivo que quitaste de la lista hace menos de 10 minutos sigue en la
# carpeta (app.py, a_papelera, no toca lo recién subido), pero ya no es del video y no viaja
LISTAS = {'pistas_trailer': ('pistas.json', ('ANTES', 'DURANTE', 'DESPUES')), 'tarjetas': ('tarjetas.json', ('COMENTARIOS', 'WHATSAPP')),
          'testimonios': ('testimonios.json', ('TESTIMONIOS',)), 'nuevos_modelos': ('modelos.json', ('MODELOS',)),
          'marcas_senales': ('marcas.json', ('MARCAS',))}
RESPALDOS = ('_sin_zoom', '_sin_color', '_sin_limpiar')  # el audio o la imagen de antes de una pista (mejoras.RESPALDOS)


def fuera_de_la_lista(d, c):
    """Los archivos sueltos de la carpeta c que su lista ya no usa. Mismo criterio que la app al guardar la lista (app.py,
    /api/pistas): la pista, su transcripción, la narración guardada de un testimonio y el audio o la imagen de antes quedan."""
    if c not in LISTAS or not os.path.isdir(os.path.join(d, c)):
        return set()
    nombre, apartados = LISTAS[c]
    try:
        with open(os.path.join(d, c, nombre), encoding='utf-8') as fh:
            datos = json.load(fh)
    except FileNotFoundError:
        datos = {}  # sin lista (quitaste todo): la app ya no usa nada de la carpeta
    except (OSError, ValueError):
        return set()  # no se pudo leer: viaja todo, como antes
    if not isinstance(datos, dict):
        return set()
    usados = {os.path.basename(str(p.get('archivo') or '')) for x in apartados for p in datos.get(x) or [] if isinstance(p, dict)}
    narr = {'narr_' + re.sub(r'\W+', '', os.path.splitext(u)[0]) for u in usados}
    fuera = set()
    for f in os.listdir(os.path.join(d, c)):
        base = f[:-4] if f.endswith('.txt') else f
        raiz, ext = os.path.splitext(f)
        de = next((raiz[:-len(s)] + ext for s in RESPALDOS if raiz.endswith(s)), None)
        if f != nombre and base not in usados and raiz not in narr and de not in usados:
            fuera.add(f)
    return fuera


def sin_secretos(x):
    """Los ajustes sin ninguna clave, también las de adentro (ias_guion → deepseek → clave)."""
    if isinstance(x, dict):
        return {k: sin_secretos(v) for k, v in x.items() if not any(s in str(k).lower() for s in SECRETOS)}
    if isinstance(x, list):
        return [sin_secretos(v) for v in x]
    return x


def huella(f):
    h = hashlib.sha256()
    with open(f, 'rb') as fh:
        for trozo in iter(lambda: fh.read(1 << 20), b''):
            h.update(trozo)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--ajustes', required=True)
    ap.add_argument('--estilos', required=True)
    ap.add_argument('--conocimientos', default='', help='mis_conocimientos: preguntas, ideas y mejoras de cada marca')
    ap.add_argument('--mb', type=float, default=300, help='tamaño máximo de cada trozo, en MB')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    limite = int(max(5, a.mb) * 1024 * 1024)
    out = os.path.join(d, SALIDA)
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)

    lista = [(f, os.path.join(d, f)) for f in ARCHIVOS if os.path.isfile(os.path.join(d, f))]
    for c in CARPETAS:
        fuera = fuera_de_la_lista(d, c)
        for raiz, subs, fs in os.walk(os.path.join(d, c)):
            subs[:] = [x for x in subs if x != '_papelera']  # lo que quitaste de la lista (app.py, a_papelera) no viaja
            for f in sorted(fs):
                if f in fuera and raiz == os.path.join(d, c):  # quitado de la lista hace un momento: tampoco viaja
                    continue
                ruta = os.path.join(raiz, f)
                lista.append((os.path.relpath(ruta, d).replace(os.sep, '/'), ruta))
    try:
        ajustes = json.load(open(a.ajustes, encoding='utf-8'))
    except (OSError, ValueError):
        ajustes = {}
    if not isinstance(ajustes, dict):
        ajustes = {}
    ajustes = {k: v for k, v in ajustes.items() if k not in NO_VIAJAN}
    estilo = ajustes.get('estilo')
    if estilo:
        for f in ('perfil.md', 'perfil.json'):
            ruta = os.path.join(a.estilos, estilo, f)
            if os.path.isfile(ruta):
                lista.append((f'_estilo/{f}', ruta))
    if a.conocimientos:  # lo que aprendimos del canal y de cada marca (MOTOROLA.md…): solo texto
        for raiz, _, fs in os.walk(a.conocimientos):
            for f in sorted(fs):
                if f.endswith('.md'):
                    ruta = os.path.join(raiz, f)
                    lista.append(('_conocimiento/' + os.path.relpath(ruta, a.conocimientos).replace(os.sep, '/'), ruta))
    if not any(r == 'original.mp4' for r, _ in lista):
        raise SystemExit('ERROR: falta el video grabado (original.mp4). Súbelo primero.')

    manifiesto = {'proyecto': os.path.basename(d), 'fecha': time.strftime('%Y-%m-%d %H:%M'), 'mb_por_trozo': a.mb,
                  'ajustes': sin_secretos(ajustes), 'estilo': estilo, 'archivos': []}
    n, total = 0, 0
    for rel, ruta in lista:
        tam = os.path.getsize(ruta)
        partes = []
        cuantos = max(1, -(-tam // limite))
        base = rel.replace('/', '__')
        with open(ruta, 'rb') as fh:
            for k in range(cuantos):
                n += 1
                nombre = f'{n:03d}_{base}' + (f'.parte{k + 1}de{cuantos}' if cuantos > 1 else '')
                with open(os.path.join(out, nombre), 'wb') as dest:
                    resto = min(limite, tam - k * limite)
                    while resto > 0:
                        trozo = fh.read(min(1 << 20, resto))
                        dest.write(trozo)
                        resto -= len(trozo)
                partes.append({'nombre': nombre, 'tam': os.path.getsize(os.path.join(out, nombre)),
                               'sha256': huella(os.path.join(out, nombre))})
        manifiesto['archivos'].append({'ruta': rel, 'tam': tam, 'sha256': huella(ruta), 'partes': partes})
        total += tam
        if cuantos > 1:
            print(f'· {rel}: {tam / 1e6:.0f} MB en {cuantos} trozos', flush=True)
    json.dump(manifiesto, open(os.path.join(out, 'parametros.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Listo {SALIDA}/: {len(lista)} archivos ({total / 1e6:.0f} MB) en {n} trozos de hasta {a.mb:g} MB, más parametros.json.')
    print(f'Ahora escríbele a Claude en el chat: «hazlo desde la nube: {manifiesto["proyecto"]}».')


if __name__ == '__main__':
    main()
