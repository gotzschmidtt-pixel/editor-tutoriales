import {AbsoluteFill, Audio, Img, interpolate, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {estilo} from './estilo';

export type Fase = 'ANTES' | 'DURANTE' | 'DESPUÉS';
export type Clip = {src: string; dur: number; fase: Fase};
// fondo: la imagen de la marca para la placa final (mis_conocimientos/fondos, hecha con gpt-image-2.5 sin texto); el título va encima
export type TrailerProps = {clips: Clip[]; titulo: string; subtitulo?: string; audio?: string; fondo?: string};

const CIERRE = 2.4; // segundos de la placa final con el título
const FLASH = 4; // cuadros de destello entre cortes

export const duracionTrailer = (p: TrailerProps, fps: number) =>
  Math.round((p.clips.reduce((s, c) => s + c.dur, 0) + CIERRE) * fps);

// Sello ANTES / DURANTE / DESPUÉS: entra con golpe, tiembla un poco y se queda. Va chico y arriba a la izquierda: grande y
// abajo tapaba el teléfono (pedido de fabian, 30/10/2026, tráiler de HONOR 8 LITE)
const Sello: React.FC<{fase: Fase; nuevo: boolean}> = ({fase, nuevo}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = nuevo ? spring({frame: f, fps, config: {damping: 9, stiffness: 180}}) : 1;
  const sacudida = nuevo ? Math.sin(f * 2.3) * interpolate(f, [0, 10], [10, 0], {extrapolateRight: 'clamp'}) : 0;
  const color = estilo.colorFase[fase];
  return (
    <div style={{position: 'absolute', left: 60, top: 100, transform: `scale(${0.4 + 0.6 * s}) rotate(${-3 + sacudida * 0.3}deg)`,
      transformOrigin: 'left top', opacity: s}}>
      <div style={{fontFamily: estilo.fuente, fontWeight: 900, fontSize: 78, letterSpacing: 3, color: 'white',
        padding: '2px 22px', background: color, borderRadius: 12,
        boxShadow: `0 0 0 4px rgba(255,255,255,.9), 0 0 30px ${color}, 0 10px 24px rgba(0,0,0,.5)`,
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

const Cierre: React.FC<{titulo: string; subtitulo?: string; fondo?: string}> = ({titulo, subtitulo, fondo}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f, fps, config: {damping: 12}});
  const s2 = spring({frame: f - 8, fps, config: {damping: 14}});
  const brillo = interpolate(f, [0, 2 * fps], [-30, 130]);
  if (fondo) {  // con el fondo de la marca: la imagen se acerca despacio y el título va a la izquierda, sobre la parte oscura
    const zoom = interpolate(f, [0, CIERRE * fps], [1.0, 1.06]);
    return (
      <AbsoluteFill style={{backgroundColor: '#07080d', fontFamily: estilo.fuente}}>
        <Img src={staticFile(fondo)} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${zoom})`}} />
        <AbsoluteFill style={{background: 'linear-gradient(90deg, rgba(7,8,13,.85) 0%, rgba(7,8,13,.55) 38%, transparent 62%)'}} />
        <AbsoluteFill style={{justifyContent: 'center', paddingLeft: 110, paddingRight: 820}}>
          <div style={{fontWeight: 900, fontSize: 104, transform: `translateY(${(1 - s) * 60}px)`, opacity: s, lineHeight: 1.05,
            backgroundImage: `linear-gradient(100deg, white ${brillo - 15}%, ${estilo.azul} ${brillo}%, white ${brillo + 15}%)`,
            WebkitBackgroundClip: 'text', color: 'transparent', textShadow: 'none'}}>{titulo}</div>
          {subtitulo && <div style={{marginTop: 26, fontSize: 50, fontWeight: 700, color: estilo.rosa, opacity: s2,
            transform: `translateY(${(1 - s2) * 30}px)`, letterSpacing: 1}}>{subtitulo}</div>}
        </AbsoluteFill>
      </AbsoluteFill>
    );
  }
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

export const Trailer: React.FC<TrailerProps> = ({clips, titulo, subtitulo, audio, fondo}) => {
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
        <Cierre titulo={titulo} subtitulo={subtitulo} fondo={fondo} />
      </Sequence>
      {audio && <Audio src={staticFile(audio)} />}
    </AbsoluteFill>
  );
};
