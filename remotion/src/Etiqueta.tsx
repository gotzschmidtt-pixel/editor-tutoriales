import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {estilo} from './estilo';

// Misma etiqueta que etiquetas/plantilla.html, ahora como componente de Remotion
export type EtiquetaProps = {tipo: 'web' | 'archivo' | 'dato' | 'precio' | 'pin' | 'consejo'; titulo?: string; texto: string; color?: string};

const ICONO: Record<EtiquetaProps['tipo'], string> = {web: '🌐', archivo: '📄', dato: '⚡', precio: '💲', pin: '📍', consejo: '💡'};

export const Etiqueta: React.FC<EtiquetaProps> = ({tipo, titulo, texto, color}) => {
  const f = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const entra = spring({frame: f, fps, config: {damping: 13}});
  const sale = interpolate(f, [durationInFrames - 0.55 * fps, durationInFrames], [0, 1], {extrapolateLeft: 'clamp'});
  const escribe = interpolate(f, [6, 6 + texto.length * 1.6], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const acento = color ?? estilo.azul;
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', right: 70, top: 90, transform: `translateX(${(1 - entra) * 140 + sale * 160}px)`,
        opacity: entra * (1 - sale), padding: 3, borderRadius: 26,
        background: `linear-gradient(120deg, ${estilo.rosa}, ${acento})`, boxShadow: `0 0 40px ${acento}88`}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 22, padding: '18px 34px', borderRadius: 23,
          background: estilo.fondo, fontFamily: estilo.fuente, color: 'white'}}>
          <div style={{fontSize: 54}}>{ICONO[tipo]}</div>
          <div>
            {titulo && <div style={{fontSize: 26, fontWeight: 700, opacity: 0.75, textTransform: 'uppercase', letterSpacing: 2}}>{titulo}</div>}
            <div style={{fontSize: 52, fontWeight: 900, clipPath: `inset(0 ${100 - escribe}% 0 0)`}}>{texto}</div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
