import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Film,
  FileText,
  Loader2,
  Trash2,
} from "lucide-react";
import { api } from "../api";
import { formatBytes, formatDuration, formatResolution } from "../format";

const STATUS_STYLES = {
  ready: "border-[#204a3a] bg-[#0f2019] text-[#6ee7b7]",
  failed: "border-[#5b2130] bg-[#2a121a] text-[#fda4af]",
  probing: "border-[#4a3d20] bg-[#231d0f] text-[#fcd34d]",
  uploaded: "border-[#2c2c36] bg-[#15151b] text-[#a1a1aa]",
};

const POLL_INTERVAL_MS = 2000;

function latestTranscribeJob(jobs) {
  return jobs.find((job) => job.kind === "transcribe") ?? null;
}

export default function VideoList({ videos, loading, onDelete }) {
  const [jobs, setJobs] = useState({});
  const [transcripts, setTranscripts] = useState({});
  const [openTranscript, setOpenTranscript] = useState(null);
  const [error, setError] = useState("");
  const pollTimer = useRef(null);

  const refreshJobs = useCallback(async (videoIds) => {
    const results = await Promise.allSettled(videoIds.map((id) => api.listVideoJobs(id)));
    setJobs((current) => {
      const next = { ...current };
      results.forEach((result, index) => {
        if (result.status === "fulfilled") next[videoIds[index]] = result.value;
      });
      return next;
    });
  }, []);

  useEffect(() => {
    if (videos.length > 0) refreshJobs(videos.map((video) => video.id));
  }, [videos, refreshJobs]);

  // Poll only while at least one transcription job is still active.
  useEffect(() => {
    const activeIds = videos
      .filter((video) => {
        const job = latestTranscribeJob(jobs[video.id] ?? []);
        return job && (job.status === "queued" || job.status === "running");
      })
      .map((video) => video.id);

    if (activeIds.length === 0) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
      return;
    }

    pollTimer.current = setInterval(() => refreshJobs(activeIds), POLL_INTERVAL_MS);
    return () => {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    };
  }, [videos, jobs, refreshJobs]);

  async function handleTranscribe(videoId) {
    setError("");
    try {
      await api.startTranscription(videoId);
      await refreshJobs([videoId]);
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleTranscript(videoId) {
    if (openTranscript === videoId) {
      setOpenTranscript(null);
      return;
    }
    setOpenTranscript(videoId);
    if (transcripts[videoId] !== undefined) return;

    try {
      const transcript = await api.getTranscript(videoId);
      setTranscripts((current) => ({ ...current, [videoId]: transcript }));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="mt-8">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Recent videos</h3>
        <span className="text-[10px] text-[#71717a]">{videos.length} file</span>
      </div>

      {error && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-[#5b2130] bg-[#2a121a] px-3 py-2 text-[11px] text-[#fda4af]">
          <AlertCircle size={14} className="mt-[1px] shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading && <p className="text-[11px] text-[#71717a]">Memuat…</p>}
      {!loading && videos.length === 0 && (
        <p className="rounded-xl border border-[#25252d] bg-[#111115] px-4 py-6 text-center text-[11px] text-[#71717a]">
          Belum ada video. Unggah file pertama Anda di atas.
        </p>
      )}

      <div className="flex flex-col gap-2">
        {videos.map((video) => {
          const job = latestTranscribeJob(jobs[video.id] ?? []);
          const running = job && (job.status === "queued" || job.status === "running");
          const transcript = transcripts[video.id];
          const canViewTranscript = Boolean(transcript) || job?.status === "succeeded";
          const isOpen = openTranscript === video.id;

          return (
            <article
              key={video.id}
              className="rounded-xl border border-[#25252d] bg-[#111115] px-4 py-3"
            >
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#1c1728] text-[#a78bfa]">
                  <Film size={16} />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12px] text-[#e4e4e7]">{video.original_filename}</div>
                  <div className="mt-0.5 flex flex-wrap gap-x-3 text-[10px] text-[#8b8b95]">
                    <span>{formatDuration(video.duration_sec)}</span>
                    <span>{formatResolution(video.width, video.height)}</span>
                    <span>{video.fps ? `${video.fps.toFixed(1)} fps` : "—"}</span>
                    <span>{video.video_codec || "—"}</span>
                    <span>{formatBytes(video.size_bytes)}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {!canViewTranscript && (
                    <button
                      type="button"
                      onClick={() => handleTranscribe(video.id)}
                      disabled={Boolean(running) || !video.audio_codec}
                      title={video.audio_codec ? "Jalankan transkripsi lokal" : "Video tanpa audio"}
                      className="flex items-center gap-1.5 rounded-lg border border-[#2c2c36] bg-[#17171d] px-2.5 py-1.5 text-[10px] font-semibold text-[#c4b5fd] disabled:opacity-50"
                    >
                      {running ? <Loader2 size={12} className="animate-spin" /> : <FileText size={12} />}
                      {running ? `${job.progress}%` : "Transkrip"}
                    </button>
                  )}

                  {canViewTranscript && (
                    <button
                      type="button"
                      onClick={() => toggleTranscript(video.id)}
                      className="flex items-center gap-1.5 rounded-lg border border-[#2c2c36] bg-[#17171d] px-2.5 py-1.5 text-[10px] font-semibold text-[#c4b5fd]"
                    >
                      <FileText size={12} />
                      Transkrip
                      {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    </button>
                  )}

                  <span
                    className={`rounded-md border px-2 py-0.5 text-[9px] uppercase tracking-[0.8px] ${
                      STATUS_STYLES[video.status] || STATUS_STYLES.uploaded
                    }`}
                  >
                    {video.status}
                  </span>

                  {onDelete && (
                    <button
                      type="button"
                      onClick={() => onDelete(video)}
                      title="Hapus video"
                      aria-label={`Hapus ${video.original_filename}`}
                      className="rounded-lg border border-[#5b2130] bg-[#2a121a] p-1.5 text-[#fda4af] hover:bg-[#34151f]"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              </div>

              {running && (
                <div className="mt-2.5">
                  <div className="h-1 w-full overflow-hidden rounded-full bg-[#26262f]">
                    <div
                      className="h-full rounded-full bg-[#8b5cf6] transition-[width] duration-300"
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                  <div className="mt-1 text-[9px] uppercase tracking-[0.8px] text-[#71717a]">
                    {job.status === "queued" ? "Menunggu worker…" : "Memproses transkripsi…"}
                  </div>
                </div>
              )}

              {job?.status === "failed" && (
                <div className="mt-2 flex items-start gap-2 rounded-lg border border-[#5b2130] bg-[#2a121a] px-2.5 py-1.5 text-[10px] text-[#fda4af]">
                  <AlertCircle size={12} className="mt-[1px] shrink-0" />
                  <span>{job.error || "Transkripsi gagal"}</span>
                </div>
              )}

              {isOpen && (
                <div className="mt-3 rounded-lg border border-[#25252d] bg-[#0d0d12] p-3">
                  {transcript === undefined && (
                    <div className="flex items-center gap-2 text-[10px] text-[#71717a]">
                      <Loader2 size={12} className="animate-spin" /> Memuat transkrip…
                    </div>
                  )}
                  {transcript === null && (
                    <div className="text-[10px] text-[#71717a]">Transkrip belum tersedia.</div>
                  )}
                  {transcript && (
                    <>
                      <div className="mb-2 flex flex-wrap gap-x-3 text-[9px] uppercase tracking-[0.8px] text-[#71717a]">
                        <span>lang: {transcript.language || "—"}</span>
                        <span>model: {transcript.model_name}</span>
                        <span>{transcript.segments.length} segmen</span>
                      </div>
                      <div className="max-h-64 space-y-1.5 overflow-y-auto pr-1">
                        {transcript.segments.map((segment, index) => (
                          <div key={`${segment.start}-${index}`} className="flex gap-2 text-[11px]">
                            <span className="shrink-0 font-mono text-[10px] text-[#7c7c88]">
                              {formatDuration(segment.start)}
                            </span>
                            <span className="text-[#d4d4d8]">{segment.text}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
