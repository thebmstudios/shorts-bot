import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  random,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type Cue = {
  text: string;
  start: number;
  end: number;
};

export type ShortsProps = {
  voiceSrc: string;
  subtitles: Cue[];
  durationSeconds: number;
  images?: string[];
};

/* --- Ken Burns animated background image --- */
const KenBurns: React.FC<{ src: string; t: number; seed: number }> = ({ src, t, seed }) => {
  const startScale = 1.05 + (seed % 3) * 0.05;
  const endScale = 1.25 + ((seed + 1) % 3) * 0.05;
  const scale = interpolate(t, [0, 1], [startScale, endScale], { extrapolateRight: "clamp" });
  const tx = interpolate(t, [0, 1], [((seed * 13) % 60) - 30, ((seed * 7) % 60) - 30]);
  const ty = interpolate(t, [0, 1], [((seed * 11) % 60) - 30, ((seed * 17) % 60) - 30]);
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translate(${tx}px, ${ty}px)`,
          filter: "brightness(0.55) saturate(1.15) contrast(1.05)",
        }}
      />
      {/* vignette */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,0,0,0) 40%, rgba(0,0,0,0.75) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

/* --- Rotates through images, one per cue, cross-faded --- */
const ImageStage: React.FC<{ images: string[]; cues: Cue[]; frame: number; fps: number }> = ({
  images,
  cues,
  frame,
  fps,
}) => {
  if (!images.length || !cues.length) {
    return (
      <AbsoluteFill style={{ backgroundColor: "#060210" }}>
        <BlobsFallback />
      </AbsoluteFill>
    );
  }
  const nowSec = frame / fps;
  const idx = cues.findIndex((c) => nowSec >= c.start && nowSec < c.end);
  const activeCueIdx = idx === -1 ? cues.length - 1 : idx;
  const cue = cues[activeCueIdx];
  const imgIdx = activeCueIdx % images.length;
  const prevImgIdx = (activeCueIdx - 1 + images.length) % images.length;

  const localSec = nowSec - cue.start;
  const dur = Math.max(0.2, cue.end - cue.start);
  const progress = Math.max(0, Math.min(1, localSec / dur));
  const fadeIn = interpolate(localSec, [0, 0.35], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Outgoing image (previous cue's) fading out */}
      <AbsoluteFill style={{ opacity: 1 - fadeIn }}>
        <KenBurns src={images[prevImgIdx]} t={1} seed={prevImgIdx} />
      </AbsoluteFill>
      {/* Incoming image fading in, with Ken Burns through the whole cue */}
      <AbsoluteFill style={{ opacity: fadeIn }}>
        <KenBurns src={images[imgIdx]} t={progress} seed={imgIdx} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const BlobsFallback: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      {[0, 1, 2].map((i) => {
        const ox = Math.sin(t * 0.5 + i) * 150;
        const oy = Math.cos(t * 0.4 + i * 1.2) * 120;
        const hue = (i * 80 + t * 15) % 360;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${20 + i * 30}%`,
              top: `${30 + (i % 2) * 40}%`,
              width: 800,
              height: 800,
              transform: `translate(-50%, -50%) translate(${ox}px, ${oy}px)`,
              background: `radial-gradient(circle, hsla(${hue},70%,50%,0.5), transparent 65%)`,
              filter: "blur(50px)",
              mixBlendMode: "screen",
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

/* --- Subtle floating dust particles (not distracting) --- */
const Particles: React.FC<{ count?: number }> = ({ count = 25 }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {new Array(count).fill(0).map((_, i) => {
        const seedX = random(`px-${i}`);
        const seedY = random(`py-${i}`);
        const seedSpeed = 0.3 + random(`ps-${i}`) * 0.5;
        const size = 2 + random(`pz-${i}`) * 4;
        const x = (seedX * width + t * 20 * seedSpeed) % width;
        const y = (seedY * height - t * 25 * seedSpeed + height * 2) % height;
        const alpha = 0.15 + 0.35 * (0.5 + 0.5 * Math.sin(t * 0.8 + i));
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: size,
              height: size,
              borderRadius: "50%",
              background: "#fff",
              opacity: alpha,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

/* --- Full-sentence subtitle: pop in once, hold, fade out --- */
const Caption: React.FC<{ cue: Cue; frame: number; fps: number }> = ({ cue, frame, fps }) => {
  const localSec = frame / fps - cue.start;
  const dur = Math.max(0.3, cue.end - cue.start);

  const pop = spring({
    frame: localSec * fps,
    fps,
    config: { damping: 14, stiffness: 130 },
  });
  const scale = interpolate(pop, [0, 1], [0.7, 1], { extrapolateRight: "clamp" });
  const translateY = interpolate(pop, [0, 1], [40, 0], { extrapolateRight: "clamp" });
  // Build a safe monotonically-increasing input range for any duration.
  const inA = 0;
  const inB = Math.min(0.2, dur * 0.25);
  const inD = dur;
  const inC = Math.max(inB + 0.001, dur - Math.min(0.25, dur * 0.25));
  const opacity = interpolate(
    localSec,
    [inA, inB, inC, inD],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 180 }}>
      <div
        style={{
          transform: `translateY(${translateY}px) scale(${scale})`,
          opacity,
          fontFamily: "Impact, Arial Black, sans-serif",
          fontSize: 68,
          lineHeight: 1.08,
          color: "#fff",
          textAlign: "center",
          textTransform: "uppercase",
          letterSpacing: 1,
          maxWidth: 900,
          padding: "18px 28px",
          background: "rgba(0,0,0,0.55)",
          borderRadius: 18,
          textShadow:
            "3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000",
          border: "3px solid rgba(255,216,74,0.85)",
          boxShadow: "0 8px 40px rgba(0,0,0,0.7)",
        }}
      >
        {cue.text}
      </div>
    </AbsoluteFill>
  );
};

const ProgressBar: React.FC<{ frame: number; totalFrames: number }> = ({ frame, totalFrames }) => {
  const pct = Math.min(1, frame / Math.max(1, totalFrames));
  return (
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        height: 12,
        width: `${pct * 100}%`,
        background: "linear-gradient(90deg, #ff3366, #ff9933, #ffcc00)",
        boxShadow: "0 0 20px rgba(255,150,80,0.9)",
      }}
    />
  );
};

const Watermark: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pulse = 1 + 0.025 * Math.sin((frame / fps) * 2.5);
  return (
    <div
      style={{
        position: "absolute",
        top: 70,
        left: 0,
        right: 0,
        textAlign: "center",
        fontFamily: "Impact, Arial Black, sans-serif",
        fontSize: 42,
        color: "rgba(255,255,255,0.85)",
        letterSpacing: 6,
        transform: `scale(${pulse})`,
        textShadow: "0 0 14px rgba(0,0,0,0.95), 2px 2px 0 #000",
      }}
    >
      HISTORY IN 60 SECONDS
    </div>
  );
};

const IntroBurst: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  if (t > 0.6) return null;
  const s = spring({ frame, fps, config: { damping: 9, stiffness: 150 } });
  const scale = interpolate(s, [0, 1], [0.2, 3.5], { extrapolateRight: "clamp" });
  const opacity = interpolate(t, [0, 0.15, 0.5, 0.6], [0, 0.85, 0.2, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: "radial-gradient(circle, #fff 0%, rgba(255,255,255,0) 70%)",
          transform: `scale(${scale})`,
          opacity,
        }}
      />
    </AbsoluteFill>
  );
};

export const Shorts: React.FC<ShortsProps> = ({ voiceSrc, subtitles, images = [] }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const now = frame / fps;
  const cue = subtitles.find((c) => now >= c.start && now < c.end);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <ImageStage images={images} cues={subtitles} frame={frame} fps={fps} />
      <Particles count={20} />
      <IntroBurst />
      <Audio src={staticFile(voiceSrc)} />
      {cue && <Caption cue={cue} frame={frame} fps={fps} />}
      <ProgressBar frame={frame} totalFrames={durationInFrames} />
    </AbsoluteFill>
  );
};
