import { useRef, useState } from 'react';
import { Play, Pause, Volume2, VolumeX, Maximize2, Download } from 'lucide-react';
import type { VideoData, SceneChapter, ClipData } from '../../types';

const T = {
  gold: '#D4A843', goldLight: '#F0D78C', dim: '#888',
  bg: '#111', cardBg: '#1a1a1a', border: 'rgba(255,255,255,0.08)',
};

interface TrailerPlayerProps {
  video: VideoData;
  projectTitle?: string;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

/** Full assembled trailer player */
function AssembledPlayer({ video, projectTitle }: { video: VideoData; projectTitle?: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [activeChapter, setActiveChapter] = useState<SceneChapter | null>(null);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) videoRef.current.pause();
    else videoRef.current.play();
    setIsPlaying(!isPlaying);
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const t = videoRef.current.currentTime;
    setCurrentTime(t);
    const chapter = video.chapters.find((c) => t >= c.start_time && t < c.end_time);
    setActiveChapter(chapter ?? null);
  };

  const seekTo = (time: number) => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = time;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ position: 'relative', borderRadius: 12, overflow: 'hidden', background: '#000' }}>
        <video
          ref={videoRef}
          src={video.video_url!}
          onTimeUpdate={handleTimeUpdate}
          onEnded={() => setIsPlaying(false)}
          muted={isMuted}
          style={{ width: '100%', aspectRatio: '16/9', display: 'block' }}
        />
        <div style={{
          position: 'absolute', inset: '0 0 0 0', display: 'flex', flexDirection: 'column',
          justifyContent: 'flex-end', padding: 16,
          background: 'linear-gradient(transparent 60%, rgba(0,0,0,0.8))',
          opacity: 0, transition: 'opacity 0.2s',
        }}
          onMouseEnter={e => (e.currentTarget.style.opacity = '1')}
          onMouseLeave={e => (e.currentTarget.style.opacity = '0')}
        >
          <div
            style={{ height: 4, background: 'rgba(255,255,255,0.2)', borderRadius: 2, marginBottom: 12, cursor: 'pointer', position: 'relative' }}
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              seekTo(((e.clientX - rect.left) / rect.width) * video.duration);
            }}
          >
            <div style={{ height: '100%', background: '#fff', borderRadius: 2, width: `${(currentTime / video.duration) * 100}%` }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button onClick={togglePlay} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>
              {isPlaying ? <Pause size={20} /> : <Play size={20} />}
            </button>
            <button onClick={() => setIsMuted(!isMuted)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>
              {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
            </button>
            <span style={{ fontSize: 12, color: '#ccc', fontFamily: 'monospace' }}>
              {formatTime(currentTime)} / {formatTime(video.duration)}
            </span>
            {activeChapter && <span style={{ fontSize: 12, color: T.dim, marginLeft: 8 }}>{activeChapter.title}</span>}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              <a
                href={video.video_url!}
                download={`${projectTitle || 'storyforge'}-trailer.mp4`}
                style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                title="Download trailer"
              >
                <Download size={18} />
              </a>
              <button
                onClick={() => videoRef.current?.requestFullscreen()}
                style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}
              >
                <Maximize2 size={18} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {video.chapters.length > 0 && (
        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 8 }}>
          {video.chapters.map((ch) => (
            <button
              key={ch.scene_id}
              onClick={() => seekTo(ch.start_time)}
              style={{
                flexShrink: 0, padding: '8px 12px', borderRadius: 8, fontSize: 12,
                background: activeChapter?.scene_id === ch.scene_id ? 'rgba(255,255,255,0.1)' : T.cardBg,
                border: `1px solid ${T.border}`, color: '#aaa', cursor: 'pointer',
              }}
            >
              {ch.title} · {formatTime(ch.start_time)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Individual clips grid — shown when no assembled trailer */
function ClipsGrid({ clips, projectTitle }: { clips: ClipData[]; projectTitle?: string }) {
  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16,
        padding: '8px 12px', borderRadius: 8,
        background: 'rgba(212,168,67,0.08)', border: '1px solid rgba(212,168,67,0.15)',
      }}>
        <span style={{ fontSize: 18 }}>🎬</span>
        <span style={{ fontSize: 13, color: T.goldLight }}>
          {clips.length} clip{clips.length !== 1 ? 's' : ''} generated — individual scenes shown below
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
        {clips.map((clip, i) => (
          <ClipCard key={clip.clip_id} clip={clip} index={i} projectTitle={projectTitle} />
        ))}
      </div>
    </div>
  );
}

function ClipCard({ clip, index, projectTitle }: { clip: ClipData; index: number; projectTitle?: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) videoRef.current.pause();
    else videoRef.current.play();
    setIsPlaying(!isPlaying);
  };

  return (
    <div style={{
      borderRadius: 12, overflow: 'hidden', background: T.cardBg,
      border: `1px solid ${T.border}`,
    }}>
      <div style={{ position: 'relative', cursor: 'pointer' }} onClick={togglePlay}>
        <video
          ref={videoRef}
          src={clip.video_url}
          onEnded={() => setIsPlaying(false)}
          style={{ width: '100%', aspectRatio: '16/9', display: 'block', background: '#000' }}
        />
        {!isPlaying && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(0,0,0,0.3)',
          }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%', background: 'rgba(0,0,0,0.6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Play size={24} color="#fff" />
            </div>
          </div>
        )}
      </div>
      <div style={{ padding: '10px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#ccc' }}>
          Clip {index + 1} — {clip.scene_id.replace(/_/g, ' ')}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: T.dim }}>{clip.duration}s</span>
          <a
            href={clip.video_url}
            download={`${projectTitle || 'clip'}-${index + 1}.mp4`}
            style={{ color: T.gold, display: 'flex' }}
            title="Download clip"
          >
            <Download size={14} />
          </a>
        </div>
      </div>
    </div>
  );
}

export function TrailerPlayer({ video, projectTitle }: TrailerPlayerProps) {
  const hasAssembledVideo = !!video.video_url;
  const readyClips = (video.clips || []).filter(c => c.status === 'ready' && c.video_url);

  // Assembled trailer available — show full player
  if (hasAssembledVideo) {
    return <AssembledPlayer video={video} projectTitle={projectTitle} />;
  }

  // Individual clips available — show clips grid
  if (readyClips.length > 0) {
    return <ClipsGrid clips={readyClips} projectTitle={projectTitle} />;
  }

  // Nothing available
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: 256, borderRadius: 12, background: T.bg,
      border: `1px solid ${T.border}`,
    }}>
      <p style={{ color: T.dim, fontSize: 14 }}>Trailer not yet generated</p>
    </div>
  );
}
