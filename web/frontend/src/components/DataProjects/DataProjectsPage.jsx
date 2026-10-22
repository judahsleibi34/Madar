import { ArrowLeft, ArrowRight, FolderOpen, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { cleanBuilderProject } from "../PageBuilder/core/PageBuilder.project";
import { createBlankWorkspaceProject } from "../PageBuilder/core/PageBuilder.starters";
import { getBuilderWorkspacePath } from "../PageBuilder/core/PageBuilder.workspaceRouting";
import {
  createBuilderProject,
  listBuilderProjects,
} from "../PageBuilder/services/PageBuilder.api";

const isDataProject = (project) =>
  project?.draft_schema?.workspaceKind === "data" ||
  String(project?.slug || "").startsWith("data-project-");

const getDataProjectName = (project) => {
  const name = String(project?.name || "").trim();
  return !name || name === "Untitled data project" || name === "My Projects"
    ? "My data project"
    : name;
};

const formatUpdatedAt = (value) => {
  if (!value) return "Data project";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Data project";
  return `Updated ${date.toLocaleDateString()}`;
};

export default function DataProjectsPage({ dataProjectSelectionKey = "" }) {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [projectName, setProjectName] = useState("");

  useEffect(() => {
    let cancelled = false;
    listBuilderProjects({
      limit: 100,
      offset: 0,
      usageProfile: "website",
    })
      .then(({ projects: records }) => {
        if (cancelled) return;
        setProjects(records.filter(isDataProject));
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setError("Your data projects could not be loaded. Try again.");
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const openProject = (projectId) => {
    if (dataProjectSelectionKey) {
      try {
        window.sessionStorage.setItem(dataProjectSelectionKey, String(projectId));
      } catch {
        // Navigation still carries the selection if storage is unavailable.
      }
    }
    navigate(getBuilderWorkspacePath(projectId, "data", "builder-data"), {
      state: { dataProjectConfirmed: true },
    });
  };

  const createProject = async (event) => {
    event.preventDefault();
    if (status === "creating") return;
    const name = projectName.trim() || "My data project";
    setStatus("creating");
    setError("");
    try {
      const draft = cleanBuilderProject({
        ...createBlankWorkspaceProject(),
        name,
        workspaceKind: "data",
      });
      const record = await createBuilderProject({
        name,
        slug: `data-project-${Date.now()}`,
        draft_schema: draft,
      });
      openProject(record.id);
    } catch {
      setError("The data project could not be created. Try again.");
      setStatus("ready");
    }
  };

  return (
    <main className="data-projects-page">
      <header className="data-projects-page-header">
        <div>
          <span>Data workspace</span>
          <h1>Projects</h1>
          <p>Create and manage the independent project spaces that contain your datasets, charts, reports, and Athena sessions.</p>
        </div>
        <div className="data-projects-page-actions">
          <button type="button" onClick={() => navigate("/dashboard")}>
            <ArrowLeft size={17} aria-hidden="true" />
            Back to dashboard
          </button>
          <button type="button" onClick={() => setCreateOpen(true)}>
            <Plus size={18} aria-hidden="true" />
            New project
          </button>
        </div>
      </header>

      {error && <p className="data-projects-error" role="alert">{error}</p>}

      <section className="data-projects-panel" aria-labelledby="data-projects-panel-title">
        <header>
          <div>
            <h2 id="data-projects-panel-title">Your data projects</h2>
            <p>Only projects created for the Data Workspace appear here.</p>
          </div>
          <span>{projects.length} {projects.length === 1 ? "project" : "projects"}</span>
        </header>

        {status === "loading" ? (
          <div className="data-projects-state" role="status">Loading your projects…</div>
        ) : projects.length === 0 ? (
          <div className="data-projects-empty">
            <div aria-hidden="true"><FolderOpen size={26} /></div>
            <h3>No data projects yet</h3>
            <p>Create your first project to start collecting and analyzing data.</p>
            <button type="button" onClick={() => setCreateOpen(true)}>
              <Plus size={17} aria-hidden="true" /> Create project
            </button>
          </div>
        ) : (
          <div className="data-projects-grid">
            {projects.map((project) => (
              <article key={project.id} className="data-project-card">
                <div className="data-project-card-icon" aria-hidden="true">
                  <FolderOpen size={21} />
                </div>
                <div className="data-project-card-copy">
                  <h3>{getDataProjectName(project)}</h3>
                  <p>{formatUpdatedAt(project.updated_at)}</p>
                </div>
                <button type="button" onClick={() => openProject(project.id)}>
                  Open <ArrowRight size={16} aria-hidden="true" />
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      {createOpen && (
        <div className="builder-modal-backdrop data-project-create-backdrop" role="presentation">
          <form
            className="builder-modal data-project-create-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="data-project-create-title"
            onSubmit={createProject}
          >
            <div className="data-project-create-icon" aria-hidden="true">
              <FolderOpen size={27} strokeWidth={2.2} />
            </div>
            <div className="data-project-create-copy">
              <h2 id="data-project-create-title">Create a data project</h2>
              <p>Give this workspace a clear name. Its datasets, reports, and Athena sessions will stay together.</p>
            </div>
            <label className="data-project-create-field">
              <span>Project name</span>
              <input
                autoFocus
                maxLength={120}
                placeholder="Example: Quarterly sales analysis"
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
              />
            </label>
            <div className="data-project-create-actions">
              <button
                type="button"
                onClick={() => {
                  setCreateOpen(false);
                  setProjectName("");
                }}
                disabled={status === "creating"}
              >
                Cancel
              </button>
              <button type="submit" disabled={status === "creating"}>
                {status === "creating" ? "Creating…" : "Create project"}
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}
