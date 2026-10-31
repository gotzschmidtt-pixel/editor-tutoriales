"""Regla de fabian (31/10/2026), para todos los videos: pocas emociones en la voz. El bloque 1 de Movistar salió con 13
etiquetas ([laughs], [sighs], [whispers]…) en 1:41 y el avatar de HeyGen exageró las caras («se ve raro»).

moderar(texto) deja como máximo 3 etiquetas por minuto de voz (≈ 3 cada 150 palabras), nunca dos seguidas (a menos de
12 palabras), sin [excited] en la primera frase si ya empieza con «¡…!», [chuckles] en vez de [laughs] y [whispers] una
sola vez en todo el video. Devuelve (texto, cuántas quitó o cambió). El resto queda narrado natural.
"""
import re

ETIQUETA = re.compile(r'\[([a-záéíóúñ ,]+)\]\s*', re.I)
POR_MINUTO, PALABRAS_MINUTO, SEPARACION = 3, 150, 12
_SUSURROS = {'usados': 0}  # en todo el video (una corrida)


def moderar(texto, primera_del_video=False):
    sin = ETIQUETA.sub('', texto)
    palabras = len(sin.split())
    limite = max(1, int(palabras * POR_MINUTO / PALABRAS_MINUTO + 0.5))
    salida, quitadas, puestas, ultima, pos = [], 0, 0, -SEPARACION - 1, 0
    for m in ETIQUETA.finditer(texto):
        antes = texto[pos:m.start()]
        salida.append(antes)
        pos = m.end()
        n_palabra = len(ETIQUETA.sub('', ''.join(salida)).split())
        tag = m.group(1).strip().lower()
        resto = texto[m.end():].lstrip()
        if tag == 'laughs':
            tag, quitadas = 'chuckles', quitadas + 1
        if (tag == 'excited' and n_palabra == 0 and resto.startswith('¡')) \
                or (tag == 'whispers' and _SUSURROS['usados'] >= 1) \
                or puestas >= limite or n_palabra - ultima < SEPARACION:
            quitadas += 1
            continue
        if tag == 'whispers':
            _SUSURROS['usados'] += 1
        salida.append(f'[{tag}] ')
        puestas, ultima = puestas + 1, n_palabra
    salida.append(texto[pos:])
    return re.sub(r'[ \t]{2,}', ' ', ''.join(salida)), quitadas


if __name__ == '__main__':  # prueba rápida: python voz/emociones.py
    t = ('[excited] ¡Movistar se va! [laughs] Y no, no es un chisme. [sighs] El matrimonio con el Estado. [excited] ¡Y la boda! '
         '[chuckles] Ah, y el socio. [whispers] Spoiler: menos. [serious] La llamada. [laughs] Veinte años. [excited] ¡Quédate!')
    nuevo, n = moderar(t)
    assert nuevo.count('[') <= 3 and '[laughs]' not in nuevo and not nuevo.startswith('[excited]'), nuevo
    print(n, 'quitadas →', nuevo)
