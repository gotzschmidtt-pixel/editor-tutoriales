"""«🎧 Pista de audio en inglés» para YouTube (fabian, 03/11/2026: «¿Pistas de audio en inglés? SÍ, PERO CON MI
CONFIRMACIÓN»). YouTube deja poner en el MISMO video una pista de audio en otro idioma: quien tiene YouTube en inglés lo
escucha en inglés. La API de YouTube no sube pistas de audio: la subes tú en YouTube Studio → tu video → Idiomas →
Agregar idioma → Audio. La app solo prepara el mp3 y te avisa.

Arma PISTA_AUDIO_EN.mp3 con el largo exacto de FINAL.mp4 (el video en español): la voz traducida de cada bloque (la de la
versión NOMBRE_EN, voz Brian) en el segundo en que ese bloque se empieza a decir en FINAL.mp4, y tu música debajo, que
baja sola cuando habla la voz (como en el video). Si una voz no cabe en su lugar va un poco más rápida (hasta ×1,25); si
ni así cabe, se corta con un fundido y se avisa.

NO gasta ni sube nada: no genera voz (la de la versión se hace allá, con tu SI) y no llama a YouTube. Si falta la voz de
algún bloque, se para y dice cuáles y cuántos créditos costarían; tú decides si la generas en la versión.

    python voz/pista_idioma.py --proyecto mis_proyectos/NOMBRE --idioma en
"""
import argparse, json, os, subprocess, sys

VEL_MAX = 1.25        # lo más rápido que va una voz que no cabe en su lugar (más se nota apurada)
AIRE = 0.15           # silencio mínimo antes de la voz siguiente
VOLUMEN_MUSICA = 0.22  # como musica.py: ≈ 10 dB bajo la voz


class FaltaVoz(Exception):
    """Falta la voz traducida de algunos bloques: se genera en la versión (gasta ElevenLabs, con el SI de fabian)."""
    def __init__(self, bloques, caracteres, version):
        self.bloques, self.caracteres = bloques, caracteres
        n = f'{caracteres:,}'.replace(',', '.')
        super().__init__(f'Falta la voz traducida de {len(bloques)} bloque(s) ({", ".join(bloques[:12])}'
                         f'{"…" if len(bloques) > 12 else ""}): unos {n} créditos de ElevenLabs. '
                         f'Genérala en «{version}» con «▶ Hacer todo» (te pide tu SI antes de gastar) y vuelve a pulsar. '
                         'Esto no la genera ni gasta nada.')


SIN_VENTANA = {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)} if sys.platform == 'win32' else {}  # sin ventanas negras


def _filtro_archivo(script):
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'codificar'))
        import codificar
        return codificar.filtro_desde_archivo(script)
    except ImportError:
        return ['-filter_complex_script', script]


def duracion(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                       capture_output=True, text=True, **SIN_VENTANA)
    return float(r.stdout.strip() or 0)


def version_de(d, idioma):
    return os.path.abspath(d).rstrip('\\/') + '_' + idioma.upper()


def plan(d, idioma, inicios, total):
    """[(bloque, mp3, segundo, tempo, cortar_en o None)] y avisos. inicios: {bloque: segundo de FINAL.mp4 en que empieza
    su voz}. Lanza FaltaVoz si a la versión le falta la voz de algún bloque."""
    ver = version_de(d, idioma)
    try:
        bloques = json.load(open(os.path.join(ver, 'guion.json'), encoding='utf-8'))['bloques']
    except (OSError, ValueError, KeyError):
        raise SystemExit(f'No encuentro la versión {os.path.basename(ver)}: créala primero con «🌐 Crear la versión».')
    textos = {b['id']: b['texto'] for b in bloques if str(b.get('texto') or '').strip()}
    orden = sorted((i for i in inicios if i in textos), key=lambda i: float(inicios[i]))
    faltan = [i for i in orden if not os.path.isfile(os.path.join(ver, 'voz', f'{i}.mp3'))]
    if faltan:
        raise FaltaVoz(faltan, sum(len(textos[i]) for i in faltan), os.path.basename(ver))
    avisos = []
    sin_lugar = [i for i in textos if i not in inicios]
    if sin_lugar:
        avisos.append('No encontré en FINAL.mp4 dónde empiezan estos bloques y quedan sin voz: ' + ', '.join(sin_lugar))
    filas = []
    for k, i in enumerate(orden):
        t0 = max(0.0, float(inicios[i]))
        t1 = float(inicios[orden[k + 1]]) if k + 1 < len(orden) else total
        lugar = max(0.5, t1 - t0 - AIRE)
        mp3 = os.path.join(ver, 'voz', f'{i}.mp3')
        largo = duracion(mp3)
        tempo = round(min(VEL_MAX, largo / lugar), 3) if largo > lugar else 1.0
        cortar = round(lugar, 2) if largo / tempo > lugar + 0.05 else None
        filas.append((i, mp3, round(t0, 3), tempo, cortar))
    return filas, avisos


def armar(d, idioma, inicios, total, musica=None, volumen=VOLUMEN_MUSICA, salida=None):
    """Deja la pista en d/PISTA_AUDIO_<IDIOMA>.mp3 (o `salida`) y devuelve {'archivo', 'duracion', 'bloques', 'acelerados',
    'cortados', 'avisos'}. No genera voz ni sube nada."""
    filas, avisos = plan(d, idioma, inicios, total)
    if not filas:
        raise SystemExit('No encontré en FINAL.mp4 dónde empieza cada bloque (faltan los subtítulos del video final).' if not inicios
                         else 'La versión no tiene bloques con voz para la pista.')
    salida = salida or os.path.join(d, f'PISTA_AUDIO_{idioma.upper()}.mp3')
    ins, flt, labs = [], [], []
    for k, (i, mp3, t0, tempo, cortar) in enumerate(filas):
        ins += ['-i', mp3]
        f = f'[{k}:a]aresample=44100,aformat=channel_layouts=stereo' + (f',atempo={tempo}' if tempo != 1 else '')
        if cortar:
            f += f',atrim=0:{cortar + 0.1:.2f},afade=t=out:st={max(0, cortar - 0.2):.2f}:d=0.3'
        flt.append(f + f',adelay={int(t0 * 1000)}:all=1[v{k}]')
        labs.append(f'[v{k}]')
    flt.append(''.join(labs) + f'amix=inputs={len(labs)}:normalize=0,apad=whole_dur={total:.3f}[voz]')
    if musica and os.path.isfile(musica):
        ins += ['-stream_loop', '-1', '-i', musica]
        n = len(filas)
        flt.append(f'[{n}:a]aresample=44100,aformat=channel_layouts=stereo,atrim=0:{total:.3f},afade=t=in:d=2,'
                   f'afade=t=out:st={max(0, total - 6):.3f}:d=6,volume={volumen}[mu];[voz]asplit=2[vv][sc];'
                   '[mu][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck];'
                   '[vv][duck]amix=inputs=2:normalize=0:duration=first[mez]')
        fin = 'mez'
    else:
        avisos.append('Sin música: no encontré tu música fija ni la del proyecto (musica.mp3); la pista lleva solo la voz.')
        fin = 'voz'
    flt.append(f'[{fin}]loudnorm=I=-16:TP=-1.5,aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,'
               f'apad=whole_dur={total:.3f},atrim=0:{total:.3f}[a]')
    script = salida + '.filtro.txt'  # con cientos de bloques la línea de comandos de Windows queda corta
    open(script, 'w', encoding='utf-8').write(';\n'.join(flt))
    try:
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + ins + _filtro_archivo(script) + ['-map', '[a]',
                        '-t', f'{total:.3f}', '-c:a', 'libmp3lame', '-b:a', '192k', salida], check=True, **SIN_VENTANA)
    finally:
        os.remove(script)
    acelerados = [i for i, _, _, tempo, _ in filas if tempo != 1]
    cortados = [i for i, _, _, _, cortar in filas if cortar]
    if cortados:
        avisos.append(f'Estos bloques no caben ni a ×{VEL_MAX:g} y se cortan al final con un fundido: {", ".join(cortados)}. '
                      'Acórtalos en el guion de la versión (rehacer su voz gasta ElevenLabs: te lo pregunta).')
    if any(os.path.exists(os.path.join(d, f)) for f in ('trailer.mp4', '8_testimonios.mp4', '9_modelos.mp4')):
        avisos.append('En el tráiler, los testimonios y los nuevos modelos la pista lleva solo la música (sus voces son en español).')
    avisos.append('La app NO la sube: súbela tú en YouTube Studio → tu video → Idiomas → Agregar idioma → '
                  f'{idioma.upper()} → Audio. Dura lo mismo que FINAL.mp4.')
    return {'archivo': os.path.basename(salida), 'duracion': round(duracion(salida), 2), 'bloques': len(filas),
            'acelerados': acelerados, 'cortados': cortados, 'avisos': avisos}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True, help='el proyecto en español, con FINAL.mp4')
    ap.add_argument('--idioma', default='en')
    ap.add_argument('--inicios', help='JSON {bloque: segundo en FINAL.mp4}; sin esto, inicio_min + 0,3 s del guion')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    total = duracion(os.path.join(d, 'FINAL.mp4'))
    if not total:
        raise SystemExit('Falta FINAL.mp4 en el proyecto en español.')
    if a.inicios:
        inicios = json.load(open(a.inicios, encoding='utf-8'))
    else:  # sin tráiler ni cortes al inicio: el segundo de cada bloque en el guion
        g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
        inicios = {b['id']: float(b['inicio_min']) + 0.3 for b in g['bloques'] if b.get('inicio_min') is not None}
    try:
        r = armar(d, a.idioma.lower(), inicios, total)
    except FaltaVoz as e:
        raise SystemExit(str(e))
    print(json.dumps(r, ensure_ascii=False))


if __name__ == '__main__':
    sys.exit(main())
