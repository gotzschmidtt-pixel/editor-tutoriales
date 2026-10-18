import {AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {estilo} from './estilo';

export type Fase = 'ANTES' | 'DURANTE' | 'DESPUÉS';
export type Clip = {src: string; dur: number; fase: Fase};
export type TrailerProps = {clips: Clip[]; titulo: string; subtitulo?: string; audio?: string};

const CIERRE = 2.4; // segundos de la placa final con el título
const FLASH = 4; // cuadros de destello entre cortes

export const duracionTrailer = (p: TrailerProps, fps: number) =>
  Math.round((p.clips.reduce((s, c) => s + c.dur, 0) + CIERRE) * fps);

// Sello grande ANTES / DURANTE / DESPUÉS: entra con golpe, tiembla un poco y se queda
const Sello: React.FC<{fase: Fase; nuevo: boolean}> = ({fase, nuevo}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = nuevo ? spring({frame: f, fps, config: {damping: 9, stiffness: 180}}) : 1;
  const sacudida = nuevo ? Math.sin(f * 2.3) * interpolate(f, [0, 10], [10, 0], {extrapolateRight: 'clamp'}) : 0;
  const color = estilo.colorFase[fase];
  return (
    <div style={{position: 'absolute', left: 90, bottom: 110, transform: `scale(${0.4 + 0.6 * s}) rotate(${-4 + sacudida * 0.3}deg)`,
      transformOrigin: 'left bottom', opacity: s}}>
      <div style={{fontFamily: estilo.fuente, fontWeight: 900, fontSize: 170, letterSpacing: 6, color: 'white',
        padding: '6px 38px', background: color, borderRadius: 18,
        boxShadow: `0 0 0 6px rgba(255,255,255,.9), 0 0 60px ${color}, 0 18px 40px rgba(0,0,0,.5)`,
        textShadow: '0 6px 0 rgba(0,0,0,.25)'}}>{fase}</div>
    </div>
  );
};

const Toma: React.FC<{clip: Clip; nuevo: boolean}> = ({clip, nuevo}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const n = clip.dur * fps;
  const zoom = interpolate(f, [0, n], [1.0, 1.08]); // empuje de cámara constante
  const flash = interpolate(f, [0, FLASH], [0.85, 0], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      <AbsoluteFill style={{transform: `scale(${zoom})`}}>
        <OffthreadVideo src={staticFile(clip.src)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </AbsoluteFill>
      {/* viñeta y franjas de cine */}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,.55) 100%)'}} />
      <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 70, background: 'black'}} />
      <div style={{position: 'absolute', bottom: 0, left: 0, right: 0, height: 70, background: 'black'}} />
      <Sello fase={clip.fase} nuevo={nuevo} />
      <AbsoluteFill style={{backgroundColor: 'white', opacity: flash}} />
    </AbsoluteFill>
  );
};

const Cierre: React.FC<{titulo: string; subtitulo?: string}> = ({titulo, subtitulo}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f, fps, config: {damping: 12}});
  const s2 = spring({frame: f - 8, fps, config: {damping: 14}});
  const brillo = interpolate(f, [0, 2 * fps], [-30, 130]);
  return (
    <AbsoluteFill style={{background: `radial-gradient(circle at 30% 30%, ${estilo.rosa}55, transparent 60%), radial-gradient(circle at 75% 70%, ${estilo.azul}55, transparent 60%), #07080d`,
      justifyContent: 'center', alignItems: 'center', fontFamily: estilo.fuente}}>
      <div style={{fontWeight: 900, fontSize: 120, transform: `translateY(${(1 - s) * 60}px)`, opacity: s,
        textAlign: 'center', maxWidth: 1600, lineHeight: 1.05,
        backgroundImage: `linear-gradient(100deg, white ${brillo - 15}%, ${estilo.azul} ${brillo}%, white ${brillo + 15}%)`,
        WebkitBackgroundClip: 'text', color: 'transparent'}}>{titulo}</div>
      {subtitulo && <div style={{marginTop: 30, fontSize: 54, fontWeight: 700, color: estilo.rosa, opacity: s2,
        transform: `translateY(${(1 - s2) * 30}px)`, letterSpacing: 2}}>{subtitulo}</div>}
    </AbsoluteFill>
  );
};

export const Trailer: React.FC<TrailerProps> = ({clips, titulo, subtitulo, audio}) => {
  const {fps} = useVideoConfig();
  let desde = 0;
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      {clips.map((c, k) => {
        const n = Math.round(c.dur * fps);
        const seq = (
          <Sequence key={k} from={desde} durationInFrames={n}>
            <Toma clip={c} nuevo={k === 0 || clips[k - 1].fase !== c.fase} />
          </Sequence>
        );
        desde += n;
        return seq;
      })}
      <Sequence from={desde}>
        <Cierre titulo={titulo} subtitulo={subtitulo} />
      </Sequence>
      {audio && <Audio src={staticFile(audio)} />}
    </AbsoluteFill>
  );
};
