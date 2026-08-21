import type { ReactNode } from "react";

export type BadgeStatus = "completed" | "failed" | "running";

interface BadgeProps {
  children: ReactNode;
  muted?: boolean;
  status?: BadgeStatus;
  dot?: boolean;
}

export function Badge({ children, muted = false, status, dot = false }: BadgeProps) {
  const className = ["badge", muted && "badge-muted", status && `status-${status}`]
    .filter(Boolean)
    .join(" ");
  return (
    <span className={className}>
      {dot && <span className="badge-dot" />}
      {children}
    </span>
  );
}
