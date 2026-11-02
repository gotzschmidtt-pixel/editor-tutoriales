"""Respaldo antes de «🔁 Rehacer video» (pedido de fabian, 02/11/2026: pulsó «Actualizar» y la app borró el FINAL con los
arreglos puestos por fuera). Antes de borrar nada, los finales se copian a FINAL_antes_rehacer_<fecha>_<nombre>.mp4, que
el rehacer no toca. También dice qué capas puestas por fuera se vuelven a poner solas y cuáles no.
"""
import glob, json, os, shutil, time

FINALES = ('FINAL.mp4', 'FINAL_EN.mp4', 'FINAL_PT.mp4', 'FINAL_480p.mp4', 'FINAL_EN_480p.mp4', 'FINAL_720p.mp4', 'FINAL_1080p.mp4')
PREFIJO = 'FINAL_antes_rehacer_'


def respaldar(d, fecha=None, finales=FINALES):
    """Copia los finales que haya (o solo los de `finales`). Devuelve los nombres de las copias."""
    fecha = fecha or time.strftime('%Y%m%d_%H%M')
    hechas = []
    for f in finales:
        src = os.path.join(d, f)
        if os.path.isfile(src):
            dst, k = os.path.join(d, f'{PREFIJO}{fecha}_{f}'), 1
            while os.path.exists(dst):  # dos copias en el mismo minuto: la segunda no pisa la primera
                k += 1
                dst = os.path.join(d, f'{PREFIJO}{fecha}_{k}_{f}')
            shutil.copy2(src, dst)
            hechas.append(os.path.basename(dst))
    return hechas


MARCA = '.final_de_la_app.json'  # tamaño y fecha del último FINAL.mp4 que armó la app (y que nadie tocó después)


def anotar_final(d, f='FINAL.mp4'):
    """Anota el FINAL que la app acaba de armar. Mientras siga igual no hace falta copiarlo antes de rehacerlo: la app lo
    vuelve a armar sola. Así «✨ Agregar extras» no suma una copia de varios GB en cada vuelta."""
    try:
        st = os.stat(os.path.join(d, f))
        with open(os.path.join(d, MARCA), 'w', encoding='utf-8') as fh:
            json.dump({'archivo': f, 'tam': st.st_size, 'fecha': st.st_mtime}, fh)
    except OSError:
        pass


def tocado_por_fuera(d, f='FINAL.mp4'):
    """True si el FINAL no es el que dejó la app (le hiciste arreglos a mano, o no hay anotación): ese sí se copia."""
    try:
        st = os.stat(os.path.join(d, f))
        with open(os.path.join(d, MARCA), encoding='utf-8') as fh:
            m = json.load(fh)
        return not (m.get('archivo') == f and m.get('tam') == st.st_size and float(m.get('fecha')) == st.st_mtime)
    except (OSError, ValueError, TypeError, AttributeError):
        return True


def capas_por_fuera(d):
    """Lo que se puso encima del video fuera de los pasos de la app: {'solas': [...], 'a_mano': [...]}.
    «solas» se vuelven a poner en «Video final sin tráiler»; «a_mano» no, y quedan solo en la copia de respaldo."""
    solas, a_mano = [], []
    try:
        fijo = json.load(open(os.path.join(d, 'inicio_fijo.json'), encoding='utf-8'))
        solas.append(f"inicio fijo ({fijo.get('video', '')}, hasta {fijo.get('hasta', '?')} s)")
    except (OSError, ValueError):
        pass
    if os.path.exists(os.path.join(d, 'difuminar_datos.json')):
        solas.append('datos difuminados (difuminar_datos.json)')
    # versiones en otro idioma y arreglos guardados como FINAL_antes_*.mp4: señal de que hubo cambios a mano encima del final
    if os.path.exists(os.path.join(d, 'FINAL_EN.mp4')):
        a_mano.append('la versión en inglés (FINAL_EN.mp4) no se rehace sola')
    arreglos = sorted({os.path.basename(f)[len('FINAL_antes_'):-4] for f in glob.glob(os.path.join(d, 'FINAL_antes_*.mp4'))
                       if not os.path.basename(f).startswith(PREFIJO)})
    if arreglos:
        a_mano.append('arreglos hechos por fuera del final: ' + ', '.join(arreglos))
    return {'solas': solas, 'a_mano': a_mano}
