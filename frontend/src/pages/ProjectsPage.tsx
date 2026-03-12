import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Plus, Trash2, Clock, CheckCircle, AlertCircle, Loader2, Film,
  BookOpen, Grid3X3, Clapperboard, PenTool, Palette,
} from 'lucide-react';
import { listProjects, deleteProject } from '../services/api';
import type { Project, OutputMode } from '../types';

const T = {
  bg: '#0a0a0a', card: '#111111', gold: '#D4A843', goldLight: '#F0D78C',
  goldGrad: 'linear-gradient(135deg, #FFF1B8, #F0D78C, #D4A843, #8B6914)',
  silverLight: '#E8E8E8', dim: '#888', dimmer: '#555',
  border: 'rgba(212,168,67,0.1)',
};

const MODE_ICONS: Record<string, typeof Film> = {
  comic: BookOpen, manga: Grid3X3, storyboard: Clapperboard, trailer: Film,
};

const MODE_LABELS: Record<string, string> = {
  comic: 'Comic', manga: 'Manga', storyboard: 'Storyboard', trailer: 'Trailer',
};

const STATUS_CONFIG: Record<string, { color: string; icon: typeof Clock; label: string }> = {
  created: { color: '#888', icon: PenTool, label: 'Draft' },
  parsing: { color: '#D4A843', icon: Loader2, label: 'Parsing' },
  parsed: { color: '#4ECDC4', icon: Palette, label: 'Styled' },
  generating_characters: { color: '#D4A843', icon: Loader2, label: 'Characters' },
  generating_panels: { color: '#D4A843', icon: Loader2, label: 'Generating' },
  generating_trailer: { color: '#D4A843', icon: Loader2, label: 'Generating' },
  complete: { color: '#4ADE80', icon: CheckCircle, label: 'Complete' },
  failed: { color: '#F87171', icon: AlertCircle, label: 'Failed' },
};

function getStatusStep(status: string): string {
  const map: Record<string, string> = {
    created: 'script', parsing: 'style', parsed: 'generate',
    generating_characters: 'generate', generating_panels: 'generate',
    generating_trailer: 'generate', complete: 'output', failed: 'generate',
  };
  return map[status] || 'script';
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    loadProjects();
  }, []);

  async function loadProjects() {
    setLoading(true);
    try {
      const data = await listProjects();
      setProjects(data);
    } catch (e) {
      console.error('Failed to load projects:', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(e: React.MouseEvent, projectId: string) {
    e.stopPropagation();
    if (!confirm('Delete this project? This cannot be undone.')) return;
    setDeleting(projectId);
    try {
      await deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
    } catch (err) {
      console.error('Delete failed:', err);
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div style={{ background: T.bg, minHeight: 'calc(100vh - 56px)' }}>
      <div style={{ maxWidth: 960, margin: '0 auto', padding: '32px 20px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
          <div>
            <h1 style={{
              fontSize: 26, fontWeight: 700, marginBottom: 4,
              background: 'linear-gradient(135deg, #FFFFFF, #E8E8E8, #C0C0C0)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
            }}>
              My Projects
            </h1>
            <p style={{ fontSize: 13, color: T.dim }}>
              {projects.length} project{projects.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button onClick={() => navigate('/project/new')} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 20px', borderRadius: 10,
            background: T.goldGrad, border: 'none', cursor: 'pointer',
            color: T.bg, fontSize: 13, fontWeight: 700,
            boxShadow: '0 2px 16px rgba(212,168,67,0.2)',
          }}>
            <Plus size={16} /> New Project
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <Loader2 size={28} color={T.gold} style={{ animation: 'spin 1s linear infinite' }} />
          </div>
        )}

        {/* Empty state */}
        {!loading && projects.length === 0 && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            padding: '80px 20px', borderRadius: 16,
            background: T.card, border: `1px dashed ${T.border}`,
          }}>
            <BookOpen size={48} color={T.dimmer} style={{ marginBottom: 16 }} />
            <h3 style={{ fontSize: 16, fontWeight: 600, color: T.silverLight, marginBottom: 6 }}>
              No projects yet
            </h3>
            <p style={{ fontSize: 13, color: T.dim, marginBottom: 20 }}>
              Create your first story and watch it come to life
            </p>
            <button onClick={() => navigate('/project/new')} style={{
              padding: '10px 24px', borderRadius: 10,
              background: T.goldGrad, border: 'none', cursor: 'pointer',
              color: T.bg, fontSize: 13, fontWeight: 700,
            }}>
              Create Your Story
            </button>
          </div>
        )}

        {/* Project Grid */}
        {!loading && projects.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280, 1fr))', gap: 16 }}>
            <AnimatePresence>
              {projects.map((project, i) => {
                const status = STATUS_CONFIG[project.status || 'created'] || STATUS_CONFIG.created;
                const StatusIcon = status.icon;
                const ModeIcon = MODE_ICONS[project.output_mode] || BookOpen;
                const step = getStatusStep(project.status || 'created');
                const sceneCount = project.script?.scenes?.length || 0;

                return (
                  <motion.div
                    key={project.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ delay: i * 0.05 }}
                    onClick={() => navigate(`/project/${project.id}?step=${step}`)}
                    style={{
                      padding: 20, borderRadius: 16, cursor: 'pointer',
                      background: T.card, border: `1px solid ${T.border}`,
                      transition: 'all 0.3s ease', position: 'relative',
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.borderColor = 'rgba(212,168,67,0.25)';
                      e.currentTarget.style.transform = 'translateY(-2px)';
                      e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.3)';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.borderColor = 'rgba(212,168,67,0.1)';
                      e.currentTarget.style.transform = 'translateY(0)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    {/* Top row: mode icon + status */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '4px 10px', borderRadius: 6,
                        background: 'rgba(212,168,67,0.06)',
                      }}>
                        <ModeIcon size={12} color={T.gold} />
                        <span style={{ fontSize: 10, fontWeight: 600, color: T.gold }}>
                          {MODE_LABELS[project.output_mode] || 'Comic'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <StatusIcon size={12} color={status.color}
                          style={status.label === 'Generating' || status.label === 'Parsing' || status.label === 'Characters'
                            ? { animation: 'spin 1s linear infinite' } : {}} />
                        <span style={{ fontSize: 10, fontWeight: 600, color: status.color }}>
                          {status.label}
                        </span>
                      </div>
                    </div>

                    {/* Title */}
                    <h3 style={{
                      fontSize: 15, fontWeight: 700, color: T.silverLight,
                      marginBottom: 6, lineHeight: 1.3,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {project.title || 'Untitled Story'}
                    </h3>

                    {/* Meta */}
                    <div style={{ display: 'flex', gap: 12, fontSize: 10, color: T.dimmer, marginBottom: 12 }}>
                      {sceneCount > 0 && <span>{sceneCount} scene{sceneCount !== 1 ? 's' : ''}</span>}
                      {project.director_style_id && <span>Style: {project.director_style_id}</span>}
                    </div>

                    {/* Footer */}
                    <div style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      paddingTop: 10, borderTop: `1px solid ${T.border}`,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Clock size={10} color={T.dimmer} />
                        <span style={{ fontSize: 10, color: T.dimmer }}>
                          {project.updated_at ? timeAgo(project.updated_at) : 'just now'}
                        </span>
                      </div>
                      <button
                        onClick={(e) => handleDelete(e, project.id)}
                        disabled={deleting === project.id}
                        style={{
                          display: 'flex', alignItems: 'center', padding: '4px 8px',
                          borderRadius: 6, background: 'transparent',
                          border: '1px solid rgba(248,113,113,0.15)', cursor: 'pointer',
                          color: '#F87171', fontSize: 10, opacity: 0.5,
                          transition: 'opacity 0.2s',
                        }}
                        onMouseOver={(e) => e.currentTarget.style.opacity = '1'}
                        onMouseOut={(e) => e.currentTarget.style.opacity = '0.5'}
                      >
                        {deleting === project.id ? <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} /> : <Trash2 size={10} />}
                      </button>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
