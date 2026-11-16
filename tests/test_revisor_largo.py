"""Revisor automático del video LARGO (fabian 15/11/2026, todas las marcas): lo que falló en el Honor 400 Lite no puede
volver a pasar. Sin videos reales ni gastos: imagen más corta que el sonido, páginas dichas deletreadas, WhatsApp
después de 2:00, voz apurada, montos, cartel DESPUÉS sobre «así empieza»."""
import os, subprocess, sys, tempfile
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'revision'))
import revisor_auto as r  # noqa: E402

d = tempfile.mkdtemp()
# 1. imagen 3 s y sonido 5 s: desfase
v = os.path.join(d, 'v.mp4')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:d=3', '-f', 'lavfi', '-i',
                'sine=f=440:d=5', '-c:v', 'libx264', '-c:a', 'aac', v], check=True)
f = r.revisar_av(v)
assert f and 'desfasada' in f[0]['que'], f
ok = os.path.join(d, 'ok.mp4')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:d=3', '-f', 'lavfi', '-i',
                'sine=f=440:d=3', '-c:v', 'libx264', '-c:a', 'aac', '-shortest', ok], check=True)
assert not r.revisar_av(ok)
# 2. un tramo más corto que su voz
assert r.revisar_bloques({'L10': {'D': 5.0, 'f': v}}) and not r.revisar_bloques({'L10': {'D': 3.0, 'f': v}})

# 3. páginas deletreadas y reglas de minutos
def frase(t0, txt, paso=0.4):
    return [[w, t0 + i * paso, t0 + i * paso + 0.3] for i, w in enumerate(txt.split())]
ws = (frase(20, 'escríbenos por WhatsApp y comenta tu modelo') + frase(70, 'en G S M Prime punto co y Xiaomi Unlock punto com')
      + frase(200, 'fin del video'))
ev = r.ev_de_palabras(ws)
assert [70 <= x <= 71 for x in r.momentos(ev, 'gsmprime')] == [True] and r.momentos(ev, 'xiaomiunlock')
assert not r.revisar_reglas_minuto(ev, 300), r.revisar_reglas_minuto(ev, 300)
tarde = r.ev_de_palabras(frase(130, 'escríbenos por WhatsApp y comenta') + frase(70, 'G S M Prime punto co Xiaomi Unlock punto com'))
fallas = r.revisar_reglas_minuto(tarde, 300)
assert any('whatsapp' in x['que'] and '2:10' in x['que'] for x in fallas), fallas
assert not r.revisar_reglas_minuto(tarde, 100)  # un Short o video corto no lleva estas reglas

# 4. ritmo: 160 palabras en un minuto sin respiro = apurada; 110 con respiros = bien
rapido = r.ev_de_palabras([['palabra', i * 0.375, i * 0.375 + 0.3] for i in range(160)])
assert any('apurada' in x['que'] for x in r.revisar_ritmo(rapido)) and any('respiro' in x['que'] for x in r.revisar_ritmo(rapido))
calmo = r.ev_de_palabras([['palabra', i * 0.45 + (2.5 if i >= 55 else 0), i * 0.45 + 0.3 + (2.5 if i >= 55 else 0)] for i in range(110)])
assert not r.revisar_ritmo(calmo), r.revisar_ritmo(calmo)

# 5. montos: con OCR falso
falso = lambda img: ([(None, 'Your Current Balance $ 4535.5', 1)], None)
assert r.revisar_montos(falso, [(10.0, __import__('numpy').zeros((10, 10, 3), 'uint8'))], None)
assert r.MONTO.search('40 USD') and not r.MONTO.search('Android 16') and not r.MONTO.search('$1s)Finished')

# 6. srt -> palabras
s = os.path.join(d, 'a.srt')
open(s, 'w', encoding='utf-8').write('1\n00:01:40,000 --> 00:01:42,000\nescríbenos por WhatsApp\n\n')
e = r.ev_de_srt(s)
assert len(e) == 3 and abs(e[2][0] - (100 + 4 / 3)) < 0.01
print('ok: revisor del video largo')

# revisión grande 15/11: el primer paso real antes del 1:30
import revisor_auto as _R
_ev = lambda pal: [(t, t + 0.3, w, w) for w, t in pal]
assert _R.revisar_primer_paso(_ev([('Elimina', 1), ('Lo', 50), ('descargas', 56)]), 540) == [], 'paso a los 56 s marcado'
assert _R.revisar_primer_paso(_ev([('Primero', 170), ('apagamos', 171)]), 540), 'paso a las 2:51 no marcado'
assert _R.revisar_primer_paso(_ev([('apagamos', 171)]), 60) == [], 'un Short no se mide'
print('ok: primer paso antes del 1:30')
