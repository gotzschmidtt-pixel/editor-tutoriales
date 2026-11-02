"""«⚖ Avisos de cuidado»: en los videos de quitar cuentas (FRP, iCloud, MDM), bypass, abrir el equipo o soldar, que haya
una frase de cuidado («solo en un equipo tuyo», «esto puede dañar la placa»). Ayuda a que YouTube no limite el video.

La IA del guion ya la escribe en la voz (regla del encargo). Esto lo revisa sin gastar nada:
  - si el guion trata un tema de riesgo y la voz NO dice ninguna frase de cuidado, agrega una etiqueta «consejo» en el
    primer bloque del proceso (no gasta créditos: es texto en pantalla, no voz);
  - si ya la dice, no hace nada.
Las etiquetas que agrega llevan "origen": "aviso_legal" y se rehacen cada vez; las tuyas no se tocan.

Uso: python avisos_legales.py --proyecto . [--solo-revisar]
"""
import argparse, json, os, re

TEMAS = [
    ('cuenta', re.compile(r'\bfrp\b|cuenta (de )?google|icloud|\bmdm\b|bypass|desbloque|quitar (la )?cuenta|borrar (la )?cuenta|'
                          r'activaci[oó]n|hello', re.I), 'Hazlo solo en un equipo tuyo o con permiso del dueño'),
    ('placa', re.compile(r'sold|abr(ir|e|imos) (el )?(equipo|tel[eé]fono|celular)|placa|desarm|flashe|firmware', re.I),
     'Con cuidado: un error puede dañar la placa'),
]
YA_DICE = re.compile(r'(equipo|tel[eé]fono|celular|dispositivo)s? (que sea )?(tuyo|propio|de tu propiedad)|permiso del (due[ñn]o|propietario)|'
                     r'\bsolo (en|con) (un |tu |tus )?(equipo|tel[eé]fono|celular)|bajo tu (propia )?responsabilidad|'
                     r'no me hago responsable|puede da[ñn]ar|con cuidado|\briesgo|\blegal(mente)?\b|uso [ée]tico', re.I)


def revisar(g):
    """[(tema, bloque donde empieza, texto de la etiqueta)] de los temas de riesgo sin frase de cuidado."""
    bl = [b for b in g.get('bloques', []) if str(b.get('texto') or '').strip()]
    todo = ' '.join(b['texto'] for b in bl)
    falta = []
    for tema, rx, frase in TEMAS:
        primero = next((b for b in bl[1:] if rx.search(b['texto'])), None) or next((b for b in bl if rx.search(b['texto'])), None)
        if primero and not YA_DICE.search(todo):
            falta.append((tema, primero, frase))
    return falta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proyecto', default='.')
    ap.add_argument('--solo-revisar', action='store_true')
    a = ap.parse_args()
    d = os.path.abspath(a.proyecto)
    g = json.load(open(os.path.join(d, 'guion.json'), encoding='utf-8'))
    falta = revisar(g)
    f = os.path.join(d, 'etiquetas.json')
    try:
        et = json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        et = []
    lista = et.get('etiquetas', []) if isinstance(et, dict) else et
    lista = [x for x in lista if x.get('origen') != 'aviso_legal']
    if not falta:
        print('· la voz ya dice una frase de cuidado (o el tema no la necesita): nada que agregar', flush=True)
    for tema, b, frase in falta:
        palabras = re.findall(r"[\wáéíóúñü']+", b['texto'])
        print(f"· {b['id']}: el video trata de {'quitar cuentas o bypass' if tema == 'cuenta' else 'abrir o soldar el equipo'} "
              f"y la voz no dice ninguna frase de cuidado → etiqueta «{frase}»", flush=True)
        lista.append({'bloque': b['id'], 'frase': ' '.join(palabras[:3]), 'tipo': 'consejo', 'titulo': 'Importante',
                      'texto': frase, 'dur': 4.5, 'origen': 'aviso_legal', 'por_que': 'aviso de cuidado para que YouTube no limite el video'})
    if a.solo_revisar:
        return
    if isinstance(et, dict):
        et['etiquetas'] = lista
    else:
        et = lista
    json.dump(et, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Listo: {len(falta)} avisos en etiquetas.json (se ponen con «Etiquetas animadas»).', flush=True)


if __name__ == '__main__':
    main()
