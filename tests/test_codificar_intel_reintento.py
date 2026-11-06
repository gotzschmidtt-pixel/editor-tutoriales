"""Prueba (03/11/2026): si la gráfica Intel falla en un tramo, se repite con Intel (hasta 4 veces) antes de pasar al procesador.

En la laptop de fabian (ffmpeg 9.0.2, Quick Sync), h264_qsv falla al azar más o menos 1 de cada 8 a 13 tramos, aunque el
comando sea simple, y a veces 2 seguidas. Antes, con el primer fallo, todo lo demás iba con el procesador y el video se recodificaba entero.
Sin red y sin ffmpeg: se simula subprocess.run.
"""
import os, subprocess, sys, types

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'codificar'))
import codificar  # noqa: E402
codificar.time = types.SimpleNamespace(sleep=lambda s: None)  # sin esperar de verdad

CMD = ['ffmpeg', '-i', 'a.mp4', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-pix_fmt', 'yuv420p', 'b.mp4']
llamadas = []


def simular(fallos_intel):
    """subprocess.run falso: h264_qsv falla las primeras `fallos_intel` veces; libx264 siempre sale bien."""
    def run(cmd, **kw):
        llamadas.append(list(cmd))
        intel = 'h264_qsv' in cmd
        n_intel = sum('h264_qsv' in c for c in llamadas)
        ok = not intel or n_intel > fallos_intel
        return types.SimpleNamespace(returncode=0 if ok else 1, stdout='', stderr='')
    return run


def preparar(fallos_intel):
    llamadas.clear()
    codificar.USADOS.clear()
    codificar._nvenc, codificar._qsv = False, True  # sin NVIDIA, con Intel
    codificar.subprocess = types.SimpleNamespace(run=simular(fallos_intel), SubprocessError=subprocess.SubprocessError)


# 1) un fallo suelto: el mismo tramo sale con Intel al segundo intento, y Intel sigue para los tramos siguientes
preparar(1)
assert codificar.run(CMD).returncode == 0
assert [('h264_qsv' in c) for c in llamadas] == [True, True], llamadas
assert codificar.USADOS == {'intel'} and codificar._qsv is True, (codificar.USADOS, codificar._qsv)
assert codificar.run(CMD).returncode == 0 and 'h264_qsv' in llamadas[-1], 'el tramo siguiente también va con Intel'
assert codificar.USADOS == {'intel'}, 'todo con un solo codificador: el final no se recodifica'
# la traducción a Quick Sync sigue igual: -crf → -global_quality y yuv420p → nv12
assert '-global_quality' in llamadas[0] and 'nv12' in llamadas[0] and '-crf' not in llamadas[0], llamadas[0]

# 2) tres fallos seguidos (pasó en la laptop: 2 seguidos cerca del final): al cuarto intento sale con Intel
preparar(3)
assert codificar.run(CMD).returncode == 0
assert [('h264_qsv' in c) for c in llamadas] == [True] * 4, llamadas
assert codificar.USADOS == {'intel'} and codificar._qsv is True

# 3) cuatro fallos seguidos: ese tramo va con el procesador y ya no se insiste con Intel en este paso
preparar(4)
assert codificar.run(CMD).returncode == 0
assert [('h264_qsv' in c) for c in llamadas] == [True] * 4 + [False], llamadas
assert llamadas[-1] == CMD, 'con el procesador va el comando original, tal cual'
assert codificar.USADOS == {'procesador'} and codificar._qsv is False
codificar.run(CMD)
assert 'h264_qsv' not in llamadas[-1], 'después de 4 fallos seguidos, el resto del paso va con el procesador'

print('ok: Intel se repite hasta 4 veces en un tramo; solo con 4 fallos seguidos pasa al procesador')
