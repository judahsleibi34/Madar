import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import LoadingBar from "../../common/LoadingBar";
import { createBuilderProject, listBuilderProjects } from "../services/PageBuilder.api";
import { cleanBuilderProject } from "../core/PageBuilder.project";
import { createBlankWorkspaceProject } from "../core/PageBuilder.starters";
import { getBuilderWorkspacePath } from "../core/PageBuilder.workspaceRouting";
import "../../../styles/admin/PageBuilder/index.css";

function BuilderProjectLoadingState({
  variant = "projects",
  title,
  description,
  note,
  announcement,
}) {
  return (
    <div className={`builder-project-loading-bar is-${variant}`}>
      <div className="builder-project-loading-bar-copy">
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
      <LoadingBar mode="inline" label={title} />
      <span className="builder-project-loading-announcement">{announcement || note}</span>
    </div>
  );
}

export default function BuilderProjectChooser({
  workspace = "page-builder",
  autoEnterProject = false,
  autoOpenSingleProject = false,
}) {
  const navigate = useNavigate();
  const automaticEntryStartedRef = useRef(false);
  const [projects, setProjects] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [pagination, setPagination] = useState({ limit: 20, offset: 0, has_more: false });

  useEffect(() => {
    let cancelled = false;
    listBuilderProjects({ limit: 20, offset: 0 })
      .then(({ projects: records, pagination: nextPagination }) => {
        if (cancelled) return;
        if (autoEnterProject) {
          if (automaticEntryStartedRef.current) return;
          automaticEntryStartedRef.current = true;
          if (records.length > 0) {
            navigate(getBuilderWorkspacePath(records[0].id, "design", workspace), { replace: true });
            return;
          }

          const draft = cleanBuilderProject(createBlankWorkspaceProject());
          setStatus("creating");
          return createBuilderProject({
            name: draft.name || "Untitled Site",
            slug: `untitled-site-${Date.now()}`,
            draft_schema: draft,
          }).then((record) => {
            if (!cancelled) {
              navigate(getBuilderWorkspacePath(record.id, "design", workspace), { replace: true });
            }
          });
        }
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
  }, [autoEnterProject, autoOpenSingleProject, navigate, workspace]);

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

  if (autoEnterProject) {
    return (
      <section className="builder-project-loading-screen" aria-busy="true">
        <BuilderProjectLoadingState
          variant="builder"
          title="Opening the Page Builder"
          description="Preparing your canvas, components, and latest cloud draft."
          note="Your workspace will be ready in a moment."
          announcement="Opening the Page Builder..."
        />
      </section>
    );
  }

  return (
    <section className="builder-project-chooser" aria-busy={["loading", "loading-more", "creating"].includes(status)}>
      <header className="builder-project-chooser-header app-page-intro">
        <h1>Choose a project</h1>
        <span>Each project opens with its own cloud draft and recovery copy.</span>
      </header>
      {error && <p className="builder-project-chooser-error" role="alert">{error}</p>}
      {status === "loading" ? (
        <BuilderProjectLoadingState
          title="Loading your projects"
          description="Retrieving your cloud drafts and recovery copies."
          note="Your workspace is being prepared securely."
          announcement="Loading projects..."
        />
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
