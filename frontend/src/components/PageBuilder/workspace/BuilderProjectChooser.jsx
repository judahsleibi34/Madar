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

  useEffect(() => {
    let cancelled = false;
    listBuilderProjects()
      .then((records) => {
        if (cancelled) return;
        if (autoOpenSingleProject && records.length === 1) {
          const tab = workspace === "builder-responses" ? "responses" : workspace === "builder-data" ? "data" : "design";
          navigate(getBuilderWorkspacePath(records[0].id, tab, workspace), { replace: true });
          return;
        }
        setProjects(records);
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setError("Projects could not be loaded. Try again.");
        setStatus("error");
      });
    return () => { cancelled = true; };
  }, [autoOpenSingleProject, navigate, workspace]);

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
    <section className="builder-project-chooser" aria-busy={status === "loading" || status === "creating"}>
      <header>
        <p>Page Builder</p>
        <h1>Choose a project</h1>
        <span>Each project opens with its own cloud draft and recovery copy.</span>
      </header>
      {error && <p role="alert">{error}</p>}
      {status === "loading" ? (
        <p role="status">Loading projects…</p>
      ) : (
        <div className="builder-project-chooser-list">
          {projects.map((project) => (
            <button key={project.id} type="button" onClick={() => openProject(project.id)}>
              <strong>{project.name || "Untitled Site"}</strong>
              <span>{project.status || "draft"}</span>
            </button>
          ))}
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
