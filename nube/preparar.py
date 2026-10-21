"""NUBE: prepara un proyecto para que Claude lo haga en la nube.

Junta en para_claude/ todo lo que subiste y elegiste en la app (video grabado, material extra, imagen, música, tu idea,
referencias, pistas del tráiler, tarjetas, marcas, testimonios, tu estilo y los ajustes SIN tus claves) y parte los
archivos grandes en trozos de un tamaño que Claude acepta. Los trozos quedan en tu PC; parametros.json dice qué es cada
uno (con su huella sha256), así se vuelve a armar el archivo idéntico aunque los nombres cambien al subirlos.

Uso: python preparar.py --proyecto . --ajustes ../../app/ajustes.json --estilos ../../mis_estilos --mb 300
"""
import argparse, hashlib, json, os, shutil, time

# lo que subes o eliges tú (lo que la app genera no hace falta: se rehace allá)
ARCHIVOS = ['original.mp4', 'material.mp4', 'imagen.png', 'musica.mp3', 'idea.txt', 'referencias.json', 'guion.json',
            'etiquetas.json', 'senales.json', 'insertos.json', 'trailer.json', 'preguntas_guion.json',
            'transcripcion.json', 'transcripcion.srt', 'transcripcion.txt']
CARPETAS = ['referencias', 'pistas_trailer', 'tarjetas', 'marcas_senales', 'testimonios']
SECRETOS = ('clave', 'elevenlabs')
SALIDA = 'para_claude'


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
        for raiz, _, fs in os.walk(os.path.join(d, c)):
            for f in sorted(fs):
                ruta = os.path.join(raiz, f)
                lista.append((os.path.relpath(ruta, d).replace(os.sep, '/'), ruta))
    try:
        ajustes = json.load(open(a.ajustes, encoding='utf-8'))
    except (OSError, ValueError):
        ajustes = {}
    estilo = ajustes.get('estilo')
    if estilo:
        for f in ('perfil.md', 'perfil.json'):
            ruta = os.path.join(a.estilos, estilo, f)
            if os.path.isfile(ruta):
                lista.append((f'_estilo/{f}', ruta))
    if not any(r == 'original.mp4' for r, _ in lista):
        raise SystemExit('ERROR: falta el video grabado (original.mp4). Súbelo primero.')

    manifiesto = {'proyecto': os.path.basename(d), 'fecha': time.strftime('%Y-%m-%d %H:%M'), 'mb_por_trozo': a.mb,
                  'ajustes': {k: v for k, v in ajustes.items() if k not in SECRETOS}, 'estilo': estilo, 'archivos': []}
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
