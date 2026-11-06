"""Revisión de «frenar antes de congelar» (03/11/2026). Sin red ni gastos: las voces son tiempos falsos (no se llama a
ElevenLabs) y no hace falta ningún video.
- el aviso dice la velocidad con la que queda el tramo de verdad: si además sobra imagen sin voz, primero se quita esa
  imagen y después se frena (antes avisaba «×3 → ×1,5, más despacio» y el tramo quedaba a ×4,17);
- un bloque con su «cuadro» elegido para la pausa no se toca;
- frenar_tramo no hace nada con bloques sin voz, sin pausa, sin tramo o con velocidad 0.
Uso: python tests/test_frenar_revision.py   (sale con 1 si algo falla)
"""
import json, os, re, shutil, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'voz'))
import voz  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def montaje(a, z, v, pausa=None, **extra):
    return {'modo': 'lento+congelar' if pausa else 'lento', 'src_inicio': a, 'src_fin': z, 'velocidad': v,
            'congelar_s': pausa, **extra}


def correr(d, bloques, voces):
    """Guarda el guion y voces falsas (solo sus tiempos) y corre voz.ajustar_guion. Devuelve ({id: bloque}, avisos)."""
    os.makedirs(os.path.join(d, 'voz'), exist_ok=True)
    g = os.path.join(d, 'guion.json')
    with open(g, 'w', encoding='utf-8') as f:
        json.dump({'bloques': bloques}, f, ensure_ascii=False)
    for bid, s in voces.items():
        with open(os.path.join(d, 'voz', f'{bid}.align.json'), 'w', encoding='utf-8') as f:
            json.dump({'characters': list('hola'), 'character_start_times_seconds': [0] * 4,
                       'character_end_times_seconds': [s] * 4}, f)
    avisos = voz.ajustar_guion(g, os.path.join(d, 'voz'))
    with open(g, encoding='utf-8') as f:
        return {b['id']: b for b in json.load(f)['bloques']}, avisos


def velocidades_avisadas(avisos, bid):
    """Las velocidades «→ ×N» que dicen los avisos de ese bloque."""
    return [float(x) for a in avisos if a.startswith(bid + ':') for x in re.findall(r'→ ×([\d.]+)', a)]


TEXTO = 'Esperamos a que termine de borrar y se reinicie el teléfono solo.'
tmp = tempfile.mkdtemp(prefix='frenar_rev_')
try:
    # 1. ×3 + 10 s de pausa con 5 s de voz: sobra mucha imagen; queda como antes de la mejora (×4,17, sin pausa) y
    #    ningún aviso dice que el tramo va más despacio
    r, avisos = correr(os.path.join(tmp, 'a'), [{'id': 'L01', 'texto': TEXTO, 'montaje': montaje(0.0, 30.0, 3.0, 10.0)}],
                       {'L01': 5.0})
    mo = r['L01']['montaje']
    ok(mo['modo'] == 'lento' and abs(mo['velocidad'] - 4.17) < 0.011, f'debería quedar a ×4,17 sin pausa: {mo}')
    ok(not any('más despacio' in a for a in avisos), f'no debería avisar «más despacio» si el tramo quedó más rápido: {avisos}')

    # 2. ×3 + 5 s de pausa con 10 s de voz: se quita la imagen que sobra y el resto de la pausa se cambia por ir más despacio;
    #    el aviso dice la velocidad con la que queda
    r, avisos = correr(os.path.join(tmp, 'b'), [{'id': 'L02', 'texto': TEXTO, 'montaje': montaje(0.0, 30.0, 3.0, 5.0)}],
                       {'L02': 10.0})
    mo = r['L02']['montaje']
    ok(mo['modo'] == 'lento' and 1.0 <= mo['velocidad'] < 3.0 and not mo.get('congelar_s'),
       f'debería ir más despacio que ×3 y sin pausa: {mo}')
    dichas = velocidades_avisadas(avisos, 'L02')
    ok(dichas and dichas[-1] == mo['velocidad'], f"el aviso debería decir ×{mo['velocidad']:g} (la que queda): {avisos}")
    ok(abs(voz.largo_bloque(mo) - (10.0 + voz.DESFASE + voz.MARGEN + voz.RELLENO)) < 0.1,
       f'el bloque debería durar la voz más la holgura: {voz.largo_bloque(mo):.2f} s')

    # 3. con su «cuadro» elegido para la pausa (pedida a mano): como antes, ×3 + 3,7 s de pausa
    r, _ = correr(os.path.join(tmp, 'c'), [{'id': 'L03', 'texto': TEXTO, 'montaje': montaje(100.0, 130.0, 3.0, cuadro=129.0)}],
                  {'L03': 13.0})
    mo = r['L03']['montaje']
    ok(mo['velocidad'] == 3.0 and mo['modo'] == 'lento+congelar' and mo['congelar_s'] == 3.7,
       f'un bloque con su «cuadro» no debería frenarse: {mo}')

    # 4. frenar_tramo directo: nada que hacer
    for nombre, b in {
        'sin texto': {'texto': '', 'montaje': montaje(0.0, 30.0, 3.0, 4.0)},
        'sin voz': {'texto': TEXTO, 'montaje': montaje(0.0, 30.0, 3.0, 4.0, sin_voz=True)},
        'sin pausa': {'texto': TEXTO, 'montaje': montaje(0.0, 30.0, 3.0)},
        'pausa 0': {'texto': TEXTO, 'montaje': dict(montaje(0.0, 30.0, 3.0, 4.0), congelar_s=0)},
        'tramo vacío': {'texto': TEXTO, 'montaje': montaje(30.0, 30.0, 3.0, 4.0)},
        'sin tramo': {'texto': TEXTO, 'montaje': {'modo': 'lento+congelar', 'velocidad': 3.0, 'congelar_s': 4.0}},
        'velocidad 0': {'texto': TEXTO, 'montaje': montaje(0.0, 30.0, 0, 4.0)},
        'más lento que ×1': {'texto': TEXTO, 'montaje': montaje(0.0, 30.0, 0.8, 4.0)},
        'solo pausa': {'texto': TEXTO, 'montaje': {'modo': 'congelar', 'src_inicio': 0.0, 'velocidad': 3.0, 'congelar_s': 4.0}},
        'sin montaje': {'texto': TEXTO},
    }.items():
        antes = json.dumps(b, sort_keys=True)
        ok(voz.frenar_tramo(b) == '' and json.dumps(b, sort_keys=True) == antes, f'{nombre}: no debería tocarse: {b}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n'.join(fallos) or 'ok: revisión de frenar antes de congelar (aviso con la velocidad final, cuadro y bordes)')
sys.exit(1 if fallos else 0)
