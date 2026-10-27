"""Pega en UNA sola pasada de ffmpeg las capas de etiquetas, flechas y círculos, y tarjetas.

Antes cada extra volvía a codificar el video entero: tres codificaciones (más lento y cada una pierde un poco de
calidad). Ahora etiquetas.py, senales.py y tarjetas.py, con --capa, solo dibujan lo suyo y dejan la lista de lo que hay
que pegar en un .json; este programa las pega todas a la vez sobre el video base.

Uso (la app lo llama solo):
  python capas.py --video 4_musica.mp4 --carpeta .capas --orden etiquetas:5_etiquetas.mp4,senales:6_senales.mp4,tarjetas:7_tarjetas.mp4

Capa (.capas/<nombre>.json): {"entradas": [{"args": ["-i", "x.mov"], "pre": "setpts=PTS+3/TB", "overlay": "0:0:eof_action=pass"}],
                             "borrar": "carpeta temporal de esa capa", "crf": 20}
Si un extra falló, su .json no está y el resto se pega igual. El video sale con el nombre del último extra que se
pegó (como antes) y capas_hechas.json dice cuáles lleva.
"""
import argparse, json, os, shutil, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'codificar'))
import codificar  # noqa: E402  con la tarjeta NVIDIA si la hay, si no con el procesador


def guardar(archivo, entradas, borrar=None, crf=20):
    """Lo usa cada extra con --capa: deja lo que hay que pegar en vez de codificar el video."""
    os.makedirs(os.path.dirname(os.path.abspath(archivo)), exist_ok=True)
    json.dump({'entradas': entradas, 'borrar': borrar and os.path.abspath(borrar), 'crf': crf},
              open(archivo, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def pegar(video, capas, salida):
    """capas: lista de dicts (ya leídos). Una sola codificación con todas las entradas."""
    ins, filtros, ultimo, k = ['-i', video], [], '0:v', 0
    for c in capas:
        for e in c['entradas']:
            k += 1
            ins += e['args']
            filtros.append(f"[{k}:v]{e.get('pre') or 'null'}[c{k}];[{ultimo}][c{k}]overlay={e['overlay']}[v{k}]")
            ultimo = f'v{k}'
    crf = min(c.get('crf', 20) for c in capas)
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins +
                  ['-filter_complex', ';'.join(filtros), '-map', f'[{ultimo}]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'medium',
                   '-crf', str(crf), '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', salida], check=True)
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True, help='el video sin extras (4_musica.mp4 o 3_voz.mp4)')
    ap.add_argument('--carpeta', default='.capas')
    ap.add_argument('--orden', required=True, help='nombre:salida,… en el orden en que se apilan')
    a = ap.parse_args()
    orden = [x.split(':', 1) for x in a.orden.split(',') if ':' in x]
    hechas, capas, salida = [], [], None
    for nombre, archivo in orden:
        f = os.path.join(a.carpeta, nombre + '.json')
        if not os.path.exists(f):
            continue
        c = json.load(open(f, encoding='utf-8'))
        hechas.append(nombre)
        if c['entradas']:
            capas.append(c)
        salida = archivo
    if not hechas:
        raise SystemExit('ERROR: ningún extra dejó su capa (todos fallaron o no tenían nada que poner).')
    if capas:
        n = pegar(a.video, capas, salida)
        print(f'✓ {n} piezas de {", ".join(hechas)} pegadas en una sola pasada -> {salida}', flush=True)
    else:
        shutil.copyfile(a.video, salida)
        print(f'· {", ".join(hechas)} no tenían nada que poner; el video sigue igual -> {salida}', flush=True)
    json.dump(hechas, open('capas_hechas.json', 'w', encoding='utf-8'))
    for c in capas:
        if c.get('borrar'):
            shutil.rmtree(c['borrar'], ignore_errors=True)
    shutil.rmtree(a.carpeta, ignore_errors=True)


if __name__ == '__main__':
    main()
