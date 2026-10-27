"""El texto de un bloque tal como se manda a ElevenLabs (lo usan voz.py y montaje.py)."""
import re


def texto_voz(t):
    """El texto tal como se manda a ElevenLabs: sin espacios antes de la puntuación («herramienta , UnlockTool»), sin «;»
    sueltos ni marcas de formato (*, #, `), con mayúscula al empezar y punto al final. El guion no se toca: solo cambia
    lo que se lee, así la voz no hace pausas raras ni lee símbolos."""
    t = re.sub(r'[*#`]+', '', str(t or ''))
    t = re.sub(r'\s+([,.;:!?…])', r'\1', t)
    t = re.sub(r'\s*;\s*', ', ', t)
    t = re.sub(r',(?=[^\s\d])', ', ', t)  # «hola,que» → «hola, que» (no toca 27,5 ni xiaomiunlock.com)
    t = re.sub(r',\s*([.!?…])', r'\1', t)
    t = re.sub(r'\s+', ' ', t).strip().rstrip(',:').strip()
    if t and t[0].islower():
        t = t[0].upper() + t[1:]
    if t and t[-1] not in '.!?…»"':
        t += '.'
    return t
