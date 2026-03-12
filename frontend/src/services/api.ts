import type {
  ApiResponse,
  CreateProjectRequest,
  DirectorStyle,
  EditMessage,
  EditRequest,
  Project,
  CharacterRef,
  PageData,
  StoryboardFrameData,
  VideoData,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  if (!res.ok) {
    let message = 'Unknown error';
    try {
      const body = await res.json();
      message = body.detail || body.message || JSON.stringify(body);
    } catch {
      message = await res.text().catch(() => 'Unknown error');
    }
    throw new ApiError(res.status, message);
  }

  return res.json() as Promise<T>;
}

// ── Directors ──

export async function fetchDirectors(): Promise<DirectorStyle[]> {
  const res = await request<ApiResponse<DirectorStyle[]>>('/directors/');
  return res.data;
}

// ── Projects ──

export async function listProjects(): Promise<Project[]> {
  const res = await request<ApiResponse<Project[]>>('/projects/');
  return res.data;
}

export async function deleteProject(projectId: string): Promise<void> {
  await request<ApiResponse<unknown>>(`/projects/${projectId}`, { method: 'DELETE' });
}

export async function createProject(req: CreateProjectRequest): Promise<Project> {
  const res = await request<ApiResponse<Project>>('/projects/', {
    method: 'POST',
    body: JSON.stringify(req),
  });
  return res.data;
}

export async function fetchProject(projectId: string): Promise<Project> {
  const res = await request<ApiResponse<Project>>(`/projects/${projectId}`);
  return res.data;
}

export async function analyzeScript(projectId: string): Promise<Project> {
  const res = await request<ApiResponse<Project>>(`/projects/${projectId}/analyze`, {
    method: 'POST',
  });
  return res.data;
}

// ── Generation ──

export async function generatePanels(projectId: string): Promise<PageData[]> {
  const res = await request<ApiResponse<PageData[]>>(`/projects/${projectId}/generate/panels`, {
    method: 'POST',
  });
  return res.data;
}

export async function generateStoryboard(projectId: string): Promise<StoryboardFrameData[]> {
  const res = await request<ApiResponse<StoryboardFrameData[]>>(
    `/projects/${projectId}/generate/storyboard`,
    { method: 'POST' },
  );
  return res.data;
}

export async function generateTrailer(projectId: string): Promise<VideoData> {
  // Trigger trailer generation (returns immediately, runs in background)
  await request<ApiResponse<VideoData>>(`/projects/${projectId}/generate/trailer`, {
    method: 'POST',
  });

  // Poll for completion — check project status every 10s
  const maxWait = 20 * 60 * 1000; // 20 min max
  const pollInterval = 10_000;
  const start = Date.now();

  while (Date.now() - start < maxWait) {
    await new Promise(r => setTimeout(r, pollInterval));
    const project = await fetchProject(projectId);
    // Return video when available (full trailer or partial clips assembled)
    if (project.video?.video_url) {
      return project.video;
    }
    // If generation is complete but no video URL, return whatever we have
    if (project.status === 'complete' && project.video) {
      return project.video;
    }
    if (project.status === 'failed') {
      // Re-fetch to see if partial clips exist
      const updated = await fetchProject(projectId);
      if (updated.video?.video_url) return updated.video;
      throw new Error('Trailer generation failed');
    }
  }
  // On timeout, return whatever partial results exist
  const final = await fetchProject(projectId);
  if (final.video) return final.video;
  throw new Error('Trailer generation timed out');
}

// ── Characters ──

export async function fetchCharacters(projectId: string): Promise<CharacterRef[]> {
  const res = await request<ApiResponse<CharacterRef[]>>(`/projects/${projectId}/characters`);
  return res.data;
}

export async function editCharacter(
  projectId: string,
  characterId: string,
  instruction: string,
): Promise<CharacterRef> {
  const res = await request<ApiResponse<CharacterRef>>(
    `/projects/${projectId}/characters/${characterId}/edit`,
    { method: 'POST', body: JSON.stringify({ instruction }) },
  );
  return res.data;
}

// ── Chat Editor ──

export async function sendEdit(req: EditRequest): Promise<EditMessage> {
  const res = await request<ApiResponse<EditMessage>>(`/projects/${req.project_id}/edit`, {
    method: 'POST',
    body: JSON.stringify(req),
  });
  return res.data;
}

// ── Story Chat ──

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  reply: string;
  script: string | null;
}

export async function chatStory(
  messages: ChatMessage[],
  userMessage: string,
): Promise<ChatResponse> {
  const res = await request<ApiResponse<ChatResponse>>('/chat/story', {
    method: 'POST',
    body: JSON.stringify({ messages, user_message: userMessage }),
  });
  return res.data;
}

// ── Auto-save ──

export async function patchProject(projectId: string, updates: Record<string, unknown>): Promise<Project> {
  const res = await request<ApiResponse<Project>>(`/projects/${projectId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
  return res.data;
}

export { ApiError };
