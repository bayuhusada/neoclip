import { Film, FolderOpen, Sparkles } from "lucide-react";
import UploadCard from "../components/UploadCard";
import VideoList from "../components/VideoList";
import Eyebrow from "../components/Eyebrow";

export default function DashboardView({
  projects,
  videos,
  activeProject,
  loadingVideos,
  loadError,
  onProjectCreated,
  onProjectSelect,
  onUploaded,
  onDeleteVideo,
  config,
}) {
  const visibleVideos = activeProject
    ? videos.filter((video) => video.project_id === activeProject.id)
    : videos;

  const stats = [
    ["Projects", String(projects.length), FolderOpen],
    ["Videos", String(activeProject ? visibleVideos.length : videos.length), Film],
    ["Clips generated", "0", Sparkles],
  ];

  return (
    <>
      <section className="relative flex min-h-[230px] items-center justify-between overflow-hidden rounded-2xl border border-[#393047] bg-[linear-gradient(110deg,#1c1728,#15131c_64%,#211735)] px-[39px] py-9 max-md:px-[25px]">
        <div>
          <Eyebrow bright>AI-Powered Video Workflow</Eyebrow>
          <h2 className="my-[13px] text-[clamp(25px,3vw,38px)] font-semibold leading-[1.16]">
            Turn long videos into
            <br />
            <span className="bg-[linear-gradient(90deg,#c4b5fd,#a78bfa,#67e8f9)] bg-clip-text text-transparent">
              scroll-stopping clips.
            </span>
          </h2>
          <p className="m-0 text-[13px] text-[#aaa7b5]">
            Upload a video and let NeoClip find the moments worth sharing.
          </p>
        </div>
        <div className="relative grid h-40 w-[190px] shrink-0 place-items-center text-[#c4b5fd] max-md:hidden">
          <span className="absolute h-[150px] w-[150px] rounded-full border border-[#9b79d355]" />
          <span className="absolute h-[110px] w-[110px] rounded-full border border-[#67e8f955]" />
          <Film size={76} strokeWidth={1} />
          <Sparkles className="absolute right-[17px] top-[25px] text-[#67e8f9]" size={25} />
        </div>
      </section>

      <section className="my-[22px] mb-[35px] grid grid-cols-3 gap-3.5 max-md:gap-2">
        {stats.map(([label, value, Icon]) => (
          <div
            key={label}
            className="rounded-xl border border-[#25252d] bg-[#111115] p-[17px] max-md:p-3"
          >
            <div className="mb-[13px] text-[#a78bfa]">
              <Icon size={18} />
            </div>
            <div className="text-[11px] text-[#92929d] max-md:text-[10px]">{label}</div>
            <div className="mt-[5px] text-[25px] font-semibold max-md:text-xl">{value}</div>
          </div>
        ))}
      </section>

      <section className="mb-3.5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Eyebrow>Get Started</Eyebrow>
          <h3 className="my-1.5 text-[18px] font-semibold">
            {activeProject ? activeProject.name : "Create your first project"}
          </h3>
        </div>

        {projects.length > 1 && (
          <label className="flex items-center gap-2 text-[10px] uppercase tracking-[1.2px] text-[#777783]">
            Project
            <select
              value={activeProject?.id ?? ""}
              onChange={(event) => {
                const selected = projects.find((p) => p.id === Number(event.target.value));
                onProjectSelect(selected ?? null);
              }}
              className="rounded-lg border border-[#2c2c36] bg-[#0d0d12] px-2 py-1.5 text-[11px] normal-case tracking-normal text-[#e4e4e7] outline-none focus:border-[#7c3aed]"
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </section>

      {loadError && (
        <div className="mb-3 rounded-lg border border-[#5b2130] bg-[#2a121a] px-3 py-2 text-[11px] text-[#fda4af]">
          {loadError}
        </div>
      )}

      <UploadCard
        project={activeProject}
        onProjectCreated={onProjectCreated}
        onUploaded={onUploaded}
        config={config}
      />

      <VideoList videos={visibleVideos} loading={loadingVideos} onDelete={onDeleteVideo} />
    </>
  );
}
