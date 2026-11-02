"""«✅ Revisor automático» sin videos reales ni gastos: detecta subtítulos encimados o en dos líneas, subtítulos en la zona de
los botones de YouTube, planos de más de 5 s al inicio y compara palabras completas («era» no es «erase»)."""
import os, sys, tempfile
import numpy as np
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'revision'))
import revisor_auto as r  # noqa: E402

ass = os.path.join(tempfile.mkdtemp(), 's.ass')
open(ass, 'w', encoding='utf-8').write('\n'.join([
    '[Script Info]', 'WrapStyle: 2', '[V4+ Styles]',
    'Style: S,Arial Black,126,&H00FFFFFF,&H0000D2FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,9,3,2,50,50,200,1',
    '[Events]',
    'Dialogue: 0,0:00:01.00,0:00:02.50,S,,0,0,0,,{\\c&H0000D2FF&}OKAY{\\c&H00FFFFFF&} FINISHED',
    'Dialogue: 0,0:00:02.00,0:00:03.00,S,,0,0,0,,ERA',
]))
ev, margen, wrap2 = r.leer_ass(ass)
assert ev[0][3] == 'OKAY' and margen == 200 and wrap2
fallas = r.revisar_subs(ev, margen, wrap2, 1920, True)
assert any('a la vez' in f['que'] and f['s'] == 2.0 for f in fallas), fallas
assert any('muy abajo' in f['que'] for f in fallas)  # 200 px < 20 % de 1920: lo tapan los botones

quieto = np.zeros((1920, 1080, 3), np.uint8); quieto[:] = (200, 60, 60)  # azul
otro = np.zeros_like(quieto); otro[:] = (60, 60, 200)  # rojo
cuadros = [(t / 2, quieto) for t in range(0, 17)] + [(8.5, otro), (9.0, otro)]
assert any('8 s seguidos' in f['que'] for f in r.revisar_planos(cuadros)), r.revisar_planos(cuadros)
assert not r.revisar_planos([(t / 2, quieto if (t // 8) % 2 else otro) for t in range(0, 40)])  # cambia cada 4 s: bien

assert r.normal('Configuración') == 'configuracion'
assert 'erase' in r.palabras('Erase FRP By Code') and 'era' not in r.palabras('Erase FRP By Code')
assert 'era' not in r.PALABRAS_PANTALLA and 'omitir' in r.PALABRAS_PANTALLA
print('ok: revisor automático')
