import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Cpu,
  ExternalLink,
  HardDrive,
  KeyRound,
  MessageSquare,
  Plug,
  RefreshCw,
  Save,
  Server,
  Wallet,
  XCircle,
} from "lucide-react";
import { api } from "../api";
import Eyebrow from "../components/Eyebrow";

const INPUT_CLASS =
  "w-full rounded-lg border border-[#2c2c36] bg-[#0d0d12] px-2.5 py-1.5 text-[11px] text-[#e4e4e7] outline-none placeholder:text-[#52525b] focus:border-[#7c3aed]";

function StatusRow({ label, value, ok }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[#22222a] py-2 last:border-b-0">
      <span className="text-[11px] text-[#8b8b95]">{label}</span>
      <span className="flex items-center gap-1.5 text-right text-[11px] text-[#e4e4e7]">
        {ok === true && <CheckCircle2 size={13} className="text-[#34d399]" />}
        {ok === false && <XCircle size={13} className="text-[#fb7185]" />}
        {value}
      </span>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-[#8b8b95]">
        {label}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[10px] leading-relaxed text-[#71717a]">{hint}</span>}
    </label>
  );
}

function ActionButton({ onClick, disabled, busy, icon: Icon, children, tone = "ghost" }) {
  const toneClass =
    tone === "primary"
      ? "border-[#7c3aed] bg-[#3b1d63] text-[#ddd6fe] hover:bg-[#4a2479]"
      : "border-[#2c2c36] bg-[#17171d] text-[#d4d4d8] hover:bg-[#1d1d24]";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || busy}
      className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold disabled:opacity-50 ${toneClass}`}
    >
      <Icon size={12} className={busy ? "animate-spin" : ""} />
      {children}
    </button>
  );
}

function usd(value) {
  if (value === null || value === undefined) return "—";
  return `$${Number(value).toFixed(2)}`;
}

function AiSettingsCard({ onSaved }) {
  const [form, setForm] = useState({ base_url: "", api_key: "", model: "" });
  const [stored, setStored] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState(null); // { kind, text }
  const [test, setTest] = useState(null);
  const [chatTest, setChatTest] = useState(null);
  const [quota, setQuota] = useState(null);
  const [showHelp, setShowHelp] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await api.getAiSettings();
      setStored(data);
      setForm({
        base_url: data.base_url || "",
        api_key: "",
        model: data.model || "",
      });
    } catch (err) {
      setNotice({ kind: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function payload() {
    const body = { base_url: form.base_url.trim(), model: form.model.trim() };
    if (form.api_key.trim()) body.api_key = form.api_key.trim();
    return body;
  }

  async function save() {
    setBusy("save");
    setNotice(null);
    try {
      const data = await api.saveAiSettings(payload());
      setStored(data);
      setForm((prev) => ({ ...prev, base_url: data.base_url, api_key: "" }));
      setNotice({ kind: "ok", text: "Tersimpan. Key disimpan di backend, tidak pernah dikirim balik ke browser." });
      onSaved?.();
    } catch (err) {
      setNotice({ kind: "error", text: err.message });
    } finally {
      setBusy("");
    }
  }

  async function runTest() {
    setBusy("test");
    setNotice(null);
    setTest(null);
    try {
      const result = await api.testAiConnection(payload());
      setTest(result);
    } catch (err) {
      setTest({ ok: false, error: err.message, models: [] });
    } finally {
      setBusy("");
    }
  }

  async function runTestChat() {
    setBusy("chat");
    setNotice(null);
    setChatTest(null);
    try {
      const result = await api.testAiChat(payload());
      setChatTest(
        result.chat ?? { ok: false, error: "Backend tidak mengembalikan hasil chat completion." }
      );
    } catch (err) {
      setChatTest({ ok: false, error: err.message });
    } finally {
      setBusy("");
    }
  }

  async function runQuota() {
    setBusy("quota");
    setNotice(null);
    setQuota(null);
    try {
      setQuota(await api.checkAiQuota(payload()));
    } catch (err) {
      setQuota({ available: false, error: err.message });
    } finally {
      setBusy("");
    }
  }

  const configured = Boolean(stored?.configured);

  return (
    <div className="rounded-xl border border-[#25252d] bg-[#111115] p-4 lg:col-span-2">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[#a78bfa]">
          <KeyRound size={16} />
          <h3 className="text-[12px] font-semibold text-[#e4e4e7]">9Router / AI</h3>
        </div>
        <span
          className={`flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
            configured
              ? "border-[#14532d] bg-[#0d2a1a] text-[#6ee7b7]"
              : "border-[#5b2130] bg-[#2a121a] text-[#fda4af]"
          }`}
        >
          {configured ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
          {configured ? "Terkonfigurasi" : "Belum diisi"}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Base URL" hint="Cukup host+port; /v1 ditambahkan otomatis.">
          <input
            className={INPUT_CLASS}
            value={form.base_url}
            disabled={loading}
            onChange={(event) => setForm((prev) => ({ ...prev, base_url: event.target.value }))}
            placeholder="http://127.0.0.1:20128"
            spellCheck={false}
          />
        </Field>

        <Field label="Model" hint="Nama model persis seperti di 9Router, mis. mycombo.">
          <input
            className={INPUT_CLASS}
            value={form.model}
            disabled={loading}
            onChange={(event) => setForm((prev) => ({ ...prev, model: event.target.value }))}
            placeholder="mycombo"
            spellCheck={false}
          />
        </Field>

        <div className="sm:col-span-2">
          <Field
            label="API Key"
            hint={
              stored?.api_key
                ? `Tersimpan: ${stored.api_key}. Isi ulang hanya kalau mau mengganti.`
                : "Belum ada key tersimpan."
            }
          >
            <input
              className={INPUT_CLASS}
              type="password"
              value={form.api_key}
              disabled={loading}
              onChange={(event) => setForm((prev) => ({ ...prev, api_key: event.target.value }))}
              placeholder="sk-..."
              autoComplete="off"
              spellCheck={false}
            />
          </Field>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <ActionButton onClick={save} busy={busy === "save"} icon={Save} tone="primary">
          Save
        </ActionButton>
        <ActionButton onClick={runTest} busy={busy === "test"} icon={Plug}>
          Test koneksi
        </ActionButton>
        <ActionButton onClick={runTestChat} busy={busy === "chat"} icon={MessageSquare}>
          Test chat
        </ActionButton>
        <ActionButton onClick={runQuota} busy={busy === "quota"} icon={Wallet}>
          Cek kuota
        </ActionButton>
        <a
          href="http://127.0.0.1:20128/dashboard/endpoint"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 rounded-lg border border-[#2c2c36] bg-[#17171d] px-2.5 py-1.5 text-[11px] font-semibold text-[#d4d4d8] hover:bg-[#1d1d24]"
        >
          <ExternalLink size={12} /> Dashboard 9Router
        </a>
        <button
          type="button"
          onClick={() => setShowHelp((prev) => !prev)}
          className="text-[11px] text-[#a78bfa] underline-offset-2 hover:underline"
        >
          {showHelp ? "Sembunyikan panduan" : "Cara dapat API key"}
        </button>
      </div>

      {notice && (
        <div
          className={`mt-3 flex items-start gap-2 rounded-lg border px-3 py-2 text-[11px] ${
            notice.kind === "ok"
              ? "border-[#14532d] bg-[#0d2a1a] text-[#6ee7b7]"
              : "border-[#5b2130] bg-[#2a121a] text-[#fda4af]"
          }`}
        >
          {notice.kind === "ok" ? (
            <CheckCircle2 size={14} className="mt-[1px] shrink-0" />
          ) : (
            <AlertCircle size={14} className="mt-[1px] shrink-0" />
          )}
          {notice.text}
        </div>
      )}

      {test && (
        <div className="mt-3 rounded-lg border border-[#25252d] bg-[#0d0d12] p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold">
            {test.ok ? (
              <CheckCircle2 size={13} className="text-[#34d399]" />
            ) : (
              <XCircle size={13} className="text-[#fb7185]" />
            )}
            <span className={test.ok ? "text-[#6ee7b7]" : "text-[#fda4af]"}>
              {test.ok ? "Koneksi berhasil" : "Koneksi gagal"}
            </span>
            {test.ok && (
              <span className="text-[10px] text-[#71717a]">
                {test.latency_ms} ms · {test.models?.length ?? 0} model
              </span>
            )}
          </div>
          {!test.ok && <p className="mt-1 text-[10px] leading-relaxed text-[#fda4af]">{test.error}</p>}
          {test.ok && test.models?.length > 0 && (
            <p className="mt-1 break-all text-[10px] leading-relaxed text-[#8b8b95]">
              {test.models.slice(0, 8).join(" · ")}
              {test.models.length > 8 ? " · …" : ""}
            </p>
          )}
        </div>
      )}

      {chatTest && (
        <div className="mt-3 rounded-lg border border-[#25252d] bg-[#0d0d12] p-3">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold">
            {chatTest.ok ? (
              <CheckCircle2 size={13} className="text-[#34d399]" />
            ) : (
              <XCircle size={13} className="text-[#fb7185]" />
            )}
            <span className={chatTest.ok ? "text-[#6ee7b7]" : "text-[#fda4af]"}>
              {chatTest.ok ? "Chat completion berhasil" : "Chat completion gagal"}
            </span>
            {chatTest.ok && (
              <span className="text-[10px] text-[#71717a]">
                {chatTest.latency_ms} ms · {chatTest.model}
              </span>
            )}
          </div>
          {!chatTest.ok && (
            <p className="mt-1 text-[10px] leading-relaxed text-[#fda4af]">{chatTest.error}</p>
          )}
          {chatTest.ok && (
            <p className="mt-1 break-all text-[10px] leading-relaxed text-[#8b8b95]">
              Balasan: “{chatTest.reply || "(kosong)"}”
            </p>
          )}
        </div>
      )}

      {quota && (
        <div className="mt-3 rounded-lg border border-[#25252d] bg-[#0d0d12] p-3">
          {quota.available ? (
            <>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[
                  { label: "Total", value: usd(quota.total) },
                  { label: "Terpakai", value: usd(quota.used) },
                  { label: "Sisa", value: usd(quota.remaining) },
                  { label: "Plan", value: quota.plan || "—" },
                ].map((item) => (
                  <div key={item.label} className="rounded-lg border border-[#22222a] bg-[#111115] px-2 py-1.5">
                    <div className="text-[9px] uppercase tracking-wide text-[#71717a]">{item.label}</div>
                    <div className="text-[12px] font-semibold text-[#e4e4e7]">{item.value}</div>
                  </div>
                ))}
              </div>
              <p className="mt-2 flex items-center gap-1.5 text-[10px] text-[#71717a]">
                <Clock size={11} /> Reset berikutnya: {quota.reset_at ?? "—"} (siklus bulanan billing)
              </p>
            </>
          ) : (
            <p className="text-[10px] leading-relaxed text-[#fda4af]">
              {quota.error || "Kuota tidak tersedia untuk endpoint ini."}
            </p>
          )}
        </div>
      )}

      {showHelp && (
        <div className="mt-3 rounded-lg border border-[#25252d] bg-[#0d0d12] p-3 text-[11px] leading-relaxed text-[#a1a1aa]">
          <p className="mb-2 font-semibold text-[#e4e4e7]">Cara menambah API & mendapat key</p>
          <ol className="list-decimal space-y-1.5 pl-4">
            <li>
              Pastikan 9Router jalan. Cek{" "}
              <code className="rounded bg-[#1b1b22] px-1 text-[10px] text-[#c4b5fd]">
                http://127.0.0.1:20128/api/health
              </code>{" "}
              → <code className="text-[10px] text-[#c4b5fd]">{"{ ok: true }"}</code>.
            </li>
            <li>
              Buka{" "}
              <a
                className="text-[#a78bfa] underline"
                href="http://127.0.0.1:20128/dashboard/endpoint"
                target="_blank"
                rel="noreferrer"
              >
                Dashboard → Endpoint
              </a>
              . Bagian <b>API Keys</b> otomatis membuat “Default Key”.
            </li>
            <li>Klik Create Key, beri nama (mis. neoclip), lalu copy key (diawali sk-).</li>
            <li>
              Tempel di field <b>API Key</b> di atas, isi <b>Model</b> (mis.{" "}
              <code className="text-[10px] text-[#c4b5fd]">mycombo</code>), lalu <b>Save</b>.
            </li>
            <li>
              Klik <b>Test koneksi</b> untuk lihat daftar model. Kalau 401, key salah atau{" "}
              <code className="text-[10px] text-[#c4b5fd]">requireApiKey</code> di 9Router belum aktif.
            </li>
            <li>
              Provider upstream (Gemini, Claude, dll.) ditambahkan di 9Router sendiri (menu Providers),
              bukan di sini. NeoClip cuma butuh satu base URL + key.
            </li>
          </ol>
          <p className="mt-2 text-[10px] text-[#71717a]">
            Klik “Cek kuota” hanya berfungsi kalau endpoint mendukung{" "}
            <code className="text-[10px]">/dashboard/billing/subscription</code> dan{" "}
            <code className="text-[10px]">/dashboard/billing/usage</code> (format OpenAI). Kuota milik
            dashboard 9Router (per-provider) tidak dapat dibaca tanpa session cookie, jadi lihat langsung di
            dashboard.
          </p>
        </div>
      )}
    </div>
  );
}

export default function SettingsView({ health, onRefreshHealth }) {
  const [config, setConfig] = useState(null);
  const [aiConfig, setAiConfig] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadConfig() {
    setLoading(true);
    setError("");
    try {
      const [nextConfig, nextAi] = await Promise.all([api.config(), api.getAiSettings()]);
      setConfig(nextConfig);
      setAiConfig(nextAi);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadConfig();
  }, []);

  async function refreshAll() {
    await Promise.allSettled([loadConfig(), onRefreshHealth?.()]);
  }

  const services = health?.services ?? {};
  const aiConfigured = aiConfig?.configured ?? config?.ai_configured;

  return (
    <section>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Eyebrow>Preferences</Eyebrow>
          <h2 className="mt-1.5 text-[22px] font-semibold">Settings</h2>
          <p className="mt-1 text-[12px] text-[#8b8b95]">
            Kredensial AI bisa diisi langsung di sini (disimpan di{" "}
            <code className="rounded bg-[#1b1b22] px-1 py-0.5 text-[10px] text-[#c4b5fd]">
              storage/ai_config.json
            </code>
            ). Nilai lain lewat{" "}
            <code className="rounded bg-[#1b1b22] px-1 py-0.5 text-[10px] text-[#c4b5fd]">
              apps/backend/.env
            </code>
            .
          </p>
        </div>
        <button
          type="button"
          onClick={refreshAll}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-[#2c2c36] bg-[#17171d] px-2.5 py-1.5 text-[11px] font-semibold text-[#d4d4d8] hover:bg-[#1d1d24] disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-[#5b2130] bg-[#2a121a] px-3 py-2 text-[11px] text-[#fda4af]">
          <AlertCircle size={14} className="mt-[1px] shrink-0" />
          {error}
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-xl border border-[#25252d] bg-[#111115] p-4">
          <div className="mb-2 flex items-center gap-2 text-[#a78bfa]">
            <Server size={16} />
            <h3 className="text-[12px] font-semibold text-[#e4e4e7]">Local API</h3>
          </div>
          <StatusRow
            label="Status"
            value={health?.status === "ok" ? "Online" : "Offline"}
            ok={health?.status === "ok"}
          />
          <StatusRow label="FFmpeg" value={services.ffmpeg ? "Tersedia" : "Tidak ada"} ok={services.ffmpeg} />
          <StatusRow label="FFprobe" value={services.ffprobe ? "Tersedia" : "Tidak ada"} ok={services.ffprobe} />
          <StatusRow label="Storage" value={services.storage ? "Siap" : "Tidak siap"} ok={services.storage} />
        </div>

        <div className="rounded-xl border border-[#25252d] bg-[#111115] p-4">
          <div className="mb-2 flex items-center gap-2 text-[#a78bfa]">
            <Cpu size={16} />
            <h3 className="text-[12px] font-semibold text-[#e4e4e7]">Whisper (lokal)</h3>
          </div>
          <StatusRow label="Model" value={config?.whisper_model ?? "—"} />
          <StatusRow label="Device" value={config?.whisper_device ?? "—"} />
          <StatusRow label="Compute type" value={config?.whisper_compute_type ?? "—"} />
          <StatusRow label="CPU threads" value={config ? String(config.whisper_cpu_threads) : "—"} />
        </div>

        <AiSettingsCard onSaved={loadConfig} />

        <div className="rounded-xl border border-[#25252d] bg-[#111115] p-4">
          <div className="mb-2 flex items-center gap-2 text-[#a78bfa]">
            <HardDrive size={16} />
            <h3 className="text-[12px] font-semibold text-[#e4e4e7]">Storage & jobs</h3>
          </div>
          <StatusRow label="Folder" value={config?.storage_dir ?? "—"} />
          <StatusRow
            label="Batas ukuran"
            value={config?.max_upload_mb ? `${config.max_upload_mb} MB` : "tanpa batas"}
          />
          <StatusRow
            label="Batas durasi"
            value={
              config?.max_duration_sec
                ? `${Math.round(config.max_duration_sec / 60)} menit`
                : "tanpa batas"
            }
          />
          <StatusRow
            label="Timeout AI"
            value={config?.ai_timeout_sec ? `${config.ai_timeout_sec} detik` : "—"}
          />
          <StatusRow
            label="Format"
            value={(config?.allowed_extensions ?? [".mp4", ".mov", ".mkv"])
              .map((ext) => ext.replace(".", "").toUpperCase())
              .join(" / ")}
          />
          <StatusRow label="Job bersamaan" value={config ? String(config.max_concurrent_jobs) : "—"} />
          <div className="mt-2 flex items-center gap-1.5 text-[10px] text-[#71717a]">
            <Clock size={11} /> Worker berjalan satu job sekaligus.
          </div>
        </div>

        <div className="rounded-xl border border-[#25252d] bg-[#111115] p-4">
          <div className="mb-2 flex items-center gap-2 text-[#a78bfa]">
            <Plug size={16} />
            <h3 className="text-[12px] font-semibold text-[#e4e4e7]">AI status</h3>
          </div>
          <StatusRow
            label="Terkonfigurasi"
            value={aiConfigured ? "Ya" : "Belum"}
            ok={Boolean(aiConfigured)}
          />
          <StatusRow label="Base URL" value={aiConfig?.base_url ?? config?.ai_base_url ?? "—"} />
          <StatusRow label="Model" value={aiConfig?.model || config?.ai_model || "—"} />
          <div className="mt-2 text-[10px] leading-relaxed text-[#71717a]">
            API key tidak pernah dikirim ke browser; hanya bentuk tersamar.
          </div>
        </div>
      </div>
    </section>
  );
}
