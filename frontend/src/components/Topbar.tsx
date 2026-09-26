import {
  Bell,
  Search,
  ChevronDown,
  Command,
} from "lucide-react";

function Topbar() {
  return (
    <header className="sg-header">
      <div className="sg-header-search">
        <Search size={17} />

        <input
          type="text"
          placeholder="Search engagements, findings, controls..."
        />

        <div className="sg-search-shortcut">
          <Command size={11} />
          K
        </div>
      </div>

      <div className="sg-header-actions">
        <button
          type="button"
          className="sg-icon-button"
          title="Notifications"
        >
          <Bell size={18} />

          <span className="sg-notification-dot" />
        </button>

        <div className="sg-user-menu">
          <div className="sg-user-avatar">
            PA
          </div>

          <div className="sg-user-info">
            <strong>Pranjal Ambwani</strong>
            <span>Security Analyst</span>
          </div>

          <ChevronDown size={15} />
        </div>
      </div>
    </header>
  );
}

export default Topbar;