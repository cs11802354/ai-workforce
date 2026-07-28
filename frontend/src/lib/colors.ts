const COOL_PALETTE = ["#6366F1", "#8B5CF6", "#0EA5E9", "#14B8A6", "#3B82F6", "#06B6D4"];

function hashSeed(seed: string): number {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function colorForSeed(seed: string): string {
  return COOL_PALETTE[hashSeed(seed) % COOL_PALETTE.length];
}

export function avatarStyle(seed: string): { background: string; color: string } {
  const hue = colorForSeed(seed);
  return { background: `${hue}1f`, color: hue };
}
