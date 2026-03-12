import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { animate, stagger, createTimeline } from 'animejs';
import {
  Sparkles, Film, BookOpen, Layers, Video, ArrowRight,
  Clapperboard, Wand2, Palette, Zap, Play, PenTool,
} from 'lucide-react';

/* ═══ COLORS ═══ */
const C = {
  matte: '#0a0a0a',
  matteCard: '#111111',
  matteLight: '#161616',
  goldShiny: 'linear-gradient(135deg, #FFF1B8, #F0D78C, #D4A843, #8B6914)',
  goldText: 'linear-gradient(135deg, #FFF1B8, #F0D78C, #D4A843)',
  gold: '#D4A843',
  goldLight: '#F0D78C',
  goldBright: '#FFF1B8',
  goldDark: '#8B6914',
  silverText: 'linear-gradient(135deg, #FFFFFF, #E8E8E8, #C0C0C0)',
  silver: '#C0C0C0',
  silverLight: '#E8E8E8',
};

const centered: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', width: '100%',
};
const goldGradientText: React.CSSProperties = {
  background: C.goldText, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
};
const silverGradientText: React.CSSProperties = {
  background: C.silverText, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
};
const sectionStyle: React.CSSProperties = {
  ...centered, padding: '80px 20px', maxWidth: 900, margin: '0 auto',
};
const divider: React.CSSProperties = {
  width: 60, height: 2, borderRadius: 1, margin: '0 auto 20px',
  background: 'linear-gradient(90deg, #8B6914, #D4A843, #8B6914)',
};

/* ═══ DATA ═══ */
const FEATURES = [
  { icon: BookOpen, title: 'Comics', desc: 'Panels, bubbles, consistent characters' },
  { icon: Layers, title: 'Manga', desc: 'Screen tones, speed lines, dynamic panels' },
  { icon: Film, title: 'Storyboards', desc: 'Shot types & camera annotations' },
  { icon: Video, title: 'Trailers', desc: 'Cinematic video with audio & SFX' },
];

const PIPELINE = [
  { icon: PenTool, label: 'Write your script', desc: 'Write it yourself or let AI help you craft the perfect story' },
  { icon: Palette, label: 'Pick your mode & style', desc: 'Comic, Manga, Storyboard, or Trailer — choose your visual format' },
  { icon: Wand2, label: 'AI generates your scenes', desc: 'Your script becomes scenes — review and edit before generating' },
  { icon: Play, label: 'Generate your visuals', desc: 'Images or video, refined until you\'re happy with every frame' },
];

const CUBE_FACES = [
  { icon: BookOpen, label: 'Comics', color: C.gold },
  { icon: Layers, label: 'Manga', color: C.silver },
  { icon: Film, label: 'Storyboard', color: C.goldLight },
  { icon: Video, label: 'Trailer', color: C.goldBright },
];

/* ═══ COMPONENT ═══ */
export function HomePage() {
  const navigate = useNavigate();
  const mounted = useRef(false);

  useEffect(() => {
    if (mounted.current) return;
    mounted.current = true;

    /* ── Helper ── */
    function onVisible(sel: string, cb: () => void) {
      const el = document.querySelector(sel);
      if (!el) return;
      const obs = new IntersectionObserver((entries) => {
        if (entries[0]?.isIntersecting) { cb(); obs.disconnect(); }
      }, { threshold: 0.05, rootMargin: '0px 0px -20px 0px' });
      obs.observe(el);
    }

    /* ── Hero ── */
    const tl = createTimeline({ defaults: { duration: 800, ease: 'outExpo' } });
    tl.add('.anim-badge',   { opacity: [0, 1], translateY: [20, 0], duration: 600 }, 0);
    tl.add('.anim-title-1', { opacity: [0, 1], translateY: [50, 0] }, 150);
    tl.add('.anim-title-2', { opacity: [0, 1], translateY: [50, 0] }, 300);
    tl.add('.anim-desc',    { opacity: [0, 1], translateY: [25, 0], duration: 600 }, 500);
    tl.add('.anim-cta',     { opacity: [0, 1], translateY: [20, 0], scale: [0.95, 1] }, 650);
    tl.add('.anim-stat',    { opacity: [0, 1], translateY: [15, 0], duration: 500 }, stagger(100, { start: 800 }));

    /* ── Ambient ── */
    animate('.glow-1', { opacity: [0, 0.3, 0], scale: [0.8, 1.2, 0.8], duration: 7000, loop: true, ease: 'inOutSine' });
    animate('.glow-2', { opacity: [0, 0.2, 0], scale: [1, 1.3, 1], duration: 9000, loop: true, ease: 'inOutSine', delay: 3000 });
    animate('.ptcl', {
      opacity: [0, 0.6, 0], translateY: [-10, -100],
      translateX: () => Math.random() * 60 - 30,
      duration: () => 3000 + Math.random() * 2000,
      delay: stagger(300), loop: true, ease: 'outCubic',
    });

    /* ── Cube animation ── */
    // Start stars & bulbs immediately (they loop forever)
    setTimeout(() => {
      // Fade in the whole cube area
      const cubeEl = document.querySelector('.cube-wrap') as HTMLElement;
      if (cubeEl) {
        cubeEl.style.transition = 'opacity 1s ease, transform 1s ease';
        cubeEl.style.opacity = '1';
        cubeEl.style.transform = 'scale(1)';
      }

      // Stars flicker
      animate('.cube-star', {
        opacity: [0, 0.9, 0],
        scale: [0.3, 1.2, 0.3],
        duration: () => 1200 + Math.random() * 1500,
        delay: stagger(120, { from: 'center' }),
        loop: true,
        ease: 'inOutSine',
      });

      // Bulbs pulse
      animate('.cube-bulb', {
        opacity: [0, 0.7, 0],
        scale: [0.5, 1.4, 0.5],
        duration: () => 1800 + Math.random() * 1200,
        delay: stagger(200),
        loop: true,
        ease: 'inOutQuad',
      });
    }, 1200);

    /* ── Sections ── */
    onVisible('.feat-section', () => {
      animate('.feat-card', { opacity: [0, 1], translateY: [30, 0], duration: 600, delay: stagger(100), ease: 'outExpo' });
    });
    onVisible('.pipe-section', () => {
      animate('.pipe-step', { opacity: [0, 1], translateX: [-30, 0], duration: 600, delay: stagger(150), ease: 'outExpo' });
    });
    onVisible('.cta-section', () => {
      animate('.cta-inner', { opacity: [0, 1], translateY: [30, 0], duration: 800, ease: 'outExpo' });
    });
  }, []);

  return (
    <div style={{ ...centered, background: C.matte }}>

      {/* ════════════════ HERO ════════════════ */}
      <section style={{
        ...centered, position: 'relative', padding: '120px 20px 100px', overflow: 'hidden', minHeight: '90vh', justifyContent: 'center',
      }}>
        {/* Grid */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: 'linear-gradient(rgba(212,168,67,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(212,168,67,0.03) 1px, transparent 1px)',
          backgroundSize: '60px 60px',
          maskImage: 'radial-gradient(ellipse 70% 60% at 50% 50%, black 30%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse 70% 60% at 50% 50%, black 30%, transparent 100%)',
        }} />
        <div className="glow-1" style={{ position: 'absolute', width: '45vw', maxWidth: 500, height: '45vw', maxHeight: 500, top: '5%', left: '20%', borderRadius: '50%', filter: 'blur(120px)', background: 'rgba(212,168,67,0.1)', opacity: 0, pointerEvents: 'none' }} />
        <div className="glow-2" style={{ position: 'absolute', width: '35vw', maxWidth: 400, height: '35vw', maxHeight: 400, top: '50%', right: '10%', borderRadius: '50%', filter: 'blur(120px)', background: 'rgba(192,192,192,0.06)', opacity: 0, pointerEvents: 'none' }} />
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="ptcl" style={{ position: 'absolute', width: 2, height: 2, borderRadius: '50%', background: C.gold, opacity: 0, pointerEvents: 'none', left: `${10 + Math.random() * 80}%`, top: `${20 + Math.random() * 60}%` }} />
        ))}

        <div style={{ position: 'relative', zIndex: 10, maxWidth: 640, width: '100%', ...centered }}>
          <div className="anim-badge" style={{ opacity: 0, marginBottom: 28 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 16px', borderRadius: 100, background: 'rgba(212,168,67,0.06)', border: '1px solid rgba(212,168,67,0.15)', fontSize: 11, color: C.goldLight, letterSpacing: '0.06em', textTransform: 'uppercase' as const, fontWeight: 600 }}>
              <Zap size={11} /> Powered by Google Gemini & Veo
            </span>
          </div>
          <h1 className="anim-title-1" style={{ opacity: 0, fontSize: 'clamp(2.5rem, 8vw, 4.5rem)', fontWeight: 800, lineHeight: 1.05, marginBottom: 4, ...silverGradientText }}>From Script</h1>
          <h1 className="anim-title-2" style={{ opacity: 0, fontSize: 'clamp(2.5rem, 8vw, 4.5rem)', fontWeight: 800, lineHeight: 1.05, marginBottom: 24, ...goldGradientText }}>to Screen</h1>
          <p className="anim-desc" style={{ opacity: 0, fontSize: 'clamp(0.85rem, 2vw, 1.1rem)', color: '#999', maxWidth: 460, lineHeight: 1.7, marginBottom: 36 }}>
            Transform any story into comics, manga, storyboards, or cinematic trailers — directed by legendary AI style engines.
          </p>
          <div className="anim-cta" style={{ opacity: 0 }}>
            <GoldButton onClick={() => navigate('/project/new')}>
              <Sparkles size={16} /> Create Your Story <ArrowRight size={15} />
            </GoldButton>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 40, marginTop: 48 }}>
            {[['4', 'Output Modes'], ['5', 'Director Styles'], ['4K', 'Video Quality']].map(([v, l]) => (
              <div key={l} className="anim-stat" style={{ opacity: 0, textAlign: 'center' }}>
                <div style={{ fontSize: 'clamp(1.2rem, 3vw, 1.6rem)', fontWeight: 700, ...goldGradientText }}>{v}</div>
                <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase' as const, letterSpacing: '0.08em', marginTop: 2 }}>{l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════ SPINNING CUBE ════════════════ */}
      <section className="cube-section" style={{ ...centered, padding: '60px 20px 80px' }}>
        <div style={divider} />
        <h2 style={{ fontSize: 'clamp(1.4rem, 4vw, 2.2rem)', fontWeight: 700, marginBottom: 8, ...silverGradientText }}>
          Ideas Come Alive
        </h2>
        <p style={{ fontSize: 'clamp(0.75rem, 1.5vw, 0.9rem)', color: '#777', maxWidth: 380, marginBottom: 48 }}>
          Watch your imagination transform into stunning visual stories
        </p>

        {/* Cube container */}
        <div className="cube-wrap" style={{ opacity: 0, transform: 'scale(0.7)', position: 'relative', width: 280, height: 280 }}>
          {/* Stars */}
          {Array.from({ length: 20 }).map((_, i) => {
            const angle = (i / 20) * Math.PI * 2;
            const radius = 120 + Math.random() * 60;
            const x = 140 + Math.cos(angle) * radius;
            const y = 140 + Math.sin(angle) * radius;
            return (
              <div key={`s${i}`} className="cube-star" style={{
                position: 'absolute', left: x, top: y,
                width: i % 3 === 0 ? 6 : 3,
                height: i % 3 === 0 ? 6 : 3,
                borderRadius: '50%',
                background: i % 2 === 0 ? C.silverLight : C.silver,
                boxShadow: `0 0 ${i % 3 === 0 ? 8 : 4}px ${i % 2 === 0 ? 'rgba(255,255,255,0.6)' : 'rgba(192,192,192,0.4)'}`,
                opacity: 0, pointerEvents: 'none',
              }} />
            );
          })}

          {/* Bulbs */}
          {Array.from({ length: 8 }).map((_, i) => {
            const angle = (i / 8) * Math.PI * 2 + 0.3;
            const radius = 100 + Math.random() * 40;
            const x = 140 + Math.cos(angle) * radius;
            const y = 140 + Math.sin(angle) * radius;
            return (
              <div key={`b${i}`} className="cube-bulb" style={{
                position: 'absolute', left: x - 4, top: y - 4,
                width: 8, height: 8, borderRadius: '50%',
                background: `radial-gradient(circle, ${C.goldBright}, ${C.gold})`,
                boxShadow: `0 0 12px ${C.gold}, 0 0 4px ${C.goldBright}`,
                opacity: 0, pointerEvents: 'none',
              }} />
            );
          })}

          {/* 3D Cube */}
          <div style={{
            width: 160, height: 160,
            position: 'absolute', left: '50%', top: '50%',
            marginLeft: -80, marginTop: -80,
            perspective: '800px',
            perspectiveOrigin: '50% 50%',
          }}>
            <div className="cube-spinner" style={{
              width: 160, height: 160,
              position: 'relative',
              transformStyle: 'preserve-3d' as const,
              WebkitTransformStyle: 'preserve-3d' as any,
              animation: 'cubeRotate 10s ease-in-out infinite',
            }}>
              {/* Front */}
              <CubeFace transform="translateZ(80px)" face={CUBE_FACES[0]} />
              {/* Right */}
              <CubeFace transform="rotateY(90deg) translateZ(80px)" face={CUBE_FACES[1]} />
              {/* Back */}
              <CubeFace transform="rotateY(180deg) translateZ(80px)" face={CUBE_FACES[2]} />
              {/* Left */}
              <CubeFace transform="rotateY(-90deg) translateZ(80px)" face={CUBE_FACES[3]} />
              {/* Top */}
              <CubeFaceBlank transform="rotateX(90deg) translateZ(80px)" />
              {/* Bottom */}
              <CubeFaceBlank transform="rotateX(-90deg) translateZ(80px)" />
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════ FEATURES ════════════════ */}
      <section className="feat-section" style={sectionStyle}>
        <div style={divider} />
        <h2 style={{ fontSize: 'clamp(1.4rem, 4vw, 2.2rem)', fontWeight: 700, marginBottom: 8, ...silverGradientText }}>
          Four Ways to Tell Your Story
        </h2>
        <p style={{ fontSize: 'clamp(0.75rem, 1.5vw, 0.9rem)', color: '#777', maxWidth: 400, marginBottom: 48 }}>
          One platform. Multiple visual formats. All AI-powered.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, width: '100%' }}>
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div key={f.title} className="feat-card" style={{
                opacity: 0, padding: '24px 16px', borderRadius: 14, textAlign: 'center',
                background: `linear-gradient(145deg, ${C.matteCard}, ${C.matte})`,
                border: '1px solid rgba(212,168,67,0.08)',
                boxShadow: '0 2px 16px rgba(0,0,0,0.3)',
                transition: 'border-color 0.4s, transform 0.3s',
                display: 'flex', flexDirection: 'column', alignItems: 'center',
              }}
                onMouseOver={(e) => { e.currentTarget.style.borderColor = 'rgba(240,215,140,0.25)'; e.currentTarget.style.transform = 'translateY(-3px)'; }}
                onMouseOut={(e) => { e.currentTarget.style.borderColor = 'rgba(212,168,67,0.08)'; e.currentTarget.style.transform = 'translateY(0)'; }}
              >
                <div style={{
                  width: 36, height: 36, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: 'rgba(212,168,67,0.06)', border: '1px solid rgba(212,168,67,0.1)', marginBottom: 12,
                }}>
                  <Icon size={18} color={C.gold} />
                </div>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: C.silverLight, marginBottom: 4 }}>{f.title}</h3>
                <p style={{ fontSize: 11, color: '#888', lineHeight: 1.5 }}>{f.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ════════════════ PIPELINE ════════════════ */}
      <section className="pipe-section" style={{ ...sectionStyle, maxWidth: 560 }}>
        <div style={divider} />
        <h2 style={{ fontSize: 'clamp(1.4rem, 4vw, 2.2rem)', fontWeight: 700, marginBottom: 8, ...silverGradientText }}>
          How It Works
        </h2>
        <p style={{ fontSize: 'clamp(0.75rem, 1.5vw, 0.9rem)', color: '#777', maxWidth: 380, marginBottom: 48 }}>
          Four steps. Zero creative limits.
        </p>

        <div style={{ position: 'relative', width: '100%', maxWidth: 440, display: 'flex', flexDirection: 'column', gap: 28 }}>
          <div style={{
            position: 'absolute', left: 19, top: 40, bottom: 20, width: 2,
            background: 'linear-gradient(180deg, rgba(212,168,67,0.4), rgba(212,168,67,0.03))',
          }} />
          {PIPELINE.map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={s.label} className="pipe-step" style={{ display: 'flex', alignItems: 'flex-start', gap: 18, opacity: 0 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: '50%', flexShrink: 0, position: 'relative', zIndex: 2,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: C.matte, border: `2px solid ${C.goldDark}`,
                  boxShadow: '0 0 12px rgba(212,168,67,0.1)',
                }}>
                  <Icon size={16} color={C.gold} />
                </div>
                <div style={{ paddingTop: 2, textAlign: 'left' }}>
                  <div style={{ fontSize: 10, color: C.goldDark, textTransform: 'uppercase' as const, letterSpacing: '0.08em', fontWeight: 600, marginBottom: 2 }}>Step {i + 1}</div>
                  <h3 style={{ fontSize: 15, fontWeight: 600, color: C.silverLight, marginBottom: 3 }}>{s.label}</h3>
                  <p style={{ fontSize: 13, color: '#888' }}>{s.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ════════════════ CTA ════════════════ */}
      <section className="cta-section" style={{ ...centered, padding: '100px 20px' }}>
        <div className="cta-inner" style={{ ...centered, opacity: 0, maxWidth: 460 }}>
          <h2 style={{ fontSize: 'clamp(1.4rem, 4vw, 2.2rem)', fontWeight: 700, marginBottom: 12, ...goldGradientText }}>
            Ready to Direct?
          </h2>
          <p style={{ fontSize: 'clamp(0.75rem, 1.5vw, 0.9rem)', color: '#777', maxWidth: 360, marginBottom: 32 }}>
            Write your script. Choose your style. Let AI bring your story to life.
          </p>
          <GoldButton onClick={() => navigate('/project/new')}>
            <Clapperboard size={16} /> Start Creating <ArrowRight size={15} />
          </GoldButton>
        </div>
      </section>

      {/* ════════════════ FOOTER ════════════════ */}
      <footer style={{ width: '100%', borderTop: '1px solid rgba(212,168,67,0.06)', padding: '24px 20px', textAlign: 'center' }}>
        <p style={{ fontSize: 11, color: '#555' }}>
          Built with <span style={{ color: C.goldDark }}>♦</span> by the StoryForge Pro robot crew · Powered by Google AI
        </p>
      </footer>

      {/* Keyframes — injected once */}
      <style>{`
        @keyframes cubeRotate {
          0%   { transform: rotateX(-15deg) rotateY(0deg); }
          25%  { transform: rotateX(-8deg)  rotateY(90deg); }
          50%  { transform: rotateX(-15deg) rotateY(180deg); }
          75%  { transform: rotateX(-8deg)  rotateY(270deg); }
          100% { transform: rotateX(-15deg) rotateY(360deg); }
        }
        .cube-spinner {
          transform-style: preserve-3d !important;
        }
      `}</style>
    </div>
  );
}

/* ═══ SUB-COMPONENTS ═══ */

function CubeFace({ transform, face }: { transform: string; face: typeof CUBE_FACES[0] }) {
  const Icon = face.icon;
  return (
    <div style={{
      position: 'absolute', width: 160, height: 160,
      transform,
      backfaceVisibility: 'hidden' as const,
      WebkitBackfaceVisibility: 'hidden' as any,
      borderRadius: 20,
      background: 'linear-gradient(145deg, #2a2210, #181208, #0d0a04)',
      border: '1.5px solid rgba(212,168,67,0.25)',
      boxShadow: 'inset 0 0 30px rgba(212,168,67,0.06), 0 0 20px rgba(212,168,67,0.08), inset 0 1px 0 rgba(255,241,184,0.15)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10,
    }}>
      {/* Metallic sheen overlay */}
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 20,
        background: 'linear-gradient(135deg, rgba(255,241,184,0.08) 0%, transparent 40%, transparent 60%, rgba(255,241,184,0.04) 100%)',
        pointerEvents: 'none',
      }} />
      <Icon size={32} color={face.color} style={{ filter: `drop-shadow(0 0 8px ${face.color})` }} />
      <span style={{
        fontSize: 12, fontWeight: 700, letterSpacing: '0.1em',
        textTransform: 'uppercase' as const,
        background: `linear-gradient(135deg, ${face.color}, #FFF1B8)`,
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
      }}>
        {face.label}
      </span>
    </div>
  );
}

function CubeFaceBlank({ transform }: { transform: string }) {
  return (
    <div style={{
      position: 'absolute', width: 160, height: 160,
      transform,
      backfaceVisibility: 'hidden' as const,
      WebkitBackfaceVisibility: 'hidden' as any,
      borderRadius: 20,
      background: 'linear-gradient(145deg, #1a1508, #0d0a04)',
      border: '1.5px solid rgba(212,168,67,0.15)',
      boxShadow: 'inset 0 0 20px rgba(212,168,67,0.04)',
    }}>
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 20,
        background: 'linear-gradient(135deg, rgba(255,241,184,0.05) 0%, transparent 50%)',
        pointerEvents: 'none',
      }} />
    </div>
  );
}

function GoldButton({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', gap: 8, padding: '14px 32px', borderRadius: 12,
      background: 'linear-gradient(135deg, #FFF1B8, #F0D78C, #D4A843, #8B6914)',
      color: '#0a0a0a', fontWeight: 700, fontSize: 14, border: 'none', cursor: 'pointer', letterSpacing: '0.02em',
      boxShadow: '0 4px 30px rgba(212,168,67,0.2), inset 0 1px 0 rgba(255,255,255,0.3)',
      transition: 'all 0.3s ease',
    }}
      onMouseOver={(e) => { e.currentTarget.style.boxShadow = '0 8px 50px rgba(212,168,67,0.35), inset 0 1px 0 rgba(255,255,255,0.3)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
      onMouseOut={(e) => { e.currentTarget.style.boxShadow = '0 4px 30px rgba(212,168,67,0.2), inset 0 1px 0 rgba(255,255,255,0.3)'; e.currentTarget.style.transform = 'translateY(0)'; }}
    >
      {children}
    </button>
  );
}
