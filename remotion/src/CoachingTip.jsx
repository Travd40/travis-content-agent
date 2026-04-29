import {
  AbsoluteFill,
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

export const CoachingTip = ({ category, tip, website, coachName, bookLink, calendlyLink }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

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
  const ctaOpacity = interpolate(frame, [160, 185], [0, 1], {
    extrapolateRight: 'clamp',
  });

  // --- Bottom gold line ---
  const bottomLineWidth = interpolate(frame, [155, 185], [0, 100], {
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
          {category}
        </div>
      </div>

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
        <p style={{
          color: COLORS.offWhite,
          fontSize: 58,
          lineHeight: 1.45,
          textAlign: 'center',
          margin: 0,
          fontStyle: 'italic',
        }}>
          <AnimatedWords text={tip} startFrame={55} fps={fps} />
        </p>
      </div>

      {/* Bottom gold divider */}
      <div style={{
        position: 'absolute',
        bottom: 250,
        left: `${(100 - bottomLineWidth) / 2}%`,
        width: `${bottomLineWidth}%`,
        height: 2,
        backgroundColor: COLORS.gold,
      }} />

      {/* CTA */}
      <div style={{
        position: 'absolute',
        bottom: 110,
        left: 0,
        right: 0,
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
          calendly.com/travd40/15-minute-strategy-call
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
