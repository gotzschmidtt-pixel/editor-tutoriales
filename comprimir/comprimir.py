"""«🗜 Comprimir video»: el mismo video, con la calidad que se ve igual, en mucho menos espacio (como lo deja YouTube).

Un video de Filmora o de la app sale con muchos megabits por segundo (≈ 1 GB por 10 min); YouTube lo recomprime a
≈ 2–4 Mbps y se ve prácticamente igual. Aquí se hace lo mismo con ffmpeg:
  - youtube   H.264 calidad constante (CRF 23, preset slow): se ve igual y pesa ≈ 3 a 5 veces menos. Se abre en todo.
  - liviano   H.265/HEVC (CRF 27): ≈ la mitad que el anterior con la misma calidad. Windows y YouTube lo leen; algunos
              reproductores viejos no.
  - maxima    H.264 CRF 19: casi sin pérdida, ahorra menos.
«Rápido con la gráfica» usa NVIDIA/Intel (mucho más rápido, pesa algo más). El audio pasa a AAC 160 kbps.
Deja «NOMBRE_comprimido.mp4» al lado del original; el original no se toca.

Uso suelto: python comprimir.py "C:\\ruta\\video.mp4" [--perfil youtube|liviano|maxima] [--alto 1080] [--rapido]
"""
import argparse, json, os, re, subprocess, sys, threading, time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'codificar'))

PERFILES = {
    'youtube': {'nombre': 'Como YouTube (H.264)', 'cpu': ['-c:v', 'libx264', '-preset', 'slow', '-crf', '23'],
                'gpu': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '25']},
    'liviano': {'nombre': 'Más liviano (H.265)', 'cpu': ['-c:v', 'libx265', '-preset', 'medium', '-crf', '27', '-tag:v', 'hvc1'],
                'gpu': ['-c:v', 'hevc_nvenc', '-preset', 'p5', '-rc', 'vbr', '-cq', '30', '-b:v', '0', '-tag:v', 'hvc1']},
    'maxima': {'nombre': 'Máxima calidad (H.264)', 'cpu': ['-c:v', 'libx264', '-preset', 'slow', '-crf', '19'],
               'gpu': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20']},
}
ESTADO = {'activo': False}
_CANDADO = threading.Lock()


def duracion(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def salida_de(entrada):
    base, _ = os.path.splitext(entrada)
    return base + '_comprimido.mp4'


def comando(entrada, salida, perfil, alto, rapido):
    p = PERFILES.get(perfil, PERFILES['youtube'])
    vf = ['-vf', f"scale=-2:'min({int(alto)},ih)'"] if alto else []
    video = p['gpu'] if rapido else p['cpu']
    return (['ffmpeg', '-nostdin', '-hide_banner', '-y', '-i', entrada] + vf + video +
            ['-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', salida])


def _correr(entrada, salida, perfil, alto, rapido):
    total = duracion(entrada) or 1
    cmd = comando(entrada, salida, perfil, alto, rapido)
    if rapido and 'libx264' in cmd:  # la gráfica: codificar cambia libx264 por NVENC o Quick Sync
        import codificar
        cmd = codificar.con_nvenc(cmd) if codificar.hay_nvenc() else (codificar.con_qsv(cmd) if codificar.hay_qsv() else None) or cmd
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    ESTADO['pid'] = proc.pid
    errores = []
    hilo = threading.Thread(target=lambda: errores.extend(proc.stderr.read().splitlines()[-8:]), daemon=True)
    hilo.start()
    for linea in proc.stdout:
        m = re.match(r'out_time_(?:us|ms)=(\d+)', linea.strip())
        if m:
            hecho = int(m.group(1)) / 1e6
            ESTADO['pct'] = round(min(99.0, hecho * 100 / total), 1)
            pasado = time.time() - t0
            ESTADO['falta_s'] = round(pasado * (total - hecho) / hecho) if hecho > 1 else None
    proc.wait()
    hilo.join(timeout=5)
    if proc.returncode != 0:
        if rapido and not ESTADO.get('error'):  # la gráfica no pudo (sin NVENC/Quick Sync, o falló): se hace con el procesador
            ESTADO['perfil'] = ESTADO.get('perfil', '') + ' · con el procesador'
            return _correr(entrada, salida, perfil, alto, False)
        raise RuntimeError(' '.join(errores)[-400:] or f'ffmpeg terminó con error {proc.returncode}')


def iniciar(entrada, perfil='youtube', alto=0, rapido=False):
    """Empieza a comprimir en segundo plano. Devuelve la ruta de salida."""
    entrada = os.path.abspath(entrada)
    if not os.path.isfile(entrada):
        raise ValueError('No encuentro ese video.')
    with _CANDADO:
        if ESTADO.get('activo'):
            raise ValueError('Ya estoy comprimiendo otro video: espera a que termine.')
        salida = salida_de(entrada)
        ESTADO.clear()
        ESTADO.update(activo=True, pct=0.0, entrada=entrada, salida=salida, perfil=PERFILES.get(perfil, PERFILES['youtube'])['nombre'],
                      tam_antes=os.path.getsize(entrada), tam_despues=None, error=None, falta_s=None, inicio=time.time())

    def trabajo():
        try:
            _correr(entrada, salida, perfil, alto, rapido)
            ESTADO.update(pct=100.0, tam_despues=os.path.getsize(salida), segundos=round(time.time() - ESTADO['inicio']))
        except Exception as e:
            ESTADO['error'] = str(e)
            if os.path.exists(salida):
                try:
                    os.remove(salida)
                except OSError:
                    pass
        finally:
            ESTADO['activo'] = False
    threading.Thread(target=trabajo, daemon=True).start()
    return salida


def cancelar():
    pid = ESTADO.get('pid')
    if ESTADO.get('activo') and pid:
        subprocess.run(['taskkill', '/PID', str(pid), '/F'] if os.name == 'nt' else ['kill', str(pid)], capture_output=True)
        ESTADO['error'] = 'Cancelado.'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada')
    ap.add_argument('--perfil', default='youtube', choices=list(PERFILES))
    ap.add_argument('--alto', type=int, default=0)
    ap.add_argument('--rapido', action='store_true')
    a = ap.parse_args()
    salida = iniciar(a.entrada, a.perfil, a.alto, a.rapido)
    while ESTADO.get('activo'):
        time.sleep(2)
        print(f"{ESTADO.get('pct', 0):5.1f} %", flush=True)
    print(json.dumps({k: ESTADO.get(k) for k in ('salida', 'tam_antes', 'tam_despues', 'error', 'segundos')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
