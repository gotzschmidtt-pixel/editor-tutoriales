"""NUBE: vuelve a armar en la nube el proyecto que preparó preparar.py.

Busca cada trozo en --origen por su nombre o, si al subirlo le cambiaron el nombre, por su huella sha256; une los trozos
y comprueba que cada archivo quede idéntico al de tu PC. Los ajustes (sin claves) quedan en ajustes_nube.json.

Uso: python rearmar.py --origen carpeta_con_los_trozos --destino mis_proyectos/NOMBRE
"""
import argparse, hashlib, json, os

from preparar import huella


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--origen', required=True, nargs='+', help='carpetas donde están los trozos y parametros.json')
    ap.add_argument('--destino', required=True)
    a = ap.parse_args()
    todos = [os.path.join(r, f) for o in a.origen for r, _, fs in os.walk(o) for f in fs]
    man = next((f for f in todos if os.path.basename(f) == 'parametros.json'), None)
    if not man:
        raise SystemExit('ERROR: no encuentro parametros.json entre los archivos.')
    m = json.load(open(man, encoding='utf-8'))
    por_nombre = {os.path.basename(f): f for f in todos}
    por_tam = {}
    for f in todos:
        por_tam.setdefault(os.path.getsize(f), []).append(f)
    cache = {}

    def buscar(p):
        f = por_nombre.get(p['nombre'])
        if f and os.path.getsize(f) == p['tam']:
            return f
        for f in por_tam.get(p['tam'], []):  # subido con otro nombre: se reconoce por su huella
            if f not in cache:
                cache[f] = huella(f)
            if cache[f] == p['sha256']:
                return f
        return None

    os.makedirs(a.destino, exist_ok=True)
    faltan = []
    for x in m['archivos']:
        partes = [buscar(p) for p in x['partes']]
        if None in partes:
            faltan += [p['nombre'] for p, f in zip(x['partes'], partes) if f is None]
            continue
        dest = os.path.join(a.destino, *x['ruta'].split('/'))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        h = hashlib.sha256()
        with open(dest, 'wb') as out:
            for f in partes:
                with open(f, 'rb') as fh:
                    for trozo in iter(lambda: fh.read(1 << 20), b''):
                        h.update(trozo); out.write(trozo)
        if h.hexdigest() != x['sha256']:
            raise SystemExit(f'ERROR: {x["ruta"]} no quedó idéntico al de tu PC.')
        print(f'✓ {x["ruta"]} ({x["tam"] / 1e6:.1f} MB)')
    json.dump({**m['ajustes'], 'estilo': m.get('estilo')}, open(os.path.join(a.destino, 'ajustes_nube.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    if faltan:
        raise SystemExit(f'ERROR: faltan {len(faltan)} trozos: ' + ', '.join(faltan))
    print(f'Proyecto «{m["proyecto"]}» armado en {a.destino}')


if __name__ == '__main__':
    main()
