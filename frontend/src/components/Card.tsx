import type { ComponentType, HTMLAttributes, ReactNode } from "react";
import { tint } from "../lib/colors";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={["agent-card", className].filter(Boolean).join(" ")} {...props} />;
}

interface StatCardProps {
  icon: ComponentType<{ size?: number }>;
  hue: string;
  value: ReactNode;
  label: string;
  sub?: string;
}

export function StatCard({ icon: Icon, hue, value, label, sub }: StatCardProps) {
  return (
    <div className="stat-card-item">
      <div className="stat-icon" style={tint(hue)}>
        <Icon size={18} />
      </div>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
    </div>
  );
}

/** Stat row that renders skeleton placeholders while `loading`, so every page
 * with a stat strip doesn't reimplement the same skeleton markup. */
export function StatGrid({
  loading,
  skeletonCount = 3,
  children,
}: {
  loading: boolean;
  skeletonCount?: number;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <div className="stat-grid">
        {Array.from({ length: skeletonCount }, (_, i) => (
          <div key={i} className="stat-card-item">
            <div className="skeleton skeleton-stat" style={{ width: "100%" }} />
          </div>
        ))}
      </div>
    );
  }
  return <div className="stat-grid">{children}</div>;
}
