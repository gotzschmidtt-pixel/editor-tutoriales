"""Velocidad de los pasos clave (fabian, 03/11/2026, respuesta 8). A «¿Los pasos clave siempre a velocidad normal? (Solo el
segundo exacto del dato: PIN, key, botones)» contestó «SÍ, INCLUSIVE PASOS CLAVE PODRÍAMOS HACERLO UN POQUITÍN MÁS LENTO».

- El momento exacto del dato (cuando escribes o pegas la key, el PIN, el código o la contraseña, o aprietas el botón que
  hay que tocar) NUNCA va acelerado: va a ×0,9 (VEL_DATO), un poquito más lento que lo grabado, para que se lea.
  La app lo saca de tu transcripción, porque lo dices mientras lo haces («pegamos la key», «volumen más y power»): desde
  1 s antes de que lo dices hasta 2 s después (lo que escribes o el menú que sale tarda un poco en verse). Queda en el
  montaje del bloque como "datos": [[desde, hasta], …] (segundos de tu grabación). Lo que dices como aviso o hipótesis
  («no toques ningún botón», «si sueltas el botón…») no cuenta.
- El resto del bloque puede ir más rápido, hasta su tope de siempre (×1,5 lo demás de un paso clave, ×2 un paso de
  configuración, ×6 una espera). "velocidad" sigue siendo la del tramo entero (el bloque dura tramo / velocidad, como
  siempre): el montaje reparte ese tiempo, el dato a ×0,9 y lo demás un poco más rápido, así la voz, los subtítulos y las
  etiquetas no se mueven. Si lo demás no alcanza sin pasar su tope, tope() baja la velocidad del bloque y el bloque se
  alarga: eso lo hacen la revisión del guion (ia.py) y «Generar voz» (voz.ajustar_guion), que vuelven a calcular dónde
  empieza cada bloque (inicio_min), igual que después de «Alinear».
- Un paso clave en el que no se encuentra el dato va ENTERO sin acelerar (×1 como máximo; antes ×1,5) y, si su voz no
  cabe, primero va a ×0,9 y recién después queda la pausa que falte (piso(), en voz.frenar_tramo).
- Con tu cara (×1 justo: ni acelerada ni en cámara lenta), en un «⭐ corte importante» (entero a ×1), en el gancho y en
  un tramo sin voz no se marca nada.

Por qué ×0,9 y no ×0,85: a ×0,9 las manos y el puntero se siguen viendo naturales (un 10 % no se nota como cámara lenta)
y da un 11 % más de tiempo para leer; a ×0,85 ya se nota lento y, como el montaje repite cuadros en vez de mezclarlos (así
la key no sale doble), uno de cada 6 cuadros saldría repetido (a ×0,9, uno de cada 9) y el tecleo se vería a saltitos.
Y cada paso clave se alarga menos (un dato de 3 s dura 3,3 s, no 3,5 s).
"""
import json, math, os, re, unicodedata

VEL_DATO = 0.9      # el momento exacto del dato: un poquito más lento que lo grabado
VEL_CLAVE = 1.0     # un paso clave sin el dato ubicado: entero, nunca acelerado (antes ×1,5)
RESTO_CLAVE = 1.5   # lo demás de un paso clave cuyo dato sí se ubicó (el tope de antes)
VEL_PASO = 2.0      # paso de configuración (seleccionar, activar, verificar)
VEL_MAX = 6.0       # esperas y cargas
ANTES, DESPUES = 1.0, 2.0  # alrededor de lo que dices: lo haces casi a la vez, y el resultado tarda un poco en verse
JUNTAR = 1.0        # dos datos a menos de 1 s quedan en uno solo
BORDE = 0.6         # un dato a menos de 0,6 s del borde del tramo llega hasta el borde (sin pedazos de un par de cuadros)
MINIMO = 0.4        # lo que queda de un dato cortado por el borde del tramo, si es menos, no cuenta

# lo que dices cuando pones el dato o aprietas el botón (palabra por palabra de la transcripción, sin tildes): lo que haces
# (pegar, escribir, apretar un botón)…
HACER = re.compile(r'^(escrib\w*|tecle\w*|digit\w*|peg(a|ar|amos|as|ue|uen|o|ando)|copi(a|ar|amos|o|ando)|ingres\w*|'
                   r'introduc\w*|volumen|power|presion\w*|puls(a|ar|amos|as|e|en|o|ando|ado)|clic\w*|omit\w*|'
                   # (revisión, 03/11/2026) los botones que hay que tocar: «tocamos aceptar», «oprime», «apretamos»
                   r'toc(a|ar|amos|as|o|an|ando|ue|uen|amos)|oprim\w*|apret\w*|aprieta\w*|aprieten)$')
# (revisión, 03/11/2026) «le damos a siguiente», «dale en aceptar», «damos clic»: dar + en/a/clic es apretar un botón
DAR = re.compile(r'^(damos|dar|dale|demos|damosle|da|dan|denle|doy)$')
DAR_SIGUE = re.compile(r'^(en|a|al|clic\w*|click\w*|aceptar|siguiente|ok|continuar|permitir|omitir|si)$')
# (revisión, 03/11/2026) lo que suena a hacer y no lo es: el llamado al WhatsApp («escríbenos», 185 veces en sus
# transcripciones), «se queda pegado», «copia de seguridad», «ingresar a nuestra página»
NO_HACER = re.compile(r'^(escrib\w*nos|escrib\w*me|escrib\w*nme)$')
NO_SIGUE = {'copi': (('de', 'seguridad'),), 'ingres': (('a', 'nuestra'), ('a', 'nuestro'), ('al', 'canal'), ('a', 'la', 'pagina'),
                                                        ('a', 'mi'), ('a', 'la', 'web'), ('al', 'link'), ('al', 'enlace'))}
# …y el dato mismo. Solo con su nombre («la key la compran en la página») puede ser una explicación: cuenta en un paso
# clave, no en una espera
DATO = re.compile(r'^(keys?|clave|codigo|pin|contrasena\w*|password|imei|serial|token)$')
NO_ES = re.compile(r'^(no|ni|nunca|sin|si)$')  # «no toques ningún botón», «si sueltas el botón…»: no lo está haciendo


def _normal(s):
    s = unicodedata.normalize('NFKD', str(s).lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '', s)


def momentos(d):
    """[[desde, hasta, haces]] de tu grabación donde pones un dato o aprietas un botón, según tu transcripción
    (transcripcion.json del proyecto); haces = True si dices lo que haces (pegar, escribir, apretar), False si solo nombras
    el dato. Vacío si no hay transcripción."""
    try:
        pal = json.load(open(os.path.join(d, 'transcripcion.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return []
    pal = sorted((w for w in pal if isinstance(w, dict) and isinstance(w.get('inicio'), (int, float))),
                 key=lambda w: w['inicio']) if isinstance(pal, list) else []
    out = []
    for k, w in enumerate(pal):
        palabra = _normal(w.get('texto', ''))
        sigue = [_normal(x.get('texto', '')) for x in pal[k + 1:k + 4]]
        haces = bool(HACER.match(palabra)) and not NO_HACER.match(palabra)
        if haces:
            for raiz, frases in NO_SIGUE.items():
                if palabra.startswith(raiz) and any(tuple(sigue[:len(fr)]) == fr for fr in frases):
                    haces = False
        if not haces and DAR.match(palabra) and sigue and DAR_SIGUE.match(sigue[0]):
            haces = True
        if not (haces or DATO.match(palabra)):
            continue
        antes = []  # lo dicho antes en la misma frase (hasta 4 palabras, hasta una coma o un punto)
        for x in reversed(pal[max(0, k - 4):k]):
            if re.search(r'[.,;:!?]$', str(x.get('texto', '')).strip()):
                break
            # (revisión, 03/11/2026) «sí» con tilde («ahora sí pegamos la key») no es el «si» de «si sueltas el botón…»
            antes.append('' if 'í' in str(x.get('texto', '')).lower() else _normal(x.get('texto', '')))
        if any(NO_ES.match(x) for x in antes if x):
            continue
        a, z = w['inicio'] - ANTES, max(w['inicio'], float(w.get('fin') or w['inicio'])) + DESPUES
        if out and a <= out[-1][1] + JUNTAR:
            out[-1][1], out[-1][2] = max(out[-1][1], z), out[-1][2] or haces
        else:
            out.append([a, z, haces])
    return [[round(max(0.0, a), 2), round(z, 2), h] for a, z, h in out]


def ventanas(mo):
    """Los datos del montaje dentro de su tramo: [(desde, hasta)] ordenados y juntos, en segundos de la grabación."""
    a, z = mo.get('src_inicio'), mo.get('src_fin')
    if not isinstance(a, (int, float)) or not isinstance(z, (int, float)) or z <= a or not str(mo.get('modo', '')).startswith('lento'):
        return []
    if mo.get('sin_voz'):  # (revisión, 03/11/2026) le quitaste la voz en el editor: los datos de antes ya no cuentan
        return []
    out = []
    for x in mo.get('datos') or []:
        try:
            x0, x1 = max(a, float(x[0])), min(z, float(x[1]))
        except (TypeError, ValueError, IndexError):
            continue
        if x0 - a < BORDE:
            x0 = a
        if z - x1 < BORDE:
            x1 = z
        if x1 - x0 < MINIMO:
            continue
        if out and x0 <= out[-1][1] + JUNTAR:
            out[-1] = (out[-1][0], max(out[-1][1], x1))
        else:
            out.append((x0, x1))
    return out


def marcar(bloques, lista):
    """Pone en el montaje de cada bloque los datos que caen en su tramo ("datos") y quita los que ya no caen. En un paso
    clave cuenta también el dato solo nombrado («el PIN: uno, dos, tres, cuatro»); en los demás, solo lo que haces.
    Devuelve los id de los bloques que cambiaron."""
    cambiados = []
    for b in bloques:
        mo = b.get('montaje') or {}
        antes = mo.get('datos')
        a, z = mo.get('src_inicio'), mo.get('src_fin')
        nuevos = []
        if (str(mo.get('modo', '')).startswith('lento') and isinstance(a, (int, float)) and isinstance(z, (int, float))
                and str(b.get('texto') or '').strip() and not (b.get('gancho') or mo.get('cara') or mo.get('importante')
                                                                or mo.get('sin_voz'))):
            clave = mo.get('critico') or str(b.get('tipo', '')).lower().startswith(('crit', 'clave'))  # como ia.es_critico
            nuevos = [[x[0], x[1]] for x in lista if x[0] < z and x[1] > a and (clave or len(x) < 3 or x[2])]
            nuevos = [[x0, x1] for x0, x1 in ventanas(dict(mo, datos=nuevos))]
            nuevos = [[round(x0, 2), round(x1, 2)] for x0, x1 in nuevos]
        if nuevos:
            mo['datos'] = nuevos
        else:
            mo.pop('datos', None)
        if (antes or None) != (mo.get('datos') or None):
            cambiados.append(b.get('id'))
    return cambiados


def resto_max(mo):
    """Lo más que se acelera lo que NO es el dato: ×1 con tu cara o en un ⭐, ×1,5 en un paso clave, ×2 en uno de
    configuración y ×6 en lo demás."""
    if mo.get('importante') or mo.get('cara'):
        return 1.0
    return RESTO_CLAVE if mo.get('critico') else VEL_PASO if mo.get('paso') else VEL_MAX


def _abajo(x):
    return math.floor(round(x * 100, 6)) / 100


def _arriba(x):
    return math.ceil(round(x * 100, 6)) / 100


def tope(mo):
    """Lo más rápido que puede ir el tramo entero (su "velocidad"), con las reglas de fabian: ×1 con tu cara o en un ⭐;
    un paso clave sin el dato ubicado, ×1 (nunca acelerado); con datos, lo que deja el dato a ×0,9 y lo demás a su tope."""
    resto = resto_max(mo)
    if mo.get('importante') or mo.get('cara'):
        return 1.0
    ws = ventanas(mo)
    if not ws:
        return VEL_CLAVE if mo.get('critico') else resto
    largo_t = mo['src_fin'] - mo['src_inicio']
    w = sum(x1 - x0 for x0, x1 in ws)
    return _abajo(largo_t / (w / VEL_DATO + (largo_t - w) / resto))


def piso(mo):
    """Lo más despacio que se puede poner el tramo para no dejar una pausa al final (voz.frenar_tramo): ×1 en general;
    en un paso clave sin el dato ubicado, ×0,9; con datos, lo que deja el dato a ×0,9 y lo demás a ×1."""
    if mo.get('cara'):
        return 1.0
    ws = ventanas(mo)
    if not ws:
        return VEL_DATO if mo.get('critico') else 1.0
    largo_t = mo['src_fin'] - mo['src_inicio']
    w = sum(x1 - x0 for x0, x1 in ws)
    return min(1.0, _arriba(largo_t / (w / VEL_DATO + (largo_t - w))))


def piezas(mo):
    """[(desde, hasta, velocidad)] del tramo «lento», de punta a punta: el dato a ×0,9 y lo demás más rápido, de modo que
    el tramo dure lo mismo que a su "velocidad" (tramo / velocidad). Sin datos, o si el tramo ya va a ×0,9 o más lento,
    una sola pieza a su velocidad. Si lo demás no alcanza a compensar sin pasar su tope, el dato va lo más despacio que
    se pueda (la revisión del guion y «Generar voz» bajan antes la velocidad del bloque para que eso no pase)."""
    a, z = float(mo['src_inicio']), float(mo['src_fin'])
    v = float(mo.get('velocidad') or 1)
    ws = ventanas(mo)
    if not ws or v <= VEL_DATO + 1e-9 or z <= a:
        return [(a, z, v)]
    largo = (z - a) / v
    w = sum(x1 - x0 for x0, x1 in ws)
    r = (z - a) - w
    if r <= 1e-6:
        return [(a, z, v)]
    vd, t_resto = VEL_DATO, largo - w / VEL_DATO
    rmax = max(resto_max(mo), v)
    if t_resto <= 1e-6 or r / t_resto > rmax:  # lo demás a su tope y el dato lo más despacio que se pueda
        t_resto = r / rmax
        vd = w / (largo - t_resto) if largo - t_resto > 1e-6 else v
        if vd > 1 + 1e-9:
            # ni así: el bloque va más rápido de lo que debería (un guion de antes). El dato manda: lo demás va todavía
            # más rápido (hasta ×6) para que el dato no pase de ×1; si ni así, el dato va lo menos acelerado posible
            rmax = max(VEL_MAX, v)
            t_resto = max(largo - w, r / rmax)
            vd = w / (largo - t_resto) if largo - t_resto > 1e-6 else v
        if vd >= v - 1e-6:
            return [(a, z, v)]
    vr = r / t_resto
    out, t = [], a
    for x0, x1 in ws:
        if x0 > t + 1e-9:
            out.append((t, x0, vr))
        out.append((x0, x1, vd))
        t = x1
    if z > t + 1e-9:
        out.append((t, z, vr))
    return out


def en_grabacion(mo, t):
    """El segundo de la grabación que se ve t s después de que empieza el tramo (sin pasar su final)."""
    s = 0.0
    ps = piezas(mo)
    for x0, x1, v in ps:
        largo = (x1 - x0) / v
        if t <= s + largo + 1e-9:
            return x0 + max(0.0, t - s) * v
        s += largo
    return ps[-1][1]


def en_bloque(mo, src):
    """Lo contrario de en_grabacion: cuántos segundos después de que empieza el tramo se ve el segundo src de la grabación."""
    s = 0.0
    for x0, x1, v in piezas(mo):
        if src <= x1 + 1e-9:
            return s + max(0.0, src - x0) / v
        s += (x1 - x0) / v
    return s
