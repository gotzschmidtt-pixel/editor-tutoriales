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
               con "en": segundos desde que empieza su bloque (lo pone el editor por pistas; sigue al bloque si se mueve)
               o "t": segundo exacto en el video, en vez de buscar la frase
Además entran las etiquetas que el autor escribió en sus capturas de «🎯 Flechas y círculos» (marcas_senales/marcas.json),
en el segundo de la captura.
tipo: web | archivo | dato | precio | pin | consejo. color: solo para "pin" (color del cable).
"""
import argparse, json, os, shutil, subprocess, sys, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
import codificar  # noqa: E402  con la tarjeta NVIDIA si la hay, si no con el procesador
sys.path.insert(0, os.path.join(RAIZ, 'capas'))
import capas  # noqa: E402  con --capa: se pega junto con flechas y tarjetas en una sola pasada
sys.path.insert(0, AQUI)
import idiomas  # noqa: E402  «🌐 Etiquetas en otro idioma»
FPS = 25


def normal(c):
    return ''.join(x for x in unicodedata.normalize('NFD', c.lower()) if unicodedata.category(x) != 'Mn')


def buscar(al, frase, original=None):
    """Segundo (relativo al bloque) en que empieza `frase` dentro de la alineación. En una versión traducida la frase
    sigue en español: si no está en la voz nueva y está en el texto `original` del bloque, va en el mismo punto relativo."""
    chars = [normal(c) for c in al['characters']]
    texto = ''.join(chars)
    # índice de carácter de texto normalizado -> índice en la alineación
    mapa = [i for i, c in enumerate(chars) for _ in c]
    pos = texto.find(normal(frase))
    if pos < 0:
        k = normal(original).find(normal(frase)) if original else -1
        if k >= 0 and al.get('character_end_times_seconds'):
            return round(k / max(1, len(normal(original))) * al['character_end_times_seconds'][-1], 2)
        return None
    return al['character_start_times_seconds'][mapa[pos]]


MONTADOS = {'1_montaje.mp4', '2_insertos.mp4', '3_voz.mp4', '4_musica.mp4', '5_etiquetas.mp4', '6_senales.mp4', '7_tarjetas.mp4'}


def segundos(s):
    """«2:56.1» o «176.1» → 176.1 (None si no se entiende)."""
    try:
        partes = [float(x.replace(',', '.')) for x in str(s).strip().split(':')]
    except ValueError:
        return None
    t = 0.0
    for x in partes:
        t = t * 60 + x
    return t if partes else None


def de_capturas(carpeta, bloques):
    """Las etiquetas que pusiste en tus capturas de «🎯 Flechas y círculos» («Presionamos VOL +, VOL − y POWER»), en el
    segundo exacto del video armado: el de la captura si es del video ya montado, o pasado del original al montaje."""
    try:
        marcas = json.load(open(os.path.join(carpeta, 'marcas_senales', 'marcas.json'), encoding='utf-8')).get('MARCAS', [])
    except (OSError, ValueError, AttributeError):
        return []
    out = []
    for m in marcas:
        texto = str(m.get('etiqueta') or '').strip() if isinstance(m, dict) else ''
        if not texto:
            continue
        s = segundos(m.get('segundo'))
        if s is None:
            print(f"AVISO: la etiqueta «{texto}» es de una captura sin segundo: captúrala desde el reproductor de la app")
            continue
        if m.get('video') in MONTADOS:
            t = s
        else:  # del original: en qué bloque se ve ese segundo y a qué velocidad va
            t = None
            for b in bloques:
                mo = b.get('montaje') or {}
                if str(mo.get('modo', '')).startswith('lento') and mo['src_inicio'] <= s <= mo['src_fin'] and b.get('inicio_min') is not None:
                    t = b['inicio_min'] + (s - mo['src_inicio']) / (mo.get('velocidad') or 1)
                    break
            if t is None:
                print(f"AVISO: el segundo {m.get('segundo')} de tu grabación no queda en el video (ese tramo se saltó); salto «{texto}»")
                continue
        out.append({'tipo': 'consejo', 'titulo': None, 'texto': texto, 't': round(t, 2), 'dur': 5.0, 'de_captura': m.get('archivo')})
    return out


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
    ap.add_argument('--capa', help='solo dibuja y deja la capa en este .json; capas/capas.py la pega junto con las demás')
    a = ap.parse_args()

    bloques = json.load(open(a.guion, encoding='utf-8'))['bloques']
    inicio = {b['id']: b['inicio_min'] for b in bloques}
    original = {b['id']: b.get('texto_original') for b in bloques}  # versión traducida: el texto en español de cada bloque
    items = de_capturas(os.path.dirname(os.path.abspath(a.guion)), bloques)
    for e in json.load(open(a.etiquetas, encoding='utf-8')):
        if e.get('t') is not None:  # con su segundo exacto en el video
            items.append({**e, 't': round(float(e['t']), 2), 'dur': e.get('dur', 3.5)})
            continue
        if e.get('en') is not None and e.get('bloque') in inicio:  # puesta a mano en el editor: segundos desde que empieza su bloque
            items.append({**e, 't': round(inicio[e['bloque']] + a.desfase + float(e['en']), 2), 'dur': e.get('dur', 3.5)})
            continue
        f_al = os.path.join(a.voz, str(e.get('bloque')) + '.align.json')
        if e.get('bloque') not in inicio or not os.path.exists(f_al):
            print(f"AVISO: el bloque {e.get('bloque')} ya no está en el guion, salto «{e.get('texto')}»")
            continue
        al = json.load(open(f_al, encoding='utf-8'))
        t = buscar(al, e['frase'], original.get(e['bloque']))
        if t is None:
            print(f"AVISO: no encontré «{e['frase']}» en {e['bloque']}, la salto")
            continue
        items.append({**e, 't': round(inicio[e['bloque']] + a.desfase + t, 2), 'dur': e.get('dur', 3.5)})

    items, idioma, faltan = idiomas.aplicar(items, os.path.dirname(os.path.abspath(a.guion)))  # «🌐 Etiquetas en otro idioma»
    if idioma != idiomas.ORIGINAL:
        print(f"Etiquetas en {idiomas.NOMBRES.get(idioma, idioma)}" + (f" ({faltan} texto(s) sin traducir van en el original)" if faltan else ''))
    grupos = agrupar(items)
    if not grupos:  # ninguna etiqueta cabe en este guion: el video sigue igual, sin fallar
        print('AVISO: ninguna etiqueta coincide con el guion actual; el video sigue sin etiquetas. '
              'Pulsa «Escribir con IA» en etiquetas para hacerlas de nuevo con este guion.')
        if a.capa:
            capas.guardar(a.capa, [])
        else:
            shutil.copyfile(a.video, a.salida)
        json.dump([], open(os.path.splitext(a.salida)[0] + '.etiquetas_tiempos.json', 'w', encoding='utf-8'))
        return
    tmp = codificar.temporal('etiquetas')
    ins, filtros, ultimo, piezas = ['-i', a.video], [], '0:v', []
    for k, g in enumerate(grupos, 1):
        total = round(g['fin'] - g['ini'], 2)
        lista = [{'tipo': i['tipo'], 'titulo': i.get('titulo'), 'texto': i['texto'], 'color': i.get('color'),
                  'at': round(i['t'] - g['ini'], 2)} for i in g['items']]
        carpeta = os.path.join(tmp, f'g{k:02d}')
        r = subprocess.run(['node', os.path.join(AQUI, 'render_frames.js'), carpeta, str(total), json.dumps(lista)],
                           cwd=RAIZ, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=codificar.env_temporal(os.environ, os.path.join(tmp, 'node_tmp')))
        if r.returncode != 0:  # se muestra lo que dijo Node, no solo «exit status 1»
            detalle = ' '.join((r.stderr or r.stdout).split())[-600:]
            if 'playwright' in detalle.lower() and ('cannot find' in detalle.lower() or 'executable' in detalle.lower()):
                detalle += ' → Falta Playwright: corre instalar.bat (o «npm install» y «npx playwright install chromium» en la carpeta del editor).'
            raise SystemExit(f'ERROR: no pude dibujar las etiquetas con Node: {detalle}')
        piezas.append({'args': ['-framerate', str(FPS), '-i', os.path.join(carpeta, 'f_%04d.png')],
                       'pre': f"setpts=PTS+{g['ini']}/TB", 'overlay': '0:0:eof_action=pass'})
        ins += piezas[-1]['args']
        filtros.append(f"[{k}:v]setpts=PTS+{g['ini']}/TB[e{k}];[{ultimo}][e{k}]overlay=0:0:eof_action=pass[v{k}]")
        ultimo = f'v{k}'
        print(f"{g['ini']:7.2f}s  " + ' + '.join(i['texto'] for i in g['items']))
    tiempos = os.path.splitext(a.salida)[0] + '.etiquetas_tiempos.json'
    if a.capa:  # se pega después junto con flechas y tarjetas: una sola codificación
        capas.guardar(a.capa, piezas, borrar=tmp, crf=20)
        json.dump(items, open(tiempos, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return
    codificar.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins +
                   ['-filter_complex', ';'.join(filtros), '-map', f'[{ultimo}]', '-map', '0:a?',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'copy', a.salida],
                   check=True)
    shutil.rmtree(tmp)
    json.dump(items, open(tiempos, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
