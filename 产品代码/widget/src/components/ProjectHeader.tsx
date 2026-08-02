import { Maximize2, Presentation, RefreshCw } from "lucide-react";

interface Props {
  projectName: string;
  revision: number;
  status: string;
  onFullscreen: () => void;
  onRefresh: () => void;
}

export function ProjectHeader({ projectName, revision, status, onFullscreen, onRefresh }: Props) {
  return (
    <header className="project-header">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true"><Presentation size={19} /></span>
        <div className="brand-copy">
          <strong>AI PPT Studio</strong>
          <span title={projectName}>{projectName}</span>
        </div>
      </div>
      <div className="header-actions">
        <span className="sync-state" aria-live="polite"><i />revision {revision} · {status}</span>
        <button className="icon-button" type="button" onClick={onRefresh} aria-label="刷新项目快照">
          <RefreshCw size={17} />
        </button>
        <button className="secondary-button fullscreen-button" type="button" onClick={onFullscreen}>
          <Maximize2 size={16} />
          <span>展开完整工作台</span>
        </button>
      </div>
    </header>
  );
}
