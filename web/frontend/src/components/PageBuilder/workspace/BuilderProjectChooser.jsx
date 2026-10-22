import PageHeaderSkeleton from "../../common/PageHeaderSkeleton";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, FolderOpen, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

import LoadingBar from "../../common/LoadingBar";
import { createBuilderProject, listBuilderProjects } from "../services/PageBuilder.api";
import { cleanBuilderProject } from "../core/PageBuilder.project";
import { createBlankWorkspaceProject } from "../core/PageBuilder.starters";
import { getBuilderWorkspacePath } from "../core/PageBuilder.workspaceRouting";
import "../../../styles/admin/PageBuilder/index.css";

const DATA_PROJECT_SLUG_PREFIX = "data-project-";
const DEFAULT_DATA_PROJECT_NAME = "My data project";

const isDataWorkspaceProject = (project) =>
  project?.draft_schema?.workspaceKind === "data" ||
  String(project?.slug || "").startsWith(DATA_PROJECT_SLUG_PREFIX);

const getProjectsForWorkspace = (records, isDataWorkspace) =>
  records.filter((project) => isDataWorkspaceProject(project) === isDataWorkspace);

const getProjectDisplayName = (project, isDataWorkspace, index = 0, projectCount = 1) => {
  const name = String(project?.name || "").trim();
  if (
    isDataWorkspace &&
    (!name ||
      name === "Untitled data project" ||
      name === "My data project" ||
      name === "My Projects")
  ) {
    return projectCount > 1 ? `${DEFAULT_DATA_PROJECT_NAME} ${index + 1}` : DEFAULT_DATA_PROJECT_NAME;
  }
  return name || "Untitled Site";
};

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
  dataProjectSelectionKey = "",
  usageProfile,
}) {
  const isDataWorkspace = workspace === "builder-data" || workspace === "data-sources";
  const navigate = useNavigate();
  const automaticEntryStartedRef = useRef(false);
  const [projects, setProjects] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [showDataProjectList, setShowDataProjectList] = useState(false);
  const [pagination, setPagination] = useState({ limit: 20, offset: 0, has_more: false });

  useEffect(() => {
    let cancelled = false;
    listBuilderProjects({ limit: 20, offset: 0, ...(usageProfile ? { usageProfile } : {}) })
      .then(({ projects: records, pagination: nextPagination }) => {
        if (cancelled) return;
        const workspaceProjects = getProjectsForWorkspace(records, isDataWorkspace);
        if (autoEnterProject) {
          if (automaticEntryStartedRef.current) return;
          automaticEntryStartedRef.current = true;
          if (workspaceProjects.length > 0) {
            navigate(getBuilderWorkspacePath(workspaceProjects[0].id, "design", workspace), { replace: true });
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
        if (autoOpenSingleProject && workspaceProjects.length === 1 && !nextPagination.has_more) {
          const tab = workspace === "builder-responses" ? "responses" : isDataWorkspace ? "data" : "design";
          navigate(getBuilderWorkspacePath(workspaceProjects[0].id, tab, workspace), { replace: true });
          return;
        }
        setProjects(workspaceProjects);
        setPagination(nextPagination);
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setError("Projects could not be loaded. Try again.");
        setStatus("error");
      });
    return () => { cancelled = true; };
  }, [autoEnterProject, autoOpenSingleProject, isDataWorkspace, navigate, usageProfile, workspace]);

  const loadMoreProjects = async () => {
    if (status === "loading-more" || !pagination.has_more) return;
    setStatus("loading-more");
    setError("");
    try {
      const nextOffset = pagination.offset + pagination.count;
      const result = await listBuilderProjects({
        limit: pagination.limit,
        offset: nextOffset,
        ...(usageProfile ? { usageProfile } : {}),
      });
      setProjects((current) => {
        const byId = new Map(current.map((project) => [project.id, project]));
        getProjectsForWorkspace(result.projects, isDataWorkspace)
          .forEach((project) => byId.set(project.id, project));
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
    const tab = workspace === "builder-responses" ? "responses" : isDataWorkspace ? "data" : "design";
    if (isDataWorkspace && dataProjectSelectionKey) {
      try {
        window.sessionStorage.setItem(dataProjectSelectionKey, String(projectId));
      } catch {
        // The route still carries the selection when session storage is unavailable.
      }
    }
    navigate(getBuilderWorkspacePath(projectId, tab, workspace), {
      state: isDataWorkspace ? { dataProjectConfirmed: true } : undefined,
    });
  };

  const createProject = async () => {
    setStatus("creating");
    setError("");
    try {
      const projectName = isDataWorkspace ? DEFAULT_DATA_PROJECT_NAME : "Untitled Site";
      const draft = cleanBuilderProject({
        ...createBlankWorkspaceProject(),
        name: projectName,
        ...(isDataWorkspace ? { workspaceKind: "data" } : {}),
      });
      const record = await createBuilderProject({
        name: draft.name || projectName,
        slug: `${isDataWorkspace ? "data-project" : "untitled-site"}-${Date.now()}`,
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

  const chooserContent = (
    <section
      className={`builder-project-chooser ${
        isDataWorkspace ? "builder-modal builder-data-project-modal is-data-workspace" : ""
      }`}
      aria-busy={["loading", "loading-more", "creating"].includes(status)}
      aria-labelledby={isDataWorkspace ? "data-project-chooser-title" : undefined}
      aria-modal={isDataWorkspace ? "true" : undefined}
      role={isDataWorkspace ? "dialog" : undefined}
    >
      {isDataWorkspace ? (
        <>
          <button
            className="builder-data-project-dashboard"
            type="button"
            onClick={() => navigate("/dashboard")}
            aria-label="Back to dashboard"
            title="Back to dashboard"
          >
            <X size={20} strokeWidth={2} aria-hidden="true" />
          </button>
          <div className="builder-data-project-modal-icon" aria-hidden="true">
            <FolderOpen size={27} strokeWidth={2.2} />
          </div>
          <header className="builder-data-project-modal-copy">
            <h2 id="data-project-chooser-title">
              {showDataProjectList ? "Select a project" : "Choose a data project"}
            </h2>
          </header>
        </>
      ) : status === "loading" ? (
        <PageHeaderSkeleton className="builder-project-chooser-header app-page-intro" />
      ) : (
        <header className="builder-project-chooser-header app-page-intro">
          <h1>Choose a project</h1>
          <span>Each project opens with its own cloud draft and recovery copy.</span>
        </header>
      )}
      {error && <p className="builder-project-chooser-error" role="alert">{error}</p>}
      {status === "loading" ? (
        <BuilderProjectLoadingState
          title="Loading your projects"
          description="Retrieving your cloud drafts and recovery copies."
          note="Your workspace is being prepared securely."
          announcement="Loading projects..."
        />
      ) : isDataWorkspace && !showDataProjectList ? (
        <div className="builder-project-chooser-list">
          <button
            className="builder-data-project-option"
            type="button"
            onClick={() => setShowDataProjectList(true)}
          >
            <strong>My Projects</strong>
          </button>
          <button
            className="builder-data-project-create"
            type="button"
            onClick={createProject}
            disabled={status === "creating"}
          >
            <strong>{status === "creating" ? "Creating…" : "Create new project"}</strong>
          </button>
        </div>
      ) : (
        <>
        <div className="builder-project-chooser-list">
          {isDataWorkspace && projects.length === 0 && (
            <p className="builder-data-project-empty">No projects yet. Go back and create your first project.</p>
          )}
          {projects.map((project, index) => (
            <button
              className={isDataWorkspace ? "builder-data-project-option" : undefined}
              key={project.id}
              type="button"
              onClick={() => openProject(project.id)}
            >
              <strong>{getProjectDisplayName(project, isDataWorkspace, index, projects.length)}</strong>
              {!isDataWorkspace && <span>{project.status || "draft"}</span>}
            </button>
          ))}
          {pagination.has_more && (
            <button
              className={isDataWorkspace ? "builder-data-project-option" : undefined}
              type="button"
              onClick={loadMoreProjects}
              disabled={status === "loading-more"}
            >
              <strong>{status === "loading-more" ? "Loading more…" : "Load more projects"}</strong>
              <span>Show the next projects</span>
            </button>
          )}
          {workspace === "page-builder" && (
            <button
              className={isDataWorkspace ? "builder-data-project-create" : undefined}
              type="button"
              onClick={createProject}
              disabled={status === "creating"}
            >
              <strong>
                {status === "creating"
                  ? "Creating…"
                  : isDataWorkspace
                    ? "Create new project"
                    : "Create a new project"}
              </strong>
              {!isDataWorkspace && <span>Start with a blank cloud-backed project</span>}
            </button>
          )}
        </div>
        {isDataWorkspace && (
          <button
            className="builder-data-project-picker-back"
            type="button"
            onClick={() => setShowDataProjectList(false)}
          >
            <ArrowLeft size={15} aria-hidden="true" />
            Back
          </button>
        )}
        </>
      )}
    </section>
  );

  if (isDataWorkspace) {
    return (
      <div className="builder-modal-backdrop builder-data-project-backdrop">
        {chooserContent}
      </div>
    );
  }

  return chooserContent;
}
