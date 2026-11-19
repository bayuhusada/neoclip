import { useRef, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, UploadCloud } from "lucide-react";
import { api } from "../api";
import { formatBytes, formatDuration, formatResolution } from "../format";

const ACCEPTED = [".mp4", ".mov", ".mkv"];

function isAccepted(file) {
  const lower = file.name.toLowerCase();
  return ACCEPTED.some((ext) => lower.endsWith(ext));
}

function limitLabel(config) {
  if (!config) return "MP4 / MOV / MKV";
  const ext = (config.allowed_extensions ?? []).map((e) => e.replace(".", "").toUpperCase()).join(" / ");
  const size = config.max_upload_mb ? `maks ${config.max_upload_mb} MB` : "tanpa batas ukuran";
  const duration = config.max_duration_sec
    ? `maks ${Math.round(config.max_duration_sec / 60)} menit`
    : "durasi bebas";
  return `${ext || "MP4 / MOV / MKV"} · ${size} · ${duration}`;
}

export default function UploadCard({ project, onProjectCreated, onUploaded, config }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [projectName, setProjectName] = useState("");
  const [creating, setCreating] = useState(false);
  const [youtubeUrl, setYoutubeUrl] = useState("");

  const busy = progress !== null;

  async function handleCreateProject(event) {
    event.preventDefault();
    const name = projectName.trim();
    if (!name || creating) return;
    setCreating(true);
    setError("");
    try {
      const created = await api.createProject({ name });
      setProjectName("");
      onProjectCreated?.(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleFile(file) {
    if (!file || busy) return;
    setError("");
    setResult(null);

    if (!isAccepted(file)) {
      setError(`Format tidak didukung: ${file.name}. Gunakan MP4, MOV, atau MKV.`);
      return;
    }
    const limitBytes = config?.max_upload_mb ? config.max_upload_mb * 1024 * 1024 : null;
    if (limitBytes && file.size > limitBytes) {
      setError(
        `Ukuran file ${formatBytes(file.size)} melebihi batas ${config.max_upload_mb} MB.`
      );
      return;
    }
    if (!project) {
      setError("Buat project dulu sebelum mengunggah video.");
      return;
    }

    setProgress(0);
    try {
      const video = await api.uploadVideo({
        projectId: project.id,
        file,
        youtubeUrl: youtubeUrl.trim() || undefined,
        onProgress: setProgress,
      });
      setResult(video);
      setYoutubeUrl("");
      onUploaded?.(video);
      if (video.status === "failed") {
        setError(video.error || "Video tersimpan tetapi metadata gagal dibaca (ffprobe).");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setProgress(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function onDrop(event) {
    event.preventDefault();
    setDragging(false);
    handleFile(event.dataTransfer.files?.[0]);
  }

  return (
    <section
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={`flex min-h-[240px] flex-col items-center justify-center rounded-[14px] border border-dashed p-[25px] text-center transition-colors ${
        dragging ? "border-[#a78bfa] bg-[#1b1626]" : "border-[#484052] bg-[#11111588]"
      }`}
    >
      <div className="rounded-xl bg-[#241d32] p-[13px] text-[#c4b5fd]">
        {busy ? <Loader2 size={27} className="animate-spin" /> : <UploadCloud size={27} />}
      </div>

      <h3 className="my-[15px] mb-[5px] text-[17px] font-semibold">
        {project ? "Drop a video, or pick a file" : "Create a project first"}
      </h3>
      <p className="m-0 text-[12px] text-[#92929d]">
        {project
          ? `Uploading ke project “${project.name}”. Semua proses tetap lokal.`
          : "Video disimpan per project agar rapi dan mudah dicari."}
      </p>

      {!project && (
        <form onSubmit={handleCreateProject} className="mt-4 flex w-full max-w-sm gap-2">
          <input
            value={projectName}
            onChange={(event) => setProjectName(event.target.value)}
            placeholder="Nama project, mis. Podcast Ep. 1"
            maxLength={200}
            className="min-w-0 flex-1 rounded-lg border border-[#2c2c36] bg-[#0d0d12] px-3 py-2 text-[12px] text-[#e4e4e7] outline-none placeholder:text-[#5f5f6b] focus:border-[#7c3aed]"
          />
          <button
            type="submit"
            disabled={creating || !projectName.trim()}
            className="rounded-lg bg-[#7c3aed] px-3.5 py-2 text-[12px] font-semibold text-white disabled:opacity-50"
          >
            {creating ? "Membuat…" : "Buat"}
          </button>
        </form>
      )}

      {project && (
        <>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED.join(",")}
            className="hidden"
            onChange={(event) => handleFile(event.target.files?.[0])}
          />
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
            className="mt-3 flex items-center gap-[9px] rounded-lg bg-[#7c3aed] px-3.5 py-2.5 text-[12px] font-semibold text-white disabled:opacity-70"
          >
            <UploadCloud size={16} />
            {busy ? `Mengunggah… ${progress}%` : "Pilih video"}
          </button>
        </>
      )}

      {project && (
        <input
          type="text"
          value={youtubeUrl}
          onChange={(event) => setYoutubeUrl(event.target.value)}
          placeholder="Tautan YouTube (opsional, mis. https://youtube.com/watch?v=xxxxxxxxxxx)"
          className="mt-3 w-full max-w-md rounded-lg border border-[#2c2c36] bg-[#0d0d12] px-3 py-2 text-[12px] text-[#e4e4e7] outline-none placeholder:text-[#52525b] focus:border-[#7c3aed]"
        />
      )}

      {busy && (
        <div className="mt-4 w-full max-w-md">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#26262f]">
            <div
              className="h-full rounded-full bg-[#8b5cf6] transition-[width] duration-200"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="mt-4 flex max-w-md items-start gap-2 rounded-lg border border-[#5b2130] bg-[#2a121a] px-3 py-2 text-left text-[11px] text-[#fda4af]">
          <AlertCircle size={14} className="mt-[1px] shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {result && !error && (
        <div className="mt-4 w-full max-w-md rounded-lg border border-[#204a3a] bg-[#0f2019] px-3 py-2 text-left text-[11px] text-[#6ee7b7]">
          <div className="flex items-center gap-2 font-semibold">
            <CheckCircle2 size={14} /> {result.original_filename}
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[#9ae6c4]">
            <span>{formatDuration(result.duration_sec)}</span>
            <span>{formatResolution(result.width, result.height)}</span>
            <span>{result.fps ? `${result.fps.toFixed(1)} fps` : "—"}</span>
            <span>{result.video_codec || "—"}</span>
            <span>{formatBytes(result.size_bytes)}</span>
          </div>
        </div>
      )}

      <div className="mt-[13px] text-[10px] text-[#71717a]">
        {limitLabel(config)} &nbsp;/&nbsp; Local processing
      </div>
    </section>
  );
}
