"""Codifica el video con la tarjeta NVIDIA (NVENC) o con la gráfica Intel (Quick Sync) cuando las hay, y si no, o si
fallan, con el procesador (libx264).

Los pasos arman sus comandos de ffmpeg con libx264 como siempre y los corren con `run(...)` en vez de subprocess.run:
si esta PC tiene NVENC que funciona, se cambia libx264 por h264_nvenc con una calidad parecida; si ffmpeg falla con la
tarjeta, se repite el mismo comando con el procesador y ya no se vuelve a intentar con la tarjeta en ese paso.

Sin NVIDIA, se prueba Quick Sync (h264_qsv) de la gráfica Intel con el ffmpeg de siempre: -crf pasa a -global_quality.

Se apaga con "nvidia": false en app/ajustes.json o con la variable EDITOR_NVENC=0 (las dos gráficas).

Un ffmpeg muy nuevo puede pedir un driver de NVIDIA que tu tarjeta ya no recibe (la GTX 1050 se quedó en el 580). Para eso,
si existe la carpeta ffmpeg_nvidia/ (con un ffmpeg compatible con tu driver), la tarjeta codifica con ese ffmpeg y todo lo
demás sigue con el ffmpeg de siempre. También se puede indicar su ruta con "ffmpeg_nvidia" en app/ajustes.json.

Uso desde la app (comando externo): python codificar.py ffmpeg -i ... -c:v libx264 ... salida.mp4
"""
import json, os, subprocess, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
AJUSTES = os.path.join(RAIZ, 'app', 'ajustes.json')
SIN_VENTANA = {'creationflags': 0x08000000} if os.name == 'nt' else {}  # en Windows, sin ventana negra de consola

# preset de libx264 -> preset de NVENC (p1 el más rápido, p7 el de mejor calidad)
PRESETS = {'ultrafast': 'p1', 'superfast': 'p2', 'veryfast': 'p3', 'faster': 'p4', 'fast': 'p4', 'medium': 'p5',
           'slow': 'p6', 'slower': 'p7', 'veryslow': 'p7'}
_nvenc = None  # None: no probado todavía en este proceso
_qsv = None
USADOS = set()  # con qué se codificó en este proceso: 'nvidia', 'intel' y/o 'procesador'


def _ajustes():
    try:
        aj = json.load(open(AJUSTES, encoding='utf-8'))
        return aj if isinstance(aj, dict) else {}
    except (OSError, ValueError):
        return {}


def quiere_nvidia():
    env = os.environ.get('EDITOR_NVENC', '').strip().lower()
    if env in ('0', 'no', 'false'):
        return False
    return _ajustes().get('nvidia', True) is not False


def ffmpeg_nvidia():
    """El ffmpeg con que codifica la tarjeta: el de ffmpeg_nvidia/ si lo hay, si no el de siempre."""
    propio = str(_ajustes().get('ffmpeg_nvidia') or '').strip()
    for f in ([propio] if propio else []) + [os.path.join(RAIZ, 'ffmpeg_nvidia', *p) for p in
                                              (('bin', 'ffmpeg.exe'), ('ffmpeg.exe',), ('bin', 'ffmpeg'), ('ffmpeg',))]:
        if os.path.isfile(f):
            return f
    return 'ffmpeg'


def hay_nvenc():
    """¿Esta PC codifica con h264_nvenc? Se prueba una vez por proceso con un video mínimo."""
    global _nvenc
    if _nvenc is None:
        if not quiere_nvidia():
            _nvenc = False
        elif os.environ.get('EDITOR_NVENC', '').strip().lower() == 'forzar':  # solo para pruebas: se da por buena sin probar
            _nvenc = True
        else:
            try:
                r = subprocess.run([ffmpeg_nvidia(), '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:r=25:d=0.2',
                                    '-c:v', 'h264_nvenc', '-preset', 'p4', '-f', 'null', '-'],
                                   capture_output=True, timeout=30, **SIN_VENTANA)
                _nvenc = r.returncode == 0
            except (OSError, subprocess.SubprocessError):
                _nvenc = False
    return _nvenc


def hay_qsv():
    """¿Esta PC codifica con Quick Sync de Intel (h264_qsv)? Se prueba una vez por proceso."""
    global _qsv
    if _qsv is None:
        if not quiere_nvidia() or os.environ.get('EDITOR_NVENC', '').strip().lower() == 'forzar':
            _qsv = False
        else:
            try:
                r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:r=25:d=0.2',
                                    '-c:v', 'h264_qsv', '-f', 'null', '-'], capture_output=True, timeout=30, **SIN_VENTANA)
                _qsv = r.returncode == 0
            except (OSError, subprocess.SubprocessError):
                _qsv = False
    return _qsv


def con_qsv(cmd):
    """El mismo comando con h264_qsv (Intel Quick Sync) en vez de libx264. None si no usa libx264."""
    cmd = [str(x) for x in cmd]
    if 'libx264' not in cmd:
        return None
    out, i = [cmd[0]], 1
    while i < len(cmd):
        x = cmd[i]
        if x == 'libx264':
            out.append('h264_qsv')
        elif x == '-crf' and i + 1 < len(cmd):  # calidad constante parecida
            out += ['-global_quality', cmd[i + 1]]
            i += 1
        elif x == '-pix_fmt' and i + 1 < len(cmd) and cmd[i + 1] == 'yuv420p':  # Quick Sync pide nv12 (también 4:2:0)
            out += ['-pix_fmt', 'nv12']
            i += 1
        else:
            out.append(x)  # -preset ultrafast…veryslow: Quick Sync acepta los mismos nombres
        i += 1
    return out


def con_nvenc(cmd):
    """El mismo comando de ffmpeg con h264_nvenc en vez de libx264 (y -crf/-preset traducidos). None si no usa libx264."""
    cmd = [str(x) for x in cmd]
    if 'libx264' not in cmd:
        return None
    out, i = [ffmpeg_nvidia() if os.path.basename(cmd[0]).lower() in ('ffmpeg', 'ffmpeg.exe') else cmd[0]], 1
    while i < len(cmd):
        x = cmd[i]
        if x == 'libx264':
            out.append('h264_nvenc')
        elif x == '-crf' and i + 1 < len(cmd):  # calidad constante: -cq de NVENC con la misma cifra se ve parecido
            out += ['-rc', 'vbr', '-cq', cmd[i + 1], '-b:v', '0']
            i += 1
        elif x == '-preset' and i + 1 < len(cmd):
            out += ['-preset', PRESETS.get(cmd[i + 1], 'p5')]
            i += 1
        else:
            out.append(x)
        i += 1
    return out


def run(cmd, **kw):
    """subprocess.run de un comando de ffmpeg: con NVIDIA, si no con Intel Quick Sync, y si no con el procesador."""
    global _nvenc, _qsv
    nv = con_nvenc(cmd) if hay_nvenc() else None
    if nv:
        kw_nv = dict(kw, check=False)
        r = subprocess.run(nv, **kw_nv)
        if r.returncode == 0:
            USADOS.add('nvidia')
            return r
        _nvenc = False  # la tarjeta falló (driver viejo, sin memoria, demasiadas a la vez): el resto del paso va con el procesador
        print('· la tarjeta NVIDIA no pudo codificar este tramo; lo repito con el procesador', flush=True)
    qs = con_qsv(cmd) if not nv and hay_qsv() else None
    if qs:
        r = subprocess.run(qs, **dict(kw, check=False))
        if r.returncode == 0:
            USADOS.add('intel')
            return r
        _qsv = False
        print('· la gráfica Intel no pudo codificar este tramo; lo repito con el procesador', flush=True)
    if 'libx264' in [str(x) for x in cmd]:
        USADOS.add('procesador')
    return subprocess.run(cmd, **kw)


if __name__ == '__main__':  # la app lo usa como envoltorio: python codificar.py ffmpeg ...
    sys.exit(run(sys.argv[1:]).returncode)
