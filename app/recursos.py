"""«📊 Uso del PC»: cuánto procesador, memoria RAM y tarjeta gráfica se está usando mientras la app trabaja.

Gratis y sin instalar nada: en Windows lee los contadores del sistema (typeperf, los mismos del Administrador de tareas)
y la memoria con la API de Windows; si hay una NVIDIA, también nvidia-smi. Mide en un hilo aparte cada pocos segundos
mientras la página lo pide, y se apaga solo al minuto de que nadie mira.
"""
import csv, ctypes, io, os, re, shutil, subprocess, sys, threading, time

SIN_VENTANA = {'creationflags': 0x08000000} if sys.platform == 'win32' else {}
CONTADORES = [r'\GPU Engine(*engtype_3D)\Utilization Percentage',
              r'\GPU Engine(*engtype_VideoEncode)\Utilization Percentage', r'\GPU Engine(*engtype_VideoDecode)\Utilization Percentage',
              r'\GPU Engine(*engtype_Compute*)\Utilization Percentage', r'\GPU Adapter Memory(*)\Dedicated Usage',
              r'\GPU Adapter Memory(*)\Shared Usage']
_ULTIMO = {'cuando': 0}
_PEDIDO = [0.0]
_CANDADO = threading.Lock()
_HILO = []
_GRAFICA = []


def ram():
    if sys.platform != 'win32':
        return {}

    class M(ctypes.Structure):
        _fields_ = [('l', ctypes.c_ulong), ('carga', ctypes.c_ulong), ('total', ctypes.c_ulonglong), ('libre', ctypes.c_ulonglong),
                    ('pt', ctypes.c_ulonglong), ('pl', ctypes.c_ulonglong), ('vt', ctypes.c_ulonglong), ('vl', ctypes.c_ulonglong),
                    ('ve', ctypes.c_ulonglong)]
    m = M()
    m.l = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return {'ram_total_gb': round(m.total / 2 ** 30, 1), 'ram_usada_gb': round((m.total - m.libre) / 2 ** 30, 1),
            'ram_pct': int(m.carga)}


_CPU = []


def cpu():
    """% del procesador desde la medición anterior (GetSystemTimes: igual en Windows en cualquier idioma)."""
    if sys.platform != 'win32':
        return {}
    i, k, u = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
    ahora = (i.value, k.value + u.value)  # el tiempo «kernel» ya incluye el ocioso
    antes = _CPU[0] if _CPU else None
    _CPU[:] = [ahora]
    if not antes or ahora[1] == antes[1]:
        return {}
    return {'cpu_pct': max(0, min(100, round(100 * (1 - (ahora[0] - antes[0]) / (ahora[1] - antes[1])))))}


def nombre_grafica():
    if not _GRAFICA:
        try:
            r = subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-CimInstance Win32_VideoController).Name'],
                               capture_output=True, text=True, encoding='oem' if sys.platform == 'win32' else None, errors='replace', timeout=20, **SIN_VENTANA)
            _GRAFICA.append(' + '.join(x.strip() for x in r.stdout.splitlines() if x.strip()))
        except Exception:
            _GRAFICA.append('')
    return _GRAFICA[0]


def _contadores():
    """CPU y gráfica con typeperf (tarda ~2 s). Las «engine» se suman por tipo, como en el Administrador de tareas."""
    r = subprocess.run(['typeperf', *CONTADORES, '-sc', '1'], capture_output=True, text=True, encoding='oem' if sys.platform == 'win32' else None, errors='replace', timeout=30, **SIN_VENTANA)
    filas = [f for f in csv.reader(io.StringIO(r.stdout)) if len(f) > 1]
    if len(filas) < 2:
        return {}
    cab, val = filas[0], filas[1]
    out, suma = {}, {}
    for nombre, v in zip(cab[1:], val[1:]):
        try:
            x = float(v)
        except ValueError:
            continue
        n = nombre.lower()
        if 'proces' in n and 'gpu' not in n:  # «Processor» o «Procesador» (Windows en español)
            out['cpu_pct'] = round(x)
        elif 'dedicated usage' in n:
            suma['vram'] = suma.get('vram', 0) + x
        elif 'shared usage' in n:
            suma['compartida'] = suma.get('compartida', 0) + x
        else:
            tipo = re.search(r'engtype_(\w+)', n)
            if tipo:
                t = 'compute' if tipo.group(1).startswith('compute') else tipo.group(1)
                suma[t] = suma.get(t, 0) + x
    for t, clave in (('3d', 'gpu_3d_pct'), ('videoencode', 'gpu_codificar_pct'), ('videodecode', 'gpu_decodificar_pct'),
                     ('compute', 'gpu_calculo_pct')):
        if t in suma:
            out[clave] = min(100, round(suma[t]))
    if 'vram' in suma:
        out['vram_gb'] = round(suma['vram'] / 2 ** 30, 2)
    if 'compartida' in suma:
        out['gpu_compartida_gb'] = round(suma['compartida'] / 2 ** 30, 2)
    return out


def _nvidia():
    if not shutil.which('nvidia-smi'):
        return {}
    r = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,utilization.encoder,memory.used,memory.total,temperature.gpu',
                        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15, **SIN_VENTANA)
    p = [x.strip() for x in (r.stdout.splitlines() or [''])[0].split(',')]
    try:
        return {'nvidia_pct': int(p[0]), 'nvidia_codificar_pct': int(p[1]), 'vram_gb': round(int(p[2]) / 1024, 2),
                'vram_total_gb': round(int(p[3]) / 1024, 1), 'gpu_temp_c': int(p[4])}
    except (ValueError, IndexError):
        return {}


def _medir():
    while time.time() - _PEDIDO[0] < 60:  # se apaga solo si nadie mira
        d = {**ram(), **cpu()}
        try:
            d.update(_contadores())
        except Exception as e:
            d['error'] = f'no pude leer los contadores de Windows ({type(e).__name__})'
        try:
            d.update(_nvidia())
        except Exception:
            pass
        d['cuando'] = time.time()
        with _CANDADO:
            _ULTIMO.clear()
            _ULTIMO.update(d)
        time.sleep(1)
    with _CANDADO:
        _HILO.clear()


def leer():
    """Lo último medido (y arranca la medición si estaba apagada)."""
    _PEDIDO[0] = time.time()
    with _CANDADO:
        if not _HILO:
            h = threading.Thread(target=_medir, daemon=True)
            _HILO.append(h)
            h.start()
        d = dict(_ULTIMO)
    d['grafica'] = nombre_grafica()
    d['nucleos'] = os.cpu_count()
    return d
