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
        calculateMetadata={({ props }) => ({
          durationInFrames: props.durationInFrames || 210,
        })}
        defaultProps={{
          category: 'COUPLES COACHING',
          tip: 'A trained partner listens to understand, not just to respond.',
          hook: 'Why does it feel like they never hear me?',
          website: 'travisdixoncoaching.com',
          coachName: 'Travis Dixon Coaching',
        }}
      />
    </>
  );
};
