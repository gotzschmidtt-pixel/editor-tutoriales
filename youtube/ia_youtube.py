"""La parte de «▶️ YouTube» que escribe la IA de «⚙ Ajustes IA». La app junta los datos (guion, retención, comentarios,
tus videos con sus vistas) en youtube/entrada_<tarea>.json del proyecto y esto le pide a la IA:

  metadatos  5 títulos con tu estilo, descripción, etiquetas, capítulos y el comentario para fijar
  aprender   en qué bloque se fue la gente y qué preguntan en los comentarios → notas para «🧠 Conocimiento»
  ideas      temas para los próximos videos: lo que piden en los comentarios y lo que se busca en YouTube

    python ia_youtube.py --proyecto CARPETA --tarea metadatos --ajustes app/ajustes.json
Deja la respuesta en youtube/<tarea>.json. Cada pedido queda en el diagnóstico (y en «💲 Gastos del mes»).
"""
import argparse, json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'ia'))
import ia  # noqa: E402
sys.path.insert(0, os.path.join(RAIZ, 'conocimiento'))
import conocimiento  # noqa: E402

REGLAS = """Escribe en español latinoamericano neutro, como el autor del canal. No inventes datos (modelos, versiones, precios,
webs): usa solo lo que está en el guion, la idea del video y el conocimiento del canal. Contesta SOLO con el JSON pedido."""


def metadatos(e):
    titulos = '\n'.join(f"- {v['titulo']} ({v['vistas']:,} vistas)".replace(',', '.') for v in e.get('mis_videos', [])[:40])
    return f"""Eres quien publica los videos de este canal de tutoriales en YouTube. {REGLAS}

TUS VIDEOS MÁS VISTOS (fíjate qué palabras, largo y forma tienen los títulos que mejor funcionaron):
{titulos or '(no hay datos del canal)'}

LA IDEA DEL VIDEO NUEVO (datos seguros del autor):
{e.get('idea') or '(sin idea escrita)'}

EL GUION DEL VIDEO NUEVO, bloque por bloque (id, segundo en que empieza y texto):
{json.dumps(e['bloques'], ensure_ascii=False)}

LO QUE LA GENTE ESCRIBE EN EL BUSCADOR DE YOUTUBE (úsalo en títulos, descripción y etiquetas, sin forzar):
{json.dumps(e.get('busquedas') or {}, ensure_ascii=False)}

PÁGINAS Y CONTACTOS DEL AUTOR (van en la descripción con su link exacto):
{json.dumps(e.get('paginas', []), ensure_ascii=False)}

CONOCIMIENTO DEL CANAL:
{e.get('conocimiento', '')[:6000]}

Devuelve este JSON:
{{"titulos": [{{"titulo": "...", "por_que": "en qué título exitoso se inspira"}}, ... 5 en total, de 100 letras o menos],
  "elegido": 0,
  "descripcion": "2 a 4 párrafos: qué resuelve el video, para qué modelos/versiones (solo los que se nombran), qué hace falta, y las páginas con su link. Sin capítulos (los pone la app)",
  "etiquetas": ["15 a 25 etiquetas: marca, modelo, problema, método, año"],
  "capitulos": [{{"bloque": "L01", "titulo": "Qué necesitas"}}, ... entre 4 y 12, el primero el bloque inicial, cada uno donde empieza un paso nuevo],
  "descripciones": ["otra versión de la descripción, con otro enfoque (más corta y directa)"],
  "comentario": "el comentario que el autor fija: invita a comentar el modelo y la versión, recuerda el WhatsApp o la web si está en las páginas",
  "comentarios": ["otras 2 opciones de comentario fijado, distintas: una con pregunta para generar respuestas, otra con un dato útil"],
  "advertencia": "una frase si el video trata de quitar bloqueos o abrir el equipo: solo en equipos propios y bajo tu responsabilidad; vacío si no hace falta"}}"""


def aprender(e):
    return f"""Analizas un video ya publicado de este canal de tutoriales. {REGLAS}

RETENCIÓN POR BLOQUE DEL GUION (mira = parte del público que sigue mirando al empezar el bloque, 1 = todos;
relativa = frente a videos parecidos de YouTube, 0,5 es normal, más es mejor):
{json.dumps(e.get('retencion_bloques', []), ensure_ascii=False)}

COMENTARIOS DEL VIDEO (los más nuevos primero):
{json.dumps([c['texto'] for c in e.get('comentarios', [])][:250], ensure_ascii=False)}

Devuelve este JSON:
{{"abandono": [{{"bloque": "L07", "que_pasa": "qué se ve y se dice ahí", "consejo": "cómo hacerlo en el próximo video"}}, ... los 3 peores],
  "lo_mejor": "qué bloque retuvo mejor y por qué",
  "preguntas": [{{"pregunta": "...", "veces": 3, "respuesta": "respuesta corta, solo si sale del guion o el conocimiento; si no, vacío"}}, ... las más repetidas, hasta 10],
  "notas": [{{"tipo": "guion|pregunta|idea", "texto": "una línea para «Conocimiento del canal» que sirva en los próximos guiones"}}, ... hasta 8]}}"""


def ideas(e):
    return f"""Propones los próximos videos de este canal de tutoriales. {REGLAS}

TUS VIDEOS (título y vistas):
{json.dumps([[v['titulo'], v['vistas']] for v in e.get('mis_videos', [])[:120]], ensure_ascii=False)}

COMENTARIOS RECIENTES DE TODO EL CANAL:
{json.dumps([c['texto'] for c in e.get('comentarios', [])][:400], ensure_ascii=False)}

LO QUE LA GENTE ESCRIBE EN EL BUSCADOR DE YOUTUBE (sugerencias del buscador):
{json.dumps(e.get('busquedas', {}), ensure_ascii=False)}

Devuelve este JSON con 10 ideas, de la más pedida a la menos:
{{"ideas": [{{"tema": "título tentativo", "por_que": "quién lo pide y cuántas veces (comentarios, búsquedas)",
              "pedidos": 4, "busquedas": ["la sugerencia que coincide"], "ya_hecho": "título de tu video parecido, si existe"}}]}}"""


def respuestas(e):
    return f"""Respondes los comentarios del canal de tutoriales del autor, como si fueras él. {REGLAS}
Respuestas cortas (1 a 3 frases), cercanas, tuteando y con buena onda. Si preguntan por un modelo o versión que no está en el
conocimiento, no prometas que sirve: invita a escribir al WhatsApp o a la web del autor (están en el conocimiento). Si el
comentario es spam, un insulto o no hace falta contestar (un «gracias» suelto se contesta con un agradecimiento corto),
márcalo con "no_responder": true. Nada de links que no estén en el conocimiento.

CONOCIMIENTO DEL CANAL (procesos, respuestas confirmadas, páginas):
{e.get('conocimiento', '')[:7000]}

COMENTARIOS SIN RESPONDER (id, autor, texto):
{json.dumps([[x['id'], x['autor'], x['texto']] for x in e.get('comentarios', [])], ensure_ascii=False)}

Devuelve este JSON, uno por comentario:
{{"respuestas": [{{"id": "el id del comentario", "respuesta": "...", "no_responder": false, "duda": "si no estás seguro de algo, qué revisar; si no, vacío"}}]}}"""


TAREAS = {'metadatos': metadatos, 'aprender': aprender, 'ideas': ideas, 'respuestas': respuestas}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', required=True)
    ap.add_argument('--tarea', required=True, choices=list(TAREAS))
    ap.add_argument('--ajustes', required=True)
    a = ap.parse_args()
    aj = json.load(open(a.ajustes, encoding='utf-8'))
    if not (aj.get('modelo') and aj.get('url')):
        sys.exit('ERROR: hace falta una IA en «⚙ Ajustes IA».')
    carpeta = os.path.join(a.proyecto, 'youtube')
    e = json.load(open(os.path.join(carpeta, f'entrada_{a.tarea}.json'), encoding='utf-8'))
    if a.tarea == 'respuestas':
        e['conocimiento'] = conocimiento.texto_para_ia(7000)
    if a.tarea == 'metadatos':
        e['conocimiento'] = conocimiento.texto_para_ia(6000, a.proyecto)
        try:  # «📊 Todo tu canal»: qué títulos y palabras funcionan en tu canal, con números
            import canal
            e['conocimiento'] = (canal.texto_para_ia() + '\n\n' + e['conocimiento']).strip()
        except Exception:
            pass
    print(f'Pido a la IA ({aj["modelo"]}): {a.tarea}…', flush=True)
    try:
        r = ia.extraer_json(ia.llamar(aj, TAREAS[a.tarea](e), []))
    except ia.ErrorIA as x:
        sys.exit(str(x))
    if not isinstance(r, dict):
        sys.exit('ERROR: la IA no contestó con el JSON pedido.')
    if a.tarea == 'aprender':
        nuevas = 0
        for n in r.get('notas') or []:
            try:
                nuevas += conocimiento.anotar(n.get('tipo') if n.get('tipo') in conocimiento.SECCIONES else 'idea', n.get('texto'))[1]
            except (ValueError, AttributeError):
                pass
        r['notas_nuevas'] = nuevas
    json.dump(r, open(os.path.join(carpeta, f'{a.tarea}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('✓ listo', flush=True)


if __name__ == '__main__':
    main()
