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
  · Honor sin «Todos los Modelos» (ni «All Models» ni «Todos os Modelos»), solo en los títulos de YouTube y de los Shorts:
    la miniatura sigue con su píldora «TODOS LOS MODELOS»;
  · «Gratis» solo si el proyecto dice que el método es gratis (la app nunca lo pone por su cuenta);
  · el año, el de anio(), solo donde es etiqueta («Método 2025», «NEW 2027»): el que es parte del modelo («Moto G Power
    2024», «iPhone SE 2022», «Samsung A2025») no se toca.
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
# (revisión, 03/11/2026) en un TEXTO suelto (guion, idea.txt) «poco» solo es Xiaomi con su modelo («Poco X6», «Poco F5»):
# «un poco» no; y «Mi Account», «cuenta Mi» o «Mi Cloud» sin la palabra Xiaomi también son de Xiaomi
EN_TEXTO = {'xiaomi': (r' (xiaomi|redmi|hyperos|miui|mi account|cuentas? (de )?mi|mi cloud|poco [xfmc]\d\w*) ',)}

# «Sin PC» y sus traducciones; «Sin PC Avanzada» / «Sin PC Básica» no cuentan (lo de Honor: basta una PC sencilla).
# (revisión, 03/11/2026) también «Sin Usar PC», «Sin Necesidad de PC», «No necesitas PC» y, entero, «No PC Needed/Required»
_SIN_VERBO = (r'(?:(?:se\s+)?(?:usar|necesitar|necesitas|necesita|necesidad\s+de|hace\s+falta|precisar|precisa|precisas|'
              r'necessidade\s+de|using|needing|need\s+for|need|needs)(?:\s+de)?\s+)?')
SIN_PC = re.compile(r'(?<![\w])(sin|sem|no|without)\s+' + _SIN_VERBO + r'(?:(?:una|la|ninguna|um|uma|a|an|any)\s+)?'
                    r'(pc|computadora|computador|ordenador|laptop|computer)\b'
                    r'(?:\s*[\U0001F5A5\U0001F4BB]️?)?(?:\s+(?:needed|required|necess[aá]ri[oa]|necesari[oa]|requerid[oa]))?'
                    r'(?!\s*(avanzad|avançad|advanced|b[aá]sic|basic|sencill|potente))', re.I)
TODOS_MODELOS = re.compile(r'(?<![\w])(para\s+|for\s+|pra\s+)?(todos\s+los\s+modelos|all\s+models|todos\s+os\s+modelos)\b', re.I)
GRATIS_TITULO = re.compile(r'(?<![\w])(100\s*%\s*)?(gratis|gratuit[oa]s?|gr[aá]tis|free)\b', re.I)
# un año suelto (no pegado a letras: «A2025» es un modelo)
ANIO_TITULO = re.compile(r'(?<![\w])20[2-9]\d(?![\w])')
# (revisión, 03/11/2026) el año que es parte del modelo, justo antes: Motorola (Moto G 2025, Moto G Power 5G 2024, Moto E 2020,
# Motorola Edge 2024, Razr+ 2024, G Stylus 2023), Apple (iPhone SE 2022, iPad Pro 2021) y las tablets (Galaxy Tab S6 Lite 2024)
MODELO_ANTES = re.compile(r'(?:\bmoto(?:rola)?\s+(?:g|e|edge|razr)|\bg\s+(?:power|stylus|play|pure)|\brazr|\bstylus|\bse'
                          r'|\bipad(?:\s+(?:pro|air|mini))?|\btab\s+[a-z]?\d*[a-z]?(?:\s+lite)?)'
                          r'(?:\s*(?:\+|(?:plus|power|stylus|play|pure|5g)\b))*\s*\(?\s*$', re.I)
# lo que va antes del año cuando es etiqueta: aunque el proyecto lo diga igual («Nuevo método 2025»), ese año sí se cambia
ETIQUETA_ANTES = {'metodo', 'method', 'new', 'nuevo', 'nueva', 'novo', 'nova', 'actualizado', 'actualizada', 'atualizado',
                  'updated', 'update', 'version', 'versao', 'ano', 'year', 'este', 'esta', 'en', 'el', 'la', 'del', 'de', 'in',
                  'of', 'for', 'para', 'the', 'em', 'do', 'da', 'desde', 'hasta', 'ate', 'gratis', 'free', 'frp', 'bypass',
                  'google', 'icloud', 'mdm', 'cuenta', 'account', 'conta', 'android', 'ios', 'hyperos', 'miui', 'magicos', 'oneui'}
# el proyecto dice que el método es gratis / habla de pagar (sobre el texto sin tildes y en minúsculas)
GRATIS_DICE = re.compile(r'\b(gratis|gratuit[oa]s?|free|sin costo|sin pagar|no (tienes que |hay que |se )?paga\w* nada|'
                         r'no cuesta nada)\b')
PAGO = re.compile(r'\b(dolar|dolares|pagar|pagas|paga|pagan|pago|pagos|pagando|precio|precios|costo|costos|cuesta|'
                  r'cuestan|cobra|cobro|creditos|usd|pesos|soles)\b|\$')
# (revisión, 03/11/2026) «no es gratis», «ya no es gratis», «not free», «não é grátis», «dejó de ser gratis»: eso NO es gratis
NO_GRATIS = re.compile(r"\b(no|not|nao|nada|isn'?t|aren'?t)\s+(?:(?:es|son|sera|era|is|are|e|sao|esta)\s+)?"
                       r"(?:(?:totalmente|completamente|100\s*%)\s+)?(gratis|gratuit[oa]s?|free)\b|\bdej[oa] de ser gratis")
SEP = '\x1e'  # separa en texto_proyecto el nombre, idea.txt y el guion (para que idea.txt mande en «Gratis»)


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
    """'APPLE', 'IPHONE', 'Redmi', 'Xiaomi Mi Account'… → 'iphone', 'xiaomi'…; '' si no es una marca conocida (o es «TU CELULAR»)."""
    m = normal(marca).strip()
    if not m or m == 'tu celular':
        return ''
    return next((k for k, alias in MARCAS.items() if m == k or m in alias), None) or _marca_de_texto(m) or m


def _marca_de_texto(t):
    t = _simple(t)
    for k, alias in MARCAS.items():
        if k in EN_TEXTO:
            if any(re.search(rx, t) for rx in EN_TEXTO[k]):
                return k
        elif any(f' {a} ' in t for a in alias):
            return k
    return ''


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
    t = _simple(f'{marca} {texto}')  # la marca también cuenta: «Xiaomi Mi Account» ya dice el proceso (revisión, 03/11/2026)
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


def _dice_gratis(t):
    if NO_GRATIS.search(t) or not GRATIS_DICE.search(t):
        return False
    return not PAGO.search(GRATIS_DICE.sub(' ', t))


def es_gratis(texto):
    """True solo si el proyecto dice que el método es gratis (sin negarlo: «no es gratis») y no habla de pagar (precio,
    dólares, créditos). (revisión, 03/11/2026) Si idea.txt (lo que escribe fabian) dice que es gratis, manda idea.txt aunque el
    guion nombre precios de otra cosa (sus cierres hablan de los servicios de pago)."""
    t = normal(texto)
    partes = t.split(SEP)
    return (len(partes) > 2 and _dice_gratis(partes[1])) or _dice_gratis(t)


def anios_etiqueta(t, texto=''):
    """Los años de t que son etiqueta («Método 2025», «NEW 2027», «2025-2026»), como objetos match. No cuentan los que son
    parte del modelo: pegados a letras («A2025»), justo después de una palabra de modelo (MODELO_ANTES: «Moto G Power 2024»,
    «iPhone SE 2022») o nombrados igual en el proyecto (texto: «Pad 2025» si el proyecto dice «Pad 2025»)."""
    proyecto = _simple(texto)
    out = []
    for m in ANIO_TITULO.finditer(str(t or '')):
        antes = t[:m.start()]
        if MODELO_ANTES.search(antes):
            continue
        prev = re.search(r'([a-z0-9]+)[^a-z0-9]*$', normal(antes))
        prev = prev.group(1) if prev else ''
        if prev and not prev.isdigit() and prev not in ETIQUETA_ANTES and f' {prev} {m.group()} ' in proyecto:
            continue
        out.append(m)
    return out


def texto_proyecto(d):
    """Lo que dice el proyecto de su proceso: el nombre (y el modelo de youtube/metadatos.json), idea.txt y el guion, en ese
    orden y separados por SEP (así idea.txt se reconoce en es_gratis)."""
    if not d:
        return ''
    nombre, idea, guion = [os.path.basename(os.path.abspath(d))], '', []
    try:
        nombre.append(str(json.load(open(os.path.join(d, 'youtube', 'metadatos.json'), encoding='utf-8')).get('modelo') or ''))
    except (OSError, ValueError, AttributeError):
        pass
    try:
        idea = open(os.path.join(d, 'idea.txt'), encoding='utf-8').read()[:3000]
    except OSError:
        pass
    try:
        g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
        guion = [str(b.get('texto') or '') + ' ' + str(b.get('ancla') or '') for b in g.get('bloques') or [] if isinstance(b, dict)]
    except (OSError, ValueError, AttributeError):
        pass
    return SEP.join([' '.join(nombre).strip(), idea, ' '.join(guion)])


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
    # el año: el mismo en títulos y miniaturas, por la fecha; solo donde es etiqueta (el del modelo no se toca)
    a = str(anio(hoy))
    etiquetas = anios_etiqueta(t, texto)
    otros = sorted({x.group() for x in etiquetas if x.group() != a})
    if otros:
        for x in reversed(etiquetas):  # \x00 marca dónde va el año de hoy: un rango «2025-2026» queda en uno solo
            t = t[:x.start()] + '\x00' + t[x.end():]
        t = re.sub(r'\x00(\s*[-–/]\s*\x00)+', '\x00', t).replace('\x00', a)
        avisos.append(f'el año va {a} (decía {", ".join(otros)})')
    # «Sin PC»: solo si el proceso no usa PC, y en el título solo al inicio
    if SIN_PC.search(t):
        if necesita_pc(m, contexto, datos):
            t = SIN_PC.sub(' ', t)
            avisos.append('quité «Sin PC»: este proceso usa PC («Sin PC Avanzada» sí se puede)')
        elif not miniatura and not re.match(r'^\W*' + SIN_PC.pattern, t, re.I):
            t = _bonito(SIN_PC.search(t).group(0)) + ' - ' + _ordenar(SIN_PC.sub(' ', t, count=1))
            avisos.append('«Sin PC» va al inicio del título')
    # Honor: sin «Todos los Modelos» en los títulos (en la miniatura sigue la píldora «TODOS LOS MODELOS»)
    if m == 'honor' and not miniatura and TODOS_MODELOS.search(t):
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
    r.append(f'- Si lleva año, es {a} (ni otro año ni un rango de años). El año que es parte del nombre del modelo («Moto G Power '
             '2024», «iPhone SE 2022») va tal cual.')
    if pc:
        r.append('- Este proceso usa PC: nunca «Sin PC», «Sin Computadora», «No PC» ni «Without PC», ni lo prometas'
                 + (' (aunque la competencia lo use). «Sin PC Avanzada» sí se puede: basta una PC sencilla.' if m == 'honor' else '.'))
    else:
        basta = f' (basta {p["basta"]})' if p and p.get('basta') else ''
        r.append(f'- Este proceso no usa PC{basta}: «Sin PC» se puede'
                 + ('.' if miniatura else ', pero SOLO al inicio del título («Sin PC - …»), nunca después de la marca.'))
    if m == 'honor' and not miniatura:
        r.append('- Honor: nada de «Todos los Modelos» (ni «All Models» ni «Todos os Modelos»).')
    if es_gratis(texto):
        r.append('- «Gratis» se puede: el proyecto dice que este método es gratis.')
    else:
        r.append('- Nada de «Gratis» ni «Free»: el método de este video no es gratis (o el proyecto no lo dice).')
    return '\n'.join(r)
