import { useEffect } from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Hapus",
  busy = false,
  error = "",
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    if (!open) return undefined;
    function onKeyDown(event) {
      if (event.key === "Escape" && !busy) onCancel?.();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      <div className="w-full max-w-[390px] rounded-2xl border border-[#2c2c36] bg-[#111115] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.55)]">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#2a121a] text-[#fda4af]">
            <AlertTriangle size={18} />
          </span>
          <div className="min-w-0 flex-1">
            <h2 id="confirm-title" className="text-[15px] font-semibold text-[#f4f4f5]">
              {title}
            </h2>
            <p className="mt-1.5 text-[12px] leading-relaxed text-[#a1a1aa]">{message}</p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md p-1 text-[#71717a] hover:bg-[#1b1b22] hover:text-[#e4e4e7] disabled:opacity-50"
            aria-label="Tutup"
          >
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-[#5b2130] bg-[#2a121a] px-3 py-2 text-[11px] text-[#fda4af]">
            {error}
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-lg border border-[#2c2c36] bg-[#17171d] px-3 py-2 text-[12px] font-semibold text-[#d4d4d8] hover:bg-[#1d1d24] disabled:opacity-50"
          >
            Batal
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="flex items-center gap-1.5 rounded-lg bg-[#be123c] px-3 py-2 text-[12px] font-semibold text-white hover:bg-[#9f1239] disabled:opacity-60"
          >
            {busy && <Loader2 size={13} className="animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
