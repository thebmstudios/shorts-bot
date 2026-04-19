import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";

type FaceCardProps = {
  color: string;
  startFrame: number;
  durationFrames: number;
};

// 2 saniyelik görünürlük için 60fps ile durationFrames genelde 120-180 aralığında olur.
// Burada basit bir yüz SVG’si ile merkezi konumda gösteriyoruz.
export const FaceCard: React.FC<FaceCardProps> = ({ color, startFrame, durationFrames }) => {
  const frame = useCurrentFrame();

  // Bu yüz sadece belirtilen aralıkta görünür
  if (frame < startFrame || frame >= startFrame + durationFrames) {
    return null;
  }

  // Basit fade-in/out efektleri (opsiyonel görsellik için kullanılıyor)
  const local = frame - startFrame;
  const fadeIn = Math.min(10, durationFrames);
  const fadeOutStart = durationFrames - Math.min(10, durationFrames);
  const opacity = local < fadeIn ? local / fadeIn : local < durationFrames - 0 ? 1 : (durationFrames - local) / 10;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          transform: "translate(-50%, -50%)",
          width: 320,
          height: 320,
          opacity,
        }}
      >
        <svg viewBox="0 0 200 200" width="100%" height="100%" aria-label="face-card">
          <defs>
            <linearGradient id="grad" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="1" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="1" />
            </linearGradient>
          </defs>
          <circle cx="100" cy="100" r="90" fill={color} opacity="0.9" />
          <circle cx="80" cy="85" r="8" fill="#fff" />
          <circle cx="120" cy="85" r="8" fill="#fff" />
          <path d="M70,120 Q100,140 130,120" stroke="#000" strokeWidth="6" fill="none" strokeLinecap="round" />
        </svg>
      </div>
    </AbsoluteFill>
  );
};
