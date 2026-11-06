"""Los Shorts siguen de ~60 s (fabian, 03/11/2026: «¿Un Short de 30-40 s? No por ahora»): «📱 Short», «📱 3 Shorts resumen»
y «📱 Varios Shorts» proponen ~60 s por defecto (Varios estaba en 45 s). Sin gastar nada.
Uso: python tests/test_shorts_60s.py"""
import os, re, sys, tempfile
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'mejoras'))
sys.path.insert(0, os.path.join(RAIZ, 'short'))
import mejoras  # noqa: E402
import resumen  # noqa: E402

leer = lambda *f: open(os.path.join(RAIZ, *f), encoding='utf-8').read()
por_defecto = lambda src: float(re.search(r"add_argument\('--duracion', type=float, default=(\d+)", src).group(1))

# «📱 Short» (short.py y su selector) y «📱 Varios Shorts» (varios.py, mejoras.py y su selector): 60 s
assert por_defecto(leer('short', 'short.py')) == 60
assert por_defecto(leer('short', 'varios.py')) == 60
c = mejoras.comandos('m_shorts', tempfile.mkdtemp(), {}, 'py', 'aj.json')[0]
assert c[c.index('--duracion') + 1] == '60', c
assert '<option value="60" selected>' in leer('app', 'index.html')
assert re.search(r'id="shDur">.*<option value="60" selected>60 s', leer('app', 'mejoras.html'))
# «📱 3 Shorts resumen»: 55-60 s de voz (750-820 letras), nada de 30-40 s
p = resumen.__doc__ + leer('short', 'resumen.py')
assert '55-60 s' in p and '750 y 820 letras' in p and not re.search(r'\b(30|35|40)\s*s\b', resumen.__doc__)
print('ok: los Shorts siguen de ~60 s')
