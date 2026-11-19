import { useState, useEffect, useRef } from "react";
import { ChevronDown, Search, Film } from "lucide-react";

export default function VideoPicker({ videos, activeVideoId, onSelect, searchPlaceholder = "Cari video..." }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  const filtered = videos.filter((v) =>
    v.original_filename.toLowerCase().includes(query.toLowerCase())
  );

  const active = videos.find((v) => v.id === activeVideoId);

  const formatDuration = (sec) => {
    if (!sec) return "—";
    const total = Math.round(sec);
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  };

  const getResolution = (v) => {
    const w = v.width ?? 1920;
    const h = v.height ?? 1080;
    return `${w}x${h}`;
  };

  const statusColor = (status) => {
    switch (status) {
      case "ready":
        return "bg-[#14532d] text-[#6ee7b7] border-[#14532d]";
      case "failed":
        return "bg-[#4a2028] text-[#fda4af] border-[#4a2028]";
      default:
        return "bg-[#4a3d20] text-[#fcd34d] border-[#4a3d20]";
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full rounded-lg border border-[#2c2c36] bg-[#17171d] px-3 py-2 text-left text-[11px] text-[#e4e4e7] outline-none focus:border-[#7c3aed] flex items-center justify-between"
      >
        <span className="truncate">
          {active?.original_filename || "Pilih video"}
        </span>
        <ChevronDown size={14} className="shrink-0 opacity-70" />
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full z-20 mt-1 rounded-lg border border-[#2c2c36] bg-[#0d0d12] shadow-lg">
          <div className="p-2 border-b border-[#2c2c36]">
            <div className="relative">
              <Search
                size={12}
                className="absolute left-2 top-1/2 -translate-y-1/2 text-[#71717a]"
              />
              <input
                type="text"
                placeholder={searchPlaceholder}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full rounded bg-[#111115] border border-[#2c2c36] pl-7 pr-2 py-1 text-[10px] text-[#e4e4e7] outline-none focus:border-[#7c3aed]"
              />
            </div>
          </div>
          <div className="max-h-48 overflow-auto">
            {filtered.length === 0 ? (
              <div className="p-3 text-center text-[10px] text-[#71717a]">Tidak ada video cocok</div>
            ) : (
              filtered.map((v) => {
                const sel = v.id === activeVideoId;
                return (
                  <div
                    key={v.id}
                    onClick={() => {
                      onSelect(v.id);
                      setOpen(false);
                      setQuery("");
                    }}
                    className={`cursor-pointer px-3 py-2 hover:bg-[#1d1d24] ${sel ? "bg-[#3b1d63]" : ""}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`truncate max-w-[180px] text-[11px] font-medium ${sel ? "text-[#ddd6fe]" : "text-[#e4e4e7]"}`}>
                        {v.original_filename}
                      </span>
                      <span
                        className={`ml-2 rounded-full border px-2 py-0.5 text-[9px] ${statusColor(v.status)}`}
                      >
                        {v.status}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-[9px] text-[#71717a]">
                      <Film size={10} />
                      <span>{formatDuration(v.duration_sec)} · {getResolution(v)}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}