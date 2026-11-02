"""Prueba rápida del «modo avatar ahorro» (avatar/ahorro.py): gancho sin avatar, pocos tramos de avatar largos y con tope,
cortes a dos velocidades que caen en las frases, que se respeten las marcas del guion y que el montaje dure lo mismo que la
voz más la pantalla final (sin desfase). No gasta nada.
Uso: python tests/test_avatar_ahorro.py   (sale con 1 si algo falla)
"""
import os, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'avatar'))
import ahorro  # noqa: E402

fallos = []


def ok(cond, msg):
    if not cond:
        fallos.append(msg)


def frases(n=112, largo=8.0, fuertes=()):
    """n frases de `largo` s (un video de ~15 min); las de `fuertes` llevan una alerta."""
    out = []
    for k in range(n):
        texto = '¡Ojo, NO le des el código a nadie!' if k in fuertes else f'Esta es la frase número {k} del video, sin nada especial.'
        out.append({'s': k * largo, 'e': k * largo + largo - 0.5, 'texto': texto, 'bloque': f'L{k // 3:02d}'})
    return out


# 1) modo ahorro: gancho sin avatar, luego la presentación; 2-4 tramos de 30-55 s; tope ~15 %; cierre con avatar
fr = frases(fuertes=(40, 75))
t = ahorro.elegir(fr)
r = ahorro.resumen(t)
av = [x for x in t if x['tipo'] == 'avatar']
ok(t[0]['tipo'] == 'voz' and 30 <= t[0]['e'] <= 60, f'el gancho (30-60 s) debería ir sin avatar: {t[0]}')
ok(av and av[0]['s'] == t[0]['e'], 'el avatar debería entrar justo después del gancho')
ok(2 <= len(av) <= 4, f'esperaba 2 a 4 tramos con avatar, hay {len(av)}')
ok(all(25 <= x['e'] - x['s'] < 60 for x in av), f'cada tramo con avatar debería durar 30-55 s: {[round(x["e"] - x["s"]) for x in av]}')
ok(r['avatar_pct'] <= 17, f'el avatar no debería pasar de ~15 %: {r}')
ok(av[-1]['e'] == fr[-1]['e'], 'el cierre debería ir con avatar')
ok(any(x['i0'] <= 40 <= x['i1'] or x['i0'] <= 75 <= x['i1'] for x in av), 'algún momento fuerte debería ir con avatar')
ok(t[0]['s'] == 0 and t[-1]['e'] == fr[-1]['e'] and all(a['e'] == b['s'] for a, b in zip(t, t[1:])), 'hay huecos entre tramos')

# 2) modo todo y gancho apagado
t2 = ahorro.elegir(fr, 'todo')
ok(all(x['tipo'] == 'avatar' for x in t2) and ahorro.resumen(t2)['ahorro_pct'] == 0, 'con «todo» todo va con avatar')
t2b = ahorro.elegir(fr, 'ahorro', {'gancho_s': 0})
ok(t2b[0]['tipo'] == 'avatar', 'sin gancho, el avatar abre el video')

# 3) las marcas del guion mandan
fr3 = frases()
for f in fr3:
    if f['bloque'] == 'L10':
        f['avatar'] = True
    if f['bloque'] == 'L06':
        f['avatar'] = False
t3 = ahorro.elegir(fr3)
ok(all(x['tipo'] == 'avatar' for x in t3 if fr3[x['i0']]['bloque'] == 'L10'), 'el bloque marcado con avatar debe ir con avatar')
ok(all(x['tipo'] == 'voz' for x in t3 if x['i0'] <= 18 <= x['i1']), 'el bloque marcado sin avatar debe ir con voz en off')

# 4) cortes: ~2 s en el primer minuto, ~5 s después, corridos al inicio de frase cercano
cs = ahorro.cortes(0, 120, [x * 7.0 for x in range(20)])
pasos = [b - a for a, b in zip(cs, cs[1:])]
primer = [p for a, p in zip(cs, pasos) if a < 55]
despues = [p for a, p in zip(cs, pasos) if a >= 62]
ok(primer and max(primer) <= 3.0, f'en el primer minuto los cortes deberían ir cada ~2 s: {primer}')
ok(despues and min(despues) >= 2.5 and 3.5 <= sum(despues) / len(despues) <= 7.0, f'después cada ~5 s: {despues}')
ok(any(abs(c - 70.0) < 0.01 or abs(c - 77.0) < 0.01 for c in cs), 'los cortes deberían caer en el inicio de una frase cercana')

# 5) montaje: dura lo mismo que la voz más la pantalla final
with tempfile.TemporaryDirectory() as tmp:
    voz = os.path.join(tmp, 'voz.mp3')
    ahorro.ff('-f', 'lavfi', '-i', 'sine=frequency=440:duration=12', voz)
    cara = os.path.join(tmp, 'cara.mp4')
    ahorro.ff('-f', 'lavfi', '-i', 'testsrc=size=640x360:rate=25:duration=3', '-pix_fmt', 'yuv420p', cara)
    img = os.path.join(tmp, 'img.png')
    ahorro.ff('-f', 'lavfi', '-i', 'color=c=red:size=640x360', '-frames:v', '1', img)
    tramos = [{'tipo': 'voz', 's': 0, 'e': 5}, {'tipo': 'avatar', 's': 5, 'e': 9}, {'tipo': 'voz', 's': 9, 'e': 12}]
    sal = os.path.join(tmp, 'm.mp4')
    ahorro.montar(tramos, voz, [cara], [img, cara], sal, {'final_s': 3, 'plano_s': 2})
    dv = float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of',
                               'csv=p=0', sal], capture_output=True, text=True).stdout.strip() or 0)
    ok(abs(dv - 15) < 0.25, f'el video debería durar 15 s (12 de voz + 3 de pantalla final), dura {dv}')

print('\n'.join(fallos) or 'ok: modo avatar ahorro')
sys.exit(1 if fallos else 0)
