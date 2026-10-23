"""Etiquetas animadas sincronizadas con la voz.

Busca en los tiempos por carácter de ElevenLabs (archivos <bloque>.align.json) el momento
exacto en que la voz dice cada frase disparadora, renderiza una etiqueta animada
(plantilla.html) y la superpone al video con ffmpeg.

Uso:
  python3 etiquetas.py --guion guion.json --voz carpeta_voz --etiquetas etiquetas.json \
      --video entrada.mp4 --salida salida.mp4 [--desfase 0.3]

guion.json: {"bloques": [{"id": "L15", "inicio_min": 296.7, ...}]}  (cuándo arranca cada bloque de voz)
etiquetas.json: [{"bloque": "L15", "frase": "gsmprime", "tipo": "web", "titulo": "Descarga aquí",
                  "texto": "gsmprime.co", "color": null, "dur": 3.5}]
               con "t": segundo exacto en el video (lo pone el editor por pistas) en vez de buscar la frase
tipo: web | archivo | dato | precio | pin | consejo. color: solo para "pin" (color del cable).
"""
import argparse, json, os, shutil, subprocess, tempfile, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
FPS = 25


def normal(c):
    return ''.join(x for x in unicodedata.normalize('NFD', c.lower()) if unicodedata.category(x) != 'Mn')


def buscar(al, frase):
    """Segundo (relativo al bloque) en que empieza `frase` dentro de la alineación."""
    chars = [normal(c) for c in al['characters']]
    texto = ''.join(chars)
    # índice de carácter de texto normalizado -> índice en la alineación
    mapa = [i for i, c in enumerate(chars) for _ in c]
    pos = texto.find(normal(frase))
    if pos < 0:
        return None
    return al['character_start_times_seconds'][mapa[pos]]


def agrupar(items, max_pila=3):
    """Junta en una misma pila las etiquetas que se solapan en el tiempo."""
    grupos = []
    for it in sorted(items, key=lambda x: x['t']):
        g = grupos[-1] if grupos else None
        if g and it['t'] < g['fin'] - 0.8 and len(g['items']) < max_pila:
            g['items'].append(it)
            g['fin'] = max(g['fin'], it['t'] + it['dur'])
        else:
            grupos.append({'ini': it['t'], 'fin': it['t'] + it['dur'], 'items': [it]})
    return grupos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--guion', required=True)
    ap.add_argument('--voz', required=True)
    ap.add_argument('--etiquetas', required=True)
    ap.add_argument('--video', required=True)
    ap.add_argument('--salida', required=True)
    ap.add_argument('--desfase', type=float, default=0.3, help='retraso con que se colocó cada bloque de voz')
    a = ap.parse_args()

    inicio = {b['id']: b['inicio_min'] for b in json.load(open(a.guion, encoding='utf-8'))['bloques']}
    items = []
    for e in json.load(open(a.etiquetas, encoding='utf-8')):
        if e.get('t') is not None:  # movida a mano en el editor por pistas: ya trae su segundo en el video
            items.append({**e, 't': round(float(e['t']), 2), 'dur': e.get('dur', 3.5)})
            continue
        f_al = os.path.join(a.voz, str(e.get('bloque')) + '.align.json')
        if e.get('bloque') not in inicio or not os.path.exists(f_al):
            print(f"AVISO: el bloque {e.get('bloque')} ya no está en el guion, salto «{e.get('texto')}»")
            continue
        al = json.load(open(f_al, encoding='utf-8'))
        t = buscar(al, e['frase'])
        if t is None:
            print(f"AVISO: no encontré «{e['frase']}» en {e['bloque']}, la salto")
            continue
        items.append({**e, 't': round(inicio[e['bloque']] + a.desfase + t, 2), 'dur': e.get('dur', 3.5)})

    grupos = agrupar(items)
    if not grupos:  # ninguna etiqueta cabe en este guion: el video sigue igual, sin fallar
        print('AVISO: ninguna etiqueta coincide con el guion actual; el video sigue sin etiquetas. '
              'Pulsa «Escribir con IA» en etiquetas para hacerlas de nuevo con este guion.')
        shutil.copyfile(a.video, a.salida)
        json.dump([], open(os.path.splitext(a.salida)[0] + '.etiquetas_tiempos.json', 'w', encoding='utf-8'))
        return
    tmp = tempfile.mkdtemp(prefix='etiquetas_')
    ins, filtros, ultimo = ['-i', a.video], [], '0:v'
    for k, g in enumerate(grupos, 1):
        total = round(g['fin'] - g['ini'], 2)
        lista = [{'tipo': i['tipo'], 'titulo': i.get('titulo'), 'texto': i['texto'], 'color': i.get('color'),
                  'at': round(i['t'] - g['ini'], 2)} for i in g['items']]
        carpeta = os.path.join(tmp, f'g{k:02d}')
        r = subprocess.run(['node', os.path.join(AQUI, 'render_frames.js'), carpeta, str(total), json.dumps(lista)],
                           cwd=RAIZ, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0:  # se muestra lo que dijo Node, no solo «exit status 1»
            detalle = ' '.join((r.stderr or r.stdout).split())[-600:]
            if 'playwright' in detalle.lower() and ('cannot find' in detalle.lower() or 'executable' in detalle.lower()):
                detalle += ' → Falta Playwright: corre instalar.bat (o «npm install» y «npx playwright install chromium» en la carpeta del editor).'
            raise SystemExit(f'ERROR: no pude dibujar las etiquetas con Node: {detalle}')
        ins += ['-framerate', str(FPS), '-i', os.path.join(carpeta, 'f_%04d.png')]
        filtros.append(f"[{k}:v]setpts=PTS+{g['ini']}/TB[e{k}];[{ultimo}][e{k}]overlay=0:0:eof_action=pass[v{k}]")
        ultimo = f'v{k}'
        print(f"{g['ini']:7.2f}s  " + ' + '.join(i['texto'] for i in g['items']))
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins +
                   ['-filter_complex', ';'.join(filtros), '-map', f'[{ultimo}]', '-map', '0:a?',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'copy', a.salida],
                   check=True)
    shutil.rmtree(tmp)
    json.dump(items, open(os.path.splitext(a.salida)[0] + '.etiquetas_tiempos.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
