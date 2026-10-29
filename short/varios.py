"""«📱 Varios Shorts»: del mismo video, de 2 a 5 Shorts con pasos distintos, para publicarlos en días distintos y llevar
gente al video largo.

Usa el mismo armado que «📱 Short» (short.py: reencuadre 9:16, la voz que ya está hecha, subtítulos grandes y tu música),
pero cada Short toma bloques que los anteriores no usaron. El primero lleva el gancho del inicio; los demás arrancan en su
propio paso. Deja SHORT_1.mp4, SHORT_2.mp4… y shorts.json con las tomas de cada uno, un título sugerido y el día para
publicarlo (uno cada 2 días desde hoy, o desde --desde). No gasta créditos.

Uso (desde la carpeta del proyecto): python varios.py --proyecto . --cantidad 3 --duracion 45 [--desde 2026-11-02]
"""
import argparse, datetime, json, os, re, shutil, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import short  # noqa: E402


def titulo(tomas, usados=()):
    """Un título corto para el Short con lo que se ve (sin el gancho del inicio), distinto de los Shorts anteriores."""
    t = ' '.join(c['texto'] for c in (tomas[1:] if len(tomas) > 1 and tomas[0]['id'] == 'L01' else tomas))
    for rx, txt in ((r'fastboot', 'Así se entra a Fastboot'), (r'recovery', 'Así se entra a Recovery'), (r'\bdfu\b', 'Modo DFU en segundos'),
                    (r'\bkey\b|clave', 'El paso de la key'), (r'cuenta de google|frp', 'Adiós a la cuenta Google'),
                    (r'icloud', 'Adiós a iCloud'), (r'desbloque|libre|sin cuenta', 'Así queda desbloqueado')):
        if re.search(rx, t, re.I) and txt not in usados:
            return txt
    palabras = re.findall(r"[\wáéíóúñü']+", tomas[0]['texto'])
    return ' '.join(palabras[:6]).capitalize()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--cantidad', type=int, default=3)
    ap.add_argument('--duracion', type=float, default=45)
    ap.add_argument('--desde', help='fecha del primer Short (AAAA-MM-DD); por defecto, mañana')
    ap.add_argument('--cada', type=int, default=2, help='días entre un Short y el siguiente')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    n = max(2, min(5, a.cantidad))
    usados, hechos = set(), []
    elegir_original = short.elegir

    def elegir_sin_repetir(dd, g, objetivo, dur_video):
        # los bloques que ya usó otro Short quedan sin texto (elegir() los salta); el gancho del inicio solo va en el primero
        bl = [dict(b, texto='') if b['id'] in usados else b for b in g['bloques']]
        return elegir_original(dd, dict(g, bloques=bl), objetivo, dur_video)

    short.elegir = elegir_sin_repetir
    inicio = datetime.date.fromisoformat(a.desde) if a.desde else datetime.date.today() + datetime.timedelta(days=1)
    for k in range(1, n + 1):
        salida = f'SHORT_{k}.mp4'
        print(f'=== Short {k} de {n} ===', flush=True)
        sys.argv = ['short.py', '--proyecto', d, '--duracion', str(a.duracion), '--salida', salida]
        try:
            short.main()
        except SystemExit as e:
            if k == 1:
                raise
            print(f'· no alcanzan los pasos para el Short {k} ({e}); quedan {k - 1}', flush=True)
            break
        plan = json.load(open(os.path.join(d, 'short.json'), encoding='utf-8'))
        ids = [t['id'] for t in plan['tomas']]
        if usados.intersection(ids) or not ids:
            break
        usados.update(ids)
        shutil.copyfile(os.path.join(d, 'short.json'), os.path.join(d, f'short_{k}.json'))
        hechos.append({'archivo': salida, 'titulo': titulo(plan['tomas'], [h['titulo'] for h in hechos]), 'duracion': plan['duracion'], 'tomas': ids,
                       'publicar': (inicio + datetime.timedelta(days=(k - 1) * a.cada)).isoformat(),
                       'descripcion': 'Mira el tutorial completo en mi canal (link en el comentario fijado).'})
    json.dump({'shorts': hechos}, open(os.path.join(d, 'shorts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for h in hechos:
        print(f"· {h['archivo']}: «{h['titulo']}», {h['duracion']:.0f} s, publicar el {h['publicar']} ({', '.join(h['tomas'])})", flush=True)
    print(f'Listo: {len(hechos)} Shorts distintos.', flush=True)


if __name__ == '__main__':
    main()
