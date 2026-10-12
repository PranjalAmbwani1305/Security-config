import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { failed: boolean };

/** Last line of defence: a render error shows a recoverable screen instead of a blank page. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI error:", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", color: "#e5e7eb", background: "#07111f", padding: 24, textAlign: "center" }}>
        <div>
          <h1 style={{ fontSize: 22, marginBottom: 8 }}>Something went wrong</h1>
          <p style={{ color: "#8aa0bd", marginBottom: 16 }}>The page hit an unexpected error. Your data is safe.</p>
          <button type="button" onClick={() => window.location.assign("/")} style={{ padding: "10px 18px", borderRadius: 8, border: 0, background: "#2563eb", color: "#fff", cursor: "pointer" }}>
            Reload application
          </button>
        </div>
      </div>
    );
  }
}
