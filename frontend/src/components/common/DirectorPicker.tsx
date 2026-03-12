import { useEffect } from 'react';
import { Clapperboard } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { fetchDirectors } from '../../services/api';
import { useProjectStore } from '../../stores/projectStore';
import type { DirectorStyle } from '../../types';

const T = {
  bg: '#0a0a0a', card: '#111111', gold: '#D4A843', goldLight: '#F0D78C',
  goldDark: '#8B6914', silver: '#C0C0C0', silverLight: '#E8E8E8', dim: '#888',
};

function DirectorCard({ director, isSelected, onSelect }: {
  director: DirectorStyle; isSelected: boolean; onSelect: () => void;
}) {
  const { palette } = director;
  return (
    <button onClick={onSelect} style={{
      display: 'flex', flexDirection: 'column', padding: 18, borderRadius: 12,
      textAlign: 'left', cursor: 'pointer', width: '100%',
      background: isSelected ? 'rgba(212,168,67,0.06)' : T.card,
      border: isSelected ? `1.5px solid ${T.gold}` : '1px solid rgba(212,168,67,0.08)',
      boxShadow: isSelected ? `0 0 24px rgba(212,168,67,0.12)` : '0 2px 8px rgba(0,0,0,0.3)',
      transition: 'all 0.3s ease', position: 'relative', overflow: 'hidden',
    }}
      onMouseOver={(e) => { if (!isSelected) e.currentTarget.style.borderColor = 'rgba(212,168,67,0.2)'; }}
      onMouseOut={(e) => { if (!isSelected) e.currentTarget.style.borderColor = 'rgba(212,168,67,0.08)'; }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <Clapperboard size={14} color={isSelected ? T.goldLight : T.gold} />
        <span style={{ fontSize: 13, fontWeight: 700, color: isSelected ? T.goldLight : T.silverLight }}>{director.name}</span>
      </div>
      <p style={{ fontSize: 10, color: T.dim, fontStyle: 'italic', marginBottom: 8 }}>"{director.tagline}"</p>
      <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
        {Object.values(palette).map((color, i) => (
          <div key={i} style={{ width: 14, height: 14, borderRadius: '50%', backgroundColor: color, border: '1px solid rgba(255,255,255,0.08)' }} />
        ))}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {director.filmography.slice(0, 3).map((f) => (
          <span key={f} style={{ fontSize: 9, padding: '2px 8px', borderRadius: 20, background: 'rgba(212,168,67,0.06)', color: T.dim }}>{f}</span>
        ))}
      </div>
    </button>
  );
}

export function DirectorPicker() {
  const { selectedDirectorId, setSelectedDirector, setDirectors, directors } = useProjectStore();
  const { data, isLoading } = useQuery({ queryKey: ['directors'], queryFn: fetchDirectors, staleTime: 5 * 60 * 1000 });

  useEffect(() => { if (data) setDirectors(data); }, [data, setDirectors]);

  const displayDirectors: DirectorStyle[] = directors.length > 0 ? directors : [
    { id: 'nolan', name: 'Christopher Nolan', tagline: 'Dark, cerebral, mind-bending', palette: { primary: '#1a1a2e', secondary: '#16213e', accent: '#e94560', shadow: '#0f3460', highlight: '#c4c4c4' }, filmography: ['Inception', 'Interstellar', 'The Dark Knight'], traits: [], thumbnail_url: '' },
    { id: 'cameron', name: 'James Cameron', tagline: 'Epic scale, emotional spectacle', palette: { primary: '#0077b6', secondary: '#00b4d8', accent: '#ff6b35', shadow: '#023e8a', highlight: '#ffd166' }, filmography: ['Avatar', 'Titanic', 'Aliens'], traits: [], thumbnail_url: '' },
    { id: 'ritchie', name: 'Guy Ritchie', tagline: 'Fast, gritty, wickedly fun', palette: { primary: '#2d3436', secondary: '#636e72', accent: '#d4a574', shadow: '#1a1a1a', highlight: '#b2bec3' }, filmography: ['Snatch', 'Lock Stock', 'The Gentlemen'], traits: [], thumbnail_url: '' },
    { id: 'maniratnam', name: 'Mani Ratnam', tagline: 'Poetic, painterly, soulful', palette: { primary: '#d4a574', secondary: '#c17817', accent: '#048a81', shadow: '#2e4057', highlight: '#f4e1c1' }, filmography: ['Roja', 'Bombay', 'Ponniyin Selvan'], traits: [], thumbnail_url: '' },
    { id: 'nelson', name: 'Nelson Dilipkumar', tagline: 'Bold, twisted, electrifying', palette: { primary: '#e63946', secondary: '#f1c40f', accent: '#ff006e', shadow: '#000000', highlight: '#8338ec' }, filmography: ['Kolamaavu Kokila', 'Doctor', 'Jailer'], traits: [], thumbnail_url: '' },
  ];

  if (isLoading) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} style={{ height: 120, borderRadius: 12, background: T.card, opacity: 0.5 }} />
        ))}
      </div>
    );
  }

  return (
    <div>
      <p style={{ fontSize: 11, color: T.dim, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Director's Eye</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
        {displayDirectors.map((d) => (
          <DirectorCard key={d.id} director={d} isSelected={selectedDirectorId === d.id} onSelect={() => setSelectedDirector(d.id)} />
        ))}
      </div>
    </div>
  );
}
