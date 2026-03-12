import { useState, useCallback, useMemo } from 'react';
import { FileText, Film, PenTool, MessageSquareMore, Save, Check } from 'lucide-react';
import { useProjectStore } from '../../stores/projectStore';
import { StoryChat } from './StoryChat';
import { patchProject } from '../../services/api';
import type { ScriptFormat } from '../../types';

const T = {
  bg: '#0a0a0a', card: '#111111', gold: '#D4A843', goldLight: '#F0D78C',
  goldDark: '#8B6914', silverLight: '#E8E8E8', dim: '#888',
};

type ActiveTab = ScriptFormat | 'ai';

const FORMAT_HINTS: Record<ScriptFormat, { icon: typeof FileText; label: string; hint: string; example: string }> = {
  screenplay: {
    icon: Film, label: 'Screenplay',
    hint: 'Standard format with INT/EXT, character names in caps, dialogue blocks.',
    example: `INT. COFFEE SHOP - DAY\n\nSARAH sits at a corner table.\n\nSARAH\nI didn't think you'd come.`,
  },
  prose: {
    icon: FileText, label: 'Prose',
    hint: 'Narrative style with descriptions and dialogue in quotes.',
    example: `The coffee shop was quiet. Sarah sat in the corner, fingers wrapped around a cold mug. "I didn't think you'd come," she whispered.`,
  },
  freeform: {
    icon: PenTool, label: 'Freeform',
    hint: 'Bullet points, outlines, stream of consciousness — any format.',
    example: `Scene 1: Coffee shop meeting\n- Sarah is waiting, nervous\n- Jake arrives late, wet from rain`,
  },
};

const TABS: { key: ActiveTab; icon: typeof FileText; label: string }[] = [
  { key: 'screenplay', icon: Film, label: 'Screenplay' },
  { key: 'prose', icon: FileText, label: 'Prose' },
  { key: 'freeform', icon: PenTool, label: 'Freeform' },
  { key: 'ai', icon: MessageSquareMore, label: 'StoryForge AI' },
];

function detectFormat(text: string): ScriptFormat {
  const lines = text.split('\n').filter(Boolean);
  const hasHeaders = lines.some((l) => /^(INT\.|EXT\.)/.test(l.trim()));
  const hasCues = lines.some((l) => /^[A-Z]{2,}(\s*\(.*\))?$/.test(l.trim()));
  if (hasHeaders && hasCues) return 'screenplay';
  const hasQuotes = (text.match(/"/g)?.length ?? 0) > 2;
  const avgLen = text.length / Math.max(lines.length, 1);
  if (hasQuotes && avgLen > 80) return 'prose';
  return 'freeform';
}

export function ScriptEditor() {
  const { draftScript, draftFormat, project, setDraftScript, setDraftFormat } = useProjectStore();
  const [activeTab, setActiveTab] = useState<ActiveTab>(draftFormat);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');

  const handleChange = useCallback((value: string) => {
    setDraftScript(value);
    if (value.length > 30) {
      const detected = detectFormat(value);
      setDraftFormat(detected);
      setActiveTab(detected);
    }
  }, [setDraftScript, setDraftFormat]);

  const handleTabClick = useCallback((tab: ActiveTab) => {
    setActiveTab(tab);
    if (tab !== 'ai') setDraftFormat(tab);
  }, [setDraftFormat]);

  const handleScriptFromChat = useCallback((script: string) => {
    setDraftScript(script);
    const detected = detectFormat(script);
    setDraftFormat(detected);
    setActiveTab(detected);
  }, [setDraftScript, setDraftFormat]);

  const handleSave = useCallback(async () => {
    if (!project || !draftScript.trim()) return;
    
    setSaveState('saving');
    try {
      await patchProject(project.id, { 
        script: draftScript,
        script_format: draftFormat 
      });
      setSaveState('saved');
      setTimeout(() => setSaveState('idle'), 2000);
    } catch (error) {
      console.error('Save failed:', error);
      setSaveState('idle');
    }
  }, [project, draftScript, draftFormat]);

  const isAI = activeTab === 'ai';
  const formatKey = isAI ? draftFormat : activeTab;
  const active = FORMAT_HINTS[formatKey];
  const Icon = active.icon;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Tabs */}
      <div style={{ display: 'flex', gap: 6 }}>
        {TABS.map(({ key, icon: TabIcon, label }) => {
          const isActive = key === activeTab;
          return (
            <button key={key} onClick={() => handleTabClick(key)} style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 8,
              fontSize: 12, fontWeight: isActive ? 600 : 400, cursor: 'pointer',
              background: isActive
                ? key === 'ai' ? 'rgba(212,168,67,0.12)' : 'rgba(212,168,67,0.08)'
                : 'transparent',
              border: isActive ? `1px solid rgba(212,168,67,0.2)` : '1px solid transparent',
              color: isActive ? T.goldLight : T.dim, transition: 'all 0.2s',
            }}>
              <TabIcon size={13} /> {label}
            </button>
          );
        })}
      </div>

      {isAI ? (
        /* ── AI Chat ── */
        <StoryChat onScriptReady={handleScriptFromChat} />
      ) : (
        /* ── Write/Paste ── */
        <>
          {/* Hint */}
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 14px', borderRadius: 10,
            background: 'rgba(212,168,67,0.03)', border: '1px solid rgba(212,168,67,0.06)',
          }}>
            <Icon size={15} color={T.dim} style={{ marginTop: 2, flexShrink: 0 }} />
            <div>
              <p style={{ fontSize: 12, color: T.silverLight }}>{active.hint}</p>
              <details style={{ marginTop: 6 }}>
                <summary style={{ fontSize: 10, color: T.dim, cursor: 'pointer' }}>Show example</summary>
                <pre style={{ marginTop: 6, fontSize: 10, color: T.dim, whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>{active.example}</pre>
              </details>
            </div>
          </div>

          {/* Editor */}
          <textarea
            value={draftScript}
            onChange={(e) => handleChange(e.target.value)}
            placeholder="Paste your script, outline, or story idea here..."
            style={{
              width: '100%', height: 300, padding: 16, borderRadius: 12,
              background: T.card, border: `1px solid rgba(212,168,67,0.08)`,
              color: T.silverLight, fontSize: 13, fontFamily: 'monospace', lineHeight: 1.7,
              resize: 'none', outline: 'none', transition: 'border-color 0.3s',
            }}
            onFocus={(e) => e.currentTarget.style.borderColor = T.gold}
            onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(212,168,67,0.08)'}
            spellCheck={false}
          />

          {/* Save Button */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <button
              onClick={handleSave}
              disabled={!project || !draftScript.trim() || saveState === 'saving'}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '8px 16px', borderRadius: 8,
                background: saveState === 'saved' 
                  ? 'rgba(34, 197, 94, 0.15)' 
                  : saveState === 'saving'
                    ? T.card
                    : T.goldDark,
                border: saveState === 'saved'
                  ? '1px solid rgba(34, 197, 94, 0.3)'
                  : '1px solid transparent',
                color: saveState === 'saved'
                  ? '#22c55e'
                  : saveState === 'saving'
                    ? T.dim
                    : '#fff',
                fontSize: 12, fontWeight: 600, cursor: saveState === 'saving' ? 'default' : 'pointer',
                transition: 'all 0.3s', opacity: (!project || !draftScript.trim()) ? 0.4 : 1,
              }}
            >
              {saveState === 'saved' ? (
                <><Check size={14} /> Saved</>
              ) : saveState === 'saving' ? (
                <><Save size={14} className="animate-spin" /> Saving...</>
              ) : (
                <><Save size={14} /> Save Script</>
              )}
            </button>

            {/* Stats */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', fontSize: 10, color: T.dim }}>
              <span>Format: <span style={{ color: T.silverLight }}>{active.label}</span></span>
              <span>{draftScript.length} chars · {draftScript.split('\n').filter(Boolean).length} lines</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
