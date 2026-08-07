"use client";

interface PulseDotProps {
  color?: "positive" | "accent" | "negative" | "neutral";
  size?: "sm" | "md" | "lg";
  label?: string;
  className?: string;
}

export default function PulseDot({
  color = "positive",
  size = "sm",
  label,
  className = "",
}: PulseDotProps) {
  const colorClasses = {
    positive: {
      dot: "bg-emerald-400",
      ping: "bg-emerald-400/60",
      text: "text-emerald-400",
    },
    accent: {
      dot: "bg-accent",
      ping: "bg-accent/60",
      text: "text-accent",
    },
    negative: {
      dot: "bg-rose-500",
      ping: "bg-rose-500/60",
      text: "text-rose-400",
    },
    neutral: {
      dot: "bg-slate-400",
      ping: "bg-slate-400/40",
      text: "text-slate-400",
    },
  };

  const sizeClasses = {
    sm: "h-2 w-2",
    md: "h-2.5 w-2.5",
    lg: "h-3 w-3",
  };

  const current = colorClasses[color];

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      <span className="relative flex items-center justify-center">
        <span
          className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${current.ping}`}
        />
        <span
          className={`relative inline-flex rounded-full ${sizeClasses[size]} ${current.dot}`}
        />
      </span>
      {label && (
        <span className={`font-mono-spec text-[10px] font-semibold uppercase tracking-wider ${current.text}`}>
          {label}
        </span>
      )}
    </div>
  );
}
