import { BookOpen, Layers, LayoutGrid, Video } from 'lucide-react';
import { useProjectStore } from '../../stores/projectStore';
import type { OutputMode } from '../../types';

const T = {
  card: '#111111', gold: '#D4A843', goldLight: '#F0D78C',
  silverLight: '#E8E8E8', dim: '#888',
};

const MODES: { id: OutputMode; icon: typeof BookOpen; label: string; desc: string }[] = [
  { id: 'comic', icon: BookOpen, label: 'Comic', desc: 'Color panels + bubbles' },
  { id: 'manga', icon: Layers, label: 'Manga', desc: 'B&W, R-to-L flow' },
  { id: 'storyboard', icon: LayoutGrid, label: 'Storyboard', desc: 'Shot types + notes' },
  { id: 'trailer', icon: Video, label: 'Trailer', desc: 'Cinematic video' },
];

export function ModePicker() {
  const { selectedMode, setSelectedMode } = useProjectStore();

  return (
    <div>
      <p style={{ fontSize: 11, color: T.dim, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Output Format</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        {MODES.map((m) => {
          const Icon = m.icon;
          const active = selectedMode === m.id;
          return (
            <button key={m.id} onClick={() => setSelectedMode(m.id)} style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
              padding: '18px 10px', borderRadius: 12, cursor: 'pointer',
              background: active ? 'rgba(212,168,67,0.06)' : T.card,
              border: active ? `1.5px solid ${T.gold}` : '1px solid rgba(212,168,67,0.08)',
              boxShadow: active ? '0 0 20px rgba(212,168,67,0.1)' : 'none',
              transition: 'all 0.3s ease',
            }}
              onMouseOver={(e) => { if (!active) e.currentTarget.style.borderColor = 'rgba(212,168,67,0.2)'; }}
              onMouseOut={(e) => { if (!active) e.currentTarget.style.borderColor = 'rgba(212,168,67,0.08)'; }}
            >
              <Icon size={22} color={active ? T.goldLight : T.dim} style={{ marginBottom: 8 }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: active ? T.goldLight : T.silverLight, marginBottom: 2 }}>{m.label}</span>
              <span style={{ fontSize: 9, color: T.dim }}>{m.desc}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
