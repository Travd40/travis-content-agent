import {
  AbsoluteFill,
  Audio,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  staticFile,
  Img,
} from 'remotion';

const COLORS = {
  bg:        '#0D0705',
  bgGlow:    '#1E1008',
  gold:      '#C9A844',
  goldLight: '#E8C96A',
  white:     '#FFFFFF',
  offWhite:  '#F5F0E8',
};

// Animate each word in the tip one by one
function AnimatedWords({ text, startFrame, fps }) {
  const frame = useCurrentFrame();
  const words = text.split(' ');

  return (
    <span>
      {words.map((word, i) => {
        const wStart = startFrame + i * 5;
        const opacity = interpolate(frame, [wStart, wStart + 10], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        const y = interpolate(frame, [wStart, wStart + 10], [20, 0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        return (
          <span
            key={i}
            style={{
              opacity,
              display: 'inline-block',
              marginRight: '0.28em',
              transform: `translateY(${y}px)`,
            }}
          >
            {word}
          </span>
        );
      })}
    </span>
  );
}

// Voiceover captions: the phrase being spoken right now, popping in as it starts
function SpokenCaption({ captions, fps }) {
  const frame = useCurrentFrame();
  const t = frame / fps;
  let idx = -1;
  for (let i = 0; i < captions.length; i++) {
    if (captions[i].start <= t) idx = i;
  }
  if (idx < 0) return null;
  const cap = captions[idx];
  // Hold each phrase until the next one starts, but clear it after a long silence
  const next = captions[idx + 1];
  const holdUntil = next ? next.start : cap.end + 1.5;
  if (t > holdUntil) return null;
  const local = frame - Math.round(cap.start * fps);
  const pop = spring({ fps, frame: local, from: 0.85, to: 1, config: { damping: 14, stiffness: 180 } });
  const opacity = interpolate(local, [0, 4], [0, 1], { extrapolateRight: 'clamp' });
  return (
    <p style={{
      color: idx === 0 ? COLORS.goldLight : COLORS.white,
      fontFamily: '"Arial", sans-serif',
      fontSize: 76,
      fontWeight: 800,
      lineHeight: 1.2,
      textAlign: 'center',
      margin: 0,
      opacity,
      transform: `scale(${pop})`,
      textShadow: '0 4px 18px rgba(0,0,0,0.6)',
    }}>
      {cap.text}
    </p>
  );
}

// Logic and Harmony open the video in a coaching session. Each portrait starts
// as a large card, and when Coach Tee takes over it shrinks to a small circle
// beside the logo so the couple stay in view while he gives the tip.
const COUPLE = {
  logic:   { name: 'Logic',   src: 'logic.jpg',   bigLeft: 50,  smallLeft: 230 },
  harmony: { name: 'Harmony', src: 'harmony.jpg', bigLeft: 560, smallLeft: 700 },
};
const CARD = { bigTop: 650, bigW: 470, bigH: 588, smallTop: 115, smallSize: 150 };

function CouplePortrait({ who, speaking, shrink, enter }) {
  const frame = useCurrentFrame();
  const c = COUPLE[who];
  const mix = (a, b) => a + (b - a) * shrink;
  const width = mix(CARD.bigW, CARD.smallSize);
  const height = mix(CARD.bigH, CARD.smallSize);
  const lift = speaking && shrink === 0 ? 1.035 : 1;
  const sway = shrink === 0 ? 3 * Math.sin(frame / 22 + (who === 'logic' ? 0 : 2)) : 0;
  return (
    <div style={{
      position: 'absolute',
      left: mix(c.bigLeft, c.smallLeft),
      top: mix(CARD.bigTop, CARD.smallTop) + sway + (1 - enter) * 120,
      width,
      height,
      borderRadius: mix(28, 75),
      overflow: 'hidden',
      border: `${mix(5, 4)}px solid ${speaking || shrink > 0 ? COLORS.goldLight : COLORS.gold}`,
      boxShadow: speaking && shrink === 0 ? '0 0 46px rgba(232,201,106,0.45)' : '0 12px 40px rgba(0,0,0,0.6)',
      opacity: enter * (speaking || shrink > 0 ? 1 : mix(0.6, 1)),
      transform: `scale(${lift})`,
      backgroundColor: '#1c1c1c',
    }}>
      <Img src={staticFile(c.src)} style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center 18%', display: 'block' }} />
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        padding: '34px 0 16px',
        background: 'linear-gradient(to top, rgba(0,0,0,0.85), rgba(0,0,0,0))',
        textAlign: 'center',
        color: COLORS.goldLight,
        fontFamily: '"Arial", sans-serif',
        fontSize: 34,
        fontWeight: 800,
        letterSpacing: 4,
        textTransform: 'uppercase',
        opacity: 1 - shrink,
      }}>
        {c.name}
      </div>
    </div>
  );
}

// What Logic or Harmony is saying right now, in a bubble that points at them
function SceneBubble({ line, fps }) {
  const frame = useCurrentFrame();
  if (!line) return null;
  const local = frame - Math.round(line.start * fps);
  const pop = spring({ fps, frame: local, from: 0.9, to: 1, config: { damping: 14, stiffness: 180 } });
  const opacity = interpolate(local, [0, 4], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const tailX = COUPLE[line.speaker].bigLeft + CARD.bigW / 2 - 50;
  return (
    <div style={{
      position: 'absolute', left: 50, right: 50, top: 440, height: 180,
      display: 'flex', alignItems: 'flex-end', justifyContent: line.speaker === 'logic' ? 'flex-start' : 'flex-end',
      opacity, transform: `scale(${pop})`, transformOrigin: `${tailX}px 100%`,
    }}>
      <div style={{
        backgroundColor: COLORS.offWhite,
        color: COLORS.bg,
        fontFamily: '"Arial", sans-serif',
        fontSize: 54,
        fontWeight: 800,
        lineHeight: 1.18,
        textAlign: 'center',
        padding: '22px 38px',
        minWidth: 380,
        borderRadius: 30,
        maxWidth: 980,
        boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
      }}>
        {line.text}
      </div>
      <div style={{
        position: 'absolute', left: tailX - 22, bottom: -24, width: 0, height: 0,
        borderLeft: '22px solid transparent', borderRight: '22px solid transparent',
        borderTop: `26px solid ${COLORS.offWhite}`,
      }} />
    </div>
  );
}

export const CoachingTip = ({ category, tip, hook, website, coachName, bookLink, calendlyLink, audioSrc, captions, sceneEnd }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const allCaptions = Array.isArray(captions) ? captions : [];
  // With a scene, the couple's lines show in speech bubbles and only Coach
  // Tee's words use the big center captions.
  const hasScene = typeof sceneEnd === 'number' && sceneEnd > 0
    && allCaptions.some((c) => c.speaker === 'logic' || c.speaker === 'harmony');
  const sceneLines = hasScene ? allCaptions.filter((c) => c.speaker === 'logic' || c.speaker === 'harmony') : [];
  captions = hasScene ? allCaptions.filter((c) => c.speaker === 'coach') : allCaptions;
  const hasCaptions = captions.length > 0;
  const tNow = frame / fps;
  let sceneLine = null;
  for (const l of sceneLines) {
    if (l.start <= tNow && tNow < sceneEnd) sceneLine = l;
  }
  // The couple stay "speaking" through the short pause after each line
  const speakingNow = sceneLine ? sceneLine.speaker : null;
  const sceneEndFrame = hasScene ? Math.round(sceneEnd * fps) : 0;
  const shrink = hasScene
    ? interpolate(frame, [sceneEndFrame - 8, sceneEndFrame + 10], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
    : 1;
  const coupleEnter = spring({ fps, frame: frame - 4, from: 0, to: 1, config: { damping: 16, stiffness: 110 } });
  // CTA fades in ~2s before the end, whatever the video length is
  const ctaStart = Math.max(150, durationInFrames - 60);

  // --- Hook question: owns the first ~2s, then the tip animates in ---
  const tipStart = hook ? 75 : 55;
  const hookOpacity = hook && !hasCaptions
    ? interpolate(frame, [0, 8, 58, 70], [0, 1, 1, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      })
    : 0;
  const hookScale = spring({ fps, frame, from: 0.92, to: 1, config: { damping: 16, stiffness: 140 } });

  // --- Logo ---
  const logoOpacity = interpolate(frame, [0, 25], [0, 1], {
    extrapolateRight: 'clamp',
  });
  const logoScale = spring({ fps, frame, from: 0.7, to: 1, config: { damping: 18, stiffness: 120 } });

  // --- Top gold line ---
  const lineWidth = interpolate(frame, [20, 50], [0, 100], {
    extrapolateRight: 'clamp',
  });

  // --- Category badge ---
  const catOpacity = interpolate(frame, [35, 55], [0, 1], {
    extrapolateRight: 'clamp',
  });
  const catY = interpolate(frame, [35, 55], [24, 0], {
    extrapolateRight: 'clamp',
  });

  // --- Bottom CTA ---
  const ctaOpacity = interpolate(frame, [ctaStart, ctaStart + 25], [0, 1], {
    extrapolateRight: 'clamp',
  });

  // --- Bottom gold line ---
  const bottomLineWidth = interpolate(frame, [ctaStart - 5, ctaStart + 25], [0, 100], {
    extrapolateRight: 'clamp',
  });

  // --- Travis's photo (bottom right) ---
  const teeEnter = spring({ fps, frame: frame - 40, from: 0, to: 1, config: { damping: 14, stiffness: 90 } });
  const teeBob = 6 * Math.sin(frame / 20);
  const teeY = interpolate(teeEnter, [0, 1], [280, 0]) + teeBob;
  const teeRot = 1.4 * Math.sin(frame / 26);
  const teeOpacity = interpolate(frame, [40, 62], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const tagOpacity = interpolate(frame, [70, 90], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 20%, ${COLORS.bgGlow} 0%, ${COLORS.bg} 65%)`,
        fontFamily: 'Georgia, "Times New Roman", serif',
        overflow: 'hidden',
      }}
    >
      {/* Ambient music bed — ducked under the voiceover when one exists */}
      <Audio src={staticFile('music.wav')} volume={audioSrc ? 0.14 : 0.9} />

      {/* ElevenLabs voiceover (only when the agent generated one) */}
      {audioSrc ? <Audio src={staticFile(audioSrc)} volume={1} /> : null}

      {/* Subtle gold corner accents */}
      <div style={{ position: 'absolute', top: 40, left: 40, width: 60, height: 60,
        borderTop: `3px solid ${COLORS.gold}`, borderLeft: `3px solid ${COLORS.gold}`, opacity: logoOpacity }} />
      <div style={{ position: 'absolute', top: 40, right: 40, width: 60, height: 60,
        borderTop: `3px solid ${COLORS.gold}`, borderRight: `3px solid ${COLORS.gold}`, opacity: logoOpacity }} />
      <div style={{ position: 'absolute', bottom: 40, left: 40, width: 60, height: 60,
        borderBottom: `3px solid ${COLORS.gold}`, borderLeft: `3px solid ${COLORS.gold}`, opacity: ctaOpacity }} />
      <div style={{ position: 'absolute', bottom: 40, right: 40, width: 60, height: 60,
        borderBottom: `3px solid ${COLORS.gold}`, borderRight: `3px solid ${COLORS.gold}`, opacity: ctaOpacity }} />

      {/* Logo */}
      <div style={{
        position: 'absolute',
        top: 110,
        left: 0,
        right: 0,
        display: 'flex',
        justifyContent: 'center',
        opacity: logoOpacity,
        transform: `scale(${logoScale})`,
      }}>
        <Img
          src={staticFile('logo.png')}
          style={{ width: 160, height: 'auto' }}
        />
      </div>

      {/* Top gold divider */}
      <div style={{
        position: 'absolute',
        top: 340,
        left: `${(100 - lineWidth) / 2}%`,
        width: `${lineWidth}%`,
        height: 2,
        backgroundColor: COLORS.gold,
      }} />

      {/* Category label */}
      <div style={{
        position: 'absolute',
        top: 368,
        left: 0,
        right: 0,
        display: 'flex',
        justifyContent: 'center',
        opacity: catOpacity,
        transform: `translateY(${catY}px)`,
      }}>
        <div style={{
          backgroundColor: COLORS.gold,
          color: COLORS.bg,
          fontFamily: '"Arial", sans-serif',
          fontSize: 30,
          fontWeight: 800,
          letterSpacing: 5,
          padding: '10px 32px',
          textTransform: 'uppercase',
        }}>
          {hasScene && shrink < 0.5 ? 'In session with Coach Tee' : category}
        </div>
      </div>

      {/* Logic and Harmony: the opening scene, then small beside the logo */}
      {hasScene ? (
        <>
          <CouplePortrait who="logic" speaking={speakingNow === 'logic'} shrink={shrink} enter={coupleEnter} />
          <CouplePortrait who="harmony" speaking={speakingNow === 'harmony'} shrink={shrink} enter={coupleEnter} />
          {shrink < 0.5 ? <SceneBubble line={sceneLine} fps={fps} /> : null}
        </>
      ) : null}

      {/* Main tip text */}
      <div style={{
        position: 'absolute',
        top: 470,
        left: 80,
        right: 80,
        bottom: 320,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        {hasCaptions ? (
          <SpokenCaption captions={captions} fps={fps} />
        ) : (
          <p style={{
            color: COLORS.offWhite,
            fontSize: 58,
            lineHeight: 1.45,
            textAlign: 'center',
            margin: 0,
            fontStyle: 'italic',
          }}>
            <AnimatedWords text={tip} startFrame={tipStart} fps={fps} />
          </p>
        )}
      </div>

      {/* Hook question (first ~2 seconds) */}
      {hook && !hasCaptions ? (
        <div style={{
          position: 'absolute',
          top: 470,
          left: 70,
          right: 70,
          bottom: 320,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: hookOpacity,
          transform: `scale(${hookScale})`,
        }}>
          <p style={{
            color: COLORS.goldLight,
            fontFamily: '"Arial", sans-serif',
            fontSize: 72,
            fontWeight: 800,
            lineHeight: 1.25,
            textAlign: 'center',
            margin: 0,
          }}>
            {hook}
          </p>
        </div>
      ) : null}

      {/* Bottom gold divider */}
      <div style={{
        position: 'absolute',
        bottom: 250,
        left: `${(100 - bottomLineWidth) / 2}%`,
        width: `${bottomLineWidth}%`,
        height: 2,
        backgroundColor: COLORS.gold,
      }} />

      {/* Travis's photo — viewers should see the real coach behind the voice */}
      <div style={{
        position: 'absolute',
        right: 40,
        bottom: 96,
        width: 250,
        height: 250,
        borderRadius: '50%',
        overflow: 'hidden',
        border: `6px solid ${COLORS.gold}`,
        boxShadow: '0 12px 40px rgba(0,0,0,0.6)',
        backgroundColor: COLORS.white,
        opacity: teeOpacity,
        transform: `translateY(${teeY}px) rotate(${teeRot}deg)`,
        transformOrigin: 'bottom center',
      }}>
        <Img src={staticFile(hasScene ? 'coach-tee-full.png' : 'travis.jpg')}
          style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: hasScene ? 'center 8%' : 'center', display: 'block',
            backgroundColor: hasScene ? '#2a1a12' : undefined }} />
      </div>

      {/* Name tag */}
      <div style={{
        position: 'absolute',
        right: 70,
        bottom: 362,
        opacity: tagOpacity,
        transform: `translateY(${teeBob}px)`,
      }}>
        <div style={{
          backgroundColor: COLORS.gold,
          color: COLORS.bg,
          fontFamily: '"Arial", sans-serif',
          fontSize: 22,
          fontWeight: 800,
          letterSpacing: 3,
          padding: '6px 16px',
          borderRadius: 999,
          textTransform: 'uppercase',
        }}>
          {hasScene ? 'Coach Tee' : 'Travis Dixon'}
        </div>
      </div>

      {/* CTA — shifted left so the photo has its corner */}
      <div style={{
        position: 'absolute',
        bottom: 110,
        left: 0,
        right: 270,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 10,
        opacity: ctaOpacity,
      }}>
        <div style={{
          color: COLORS.gold,
          fontFamily: '"Arial", sans-serif',
          fontSize: 34,
          fontWeight: 700,
          letterSpacing: 3,
          textTransform: 'uppercase',
        }}>
          {coachName}
        </div>
        <div style={{
          color: COLORS.offWhite,
          fontFamily: '"Arial", sans-serif',
          fontSize: 26,
          opacity: 0.75,
        }}>
          {website}
        </div>
        <div style={{
          color: COLORS.white,
          fontFamily: '"Arial", sans-serif',
          fontSize: 26,
          fontWeight: 700,
          letterSpacing: 1,
          marginTop: 4,
        }}>
          📞 FREE 15-Min Strategy Call
        </div>
        <div style={{
          color: COLORS.goldLight,
          fontFamily: '"Arial", sans-serif',
          fontSize: 20,
          opacity: 0.9,
        }}>
          travisdixoncoaching.com/call
        </div>
        {bookLink && (
          <div style={{
            color: COLORS.gold,
            fontFamily: '"Arial", sans-serif',
            fontSize: 20,
            opacity: 0.8,
            letterSpacing: 1,
            marginTop: 2,
          }}>
            📖 amazon.com/dp/B0GPSNXGY8
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
