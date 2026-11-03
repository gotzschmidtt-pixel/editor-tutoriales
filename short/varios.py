"""«📱 Varios Shorts»: del mismo video, de 2 a 5 Shorts con pasos distintos, para publicarlos en días distintos y llevar
gente al video largo.

Usa el mismo armado que «📱 Short» (short.py: reencuadre 9:16, la voz que ya está hecha, subtítulos grandes y tu música),
pero cada Short toma bloques que los anteriores no usaron. El primero lleva el gancho del inicio; los demás arrancan en su
propio paso. Deja SHORT_1.mp4, SHORT_2.mp4… y shorts.json con las tomas de cada uno, un título sugerido y el día para
publicarlo (uno cada 2 días desde hoy, o desde --desde). No gasta créditos.

Uso (desde la carpeta del proyecto): python varios.py --proyecto . --cantidad 3 --duracion 60 [--desde 2026-11-02]
Los Shorts siguen de ~60 s (fabian, 03/11/2026: «¿Un Short de 30-40 s? No por ahora»).
"""
import argparse, datetime, json, os, re, shutil, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import short  # noqa: E402


def descripcion(titulo_short):
    """La descripción del Short: arriba la línea del video (su título), enseguida el bloque de WhatsApp de fabian
    (02/11/2026, en todos los videos de desbloqueo) y después la invitación al tutorial completo. Sin el conocimiento
    (mis_conocimientos) queda solo la invitación, como antes."""
    base = 'Mira el tutorial completo en mi canal (link en el comentario fijado).'
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'youtube'))
        import youtube
        return youtube.con_contacto(f'{titulo_short}\n\n{base}' if titulo_short else base, 'es')
    except Exception:
        return base


def titulo(tomas, usados=()):
    """Un título corto para el Short con lo que se ve (sin el gancho del inicio), distinto de los Shorts anteriores."""
    t = ' '.join(c['texto'] for c in (tomas[1:] if len(tomas) > 1 and tomas[0]['id'] == 'L01' else tomas))
    for rx, txt in ((r'fastboot', 'Así se entra a Fastboot'), (r'recovery', 'Así se entra a Recovery'), (r'\bdfu\b', 'Modo DFU en segundos'),
                    (r'\bkey\b|clave', 'El paso de la key'), (r'cuenta de google|frp', 'Adiós a la cuenta Google'),
                    (r'icloud', 'Adiós a iCloud'), (r'desbloque|libre|sin cuenta', 'Así queda desbloqueado')):
        if re.search(rx, t, re.I) and txt not in usados:
            return txt
    # la primera toma con texto: el gancho sin voz (GANCHO) no tiene y el título salía vacío
    palabras = re.findall(r"[\wáéíóúñü']+", next((c['texto'] for c in tomas if c.get('texto')), ''))
    return ' '.join(palabras[:6]).capitalize()


def con_modelo(d, txt):
    """El título del Short con el nombre del modelo como va en el título del video largo (youtube/metadatos.json, campo
    «modelo»; p. ej. «Honor Magic 8 Lite», lo que dice la caja). Pedido del 02/11/2026."""
    try:
        modelo = (json.load(open(os.path.join(d, 'youtube', 'metadatos.json'), encoding='utf-8')).get('modelo') or '').strip()
    except (OSError, ValueError):
        modelo = ''
    return f'{modelo}: {txt}' if modelo and modelo.lower() not in txt.lower() else txt


def revisar_short(d, salida, ass):
    """«✅ Revisor automático» (revision/revisor_auto.py) sobre el Short recién armado: subtítulos, planos largos al inicio,
    que lo que nombra la voz se lea y datos privados (los difumina solo en el dato). {'ok': …, 'informe': …}."""
    sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'revision'))
    try:
        import revisor_auto
        inf = revisor_auto.revisar(os.path.join(d, salida), os.path.join(d, ass), True, arreglar=True)
        return {'ok': inf['ok'], 'informe': os.path.splitext(salida)[0] + '.revision.md'}
    except Exception as e:  # el revisor nunca frena el armado, pero sin revisión no queda como listo
        print(f'· no pude revisar {salida}: {e}', flush=True)
        return {'ok': False, 'informe': None, 'error': str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--cantidad', type=int, default=3)
    ap.add_argument('--duracion', type=float, default=60)  # ~60 s como todos los Shorts (fabian, 03/11/2026; antes 45)
    ap.add_argument('--desde', help='fecha del primer Short (AAAA-MM-DD); por defecto, mañana')
    ap.add_argument('--cada', type=int, default=2, help='días entre un Short y el siguiente')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    n = max(2, min(5, a.cantidad))
    usados, hechos = set(), []
    try:
        plan_bloques = json.load(open(os.path.join(d, 'shorts_plan.json'), encoding='utf-8'))
    except (OSError, ValueError):
        plan_bloques = None
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
        if plan_bloques and len(plan_bloques) >= k:  # shorts_plan.json: los bloques de cada Short, elegidos a mano
            pk = plan_bloques[k - 1]
            if isinstance(pk, dict):  # {"bloques": [...], "gancho": [78, 3.5]}
                sys.argv += ['--bloques', ','.join(pk['bloques'])] + (['--gancho', ','.join(map(str, pk['gancho']))] if pk.get('gancho') else [])
            else:
                sys.argv += ['--bloques', ','.join(pk)]
        try:
            short.main()
        except SystemExit as e:
            if k == 1:
                raise
            print(f'· no alcanzan los pasos para el Short {k} ({e}); quedan {k - 1}', flush=True)
            break
        plan = json.load(open(os.path.join(d, 'short.json'), encoding='utf-8'))
        ids = [t['id'] for t in plan['tomas'] if t['id'] != 'GANCHO']  # el gancho sin voz va en todos: no es un bloque usado
        if usados.intersection(ids) or not ids:
            break
        usados.update(ids)
        shutil.copyfile(os.path.join(d, 'short.json'), os.path.join(d, f'short_{k}.json'))
        shutil.copyfile(os.path.join(d, 'short_subs.ass'), os.path.join(d, f'short_{k}_subs.ass'))
        revision = revisar_short(d, salida, f'short_{k}_subs.ass')
        t = con_modelo(d, titulo(plan['tomas'], [h['titulo'] for h in hechos]))
        hechos.append({'archivo': salida, 'titulo': t, 'duracion': plan['duracion'], 'tomas': ids,
                       'publicar': (inicio + datetime.timedelta(days=(k - 1) * a.cada)).isoformat(),
                       'descripcion': descripcion(t), 'revision': revision})
    json.dump({'shorts': hechos}, open(os.path.join(d, 'shorts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for h in hechos:
        print(f"· {h['archivo']}: «{h['titulo']}», {h['duracion']:.0f} s, publicar el {h['publicar']} ({', '.join(h['tomas'])})"
              + ('' if h['revision']['ok'] else ' · ❌ NO está listo: mira su revisión'), flush=True)
    print(f'Listo: {len(hechos)} Shorts distintos.', flush=True)


if __name__ == '__main__':
    main()
