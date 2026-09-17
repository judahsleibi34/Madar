import { Component, Fragment } from "react";

import "./RouteErrorBoundary.css";

function reportRouteRenderError(surface) {
  console.error("route_render_error", { surface });
}

export default class RouteErrorBoundary extends Component {
  state = { error: null, retryCount: 0 };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch() {
    reportRouteRenderError(this.props.surface);
  }

  componentDidUpdate(previousProps) {
    if (this.state.error && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  retry = () => {
    this.setState(({ retryCount }) => ({
      error: null,
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
          <header className="route-error__intro app-page-intro">
            <h1 id="route-error-title">We could not open this page</h1>
            <p>Something interrupted the page while it was loading. You can try again safely.</p>
          </header>
          {isBuilder ? (
            <p className="route-error__note">Your last saved version is safe.</p>
          ) : null}
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
