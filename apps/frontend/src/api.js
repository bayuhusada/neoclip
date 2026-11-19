const JSON_HEADERS = { "Content-Type": "application/json" };

async function parseError(response) {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (body?.detail) return JSON.stringify(body.detail);
  } catch {
    // fall through to the generic message
  }
  return `Request failed (${response.status})`;
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(await parseError(response));
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  health: () => request("/api/health"),

  listProjects: () => request("/api/projects"),
  createProject: (payload) =>
    request("/api/projects", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
  updateProject: (projectId, payload) =>
    request(`/api/projects/${projectId}`, {
      method: "PATCH",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
  deleteProject: (projectId) =>
    request(`/api/projects/${projectId}`, { method: "DELETE" }),

  config: () => request("/api/config"),

  getAiSettings: () => request("/api/settings/ai"),
  saveAiSettings: (payload) =>
    request("/api/settings/ai", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
  testAiConnection: (payload) =>
    request("/api/settings/ai/test", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload ?? {}),
    }),
  testAiChat: (payload) =>
    request("/api/settings/ai/test", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ ...(payload ?? {}), deep: true }),
    }),
  checkAiQuota: (payload) =>
    request("/api/settings/ai/quota", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload ?? {}),
    }),

  listVideos: (projectId) =>
    request(projectId ? `/api/videos?project_id=${encodeURIComponent(projectId)}` : "/api/videos"),

  getVideo: (videoId) => request(`/api/videos/${videoId}`),
  deleteVideo: (videoId) => request(`/api/videos/${videoId}`, { method: "DELETE" }),

  startTranscription: (videoId, { force = false } = {}) =>
    request(`/api/videos/${videoId}/transcribe${force ? "?force=true" : ""}`, {
      method: "POST",
    }),

  listVideoJobs: (videoId) => request(`/api/videos/${videoId}/jobs`),

  startAnalysis: (videoId) =>
    request(`/api/videos/${videoId}/analyze`, { method: "POST" }),
  listClips: (videoId) => request(`/api/videos/${videoId}/clips`),
  updateClip: (clipId, payload) =>
    request(`/api/clips/${clipId}`, {
      method: "PATCH",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
  deleteClip: (clipId) => request(`/api/clips/${clipId}`, { method: "DELETE" }),
  renderClip: (clipId) => request(`/api/clips/${clipId}/render`, { method: "POST" }),
  getClipVideoUrl: (clipId) => `/api/clips/${clipId}/video`,
  getClipThumbnailUrl: (clipId) => `/api/clips/${clipId}/thumbnail`,

  getClipFraming: (clipId) => request(`/api/clips/${clipId}/framing`),
  updateClipFraming: (clipId, payload) =>
    request(`/api/clips/${clipId}/framing`, {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
  regenerateClipFraming: (clipId) =>
    request(`/api/clips/${clipId}/framing/regenerate`, { method: "POST" }),

  /** Returns null when the video has no transcript yet (API answers 404). */
  getTranscript: async (videoId) => {
    try {
      return await request(`/api/videos/${videoId}/transcript`);
    } catch (error) {
      if (/No transcript/i.test(error.message)) return null;
      throw error;
    }
  },

  /** XHR is used instead of fetch because only XHR reports upload progress. */
  uploadVideo: ({ projectId, file, youtubeUrl, onProgress }) =>
    new Promise((resolve, reject) => {
      const form = new FormData();
      form.append("project_id", String(projectId));
      form.append("file", file);
      if (youtubeUrl) form.append("youtube_url", youtubeUrl);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/videos");
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable || !onProgress) return;
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            reject(new Error("Server returned an unreadable response"));
          }
          return;
        }
        let message = `Upload failed (${xhr.status})`;
        try {
          const body = JSON.parse(xhr.responseText);
          if (typeof body?.detail === "string") message = body.detail;
        } catch {
          // keep the generic message
        }
        reject(new Error(message));
      };
      xhr.onerror = () => reject(new Error("Network error while uploading"));
      xhr.ontimeout = () => reject(new Error("Upload timed out"));
      xhr.send(form);
    }),
  updateVideo: (videoId, payload) =>
    request(`/api/videos/${videoId}`, {
      method: "PATCH",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
};
