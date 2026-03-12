import { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Download, RefreshCw, FileText, Film, Loader2, ChevronLeft, ChevronRight,
  ZoomIn, ZoomOut, Maximize2, Check, AlertCircle, Clock,
} from 'lucide-react';
import { TrailerPlayer } from '../video/TrailerPlayer';
import { useGenerationStore } from '../../stores/generationStore';
import type { OutputMode, PageData, StoryboardFrameData, VideoData, SceneBeat } from '../../types';

const T = {
  bg: '#0a0a0a', card: '#111111', gold: '#D4A843', goldLight: '#F0D78C',
  goldGrad: 'linear-gradient(135deg, #FFF1B8, #F0D78C, #D4A843, #8B6914)',
  silverLight: '#E8E8E8', dim: '#888', dimmer: '#555',
  border: 'rgba(212,168,67,0.1)',
};

// A4 base dimensions at 72 DPI
const PAGE_W = 595;
const PAGE_H = 842;

interface OutputViewerProps {
  mode: OutputMode;
  pages: PageData[];
  storyboardFrames: StoryboardFrameData[];
  video: VideoData | null;
  scenes: SceneBeat[];
  projectId: string;
  projectTitle?: string;
  isRegenerating: boolean;
  hasContent?: boolean;
  onGenerate?: () => void;
  onRegenerate: () => void;
  onRegenerateImage?: () => void;
  onSceneEdit: (sceneId: string, field: string, value: string) => void;
}

/* ═══ Inline Generation Progress ═══ */

function GenerationProgressBar({ mode }: { mode: OutputMode }) {
  const { isGenerating, overallProgress, currentPhase, scenes, sceneNames, clipsDone, clipsTotal } = useGenerationStore();
  const [dots, setDots] = useState('');

  useEffect(() => {
    if (!isGenerating) return;
    const iv = setInterval(() => setDots(d => d.length >= 3 ? '' : d + '.'), 500);
    return () => clearInterval(iv);
  }, [isGenerating]);

  if (!isGenerating) return null;

  const modeLabel = mode === 'manga' ? 'Manga' : mode === 'storyboard' ? 'Storyboard' : 'Comic';
  const completedScenes = scenes.filter(s => s.status === 'complete').length;
  const totalScenes = scenes.length;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      style={{
        padding: '16px 20px', borderRadius: 12,
        background: 'linear-gradient(135deg, rgba(212,168,67,0.06), rgba(212,168,67,0.02))',
        border: '1px solid rgba(212,168,67,0.15)',
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Loader2 size={14} color={T.gold} style={{ animation: 'spin 1s linear infinite' }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: T.goldLight }}>
            Generating {modeLabel}{dots}
          </span>
        </div>
        <span style={{ fontSize: 11, color: T.dim }}>
          {Math.round(overallProgress)}% · {completedScenes}/{totalScenes} scenes
          {mode === 'trailer' && clipsTotal > 0 && (
            <> · 🎬 {clipsDone}/{clipsTotal} clips</>
          )}
        </span>
      </div>

      {/* Overall progress bar */}
      <div style={{
        height: 6, borderRadius: 3,
        background: 'rgba(255,255,255,0.06)',
        overflow: 'hidden', marginBottom: 12,
      }}>
        <motion.div
          style={{
            height: '100%', borderRadius: 3,
            background: T.goldGrad,
          }}
          initial={{ width: 0 }}
          animate={{ width: `${overallProgress}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>

      {/* Phase label */}
      <div style={{ fontSize: 11, color: T.dim, marginBottom: 10 }}>
        {currentPhase}
      </div>

      {/* Per-scene chips */}
      {totalScenes > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {scenes.map((scene, i) => {
            const isComplete = scene.status === 'complete';
            const isActive = scene.status === 'generating';
            const isError = scene.status === 'error';
            return (
              <div key={scene.scene_id} style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '4px 10px', borderRadius: 6,
                background: isComplete
                  ? 'rgba(34,197,94,0.1)'
                  : isActive
                    ? 'rgba(212,168,67,0.1)'
                    : isError
                      ? 'rgba(239,68,68,0.1)'
                      : 'rgba(255,255,255,0.03)',
                border: `1px solid ${
                  isComplete ? 'rgba(34,197,94,0.2)'
                  : isActive ? 'rgba(212,168,67,0.2)'
                  : isError ? 'rgba(239,68,68,0.2)'
                  : 'rgba(255,255,255,0.05)'
                }`,
              }}>
                {isComplete ? (
                  <Check size={10} color="#22c55e" />
                ) : isActive ? (
                  <Loader2 size={10} color={T.gold} style={{ animation: 'spin 1s linear infinite' }} />
                ) : isError ? (
                  <AlertCircle size={10} color="#ef4444" />
                ) : (
                  <Clock size={10} color="#555" />
                )}
                <span style={{
                  fontSize: 10, fontWeight: 500,
                  color: isComplete ? '#22c55e' : isActive ? T.goldLight : isError ? '#ef4444' : '#666',
                }}>
                  Scene {i + 1}
                </span>
                {isActive && scene.progress > 0 && (
                  <span style={{ fontSize: 9, color: T.dim }}>{scene.progress}%</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </motion.div>
  );
}

/* ═══ PDF-style Page Viewer ═══ */

function PDFViewer({ pages, storyboardFrames, mode, hasContent, isRegenerating, onRegenerateImage, onGenerate, scenes, projectTitle }: {
  pages: PageData[];
  storyboardFrames: StoryboardFrameData[];
  mode: OutputMode;
  hasContent?: boolean;
  isRegenerating?: boolean;
  onRegenerateImage?: () => void;
  onGenerate?: () => void;
  scenes?: SceneBeat[];
  projectTitle?: string;
}) {
  const [currentPage, setCurrentPage] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [fitToWindow, setFitToWindow] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  const totalPages = mode === 'storyboard'
    ? Math.max(1, Math.ceil(storyboardFrames.length / 4))
    : pages.length;

  const hasContentLocal = hasContent ?? (mode === 'storyboard' ? storyboardFrames.length > 0 : pages.length > 0);

  // Calculate zoom that fits the A4 page inside the container
  const calculateFitZoom = useCallback(() => {
    if (!containerRef.current) return 0.75;
    const cw = containerRef.current.clientWidth - 64;
    const ch = containerRef.current.clientHeight - 64;
    return Math.min(cw / PAGE_W, ch / PAGE_H, 2);
  }, []);

  // Recalc on mount, resize, content change
  useEffect(() => {
    if (!fitToWindow) return;
    const update = () => setZoom(calculateFitZoom());
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [fitToWindow, calculateFitZoom, hasContentLocal]);

  const handleZoomChange = (v: number) => { setZoom(v); setFitToWindow(false); };
  const handleFitToWindow = () => {
    if (fitToWindow) { setFitToWindow(false); setZoom(1); }
    else { setFitToWindow(true); setZoom(calculateFitZoom()); }
  };

  /* ── Download / Print ── */
  const handleDownload = useCallback(async () => {
    if (pages.length === 0) return;
    const pw = window.open('', '_blank');
    if (!pw) return;

    pw.document.write(`<!DOCTYPE html><html><head>
      <title>${projectTitle || 'StoryForge Pro'} — ${mode}</title>
      <style>
        @page { margin:0; size:A4 portrait; }
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#fff}
        .page{width:210mm;height:297mm;display:flex;flex-direction:column;padding:4mm;page-break-after:always;overflow:hidden}
        .page:last-child{page-break-after:auto}
        .grid{flex:1;display:grid;grid-template-columns:repeat(2,1fr);grid-template-rows:repeat(3,1fr);gap:2mm}
        .panel{overflow:hidden;border:1.5px solid #222;border-radius:3px;background:#f0f0f0}
        .panel img{width:100%;height:100%;object-fit:cover;display:block}
        .foot{text-align:center;font:8px/1 sans-serif;color:#999;padding:2mm 0 1mm}
        @media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
      </style></head><body>`);

    for (const pg of pages) {
      pw.document.write('<div class="page"><div class="grid">');
      for (const panel of pg.panels) {
        pw.document.write('<div class="panel">');
        if (panel.image_url) pw.document.write(`<img src="${panel.image_url}"/>`);
        pw.document.write('</div>');
      }
      pw.document.write(`</div><div class="foot">Page ${pg.page_number} · StoryForge Pro</div></div>`);
    }

    pw.document.write('</body></html>');
    pw.document.close();
    pw.onload = () => setTimeout(() => pw.print(), 800);
  }, [pages, mode]);

  /* ── Empty state ── */
  if (!hasContentLocal) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <AnimatePresence>
          <GenerationProgressBar mode={mode} />
        </AnimatePresence>
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '70vh', borderRadius: 16, background: '#0d0d0d',
          border: `1px solid ${T.border}`,
        }}>
          <FileText size={48} color={T.dimmer} style={{ marginBottom: 12 }} />
          <p style={{ color: T.dim, fontSize: 14 }}>Output will appear here after generation</p>
          <p style={{ color: T.dimmer, fontSize: 11, marginTop: 4 }}>Your {mode} pages will be rendered as a viewable PDF</p>
        </div>
      </div>
    );
  }

  const page = pages[currentPage];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 16px', borderRadius: 10,
        background: T.card, border: `1px solid ${T.border}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText size={14} color={T.gold} />
          <span style={{ fontSize: 12, fontWeight: 600, color: T.silverLight }}>
            {mode === 'storyboard' ? 'Storyboard' : mode === 'manga' ? 'Manga' : 'Comic'} — Page {currentPage + 1} of {totalPages}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          
          <button onClick={() => handleZoomChange(Math.max(0.3, zoom - 0.1))} style={toolbarBtnStyle}>
            <ZoomOut size={14} />
          </button>
          <span style={{ fontSize: 10, color: T.dim, minWidth: 36, textAlign: 'center' }}>{Math.round(zoom * 100)}%</span>
          <button onClick={() => handleZoomChange(Math.min(2, zoom + 0.1))} style={toolbarBtnStyle}>
            <ZoomIn size={14} />
          </button>
          <button
            onClick={handleFitToWindow}
            style={{
              ...toolbarBtnStyle,
              background: fitToWindow ? 'rgba(212,168,67,0.15)' : 'transparent',
              color: fitToWindow ? T.gold : T.silverLight,
            }}
            title={fitToWindow ? 'Manual zoom' : 'Fit to window'}
          >
            <Maximize2 size={14} />
          </button>
          <div style={{ width: 1, height: 16, background: T.border, margin: '0 4px' }} />
          <button onClick={handleDownload} style={toolbarBtnStyle} title="Download PDF">
            <Download size={14} />
          </button>
        </div>
      </div>

      {/* Generation progress */}
      <AnimatePresence>
        <GenerationProgressBar mode={mode} />
      </AnimatePresence>

      {/* Page viewer container */}
      <div
        ref={containerRef}
        style={{
          position: 'relative', borderRadius: 14, overflow: 'hidden',
          background: '#080808', border: `1px solid ${T.border}`,
          height: '78vh',
        }}
      >
        {/* Scrollable canvas */}
        <div style={{
          display: 'flex', justifyContent: 'center', alignItems: 'flex-start',
          padding: 32,
          background: 'linear-gradient(180deg, #0a0a0a, #111)',
          height: '100%', overflow: 'auto',
        }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={currentPage}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
              style={{
                /* Outer wrapper sets the LAYOUT size (how much space the page takes up) */
                width: PAGE_W * zoom,
                height: PAGE_H * zoom,
                flexShrink: 0,
              }}
            >
              {/* Inner page: always 595×842, scaled via transform */}
              <div style={{
                width: PAGE_W,
                height: PAGE_H,
                transform: `scale(${zoom})`,
                transformOrigin: 'top left',
                background: '#fff',
                borderRadius: 4,
                boxShadow: '0 8px 40px rgba(0,0,0,0.6), 0 2px 10px rgba(0,0,0,0.4)',
                overflow: 'hidden',
              }}>
                {mode === 'storyboard' ? (
                  <StoryboardPage
                    frames={storyboardFrames.slice(currentPage * 4, (currentPage + 1) * 4)}
                    startIndex={currentPage * 4}
                  />
                ) : (
                  <ComicPage page={page} mode={mode} />
                )}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Nav arrows */}
        {currentPage > 0 && (
          <button onClick={() => setCurrentPage(p => p - 1)} style={{ ...navArrowStyle, left: 12 }}>
            <ChevronLeft size={24} />
          </button>
        )}
        {currentPage < totalPages - 1 && (
          <button onClick={() => setCurrentPage(p => p + 1)} style={{ ...navArrowStyle, right: 12 }}>
            <ChevronRight size={24} />
          </button>
        )}
      </div>

      {/* Page dots */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 6, alignItems: 'center' }}>
          {Array.from({ length: totalPages }).map((_, i) => (
            <button key={i} onClick={() => setCurrentPage(i)} style={{
              width: i === currentPage ? 24 : 8, height: 8, borderRadius: 4,
              background: i === currentPage ? T.gold : 'rgba(255,255,255,0.15)',
              border: 'none', cursor: 'pointer', transition: 'all 0.3s',
            }} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ═══ Comic / Manga Page ═══ */

function ComicPage({ page, mode }: { page: PageData; mode: OutputMode }) {
  if (!page) {
    return (
      <div style={{
        width: PAGE_W, height: PAGE_H,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#999', fontSize: 14,
      }}>
        Page content generating...
      </div>
    );
  }

  const isManga = mode === 'manga';
  const panelCount = page.panels.length;

  // Determine grid layout based on panel count
  // 1 panel  → 1×1  (full page cover)
  // 2 panels → 1×2
  // 3 panels → mixed (1 wide + 2 small)
  // 4 panels → 2×2
  // 5 panels → 2col, mixed rows
  // 6 panels → 2×3
  const cols = panelCount <= 1 ? 1 : 2;
  const rows = panelCount <= 1 ? 1 : panelCount <= 2 ? 1 : panelCount <= 4 ? 2 : 3;

  return (
    <div style={{
      width: PAGE_W,
      height: PAGE_H,
      padding: 12,
      background: isManga ? '#f5f5f5' : '#fff',
      display: 'flex',
      flexDirection: 'column',
      boxSizing: 'border-box',
    }}>
      {panelCount === 0 ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>
          Panels generating...
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gridTemplateRows: `repeat(${rows}, 1fr)`,
          gap: 6,
          width: PAGE_W - 24,   /* minus padding */
          height: PAGE_H - 48,  /* minus padding + footer */
        }}>
          {page.panels.map((panel, idx) => (
            <div key={panel.id} style={{
              background: isManga ? '#e8e8e8' : '#f0f0f0',
              borderRadius: 4,
              border: `2px solid ${isManga ? '#333' : '#222'}`,
              overflow: 'hidden',
              gridColumn: panel.span?.cols > 1 ? 'span 2' : 'auto',
              gridRow: panel.span?.rows > 1 ? `span ${panel.span.rows}` : 'auto',
            }}>
              {panel.image_url ? (
                <img
                  src={panel.image_url}
                  alt={`Panel ${idx + 1}`}
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                    display: 'block',
                  }}
                />
              ) : (
                <div style={{
                  width: '100%', height: '100%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: isManga
                    ? 'repeating-conic-gradient(#ddd 0% 25%, #e8e8e8 0% 50%) 50% / 8px 8px'
                    : '#f0f0f0',
                }}>
                  <span style={{ fontSize: 11, color: '#999' }}>Panel {idx + 1}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <div style={{
        textAlign: 'center', fontSize: 9, color: '#bbb',
        height: 24, lineHeight: '24px', flexShrink: 0,
      }}>
        Page {(page.page_number || 0) + 1} · {isManga ? '漫画' : 'StoryForge Pro'}
      </div>
    </div>
  );
}

/* ═══ Storyboard Page ═══ */

function StoryboardPage({ frames, startIndex }: { frames: StoryboardFrameData[]; startIndex: number }) {
  return (
    <div style={{
      width: PAGE_W, height: PAGE_H, padding: 20,
      background: '#fafafa',
      display: 'flex', flexDirection: 'column', boxSizing: 'border-box',
    }}>
      <div style={{
        fontSize: 11, fontWeight: 700, color: '#666', textTransform: 'uppercase',
        letterSpacing: '0.1em', marginBottom: 16, paddingBottom: 8,
        borderBottom: '2px solid #333', flexShrink: 0,
      }}>
        Storyboard — Frames {startIndex + 1}–{startIndex + frames.length}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20, flex: 1, overflow: 'hidden' }}>
        {frames.map((frame, i) => (
          <div key={frame.id} style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0 }}>
            <div style={{
              width: 240, borderRadius: 6, overflow: 'hidden',
              background: '#e8e8e8', border: '2px solid #444', flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {frame.image_url ? (
                <img src={frame.image_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
              ) : (
                <span style={{ fontSize: 11, color: '#999' }}>Frame {startIndex + i + 1}</span>
              )}
            </div>
            <div style={{ flex: 1, fontSize: 11, color: '#444', display: 'flex', flexDirection: 'column' }}>
              <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 6 }}>
                #{frame.frame_number} · {frame.shot_type} · {frame.camera_move}
              </div>
              {frame.dialogue && <div style={{ fontStyle: 'italic', marginBottom: 6, lineHeight: 1.4 }}>"{frame.dialogue}"</div>}
              {frame.director_notes && <div style={{ color: '#777', marginBottom: 6, lineHeight: 1.4 }}>{frame.director_notes}</div>}
              <div style={{ marginTop: 'auto', color: '#999', fontSize: 10 }}>
                {frame.duration_seconds}s · → {frame.transition}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══ Main OutputViewer ═══ */

export function OutputViewer({
  mode, pages, storyboardFrames, video, scenes, projectId, projectTitle,
  isRegenerating, hasContent, onGenerate, onRegenerate, onRegenerateImage, onSceneEdit,
}: OutputViewerProps) {
  const safeTitle = (projectTitle || 'storyforge').replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
  const modeLabel = mode === 'trailer' ? 'Trailer' : mode === 'manga' ? 'Manga' : mode === 'storyboard' ? 'Storyboard' : 'Comic';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Output Header */}
      <div>
        <h2 style={{
          fontSize: 22, fontWeight: 700, marginBottom: 4,
          background: 'linear-gradient(135deg, #FFFFFF, #E8E8E8, #C0C0C0)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
        }}>
          Your {modeLabel}
        </h2>
        <p style={{ fontSize: 13, color: T.dim }}>
          {scenes.length === 0
            ? 'Generate your story first in the Scenes tab, then return here to generate visuals'
            : hasContent
              ? `Your ${modeLabel.toLowerCase()} is ready! Edit scenes in the Scenes tab if needed.`
              : 'Your scenes are ready. Generate visuals below.'}
        </p>
      </div>

      {/* Generate / Regenerate action bar */}
      {scenes.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 20px', borderRadius: 12,
          background: 'linear-gradient(135deg, rgba(212,168,67,0.06), rgba(212,168,67,0.02))',
          border: '1px solid rgba(212,168,67,0.15)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {mode === 'trailer' ? <Film size={16} color={T.gold} /> : <FileText size={16} color={T.gold} />}
            <span style={{ fontSize: 13, color: T.silverLight }}>
              {hasContent
                ? `${modeLabel} generated — regenerate to update`
                : `Ready to generate your ${modeLabel.toLowerCase()}`}
            </span>
          </div>
          <button
            onClick={hasContent ? (onRegenerateImage ?? onRegenerate) : (onGenerate ?? onRegenerate)}
            disabled={isRegenerating || scenes.length === 0}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 20px', borderRadius: 8,
              background: isRegenerating ? T.card : T.goldGrad,
              border: 'none',
              cursor: isRegenerating ? 'default' : 'pointer',
              color: isRegenerating ? T.dim : T.bg,
              fontSize: 13, fontWeight: 700,
              boxShadow: isRegenerating ? 'none' : '0 4px 16px rgba(212,168,67,0.25)',
              transition: 'all 0.3s',
              opacity: isRegenerating ? 0.7 : 1,
            }}
          >
            {isRegenerating ? (
              <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Generating...</>
            ) : hasContent ? (
              <><RefreshCw size={16} /> Regenerate {mode === 'trailer' ? 'Trailer' : 'Images'}</>
            ) : (
              <>✨ Generate {modeLabel}</>
            )}
          </button>
          {mode === 'trailer' && (
            <a
              href={video?.video_url || '#'}
              download={video?.video_url ? `${safeTitle}-trailer.mp4` : undefined}
              onClick={e => { if (!video?.video_url) e.preventDefault(); }}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '10px 20px', borderRadius: 8,
                background: video?.video_url ? T.goldGrad : T.card,
                border: 'none',
                color: video?.video_url ? T.bg : T.dim,
                textDecoration: 'none',
                fontSize: 13, fontWeight: 700,
                boxShadow: video?.video_url ? '0 4px 16px rgba(212,168,67,0.25)' : 'none',
                cursor: video?.video_url ? 'pointer' : 'not-allowed',
                opacity: video?.video_url ? 1 : 0.7,
                transition: 'all 0.3s',
              }}
            >
              <Download size={16} /> Download Trailer
            </a>
          )}
        </div>
      )}

      {/* Generated Content Section */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
        <div style={{ flex: 1, height: 1, background: T.border }} />
        <span style={{ fontSize: 12, color: T.goldLight, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>🎨 Generated Content</span>
        <div style={{ flex: 1, height: 1, background: T.border }} />
      </div>

      {/* Primary Output — PDF or Video */}
      {mode === 'trailer' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <AnimatePresence>
            <GenerationProgressBar mode={mode} />
          </AnimatePresence>
          {video ? (
            <TrailerPlayer video={video} projectTitle={safeTitle} />
          ) : hasContent ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              height: '70vh', borderRadius: 16, background: '#0d0d0d', border: `1px solid ${T.border}`,
            }}>
              <Film size={48} color={T.dimmer} style={{ marginBottom: 12 }} />
              <p style={{ color: T.dim, fontSize: 14 }}>Regenerate to create your trailer video</p>
            </div>
          ) : (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              height: '70vh', borderRadius: 16, background: '#0d0d0d', border: `1px solid ${T.border}`,
            }}>
              <Film size={48} color={T.dimmer} style={{ marginBottom: 12 }} />
              <p style={{ color: T.dim, fontSize: 14 }}>Trailer will appear here after generation</p>
            </div>
          )}
        </div>
      ) : (
        <PDFViewer
          pages={pages}
          storyboardFrames={storyboardFrames}
          mode={mode}
          hasContent={hasContent}
          isRegenerating={isRegenerating}
          onRegenerateImage={onRegenerateImage}
          onGenerate={onGenerate}
          scenes={scenes}
          projectTitle={projectTitle}
        />
      )}
    </div>
  );
}

/* ═══ Shared Styles ═══ */

const toolbarBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: 28, height: 28, borderRadius: 6,
  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)',
  cursor: 'pointer', color: '#999', transition: 'all 0.2s',
};

const navArrowStyle: React.CSSProperties = {
  position: 'absolute', top: '50%', transform: 'translateY(-50%)',
  width: 40, height: 40, borderRadius: '50%', display: 'flex',
  alignItems: 'center', justifyContent: 'center',
  background: 'rgba(0,0,0,0.7)', border: '1px solid rgba(255,255,255,0.1)',
  color: 'rgba(255,255,255,0.7)', cursor: 'pointer', zIndex: 5,
  transition: 'all 0.2s',
};
