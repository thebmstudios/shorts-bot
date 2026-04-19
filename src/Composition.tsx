import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  staticFile,
} from "remotion";

export const MyComposition: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Audio src={staticFile("music.mp3")} />

      <Sequence from={0} durationInFrames={76}>
        <AbsoluteFill style={{ backgroundColor: "#000" }} />
      </Sequence>

      <Sequence from={76} durationInFrames={60} premountFor={60}>
        <OffthreadVideo
          src={staticFile("video.mp4")}
          startFrom={1568}
          endAt={1628}
          muted
        />
      </Sequence>

      <Sequence from={136} durationInFrames={76}>
        <AbsoluteFill style={{ backgroundColor: "#000" }} />
      </Sequence>

      <Sequence from={212} durationInFrames={60} premountFor={136}>
        <OffthreadVideo
          src={staticFile("sukuna_kesim.webm")}
          muted
        />
      </Sequence>

      <Sequence from={272} durationInFrames={76}>
        <AbsoluteFill style={{ backgroundColor: "#000" }} />
      </Sequence>

      <Sequence from={348} durationInFrames={60}>
        <OffthreadVideo
          src={staticFile("Tji_kesim.webm")}
          muted
        />
      </Sequence>
    </AbsoluteFill>
  );
};
