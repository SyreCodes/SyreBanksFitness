import { useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import { mediaPlaybackUrl } from '../../services/media';

type Props = {
  name: string;
  videoUrl?: string | null;
  videoMediaId?: string | null;
  className?: string;
  linkClassName?: string;
  linkText?: string;
};

export function ExerciseDemonstration({ name, videoUrl, videoMediaId, className, linkClassName, linkText = 'Open video demonstration' }: Props) {
  const [playbackFailed, setPlaybackFailed] = useState(false);
  const url = mediaPlaybackUrl(videoUrl);
  if (!url) return null;
  if (!videoMediaId) return <a className={linkClassName} href={url} target="_blank" rel="noreferrer">{linkText} <ArrowUpRight size={18} /></a>;
  return <div className={className} style={{ margin: '16px 0' }}>
    <video
      aria-label={`${name} video demonstration`}
      src={url}
      controls
      playsInline
      preload="metadata"
      onError={() => setPlaybackFailed(true)}
      onCanPlay={() => setPlaybackFailed(false)}
      style={{ display: 'block', width: '100%', maxHeight: 360, aspectRatio: '16 / 9', background: '#20291a' }}
    >Your browser cannot play this video.</video>
    {playbackFailed && <p role="alert">The demonstration could not be played. <a href={url} target="_blank" rel="noreferrer">Open the video directly</a>.</p>}
  </div>;
}
