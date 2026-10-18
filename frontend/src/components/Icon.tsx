export type IconName =
  | "wave"
  | "grid"
  | "queue"
  | "plus"
  | "script"
  | "shield"
  | "arrow"
  | "play"
  | "pause"
  | "back"
  | "forward"
  | "search"
  | "close"
  | "menu"
  | "mic"
  | "check"
  | "upload";
const paths: Record<IconName, string> = {
  wave: "M3 10v4M7 6v12M12 3v18M17 7v10M21 10v4",
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  queue: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  plus: "M12 5v14M5 12h14",
  script: "M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7",
  shield: "M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6",
  arrow: "M5 12h14M13 6l6 6-6 6",
  play: "M8 5l11 7-11 7z",
  pause: "M8 5v14M16 5v14",
  back: "M10 7l-5 5 5 5M5 12h8a6 6 0 010 12",
  forward: "M14 7l5 5-5 5M19 12h-8a6 6 0 000 12",
  search: "M21 21l-5-5M18 10a8 8 0 11-16 0 8 8 0 0116 0",
  close: "M6 6l12 12M6 18L18 6",
  menu: "M4 6h16M4 12h16M4 18h16",
  mic: "M9 5a3 3 0 016 0v7a3 3 0 01-6 0zM5 10v2a7 7 0 0014 0v-2M12 19v3M8 22h8",
  check: "M5 12l4 4L19 6",
  upload: "M12 16V3M7 8l5-5 5 5M4 15v6h16v-6",
};
export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name]} />
    </svg>
  );
}
