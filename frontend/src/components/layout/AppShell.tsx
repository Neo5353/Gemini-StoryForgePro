import { Outlet, Link, useLocation } from 'react-router-dom';
import { Clapperboard, Home, FolderOpen } from 'lucide-react';

export function AppShell() {
  const location = useLocation();
  const isHome = location.pathname === '/';
  const isProjects = location.pathname === '/projects';

  return (
    <div style={{ minHeight: '100vh', background: '#0a0a0a', color: '#e0e0e0' }}>
      {/* Header */}
      <header style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 40,
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        background: 'rgba(10,10,10,0.85)',
        borderBottom: '1px solid rgba(200,170,80,0.08)',
      }}>
        <div style={{
          maxWidth: 1200, margin: '0 auto', padding: '0 24px',
          height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none', color: 'inherit' }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'linear-gradient(135deg, #F0D78C, #D4A843, #8B6914)',
            }}>
              <Clapperboard size={15} color="#0a0a0a" />
            </div>
            <span style={{ fontSize: 14, fontWeight: 700, letterSpacing: '-0.02em' }}>
              StoryForge<span style={{ color: '#D4A843' }}> Pro</span>
            </span>
          </Link>
          <nav style={{ display: 'flex', gap: 4 }}>
            <Link to="/" style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', borderRadius: 8, fontSize: 12, fontWeight: 500,
              textDecoration: 'none',
              color: isHome ? '#F0D78C' : '#888',
              background: isHome ? 'rgba(212,168,67,0.08)' : 'transparent',
            }}>
              <Home size={13} /> Home
            </Link>
            <Link to="/projects" style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', borderRadius: 8, fontSize: 12, fontWeight: 500,
              textDecoration: 'none',
              color: isProjects ? '#F0D78C' : '#888',
              background: isProjects ? 'rgba(212,168,67,0.08)' : 'transparent',
            }}>
              <FolderOpen size={13} /> My Projects
            </Link>
          </nav>
        </div>
      </header>

      <main style={{ paddingTop: 56 }}>
        <Outlet />
      </main>
    </div>
  );
}
