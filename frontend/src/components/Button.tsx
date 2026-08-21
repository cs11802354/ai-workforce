import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "default" | "primary" | "ghost";
export type ButtonSize = "md" | "sm";

export function buttonClass(
  variant: ButtonVariant = "default",
  opts?: { size?: ButtonSize; danger?: boolean; className?: string }
): string {
  const { size = "md", danger = false, className } = opts || {};
  return [
    "btn",
    variant !== "default" && `btn-${variant}`,
    size === "sm" && "btn-sm",
    danger && "btn-danger",
    className,
  ]
    .filter(Boolean)
    .join(" ");
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  danger?: boolean;
}

/** Native <button>. For a react-router <Link> styled the same way, use
 * `buttonClass()` directly — Link can't render as a <button>. */
export function Button({
  variant = "default",
  size = "md",
  danger = false,
  className,
  ...props
}: ButtonProps) {
  return <button className={buttonClass(variant, { size, danger, className })} {...props} />;
}
