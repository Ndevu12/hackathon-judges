// K/M number formatting, matching the original ui/static/script.js.
export function formatNumber(num: number | string): string {
  const n = Number(num) || 0;
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toString();
}
