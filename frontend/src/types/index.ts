// ── Core Domain Types ──

export type OutputMode = 'comic' | 'manga' | 'storyboard' | 'trailer';
export type ScriptFormat = 'screenplay' | 'prose' | 'freeform';
export type ShotType = 'EWS' | 'WS' | 'FS' | 'MS' | 'MCU' | 'CU' | 'ECU' | 'OTS' | 'POV' | 'AERIAL';
export type CameraMove = 'static' | 'pan' | 'tilt' | 'dolly' | 'crane' | 'handheld' | 'steadicam' | 'zoom';
export type Transition = 'cut' | 'dissolve' | 'fade' | 'wipe' | 'smash_cut' | 'match_cut';
export type GridLayout = '2x2' | '3x2' | '2x3' | '3x3' | 'splash' | 'vertical_strip' | 'dynamic';
export type GenerationStatus = 'idle' | 'queued' | 'generating' | 'complete' | 'error';

// ── Director ──

export interface ColorPalette {
  primary: string;
  secondary: string;
  accent: string;
  shadow: string;
  highlight: string;
}

export interface DirectorStyle {
  id: string;
  name: string;
  tagline: string;
  palette: ColorPalette;
  filmography: string[];
  traits: string[];
  thumbnail_url: string;
}

// ── Script & Scene ──

export interface SceneBeat {
  id: string;
  scene_number: number;
  title: string;
  description: string;
  characters: string[];
  location: string;
  time_of_day: string;
  mood: string;
}

export interface Script {
  raw_text: string;
  format: ScriptFormat;
  scenes: SceneBeat[];
}

// ── Characters ──

export interface CharacterRef {
  id: string;
  name: string;
  description: string;
  ref_sheet_url: string | null;
  expressions: string[];
  thumbnail_url: string | null;
}

// ── Panels ──

export interface SpeechBubbleData {
  id: string;
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
  type: 'speech' | 'thought' | 'narration' | 'shout';
  tail_direction: 'left' | 'right' | 'top' | 'bottom';
}

export interface PanelData {
  id: string;
  scene_id: string;
  image_url: string | null;
  position: { row: number; col: number };
  span: { rows: number; cols: number };
  bubbles: SpeechBubbleData[];
  caption: string;
}

export interface PageData {
  id: string;
  page_number: number;
  layout: GridLayout;
  panels: PanelData[];
}

// ── Storyboard ──

export interface StoryboardFrameData {
  id: string;
  scene_id: string;
  frame_number: number;
  image_url: string | null;
  shot_type: ShotType;
  camera_move: CameraMove;
  transition: Transition;
  director_notes: string;
  duration_seconds: number;
  dialogue: string;
}

// ── Video ──

export interface SceneChapter {
  scene_id: string;
  title: string;
  start_time: number;
  end_time: number;
  thumbnail_url: string | null;
}

export interface ClipData {
  clip_id: string;
  scene_id: string;
  video_url: string;
  duration: number;
  status: string;
}

export interface VideoData {
  video_url: string | null;
  duration: number;
  chapters: SceneChapter[];
  clips?: ClipData[];
}

// ── Generation Progress ──

export interface SceneProgress {
  scene_id: string;
  status: GenerationStatus;
  progress: number; // 0-100
  thumbnail_url: string | null;
  message: string;
}

export interface GenerationState {
  project_id: string;
  overall_progress: number;
  scenes: SceneProgress[];
  current_phase: string;
}

// ── Project ──

export interface Project {
  id: string;
  title: string;
  status?: string;
  script: Script;
  director_style_id: string | null;
  output_mode: OutputMode;
  characters: CharacterRef[];
  pages: PageData[];
  storyboard_frames: StoryboardFrameData[];
  video: VideoData | null;
  created_at: string;
  updated_at: string;
}

// ── Chat Editor ──

export interface EditMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  before_url: string | null;
  after_url: string | null;
  timestamp: string;
}

// ── API Responses ──

export interface ApiResponse<T> {
  data: T;
  message: string;
  success: boolean;
}

export interface CreateProjectRequest {
  title: string;
  script: string;
  director_style?: string;
  output_mode: OutputMode;
}

export interface EditRequest {
  project_id: string;
  target_id: string;
  instruction: string;
}

// ── WebSocket Messages ──

export interface WsMessage {
  type: 'progress' | 'scene_complete' | 'generation_complete' | 'error';
  // Flat fields from backend progress_tracker.to_dict()
  project_id?: string;
  phase?: string;
  overall_progress_pct?: number;
  message?: string;
  elapsed_seconds?: number;
  scenes?: Record<string, {
    phase: string;
    progress_pct: number;
    message: string;
    error: string | null;
    thumbnail_url?: string;
  }>;
  error?: string;
  // Legacy payload format
  payload?: GenerationState | SceneProgress | { message: string };
}
