import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {estilo} from './estilo';

// Flechas, círculos y recuadros que se dibujan solos y siguen al objeto (posiciones por cuadro).
export type SenalProps = {
  tipo: 'circulo' | 'flecha' | 'caja';
  puntos: [number, number][]; // centro en píxeles, uno por cuadro (si hay menos, se queda en el último)
  r?: number; // radio del círculo o largo de la flecha
  w?: number; h?: number; // tamaño de la caja
  color?: string;
  texto?: string;
  foco?: boolean; // oscurece el resto de la imagen
  angulo?: number; // de dónde viene la flecha, en grados (0 = desde la derecha)
};

export const Senal: React.FC<SenalProps> = ({tipo, puntos, r = 70, w = 200, h = 80, color = estilo.amarillo, texto, foco, angulo = -35}) => {
  const f = useCurrentFrame();
  const {fps, durationInFrames, width, height} = useVideoConfig();
  const [x, y] = puntos[Math.min(f, puntos.length - 1)];
  const dibuja = interpolate(f, [0, 0.45 * fps], [0, 1], {extrapolateRight: 'clamp'});
  const pop = spring({frame: f, fps, config: {damping: 10, stiffness: 160}});
  const sale = interpolate(f, [durationInFrames - 0.4 * fps, durationInFrames], [1, 0], {extrapolateLeft: 'clamp'});
  const pulso = 1 + 0.04 * Math.sin((f / fps) * Math.PI * 2.2);
  const brillo = `drop-shadow(0 0 10px ${color}) drop-shadow(0 4px 6px rgba(0,0,0,.6))`;
  const trazo = {fill: 'none', stroke: color, strokeWidth: 9, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const};

  let forma: React.ReactNode = null;
  if (tipo === 'circulo') {
    // trazo a mano: elipse un poco irregular que se pasa de largo al cerrar
    const L = 2 * Math.PI * r * 1.15;
    forma = (
      <g transform={`translate(${x} ${y}) scale(${pulso}) rotate(-12)`}>
        <ellipse rx={r * 1.08} ry={r * 0.92} {...trazo} strokeDasharray={L} strokeDashoffset={L * (1 - dibuja)} />
      </g>
    );
  } else if (tipo === 'caja') {
    const L = 2 * (w + h) + 40;
    forma = (
      <rect x={x - w / 2} y={y - h / 2} width={w} height={h} rx={16} {...trazo}
        transform={`rotate(-1.5 ${x} ${y})`} strokeDasharray={L} strokeDashoffset={L * (1 - dibuja)} />
    );
  } else {
    // flecha que llega desde fuera y rebota apuntando al objeto
    const a = (angulo * Math.PI) / 180;
    const largo = r * 2.2;
    const rebote = Math.sin((f / fps) * Math.PI * 3) * 8 * (f > 0.45 * fps ? 1 : 0);
    const px = x + Math.cos(a) * (18 + rebote), py = y + Math.sin(a) * (18 + rebote);
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

  const rf = (tipo === 'caja' ? Math.max(w, h) * 0.75 : r * 1.3) * pulso;
  return (
    <AbsoluteFill style={{opacity: sale}}>
      {foco && (
        <AbsoluteFill style={{opacity: 0.55 * dibuja,
          background: `radial-gradient(circle at ${x}px ${y}px, transparent ${rf}px, rgba(0,0,0,.85) ${rf + 60}px)`}} />
      )}
      <svg width={width} height={height} style={{position: 'absolute', filter: brillo}}>{forma}</svg>
      {texto && (
        <div style={{position: 'absolute', left: x - 300, width: 600, top: y + (tipo === 'caja' ? h / 2 : r) + 22, textAlign: 'center',
          transform: `scale(${pop})`, fontFamily: estilo.fuente, fontWeight: 900, fontSize: 44, color: 'white',
          textShadow: `0 0 12px ${color}, 0 3px 0 rgba(0,0,0,.7)`}}>{texto}</div>
      )}
    </AbsoluteFill>
  );
};
