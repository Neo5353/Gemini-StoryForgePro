import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Loader2, PenTool, Palette, Play, FileText } from 'lucide-react';
import { useProjectStore } from '../stores/projectStore';
import { useGenerationStore } from '../stores/generationStore';
import { ScriptEditor } from '../components/script/ScriptEditor';
import { DirectorPicker } from '../components/common/DirectorPicker';
import { ModePicker } from '../components/common/ModePicker';
import { ComicStylePicker } from '../components/common/ComicStylePicker';
import { MangaStylePicker } from '../components/common/MangaStylePicker';
import { StoryboardStylePicker } from '../components/common/StoryboardStylePicker';
import { SceneEditor } from '../components/scenes/SceneEditor';
import { OutputViewer } from '../components/output/OutputViewer';
import { GeneratingOverlay } from '../components/common/GeneratingOverlay';
import { getSocket, cleanupSocket } from '../services/websocket';
import { createProject, analyzeScript, generatePanels, generateStoryboard, generateTrailer, fetchProject, patchProject } from '../services/api';

/* ═══ THEME ═══ */
const T = {
  bg: '#0a0a0a',
  card: '#111111',
  cardLight: '#161616',
  gold: '#D4A843',
  goldLight: '#F0D78C',
  goldBright: '#FFF1B8',
  goldDark: '#8B6914',
  silver: '#C0C0C0',
  silverLight: '#E8E8E8',
  dim: '#888',
  dimmer: '#555',
  border: 'rgba(212,168,67,0.1)',
  goldGrad: 'linear-gradient(135deg, #FFF1B8, #F0D78C, #D4A843, #8B6914)',
};

type Step = 'script' | 'style' | 'scenes' | 'output';

const STEPS: { id: Step; label: string; icon: typeof PenTool; hint: string }[] = [
  { id: 'script', label: 'Script', icon: PenTool, hint: 'Write or paste' },
  { id: 'style', label: 'Style', icon: Palette, hint: 'Director & format' },
  { id: 'scenes', label: 'Scenes', icon: FileText, hint: 'Edit story beats' },
  { id: 'output', label: 'Output', icon: Play, hint: 'View & refine' },
];

export function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const rawStep = searchParams.get('step');
  const initialStep = (rawStep === 'generate' ? 'output' : (rawStep || 'script')) as Step;
  const [step, setStep] = useState<Step>(initialStep as Step);
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastGenerationTime, setLastGenerationTime] = useState<{ action: string; seconds: number } | null>(null);
  const [congestionPopup, setCongestionPopup] = useState(false);
  const isNew = projectId === 'new';

  const {
    project, draftScript, draftTitle, selectedDirectorId, selectedStyleId, selectedMode,
    setProject, setLoading, setError, isLoading, error,
  } = useProjectStore();

  // Reset store when switching projects to prevent cross-contamination
  useEffect(() => {
    return () => { useProjectStore.getState().reset(); };
  }, [projectId]);

  // Load existing project
  useEffect(() => {
    if (isNew || !projectId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const proj = await fetchProject(projectId!);
        if (!cancelled) {
          setProject(proj);
          
          // Sync loaded project data into draft fields
          const store = useProjectStore.getState();
          if (proj.title) store.setDraftTitle(proj.title);
          if (proj.script?.raw_text) store.setDraftScript(proj.script.raw_text);
          if (proj.output_mode) store.setSelectedMode(proj.output_mode as any);
          
          if (proj.director_style_id) {
            const directorIds = ['nolan', 'cameron', 'ritchie', 'maniratnam', 'nelson'];
            if (directorIds.includes(proj.director_style_id)) {
              store.setSelectedDirector(proj.director_style_id);
            } else {
              store.setSelectedStyle(proj.director_style_id);
            }
          }
          // Determine starting step based on project state
          if (!rawStep) {
            if (proj.pages?.length > 0 || proj.video) {
              setStep('output');
            } else if (proj.script?.scenes && proj.script.scenes.length > 0) {
              setStep('scenes'); // Go to scenes if script is analyzed but no content generated
            } else if (proj.director_style_id) {
              setStep('scenes'); // Go to scenes after style is chosen
            }
          }
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load project');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [projectId]);

  const stepIndex = STEPS.findIndex((s) => s.id === step);
  const canNext = (() => {
    switch (step) {
      case 'script': return draftScript.trim().length > 20;
      case 'style': return selectedMode === 'trailer' ? !!selectedDirectorId : !!selectedStyleId;
      case 'scenes': return project && project.script?.scenes && project.script.scenes.length > 0;
      case 'output': return false;
    }
  })();

  const hasContent = project && (
    (project.pages?.length > 0 && project.pages.some(p => p.panels?.length > 0)) ||
    project.storyboard_frames?.length > 0 ||
    project.video
  );

  // Wire WebSocket progress into generation store
  const connectProgress = useCallback((projectId: string) => {
    const projectScenes = project?.script?.scenes || [];
    const sceneIds = projectScenes.map((s: any) => s.id);
    const sceneNames: Record<string, string> = {};
    projectScenes.forEach((s: any) => {
      sceneNames[s.id] = s.title || s.location || `Scene ${s.scene_number || '?'}`;
    });
    useGenerationStore.getState().startGeneration(sceneIds, sceneNames);

    // WebSocket is best-effort — don't let failures block generation
    try {
      const socket = getSocket(projectId);
      socket.connect();
      const unsub = socket.subscribe((msg) => {
        if (msg.type === 'progress') {
          const store = useGenerationStore.getState();
          store.updateOverall(msg.overall_progress_pct ?? 0, msg.message ?? '');
          // Update clips progress for trailer mode
          if ((msg as any).clips_done !== undefined) {
            store.updateClips((msg as any).clips_done, (msg as any).clips_total ?? 0);
          }
          // Update per-scene progress
          if (msg.scenes) {
            Object.entries(msg.scenes).forEach(([sid, sp]: [string, any]) => {
              const status = sp.phase === 'complete' ? 'complete'
                : sp.phase === 'failed' ? 'error'
                : sp.progress_pct > 0 ? 'generating' : 'queued';
              store.updateSceneProgress(sid, sp.progress_pct ?? 0, status as any);
              if (sp.phase === 'complete' && sp.thumbnail_url) {
                store.setSceneComplete(sid, sp.thumbnail_url);
              }
              if (sp.phase === 'failed' && sp.error) {
                store.setError(sid, sp.error);
              }
            });
          }
          if (msg.phase === 'complete') store.completeGeneration();
        }
      });
      return () => { unsub(); cleanupSocket(projectId); };
    } catch (e) {
      console.warn('[StoryForge] WebSocket setup failed, progress updates unavailable:', e);
      return () => {};
    }
  }, [project]);

  // Generate / Regenerate logic
  const runGeneration = useCallback(async () => {
    if (!project) return;
    setIsGenerating(true);
    setError(null);
    const disconnect = connectProgress(project.id);
    const t0 = performance.now();
    try {
      if (selectedMode === 'comic' || selectedMode === 'manga') {
        const pages = await generatePanels(project.id);
        useProjectStore.getState().updatePages(pages);
      } else if (selectedMode === 'storyboard') {
        const frames = await generateStoryboard(project.id);
        useProjectStore.getState().updateStoryboardFrames(frames);
      } else {
        const video = await generateTrailer(project.id);
        useProjectStore.getState().updateVideo(video);
      }
      const secs = Math.round((performance.now() - t0) / 100) / 10;
      setLastGenerationTime({ action: `generate_${selectedMode}`, seconds: secs });
      console.log(`[StoryForge] generate_${selectedMode}: ${secs}s`);
    } catch (e: any) {
      if (e?.status === 429) {
        setCongestionPopup(true);
        setError(null);
      } else {
        setError(e instanceof Error ? e.message : 'Generation failed');
      }
    } finally {
      setIsGenerating(false);
      useGenerationStore.getState().completeGeneration();
      disconnect();
    }
  }, [project, selectedMode, setError, connectProgress]);

  // Regenerate Story - Parse script and update scenes
  const regenerateStory = useCallback(async () => {
    if (!project) return;
    setIsGenerating(true);
    setError(null);
    const t0 = performance.now();
    try {
      // First, save the current draft script content to the project
      await patchProject(project.id, { script: draftScript });
      
      // Then analyze the updated script to regenerate scenes
      const analyzed = await analyzeScript(project.id);
      setProject(analyzed);
      const secs = Math.round((performance.now() - t0) / 100) / 10;
      setLastGenerationTime({ action: 'generate_story', seconds: secs });
      console.log(`[StoryForge] generate_story: ${secs}s`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Story regeneration failed');
    } finally {
      setIsGenerating(false);
    }
  }, [project, draftScript, setError]);

  // Regenerate Images - Keep story, regenerate visuals
  const regenerateImages = useCallback(async () => {
    if (!project) return;
    setIsGenerating(true);
    setError(null);
    const disconnect = connectProgress(project.id);
    const t0 = performance.now();
    try {
      if (selectedMode === 'comic' || selectedMode === 'manga') {
        const pages = await generatePanels(project.id);
        useProjectStore.getState().updatePages(pages);
      } else if (selectedMode === 'storyboard') {
        const frames = await generateStoryboard(project.id);
        useProjectStore.getState().updateStoryboardFrames(frames);
      } else {
        const video = await generateTrailer(project.id);
        useProjectStore.getState().updateVideo(video);
      }
      const secs = Math.round((performance.now() - t0) / 100) / 10;
      setLastGenerationTime({ action: `regenerate_${selectedMode}`, seconds: secs });
      console.log(`[StoryForge] regenerate_${selectedMode}: ${secs}s`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Image regeneration failed');
    } finally {
      setIsGenerating(false);
      useGenerationStore.getState().completeGeneration();
      disconnect();
    }
  }, [project, selectedMode, setError, connectProgress]);

  const handleNext = async () => {
    if (step === 'style') {
      if (isNew) {
        // Create project, analyze script, then go to scenes
        setLoading(true);
        try {
          const styleParam = selectedMode === 'trailer' ? selectedDirectorId! : selectedStyleId!;
          const proj = await createProject({
            title: draftTitle || 'Untitled Story',
            script: draftScript,
            director_style: styleParam,
            output_mode: selectedMode,
          });
          setProject(proj);
          navigate(`/project/${proj.id}`, { replace: true });
          setStep('scenes');
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Failed to create project');
        } finally {
          setLoading(false);
        }
      } else {
        setStep('scenes');
      }
      return;
    }
    const nextIdx = stepIndex + 1;
    if (nextIdx < STEPS.length) setStep(STEPS[nextIdx].id);
  };

  const handleBack = () => {
    const prevIdx = stepIndex - 1;
    if (prevIdx >= 0) setStep(STEPS[prevIdx].id);
    else navigate('/projects');
  };

  return (
    <div style={{ background: T.bg, minHeight: 'calc(100vh - 56px)', position: 'relative' }}>

      {/* Generating overlay */}
      {isGenerating && <GeneratingOverlay mode={selectedMode} />}

      {/* ──── NAV BAR + TABS ──── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 0,
        maxWidth: 960, margin: '0 auto', padding: '12px 20px 0',
      }}>
        <button onClick={handleBack} style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 8,
          background: 'none', border: 'none', cursor: 'pointer',
          color: T.dim, fontSize: 13, fontWeight: 500, transition: 'color 0.2s',
          marginRight: 8, flexShrink: 0,
        }}
          onMouseOver={(e) => e.currentTarget.style.color = T.silverLight}
          onMouseOut={(e) => e.currentTarget.style.color = T.dim}
        >
          <ArrowLeft size={16} />
        </button>

        <div style={{ display: 'flex', gap: 2, flex: 1 }}>
          {STEPS.map((s, i) => {
            const Icon = s.icon;
            const isActive = s.id === step;
            const isPast = i < stepIndex;
            const isFuture = i > stepIndex;
            return (
              <button
                key={s.id}
                onClick={() => (isPast || isActive) && setStep(s.id)}
                style={{
                  flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  padding: '10px 8px', borderRadius: '10px 10px 0 0',
                  background: isActive ? T.card : 'transparent',
                  border: 'none',
                  borderBottom: isActive ? `2px solid ${T.gold}` : '2px solid transparent',
                  cursor: isFuture ? 'default' : 'pointer',
                  transition: 'all 0.3s ease',
                  opacity: isFuture ? 0.35 : 1,
                }}
              >
                <Icon size={14} color={isActive ? T.goldLight : isPast ? T.gold : T.dimmer} />
                <span style={{
                  fontSize: 12, fontWeight: isActive ? 700 : 500, letterSpacing: '0.02em',
                  color: isActive ? T.goldLight : isPast ? T.silver : T.dimmer,
                }}>
                  {s.label}
                </span>
                {isActive && (
                  <span style={{ fontSize: 9, color: T.dim, marginLeft: 2 }}>{s.hint}</span>
                )}
              </button>
            );
          })}
        </div>

        {step !== 'output' ? (
          <button onClick={handleNext} disabled={!canNext || isLoading} style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8,
            background: canNext && !isLoading ? T.goldGrad : T.cardLight,
            border: 'none', cursor: canNext && !isLoading ? 'pointer' : 'default',
            color: canNext && !isLoading ? T.bg : T.dimmer,
            fontSize: 12, fontWeight: 700, marginLeft: 8, flexShrink: 0,
            boxShadow: canNext && !isLoading ? '0 2px 16px rgba(212,168,67,0.15)' : 'none',
            transition: 'all 0.3s ease', opacity: canNext ? 1 : 0.4,
          }}>
            {isLoading ? (
              <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Working...</>
            ) : (
              <><span>Next</span> <ArrowRight size={14} /></>
            )}
          </button>
        ) : <div style={{ width: 80 }} />}
      </div>

      <div style={{ maxWidth: 960, margin: '0 auto', padding: '0 20px' }}>
        <div style={{ height: 1, background: T.border }} />
      </div>

      {/* ──── ERROR ──── */}
      {error && (
        <div style={{ maxWidth: 960, margin: '12px auto 0', padding: '0 20px' }}>
          <div style={{
            padding: '12px 16px', borderRadius: 10,
            background: 'rgba(180,40,40,0.1)', border: '1px solid rgba(180,40,40,0.2)',
            color: '#e88', fontSize: 13,
          }}>
            {error}
          </div>
        </div>
      )}

      {/* ──── STEP CONTENT ──── */}
      <div style={{ maxWidth: 960, margin: '0 auto', padding: '28px 20px 40px' }}>

        {step === 'script' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <SectionHeader title="Your Script" sub="Paste a screenplay, story, or outline" />
            <input
              value={draftTitle}
              onChange={(e) => useProjectStore.getState().setDraftTitle(e.target.value)}
              placeholder="Story title..."
              style={{
                width: '100%', padding: '12px 16px', borderRadius: 10,
                background: T.card, border: `1px solid ${T.border}`,
                color: T.silverLight, fontSize: 16, fontWeight: 600,
                outline: 'none', transition: 'border-color 0.3s',
              }}
              onFocus={(e) => e.currentTarget.style.borderColor = T.gold}
              onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(212,168,67,0.1)'}
            />
            <ScriptEditor />
          </div>
        )}

        {step === 'style' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
            <SectionHeader title="Visual Style" sub="Choose your output format, then pick a style" />
            <ModePicker />
            {selectedMode === 'comic' && <ComicStylePicker />}
            {selectedMode === 'manga' && <MangaStylePicker />}
            {selectedMode === 'storyboard' && <StoryboardStylePicker />}
            {selectedMode === 'trailer' && <DirectorPicker />}
          </div>
        )}

        {step === 'scenes' && project && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <SectionHeader title="Story Scenes" sub="Review and edit the scenes generated from your script" />
            <SceneEditor
              scenes={project.script?.scenes || []}
              onSceneEdit={(sceneId, field, value) => {
                useProjectStore.getState().updateScene(sceneId, field, value);
              }}
              onRegenerateStory={regenerateStory}
              isRegenerating={isGenerating}
            />
          </div>
        )}

        {step === 'output' && project && (
          <OutputViewer
            mode={selectedMode}
            pages={project.pages}
            storyboardFrames={project.storyboard_frames}
            video={project.video}
            scenes={project.script.scenes}
            projectId={project.id}
            projectTitle={project.title}
            isRegenerating={isGenerating}
            hasContent={!!hasContent}
            onGenerate={runGeneration}
            onRegenerate={runGeneration}
            onRegenerateImage={regenerateImages}
            onSceneEdit={(sceneId, field, value) => {
              useProjectStore.getState().updateScene(sceneId, field, value);
            }}
          />
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* ──── GCP CONGESTION POPUP ──── */}
      {congestionPopup && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
          onClick={() => setCongestionPopup(false)}
        >
          <div
            style={{
              background: '#1a1a1a', border: '1px solid rgba(255,180,0,0.3)',
              borderRadius: 16, padding: '32px 36px', maxWidth: 440, textAlign: 'center',
              boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ fontSize: 48, marginBottom: 16 }}>⏳</div>
            <h3 style={{
              fontSize: 20, fontWeight: 700, marginBottom: 12,
              color: '#FFB400',
            }}>
              GCP is Congested
            </h3>
            <p style={{ fontSize: 14, color: '#aaa', lineHeight: 1.6, marginBottom: 24 }}>
              Google Cloud's AI servers are busy right now. This is temporary — please wait about <strong style={{ color: '#fff' }}>5 minutes</strong> and try again.
            </p>
            <button
              onClick={() => setCongestionPopup(false)}
              style={{
                background: 'linear-gradient(135deg, #FFB400, #FF8C00)',
                color: '#000', border: 'none', borderRadius: 10,
                padding: '10px 32px', fontSize: 14, fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function SectionHeader({ title, sub }: { title: string; sub: string }) {
  return (
    <div>
      <h2 style={{
        fontSize: 22, fontWeight: 700, marginBottom: 4,
        background: 'linear-gradient(135deg, #FFFFFF, #E8E8E8, #C0C0C0)',
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
      }}>{title}</h2>
      <p style={{ fontSize: 13, color: '#888' }}>{sub}</p>
    </div>
  );
}
