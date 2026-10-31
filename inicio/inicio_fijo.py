"""«Inicio fijo»: un inicio hecho aparte (por ejemplo, el nuevo inicio del HONOR 8 LITE, con su precio difuminado) que se
vuelve a poner solo cada vez que se arma el video final. Antes se ponía a mano encima de FINAL.mp4, y al rehacer el
final (31/10/2026, al poner los logos) se perdió: ahora el paso «Video final sin tráiler» lo aplica al terminar.

El proyecto lo activa con inicio_fijo.json:  {"video": "prueba_inicio/inicio_con_logos.mp4", "hasta": 79.34}
- Del segundo 0 a «hasta», la imagen es la de ese video; desde ahí, la del video armado. El audio (voz y música) es
  siempre el del video armado, sin tocar, así la voz no se corre.
- Las etiquetas que salen en ese tramo quedarían tapadas por el inicio: se vuelven a dibujar encima, con la misma
  plantilla y el mismo lugar que el armado (etiquetas/plantilla.html, arriba a la derecha). Los círculos y flechas de ese
  tramo no se redibujan (el inicio ya trae lo suyo).

Uso (desde la carpeta del proyecto): python inicio_fijo.py --entrada FINAL.mp4 --salida FINAL.mp4
Sin inicio_fijo.json no hace nada (deja la entrada como salida).
"""
import argparse, json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'etiquetas'))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))


def ff(*a):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *a], check=True)


def duracion(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True, check=True).stdout)


def etiquetas_del_tramo(hasta):
    """Las etiquetas que salen antes de «hasta», con su segundo en el video (el mismo que muestra la vista previa)."""
    try:
        lista = json.load(open(os.path.join('vista_extras', 'lista.json'), encoding='utf-8'))
        datos = json.load(open('etiquetas.json', encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return [(z['t'], datos[z['idx']]) for z in lista
            if z.get('clase') == 'etiqueta' and z.get('t') is not None and not z.get('aviso') and z['t'] < hasta and z['idx'] < len(datos)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entrada', required=True)
    ap.add_argument('--salida', required=True)
    a = ap.parse_args()
    if not os.path.exists('inicio_fijo.json'):
        if os.path.abspath(a.entrada) != os.path.abspath(a.salida):
            shutil.copyfile(a.entrada, a.salida)
        return print('Sin inicio fijo (no hay inicio_fijo.json): el video queda como está.')
    conf = json.load(open('inicio_fijo.json', encoding='utf-8'))
    inicio, hasta = conf['video'], float(conf['hasta'])
    if not os.path.exists(inicio):
        raise SystemExit(f'ERROR: inicio_fijo.json pide {inicio} y no está en el proyecto.')
    if duracion(inicio) < hasta - 0.05:
        raise SystemExit(f'ERROR: {inicio} dura {duracion(inicio):.2f} s y tiene que durar al menos {hasta} s (si no, la voz se corre).')
    import etiquetas as et
    tmp = tempfile.mkdtemp(prefix='.inicio_tmp_', dir=os.getcwd())
    try:
        entradas, filtros, ult = ['-i', inicio, '-i', a.entrada], [f'[0:v]trim=0:{hasta},setpts=PTS-STARTPTS,fps=25[a]',
                                 f'[1:v]trim={hasta},setpts=PTS-STARTPTS,fps=25[b]', '[a][b]concat=n=2:v=1:a=0[v0]'], '[v0]'
        for k, (t, e) in enumerate(etiquetas_del_tramo(hasta), 1):
            dur = float(e.get('dur') or 4)
            ancho = 1920 if len(str(e.get('texto') or '')) > 38 else et.ANCHO_ZONA
            x, y = 1920 - ancho, 0
            item = {'tipo': e.get('tipo') or 'consejo', 'titulo': e.get('titulo'), 'texto': str(e.get('texto') or ''),
                    'color': e.get('color'), 'at': 0, 'placa': et.placa_gpt(e.get('tipo') or 'consejo')}
            carpeta = os.path.join(tmp, f'e{k}')
            r = subprocess.run(['node', os.path.join(RAIZ, 'etiquetas', 'render_frames.js'), carpeta, str(dur), json.dumps([item]),
                                'arriba', f'{x},{y},{ancho},{et.ALTO_ZONA}'], cwd=RAIZ, capture_output=True, text=True,
                               encoding='utf-8', errors='replace')
            if r.returncode != 0:
                raise SystemExit('ERROR: no pude dibujar la etiqueta con Node: ' + ' '.join((r.stderr or r.stdout).split())[-400:])
            entradas += ['-framerate', '25', '-i', os.path.join(carpeta, 'f_%04d.png')]
            idx = sum(1 for z in entradas if z == '-i') - 1
            filtros.append(f'[{idx}:v]setpts=PTS+{t}/TB[e{k}];{ult}[e{k}]overlay={x}:{y}:eof_action=pass[v{k}]')
            ult = f'[v{k}]'
            print(f'{t:7.2f}s  etiqueta «{e.get("texto")}» redibujada encima del inicio')
        salida_tmp = os.path.join(tmp, 'salida.mp4')
        ff(*entradas, '-filter_complex', ';'.join(filtros), '-map', ult, '-map', '1:a', '-c:v', 'libx264', '-crf', '18',
           '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', salida_tmp)
        d_in, d_out = duracion(a.entrada), duracion(salida_tmp)
        if abs(d_in - d_out) > 0.2:
            raise SystemExit(f'ERROR: el video con el inicio dura {d_out:.2f} s y el armado {d_in:.2f} s: no lo guardo.')
        os.replace(salida_tmp, a.salida)
        print(f'Inicio fijo puesto: {inicio} de 0:00 a {int(hasta // 60)}:{hasta % 60:05.2f} -> {a.salida}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
