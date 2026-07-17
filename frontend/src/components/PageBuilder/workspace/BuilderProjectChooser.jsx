import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createBuilderProject, listBuilderProjects } from "../services/PageBuilder.api";
import { cleanBuilderProject } from "../core/PageBuilder.project";
import { createBlankWorkspaceProject } from "../core/PageBuilder.starters";
import { getBuilderWorkspacePath } from "../core/PageBuilder.workspaceRouting";
import "../../../styles/admin/PageBuilder/index.css";

export default function BuilderProjectChooser({ workspace = "page-builder", autoOpenSingleProject = false }) {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [pagination, setPagination] = useState({ limit: 20, offset: 0, has_more: false });

  useEffect(() => {
    let cancelled = false;
    listBuilderProjects({ limit: 20, offset: 0 })
      .then(({ projects: records, pagination: nextPagination }) => {
        if (cancelled) return;
        if (autoOpenSingleProject && records.length === 1 && !nextPagination.has_more) {
          const tab = workspace === "builder-responses" ? "responses" : workspace === "builder-data" ? "data" : "design";
          navigate(getBuilderWorkspacePath(records[0].id, tab, workspace), { replace: true });
          return;
        }
        setProjects(records);
        setPagination(nextPagination);
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setError("Projects could not be loaded. Try again.");
        setStatus("error");
      });
    return () => { cancelled = true; };
  }, [autoOpenSingleProject, navigate, workspace]);

  const loadMoreProjects = async () => {
    if (status === "loading-more" || !pagination.has_more) return;
    setStatus("loading-more");
    setError("");
    try {
      const nextOffset = pagination.offset + pagination.count;
      const result = await listBuilderProjects({
        limit: pagination.limit,
        offset: nextOffset,
      });
      setProjects((current) => {
        const byId = new Map(current.map((project) => [project.id, project]));
        result.projects.forEach((project) => byId.set(project.id, project));
        return [...byId.values()];
      });
      setPagination(result.pagination);
      setStatus("ready");
    } catch {
      setError("More projects could not be loaded. Try again.");
      setStatus("ready");
    }
  };

  const openProject = (projectId) => {
    const tab = workspace === "builder-responses" ? "responses" : workspace === "builder-data" ? "data" : "design";
    navigate(getBuilderWorkspacePath(projectId, tab, workspace));
  };

  const createProject = async () => {
    setStatus("creating");
    setError("");
    try {
      const draft = cleanBuilderProject(createBlankWorkspaceProject());
      const record = await createBuilderProject({
        name: draft.name || "Untitled Site",
        slug: `untitled-site-${Date.now()}`,
        draft_schema: draft,
      });
      openProject(record.id);
    } catch {
      setError("The project could not be created. Try again.");
      setStatus("error");
    }
  };

  return (
    <section className="builder-project-chooser" aria-busy={["loading", "loading-more", "creating"].includes(status)}>
      <header className="builder-project-chooser-header">
        <p className="builder-project-chooser-eyebrow">
          <span aria-hidden="true" />
          Page Builder
        </p>
        <h1>Choose a project</h1>
        <span>Each project opens with its own cloud draft and recovery copy.</span>
      </header>
      {error && <p className="builder-project-chooser-error" role="alert">{error}</p>}
      {status === "loading" ? (
        <div className="builder-project-chooser-loading" role="status" aria-live="polite">
          <div className="builder-project-loading-heading">
            <div className="builder-project-loading-mark" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <div>
              <strong>Loading your projects</strong>
              <span>Retrieving your cloud drafts and recovery copies.</span>
            </div>
          </div>

          <div className="builder-project-loading-progress" aria-hidden="true">
            <span />
          </div>

          <div className="builder-project-loading-list" aria-hidden="true">
            {[0, 1, 2].map((item) => (
              <div className="builder-project-loading-row" key={item}>
                <span className="builder-project-loading-icon" />
                <span className="builder-project-loading-copy">
                  <span />
                  <span />
                </span>
                <span className="builder-project-loading-status" />
              </div>
            ))}
          </div>

          <p className="builder-project-loading-note">
            <span aria-hidden="true" />
            Your workspace is being prepared securely.
          </p>
          <span className="builder-project-loading-announcement">Loading projects...</span>
        </div>
      ) : (
        <div className="builder-project-chooser-list">
          {projects.map((project) => (
            <button key={project.id} type="button" onClick={() => openProject(project.id)}>
              <strong>{project.name || "Untitled Site"}</strong>
              <span>{project.status || "draft"}</span>
            </button>
          ))}
          {pagination.has_more && (
            <button
              type="button"
              onClick={loadMoreProjects}
              disabled={status === "loading-more"}
            >
              <strong>{status === "loading-more" ? "Loading more…" : "Load more projects"}</strong>
              <span>Show the next projects</span>
            </button>
          )}
          {workspace === "page-builder" && (
            <button type="button" onClick={createProject} disabled={status === "creating"}>
              <strong>{status === "creating" ? "Creating…" : "Create a new project"}</strong>
              <span>Start with a blank cloud-backed project</span>
            </button>
          )}
        </div>
      )}
    </section>
  );
}
