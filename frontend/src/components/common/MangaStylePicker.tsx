import { useProjectStore } from '../../stores/projectStore';

const T = {
  card: '#111111', gold: '#D4A843', goldLight: '#F0D78C',
  goldDark: '#8B6914', silverLight: '#E8E8E8', dim: '#888',
};

interface MangaStyle {
  id: string;
  name: string;
  desc: string;
  image: string;
}

const MANGA_STYLES: MangaStyle[] = [
  {
    id: 'shonen',
    name: 'Shōnen',
    desc: 'High-energy action, bold lines, speed effects',
    image: '/styles/shonen.png',
  },
  {
    id: 'shojo',
    name: 'Shōjo',
    desc: 'Elegant, expressive eyes, floral motifs',
    image: '/styles/shojo.png',
  },
  {
    id: 'seinen',
    name: 'Seinen',
    desc: 'Dark, detailed, mature themes',
    image: '/styles/seinen.png',
  },
  {
    id: 'chibi',
    name: 'Chibi / Kawaii',
    desc: 'Cute, oversized heads, pastel colors',
    image: '/styles/chibi.png',
  },
];

export function MangaStylePicker() {
  const { selectedStyleId, setSelectedStyle } = useProjectStore();

  return (
    <div>
      <p style={{ fontSize: 11, color: T.dim, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
        Manga Style
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {MANGA_STYLES.map((style) => {
          const active = selectedStyleId === style.id;
          return (
            <button key={style.id} onClick={() => setSelectedStyle(style.id)} style={{
              display: 'flex', flexDirection: 'column', padding: 0, borderRadius: 14,
              cursor: 'pointer', overflow: 'hidden',
              background: active ? 'rgba(212,168,67,0.06)' : T.card,
              border: active ? `2px solid ${T.gold}` : '1px solid rgba(212,168,67,0.08)',
              boxShadow: active ? '0 0 24px rgba(212,168,67,0.15)' : '0 2px 8px rgba(0,0,0,0.3)',
              transition: 'all 0.3s ease',
            }}
              onMouseOver={(e) => { if (!active) e.currentTarget.style.borderColor = 'rgba(212,168,67,0.25)'; e.currentTarget.style.transform = 'translateY(-3px)'; }}
              onMouseOut={(e) => { if (!active) e.currentTarget.style.borderColor = active ? T.gold : 'rgba(212,168,67,0.08)'; e.currentTarget.style.transform = 'translateY(0)'; }}
            >
              <div style={{
                width: '100%', aspectRatio: '3/4', overflow: 'hidden',
                background: '#0a0a0a',
              }}>
                <img
                  src={style.image}
                  alt={style.name}
                  style={{
                    width: '100%', height: '100%', objectFit: 'cover',
                    transition: 'transform 0.3s ease',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.05)'}
                  onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
                />
              </div>
              <div style={{ padding: '12px 14px' }}>
                <h3 style={{ fontSize: 12, fontWeight: 700, color: active ? T.goldLight : T.silverLight, marginBottom: 3 }}>{style.name}</h3>
                <p style={{ fontSize: 10, color: T.dim, lineHeight: 1.4 }}>{style.desc}</p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
