import { create } from 'zustand';
import { patchProject } from '../services/api';
import type {
  Project,
  OutputMode,
  ScriptFormat,
  DirectorStyle,
  SceneBeat,
  CharacterRef,
  PageData,
  StoryboardFrameData,
  VideoData,
} from '../types';

// ── Debounce helper ──

let _saveTimer: ReturnType<typeof setTimeout> | null = null;
const SAVE_DELAY = 1200; // ms

function debouncedSave(projectId: string, updates: Record<string, unknown>) {
  if (_saveTimer) clearTimeout(_saveTimer);
  _saveTimer = setTimeout(async () => {
    try {
      await patchProject(projectId, updates);
      console.log('[autosave] saved', Object.keys(updates));
    } catch (e) {
      console.warn('[autosave] failed', e);
    }
  }, SAVE_DELAY);
}

// ── Draft persistence (localStorage for pre-creation state) ──

const DRAFT_KEY = 'storyforge_draft';

function saveDraft(state: Pick<ProjectState, 'draftTitle' | 'draftScript' | 'draftFormat' | 'selectedDirectorId' | 'selectedStyleId' | 'selectedMode'>) {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({
      draftTitle: state.draftTitle,
      draftScript: state.draftScript,
      draftFormat: state.draftFormat,
      selectedDirectorId: state.selectedDirectorId,
      selectedStyleId: state.selectedStyleId,
      selectedMode: state.selectedMode,
      savedAt: Date.now(),
    }));
  } catch { /* quota exceeded etc */ }
}

function loadDraft(): Partial<ProjectState> {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return {};
    const data = JSON.parse(raw);
    // Expire drafts older than 24h
    if (Date.now() - (data.savedAt || 0) > 86_400_000) {
      localStorage.removeItem(DRAFT_KEY);
      return {};
    }
    return data;
  } catch { return {}; }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY);
}

// ── Store ──

interface ProjectState {
  project: Project | null;
  isLoading: boolean;
  error: string | null;

  draftTitle: string;
  draftScript: string;
  draftFormat: ScriptFormat;
  selectedDirectorId: string | null;
  selectedStyleId: string | null;
  selectedMode: OutputMode;

  directors: DirectorStyle[];
  _skipAutoSave: boolean; // internal flag to prevent auto-save during project load

  setProject: (project: Project) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setDraftTitle: (title: string) => void;
  setDraftScript: (script: string) => void;
  setDraftFormat: (format: ScriptFormat) => void;
  setSelectedDirector: (id: string | null) => void;
  setSelectedStyle: (id: string | null) => void;
  setSelectedMode: (mode: OutputMode) => void;
  setDirectors: (directors: DirectorStyle[]) => void;
  updateScene: (sceneId: string, field: string, value: string) => void;
  updateScenes: (scenes: SceneBeat[]) => void;
  updateCharacters: (characters: CharacterRef[]) => void;
  updatePages: (pages: PageData[]) => void;
  updateStoryboardFrames: (frames: StoryboardFrameData[]) => void;
  updateVideo: (video: VideoData) => void;
  reset: () => void;
}

const defaultState = {
  project: null,
  isLoading: false,
  error: null,
  draftTitle: '',
  draftScript: '',
  draftFormat: 'freeform' as ScriptFormat,
  selectedDirectorId: null as string | null,
  selectedStyleId: null as string | null,
  selectedMode: 'comic' as OutputMode,
  directors: [] as DirectorStyle[],
  _skipAutoSave: false,
};

// Merge saved draft into initial state
const draft = loadDraft();
const initialState = { ...defaultState, ...draft };

export const useProjectStore = create<ProjectState>((set, get) => ({
  ...initialState,

  setProject: (project) => {
    // Cancel any pending auto-save from previous project
    if (_saveTimer) { clearTimeout(_saveTimer); _saveTimer = null; }
    clearDraft(); // Project created — draft no longer needed
    set({ project, error: null, _skipAutoSave: true });
    // Re-enable auto-save after a tick (once load-time setters have fired)
    setTimeout(() => set({ _skipAutoSave: false }), 100);
  },

  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error, isLoading: false }),

  setDraftTitle: (draftTitle) => {
    set({ draftTitle });
    const { project, _skipAutoSave } = get();
    if (_skipAutoSave) return; // Don't auto-save during project load
    if (project) {
      debouncedSave(project.id, { title: draftTitle });
    } else {
      saveDraft({ ...get(), draftTitle });
    }
  },

  setDraftScript: (draftScript) => {
    set({ draftScript });
    const { project, _skipAutoSave } = get();
    if (_skipAutoSave) return; // Don't auto-save during project load
    if (project) {
      debouncedSave(project.id, { script: draftScript });
    } else {
      saveDraft({ ...get(), draftScript });
    }
  },

  setDraftFormat: (draftFormat) => {
    set({ draftFormat });
    if (!get().project) saveDraft({ ...get(), draftFormat });
  },

  setSelectedDirector: (selectedDirectorId) => {
    set({ selectedDirectorId });
    const { project, _skipAutoSave } = get();
    if (_skipAutoSave) return;
    if (project && selectedDirectorId) {
      debouncedSave(project.id, { director_style: selectedDirectorId });
    } else {
      saveDraft({ ...get(), selectedDirectorId });
    }
  },

  setSelectedStyle: (selectedStyleId) => {
    set({ selectedStyleId });
    const { project, _skipAutoSave } = get();
    if (_skipAutoSave) return;
    if (project && selectedStyleId) {
      debouncedSave(project.id, { director_style: selectedStyleId });
    } else {
      saveDraft({ ...get(), selectedStyleId });
    }
  },

  setSelectedMode: (selectedMode) => {
    set({ selectedMode, selectedStyleId: null, selectedDirectorId: null });
    const { project, _skipAutoSave } = get();
    if (_skipAutoSave) return;
    if (project) {
      debouncedSave(project.id, { output_mode: selectedMode });
    } else {
      saveDraft({ ...get(), selectedMode, selectedStyleId: null, selectedDirectorId: null });
    }
  },

  setDirectors: (directors) => set({ directors }),

  updateScene: (sceneId, field, value) => {
    set((state) => {
      if (!state.project) return state;
      const scenes = state.project.script.scenes.map((s) =>
        s.id === sceneId ? { ...s, [field]: value } : s
      );
      return { project: { ...state.project, script: { ...state.project.script, scenes } } };
    });
    // Auto-save the edited scene to backend
    const { project } = get();
    if (project) {
      const scene = project.script.scenes.find((s) => s.id === sceneId);
      if (scene) {
        debouncedSave(project.id, {
          scenes: [{ id: sceneId, [field]: value }],
        });
      }
    }
  },

  updateScenes: (scenes) =>
    set((state) => {
      if (!state.project) return state;
      return { project: { ...state.project, script: { ...state.project.script, scenes } } };
    }),

  updateCharacters: (characters) =>
    set((state) => {
      if (!state.project) return state;
      return { project: { ...state.project, characters } };
    }),

  updatePages: (pages) =>
    set((state) => {
      if (!state.project) return state;
      return { project: { ...state.project, pages } };
    }),

  updateStoryboardFrames: (storyboard_frames) =>
    set((state) => {
      if (!state.project) return state;
      return { project: { ...state.project, storyboard_frames } };
    }),

  updateVideo: (video) =>
    set((state) => {
      if (!state.project) return state;
      return { project: { ...state.project, video } };
    }),

  reset: () => {
    if (_saveTimer) { clearTimeout(_saveTimer); _saveTimer = null; }
    clearDraft();
    set(defaultState);
  },
}));
