import {Composition} from 'remotion';
import {Trailer, duracionTrailer, TrailerProps} from './Trailer';
import {Etiqueta, EtiquetaProps} from './Etiqueta';
import {Senal, SenalProps} from './Senal';

const FPS = 25; // igual que los videos de salida, para unirlos sin recodificar raro

// Ejemplo con el video de la Pico 2; trailer/trailer.py pasa los datos reales con --props
const ejemplo: TrailerProps = {
  clips: [
    {src: 'trailer/c1.mp4', dur: 2.2, fase: 'ANTES'},
    {src: 'trailer/c2.mp4', dur: 1.4, fase: 'DURANTE'},
    {src: 'trailer/c3.mp4', dur: 1.4, fase: 'DURANTE'},
    {src: 'trailer/c4.mp4', dur: 1.4, fase: 'DURANTE'},
    {src: 'trailer/c5.mp4', dur: 2.6, fase: 'DESPUÉS'},
  ],
  titulo: 'Pico 2 lista para bypass',
  subtitulo: 'Paso a paso, sin humo',
  audio: 'trailer/audio.mp3',
};

export const Root: React.FC = () => (
  <>
    <Composition
      id="Trailer"
      component={Trailer}
      fps={FPS}
      width={1920}
      height={1080}
      defaultProps={ejemplo}
      calculateMetadata={({props}) => ({durationInFrames: duracionTrailer(props, FPS)})}
    />
    <Composition
      id="Etiqueta"
      component={Etiqueta}
      fps={FPS}
      width={1920}
      height={1080}
      durationInFrames={4 * FPS}
      defaultProps={{tipo: 'web', titulo: 'Descarga aquí', texto: 'gsmprime.co'} as EtiquetaProps}
    />
    <Composition
      id="Senal"
      component={Senal}
      fps={FPS}
      width={1920}
      height={1080}
      durationInFrames={3 * FPS}
      defaultProps={{tipo: 'circulo', puntos: [[960, 540]], r: 90} as SenalProps}
      calculateMetadata={({props}) => ({durationInFrames: Math.max(props.puntos.length, 1)})}
    />
  </>
);
