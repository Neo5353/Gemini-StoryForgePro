import { create } from 'zustand';
import type { GenerationStatus, SceneProgress } from '../types';

interface GenerationStore {
  isGenerating: boolean;
  overallProgress: number;
  currentPhase: string;
  scenes: SceneProgress[];
  sceneNames: Record<string, string>; // scene_id → display name
  clipsDone: number;
  clipsTotal: number;

  // Actions
  startGeneration: (sceneIds: string[], sceneNames?: Record<string, string>) => void;
  updateClips: (done: number, total: number) => void;
  updateSceneProgress: (sceneId: string, progress: number, status: GenerationStatus, thumbnail?: string) => void;
  updateOverall: (progress: number, phase: string) => void;
  setSceneComplete: (sceneId: string, thumbnailUrl: string) => void;
  setError: (sceneId: string, message: string) => void;
  completeGeneration: () => void;
  reset: () => void;
}

export const useGenerationStore = create<GenerationStore>((set) => ({
  isGenerating: false,
  overallProgress: 0,
  currentPhase: '',
  scenes: [],
  sceneNames: {},
  clipsDone: 0,
  clipsTotal: 0,

  startGeneration: (sceneIds, sceneNames) =>
    set({
      isGenerating: true,
      overallProgress: 0,
      currentPhase: 'Initializing...',
      sceneNames: sceneNames ?? {},
      clipsDone: 0,
      clipsTotal: 0,
      scenes: sceneIds.map((id) => ({
        scene_id: id,
        status: 'queued' as GenerationStatus,
        progress: 0,
        thumbnail_url: null,
        message: 'Waiting...',
      })),
    }),

  updateClips: (done, total) => set({ clipsDone: done, clipsTotal: total }),

  updateSceneProgress: (sceneId, progress, status, thumbnail) =>
    set((state) => ({
      scenes: state.scenes.map((s) =>
        s.scene_id === sceneId
          ? { ...s, progress, status, thumbnail_url: thumbnail ?? s.thumbnail_url, message: `${progress}%` }
          : s,
      ),
    })),

  updateOverall: (overallProgress, currentPhase) => set({ overallProgress, currentPhase }),

  setSceneComplete: (sceneId, thumbnailUrl) =>
    set((state) => ({
      scenes: state.scenes.map((s) =>
        s.scene_id === sceneId
          ? { ...s, status: 'complete', progress: 100, thumbnail_url: thumbnailUrl, message: 'Done' }
          : s,
      ),
    })),

  setError: (sceneId, message) =>
    set((state) => ({
      scenes: state.scenes.map((s) =>
        s.scene_id === sceneId ? { ...s, status: 'error', message } : s,
      ),
    })),

  completeGeneration: () => set({ isGenerating: false, overallProgress: 100, currentPhase: 'Complete!' }),
  reset: () => set({ isGenerating: false, overallProgress: 0, currentPhase: '', scenes: [], sceneNames: {}, clipsDone: 0, clipsTotal: 0 }),
}));
