"""Las reglas de fabian para los títulos de YouTube (videos y Shorts) y los textos de las miniaturas (03/11/2026), en un
solo lugar para que todas las partes de la app hagan lo mismo:

- anio(): el año de títulos y miniaturas, el mismo en los dos. Es el de hoy hasta el 14 de diciembre y el siguiente desde
  el 15 de diciembre (en noviembre nadie busca «2027»). Se calcula con la fecha, nunca a mano.
- necesita_pc(marca, texto): por PROCESO, con mis_conocimientos/procesos_pc.json. Hoy SIN PC solo van la cuenta Mi de
  Xiaomi (basta el unlock code o el IMEI) y la liberación de bandas de iPhone (basta el IMEI y el número de serie); todo lo
  demás usa PC (Honor, Samsung, Motorola, Xiaomi cuenta Google, iCloud…). Si no se reconoce el proceso, usa PC: nunca se
  promete «SIN PC» de más. El formato viejo de ese archivo ({"honor": true}, por marca) se sigue leyendo.
- revisar_titulo(): lo que la app corrige sola en un título NUEVO (los publicados no se tocan), con un aviso por cada cosa:
  · «Sin PC» solo si el proceso no usa PC y solo AL INICIO del título («Sin PC Avanzada» no es «Sin PC»: se deja);
  · Honor sin «Todos los Modelos» (ni «All Models» ni «Todos os Modelos»);
  · «Gratis» solo si el proyecto dice que el método es gratis (la app nunca lo pone por su cuenta);
  · el año, el de anio().
- para_ia(): las mismas reglas en texto, para el pedido a la IA (también: el título puede empezar con dos verbos
  separados por coma, «Quitar, Eliminar Cuenta Google…»).
"""
import datetime, json, os, re, unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESOS_PC = os.path.join(RAIZ, 'mis_conocimientos', 'procesos_pc.json')

# una marca con sus otros nombres (como en conocimiento.ALIAS; miniatura.py dice IPHONE donde conocimiento dice APPLE)
MARCAS = {'iphone': ('iphone', 'apple', 'ios', 'icloud', 'ipad'), 'xiaomi': ('xiaomi', 'redmi', 'poco', 'hyperos', 'miui'),
          'motorola': ('motorola', 'moto'), 'samsung': ('samsung', 'galaxy'), 'honor': ('honor', 'magicos'),
          'huawei': ('huawei',)}

# «Sin PC» y sus traducciones; «Sin PC Avanzada» / «Sin PC Básica» no cuentan (lo de Honor: basta una PC sencilla)
SIN_PC = re.compile(r'(?<![\w])(sin|sem|no|without(?: an?)?)\s+(pc|computadora|computador|ordenador|laptop|computer)\b'
                    r'(?:\s*[\U0001F5A5\U0001F4BB]️?)?(?!\s*(avanzad|avançad|advanced|b[aá]sic|basic|sencill|potente))', re.I)
TODOS_MODELOS = re.compile(r'(?<![\w])(para\s+|for\s+|pra\s+)?(todos\s+los\s+modelos|all\s+models|todos\s+os\s+modelos)\b', re.I)
GRATIS_TITULO = re.compile(r'(?<![\w])(100\s*%\s*)?(gratis|gratuit[oa]s?|gr[aá]tis|free)\b', re.I)
ANIO_TITULO = re.compile(r'(?<!\d)20[2-9]\d(?!\d)')
# el proyecto dice que el método es gratis / habla de pagar (sobre el texto sin tildes y en minúsculas)
GRATIS_DICE = re.compile(r'\b(gratis|gratuit[oa]s?|free|sin costo|sin pagar|no (tienes que |hay que |se )?paga\w* nada|'
                         r'no cuesta nada)\b')
PAGO = re.compile(r'\b(dolar|dolares|pagar|pagas|paga|pagan|pago|pagos|pagando|precio|precios|costo|costos|cuesta|'
                  r'cuestan|cobra|cobro|creditos|usd|pesos|soles)\b|\$')


def anio(hoy=None):
    """2026 hasta el 14 de diciembre de 2026; 2027 desde el 15 de diciembre (y así cada año)."""
    hoy = hoy or datetime.date.today()
    return hoy.year + 1 if (hoy.month, hoy.day) >= (12, 15) else hoy.year


def normal(t):
    """minúsculas y sin tildes, para comparar."""
    return ''.join(c for c in unicodedata.normalize('NFKD', str(t or '').lower()) if not unicodedata.combining(c))


def _simple(t):
    return ' ' + re.sub(r'[^a-z0-9]+', ' ', normal(t)).strip() + ' '


def marca_normal(marca):
    """'APPLE', 'IPHONE', 'Redmi'… → 'iphone', 'xiaomi'…; '' si no es una marca conocida (o es «TU CELULAR»)."""
    m = normal(marca).strip()
    return next((k for k, alias in MARCAS.items() if m == k or m in alias), m if m and m != 'tu celular' else '')


def _marca_de_texto(t):
    t = _simple(t)
    return next((k for k, alias in MARCAS.items() if any(f' {a} ' in t for a in alias)), '')


def leer_procesos(archivo=None):
    try:
        datos = json.load(open(archivo or PROCESOS_PC, encoding='utf-8'))
    except (OSError, ValueError):
        datos = {}
    return datos if isinstance(datos, dict) else {}


def proceso(texto='', marca='', datos=None):
    """El proceso del video (un elemento de «procesos» de procesos_pc.json) que más se nombra en el texto, o None. Si dos
    empatan, gana el que usa PC (así nunca se promete «SIN PC» de más)."""
    datos = leer_procesos() if datos is None else datos
    t = _simple(texto)
    m = marca_normal(marca) or _marca_de_texto(texto)
    mejor, puntos = None, 0
    for p in datos.get('procesos') or []:
        if not isinstance(p, dict):
            continue
        marcas = [marca_normal(x) for x in p.get('marcas') or []]
        if marcas and m not in marcas:
            continue
        n = sum(len(re.findall(r'(?<= )' + re.escape(_simple(w).strip()) + r'(?= )', t)) for w in p.get('palabras') or []
                if _simple(w).strip())
        usa_pc = p.get('pc', True) is not False
        if n and (n > puntos or (n == puntos and usa_pc)):
            mejor, puntos = p, n
    return mejor


def necesita_pc(marca='', texto='', datos=None):
    """True salvo que el proceso del video (por el texto) o la marca (formato viejo) estén marcados sin PC."""
    datos = leer_procesos() if datos is None else datos
    p = proceso(texto, marca, datos)
    if p is not None:
        return p.get('pc', True) is not False
    m = normal(marca).strip()
    return datos.get(m, datos.get(marca_normal(m), True)) is not False


def es_gratis(texto):
    """True solo si el proyecto dice que el método es gratis y no habla de pagar (precio, dólares, créditos)."""
    t = normal(texto)
    if not GRATIS_DICE.search(t):
        return False
    return not PAGO.search(GRATIS_DICE.sub(' ', t))


def texto_proyecto(d):
    """Lo que dice el proyecto de su proceso: el nombre, idea.txt y el guion."""
    if not d:
        return ''
    partes = [os.path.basename(os.path.abspath(d))]
    try:
        partes.append(open(os.path.join(d, 'idea.txt'), encoding='utf-8').read()[:3000])
    except OSError:
        pass
    try:
        g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
        partes += [str(b.get('texto') or '') + ' ' + str(b.get('ancla') or '') for b in g.get('bloques') or [] if isinstance(b, dict)]
    except (OSError, ValueError, AttributeError):
        pass
    return ' '.join(partes)


def _ordenar(t):
    """Sin separadores sueltos o repetidos ni paréntesis vacíos después de sacar palabras."""
    t = re.sub(r'\(\s*[-|–—,]*\s*\)', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    antes = None
    while antes != t:  # «Honor - | Nuevo» → «Honor - Nuevo»: dos separadores seguidos quedan en uno
        antes, t = t, re.sub(r'(^|\s)([|–—-])\s*([|–—-])(?=\s|$)', r'\1\2', t)
    t = re.sub(r'\s+([,.:;!?])', r'\1', t)
    t = re.sub(r',(\s*,)+', ',', t)
    return t.strip(' |-–—:,;')


def _bonito(frase):
    """«sin pc» → «Sin PC»."""
    frase = re.sub(r'\bpc\b', 'PC', frase.strip(), flags=re.I)
    return frase[:1].upper() + frase[1:]


def revisar_titulo(titulo, marca='', texto='', hoy=None, datos=None, miniatura=False):
    """(título corregido, [avisos]). texto = lo que dice el proyecto (texto_proyecto), para saber el proceso y si es gratis.
    miniatura=True: un texto de miniatura (ahí «SIN PC» puede ir en cualquier lado, si el proceso no usa PC)."""
    t, avisos = str(titulo or ''), []
    if not t.strip():
        return t, avisos
    contexto = f'{t} {texto}'
    m = marca_normal(marca) or _marca_de_texto(contexto)
    # el año: el mismo en títulos y miniaturas, por la fecha
    a = str(anio(hoy))
    otros = sorted({x for x in ANIO_TITULO.findall(t) if x != a})
    if otros:
        t = ANIO_TITULO.sub(a, t)
        t = re.sub(rf'{a}(\s*[-–/]\s*{a})+', a, t)
        avisos.append(f'el año va {a} (decía {", ".join(otros)})')
    # «Sin PC»: solo si el proceso no usa PC, y en el título solo al inicio
    if SIN_PC.search(t):
        if necesita_pc(m, contexto, datos):
            t = SIN_PC.sub(' ', t)
            avisos.append('quité «Sin PC»: este proceso usa PC («Sin PC Avanzada» sí se puede)')
        elif not miniatura and not re.match(r'^\W*' + SIN_PC.pattern, t, re.I):
            t = _bonito(SIN_PC.search(t).group(0)) + ' - ' + _ordenar(SIN_PC.sub(' ', t, count=1))
            avisos.append('«Sin PC» va al inicio del título')
    # Honor: sin «Todos los Modelos»
    if m == 'honor' and TODOS_MODELOS.search(t):
        t = TODOS_MODELOS.sub(' ', t)
        avisos.append('quité «Todos los Modelos» (en Honor ya no va)')
    # «Gratis» solo si el método de este video es gratis
    if GRATIS_TITULO.search(t) and not es_gratis(texto):
        t = GRATIS_TITULO.sub(' ', t)
        avisos.append('quité «Gratis»: el proyecto no dice que este método sea gratis')
    return (_ordenar(t) if avisos else t), avisos


def para_ia(marca='', texto='', hoy=None, datos=None, miniatura=False):
    """Las reglas de los títulos (o de los textos de la miniatura) para el pedido a la IA, según el proceso del video."""
    datos = leer_procesos() if datos is None else datos
    m = marca_normal(marca) or _marca_de_texto(texto)
    a = anio(hoy)
    p = proceso(texto, m, datos)
    pc = necesita_pc(m, texto, datos)
    r = [f'REGLAS DEL AUTOR PARA {"LOS TEXTOS DE LA MINIATURA" if miniatura else "LOS TÍTULOS"} (obligatorias):']
    if not miniatura:
        r.append('- Puede empezar con dos verbos separados por coma, por ejemplo «Quitar, Eliminar Cuenta Google …».')
    r.append(f'- Si lleva año, es {a} (ni otro año ni un rango de años).')
    if pc:
        r.append('- Este proceso usa PC: nunca «Sin PC», «Sin Computadora», «No PC» ni «Without PC», ni lo prometas'
                 + (' (aunque la competencia lo use). «Sin PC Avanzada» sí se puede: basta una PC sencilla.' if m == 'honor' else '.'))
    else:
        basta = f' (basta {p["basta"]})' if p and p.get('basta') else ''
        r.append(f'- Este proceso no usa PC{basta}: «Sin PC» se puede'
                 + ('.' if miniatura else ', pero SOLO al inicio del título («Sin PC - …»), nunca después de la marca.'))
    if m == 'honor':
        r.append('- Honor: nada de «Todos los Modelos» (ni «All Models» ni «Todos os Modelos»).')
    if es_gratis(texto):
        r.append('- «Gratis» se puede: el proyecto dice que este método es gratis.')
    else:
        r.append('- Nada de «Gratis» ni «Free»: el método de este video no es gratis (o el proyecto no lo dice).')
    return '\n'.join(r)
