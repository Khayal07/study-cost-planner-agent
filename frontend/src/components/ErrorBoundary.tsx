"use client";

import { Component, type ReactNode } from "react";

type Props = { children: ReactNode; fallback?: ReactNode };
type State = { hasError: boolean };

/** App-wide safety net: a render error shows a recoverable card instead of a blank page. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    // Surfaced in the console for debugging; users see the fallback below.
    console.error("Unhandled UI error:", error);
  }

  private reset = () => this.setState({ hasError: false });

  render() {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback) return this.props.fallback;
    return (
      <div className="card mx-auto my-10 max-w-md p-8 text-center">
        <h2 className="font-display text-lg font-semibold">Something went wrong</h2>
        <p className="mt-2 text-sm text-muted">
          An unexpected error occurred while rendering this view. You can try again.
        </p>
        <button type="button" onClick={this.reset} className="btn-primary mt-5">
          Reload this section
        </button>
      </div>
    );
  }
}
