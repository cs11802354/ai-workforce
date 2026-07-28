/**
 * Monogram tiles for the finance data tools.
 *
 * These are deliberately NOT the vendors' real logos — those are trademarks,
 * and shipping copies of them in the repo isn't something to do casually for a
 * demo. A lettermark in each vendor's recognisable brand colour gives the same
 * "logo, then name" scan without misappropriating the marks. Swap in licensed
 * assets here if this ever goes in front of customers.
 */

type Brand = { mark: string; fg: string; bg: string };

const BRANDS: Record<string, Brand> = {
  bloomberg: { mark: "B", fg: "#ffffff", bg: "#0A0A0A" },
  lseg_workspace: { mark: "LS", fg: "#ffffff", bg: "#00174F" },
  factset: { mark: "FS", fg: "#ffffff", bg: "#0F4C81" },
  capital_iq: { mark: "IQ", fg: "#ffffff", bg: "#C8102E" },
  pitchbook: { mark: "PB", fg: "#ffffff", bg: "#E8532E" },
  morningstar: { mark: "M", fg: "#ffffff", bg: "#EE1B2E" },
  aladdin: { mark: "AL", fg: "#ffffff", bg: "#1C1C1C" },
  sec_edgar: { mark: "SEC", fg: "#ffffff", bg: "#1F4E79" },
};

const FALLBACK: Brand = { mark: "?", fg: "#ffffff", bg: "#6b6d7c" };

export function ToolLogo({ id, size = 34 }: { id: string; size?: number }) {
  const brand = BRANDS[id] ?? FALLBACK;
  return (
    <span
      className="tool-logo"
      style={{
        width: size,
        height: size,
        background: brand.bg,
        color: brand.fg,
        fontSize: brand.mark.length > 2 ? size * 0.29 : size * 0.4,
      }}
      aria-hidden="true"
    >
      {brand.mark}
    </span>
  );
}
