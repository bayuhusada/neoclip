import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  Download,
  Film,
  Loader2,
  Play,
  RefreshCw,
  Scissors,
  Sparkles,
  Trash2,
  Undo2,
  Wand2,
} from "lucide-react";
import { api } from "../api";
import Eyebrow from "../components/Eyebrow";

const CARD = "rounded-xl border border-[#25252d] bg-[#111115] p-4";
const INPUT =
  "w-full rounded-lg border border-[#2c2c36] bg-[#0d0d12] px-2.5 py-1.5 text-[11px] text-[#e4e4e7] outline-none placeholder:text-[#52525b] focus:border-[#7c3aed]";

const CAPTION_PRESETS = [
  { value: "modern_bold", label: "Modern Bold" },
  { value: "karaoke", label: "Karaoke" },
  { value: "minimal", label: "Minimal" },
  { value: "podcast", label: "Podcast" },
  { value: "hormozi", label: "Hormozi" },
  { value: "classic", label: "Classic" },
  { value: "anton", label: "Anton (headline)" },
  { value: "pill", label: "Pill (kotak ungu)" },
  { value: "oneword", label: "One Word" },
];

const CAMERA_MODES = [
  { value: "smart_auto", label: "Otomatis Cerdas (rekomendasi)" },
  { value: "original", label: "Original (crop tengah)" },
  { value: "single", label: "Fokus 1 orang" },
  { value: "split", label: "Split screen 2 orang" },
  { value: "split_stacked", label: "Split atas-bawah 2 orang" },
  { value: "group", label: "Tampilkan semua wajah" },
  { value: "auto_speaker", label: "Ikuti wajah dominan" },
  { value: "dynamic_zoom", label: "Dynamic zoom" },
];

const RESOLVED_MODE_LABEL = {
  original: "Original",
  single: "Fokus 1 orang",
  split: "Split screen",
  split_stacked: "Split atas-bawah",
  group: "Group (semua wajah)",
};

function formatTime(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

function scoreLabel(score) {
  if (score === null || score === undefined) return "—";
  return `${Math.round(score * 100)}%`;
}

function ClipCard({ clip, busy, onSave, onApprove, onDelete, onRender, onDownload }) {
  const [form, setForm] = useState({
    title: clip.title,
    hook: clip.hook ?? "",
    start_sec: String(clip.start_sec),
    end_sec: String(clip.end_sec),
    template: clip.template ?? "clean",
    caption_preset: clip.caption_preset ?? "modern_bold",
    caption_size: clip.caption_size ?? 1.0,
    camera_mode: clip.camera_mode ?? "smart_auto",
    hook_enabled: Boolean(clip.hook_enabled),
    hook_duration: String(clip.hook_duration ?? 3),
  });
  const [dirty, setDirty] = useState(false);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    setForm({
      title: clip.title,
      hook: clip.hook ?? "",
      start_sec: String(clip.start_sec),
      end_sec: String(clip.end_sec),
      template: clip.template ?? "clean",
      caption_preset: clip.caption_preset ?? "modern_bold",
      caption_size: clip.caption_size ?? 1.0,
      camera_mode: clip.camera_mode ?? "smart_auto",
      hook_enabled: Boolean(clip.hook_enabled),
      hook_duration: String(clip.hook_duration ?? 3),
    });
    setDirty(false);
    setPlaying(false);
  }, [clip]);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setDirty(true);
  }

  const approved = clip.status === "approved";
  const rendered = clip.status === "rendered";
  const thumbUrl = api.getClipThumbnailUrl(clip.id);
  const videoUrl = rendered ? api.getClipVideoUrl(clip.id) : null;

  return (
    <div className={CARD}>
      <div className="flex gap-3 max-sm:flex-col">
        <div className="relative h-32 w-20 shrink-0 overflow-hidden rounded-lg bg-[#000] max-sm:h-40 max-sm:w-full">
          {playing && videoUrl ? (
            <video
              src={videoUrl}
              controls
              autoPlay
              className="h-full w-full object-cover"
              onEnded={() => setPlaying(false)}
            />
          ) : (
            <>
              <img
                src={thumbUrl}
                alt="Preview"
                className="h-full w-full object-cover"
                onError={(e) => {
                  e.target.style.display = "none";
                }}
              />
              <button
                type="button"
                disabled={!rendered}
                onClick={() => setPlaying(true)}
                className="absolute inset-0 grid place-items-center bg-[#00000055] hover:bg-[#00000033] disabled:opacity-40"
              >
                <div className="grid h-8 w-8 place-items-center rounded-full bg-[#7c3aed] text-white">
                  <Play size={14} className="ml-0.5" />
                </div>
              </button>
            </>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                rendered
                  ? "border-[#1e3a8a] bg-[#172554] text-[#93c5fd]"
                  : approved
                  ? "border-[#14532d] bg-[#0d2a1a] text-[#6ee7b7]"
                  : "border-[#4a3d20] bg-[#231d0f] text-[#fcd34d]"
              }`}
            >
              {rendered ? "Dirender" : approved ? "Disetujui" : "Kandidat"}
            </span>
            <span className="text-[10px] text-[#8b8b95]">
              {formatTime(clip.start_sec)} – {formatTime(clip.end_sec)} ·{" "}
              {Math.round(clip.end_sec - clip.start_sec)}s · skor {scoreLabel(clip.score)}
            </span>
          </div>

          {clip.framing_mode && (
            <div className="mb-2 inline-flex items-center gap-1 rounded-md border border-[#1e3a8a] bg-[#172554] px-2 py-0.5 text-[9px] text-[#93c5fd]">
              Kamera: {RESOLVED_MODE_LABEL[clip.framing_mode] ?? clip.framing_mode}
            </div>
          )}

          {clip.caption_source === "estimated" && (
            <div className="mb-2 flex items-center gap-1.5 rounded-md border border-[#4a3d20] bg-[#231d0f] px-2 py-1 text-[9px] text-[#fcd34d]">
              <AlertCircle size={11} className="shrink-0" />
              Timing caption diperkirakan (transkrip lama). Jalankan “Transkripsi ulang” untuk
              akurasi kata.
            </div>
          )}

          <input
            className={INPUT}
            value={form.title}
            onChange={(event) => update("title", event.target.value)}
            aria-label="Judul klip"
          />
          <input
            className={`${INPUT} mt-2`}
            value={form.hook}
            onChange={(event) => update("hook", event.target.value)}
            placeholder="Hook / kalimat pembuka"
            aria-label="Hook klip"
          />

          <div className="mt-2 flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-1.5 text-[10px] text-[#a1a1aa]">
              <input
                type="checkbox"
                checked={form.hook_enabled}
                onChange={(event) => update("hook_enabled", event.target.checked)}
                className="accent-[#7c3aed]"
              />
              Tampilkan hook di video
            </label>
            {form.hook_enabled && (
              <label className="flex items-center gap-1.5 text-[10px] text-[#a1a1aa]">
                Durasi
                <input
                  className={`${INPUT} w-16`}
                  value={form.hook_duration}
                  onChange={(event) => update("hook_duration", event.target.value)}
                  inputMode="decimal"
                />
                detik
              </label>
            )}
          </div>

          <div className="mt-2 grid grid-cols-2 gap-2 max-sm:grid-cols-1">
            <label className="block">
              <span className="mb-1 block text-[9px] uppercase tracking-wide text-[#71717a]">
                Mulai (detik)
              </span>
              <input
                className={INPUT}
                value={form.start_sec}
                onChange={(event) => update("start_sec", event.target.value)}
                inputMode="decimal"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[9px] uppercase tracking-wide text-[#71717a]">
                Selesai (detik)
              </span>
              <input
                className={INPUT}
                value={form.end_sec}
                onChange={(event) => update("end_sec", event.target.value)}
                inputMode="decimal"
              />
            </label>
          </div>

          <div className="mt-2 grid grid-cols-3 gap-2 max-sm:grid-cols-1">
            <label className="block">
              <span className="mb-1 block text-[9px] uppercase tracking-wide text-[#71717a]">
                Background Style
              </span>
              <select
                className={INPUT}
                value={form.template}
                onChange={(event) => update("template", event.target.value)}
              >
                <option value="clean">Clean (Center Crop)</option>
                <option value="bold">Bold (SubT Tebal)</option>
                <option value="blur">Blur (Background Blur)</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[9px] uppercase tracking-wide text-[#71717a]">
                Caption Style
              </span>
              <select
                className={INPUT}
                value={form.caption_preset}
                onChange={(event) => update("caption_preset", event.target.value)}
              >
                {CAPTION_PRESETS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-[9px] uppercase tracking-wide text-[#71717a]">
                  Ukuran Teks
                </span>
                <span className="text-[10px] text-[#a1a1aa]">
                  {Math.round(Number(form.caption_size || 1.0) * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0.6"
                max="1.8"
                step="0.1"
                value={form.caption_size || 1.0}
                onChange={(event) => update("caption_size", Number(event.target.value))}
                className="w-full accent-[#3b82f6]"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[9px] uppercase tracking-wide text-[#71717a]">
                Camera Mode
              </span>
              <select
                className={INPUT}
                value={form.camera_mode}
                onChange={(event) => update("camera_mode", event.target.value)}
              >
                {CAMERA_MODES.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </div>

      {clip.rationale && (
        <p className="mt-2 text-[10px] leading-relaxed text-[#8b8b95]">{clip.rationale}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={!dirty || busy}
          onClick={() =>
            onSave(clip.id, {
              title: form.title.trim(),
              hook: form.hook.trim(),
              start_sec: Number(form.start_sec),
              end_sec: Number(form.end_sec),
              template: form.template,
              caption_preset: form.caption_preset,
              caption_size: Number(form.caption_size),
              camera_mode: form.camera_mode,
              hook_enabled: Boolean(form.hook_enabled),
              hook_duration: Number(form.hook_duration) || 3,
            })
          }
          className="flex items-center gap-1.5 rounded-lg border border-[#2c2c36] bg-[#17171d] px-2.5 py-1.5 text-[11px] font-semibold text-[#d4d4d8] hover:bg-[#1d1d24] disabled:opacity-40"
        >
          <Check size={12} /> Simpan
        </button>

        <button
          type="button"
          disabled={busy}
          onClick={() => onApprove(clip, approved ? "candidate" : "approved")}
          className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold disabled:opacity-40 ${
            approved
              ? "border-[#2c2c36] bg-[#17171d] text-[#d4d4d8] hover:bg-[#1d1d24]"
              : "border-[#7c3aed] bg-[#3b1d63] text-[#ddd6fe] hover:bg-[#4a2479]"
          }`}
        >
          {approved ? <Undo2 size={12} /> : <Check size={12} />}
          {approved ? "Batalkan" : "Setujui"}
        </button>

        <button
          type="button"
          disabled={(!approved && !rendered) || busy}
          onClick={() => onRender(clip)}
          className="flex items-center gap-1.5 rounded-lg border border-[#7c3aed] bg-[#3b1d63] px-2.5 py-1.5 text-[11px] font-semibold text-[#ddd6fe] hover:bg-[#4a2479] disabled:opacity-40"
        >
          {rendered ? <RefreshCw size={12} /> : <Film size={12} />}
          {rendered ? "Render Ulang" : "Render 9:16"}
        </button>

        {rendered && (
          <button
            type="button"
            onClick={() => onDownload(clip.id)}
            className="flex items-center gap-1.5 rounded-lg border border-[#14532d] bg-[#0d2a1a] px-2.5 py-1.5 text-[11px] font-semibold text-[#6ee7b7] hover:bg-[#123823]"
          >
            <Download size={12} /> Download MP4
          </button>
        )}

        <button
          type="button"
          disabled={busy}
          onClick={() => onDelete(clip)}
          className="ml-auto flex items-center gap-1.5 rounded-lg border border-[#4a2028] bg-[#201013] px-2.5 py-1.5 text-[11px] font-semibold text-[#fda4af] hover:bg-[#2a151a] disabled:opacity-40"
        >
          <Trash2 size={12} /> Hapus
        </button>
      </div>
    </div>
  );
}

export default function EditorView({ videos, onNavigate }) {
  const [videoId, setVideoId] = useState(null);
  const [clips, setClips] = useState([]);
  const [hasTranscript, setHasTranscript] = useState(false);
  const [aiConfigured, setAiConfigured] = useState(null);
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (videoId === null && videos.length > 0) setVideoId(videos[0].id);
  }, [videos, videoId]);

  useEffect(() => {
    api
      .getAiSettings()
      .then((data) => setAiConfigured(Boolean(data.configured)))
      .catch(() => setAiConfigured(false));
  }, []);

  const loadVideoData = useCallback(
    async (id) => {
      setLoading(true);
      setError("");
      try {
        const [transcript, nextClips] = await Promise.all([api.getTranscript(id), api.listClips(id)]);
        setHasTranscript(Boolean(transcript));
        setClips(nextClips);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (videoId === null) return;
    setJob(null);
    loadVideoData(videoId);
  }, [videoId, loadVideoData]);

  useEffect(() => {
    if (!job || !videoId || (job.status !== "queued" && job.status !== "running")) return undefined;

    const timer = setInterval(async () => {
      try {
        const jobs = await api.listVideoJobs(videoId);
        const current = jobs.find((item) => item.id === job.id);
        if (!current) return;
        setJob(current);
        if (current.status === "succeeded") {
          clearInterval(timer);
          setNotice(
            current.kind === "render"
              ? "Render selesai. Klip siap diputar & diunduh."
              : "Analisis selesai. Periksa kandidat klip di bawah."
          );
          await loadVideoData(videoId);
        } else if (current.status === "failed") {
          clearInterval(timer);
          setError(current.error || "Proses gagal.");
        }
      } catch {
        // keep polling
      }
    }, 2000);

    return () => clearInterval(timer);
  }, [job, videoId, loadVideoData]);

  async function retranscribeVideo() {
    if (!videoId) return;
    setBusy("transcribe");
    setError("");
    setNotice("");
    try {
      const result = await api.startTranscription(videoId, { force: true });
      setJob({ id: result.job_id, status: "queued", progress: 0, kind: "transcribe" });
      setNotice("Transkripsi ulang diajukan. Menyimpan timestamp per kata…");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function startAnalysis() {
    if (!videoId) return;
    setBusy("analyze");
    setError("");
    setNotice("");
    try {
      const result = await api.startAnalysis(videoId);
      setJob({ id: result.job_id, status: "queued", progress: 0, kind: "analyze" });
      await loadVideoData(videoId);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function renderClip(clip) {
    setBusy(`render-${clip.id}`);
    setError("");
    setNotice("");
    try {
      const result = await api.renderClip(clip.id);
      setJob({ id: result.job_id, status: "queued", progress: 0, kind: "render" });
      setNotice("Render antre. FFmpeg sedang memproses video...");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  function downloadClip(clipId) {
    const url = api.getClipVideoUrl(clipId);
    window.open(url, "_blank");
  }

  async function saveClip(clipId, payload) {
    setBusy(`clip-${clipId}`);
    setError("");
    try {
      const updated = await api.updateClip(clipId, payload);
      setClips((current) => current.map((clip) => (clip.id === clipId ? updated : clip)));
      setNotice("Perubahan klip disimpan.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function setClipStatus(clip, status) {
    setBusy(`clip-${clip.id}`);
    setError("");
    try {
      const updated = await api.updateClip(clip.id, { status });
      setClips((current) => current.map((item) => (item.id === clip.id ? updated : item)));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function deleteClip(clip) {
    setBusy(`clip-${clip.id}`);
    setError("");
    try {
      await api.deleteClip(clip.id);
      setClips((current) => current.filter((item) => item.id !== clip.id));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  const activeVideo = videos.find((video) => video.id === videoId) ?? null;
  const running = job && (job.status === "queued" || job.status === "running");
  const approvedCount = clips.filter((clip) => clip.status === "approved" || clip.status === "rendered").length;

  return (
    <section>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Eyebrow>Workspace</Eyebrow>
          <h2 className="mt-1.5 text-[22px] font-semibold">AI Clip Editor</h2>
          <p className="mt-1 text-[12px] text-[#8b8b95]">
            Minta 9Router memilih momen terbaik, pilih template style, lalu render 9:16 + subtitle.
          </p>
        </div>
        <span
          className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[1px] ${
            aiConfigured
              ? "border-[#14532d] bg-[#0d2a1a] text-[#6ee7b7]"
              : "border-[#4a3d20] bg-[#231d0f] text-[#fcd34d]"
          }`}
        >
          {aiConfigured === null ? "AI: cek…" : aiConfigured ? "AI siap" : "AI belum diatur"}
        </span>
      </div>

      {aiConfigured === false && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#4a3d20] bg-[#231d0f] px-3 py-2 text-[11px] text-[#fcd34d]">
          <span className="flex items-center gap-2">
            <AlertCircle size={14} /> API key / model belum diisi. Analisis AI tidak bisa jalan.
          </span>
          <button
            type="button"
            onClick={() => onNavigate?.("settings")}
            className="rounded-lg border border-[#6b5a27] px-2 py-1 text-[10px] font-semibold hover:bg-[#2b2413]"
          >
            Buka Settings
          </button>
        </div>
      )}

      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-[#5b2130] bg-[#2a121a] px-3 py-2 text-[11px] text-[#fda4af]">
          <AlertCircle size={14} className="mt-[1px] shrink-0" />
          {error}
        </div>
      )}

      {notice && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-[#14532d] bg-[#0d2a1a] px-3 py-2 text-[11px] text-[#6ee7b7]">
          <Check size={14} className="mt-[1px] shrink-0" />
          {notice}
        </div>
      )}

      {videos.length === 0 ? (
        <div className="rounded-2xl border border-[#393047] bg-[linear-gradient(120deg,#17131f,#111115_60%,#1b1526)] px-6 py-10 text-center">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl border border-[#4c3b66] bg-[#241d32] text-[#c4b5fd]">
            <Sparkles size={28} />
          </div>
          <h3 className="mt-4 text-[18px] font-semibold">Belum ada video</h3>
          <p className="mx-auto mt-1.5 max-w-md text-[12px] leading-relaxed text-[#a1a1aa]">
            Unggah video dan jalankan transkripsi dulu di Dashboard.
          </p>
          <button
            type="button"
            onClick={() => onNavigate?.("dashboard")}
            className="mx-auto mt-5 flex items-center gap-1.5 rounded-lg bg-[#7c3aed] px-3.5 py-2 text-[12px] font-semibold text-white"
          >
            Ke Dashboard
          </button>
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-[300px_1fr]">
          <div className={CARD}>
            <div className="mb-2 flex items-center gap-2 text-[#a78bfa]">
              <Film size={15} />
              <h3 className="text-[12px] font-semibold text-[#e4e4e7]">Pilih video</h3>
            </div>
            <select
              className={INPUT}
              value={videoId ?? ""}
              onChange={(event) => setVideoId(Number(event.target.value))}
            >
              {videos.map((video) => (
                <option key={video.id} value={video.id}>
                  {video.original_filename}
                </option>
              ))}
            </select>

            <div className="mt-2 space-y-1 text-[10px] text-[#8b8b95]">
              <p>
                Durasi: <span className="text-[#e4e4e7]">{formatTime(activeVideo?.duration_sec)}</span>
              </p>
              <p>
                Transkrip:{" "}
                <span className={hasTranscript ? "text-[#6ee7b7]" : "text-[#fda4af]"}>
                  {loading ? "memeriksa…" : hasTranscript ? "tersedia" : "belum ada"}
                </span>
              </p>
              <p>
                Kandidat: <span className="text-[#e4e4e7]">{clips.length}</span> · siap/render{" "}
                <span className="text-[#e4e4e7]">{approvedCount}</span>
              </p>
            </div>

            <button
              type="button"
              disabled={!hasTranscript || !aiConfigured || running || busy === "analyze"}
              onClick={startAnalysis}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg bg-[#7c3aed] px-3 py-2 text-[11px] font-semibold text-white disabled:opacity-40"
            >
              {running && job?.kind === "analyze" ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Wand2 size={13} />
              )}
              {running && job?.kind === "analyze"
                ? "Menganalisis…"
                : clips.length
                ? "Analisis ulang"
                : "Analisis AI"}
            </button>

            {!hasTranscript && (
              <p className="mt-2 text-[10px] leading-relaxed text-[#71717a]">
                Jalankan transkripsi dulu di Dashboard atau daftar video, lalu kembali ke sini.
              </p>
            )}

            {running && (
              <div className="mt-3">
                <div className="h-1.5 overflow-hidden rounded-full bg-[#1f1f27]">
                  <div
                    className="h-full rounded-full bg-[#7c3aed] transition-all"
                    style={{ width: `${job.progress || 5}%` }}
                  />
                </div>
                <p className="mt-1 text-[10px] text-[#8b8b95]">
                  {job.kind === "render"
                    ? `Rendering 9:16 + Subtitle (${job.progress}%)`
                    : `Mengirim transkrip ke 9Router (${job.progress}%)`}
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={() => videoId && loadVideoData(videoId)}
              disabled={loading}
              className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-[#2c2c36] bg-[#17171d] px-3 py-1.5 text-[11px] font-semibold text-[#d4d4d8] hover:bg-[#1d1d24] disabled:opacity-50"
            >
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Muat ulang
            </button>

            <button
              type="button"
              onClick={retranscribeVideo}
              disabled={!videoId || running || busy === "transcribe"}
              className="mt-1.5 flex w-full items-center justify-center gap-1.5 rounded-lg border border-[#4a3d20] bg-[#231d0f] px-3 py-1.5 text-[11px] font-semibold text-[#fcd34d] hover:bg-[#2b2413] disabled:opacity-50"
            >
              {running && job?.kind === "transcribe" ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Sparkles size={12} />
              )}
              Transkripsi Ulang (Word Timings)
            </button>
          </div>

          <div>
            {clips.length === 0 ? (
              <div className={`${CARD} flex min-h-[220px] flex-col items-center justify-center text-center`}>
                <div className="mb-3 grid h-12 w-12 place-items-center rounded-xl border border-[#4c3b66] bg-[#241d32] text-[#c4b5fd]">
                  <Scissors size={22} />
                </div>
                <h3 className="text-[13px] font-semibold">Belum ada kandidat klip</h3>
                <p className="mt-1 max-w-sm text-[11px] leading-relaxed text-[#8b8b95]">
                  Klik “Analisis AI” untuk meminta 9Router memilih 3-6 momen terbaik dari transkrip
                  video ini.
                </p>
              </div>
            ) : (
              <div className="grid gap-3">
                {clips.map((clip) => (
                  <ClipCard
                    key={clip.id}
                    clip={clip}
                    busy={busy === `clip-${clip.id}` || busy === `render-${clip.id}`}
                    onSave={saveClip}
                    onApprove={setClipStatus}
                    onDelete={deleteClip}
                    onRender={renderClip}
                    onDownload={downloadClip}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
