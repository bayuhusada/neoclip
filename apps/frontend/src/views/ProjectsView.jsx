import { useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Check,
  Film,
  FolderOpen,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../api";
import UploadCard from "../components/UploadCard";
import VideoList from "../components/VideoList";
import Eyebrow from "../components/Eyebrow";
import { formatDate } from "../format";

export default function ProjectsView({
  projects,
  videos,
  loadingVideos,
  loadError,
  onProjectCreated,
  onRefresh,
  onDeleteProject,
  onDeleteVideo,
}) {
  const [selectedId, setSelectedId] = useState(null);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState("");

  const selectedProject = projects.find((project) => project.id === selectedId) ?? null;
  const selectedVideos = selectedProject
    ? videos.filter((video) => video.project_id === selectedProject.id)
    : [];

  async function handleCreate(event) {
    event.preventDefault();
    const name = newName.trim();
    if (!name || creating) return;

    setCreating(true);
    setCreateError("");
    try {
      const created = await api.createProject({ name });
      setNewName("");
      onProjectCreated?.(created);
      setSelectedId(created.id);
    } catch (error) {
      setCreateError(error.message);
    } finally {
      setCreating(false);
    }
  }

  function startEdit(project) {
    setEditingId(project.id);
    setEditName(project.name);
    setEditDescription(project.description ?? "");
    setEditError("");
  }

  async function saveEdit(event, project) {
    event.preventDefault();
    const name = editName.trim();
    if (!name || savingEdit) return;

    setSavingEdit(true);
    setEditError("");
    try {
      await api.updateProject(project.id, {
        name,
        description: editDescription.trim() || null,
      });
      setEditingId(null);
      await onRefresh?.();
    } catch (error) {
      setEditError(error.message);
    } finally {
      setSavingEdit(false);
    }
  }

  if (selectedProject) {
    return (
      <section>
        <button
          type="button"
          onClick={() => setSelectedId(null)}
          className="mb-4 flex items-center gap-1.5 rounded-lg border border-[#2c2c36] bg-[#17171d] px-2.5 py-1.5 text-[11px] font-semibold text-[#c4b5fd] hover:bg-[#1d1d24]"
        >
          <ArrowLeft size={13} /> Semua project
        </button>

        <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <Eyebrow>Project</Eyebrow>
            <h2 className="mt-1.5 text-[22px] font-semibold">{selectedProject.name}</h2>
            <p className="mt-1 max-w-2xl text-[12px] text-[#8b8b95]">
              {selectedProject.description || "Belum ada deskripsi."}
            </p>
            <div className="mt-2 flex flex-wrap gap-x-3 text-[10px] uppercase tracking-[0.8px] text-[#71717a]">
              <span>{selectedVideos.length} video</span>
              <span>dibuat {formatDate(selectedProject.created_at)}</span>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => startEdit(selectedProject)}
              className="flex items-center gap-1.5 rounded-lg border border-[#2c2c36] bg-[#17171d] px-2.5 py-1.5 text-[11px] font-semibold text-[#d4d4d8] hover:bg-[#1d1d24]"
            >
              <Pencil size={12} /> Edit
            </button>
            <button
              type="button"
              onClick={() => onDeleteProject(selectedProject)}
              className="flex items-center gap-1.5 rounded-lg border border-[#5b2130] bg-[#2a121a] px-2.5 py-1.5 text-[11px] font-semibold text-[#fda4af] hover:bg-[#34151f]"
            >
              <Trash2 size={12} /> Hapus
            </button>
          </div>
        </div>

        {editingId === selectedProject.id && (
          <form
            onSubmit={(event) => saveEdit(event, selectedProject)}
            className="mb-5 rounded-xl border border-[#393047] bg-[#14111c] p-4"
          >
            <div className="grid gap-2 sm:grid-cols-2">
              <input
                value={editName}
                onChange={(event) => setEditName(event.target.value)}
                maxLength={200}
                className="rounded-lg border border-[#2c2c36] bg-[#0d0d12] px-3 py-2 text-[12px] text-[#e4e4e7] outline-none focus:border-[#7c3aed]"
                placeholder="Nama project"
              />
              <input
                value={editDescription}
                onChange={(event) => setEditDescription(event.target.value)}
                className="rounded-lg border border-[#2c2c36] bg-[#0d0d12] px-3 py-2 text-[12px] text-[#e4e4e7] outline-none focus:border-[#7c3aed]"
                placeholder="Deskripsi (opsional)"
              />
            </div>
            {editError && <p className="mt-2 text-[11px] text-[#fda4af]">{editError}</p>}
            <div className="mt-3 flex gap-2">
              <button
                type="submit"
                disabled={savingEdit || !editName.trim()}
                className="flex items-center gap-1.5 rounded-lg bg-[#7c3aed] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-50"
              >
                {savingEdit ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                Simpan
              </button>
              <button
                type="button"
                onClick={() => setEditingId(null)}
                className="flex items-center gap-1.5 rounded-lg border border-[#2c2c36] px-3 py-1.5 text-[11px] font-semibold text-[#a1a1aa]"
              >
                <X size={12} /> Batal
              </button>
            </div>
          </form>
        )}

        <UploadCard project={selectedProject} onUploaded={() => onRefresh?.()} />
        <VideoList videos={selectedVideos} loading={loadingVideos} onDelete={onDeleteVideo} />
      </section>
    );
  }

  return (
    <section>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Eyebrow>Workspace</Eyebrow>
          <h2 className="mt-1.5 text-[22px] font-semibold">My Projects</h2>
          <p className="mt-1 text-[12px] text-[#8b8b95]">
            Kelola project, lihat isinya, dan hapus yang sudah tidak dipakai.
          </p>
        </div>
        <span className="text-[10px] uppercase tracking-[1.2px] text-[#71717a]">
          {projects.length} project
        </span>
      </div>

      <form
        onSubmit={handleCreate}
        className="mb-6 flex flex-wrap gap-2 rounded-xl border border-[#25252d] bg-[#111115] p-3"
      >
        <input
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          maxLength={200}
          placeholder="Nama project baru, mis. Podcast Ep. 2"
          className="min-w-[220px] flex-1 rounded-lg border border-[#2c2c36] bg-[#0d0d12] px-3 py-2 text-[12px] text-[#e4e4e7] outline-none placeholder:text-[#5f5f6b] focus:border-[#7c3aed]"
        />
        <button
          type="submit"
          disabled={creating || !newName.trim()}
          className="flex items-center gap-1.5 rounded-lg bg-[#7c3aed] px-3.5 py-2 text-[12px] font-semibold text-white disabled:opacity-50"
        >
          {creating ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          Buat project
        </button>
      </form>

      {createError && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-[#5b2130] bg-[#2a121a] px-3 py-2 text-[11px] text-[#fda4af]">
          <AlertCircle size={14} className="mt-[1px] shrink-0" />
          {createError}
        </div>
      )}

      {loadError && (
        <div className="mb-4 rounded-lg border border-[#5b2130] bg-[#2a121a] px-3 py-2 text-[11px] text-[#fda4af]">
          {loadError}
        </div>
      )}

      {projects.length === 0 && !loadError && (
        <div className="rounded-2xl border border-dashed border-[#393047] bg-[#111115] px-5 py-12 text-center">
          <FolderOpen size={26} className="mx-auto text-[#a78bfa]" />
          <h3 className="mt-3 text-[15px] font-semibold">Belum ada project</h3>
          <p className="mt-1 text-[11px] text-[#71717a]">
            Buat project pertama di form atas, lalu unggah video.
          </p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {projects.map((project) => {
          const count = videos.filter((video) => video.project_id === project.id).length;
          const editing = editingId === project.id;

          return (
            <article
              key={project.id}
              className="flex flex-col rounded-xl border border-[#25252d] bg-[#111115] p-4 transition-colors hover:border-[#393047]"
            >
              {editing ? (
                <form onSubmit={(event) => saveEdit(event, project)}>
                  <input
                    value={editName}
                    onChange={(event) => setEditName(event.target.value)}
                    maxLength={200}
                    className="w-full rounded-lg border border-[#2c2c36] bg-[#0d0d12] px-2.5 py-1.5 text-[12px] text-[#e4e4e7] outline-none focus:border-[#7c3aed]"
                    placeholder="Nama project"
                  />
                  <input
                    value={editDescription}
                    onChange={(event) => setEditDescription(event.target.value)}
                    className="mt-2 w-full rounded-lg border border-[#2c2c36] bg-[#0d0d12] px-2.5 py-1.5 text-[11px] text-[#e4e4e7] outline-none focus:border-[#7c3aed]"
                    placeholder="Deskripsi (opsional)"
                  />
                  {editError && <p className="mt-2 text-[10px] text-[#fda4af]">{editError}</p>}
                  <div className="mt-2.5 flex gap-1.5">
                    <button
                      type="submit"
                      disabled={savingEdit || !editName.trim()}
                      className="flex items-center gap-1 rounded-md bg-[#7c3aed] px-2 py-1 text-[10px] font-semibold text-white disabled:opacity-50"
                    >
                      {savingEdit ? (
                        <Loader2 size={11} className="animate-spin" />
                      ) : (
                        <Check size={11} />
                      )}
                      Simpan
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="rounded-md border border-[#2c2c36] px-2 py-1 text-[10px] font-semibold text-[#a1a1aa]"
                    >
                      Batal
                    </button>
                  </div>
                </form>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedId(project.id)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <div className="flex items-center gap-2 text-[#c4b5fd]">
                        <FolderOpen size={15} />
                        <span className="truncate text-[13px] font-semibold text-[#e4e4e7]">
                          {project.name}
                        </span>
                      </div>
                      <p className="mt-1.5 line-clamp-2 min-h-[32px] text-[11px] leading-relaxed text-[#8b8b95]">
                        {project.description || "Tanpa deskripsi."}
                      </p>
                    </button>
                    <div className="flex shrink-0 gap-1">
                      <button
                        type="button"
                        onClick={() => startEdit(project)}
                        className="rounded-md border border-[#2c2c36] bg-[#17171d] p-1.5 text-[#a1a1aa] hover:text-[#e4e4e7]"
                        aria-label={`Edit ${project.name}`}
                      >
                        <Pencil size={12} />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDeleteProject(project)}
                        className="rounded-md border border-[#5b2130] bg-[#2a121a] p-1.5 text-[#fda4af] hover:bg-[#34151f]"
                        aria-label={`Hapus ${project.name}`}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>

                  <div className="mt-auto flex items-center gap-3 pt-3 text-[10px] text-[#71717a]">
                    <span className="flex items-center gap-1">
                      <Film size={11} /> {count} video
                    </span>
                    <span>{formatDate(project.created_at)}</span>
                  </div>
                </>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
