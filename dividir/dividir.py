"""Divide un video grande en partes más chicas, SIN perder calidad (no se vuelve a codificar).

Para subir al chat de Claude, que no acepta archivos de más de 480 MB. Cada parte se corta justo en un
cuadro clave, así se ve sola y además las partes se pueden volver a unir sin saltos.

Uso:
  python dividir/dividir.py VIDEO [VIDEO ...] [--max-mb 450]
  python dividir/dividir.py --unir CARPETA_DE_PARTES      (vuelve a unir las partes en orden)

Las partes quedan en una carpeta al lado del video: «<nombre>_PARTES/<nombre>_parte01de03.mp4», con
un LEEME.txt y lista_unir.txt para rearmar el video con:  ffmpeg -f concat -safe 0 -i lista_unir.txt -c copy unido.mp4
"""
import argparse, glob, math, os, re, shutil, subprocess, sys

SIN_VENTANA = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
MB = 1000 * 1000


def herramienta(nombre):
    f = shutil.which(nombre)
    if not f:
        sys.exit(f'No encuentro {nombre}. Instala ffmpeg (instalar.bat lo hace) y vuelve a probar.')
    return f


def barra(hecho, total, texto=''):
    p = 100 if total <= 0 else min(100, int(hecho * 100 / total))
    print(f'\r  [{"#" * (p // 4)}{"." * (25 - p // 4)}] {p:3d} %  {texto}   ', end='', flush=True)


def leer_paquetes(video):
    """Lista (bytes acumulados, segundo) en cada cuadro clave del video, en el orden en que están en el archivo."""
    cmd = [herramienta('ffprobe'), '-v', 'error', '-show_entries', 'packet=codec_type,pts_time,dts_time,size,flags',
           '-of', 'csv=p=0', video]
    claves, acumulado, ultimo = [], 0, 0.0
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, **SIN_VENTANA)
    total = os.path.getsize(video)
    for n, linea in enumerate(proc.stdout):
        c = linea.strip().split(',')
        if len(c) < 5:
            continue
        tipo, pts, dts, tam, banderas = c[0], c[1], c[2], c[3], c[4]
        try:
            acumulado += int(tam)
        except ValueError:
            continue
        if tipo == 'video' and 'K' in banderas:
            t = pts if pts not in ('', 'N/A') else dts
            try:
                t = float(t)
            except ValueError:
                continue
            claves.append((acumulado - int(tam), t))  # bytes ANTES de este cuadro clave
        if n % 20000 == 0:
            barra(acumulado, total, 'leyendo el video')
    proc.wait()
    barra(1, 1, 'leyendo el video')
    print()
    return claves, acumulado


def elegir_cortes(claves, limite):
    """Segundos donde cortar: el último cuadro clave antes de llegar al límite de cada parte."""
    claves = sorted(claves, key=lambda x: x[1])
    cortes, inicio, previo = [], 0, None
    for b, t in claves:
        if t <= 0.05:
            continue
        if b - inicio > limite:
            corte = previo or (b, t)  # sin cuadro clave previo en la parte: se corta aquí igual
            cortes.append(corte[1])
            inicio = corte[0]
            previo = (b, t) if corte != (b, t) else None
        else:
            previo = (b, t)
    return cortes


def cortar(video, cortes, carpeta, base, ext):
    patron = os.path.join(carpeta, f'{base}_parte%02d{ext}')
    cmd = [herramienta('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', '-i', video,
           '-map', '0:v', '-map', '0:a?', '-c', 'copy', '-map_metadata', '0',
           '-f', 'segment', '-reset_timestamps', '1', '-segment_start_number', '1']
    if cortes:
        cmd += ['-segment_times', ','.join(f'{t:.6f}' for t in cortes)]
    else:
        cmd += ['-segment_time', '999999']
    if ext.lower() in ('.mp4', '.mov', '.m4v'):
        cmd += ['-segment_format_options', 'movflags=+faststart']
    cmd.append(patron)
    r = subprocess.run(cmd, capture_output=True, text=True, **SIN_VENTANA)
    if r.returncode != 0:
        sys.exit('ffmpeg no pudo cortar el video:\n' + r.stderr[-1500:])
    return sorted(glob.glob(os.path.join(carpeta, f'{base}_parte[0-9][0-9]{ext}')))


VIDEOS = ('.mp4', '.mov', '.mkv', '.m4v', '.avi', '.webm', '.mts', '.m2ts', '.ts', '.wmv', '.flv', '.3gp')


def buscar(ruta):
    """La ruta tal como la pegó el usuario -> lista de videos. Acepta ruta sin extensión (Windows la oculta),
    comillas sobrantes y carpetas (devuelve los videos que hay dentro)."""
    ruta = os.path.abspath(os.path.expanduser(ruta.strip().strip('"').strip("'").strip()))
    if os.path.isfile(ruta):
        return [ruta]
    if os.path.isdir(ruta):
        vids = sorted(os.path.join(ruta, f) for f in os.listdir(ruta)
                      if os.path.splitext(f)[1].lower() in VIDEOS and os.path.isfile(os.path.join(ruta, f)))
        print(f'Es una carpeta. Videos dentro: {len(vids)}')
        for v in vids:
            print(f'  {os.path.basename(v)}   {os.path.getsize(v) / MB:.0f} MB')
        return vids
    carpeta, nombre = os.path.split(ruta)
    if os.path.isdir(carpeta):  # sin extensión: busca nombre.mp4, nombre.MOV, ...
        n = nombre.lower()
        hallados = [os.path.join(carpeta, f) for f in os.listdir(carpeta)
                    if os.path.splitext(f)[0].lower() == n and os.path.splitext(f)[1].lower() in VIDEOS]
        if hallados:
            return sorted(hallados)
    return []


def dividir(video, max_mb=450.0):
    video = os.path.abspath(video)
    tam = os.path.getsize(video)
    base, ext = os.path.splitext(os.path.basename(video))
    base = re.sub(r'[<>:"/\\|?*]', '', base).strip() or 'video'
    ext = ext or '.mp4'
    print(f'\nVideo: {video}\nTamaño: {tam / MB:.0f} MB   ·   máximo por parte: {max_mb:.0f} MB')
    if tam <= max_mb * MB:
        print('Este video ya entra en una sola parte: no hace falta dividirlo.')
        return []
    carpeta = os.path.join(os.path.dirname(video), f'{base}_PARTES')
    os.makedirs(carpeta, exist_ok=True)
    for viejo in glob.glob(os.path.join(carpeta, f'{base}_parte*')):  # partes de una vez anterior
        os.remove(viejo)
    claves, _ = leer_paquetes(video)
    margen = 0.96
    for intento in range(4):
        cortes = elegir_cortes(claves, max_mb * MB * margen)
        print(f'Cortando en {len(cortes) + 1} partes (sin volver a codificar)...')
        partes = cortar(video, cortes, carpeta, base, ext)
        grande = [p for p in partes if os.path.getsize(p) > max_mb * MB]
        if not grande:
            break
        for p in partes:
            os.remove(p)
        margen -= 0.06
        print('Una parte salió un poco grande; corto otra vez con más margen.')
    else:
        sys.exit('No pude dejar todas las partes bajo el límite.')
    n = len(partes)
    finales = []
    for i, p in enumerate(partes, 1):  # parte01 -> parte01de03
        nuevo = os.path.join(carpeta, f'{base}_parte{i:02d}de{n:02d}{ext}')
        os.replace(p, nuevo)
        finales.append(nuevo)
    with open(os.path.join(carpeta, 'lista_unir.txt'), 'w', encoding='utf-8') as fh:
        for p in finales:
            fh.write("file '" + os.path.basename(p).replace("'", "'\\''") + "'\n")
    with open(os.path.join(carpeta, 'LEEME.txt'), 'w', encoding='utf-8') as fh:
        fh.write(f'Video original: {os.path.basename(video)} ({tam / MB:.0f} MB)\n'
                 f'Partes: {n} (cada una de menos de {max_mb:.0f} MB, misma calidad, cortes en cuadro clave)\n\n')
        for p in finales:
            fh.write(f'  {os.path.basename(p)}   {os.path.getsize(p) / MB:.0f} MB\n')
        fh.write('\nPara volver a unirlas (en esta carpeta):\n'
                 f'  ffmpeg -f concat -safe 0 -i lista_unir.txt -c copy "{base}_UNIDO{ext}"\n'
                 'o: python dividir/dividir.py --unir "<esta carpeta>"\n')
    print(f'\nListo: {n} partes en\n  {carpeta}')
    for p in finales:
        print(f'  {os.path.basename(p)}   {os.path.getsize(p) / MB:.0f} MB')
    return finales


def unir(carpeta, salida=None):
    """Une las partes «..._parteXXdeYY.ext» de una carpeta, en orden, sin volver a codificar."""
    carpeta = os.path.abspath(carpeta)
    partes = sorted(f for f in os.listdir(carpeta) if re.search(r'_parte\d+de\d+\.\w+$', f))
    if not partes:
        sys.exit(f'No hay partes «_parteXXdeYY» en {carpeta}')
    m = re.match(r'(.*)_parte\d+de(\d+)(\.\w+)$', partes[0])
    base, total, ext = m.group(1), int(m.group(2)), m.group(3)
    if len(partes) != total:
        sys.exit(f'Faltan partes: hay {len(partes)} de {total}.')
    lista = os.path.join(carpeta, 'lista_unir.txt')
    with open(lista, 'w', encoding='utf-8') as fh:
        for p in partes:
            fh.write("file '" + p.replace("'", "'\\''") + "'\n")
    salida = salida or os.path.join(carpeta, f'{base}_UNIDO{ext}')
    r = subprocess.run([herramienta('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0',
                        '-i', lista, '-map', '0', '-c', 'copy', '-movflags', '+faststart', salida],
                       capture_output=True, text=True, **SIN_VENTANA)
    if r.returncode != 0:
        sys.exit('ffmpeg no pudo unir:\n' + r.stderr[-1500:])
    print(f'Unido: {salida}')
    return salida


def main():
    ap = argparse.ArgumentParser(description='Divide videos grandes en partes sin perder calidad.')
    ap.add_argument('videos', nargs='*')
    ap.add_argument('--max-mb', type=float, default=450)
    ap.add_argument('--unir', metavar='CARPETA')
    a = ap.parse_args()
    if a.unir:
        unir(a.unir)
        return
    if not a.videos:
        ap.error('falta el video')
    for r in a.videos:
        vids = buscar(r)
        if not vids:
            print(f'No encuentro ese video: {r}\nTip: arrastra el archivo encima de DIVIDIR_VIDEO.bat, así la ruta sale completa.')
            continue
        for v in vids:
            dividir(v, a.max_mb)


if __name__ == '__main__':
    main()
