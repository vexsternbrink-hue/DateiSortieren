export function formatBytes(bytes?: number | null): string {
  if (bytes == null || Number.isNaN(bytes)) return "–";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (Math.abs(value) >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toLocaleString("de-DE", { maximumFractionDigits: unit === 0 ? 0 : 1 })} ${units[unit]}`;
}

export function formatDate(iso?: string | null): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return "nie";
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "gerade eben";
  if (seconds < 3600) return `vor ${Math.round(seconds / 60)} Min.`;
  if (seconds < 86400) return `vor ${Math.round(seconds / 3600)} Std.`;
  return `vor ${Math.round(seconds / 86400)} Tagen`;
}

export function fileName(path?: string | null): string {
  if (!path) return "";
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

export function dirName(path?: string | null): string {
  if (!path) return "";
  const parts = path.split(/[\\/]/);
  parts.pop();
  return parts.join("/");
}

export function isOnline(lastSeen?: string | null): boolean {
  return !!lastSeen && Date.now() - new Date(lastSeen).getTime() < 3 * 60 * 1000;
}
