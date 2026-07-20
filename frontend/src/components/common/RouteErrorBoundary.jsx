import { Component, Fragment } from "react";

import "./RouteErrorBoundary.css";

function createEventId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `route-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function reportRouteRenderError(surface, eventId) {
  console.error("route_render_error", {
    event_id: eventId,
    surface,
  });
}

export default class RouteErrorBoundary extends Component {
  state = { error: null, eventId: null, retryCount: 0 };

  static getDerivedStateFromError(error) {
    return { error, eventId: createEventId() };
  }

  componentDidCatch() {
    reportRouteRenderError(this.props.surface, this.state.eventId);
  }

  componentDidUpdate(previousProps) {
    if (this.state.error && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null, eventId: null });
    }
  }

  retry = () => {
    this.setState(({ retryCount }) => ({
      error: null,
      eventId: null,
      retryCount: retryCount + 1,
    }));
  };

  render() {
    if (!this.state.error) {
      return <Fragment key={this.state.retryCount}>{this.props.children}</Fragment>;
    }

    const isBuilder = this.props.surface === "page-builder";
    return (
      <main className="route-error" role="alert" aria-live="assertive">
        <section className="route-error__card" aria-labelledby="route-error-title">
          <p className="route-error__eyebrow">Madar</p>
          <h1 id="route-error-title">This page could not be displayed</h1>
          <p>
            Your account data was not changed. Try this page again, or return to a safe
            starting point.
          </p>
          {isBuilder ? (
            <p className="route-error__note">
              Saved work and browser recovery drafts are preserved.
            </p>
          ) : null}
          <p className="route-error__reference">
            Reference: <code>{this.state.eventId}</code>
          </p>
          <div className="route-error__actions">
            <button type="button" onClick={this.retry} autoFocus>
              Try again
            </button>
            <a href={this.props.homePath}>{this.props.homeLabel}</a>
          </div>
        </section>
      </main>
    );
  }
}
