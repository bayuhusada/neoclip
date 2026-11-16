import { useCallback, useEffect, useState } from "react";
import { Cpu, Film, FolderOpen, HardDrive, Settings, Sparkles } from "lucide-react";
import { api } from "./api";
import ConfirmDialog from "./components/ConfirmDialog";
import Eyebrow from "./components/Eyebrow";
import DashboardView from "./views/DashboardView";
import EditorView from "./views/EditorView";
import ProjectsView from "./views/ProjectsView";
import SettingsView from "./views/SettingsView";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: FolderOpen },
  { id: "projects", label: "My Projects", icon: Film },
  { id: "editor", label: "AI Clip Editor", icon: Sparkles },
];

const VIEW_META = {
  dashboard: { eyebrow: "Workspace / Overview", title: "Dashboard" },
  projects: { eyebrow: "Workspace / Projects", title: "My Projects" },
  editor: { eyebrow: "Workspace / AI Clip Editor", title: "AI Clip Editor" },
  settings: { eyebrow: "Preferences / Local", title: "Settings" },
};

export default function App() {
  const [activeView, setActiveView] = useState("dashboard");
  const [health, setHealth] = useState(null);
  const [config, setConfig] = useState(null);
  const [projects, setProjects] = useState([]);
  const [videos, setVideos] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [loadingVideos, setLoadingVideos] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const loadProjects = useCallback(async () => {
    setLoadError("");
    try {
      const list = await api.listProjects();
      setProjects(list);
      setActiveProject((current) => {
        if (current) {
          const stillThere = list.find((project) => project.id === current.id);
          if (stillThere) return stillThere;
        }
        return list[0] ?? null;
      });
      return list;
    } catch (error) {
      setLoadError(error.message);
      return [];
    }
  }, []);

  const loadVideos = useCallback(async () => {
    setLoadError("");
    setLoadingVideos(true);
    try {
      setVideos(await api.listVideos());
    } catch (error) {
      setLoadError(error.message);
    } finally {
      setLoadingVideos(false);
    }
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
    } catch {
      setHealth({ status: "down", services: {} });
    }
  }, []);

  const loadConfig = useCallback(async () => {
    try {
      setConfig(await api.config());
    } catch {
      setConfig(null);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setLoadError("");
    await Promise.allSettled([loadProjects(), loadVideos(), refreshHealth(), loadConfig()]);
  }, [loadProjects, loadVideos, refreshHealth, loadConfig]);

  useEffect(() => {
    refreshHealth();
    loadProjects();
    loadVideos();
    loadConfig();
  }, [refreshHealth, loadProjects, loadVideos, loadConfig]);

  function requestDeleteVideo(video) {
    setDeleteError("");
    setPendingDelete({
      kind: "video",
      id: video.id,
      title: "Hapus video?",
      message: `File "${video.original_filename}" beserta transkrip dan job terkait akan dihapus permanen dari disk.`,
      confirmLabel: "Hapus video",
    });
  }

  function requestDeleteProject(project) {
    setDeleteError("");
    setPendingDelete({
      kind: "project",
      id: project.id,
      title: "Hapus project?",
      message: `Project "${project.name}" dan semua video di dalamnya akan dihapus permanen, termasuk file di disk.`,
      confirmLabel: "Hapus project",
    });
  }

  async function confirmDelete() {
    if (!pendingDelete || deleteBusy) return;

    setDeleteBusy(true);
    setDeleteError("");
    try {
      if (pendingDelete.kind === "project") {
        await api.deleteProject(pendingDelete.id);
      } else {
        await api.deleteVideo(pendingDelete.id);
      }
      setPendingDelete(null);
      await refreshAll();
    } catch (error) {
      setDeleteError(error.message);
    } finally {
      setDeleteBusy(false);
    }
  }

  const meta = VIEW_META[activeView] ?? VIEW_META.dashboard;
  const ffmpegReady = Boolean(health?.services?.ffmpeg);
  const apiOnline = health?.status === "ok";

  function navButton({ id, label, icon: Icon }) {
    const active = activeView === id;
    return (
      <button
        key={id}
        type="button"
        onClick={() => setActiveView(id)}
        className={`mb-1 flex w-full items-center gap-3 rounded-lg px-3 py-[11px] text-left text-[13px] transition-colors ${
          active
            ? "bg-[#211a31] text-[#c4b5fd]"
            : "text-[#a1a1aa] hover:bg-[#17171d] hover:text-[#e4e4e7]"
        } max-md:justify-center max-md:px-0`}
      >
        <Icon size={17} className="shrink-0" />
        <span className="max-md:hidden">{label}</span>
      </button>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-[238px] shrink-0 flex-col border-r border-[#24242b] bg-[#0c0c10] px-[17px] py-[27px] max-md:w-16 max-md:px-[9px] max-md:py-5">
        <div className="flex items-center gap-2.5 px-[9px] pb-11 text-[19px] font-bold max-md:justify-center max-md:px-0 max-md:pb-[35px]">
          <span className="grid h-[31px] w-[31px] shrink-0 place-items-center rounded-[9px] bg-[#8b5cf6] text-white">
            <Film size={20} />
          </span>
          <span className="max-md:hidden">
            NeoClip<span className="text-[#a78bfa]"> AI</span>
          </span>
        </div>

        <div className="px-2.5 pb-3 text-[10px] font-bold uppercase tracking-[1.6px] text-[#777783] max-md:hidden">
          Workspace
        </div>

        <nav className="flex flex-col">{NAV_ITEMS.map(navButton)}</nav>

        <div className="mt-[34px] px-2.5 pb-3 text-[10px] font-bold uppercase tracking-[1.6px] text-[#777783] max-md:hidden">
          Preferences
        </div>
        <nav className="flex flex-col">
          {navButton({ id: "settings", label: "Settings", icon: Settings })}
        </nav>

        <div className="mt-auto flex items-center gap-[9px] border-t border-[#24242b] px-[9px] pt-[18px] text-[11px] text-[#a1a1aa] max-md:hidden">
          <span
            className={`inline-block h-[7px] w-[7px] rounded-full ${
              apiOnline ? "bg-[#34d399] shadow-[0_0_10px_#34d399]" : "bg-red-500"
            }`}
          />
          {apiOnline ? "Local API connected" : "API offline"}
        </div>
      </aside>

      <main className="mx-auto w-full max-w-[1300px] px-12 pb-5 pt-[34px] max-md:px-[18px] max-md:pt-6">
        <header className="mb-[30px] flex items-center justify-between gap-3">
          <div>
            <Eyebrow>{meta.eyebrow}</Eyebrow>
            <h1 className="mt-[7px] text-[27px] font-semibold">{meta.title}</h1>
          </div>
          <div className="flex items-center gap-2 rounded-[20px] border border-[#292932] px-3 py-2 text-[11px] text-[#b4b4bd]">
            <span
              className={`inline-block h-[7px] w-[7px] rounded-full ${
                ffmpegReady ? "bg-[#34d399] shadow-[0_0_10px_#34d399]" : "bg-red-500"
              }`}
            />
            {ffmpegReady ? "FFmpeg ready" : "FFmpeg missing"}
          </div>
        </header>

        {activeView === "dashboard" && (
          <DashboardView
            projects={projects}
            videos={videos}
            activeProject={activeProject}
            loadingVideos={loadingVideos}
            loadError={loadError}
            onProjectCreated={(project) => {
              setProjects((current) => [project, ...current]);
              setActiveProject(project);
              loadVideos();
            }}
            onProjectSelect={setActiveProject}
            onUploaded={refreshAll}
            onDeleteVideo={requestDeleteVideo}
            config={config}
          />
        )}

        {activeView === "projects" && (
          <ProjectsView
            projects={projects}
            videos={videos}
            loadingVideos={loadingVideos}
            loadError={loadError}
            onProjectCreated={(project) => {
              setProjects((current) => [project, ...current]);
              setActiveProject(project);
            }}
            onRefresh={refreshAll}
            onDeleteProject={requestDeleteProject}
            onDeleteVideo={requestDeleteVideo}
          />
        )}

        {activeView === "editor" && (
          <EditorView videos={videos} onNavigate={setActiveView} />
        )}

        {activeView === "settings" && (
          <SettingsView health={health} onRefreshHealth={refreshHealth} />
        )}

        <footer className="flex justify-between pt-6 text-[10px] text-[#a1a1aa]">
          <span>
            NeoClip AI <span className="text-[#666]">v0.1.0 · Starter</span>
          </span>
          <span className="flex items-center gap-[7px]">
            <Cpu size={14} /> Local AI <HardDrive size={14} /> Private storage
          </span>
        </footer>
      </main>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title={pendingDelete?.title ?? ""}
        message={pendingDelete?.message ?? ""}
        confirmLabel={pendingDelete?.confirmLabel ?? "Hapus"}
        busy={deleteBusy}
        error={deleteError}
        onConfirm={confirmDelete}
        onCancel={() => {
          if (deleteBusy) return;
          setPendingDelete(null);
          setDeleteError("");
        }}
      />
    </div>
  );
}
