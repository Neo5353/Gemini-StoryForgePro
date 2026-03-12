import { useState } from 'react';
import { motion } from 'framer-motion';
import { Edit3, Save, X, RefreshCw, Loader2 } from 'lucide-react';
import type { SceneBeat } from '../../types';

const T = {
  bg: '#0a0a0a',
  card: '#111111',
  cardLight: '#161616', 
  gold: '#D4A843',
  goldLight: '#F0D78C',
  goldGrad: 'linear-gradient(135deg, #FFF1B8, #F0D78C, #D4A843, #8B6914)',
  silverLight: '#E8E8E8',
  dim: '#888',
  dimmer: '#555',
  border: 'rgba(212,168,67,0.1)',
};

interface SceneEditorProps {
  scenes: SceneBeat[];
  onSceneEdit: (sceneId: string, field: string, value: string) => void;
  onRegenerateStory?: () => void;
  isRegenerating?: boolean;
}

export function SceneEditor({ scenes, onSceneEdit, onRegenerateStory, isRegenerating }: SceneEditorProps) {
  const [editingScene, setEditingScene] = useState<string | null>(null);
  const [editField, setEditField] = useState<string>('');
  const [editValue, setEditValue] = useState<string>('');

  const startEdit = (sceneId: string, field: string, currentValue: string) => {
    setEditingScene(sceneId);
    setEditField(field);
    setEditValue(currentValue);
  };

  const saveEdit = () => {
    if (editingScene) {
      onSceneEdit(editingScene, editField, editValue);
    }
    setEditingScene(null);
  };

  const cancelEdit = () => {
    setEditingScene(null);
  };

  if (scenes.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{
          padding: 32, textAlign: 'center', borderRadius: 14,
          background: T.card, border: `1px solid ${T.border}`,
        }}>
          <p style={{ color: T.dim, fontSize: 14, marginBottom: 16 }}>
            No scenes found. Generate scenes from your script first.
          </p>
          {onRegenerateStory && (
            <button
              onClick={onRegenerateStory}
              disabled={isRegenerating}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, margin: '0 auto',
                padding: '10px 16px', borderRadius: 8,
                background: isRegenerating ? T.cardLight : T.goldGrad,
                border: 'none',
                cursor: isRegenerating ? 'default' : 'pointer',
                color: isRegenerating ? T.dim : T.bg,
                fontSize: 13, fontWeight: 600,
                boxShadow: isRegenerating ? 'none' : '0 2px 12px rgba(212,168,67,0.2)',
              }}
            >
              {isRegenerating ? (
                <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Analyzing Script...</>
              ) : (
                <><RefreshCw size={16} /> Analyze Script</>
              )}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: T.silverLight, marginBottom: 4 }}>
            Story Scenes
          </h3>
          <p style={{ fontSize: 13, color: T.dim }}>
            {scenes.length} scenes · Click any text to edit
          </p>
        </div>
        {onRegenerateStory && (
          <button
            onClick={onRegenerateStory}
            disabled={isRegenerating}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 12px', borderRadius: 6,
              background: isRegenerating ? T.cardLight : T.goldGrad,
              border: 'none',
              cursor: isRegenerating ? 'default' : 'pointer',
              color: isRegenerating ? T.dim : T.bg,
              fontSize: 11, fontWeight: 600,
              boxShadow: isRegenerating ? 'none' : '0 2px 12px rgba(212,168,67,0.2)',
            }}
          >
            {isRegenerating ? (
              <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> Regenerating...</>
            ) : (
              <><RefreshCw size={12} /> Regenerate Scenes</>
            )}
          </button>
        )}
      </div>

      {/* Scene List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {scenes.map((scene, idx) => {
          const isEditing = editingScene === scene.id;
          return (
            <motion.div
              key={scene.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.04 }}
              style={{
                padding: 20, borderRadius: 14,
                background: T.card, border: `1px solid ${T.border}`,
                transition: 'border-color 0.3s',
              }}
            >
              {/* Scene Header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, fontFamily: 'monospace',
                  padding: '4px 10px', borderRadius: 6,
                  background: 'rgba(212,168,67,0.08)', color: T.gold,
                }}>
                  Scene {scene.scene_number}
                </span>
                
                {isEditing && editField === 'title' ? (
                  <div style={{ display: 'flex', gap: 8, flex: 1, alignItems: 'center' }}>
                    <input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && saveEdit()}
                      autoFocus
                      style={{
                        flex: 1, padding: '8px 12px', borderRadius: 6,
                        background: '#1a1a1a', border: '1px solid rgba(212,168,67,0.3)',
                        color: '#e0e0e0', fontSize: 14, fontWeight: 600, outline: 'none',
                      }}
                    />
                    <button onClick={saveEdit} style={buttonStyle}><Save size={14} /></button>
                    <button onClick={cancelEdit} style={buttonStyle}><X size={14} /></button>
                  </div>
                ) : (
                  <button
                    onClick={() => startEdit(scene.id, 'title', scene.title)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 6, flex: 1,
                      background: 'none', border: 'none', cursor: 'pointer',
                      fontSize: 15, fontWeight: 600, color: T.silverLight,
                      textAlign: 'left', padding: 0,
                    }}
                  >
                    {scene.title}
                    <Edit3 size={12} color={T.dimmer} style={{ opacity: 0.5 }} />
                  </button>
                )}

                {/* Scene Metadata */}
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {scene.location && (
                    <span style={{
                      fontSize: 10, padding: '3px 8px', borderRadius: 12,
                      background: 'rgba(255,255,255,0.04)', color: T.dim,
                    }}>
                      📍 {scene.location}
                    </span>
                  )}
                  {scene.time_of_day && (
                    <span style={{
                      fontSize: 10, padding: '3px 8px', borderRadius: 12,
                      background: 'rgba(255,255,255,0.04)', color: T.dim,
                    }}>
                      🕐 {scene.time_of_day}
                    </span>
                  )}
                  {scene.mood && (
                    <span style={{
                      fontSize: 10, padding: '3px 8px', borderRadius: 12,
                      background: 'rgba(255,255,255,0.04)', color: T.dim,
                    }}>
                      💭 {scene.mood}
                    </span>
                  )}
                </div>
              </div>

              {/* Scene Description */}
              {isEditing && editField === 'description' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <textarea
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    autoFocus
                    rows={4}
                    style={{
                      padding: '12px', borderRadius: 6,
                      background: '#1a1a1a', border: '1px solid rgba(212,168,67,0.3)',
                      color: '#e0e0e0', fontSize: 13, lineHeight: 1.6, outline: 'none',
                      resize: 'vertical', minHeight: 100, fontFamily: 'inherit',
                    }}
                  />
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={saveEdit} style={{...buttonStyle, padding: '6px 12px'}}>
                      <Save size={12} /> Save
                    </button>
                    <button onClick={cancelEdit} style={{...buttonStyle, padding: '6px 12px'}}>
                      <X size={12} /> Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => startEdit(scene.id, 'description', scene.description)}
                  style={{
                    width: '100%', textAlign: 'left', background: 'none', border: 'none',
                    cursor: 'pointer', padding: '12px', borderRadius: 8,
                    backgroundColor: 'rgba(255,255,255,0.02)',
                    transition: 'background-color 0.2s',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.04)'}
                  onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.02)'}
                >
                  <p style={{
                    fontSize: 13, lineHeight: 1.6, color: '#aaa', margin: 0,
                  }}>
                    {scene.description}
                  </p>
                </button>
              )}

              {/* Characters */}
              {scene.characters && scene.characters.length > 0 && (
                <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${T.border}` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, color: T.dim, fontWeight: 600 }}>Characters:</span>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {scene.characters.map((char, i) => (
                        <span
                          key={i}
                          style={{
                            fontSize: 10, padding: '2px 8px', borderRadius: 10,
                            background: 'rgba(212,168,67,0.08)', color: T.goldLight,
                            border: `1px solid rgba(212,168,67,0.15)`,
                          }}
                        >
                          {char}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

const buttonStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4,
  padding: '4px 8px', borderRadius: 4,
  background: 'rgba(212,168,67,0.08)', border: '1px solid rgba(212,168,67,0.15)',
  color: T.gold, fontSize: 10, fontWeight: 600, cursor: 'pointer',
};