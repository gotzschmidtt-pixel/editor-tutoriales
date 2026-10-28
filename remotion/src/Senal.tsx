import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {estilo} from './estilo';

// Flechas, círculos y recuadros que se dibujan solos y siguen al objeto (posiciones por cuadro).
export type SenalProps = {
  tipo: 'circulo' | 'flecha' | 'caja';
  puntos: [number, number][]; // centro en píxeles, uno por cuadro (si hay menos, se queda en el último)
  r?: number; // radio del círculo o largo de la flecha
  w?: number; h?: number; // tamaño de la caja; en un círculo, el del botón que rodea (el contorno toma su forma)
  color?: string;
  texto?: string;
  foco?: boolean; // oscurece el resto de la imagen
  angulo?: number; // de dónde viene la flecha, en grados (0 = desde la derecha)
  hueco?: number; // distancia del centro a la punta de la flecha (para no tapar el texto señalado)
};

export const Senal: React.FC<SenalProps> = ({tipo, puntos, r = 70, w: wDado, h: hDado, color, texto, foco, angulo = -35, hueco = 18}) => {
  const f = useCurrentFrame();
  const {fps, durationInFrames, width, height} = useVideoConfig();
  const [x, y] = puntos[Math.min(f, puntos.length - 1)];
  const contorno = estilo.senal === 'contorno';
  const col = color || (contorno ? estilo.rosa : estilo.marcador);
  const w = wDado ?? 200, h = hDado ?? 80;
  // contorno: si se sabe el tamaño del botón, el círculo toma su forma (píldora); si no, queda un círculo parejo
  const pad = 12;
  const pildora = contorno && tipo === 'circulo' && !!wDado && !!hDado;
  const pw = w + 2 * pad, ph = h + 2 * pad;
  const dibuja = interpolate(f, [0, 0.45 * fps], [0, 1], {extrapolateRight: 'clamp'});
  const pop = spring({frame: f, fps, config: {damping: 10, stiffness: 160}});
  const sale = interpolate(f, [durationInFrames - 0.4 * fps, durationInFrames], [1, 0], {extrapolateLeft: 'clamp'});
  const pulso = 1; // sin latido: el trazo queda quieto
  const brillo = contorno
    ? `drop-shadow(0 0 5px ${col}) drop-shadow(0 0 14px ${col}) drop-shadow(0 3px 4px rgba(0,0,0,.45))` // brillo del mismo color
    : 'drop-shadow(0 3px 4px rgba(0,0,0,.45))'; // marcador: sombra suave, sin brillo de neón
  const trazo = {fill: 'none', stroke: col, strokeWidth: contorno ? 7 : 8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const};
  const traza = {pathLength: 1, strokeDasharray: '1 1', strokeDashoffset: 1 - dibuja}; // se dibuja de punta a punta
  // marcador: una vuelta un poco irregular que se pasa de largo al cerrar (como con un marcador)
  const aMano = (rx: number, ry: number, vueltas = 1.12) => {
    const p: string[] = [];
    const n = 64;
    for (let i = 0; i <= n * vueltas; i++) {
      const a = (i / n) * Math.PI * 2 - 2.2;
      const temblor = 1 + 0.018 * Math.sin(i * 0.45) + 0.01 * Math.cos(i * 0.21); // ondulación suave, de mano firme
      const crece = 1 + 0.06 * (i / (n * vueltas)); // la segunda pasada queda un poco más afuera
      p.push(`${(Math.cos(a) * rx * temblor * crece).toFixed(1)} ${(Math.sin(a) * ry * temblor * crece).toFixed(1)}`);
    }
    return 'M ' + p.join(' L ');
  };

  let forma: React.ReactNode = null;
  if (contorno && tipo === 'circulo') {
    forma = pildora
      ? <rect x={x - pw / 2} y={y - ph / 2} width={pw} height={ph} rx={Math.min(pw, ph) / 2} {...trazo} {...traza} />
      : <circle cx={x} cy={y} r={r} transform={`rotate(-90 ${x} ${y})`} {...trazo} {...traza} />;
  } else if (contorno && tipo === 'caja') {
    forma = <rect x={x - w / 2} y={y - h / 2} width={w} height={h} rx={Math.min(h / 2, 22)} {...trazo} {...traza} />;
  } else if (tipo === 'circulo') {
    // marcador: elipse un poco irregular que se pasa de largo al cerrar
    const L = 2 * Math.PI * r * 1.5;
    forma = (
      <g transform={`translate(${x} ${y}) rotate(-8)`}>
        <path d={aMano(r * 1.35, r * 0.85)} {...trazo} strokeDasharray={L} strokeDashoffset={L * (1 - dibuja)} />
      </g>
    );
  } else if (tipo === 'caja') {
    // marcador: un óvalo ancho que rodea la zona (como el marcador del autor, no un cuadro de PowerPoint)
    const L = Math.PI * (w + h) * 1.4;
    forma = (
      <g transform={`translate(${x} ${y}) rotate(-2)`}>
        <path d={aMano(w * 0.62, h * 0.66)} {...trazo} strokeDasharray={L} strokeDashoffset={L * (1 - dibuja)} />
      </g>
    );
  } else {
    // flecha que llega desde fuera y rebota apuntando al objeto
    const a = (angulo * Math.PI) / 180;
    const largo = r * 2.2;
    const rebote = Math.sin((f / fps) * Math.PI * 3) * 8 * (f > 0.45 * fps ? 1 : 0);
    const px = x + Math.cos(a) * (hueco + rebote), py = y + Math.sin(a) * (hueco + rebote);
    const ox = px + Math.cos(a) * largo, oy = py + Math.sin(a) * largo;
    const cx = (px + ox) / 2 - Math.sin(a) * 30, cy = (py + oy) / 2 + Math.cos(a) * 30; // curva leve
    const L = largo * 1.2;
    const cabeza = 34 * interpolate(dibuja, [0.7, 1], [0, 1], {extrapolateLeft: 'clamp'});
    forma = (
      <g>
        <path d={`M ${ox} ${oy} Q ${cx} ${cy} ${px} ${py}`} {...trazo} strokeWidth={11} strokeDasharray={L} strokeDashoffset={L * (1 - dibuja)} />
        <path d={`M ${px + Math.cos(a + 0.5) * cabeza} ${py + Math.sin(a + 0.5) * cabeza} L ${px} ${py} L ${px + Math.cos(a - 0.5) * cabeza} ${py + Math.sin(a - 0.5) * cabeza}`} {...trazo} strokeWidth={11} />
      </g>
    );
  }

  // foco con la forma de la marca: rectángulo redondeado para recuadros y píldoras, redondo para el resto
  const marco = tipo === 'caja' ? {w: w + 20, h: h + 20, rad: contorno ? Math.min(h / 2, 22) + 10 : 22}
    : pildora ? {w: pw + 20, h: ph + 20, rad: Math.min(pw, ph) / 2 + 10} : null;
  const rf = (tipo === 'caja' ? Math.max(w, h) * 0.75 : r * 1.3) * pulso;
  return (
    <AbsoluteFill style={{opacity: sale}}>
      {foco && marco && (
        <div style={{position: 'absolute', left: x - marco.w / 2, top: y - marco.h / 2, width: marco.w, height: marco.h, borderRadius: marco.rad,
          opacity: 0.42 * dibuja, boxShadow: '0 0 0 4000px rgba(0,0,0,.85), 0 0 40px 20px rgba(0,0,0,.6)'}} />
      )}
      {foco && !marco && (
        <AbsoluteFill style={{opacity: 0.42 * dibuja,
          background: `radial-gradient(circle at ${x}px ${y}px, transparent ${rf}px, rgba(0,0,0,.85) ${rf + 60}px)`}} />
      )}
      <svg width={width} height={height} style={{position: 'absolute', filter: brillo}}>{forma}</svg>
      {texto && (() => {
        // rótulo tipo píldora: debajo de la marca, o encima si no cabe; nunca se sale del cuadro
        const alto = tipo === 'caja' ? h / 2 : pildora ? ph / 2 : r;
        const abajo = y + alto + 110 < height;
        const ancho = Math.min(620, 60 + texto.length * 26);
        const left = Math.min(Math.max(x - ancho / 2, 24), width - ancho - 24);
        const top = abajo ? y + alto + 24 : y - alto - 24 - 74;
        const aspecto = contorno
          ? {background: estilo.fondo, border: `4px solid ${col}`, borderRadius: 40, boxShadow: `0 0 18px ${col}88, 0 8px 18px rgba(0,0,0,.55)`, color: 'white'}
          : {background: 'white', borderLeft: `12px solid ${col}`, borderRadius: 14, boxShadow: '0 8px 18px rgba(0,0,0,.45)', color: '#111'};
        return (
          <div style={{position: 'absolute', left, top, width: ancho, height: 74, display: 'flex', alignItems: 'center',
            justifyContent: 'center', transform: `scale(${pop})`, transformOrigin: abajo ? '50% 0' : '50% 100%', ...aspecto,
            fontFamily: estilo.fuente, fontWeight: 900, fontSize: 40, whiteSpace: 'nowrap'}}>{texto}</div>
        );
      })()}
    </AbsoluteFill>
  );
};
