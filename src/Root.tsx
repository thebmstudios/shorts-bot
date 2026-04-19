import { Composition, staticFile } from "remotion";
import { MyComposition } from "./Composition";
import { Shorts, ShortsProps, Cue } from "./Shorts";

const FPS = 30;
const DEFAULT_DURATION_SECONDS = 60;

const defaultCues: Cue[] = [
  { text: "You won't believe this.", start: 0, end: 2.5 },
  { text: "Add voice.mp3 and subtitles.json to /public to see the real script.", start: 2.5, end: 8 },
];

type ShortsInputProps = ShortsProps & { subtitlesSrc?: string };

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* Legacy landscape composition — kept so existing work isn't broken */}
      <Composition
        id="MyComposition"
        component={MyComposition}
        durationInFrames={408}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* New vertical Shorts composition (1080x1920) */}
      <Composition
        id="Shorts"
        component={Shorts as React.FC}
        fps={FPS}
        width={1080}
        height={1920}
        durationInFrames={FPS * DEFAULT_DURATION_SECONDS}
        defaultProps={{
          voiceSrc: "voice.mp3",
          subtitles: defaultCues,
          durationSeconds: DEFAULT_DURATION_SECONDS,
        } as ShortsInputProps}
        calculateMetadata={async ({ props }) => {
          const typed = props as unknown as ShortsInputProps;
          let duration = typed.durationSeconds ?? DEFAULT_DURATION_SECONDS;
          let resolvedProps: ShortsInputProps = { ...typed };

          if (typed.subtitlesSrc) {
            try {
              const url = staticFile(typed.subtitlesSrc);
              const res = await fetch(url);
              const json = (await res.json()) as Cue[];
              resolvedProps = { ...resolvedProps, subtitles: json };
              const last = json[json.length - 1];
              if (last && last.end > duration) duration = last.end;
            } catch (e) {
              console.warn("Could not load subtitlesSrc", e);
            }
          }
          return {
            durationInFrames: Math.ceil(duration * FPS),
            props: resolvedProps as unknown as Record<string, unknown>,
          };
        }}
      />
    </>
  );
};
