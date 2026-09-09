type IconName = 'undo' | 'redo' | 'search' | 'add' | 'more' | 'cube' | 'ring' | 'node' | 'trace' | 'chevron' | 'warning' | 'close';

const paths: Record<IconName, React.ReactNode> = {
  undo: <path d="M9 7 4 12l5 5M4 12h10a6 6 0 1 1 0 12" />,
  redo: <path d="m15 7 5 5-5 5m5-5H10a6 6 0 1 0 0 12" />,
  search: <><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></>,
  add: <path d="M12 5v14M5 12h14" />,
  more: <path d="M5 12h.01M12 12h.01M19 12h.01" />,
  cube: <path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Zm0 0v9m8-4.5-8 4.5-8-4.5" />,
  ring: <><circle cx="12" cy="12" r="7" /><path d="M12 2v3m0 14v3M2 12h3m14 0h3" /></>,
  node: <><circle cx="6" cy="12" r="2" /><circle cx="18" cy="6" r="2" /><circle cx="18" cy="18" r="2" /><path d="m7.8 11 8.4-4M7.8 13l8.4 4" /></>,
  trace: <><path d="M5 4h10l4 4v12H5V4Z" /><path d="M15 4v5h5M8 14h8M8 17h5" /></>,
  chevron: <path d="m9 5 7 7-7 7" />,
  warning: <><path d="m12 3 9 17H3L12 3Z" /><path d="M12 9v4m0 3h.01" /></>,
  close: <path d="M6 6l12 12M18 6 6 18" />,
};

export function Icon({ name, label }: { name: IconName; label?: string }) {
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden={label ? undefined : true} aria-label={label} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}
