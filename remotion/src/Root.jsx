import { Composition } from 'remotion';
import { CoachingTip } from './CoachingTip';

export const RemotionRoot = () => {
  return (
    <>
      <Composition
        id="CoachingTip"
        component={CoachingTip}
        durationInFrames={210}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          category: 'COUPLES COACHING',
          tip: 'A trained partner listens to understand, not just to respond.',
          website: 'travis-coaching-site-1.onrender.com',
          coachName: 'Travis Dixon Coaching',
        }}
      />
    </>
  );
};
