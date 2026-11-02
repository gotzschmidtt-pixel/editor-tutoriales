"""Baja una sola vez lo que la app usa y que no viene con pip ni con npm, para que en esta PC (o en otra, copiando la
carpeta entera con descargas_app) funcione sin esperar la descarga la primera vez. Lo llaman instalar.bat y
guardar_para_otra_pc.bat.

  - Whisper large-v3-turbo (~1,6 GB): transcribir en tu PC             → descargas_app/modelos/whisper
  - Detector de objetos YOLOX (35 MB) y de caras YuNet (230 KB)        → descargas_app/modelos
  - Real-ESRGAN (45 MB): «✨ Mejorar imagen»                            → descargas_app/programas/realesrgan
  - DeepFilterNet (27 MB) y RNNoise (300 KB): «🎙 Limpiar voz»         → descargas_app/programas y modelos
Todo es gratis y no gasta créditos. Si algo no se puede bajar, lo dice y sigue: la app lo vuelve a intentar la primera
vez que lo use.

Uso: python instalador/bajar_todo.py [--sin-whisper]
"""
import os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for carpeta in ('deteccion', 'montaje', 'mejorar', 'limpieza'):
    sys.path.insert(0, os.path.join(RAIZ, carpeta))


def whisper():
    from faster_whisper import download_model
    download_model('large-v3-turbo', cache_dir=os.path.join(RAIZ, 'descargas_app', 'modelos', 'whisper'))  # la misma carpeta que usa transcribir.py
    return True


def detector():
    import deteccion
    return deteccion.disponible() is not None


def caras():
    import montaje
    return montaje.detector_caras() is not None


def real_esrgan():
    import mejorar
    return mejorar.programa() is not None


def deep_filter():
    import limpiar_voz
    return limpiar_voz.deep_filter() is not None


def rnnoise():
    import limpiar_voz
    limpiar_voz.bajar(limpiar_voz.RNN_URL, os.path.join(limpiar_voz.MODELOS, 'rnnoise_sh.rnnn'), 'el modelo de RNNoise (300 KB)')
    return True


def main():
    pasos = [('Detector de teléfono, laptop y manos (YOLOX, 35 MB)', detector), ('Detector de caras (YuNet, 230 KB)', caras),
             ('Real-ESRGAN para «Mejorar imagen» (45 MB)', real_esrgan), ('DeepFilterNet para «Limpiar voz» (27 MB)', deep_filter),
             ('RNNoise para «Limpiar voz» (300 KB)', rnnoise)]
    if '--sin-whisper' not in sys.argv:
        pasos.insert(0, ('Whisper large-v3-turbo para transcribir en tu PC (~1,6 GB, la primera vez tarda)', whisper))
    faltan = []
    for nombre, paso in pasos:
        print(f'· {nombre}…', flush=True)
        try:
            ok = paso()
        except Exception as e:  # uno que falla no frena los demás: la app lo vuelve a intentar al usarlo
            print(f'  no se pudo ({type(e).__name__}: {str(e)[:200]})', flush=True)
            ok = False
        if ok:
            print('  listo', flush=True)
        else:
            faltan.append(nombre)
    if faltan:
        print('Quedó sin bajar (se intenta solo la primera vez que lo uses): ' + '; '.join(faltan), flush=True)
    else:
        print('Todo bajado: la app no tiene que bajar nada más la primera vez.', flush=True)


if __name__ == '__main__':
    main()
