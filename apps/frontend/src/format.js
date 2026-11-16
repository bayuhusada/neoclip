export function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const padded = (value) => String(value).padStart(2, "0");
  return hours > 0 ? `${hours}:${padded(minutes)}:${padded(secs)}` : `${minutes}:${padded(secs)}`;
}

export function formatBytes(bytes) {
  if (!bytes) return "0 MB";
  const mb = bytes / (1024 * 1024);
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
  return `${mb.toFixed(mb >= 10 ? 0 : 1)} MB`;
}

export function formatResolution(width, height) {
  if (!width || !height) return "—";
  return `${width}×${height}`;
}

export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}
