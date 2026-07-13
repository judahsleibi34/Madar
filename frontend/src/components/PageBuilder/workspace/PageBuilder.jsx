import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Baseline,
  Bold,
  Copy,
  FilePlus2,
  Globe2,
  Highlighter,
  Italic,
  LayoutTemplate,
  List,
  ListOrdered,
  Move,
  Redo2,
  Save,
  Trash2,
  Underline,
  Undo2,
} from "lucide-react";
import "../../../styles/admin/PageBuilder/index.css";
import {
  deferEffectStateUpdate,
  normalizeRuntimeAnswerValue,
} from "./pageBuilderWorkspace.helpers";
import {
  STORAGE_KEY,
  getBuilderStorageKey,
  viewports,
  builderTabs,
  alignmentOptions,
  elementTypes,
  fieldTypes,
  workflowStepTypes,
  permissionGroups,
  defaultSiteChrome,
  starterSystems,
} from "../core/PageBuilder.constants";
import { createId } from "../core/PageBuilder.constants";
import {
  createField,
  createForm,
  getFormSections,
  getFormFields,
  createElement,
  createSection,
  createPage,
  createRole,
  createUser,
  createWorkflow,
  cloneWithNewIds,
  createPosition,
} from "../core/PageBuilder.factories";
import {
  formSection,
  buildStarterProject,
  createBlankCanvasSection,
  createBlankWorkspaceProject,
  createInitialProject,
} from "../core/PageBuilder.starters";
import {
  collectPublicPageRoutingIssues,
  normalizeProjectPageRouting,
  sanitizeSubdomain,
  setProjectDefaultPage,
} from "../core/PageBuilder.routing";
import { parseCarouselSlides, serializeCarouselSlides } from "../ui/PageBuilderCarousel.utils";
import PageBuilderModals from "./PageBuilderModals";
import PageBuilderStatusBar from "./PageBuilderStatusBar";
import PageBuilderWorkspaceHeader from "./PageBuilderWorkspaceHeader";
import PageBuilderMeasuredFrame from "./PageBuilderMeasuredFrame";
import {
  FormsTab,
  ReservationsTab,
  DataTab,
  ResponsesTab,
  UsersTab,
  ThemeTab,
  PublishTab,
  WorkflowsTab,
} from "../tabs";
import {
  createBuilderProject,
  fetchBuilderProject,
  fetchWebsiteSettings,
  listBuilderProjects,
  publishBuilderProject,
  unpublishBuilderProject,
  updateBuilderProject,
  uploadBuilderAsset,
} from "../services/PageBuilder.api";
import {
  collectProjectIdIssues,
  collectFormConnectionIssues,
  getProjectIdIssueMessage,
  getFormConnectionFocusTarget,
  getFormConnectionIssueMessage,
  getBuilderConflictMessage,
  isBuilderError,
  isBuilderRevisionError,
} from "../core/PageBuilder.errors";
import {
  applyThemeModeToProject,
  getPageBuilderThemeClassName,
  getPageBuilderThemeVars,
} from "../core/PageBuilder.theme";
import { resolveMediaUrl } from "../../../utils/media";
import {
  mainBuilderHiddenTabs,
  builderWorkspaceCopy,
  mobileBlockerCopy,
  templateModalText,
  starterArabicText,
} from "../core/PageBuilder.copy";
import {
  getStoredUrlError,
  collectBuilderUrlErrorsFromUtils,
} from "../core/PageBuilder.url";
import {
  splitLines,
  getListItems,
  getCanvasTextSelectionRange,
  createInputTextSelection,
} from "../core/PageBuilder.text";
import {
  singleAnswerQuizTypes,
  correctableQuizTypes,
  gradeQuizResponse,
  getQuizSettings,
} from "../core/PageBuilder.quiz";
import {
  designPanelOptions,
  elementGroups,
  carouselElementTypes,
  builderAssetMaxBytes,
  builderAssetMimeTypes,
  builderInitialProjectLoadPromises,
} from "../core/PageBuilder.config";
import {
  getFieldOptions,
  scaleRange,
} from "../core/PageBuilder.fields";
import {
  getSectionElements,
  directElementHeight,
  estimateFormBlockHeight,
  getMetricItems,
  getMinimumBuilderSectionHeight,
  getMetricMinimumHeight,
  getDirectElementMinimumSize,
  getSectionCanvasHeight,
  convertSectionToDirectLayout,
  positionsOverlap,
  getProjectOverlapWarnings as getProjectOverlapWarningsFromLayout,
  snapToGrid,
  getDragCandidatePosition,
  getMovedElementPosition,
  createMovedFreeElement,
  commitDirectElementInteraction,
} from "../core/PageBuilder.layout";
import {
  buildFormConnectionUpdate,
  cleanBuilderProject,
  cleanBuilderProjectWithRepairs,
  normalizeFormReference,
  getBuilderProjectName,
  getBuilderProjectSlug,
  getDraftProjectFromRecord,
  getDraftProjectFromRecordWithRepairs,
  getPreviewCanvasStyle,
} from "../core/PageBuilder.project";
import {
  normalizeElementAlignSelf,
  getElementLayoutWidth,
  getElementAlignControlValue,
  getElementPlacementMargins,
  isDirectionalElementPlacement,
  getClosestColumnIdFromEvent,
  getRowCarouselElements,
} from "../core/PageBuilder.elementLayout";
import {
  getBuilderDraftReadStatus,
  hasUnreadableBuilderDraft,
  loadInitialProject,
} from "../core/PageBuilder.storage";
import {
  findElementLocationInPage,
  getFieldTypeById,
  createBuilderUrlErrorCollector,
  getElementSectionFromPage,
  getFormPlacementsFromProject,
} from "../core/PageBuilder.selectors";
import {
  runElementActionWithHandlers,
  getButtonActionIssue,
  getDirectFrameAtPoint,
} from "../core/PageBuilder.actions";
import {
  persistBuilderProject,
  createBuilderProjectPayload,
  exportBuilderProjectJson,
} from "../core/PageBuilder.persistence";
import useDebouncedProjectStorage, {
  isNewerExternalDraftMessage,
} from "./hooks/useDebouncedProjectStorage";

import {
  getBuilderElementStyle,
  getBuilderFreeElementStyle,
} from "../core/PageBuilder.styles";
import {
  createFormHandlers,
} from "../core/PageBuilder.formHandlers";
import {
  createUserHandlers,
} from "../core/PageBuilder.userHandlers";
import {
  createUploadHandlers,
} from "../core/PageBuilder.uploadHandlers";
import {
  createRuntimeFormRenderers,
} from "../core/PageBuilder.runtime";
import {
  createElementRenderer,
} from "../core/PageBuilder.elementRenderer";
import {
  createSiteChromeRenderers,
} from "../core/PageBuilder.siteChrome";
const getFieldType = (type) => getFieldTypeById(fieldTypes, type);

const builderTabPathById = {
  design: "/page-builder/pages",
  forms: "/page-builder/forms",
  reservations: "/page-builder/reservations",
  chrome: "/page-builder/header-footer",
  users: "/page-builder/users",
  theme: "/page-builder/website-theme",
  publish: "/page-builder/publish",
  data: "/page-builder/data",
  responses: "/page-builder/responses",
  workflows: "/page-builder/workflows",
};

const builderDesignPanelPathById = {
  Pages: "/page-builder/pages",
  Sections: "/page-builder/pages/sections",
  Themes: "/page-builder/pages/themes",
};

const builderTabIdByPathSegment = {
  pages: "design",
  design: "design",
  forms: "forms",
  reservations: "reservations",
  chrome: "chrome",
  "header-footer": "chrome",
  header: "chrome",
  footer: "chrome",
  users: "users",
  theme: "design",
  themes: "design",
  "website-theme": "design",
  "site-theme": "design",
  publish: "publish",
  data: "data",
  responses: "responses",
  workflows: "workflows",
};

const STARTER_MODAL_DISMISSED_KEY = `${STORAGE_KEY}:starter-template-selected`;
const BUILDER_DRAFT_SYNC_CHANNEL = "madar-builder-draft-sync";

const inlineTextElementTypes = new Set(["heading", "text", "button", "list"]);

const inlineTextToolbarButtons = [
  { id: "undo", icon: Undo2, label: "Undo" },
  { id: "redo", icon: Redo2, label: "Redo" },
  { id: "bold", icon: Bold, label: "Bold" },
  { id: "italic", icon: Italic, label: "Italic" },
  { id: "underline", icon: Underline, label: "Underline" },
  { id: "bullets", icon: List, label: "Bullets" },
  { id: "numbers", icon: ListOrdered, label: "Numbers" },
  { id: "align-left", icon: AlignLeft, label: "Align left" },
  { id: "align-center", icon: AlignCenter, label: "Align center" },
  { id: "align-right", icon: AlignRight, label: "Align right" },
  { id: "align-justify", icon: AlignJustify, label: "Justify" },
];

const getBuilderTabFromPath = (pathname = "") => {
  const match = pathname.match(/^\/page-builder\/([^/?#]+)/);
  if (!match) return null;
  return builderTabIdByPathSegment[match[1]] || null;
};

const getBuilderDesignPanelFromPath = (pathname = "") => {
  if (/^\/page-builder\/(?:theme|themes|website-theme|site-theme)(?:[/?#]|$)/.test(pathname)) {
    return "Themes";
  }
  const match = pathname.match(/^\/page-builder\/(?:pages|design)\/([^/?#]+)/);
  if (match?.[1] === "themes") return "Themes";
  if (match?.[1] === "sections") return "Sections";
  return "Pages";
};

const isDefaultShowcaseProject = (project = {}) => {
  const pageNames = Array.isArray(project.pages)
    ? project.pages.map((page) => String(page?.name || ""))
    : [];

  return (
    project?.name === "Madar Builder Demo" ||
    (pageNames.includes("Builder Demo") && pageNames.includes("Operations"))
  );
};

const createCleanBlankProject = () => cleanBuilderProject(createBlankWorkspaceProject());

const getInitialWorkspaceProject = ({ demoMode = false, storageKey = STORAGE_KEY } = {}) => {
  const initialProject = demoMode
    ? cleanBuilderProject(createInitialProject())
    : loadInitialProject(storageKey);

  if (!demoMode && isDefaultShowcaseProject(initialProject)) {
    return createCleanBlankProject();
  }

  return initialProject;
};

const isPhysicalPhoneDevice = () => {
  if (typeof window === "undefined" || typeof navigator === "undefined") {
    return false;
  }

  const userAgent = navigator.userAgent || "";
  const isPhoneUserAgent = /(?:iPhone|iPod|Mobile|Windows Phone)/i.test(userAgent);
  const isPhoneViewport = window.matchMedia?.("(max-width: 767px)")?.matches ?? window.innerWidth <= 767;
  const hasTouchInput =
    navigator.maxTouchPoints > 0 ||
    window.matchMedia?.("(pointer: coarse)")?.matches ||
    "ontouchstart" in window;

  return isPhoneUserAgent || (hasTouchInput && isPhoneViewport);
};

const rememberStarterChoice = () => {
  try {
    localStorage.setItem(STARTER_MODAL_DISMISSED_KEY, "true");
  } catch {
    // Local storage may be unavailable in private or restricted contexts.
  }
};

const isBuilderTextEditingTarget = (target) =>
  target instanceof Element &&
  Boolean(
    target.closest(
      "input:not([type='file']):not([type='checkbox']):not([type='radio']), textarea, select, [contenteditable]:not([contenteditable='false'])"
    )
  );

const insertSpaceIntoEditableTarget = (target) => {
  if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) {
    return false;
  }

  if (target.readOnly || target.disabled) return false;

  const selectionStart = target.selectionStart ?? target.value.length;
  const selectionEnd = target.selectionEnd ?? selectionStart;
  target.setRangeText(" ", selectionStart, selectionEnd, "end");
  target.dispatchEvent(
    new InputEvent("input", {
      bubbles: true,
      cancelable: false,
      data: " ",
      inputType: "insertText",
    })
  );

  return true;
};

const collectBuilderUrlErrors = createBuilderUrlErrorCollector({
  collectBuilderUrlErrorsFromUtils,
  getSectionElements,
  carouselElementTypes,
});

const collectButtonActionIssues = (project) =>
  (project?.pages || []).flatMap((page) =>
    (page?.sections || []).flatMap((section) =>
      getSectionElements(section).flatMap((element) => {
        const issue = getButtonActionIssue({
          element,
          pages: project?.pages || [],
          getStoredUrlError,
        });
        return issue ? [{
          ...issue,
          page_id: String(page?.id || ""),
          page_name: String(page?.name || page?.title || "Untitled page"),
          block_id: String(element?.id || ""),
        }] : [];
      })
    )
  );

const stripAutosaveMetadata = (project = {}) => {
  const nextProject = {
    ...project,
    publish: {
      ...(project.publish || {}),
    },
  };

  delete nextProject.publish.lastSavedAt;
  delete nextProject.publish.lastPublishedAt;

  return nextProject;
};

const getAutosaveSnapshot = (project = {}) => JSON.stringify(stripAutosaveMetadata(project));

const resolveLiveSitePath = (subdomain) => `/site/${encodeURIComponent(String(subdomain || "").trim())}/`;

const getBackendFailureDetail = (error) =>
  String(error?.data?.detail || error?.message || "");

const isLikelySessionFailure = (error) => {
  if (error?.status === 401) return true;

  if (error?.status !== 403) return false;

  return /invalid csrf token|not authenticated|unauthorized|session/i.test(
    getBackendFailureDetail(error)
  );
};

const getDefaultBuilderPageId = (project = {}) =>
  Array.isArray(project.pages) ? project.pages[0]?.id || "" : "";

const withDefaultLandingPage = (project = {}) => {
  if (!project) return project;

  const defaultPageId = getDefaultBuilderPageId(project);
  if (!defaultPageId || project.activePageId === defaultPageId) return project;

  return {
    ...project,
    activePageId: defaultPageId,
  };
};

const getColorInputValue = (value, fallback) =>
  /^#[0-9a-f]{6}$/i.test(String(value || "")) ? value : fallback;

function BuilderSidebarActions({ isSavingProject, onSave, onGoLive }) {
  const [isPublishing, setIsPublishing] = useState(false);

  const handleGoLive = async () => {
    if (!onGoLive || isPublishing) return;

    setIsPublishing(true);
    try {
      await onGoLive();
    } finally {
      setIsPublishing(false);
    }
  };

  return (
    <div className="builder-sidebar-save-control">
      <button
        type="button"
        className="page-primary-action builder-sidebar-save-button"
        disabled={isSavingProject || !onSave}
        onClick={() => onSave?.()}
      >
        <Save size={17} aria-hidden="true" />
        <span>{isSavingProject ? "Saving..." : "Save changes"}</span>
      </button>
      <button
        type="button"
        className="page-primary-action builder-sidebar-save-button"
        disabled={isPublishing || !onGoLive}
        onClick={handleGoLive}
      >
        <Globe2 size={17} aria-hidden="true" />
        <span>{isPublishing ? "Publishing..." : "Go Live"}</span>
      </button>
    </div>
  );
}

export default function PageBuilder({
  initialTab = "design",
  visibleTabIds = null,
  hideWorkspaceTabs = false,
  lang = "en",
  demoMode = false,
  templateLang = lang,
  appThemeMode = "light",
  user = null,
} = {}) {
  const location = useLocation();
  const navigate = useNavigate();
  const routeTab = getBuilderTabFromPath(location.pathname);
  const routeDesignPanel = getBuilderDesignPanelFromPath(location.pathname);
  const scopedStorageKey = getBuilderStorageKey(user?.id);
  const [project, setProject] = useState(() =>
    withDefaultLandingPage(getInitialWorkspaceProject({ demoMode, storageKey: scopedStorageKey }))
  );
  const hasProtectedUnreadableDraft = hasUnreadableBuilderDraft(scopedStorageKey);
  const hasUnrecoverableBrowserDraft =
    getBuilderDraftReadStatus(scopedStorageKey) === "unrecoverable";
  const {
    acceptExternalRevision,
    getLastPersistedAt: getLastLocalDraftPersistedAt,
    hasUnsavedChanges: hasUnsavedLocalDraftChanges,
    persistNow: persistProjectNow,
    sourceId: draftSourceId,
  } = useDebouncedProjectStorage({
    delay: 7000,
    disabled: demoMode || hasProtectedUnreadableDraft,
    project,
    storageKey: scopedStorageKey,
  });
  const [builderProjectRecord, setBuilderProjectRecord] = useState(null);
  const [builderProjectLoading, setBuilderProjectLoading] = useState(!demoMode);
  const [internalActiveTab, setInternalActiveTab] = useState(initialTab || routeTab || "design");
  const activeTab = hideWorkspaceTabs ? internalActiveTab : (routeTab || "design");
  const [designPanel, setDesignPanelState] = useState(routeDesignPanel || "Pages");
  const [viewport, setViewport] = useState("desktop");
  const [preview, setPreview] = useState(false);
  const [selected, setSelected] = useState(() => ({
    type: "page",
    id: getDefaultBuilderPageId(project) || null,
  }));
  const [modal, setModal] = useState(null);
  const [dragState, setDragState] = useState(null);
  const [paletteDropSectionId, setPaletteDropSectionId] = useState("");
  const [elementPendingDelete, setElementPendingDelete] = useState(null);
  const [userPendingDelete, setUserPendingDelete] = useState(null);
  const [pagePendingDelete, setPagePendingDelete] = useState(null);
  const [previewOverlapWarnings, setPreviewOverlapWarnings] = useState([]);
  const [publishOverlapWarnings, setPublishOverlapWarnings] = useState([]);
  const [isPhoneDevice, setIsPhoneDevice] = useState(isPhysicalPhoneDevice);
  const [, setInsertTarget] = useState(null);
  const [runtimeAnswers, setRuntimeAnswers] = useState({});
  const [runtimeErrors, setRuntimeErrors] = useState({});
  const [runtimeFormPages, setRuntimeFormPages] = useState({});
  const [runtimeFormLanguages, setRuntimeFormLanguages] = useState({});
  const [quizSessions, setQuizSessions] = useState({});
  const [toast, setToast] = useState("");
  const [isSavingProject, setIsSavingProject] = useState(false);
  const [isUnpublishingProject, setIsUnpublishingProject] = useState(false);
  const [liveSitePath, setLiveSitePath] = useState("");
  const [websiteSettings, setWebsiteSettings] = useState(null);
  const [activeTopbarAction, setActiveTopbarAction] = useState("");
  const [quizOptionsOpen, setQuizOptionsOpen] = useState(false);
  const [assetUploadBusy, setAssetUploadBusy] = useState(false);
  const [logoUrlDraft, setLogoUrlDraft] = useState(() => project.siteChrome?.logoUrl || "");
  const projectRef = useRef(project);
  const dragPreviewFrameRef = useRef(null);
  const pendingDragPreviewRef = useRef(null);
  const recentMetricAddRef = useRef(null);
  const userId = user?.id;
  const [textSelection, setTextSelection] = useState(null);
  const [inlineToolbarPosition, setInlineToolbarPosition] = useState(null);
  const backendAutosaveTimerRef = useRef(null);
  const backendBackupAutosaveTimerRef = useRef(null);
  const backendProjectSnapshotRef = useRef("");
  const pendingBackendProjectSnapshotRef = useRef("");
  const builderProjectRecordRef = useRef(builderProjectRecord);
  const remoteSaveInFlightRef = useRef(false);
  const remoteSaveActiveSnapshotRef = useRef("");
  const remoteSavePromiseRef = useRef(null);
  const pendingRemoteSaveRef = useRef(null);
  const externalDraftRevisionsRef = useRef(new Map());
  const pendingExternalDraftRef = useRef(null);
  const dragStateRef = useRef(dragState);
  const urlValidationToastShownRef = useRef(false);

  const showToast = useCallback((message) => {
    const isUrlValidationMessage =
      typeof message === "string" &&
      (message.includes("must be an HTTPS URL") ||
        message.includes("must use an HTTPS URL") ||
        message.includes("must be a valid HTTPS URL"));

    if (isUrlValidationMessage) {
      if (urlValidationToastShownRef.current) return;
      urlValidationToastShownRef.current = true;
    }

    setToast(message);
    window.setTimeout(() => setToast(""), 2200);
  }, []);

  const setActiveTab = useCallback(
    (nextTab) => {
      if (hideWorkspaceTabs) {
        setInternalActiveTab(nextTab);
        return;
      }

      const nextPath = builderTabPathById[nextTab];
      if (nextPath && location.pathname !== nextPath) {
        navigate(nextPath);
      }
    },
    [hideWorkspaceTabs, location.pathname, navigate]
  );

  const setDesignPanel = useCallback(
    (nextPanel) => {
      setDesignPanelState(nextPanel);
      if (hideWorkspaceTabs) return;

      const nextPath = builderDesignPanelPathById[nextPanel] || builderTabPathById.design;
      if (nextPath && location.pathname !== nextPath) {
        navigate(nextPath);
      }
    },
    [hideWorkspaceTabs, location.pathname, navigate]
  );

  useEffect(() => {
    projectRef.current = project;
  }, [project]);

  useEffect(() => {
    builderProjectRecordRef.current = builderProjectRecord;
  }, [builderProjectRecord]);

  useEffect(() => {
    dragStateRef.current = dragState;
  }, [dragState]);

  useEffect(() => {
    const pending = recentMetricAddRef.current;
    if (!pending) return;

    if (Date.now() > pending.expiresAt) {
      recentMetricAddRef.current = null;
      return;
    }

    const currentPage = project.pages?.find((page) => page.id === pending.pageId);
    const currentElements = (currentPage?.sections || []).flatMap(getSectionElements);
    const metricIsPresent = currentElements.some((element) => element.id === pending.elementId);

    if (metricIsPresent || currentElements.length > 0) return;

    setProject((currentProject) => ({
      ...currentProject,
      pages: currentProject.pages.map((page) =>
        page.id === pending.pageId ? pending.pageSnapshot : page
      ),
    }));
  }, [project]);

  useEffect(() => {
    const syncPhoneDevice = () => {
      setIsPhoneDevice(isPhysicalPhoneDevice());
    };

    syncPhoneDevice();
    window.addEventListener("resize", syncPhoneDevice);
    window.addEventListener("orientationchange", syncPhoneDevice);

    return () => {
      window.removeEventListener("resize", syncPhoneDevice);
      window.removeEventListener("orientationchange", syncPhoneDevice);
    };
  }, []);

  useEffect(() => {
    if (!routeTab) return;

    return deferEffectStateUpdate(() => {
      if (routeTab === "design") {
        setDesignPanelState((currentPanel) =>
          currentPanel === routeDesignPanel ? currentPanel : routeDesignPanel
        );
      }
      if (routeTab !== "design" && modal === "starter") {
        setModal(null);
        setActiveTopbarAction("");
      }
    });
  }, [modal, routeDesignPanel, routeTab]);

  useEffect(() => {
    if (hideWorkspaceTabs || routeTab) return;
    if (location.pathname === "/page-builder" || location.pathname === "/page-builder/") {
      navigate(builderTabPathById.design, { replace: true });
    }
  }, [hideWorkspaceTabs, location.pathname, navigate, routeTab]);

  useEffect(() => {
    const requiresLayoutNormalization =
      project.directLayoutVersion !== 4 ||
      (project.pages || []).some((page) =>
        (page.sections || []).some(
          (section) =>
            section.mode !== "direct" ||
            getSectionElements(section).some((element) => element.type === "responsesTable")
        )
      );

    if (!requiresLayoutNormalization) return;

    return deferEffectStateUpdate(() => {
      setProject((currentProject) => cleanBuilderProject(currentProject));
    });
  }, [project]);

  useEffect(() => {
    if (demoMode) return undefined;

    const applyExternalDraft = (candidate) => {
      if (!candidate?.serializedProject) return false;
      try {
        const nextProject = cleanBuilderProject(JSON.parse(candidate.serializedProject));
        const currentProject = projectRef.current;
        if (candidate.projectId && currentProject?.id && candidate.projectId !== currentProject.id) {
          return false;
        }
        if (JSON.stringify(currentProject) === JSON.stringify(nextProject)) {
          acceptExternalRevision(candidate.serializedProject, candidate.timestamp, candidate.revision);
          return true;
        }

        acceptExternalRevision(candidate.serializedProject, candidate.timestamp, candidate.revision);
        setProject(nextProject);
        showToast("A newer draft from another tab was applied.");
        return true;
      } catch (error) {
        if (import.meta.env.DEV) console.warn("Could not sync builder draft from another tab.", error);
        return false;
      }
    };

    const considerExternalDraft = (candidate) => {
      const sourceKey = candidate.sourceId || "storage-fallback";
      const previousRevision = externalDraftRevisionsRef.current.get(sourceKey) || 0;
      if (!isNewerExternalDraftMessage(candidate, {
        currentProjectId: projectRef.current?.id || "",
        lastPersistedAt: getLastLocalDraftPersistedAt(),
        previousRevision,
        sourceId: draftSourceId,
      })) return;
      if (candidate.revision) externalDraftRevisionsRef.current.set(sourceKey, candidate.revision);

      const editorBusy =
        Boolean(dragStateRef.current) ||
        remoteSaveInFlightRef.current ||
        isBuilderTextEditingTarget(document.activeElement) ||
        hasUnsavedLocalDraftChanges();
      if (editorBusy) {
        const pending = pendingExternalDraftRef.current;
        if (!pending || Number(candidate.timestamp || 0) >= Number(pending.timestamp || 0)) {
          pendingExternalDraftRef.current = candidate;
        }
        showToast("A newer draft from another tab is waiting until your local edits are safe.");
        return;
      }

      applyExternalDraft(candidate);
    };

    const handleDraftStorageUpdate = (event) => {
      if (draftSyncChannel) return;
      if (event.key !== scopedStorageKey || !event.newValue) return;
      considerExternalDraft({
        sourceId: "storage-fallback",
        revision: 0,
        storageKey: scopedStorageKey,
        projectId: "",
        timestamp: Date.now(),
        serializedProject: event.newValue,
      });
    };

    const draftSyncChannel =
      typeof BroadcastChannel === "undefined"
        ? null
        : new BroadcastChannel(BUILDER_DRAFT_SYNC_CHANNEL);

    const handleBroadcastDraftUpdate = (event) => {
      if (event.data?.storageKey !== scopedStorageKey) return;
      considerExternalDraft(event.data);
    };

    draftSyncChannel?.addEventListener("message", handleBroadcastDraftUpdate);
    window.addEventListener("storage", handleDraftStorageUpdate);
    return () => {
      draftSyncChannel?.removeEventListener("message", handleBroadcastDraftUpdate);
      draftSyncChannel?.close();
      window.removeEventListener("storage", handleDraftStorageUpdate);
    };
  }, [
    acceptExternalRevision,
    demoMode,
    draftSourceId,
    getLastLocalDraftPersistedAt,
    hasUnsavedLocalDraftChanges,
    scopedStorageKey,
    showToast,
  ]);

  useEffect(() => {
    const pending = pendingExternalDraftRef.current;
    if (!pending || dragState || isSavingProject) return;
    if (isBuilderTextEditingTarget(document.activeElement) || hasUnsavedLocalDraftChanges()) return;
    if (pending.timestamp && pending.timestamp <= getLastLocalDraftPersistedAt()) {
      pendingExternalDraftRef.current = null;
      return;
    }

    try {
      const nextProject = cleanBuilderProject(JSON.parse(pending.serializedProject));
      if (pending.projectId && project.id && pending.projectId !== project.id) {
        pendingExternalDraftRef.current = null;
        return;
      }
      acceptExternalRevision(pending.serializedProject, pending.timestamp, pending.revision);
      pendingExternalDraftRef.current = null;
      setProject(nextProject);
      showToast("The queued draft from another tab was applied.");
    } catch (error) {
      pendingExternalDraftRef.current = null;
      if (import.meta.env.DEV) console.warn("Queued external builder draft was unreadable.", error);
    }
  }, [
    acceptExternalRevision,
    dragState,
    getLastLocalDraftPersistedAt,
    hasUnsavedLocalDraftChanges,
    isSavingProject,
    project,
    showToast,
  ]);

  useEffect(() => {
    if (demoMode) return;

    let cancelled = false;
    const cacheKey = user?.id || "current";
    const projectSnapshotAtLoadStart = getAutosaveSnapshot(projectRef.current);
    let hasLocalDraftAtLoadStart = false;

    try {
      hasLocalDraftAtLoadStart = Boolean(localStorage.getItem(scopedStorageKey));
    } catch {
      // Continue with the backend project when storage is unavailable.
    }

    const loadBackendProject = async () => {
      setBuilderProjectLoading(true);

      try {
        if (!builderInitialProjectLoadPromises.has(cacheKey)) {
          builderInitialProjectLoadPromises.set(
            cacheKey,
            (async () => {
              const projects = await listBuilderProjects();
              const selectedProject = projects[0] || null;

              if (!selectedProject) return null;

              return fetchBuilderProject(selectedProject.id);
            })()
          );
        }

        let fullRecord = null;

        try {
          fullRecord = await builderInitialProjectLoadPromises.get(cacheKey);
          builderInitialProjectLoadPromises.delete(cacheKey);
        } catch (error) {
          builderInitialProjectLoadPromises.delete(cacheKey);
          throw error;
        }

        if (!fullRecord) {
          if (!cancelled) {
            setBuilderProjectRecord(null);
            backendProjectSnapshotRef.current = getAutosaveSnapshot(projectRef.current);
          }
          return;
        }

        const loadedResult = getDraftProjectFromRecordWithRepairs(fullRecord);
        const loadedProject = withDefaultLandingPage(loadedResult.project);

        if (!loadedProject) return;

        if (!cancelled) {
          const nextProject = isDefaultShowcaseProject(loadedProject)
            ? createCleanBlankProject()
            : loadedProject;
          const localProjectChangedWhileLoading =
            getAutosaveSnapshot(projectRef.current) !== projectSnapshotAtLoadStart;

          setBuilderProjectRecord(fullRecord);
          backendProjectSnapshotRef.current = loadedResult.repairs.length > 0
            ? ""
            : getAutosaveSnapshot(nextProject);
          // A local draft is the freshest edit source. Hydrating the backend
          // record must not replace it after the workspace is already visible.
          if (!hasLocalDraftAtLoadStart && !localProjectChangedWhileLoading) {
            setProject(nextProject);
            setSelected({ type: "page", id: nextProject.activePageId });
            persistProjectNow(nextProject);
            if (loadedResult.repairs.length > 0) {
              showToast("Madar repaired duplicate internal block IDs. Save once before going live.");
            }
          }
          if (!isDefaultShowcaseProject(loadedProject)) {
            rememberStarterChoice();
          }
          setModal((currentModal) => {
            if (currentModal !== "starter") return currentModal;
            setActiveTopbarAction("");
            return null;
          });
        }
      } catch {
        if (import.meta.env.DEV) {
          console.warn("Could not load builder project from backend.");
        }
        if (!cancelled) {
          showToast("Your saved work is ready. You can keep editing.");
        }
      } finally {
        if (!cancelled) {
          setBuilderProjectLoading(false);
        }
      }
    };

    loadBackendProject();

    return () => {
      cancelled = true;
    };
  }, [demoMode, persistProjectNow, scopedStorageKey, showToast, user?.id]);

  useEffect(() => {
    if (demoMode) {
      return deferEffectStateUpdate(() => {
        setWebsiteSettings(null);
      });
    }

    let cancelled = false;

    const loadWebsiteSettings = async () => {
      try {
        const settings = await fetchWebsiteSettings(user?.id);

        if (!cancelled) {
          setWebsiteSettings(settings || null);
        }
      } catch {
        if (!cancelled) {
          if (import.meta.env.DEV) {
            console.warn("Could not load website settings for live site URL.");
          }
        }
      }
    };

    loadWebsiteSettings();
    const refreshWebsiteSettings = () => loadWebsiteSettings();
    const refreshVisibleWebsiteSettings = () => {
      if (document.visibilityState === "visible") loadWebsiteSettings();
    };
    window.addEventListener("focus", refreshWebsiteSettings);
    document.addEventListener("visibilitychange", refreshVisibleWebsiteSettings);

    return () => {
      cancelled = true;
      window.removeEventListener("focus", refreshWebsiteSettings);
      document.removeEventListener("visibilitychange", refreshVisibleWebsiteSettings);
    };
  }, [demoMode, user?.id]);

  useEffect(() => {
    if (demoMode) return;

    const subdomain = sanitizeSubdomain(websiteSettings?.subdomain || "");

    if (!subdomain) return;

    return deferEffectStateUpdate(() => {
      const nextPath = resolveLiveSitePath(subdomain);
      setLiveSitePath((current) => (current === nextPath ? current : nextPath));
      setProject((currentProject) => {
        if (currentProject.publish?.subdomain === subdomain) return currentProject;
        return {
          ...currentProject,
          publish: {
            ...(currentProject.publish || {}),
            subdomain,
          },
        };
      });
    });
  }, [demoMode, websiteSettings?.subdomain]);

  const safeProjectPages = useMemo(
    () => (Array.isArray(project.pages) ? project.pages : []),
    [project.pages]
  );
  const safeProjectForms = useMemo(
    () => (Array.isArray(project.forms) ? project.forms : []),
    [project.forms]
  );
  const safeProjectWorkflows = useMemo(
    () => (Array.isArray(project.workflows) ? project.workflows : []),
    [project.workflows]
  );
  const safeProjectRoles = useMemo(
    () => (Array.isArray(project.roles) ? project.roles : []),
    [project.roles]
  );

  const activePage = useMemo(
    () =>
      safeProjectPages.find((page) => page.id === project.activePageId) ||
      safeProjectPages[0] ||
      null,
    [safeProjectPages, project.activePageId]
  );

  const activeForm = useMemo(
    () =>
      safeProjectForms.find((form) => form.id === project.activeFormId) ||
      safeProjectForms[0] ||
      null,
    [safeProjectForms, project.activeFormId]
  );

  const activeWorkflow = useMemo(
    () =>
      safeProjectWorkflows.find(
        (workflow) => workflow.id === project.activeWorkflowId
      ) ||
      safeProjectWorkflows[0] ||
      null,
    [safeProjectWorkflows, project.activeWorkflowId]
  );

  const openPreviewPage = () => {
    persistProjectNow(project);
    const activePageSlug = activePage?.slug === "/" ? "" : activePage?.slug || "";
    window.open(`/page-builder/preview${activePageSlug}`, "_blank", "noopener,noreferrer");
  };

  const openFormPreviewPage = (formId = activeForm?.id) => {
    if (!formId) return;
    persistProjectNow(project);
    window.open(`/page-builder/form-preview/${formId}`, "_blank", "noopener,noreferrer");
  };

  const selectedSection = useMemo(() => {
    if (selected.type !== "section") return null;

    const sections = Array.isArray(activePage?.sections)
      ? activePage.sections
      : [];

    return sections.find((section) => section.id === selected.id) || null;
  }, [activePage, selected]);

  const selectedColumn = useMemo(() => {
    if (selected.type !== "column") return null;

    const sections = Array.isArray(activePage?.sections)
      ? activePage.sections
      : [];

    for (const section of sections) {
      const rows = Array.isArray(section?.rows) ? section.rows : [];

      for (const row of rows) {
        const columns = Array.isArray(row?.columns) ? row.columns : [];
        const column = columns.find((item) => item.id === selected.id);

        if (column) return column;
      }
    }

    return null;
  }, [activePage, selected]);

  const selectedElement = useMemo(() => {
    if (selected.type !== "element") return null;

    const sections = Array.isArray(activePage?.sections)
      ? activePage.sections
      : [];

    for (const section of sections) {
      if (section.mode === "direct") {
        const freeElements = Array.isArray(section?.freeElements)
          ? section.freeElements
          : [];

        const found = freeElements.find((item) => item.id === selected.id);
        if (found) return found;
      }

      const rows = Array.isArray(section?.rows) ? section.rows : [];

      for (const row of rows) {
        const columns = Array.isArray(row?.columns) ? row.columns : [];

        for (const column of columns) {
          const elements = Array.isArray(column?.elements)
            ? column.elements
            : [];

          const found = elements.find((item) => item.id === selected.id);
          if (found) return found;
        }
      }
    }

    return null;
  }, [activePage, selected]);

  const reservationBlocks = useMemo(() => {
    const blocks = [];

    (project.pages || []).forEach((page) => {
      (page.sections || []).forEach((section) => {
        if (section.mode === "direct") {
          (section.freeElements || []).forEach((element) => {
            if (element.type === "reservationBlock") {
              blocks.push({ element, page, section });
            }
          });
        }

        (section.rows || []).forEach((row) => {
          (row.columns || []).forEach((column) => {
            (column.elements || []).forEach((element) => {
              if (element.type === "reservationBlock") {
                blocks.push({ element, page, section });
              }
            });
          });
        });
      });
    });

    return blocks;
  }, [project.pages]);

  const reservationFormOptions = useMemo(
    () =>
      reservationBlocks.map((block, index) => {
        const reservation = block.element.reservation || {};
        const title = reservation.title || block.element.name || `Reservation ${index + 1}`;
        const modeLabel = reservation.bookingMode === "flexible" ? "Date request" : "Fixed slots";

        return {
          id: block.element.id,
          label: `${index + 1}. ${title}`,
          meta: `${modeLabel} - ${block.page.name}`,
        };
      }),
    [reservationBlocks]
  );

  const getReservationBlockValue = useCallback(
    (element) => {
      const sourceId = element?.connectedReservationBlockId;
      if (!sourceId || sourceId === element?.id) return element?.reservation || null;

      const source = reservationBlocks.find((block) => block.element.id === sourceId)?.element;
      return source?.reservation || element?.reservation || null;
    },
    [reservationBlocks]
  );

  const selectedRole = useMemo(() => {
    if (selected.type !== "role") return null;
    return safeProjectRoles.find((role) => role.id === selected.id) || null;
  }, [safeProjectRoles, selected]);

  const updateProject = useCallback((updater) => {
    setProject((prev) => updater(prev));
  }, []);

  const setThemeMode = (mode) => {
    updateProject((prev) => applyThemeModeToProject(prev, mode));
  };

  const updateActivePage = useCallback((updater) => {
    updateProject((prev) => ({
      ...prev,
      pages: prev.pages.map((page) =>
        page.id === prev.activePageId ? updater(page) : page
      ),
    }));
  }, [updateProject]);

  const updateSections = useCallback((updater) => {
    updateActivePage((page) => ({ ...page, sections: updater(page.sections) }));
  }, [updateActivePage]);

  const updateActiveForm = (updater) => {
    updateProject((prev) => ({
      ...prev,
      forms: prev.forms.map((form) =>
        form.id === prev.activeFormId ? updater(form) : form
      ),
    }));
  };

  const updateActiveWorkflow = (updater) => {
    updateProject((prev) => ({
      ...prev,
      workflows: prev.workflows.map((workflow) =>
        workflow.id === prev.activeWorkflowId ? updater(workflow) : workflow
      ),
    }));
  };

  const selectPage = useCallback((pageId) => {
    updateProject((prev) => ({ ...prev, activePageId: pageId }));
    setSelected({ type: "page", id: pageId });
  }, [updateProject]);

  const selectForm = (formId) => {
    updateProject((prev) => ({ ...prev, activeFormId: formId }));
    setSelected({ type: "form", id: formId });
  };

  const selectWorkflow = (workflowId) => {
    updateProject((prev) => ({ ...prev, activeWorkflowId: workflowId }));
    setSelected({ type: "workflow", id: workflowId });
  };

  const addWorkflow = () => {
    const workflow = createWorkflow(
      `Workflow ${project.workflows.length + 1}`,
      project.activeFormId
    );

    updateProject((prev) => ({
      ...prev,
      workflows: [...prev.workflows, workflow],
      activeWorkflowId: workflow.id,
    }));

    setSelected({ type: "workflow", id: workflow.id });
  };

  const addWorkflowStep = () => {
    if (!activeWorkflow) return;

    updateActiveWorkflow((workflow) => ({
      ...workflow,
      steps: [
        ...(workflow.steps || []),
        {
          id: createId("step"),
          type: workflowStepTypes[0]?.id || "email",
          label: `Step ${(workflow.steps || []).length + 1}`,
          details: "",
        },
      ],
    }));
  };

  const updateWorkflowStep = (stepId, updates) => {
    updateActiveWorkflow((workflow) => ({
      ...workflow,
      steps: (workflow.steps || []).map((step) =>
        step.id === stepId ? { ...step, ...updates } : step
      ),
    }));
  };

  const deleteWorkflowStep = (stepId) => {
    updateActiveWorkflow((workflow) => ({
      ...workflow,
      steps: (workflow.steps || []).filter((step) => step.id !== stepId),
    }));
  };

  const addPage = () => {
    const canvasSection = createBlankCanvasSection();
    const page = createPage(`Page ${project.pages.length + 1}`, [canvasSection], {
      canvasLayoutVersion: 1,
    });
    updateProject((prev) => normalizeProjectPageRouting({
      ...prev,
      pages: [...prev.pages, page],
      activePageId: page.id,
    }));
    setSelected({ type: "section", id: canvasSection.id });
  };

  const duplicatePage = () => {
    if (!activePage) return;
    const copy = cloneWithNewIds(activePage);
    copy.name = `${activePage.name} Copy`;
    copy.slug = `${activePage.slug === "/" ? "/home" : activePage.slug}-copy`;
    copy.isDefault = false;

    updateProject((prev) => normalizeProjectPageRouting({
      ...prev,
      pages: [...prev.pages, copy],
      activePageId: copy.id,
    }));

    setSelected({ type: "page", id: copy.id });
  };

  const eraseActivePageBlocks = () => {
    if (!activePage) return;

    updateActivePage((page) => ({
      ...page,
      sections: [],
    }));
    setSelected({ type: "page", id: activePage.id });
    showToast("Page blocks erased. Pages are kept.");
  };

  const requestDeleteActivePage = () => {
    if (!activePage || safeProjectPages.length <= 1) return;

    setPagePendingDelete({
      id: activePage.id,
      name: activePage.name || "Page",
    });
  };

  const confirmDeletePendingPage = () => {
    if (!pagePendingDelete?.id || safeProjectPages.length <= 1) {
      setPagePendingDelete(null);
      return;
    }

    const nextPage =
      safeProjectPages.find((page) => page.id !== pagePendingDelete.id) ||
      safeProjectPages[0];

    updateProject((prev) => normalizeProjectPageRouting({
      ...prev,
      pages: (prev.pages || []).filter((page) => page.id !== pagePendingDelete.id),
      defaultPageId: prev.defaultPageId === pagePendingDelete.id ? "" : prev.defaultPageId,
      activePageId: nextPage.id,
    }));
    setSelected({ type: "page", id: nextPage.id });
    setPagePendingDelete(null);
    showToast("Page deleted.");
  };

  const {
    addForm,
    deleteActiveForm,
    addFormSection,
    addFieldToForm,
    updateActiveFormQuiz,
    updateFormField,
    updateFormSection,
    moveFormField,
    duplicateFormField,
    deleteFormField,
    deleteFormSection,
  } = createFormHandlers({
    project,
    activeForm,
    updateProject,
    updateActiveForm,
    setSelected,
    createId,
    createField,
    createForm,
    createWorkflow,
    getFormSections,
    getFormFields,
    getQuizSettings,
    cloneWithNewIds,
  });

  const updateSelectedColumn = (updates) => {
    if (!selectedColumn) return;

    updateSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) =>
            column.id === selectedColumn.id
              ? { ...column, ...updates, layout: { ...column.layout, ...(updates.layout || {}) } }
              : column
          ),
        })),
      }))
    );
  };

  const addComponentToSection = (type, requestedSectionId = "", dropPoint = null, overrides = {}) => {
    const element = createElement(
      type,
      type === "formBlock"
        ? { connectedFormId: project.activeFormId }
        : {}
    );
    const nextElementConnectedFormId = overrides.connectedFormId || element.connectedFormId;
    const existingTarget =
      activePage?.sections.find((section) => section.id === requestedSectionId) ||
      selectedSection ||
      activePage?.sections[activePage.sections.length - 1];
    const targetSection = existingTarget || convertSectionToDirectLayout(
      createSection({
        name: "Section 1",
        layout: { width: "full", minHeight: 480 },
        rows: [],
      })
    );
    const isNewSection = !existingTarget;
    const nextPosition = {};
    const requiredHeights = {};

    ["desktop", "tablet", "mobile"].forEach((viewportName) => {
      const base = element.position?.[viewportName] || createPosition()[viewportName];
      const canvasWidth = viewports[viewportName] || viewports.desktop;
      const nextY = (targetSection.freeElements || []).reduce((bottom, item) => {
        const position = item.position?.[viewportName] || createPosition()[viewportName];
        return Math.max(bottom, (Number(position.y) || 0) + (Number(position.height) || 80));
      }, 8) + 16;
      const useDropPoint = viewportName === viewport && dropPoint;
      const width = Math.min(Number(base.width) || 380, canvasWidth - 24);
      const connectedForm = type === "formBlock"
        ? project.forms.find((form) => form.id === nextElementConnectedFormId)
        : null;
      const height = type === "formBlock"
        ? estimateFormBlockHeight(connectedForm, viewportName)
        : directElementHeight(element);

      nextPosition[viewportName] = {
        ...base,
        width,
        height,
        x: useDropPoint
          ? Math.max(0, Math.min(dropPoint.x - width / 2, canvasWidth - width))
          : 24,
        y: useDropPoint ? Math.max(0, dropPoint.y - height / 2) : nextY,
      };
      requiredHeights[viewportName] = Math.max(
        getSectionCanvasHeight(targetSection, viewportName),
        getMinimumBuilderSectionHeight(),
        nextPosition[viewportName].y + height + 24
      );
    });

    const nextElement = { ...element, ...overrides, mode: "direct", position: nextPosition };
    const updateTarget = (section) => ({
      ...section,
      layout: {
        ...section.layout,
        minHeight: requiredHeights.desktop,
        minHeightByViewport: requiredHeights,
      },
      freeElements: [...(section.freeElements || []), nextElement],
    });

    updateActivePage((page) => {
      const nextPage = {
        ...page,
        sections: isNewSection
          ? [...(page.sections || []), updateTarget(targetSection)]
          : (page.sections || []).map((section) =>
              section.id === targetSection.id ? updateTarget(section) : section
            ),
      };

      if (type === "metric") {
        recentMetricAddRef.current = {
          pageId: page.id,
          elementId: nextElement.id,
          pageSnapshot: nextPage,
          expiresAt: Date.now() + 5000,
        };
      }

      return nextPage;
    });
    setSelected({ type: "element", id: nextElement.id });
    setPaletteDropSectionId("");
    showToast(`${nextElement.name || "Component"} added to ${targetSection.name || "section"}.`);
  };

  const handlePaletteDragStart = (event, type) => {
    event.dataTransfer.effectAllowed = "copy";
    event.dataTransfer.setData("application/x-madar-component", type);
    event.dataTransfer.setData("text/plain", type);
  };

  const handlePaletteDrop = (event, section) => {
    event.preventDefault();
    event.stopPropagation();
    const type =
      event.dataTransfer.getData("application/x-madar-component") ||
      event.dataTransfer.getData("text/plain");
    if (!elementTypes.some((item) => item.id === type)) return;

    const rect = event.currentTarget.getBoundingClientRect();
    addComponentToSection(type, section.id, {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    });
  };

  const updateSelectedElement = useCallback((updates) => {
    if (!selectedElement) return;

    const merge = (element) => ({
      ...element,
      ...updates,
      styles: { ...element.styles, ...(updates.styles || {}) },
      action: { ...element.action, ...(updates.action || {}) },
    });

    updateSections((sections) =>
      sections.map((section) => {
        if (section.mode === "direct") {
          return {
            ...section,
            freeElements: section.freeElements.map((element) =>
              element.id === selectedElement.id ? merge(element) : element
            ),
          };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.map((element) =>
                element.id === selectedElement.id ? merge(element) : element
              ),
            })),
          })),
        };
      })
    );
  }, [selectedElement, updateSections]);

  const updateElementInlineText = useCallback((elementId, updates) => {
    if (!elementId) return;

    const merge = (element) => ({
      ...element,
      ...updates,
      styles: { ...element.styles, ...(updates.styles || {}) },
      action: { ...element.action, ...(updates.action || {}) },
    });

    updateSections((sections) =>
      sections.map((section) => {
        if (section.mode === "direct") {
          return {
            ...section,
            freeElements: section.freeElements.map((element) =>
              element.id === elementId ? merge(element) : element
            ),
          };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.map((element) =>
                element.id === elementId ? merge(element) : element
              ),
            })),
          })),
        };
      })
    );
  }, [updateSections]);

  const updateReservationBlock = (elementId, updates) => {
    const merge = (element) => ({
      ...element,
      ...updates,
      styles: { ...element.styles, ...(updates.styles || {}) },
      action: { ...element.action, ...(updates.action || {}) },
    });

    updateProject((prev) => ({
      ...prev,
      pages: prev.pages.map((page) => ({
        ...page,
        sections: page.sections.map((section) => {
          if (section.mode === "direct") {
            return {
              ...section,
              freeElements: (section.freeElements || []).map((element) =>
                element.id === elementId ? merge(element) : element
              ),
            };
          }

          return {
            ...section,
            rows: (section.rows || []).map((row) => ({
              ...row,
              columns: (row.columns || []).map((column) => ({
                ...column,
                elements: (column.elements || []).map((element) =>
                  element.id === elementId ? merge(element) : element
                ),
              })),
            })),
          };
        }),
      })),
    }));
  };

  const selectReservationBlock = (elementId, pageId) => {
    updateProject((prev) => ({ ...prev, activePageId: pageId || prev.activePageId }));
    setSelected({ type: "element", id: elementId });
  };

  const resizeReservationBlockForEditing = (elementId) => {
    updateProject((prev) => ({
      ...prev,
      pages: prev.pages.map((page) => ({
        ...page,
        sections: page.sections.map((section) => {
          const resizeElement = (element) => {
            if (element.id !== elementId || element.type !== "reservationBlock") return element;

            const nextPosition = {};
            ["desktop", "tablet", "mobile"].forEach((viewportName) => {
              const base = element.position?.[viewportName] || createPosition()[viewportName];
              const canvasWidth = viewports[viewportName] || viewports.desktop;
              const targetWidth = viewportName === "mobile" ? 360 : 760;
              const targetHeight = 770;

              nextPosition[viewportName] = {
                ...base,
                width: Math.min(Math.max(Number(base.width) || targetWidth, targetWidth), canvasWidth - 24),
                height: Math.max(Number(base.height) || targetHeight, targetHeight),
              };
            });

            return { ...element, position: { ...(element.position || {}), ...nextPosition } };
          };

          if (section.mode === "direct") {
            return {
              ...section,
              freeElements: (section.freeElements || []).map(resizeElement),
            };
          }

          return {
            ...section,
            rows: (section.rows || []).map((row) => ({
              ...row,
              columns: (row.columns || []).map((column) => ({
                ...column,
                elements: (column.elements || []).map(resizeElement),
              })),
            })),
          };
        }),
      })),
    }));
  };

  const openReservationBlockOnPage = (elementId, pageId) => {
    resizeReservationBlockForEditing(elementId);
    selectReservationBlock(elementId, pageId);
    setActiveTab("design");
    setDesignPanel("Sections");
  };

  const deleteReservationBlock = (elementId, pageId) => {
    const item = reservationBlocks.find((block) => block.element.id === elementId);
    selectReservationBlock(elementId, pageId);
    setElementPendingDelete({
      id: elementId,
      name: item?.element?.reservation?.title || item?.element?.name || "Reservation block",
    });
  };

  const updateSelectedElementPlacement = (value) => {
    const alignSelf = normalizeElementAlignSelf(value);
    const isDirectional = isDirectionalElementPlacement(value);

    updateSelectedElement({
      styles: {
        alignSelf,
        width:
          alignSelf === "stretch"
            ? "100%"
            : isDirectional
              ? getElementLayoutWidth(selectedElement?.styles?.width, alignSelf)
              : selectedElement?.styles?.width,
      },
    });
  };

  const deleteSelectedElement = () => {
    if (!selectedElement) return;
    setElementPendingDelete({
      id: selectedElement.id,
      name: selectedElement.name || "Element",
    });
  };

  useEffect(() => {
    if (
      activeTab !== "design" ||
      preview ||
      modal ||
      elementPendingDelete ||
      !selectedElement
    ) {
      return undefined;
    }

    const handleElementDeleteKey = (event) => {
      const isDeleteKey =
        event.key === "Delete" ||
        event.key === "Del" ||
        event.code === "Delete" ||
        event.keyCode === 46;
      const isBackspaceKey =
        event.key === "Backspace" ||
        event.code === "Backspace" ||
        event.keyCode === 8;

      if (
        (!isDeleteKey && !isBackspaceKey) ||
        event.defaultPrevented ||
        event.repeat
      ) {
        return;
      }

      const target = event.target;
      if (
        target instanceof Element &&
        target.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])")
      ) {
        return;
      }

      event.preventDefault();
      setElementPendingDelete({
        id: selectedElement.id,
        name: selectedElement.name || "Element",
      });
    };

    document.addEventListener("keydown", handleElementDeleteKey, true);
    return () => document.removeEventListener("keydown", handleElementDeleteKey, true);
  }, [activeTab, elementPendingDelete, modal, preview, selectedElement]);

  const confirmDeleteSelectedElement = () => {
    if (!elementPendingDelete?.id) return;
    const elementId = elementPendingDelete.id;

    updateSections((sections) =>
      sections.map((section) => {
        if (section.mode === "direct") {
          return {
            ...section,
            freeElements: section.freeElements.filter((element) => element.id !== elementId),
          };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.filter((element) => element.id !== elementId),
            })),
          })),
        };
      })
    );

    setSelected({ type: "page", id: activePage.id });
    setElementPendingDelete(null);
    showToast("Element deleted.");
  };

  const confirmDeletePendingUser = () => {
    if (!userPendingDelete?.id) return;
    const userId = userPendingDelete.id;

    updateProject((prev) => ({
      ...prev,
      users: (prev.users || []).filter((item) => item.id !== userId),
    }));

    if (selected.type === "user" && selected.id === userId) {
      setSelected({ type: "page", id: activePage?.id || project.activePageId || null });
    }

    setUserPendingDelete(null);
    showToast("User deleted.");
  };

  const findElementLocation = useCallback(
    (elementId) => findElementLocationInPage(activePage, elementId),
    [activePage]
  );

  const {
    addUser,
    updateUser,
    deleteUser,
    addRole,
    updateRole,
  } = useMemo(
    // eslint-disable-next-line react-hooks/refs
    () => createUserHandlers({
      project,
      updateProject,
      setSelected,
      showToast,
      createRole,
      createUser,
      requestDeleteUser: setUserPendingDelete,
    }),
    [project, updateProject, showToast]
  );
  const setAnswer = useCallback((formId, fieldId, value) => {
    setRuntimeAnswers((prev) => ({
      ...prev,
      [formId]: {
        ...(prev[formId] || {}),
        [fieldId]: value,
      },
    }));

    setRuntimeErrors((prev) => {
      const next = { ...prev };
      delete next[fieldId];
      return next;
    });
  }, []);

  const resetQuizSession = (formId) => {
    setQuizSessions((prev) => {
      const next = { ...prev };
      delete next[formId];
      return next;
    });
  };

  const lockFocusedQuizAttempt = useCallback((formId) => {
    setQuizSessions((prev) => {
      const session = prev[formId];
      if (!session?.active || session.locked) return prev;

      return {
        ...prev,
        [formId]: {
          ...session,
          active: false,
          locked: true,
          lockedReason: "Focus mode was interrupted. This quiz cannot be continued or retaken.",
        },
      };
    });

    showToast("Focus mode was interrupted. This quiz cannot be retaken.");
  }, [showToast]);

  const startQuizSession = useCallback((form) => {
    const settings = getQuizSettings(form);
    if (quizSessions[form.id]?.locked) {
      showToast("Focus mode was interrupted. This quiz cannot be retaken.");
      return;
    }

    const fields = getFormFields(form);
    const firstField = fields[0];
    const firstQuestionLimit = Number(
      firstField?.quizTimeLimitSec || settings.questionTimeLimitSec || 0
    );

    setQuizSessions((prev) => ({
      ...prev,
      [form.id]: {
        active: true,
        currentIndex: 0,
        totalRemaining: Number(settings.totalTimeLimitSec || 0),
        questionRemaining: firstQuestionLimit,
      },
    }));

    if (settings.lockScreen) {
      document.documentElement.requestFullscreen?.().catch(() => undefined);
    }
  }, [quizSessions, showToast]);

  const moveQuizQuestion = useCallback((form, direction) => {
    const fields = getFormFields(form);
    const settings = getQuizSettings(form);

    setQuizSessions((prev) => {
      const current = prev[form.id] || { active: true, currentIndex: 0 };
      const delta = direction === "previous" ? -1 : 1;
      const currentIndex = Math.max(
        0,
        Math.min(fields.length - 1, Number(current.currentIndex || 0) + delta)
      );
      const field = fields[currentIndex];
      const questionLimit = Number(
        field?.quizTimeLimitSec || settings.questionTimeLimitSec || 0
      );

      return {
        ...prev,
        [form.id]: {
          ...current,
          active: true,
          currentIndex,
          questionRemaining: questionLimit,
        },
      };
    });
  }, []);

  const submitRuntimeForm = useCallback((form, { skipValidation = false } = {}) => {
    const enteredAnswers = runtimeAnswers[form.id] || {};
    const answers = getFormFields(form).reduce((acc, field) => {
      if (enteredAnswers[field.id] !== undefined) {
        acc[field.id] = normalizeRuntimeAnswerValue(enteredAnswers[field.id]);
      } else if (field.defaultValue) {
        acc[field.id] = normalizeRuntimeAnswerValue(field.defaultValue);
      }
      return acc;
    }, {});
    const nextErrors = {};

    if (!skipValidation) {
      getFormFields(form).forEach((field) => {
        if (!field.required) return;
        const value = answers[field.id];

        if (
          value === undefined ||
          value === null ||
          value === "" ||
          (Array.isArray(value) && value.length === 0)
        ) {
          nextErrors[field.id] = "This field is required.";
        }
      });
    }

    setRuntimeErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) return;

    const quizResult = form.mode === "quiz" ? gradeQuizResponse(form, answers) : null;
    setRuntimeAnswers((prev) => ({ ...prev, [form.id]: {} }));
    resetQuizSession(form.id);
    if (form.mode === "quiz" && document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => undefined);
    }
    if (form.mode === "quiz" && quizResult && getQuizSettings(form).showResults) {
      if (quizResult.score === null) {
        showToast("Quiz submitted. This quiz needs manual review.");
      } else {
        showToast(`Quiz submitted. Score: ${quizResult.score}% (${quizResult.correct}/${quizResult.total}).`);
      }
    } else {
      showToast(form.successMessage);
    }
  }, [runtimeAnswers, showToast]);

  const runElementAction = useCallback(
    (element) => runElementActionWithHandlers({
      element,
      selectPage,
      getStoredUrlError,
      showToast,
    }),
    [selectPage, showToast]
  );

  const persistProject = useCallback((nextProject, message, options = {}) =>
    persistBuilderProject({
      nextProject,
      message,
      demoMode,
      storageKey: scopedStorageKey,
      setProject,
      showToast,
      silent: Boolean(options.silent),
    }), [demoMode, scopedStorageKey, showToast]);

  const saveSingleProjectRevision = useCallback(async ({ nextProject, silent, repairs = [] }) => {
    const urlErrors = collectBuilderUrlErrors(nextProject);
    if (urlErrors.length > 0) {
      if (!silent) showToast(urlErrors[0]);
      return false;
    }

    if (demoMode) {
      persistProject(nextProject, "Changes saved for this preview.", { silent });
      return true;
    }
    if (builderProjectLoading) {
      if (!silent) showToast("Still loading your site. Try saving again in a moment.");
      return false;
    }

    if (silent && repairs.length === 0) {
      persistProjectNow(nextProject);
    } else {
      persistProject(nextProject, "Saving your changes...", { silent });
    }

    try {
      const currentRecord = builderProjectRecordRef.current;
      const payload = createBuilderProjectPayload({
        project: nextProject,
        builderProjectRecord: currentRecord,
        getBuilderProjectName,
        getBuilderProjectSlug,
      });
      const savedRecord = currentRecord?.id
        ? await updateBuilderProject(currentRecord.id, payload, userId)
        : await createBuilderProject(payload, userId);

      builderProjectRecordRef.current = savedRecord;
      setBuilderProjectRecord(savedRecord);
      backendProjectSnapshotRef.current = getAutosaveSnapshot(nextProject);
      pendingBackendProjectSnapshotRef.current = "";
      if (!silent) {
        showToast(repairs.length > 0
          ? "Duplicate internal IDs were repaired and your changes are saved."
          : "Your changes are saved.");
      }
      return true;
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error("Could not save builder project.");
      }
      if (isLikelySessionFailure(error)) {
        if (!silent) {
          showToast("Please sign in again, then save your changes.");
        }
        return false;
      }

      if (isBuilderRevisionError(error)) {
        showToast(getBuilderConflictMessage(error));
        return false;
      }

      if (!silent) {
        showToast("Your changes are safe here. Please try saving again.");
      }
      return false;
    }
  }, [builderProjectLoading, demoMode, persistProject, persistProjectNow, showToast, userId]);

  const saveProject = useCallback(({ silent = false, projectOverride = null } = {}) => {
    if (hasProtectedUnreadableDraft) {
      if (!silent) {
        showToast("The stored draft is unreadable and was preserved. Export your current view before resolving it.");
      }
      return Promise.resolve(false);
    }

    const sourceProject = projectOverride || projectRef.current;
    const nextProject = silent
      ? sourceProject
      : {
          ...sourceProject,
          publish: {
            ...(sourceProject.publish || {}),
            lastSavedAt: new Date().toISOString(),
          },
        };
    const repaired = cleanBuilderProjectWithRepairs(nextProject);
    const request = {
      nextProject: repaired.project,
      silent,
      repairs: repaired.repairs,
      snapshot: getAutosaveSnapshot(repaired.project),
    };

    if (!silent) setActiveTopbarAction("save");
    if (remoteSaveInFlightRef.current) {
      if (
        silent &&
        (request.snapshot === remoteSaveActiveSnapshotRef.current ||
          request.snapshot === pendingRemoteSaveRef.current?.snapshot)
      ) {
        return remoteSavePromiseRef.current || Promise.resolve(false);
      }
      pendingRemoteSaveRef.current = request;
      return remoteSavePromiseRef.current || Promise.resolve(false);
    }

    remoteSaveInFlightRef.current = true;
    setIsSavingProject(true);
    remoteSavePromiseRef.current = (async () => {
      let currentRequest = request;
      let result = false;
      while (currentRequest) {
        pendingRemoteSaveRef.current = null;
        remoteSaveActiveSnapshotRef.current = currentRequest.snapshot;
        result = await saveSingleProjectRevision(currentRequest);
        currentRequest = pendingRemoteSaveRef.current;
      }
      return result;
    })().finally(() => {
      remoteSaveInFlightRef.current = false;
      remoteSaveActiveSnapshotRef.current = "";
      remoteSavePromiseRef.current = null;
      setIsSavingProject(false);
    });

    return remoteSavePromiseRef.current;
  }, [hasProtectedUnreadableDraft, saveSingleProjectRevision, showToast]);

  useEffect(() => {
    if (demoMode || builderProjectLoading) return;
    if (!project) return;

    const currentSnapshot = getAutosaveSnapshot(project);
    if (!currentSnapshot) return;
    if (
      currentSnapshot === backendProjectSnapshotRef.current ||
      currentSnapshot === pendingBackendProjectSnapshotRef.current
    ) {
      return;
    }

    window.clearTimeout(backendAutosaveTimerRef.current);
    backendAutosaveTimerRef.current = window.setTimeout(() => {
      if (dragStateRef.current || isBuilderTextEditingTarget(document.activeElement)) return;
      pendingBackendProjectSnapshotRef.current = currentSnapshot;
      saveProject({ silent: true, projectOverride: project }).finally(() => {
        pendingBackendProjectSnapshotRef.current = "";
      });
    }, 7000);

    return () => {
      window.clearTimeout(backendAutosaveTimerRef.current);
    };
  }, [builderProjectLoading, demoMode, project, saveProject]);

  useEffect(() => {
    if (demoMode || builderProjectLoading) return undefined;
    backendBackupAutosaveTimerRef.current = window.setInterval(() => {
      const latestProject = projectRef.current;
      if (!latestProject || dragStateRef.current || isBuilderTextEditingTarget(document.activeElement)) return;
      const latestSnapshot = getAutosaveSnapshot(latestProject);
      if (latestSnapshot === backendProjectSnapshotRef.current) return;
      saveProject({ silent: true, projectOverride: latestProject });
    }, 120000);
    return () => window.clearInterval(backendBackupAutosaveTimerRef.current);
  }, [builderProjectLoading, demoMode, saveProject]);

  useEffect(() => {
    if (demoMode || builderProjectLoading) return undefined;
    const saveLatestIfSafe = () => {
      if (dragStateRef.current || isBuilderTextEditingTarget(document.activeElement)) return;
      const latestProject = projectRef.current;
      if (!latestProject || getAutosaveSnapshot(latestProject) === backendProjectSnapshotRef.current) return;
      saveProject({ silent: true, projectOverride: latestProject });
    };
    const handleVisibility = () => {
      if (document.visibilityState === "hidden") saveLatestIfSafe();
    };
    window.addEventListener("blur", saveLatestIfSafe);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("blur", saveLatestIfSafe);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [builderProjectLoading, demoMode, saveProject]);

  const saveThemeProject = async () => {
    setActiveTopbarAction("theme");

    if (hasProtectedUnreadableDraft) {
      showToast("The stored draft is unreadable and was preserved. Theme saving is paused for safety.");
      return;
    }

    const nextProject = {
      ...project,
      publish: {
        ...project.publish,
        lastSavedAt: new Date().toISOString(),
      },
    };

    if (demoMode) {
      persistProject(nextProject, "Your theme changes are saved.");
      return;
    }

    if (builderProjectLoading) {
      showToast("Your site is still getting ready. Please try again in a moment.");
      return;
    }

    persistProject(nextProject, "Saving website theme...");

    try {
      const payload = createBuilderProjectPayload({
        project: nextProject,
        builderProjectRecord,
        getBuilderProjectName,
        getBuilderProjectSlug,
      });

      const savedRecord = builderProjectRecord?.id
        ? await updateBuilderProject(builderProjectRecord.id, payload, user?.id)
        : await createBuilderProject(payload, user?.id);

      setBuilderProjectRecord(savedRecord);
      showToast("Website theme saved.");
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error("Could not save website theme.");
      }
      if (isLikelySessionFailure(error)) {
        showToast("Please sign in again, then save your theme.");
        return;
      }

      if (isBuilderRevisionError(error)) {
        showToast(getBuilderConflictMessage(error));
        return;
      }

      showToast("Your theme changes are safe here. Please try saving again.");
    }
  };

  const loadProject = async () => {
    if (demoMode) {
      const freshProject = cleanBuilderProject(createInitialProject());
      setProject(freshProject);
      setSelected({ type: "page", id: freshProject.activePageId });
      showToast("Default demo template loaded.");
      return;
    }

    try {
      const projects = await listBuilderProjects(user?.id);
      const selectedProject = projects[0] || null;

      if (selectedProject) {
        const fullRecord = await fetchBuilderProject(selectedProject.id, user?.id);
        const loadedProject = getDraftProjectFromRecord(fullRecord);

        if (loadedProject) {
          const nextProject = isDefaultShowcaseProject(loadedProject)
            ? createCleanBlankProject()
            : loadedProject;

          setBuilderProjectRecord(fullRecord);
          setProject(nextProject);
          setSelected({ type: "page", id: nextProject.activePageId });
          persistProjectNow(nextProject);
          backendProjectSnapshotRef.current = getAutosaveSnapshot(nextProject);

          showToast(
            isDefaultShowcaseProject(loadedProject)
              ? "Blank builder canvas loaded."
              : "Loaded backend project."
          );
          return;
        }
      }
    } catch {
      if (import.meta.env.DEV) {
        console.warn("Could not load backend builder project.");
      }
    }

    const raw = localStorage.getItem(scopedStorageKey);
    if (!raw) {
      alert("No backend project or local draft cache found.");
      return;
    }

    try {
      const loaded = cleanBuilderProject(JSON.parse(raw));
      const nextProject = isDefaultShowcaseProject(loaded)
        ? createCleanBlankProject()
        : loaded;
      setProject(nextProject);
      setSelected({ type: "page", id: nextProject.activePageId });
      showToast(
        isDefaultShowcaseProject(loaded)
          ? "Blank builder canvas loaded."
          : "Your saved site is ready."
      );
      backendProjectSnapshotRef.current = getAutosaveSnapshot(nextProject);
    } catch {
      alert("Saved project is not valid JSON.");
    }
  };

  const publicSiteSubdomain = sanitizeSubdomain(
    websiteSettings?.subdomain || project?.publish?.subdomain || ""
  );
  const canonicalLiveSitePath = publicSiteSubdomain
    ? resolveLiveSitePath(publicSiteSubdomain)
    : liveSitePath;

  const publishProject = async (skipOverlapCheck = false) => {
    setActiveTopbarAction("publish");
    setToast("");

    if (hasProtectedUnreadableDraft) {
      showToast("The stored draft is unreadable and was preserved. Publishing is paused for safety.");
      return;
    }

    if (!publicSiteSubdomain) {
      setActiveTab("publish");
      showToast("Choose your website address before going live.");
      return;
    }

    const pageRoutingIssues = collectPublicPageRoutingIssues(project);
    if (pageRoutingIssues.length > 0) {
      const issue = pageRoutingIssues[0];
      if (issue.page_id) {
        updateProject((prev) => ({ ...prev, activePageId: issue.page_id }));
        setSelected({ type: "page", id: issue.page_id });
      }
      setActiveTab("design");
      setDesignPanel("Pages");
      showToast("Review the homepage and page links before going live.");
      return;
    }

    const projectIdIssues = collectProjectIdIssues(project);
    if (projectIdIssues.length > 0) {
      showToast(getProjectIdIssueMessage(projectIdIssues[0]));
      return;
    }

    const formConnectionIssues = collectFormConnectionIssues(project);
    if (formConnectionIssues.length > 0) {
      const issue = formConnectionIssues[0];
      const target = getFormConnectionFocusTarget(issue);
      if (project.activePageId !== target.pageId) {
        updateProject((prev) => ({ ...prev, activePageId: target.pageId }));
      }
      setSelected(target.selection);
      setActiveTab("design");
      setDesignPanel("Pages");
      showToast(getFormConnectionIssueMessage(issue));
      return;
    }

    const savedAt = new Date().toISOString();
    const draftForPublish = {
      ...project,
      publish: {
        ...project.publish,
        lastSavedAt: savedAt,
      },
    };
    const publishedProject = {
      ...draftForPublish,
      status: "published",
      publish: {
        ...draftForPublish.publish,
        lastPublishedAt: new Date().toISOString(),
      },
    };
    const buttonActionIssues = collectButtonActionIssues(publishedProject);
    if (buttonActionIssues.length > 0) {
      const issue = buttonActionIssues[0];
      updateProject((prev) => ({ ...prev, activePageId: issue.page_id }));
      setSelected({ type: "element", id: issue.block_id });
      setActiveTab("design");
      setDesignPanel("Pages");
      const messages = {
        invalid_button_page_target: "Choose a valid destination page for this button before publishing.",
        invalid_button_url: "Enter a valid HTTPS URL for this button before publishing.",
        empty_button_message: "Enter a message for this button before publishing.",
      };
      showToast(messages[issue.issue_type] || "Review this button action before publishing.");
      return;
    }
    const urlErrors = collectBuilderUrlErrors(publishedProject);

    if (urlErrors.length > 0) {
      showToast(urlErrors[0]);
      return;
    }

    const overlapWarnings = getProjectOverlapWarnings(publishedProject);

    if (!skipOverlapCheck && overlapWarnings.length > 0) {
      setPublishOverlapWarnings(overlapWarnings);
      return;
    }

    setPublishOverlapWarnings([]);

    if (demoMode) {
      persistProject(publishedProject, "Your site is live for this preview.");
      return;
    }

    if (builderProjectLoading) {
      showToast("Your site is still getting ready. Please try Go Live again in a moment.");
      return;
    }

    persistProject(project, "Getting your site ready...");

    try {
      const payload = createBuilderProjectPayload({
        project: draftForPublish,
        builderProjectRecord,
        getBuilderProjectName,
        getBuilderProjectSlug,
      });

      const savedRecord = builderProjectRecord?.id
        ? await updateBuilderProject(builderProjectRecord.id, payload, user?.id)
        : await createBuilderProject(payload, user?.id);

      setBuilderProjectRecord(savedRecord);
      backendProjectSnapshotRef.current = getAutosaveSnapshot(draftForPublish);

      const publishResponse = await publishBuilderProject(
        savedRecord.id,
        savedRecord?.draft_revision
      );
      const publishedRecord = publishResponse?.project || savedRecord;
      const publishedSite = publishResponse?.site || {};
      const resolvedPublicSubdomain = sanitizeSubdomain(
        publishedSite?.subdomain || websiteSettings?.subdomain || project?.publish?.subdomain || ""
      );
      const resolvedLiveSitePath = resolvedPublicSubdomain
        ? resolveLiveSitePath(resolvedPublicSubdomain)
        : "";

      // The server publish has already committed at this point. Reflect that
      // durable state even if the optional public-link metadata is incomplete.
      setBuilderProjectRecord(publishedRecord);
      persistProject(publishedProject, "");
      backendProjectSnapshotRef.current = getAutosaveSnapshot(publishedProject);
      pendingBackendProjectSnapshotRef.current = "";

      if (import.meta.env.DEV) {
        console.debug("Builder publish completed.");
      }

      if (!resolvedLiveSitePath) {
        showToast("Your site is live, but its public link could not be loaded. Refresh the Publish page.");
        return;
      }

      setLiveSitePath(resolvedLiveSitePath);
      showToast("Your site is live. Go to the Publish page to open your website.");
    } catch (error) {
      console.error("Could not publish builder project:", error);

      if (isLikelySessionFailure(error)) {
        showToast("Please sign in again, then choose Go Live.");
        return;
      }

      if (isBuilderRevisionError(error)) {
        showToast(getBuilderConflictMessage(error));
        return;
      }

      if (isBuilderError(error, "entitlement_pending")) {
        showToast("Your publishing access is still pending. No changes were lost.");
        return;
      }

      if (
        isBuilderError(error, "entitlement_inactive") ||
        isBuilderError(error, "payment_required")
      ) {
        showToast("Publishing is not active for this workspace. Review your plan; your edits are still saved locally.");
        return;
      }

      if (isBuilderError(error, "publish_validation_failed")) {
        if (String(error.context?.issue_type || "").includes("_id")) {
          showToast(getProjectIdIssueMessage(error.context));
          return;
        }
        const issue = error.context?.issue_type === "orphaned_form_block"
          ? error.context
          : null;
        if (issue) {
          if (issue.page_id) updateProject((prev) => ({ ...prev, activePageId: issue.page_id }));
          if (issue.block_id) setSelected({ type: "element", id: issue.block_id });
          setActiveTab("design");
          setDesignPanel("Pages");
          showToast(getFormConnectionIssueMessage(issue));
        } else {
          showToast(error.message || "This draft is not ready to publish. Review the highlighted content.");
        }
        return;
      }

      showToast("We couldn't put your site live. Please try again.");
    }
  };

  const unpublishProject = async () => {
    if (!builderProjectRecord?.id || project.status !== "published") return;
    if (!window.confirm("Take this website offline? The current published content will be preserved for a later republish.")) {
      return;
    }

    setIsUnpublishingProject(true);

    try {
      const response = await unpublishBuilderProject(
        builderProjectRecord.id,
        builderProjectRecord.draft_revision
      );
      const nextRecord = response?.project || builderProjectRecord;
      const unpublishedProject = {
        ...project,
        status: "draft",
      };

      setBuilderProjectRecord(nextRecord);
      persistProject(unpublishedProject, "Your website is offline. Its last published version is preserved.");
      setLiveSitePath("");
      backendProjectSnapshotRef.current = getAutosaveSnapshot(unpublishedProject);
    } catch (error) {
      if (isLikelySessionFailure(error)) {
        showToast("Please sign in again before taking this site offline.");
      } else if (isBuilderRevisionError(error)) {
        showToast(getBuilderConflictMessage(error));
      } else if (isBuilderError(error, "project_not_published")) {
        showToast("This website is already offline.");
      } else {
        showToast("We could not take the website offline. It remains published.");
      }
    } finally {
      setIsUnpublishingProject(false);
    }
  };

  const exportProject = () => exportBuilderProjectJson({ project, showToast });

  const applyStarter = (starterId) => {
    rememberStarterChoice();

    if (starterId === "blankPage") {
      const canvasSection = createBlankCanvasSection();
      const page = createPage(`Page ${project.pages.length + 1}`, [canvasSection], {
        canvasLayoutVersion: 1,
      });

      updateProject((prev) => ({
        ...prev,
        pages: [...prev.pages, page],
        activePageId: page.id,
      }));
      setSelected({ type: "section", id: canvasSection.id });
      setActiveTab("design");
      setDesignPanel("Sections");
      setModal(null);
      showToast("Blank page created.");
      return;
    }

    const starter = cleanBuilderProject(buildStarterProject(starterId));
    setProject(starter);
    setSelected({ type: "page", id: starter.activePageId });
    setActiveTab("design");
    setModal(null);
  };

  const getFormPlacements = (formId) => getFormPlacementsFromProject(project, formId);

  const addConnectedFormSectionToPage = (formId, pageId = project.activePageId) => {
    if (!formId || !pageId) return;

    const section = formSection(formId);

    updateProject((prev) => ({
      ...prev,
      activePageId: pageId,
      activeFormId: formId,
      pages: prev.pages.map((page) =>
        page.id === pageId ? { ...page, sections: [...page.sections, section] } : page
      ),
    }));

    setSelected({ type: "section", id: section.id });
    setActiveTab("design");
    setDesignPanel("Sections");
    showToast("Form added to the selected page.");
  };

  const getElementStyle = useCallback((element) =>
    getBuilderElementStyle({
      element,
      selected,
      carouselElementTypes,
      getElementPlacementMargins,
      getElementLayoutWidth,
      normalizeElementAlignSelf,
    }), [selected]);

  const getFreeElementStyle = useCallback((element) =>
    getBuilderFreeElementStyle({
      element,
      viewport,
      activePage,
      viewports,
      createPosition,
      findElementLocation,
      getSectionCanvasHeight,
      getMetricMinimumHeight,
      getDirectElementMinimumSize,
    }), [activePage, findElementLocation, viewport]);

  const getDirectElementFrameStyle = (element) => {
    const previewPosition = dragState?.elementId === element.id ? dragState.previewPosition : null;
    const renderedElement = previewPosition
      ? {
          ...element,
          position: { ...(element.position || {}), [viewport]: previewPosition },
        }
      : element;
    const style = getFreeElementStyle(renderedElement);

    if (element.type !== "formBlock") return style;

    const edge = viewport === "mobile" ? 12 : 24;
    const position = renderedElement.position?.[viewport] || createPosition()[viewport];
    const y = Math.max(0, Number(position.y) || 0);

    return {
      ...style,
      width: `calc(100% - ${edge * 2}px)`,
      height: "auto",
      maxWidth: `calc(100% - ${edge * 2}px)`,
      transform: `translate3d(${edge}px, ${y}px, 0)`,
    };
  };

  const restorePreviousDraft = () => {
    const rawBackup = localStorage.getItem(`${scopedStorageKey}:backup`);
    if (!rawBackup) {
      showToast("No previous browser draft was found.");
      return;
    }

    if (!window.confirm("Restore the previous browser draft? Your current draft will be kept as the next backup.")) return;

    try {
      const restoredProject = withDefaultLandingPage(cleanBuilderProject(JSON.parse(rawBackup)));
      setProject(restoredProject);
      setSelected({
        type: restoredProject.forms?.length ? "form" : "page",
        id: restoredProject.activeFormId || restoredProject.forms?.[0]?.id || restoredProject.activePageId || null,
      });
      persistProjectNow(restoredProject);
      showToast("Previous draft restored. Check your form, then press Save form.");
    } catch {
      showToast("The previous browser draft could not be restored.");
    }
  };

  const reconcileDirectFormBlockSize = useCallback((sectionId, elementId, measuredHeight) => {
    if (!measuredHeight || dragState?.elementId === elementId) return;

    const canvasWidth = viewports[viewport] || viewports.desktop;
    const edge = viewport === "mobile" ? 12 : 24;
    const nextWidth = Math.max(120, canvasWidth - edge * 2);

    updateProject((prev) => {
      let projectChanged = false;
      const pages = prev.pages.map((page) => {
        if (page.id !== activePage?.id) return page;

        let pageChanged = false;
        const sections = page.sections.map((section) => {
          if (section.id !== sectionId) return section;

          let formY = 0;
          let geometryChanged = false;
          const freeElements = (section.freeElements || []).map((item) => {
            if (item.id !== elementId || item.type !== "formBlock") return item;

            const current = item.position?.[viewport] || createPosition()[viewport];
            formY = Number(current.y) || 0;
            const nextPosition = { ...current, x: edge, width: nextWidth, height: measuredHeight };
            const changed =
              Math.abs((Number(current.x) || 0) - nextPosition.x) > 1 ||
              Math.abs((Number(current.width) || 0) - nextPosition.width) > 1 ||
              Math.abs((Number(current.height) || 0) - nextPosition.height) > 1;
            if (!changed) return item;

            geometryChanged = true;
            return {
              ...item,
              position: { ...(item.position || {}), [viewport]: nextPosition },
            };
          });

          const currentSectionHeight = getSectionCanvasHeight(section, viewport);
          const nextSectionHeight = Math.max(currentSectionHeight, formY + measuredHeight + edge);
          if (!geometryChanged && nextSectionHeight === currentSectionHeight) return section;

          pageChanged = true;
          return {
            ...section,
            layout: {
              ...(section.layout || {}),
              minHeight: viewport === "desktop" ? nextSectionHeight : section.layout?.minHeight,
              minHeightByViewport: {
                ...(section.layout?.minHeightByViewport || {}),
                [viewport]: nextSectionHeight,
              },
            },
            freeElements,
          };
        });

        if (!pageChanged) return page;
        projectChanged = true;
        return { ...page, sections };
      });

      return projectChanged ? { ...prev, pages } : prev;
    });
  }, [activePage?.id, dragState?.elementId, updateProject, viewport]);

  const {
    handleSelectedElementImageUpload,
    handleSiteLogoUpload,
    handleCarouselSlideImageUpload,
  } = useMemo(
    // eslint-disable-next-line react-hooks/refs
    () => createUploadHandlers({
      selectedElement,
      carouselElementTypes,
      defaultSiteChrome,
      builderAssetMimeTypes,
      builderAssetMaxBytes,
      uploadBuilderAsset,
      user,
      setAssetUploadBusy,
      updateSelectedElement,
      updateProject,
      showToast,
      parseCarouselSlides,
      serializeCarouselSlides,
    }),
    [selectedElement, user, updateSelectedElement, updateProject, showToast]
  );
  const getElementSection = (elementId) =>
    getElementSectionFromPage({
      page: activePage,
      elementId,
      findElementLocation,
    });

  const getProjectOverlapWarnings = (projectToCheck) =>
    getProjectOverlapWarningsFromLayout({
      project: projectToCheck,
      createPosition,
      positionsOverlap,
    });

  const handlePreviewClick = () => {
    if (preview) {
      setPreview(false);
      showToast("Preview closed.");
      return;
    }

    const overlapWarnings = getProjectOverlapWarnings(project);

    if (overlapWarnings.length > 0) {
      setPreviewOverlapWarnings(overlapWarnings);
      showToast("Preview blocked. Fix the overlapping elements first.");
      return;
    }

    setPreview(true);
    showToast("Preview mode on.");
  };

  const startDrag = useCallback((event, element, interaction = "move", forceInteraction = false) => {
    if (preview || element.mode !== "direct") return;

    const tagName = event.target?.tagName?.toLowerCase();
    const isSelectableText = Boolean(
      event.target?.closest?.(
        ".builder-element-heading, .builder-element-text, .builder-list-title, .builder-element-list li"
      )
    );
    if (
      !forceInteraction &&
      interaction === "move" &&
      (["input", "textarea", "select", "option", "button"].includes(tagName) || isSelectableText)
    ) return;

    event.stopPropagation();
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);

    const current = element.position?.[viewport] || createPosition()[viewport];

    setSelected({ type: "element", id: element.id });
    setDragState({
      elementId: element.id,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: current.x || 0,
      startY: current.y || 0,
      startWidth: current.width || 240,
      startHeight: current.height || 80,
      pointerId: event.pointerId,
      previewPosition: { ...current },
      previewSectionHeight: 0,
      interaction,
    });
  }, [preview, viewport]);

  const captureTextSelection = (event, field, itemIndex = null) => {
    setTextSelection(
      createInputTextSelection({
        elementId: selectedElement?.id,
        field,
        itemIndex,
        selectionStart: event.currentTarget.selectionStart,
        selectionEnd: event.currentTarget.selectionEnd,
      })
    );
  };

  const positionInlineToolbarNear = useCallback((target) => {
    if (!target || typeof window === "undefined") return;

    const rect = target.getBoundingClientRect();
    const left = Math.min(Math.max(rect.left + rect.width / 2, 18), window.innerWidth - 18);
    const top = Math.min(Math.max(rect.top - 34, 84), window.innerHeight - 18);

    setInlineToolbarPosition({ left, top });
  }, []);

  const captureCanvasTextSelection = useCallback((event, field, itemIndex = null, elementId = selectedElement?.id) => {
    const range = getCanvasTextSelectionRange(event);

    if (!range) return;

    positionInlineToolbarNear(event.currentTarget);

    if (range.collapsed) {
      setTextSelection({
        elementId,
        field,
        itemIndex,
        start: 0,
        end: 0,
      });
      return;
    }

    setTextSelection({
      elementId,
      field,
      itemIndex,
      start: range.start,
      end: range.end,
    });
  }, [positionInlineToolbarNear, selectedElement?.id]);

  const getSelectedTextTargetValue = () => {
    if (!selectedElement || textSelection?.elementId !== selectedElement.id) return "";

    if (textSelection.field === "listTitle") {
      return selectedElement.listTitle || "";
    }

    if (textSelection.field === "listItem") {
      return getListItems(selectedElement)[textSelection.itemIndex] || "";
    }

    return selectedElement.content || "";
  };

  const getSelectedTextRange = () => {
    if (!selectedElement || textSelection?.elementId !== selectedElement.id) return null;

    const targetText = getSelectedTextTargetValue();
    const targetLength = targetText.length;
    if (!targetLength) return null;

    const start = Number(textSelection.start) || 0;
    const end = Number(textSelection.end) || 0;

    return {
      field: textSelection.field || "content",
      itemIndex: textSelection.itemIndex ?? null,
      start: start === end ? 0 : Math.max(0, Math.min(start, targetLength)),
      end: start === end ? targetLength : Math.max(0, Math.min(end, targetLength)),
    };
  };

  const selectedTextTargetIsListPart = () =>
    selectedElement?.type === "list" &&
    textSelection?.elementId === selectedElement.id &&
    (textSelection.field === "listTitle" || textSelection.field === "listItem");

  const getSelectedTextRangeStyle = (property) => {
    const selectedRange = getSelectedTextRange();
    if (!selectedElement || !selectedRange) return "";

    const ranges = [
      ...(selectedElement.richTextColors || []),
      ...(selectedElement.richTextSizes || []),
      ...(selectedElement.richTextStyles || []),
    ];

    return [...ranges].reverse().find(
      (range) =>
        range.field === selectedRange.field &&
        (range.itemIndex ?? null) === selectedRange.itemIndex &&
        range.start <= selectedRange.start &&
        range.end >= selectedRange.end &&
        range[property]
    )?.[property] || "";
  };

  const applyTextColor = (color) => {
    const selectedRange = getSelectedTextRange();

    if (!selectedRange) {
      updateSelectedElement({ styles: { color, selectedTextColor: color } });
      return;
    }

    updateSelectedElement({
      richTextColors: [
        ...(selectedElement.richTextColors || []),
        { ...selectedRange, color },
      ],
      styles: { selectedTextColor: color },
    });
    window.getSelection()?.removeAllRanges();
  };

  const getSelectedElementFontSizeNumber = () => {
    const rawSize = String(selectedElement?.styles?.fontSize || "").trim();
    const parsed = Number.parseInt(rawSize, 10);

    if (Number.isFinite(parsed) && parsed > 0) return parsed;
    if (selectedElement?.type === "heading") return 46;
    if (selectedElement?.type === "button") return 16;
    return 17;
  };

  const applyTextFontSize = (value) => {
    const numericValue = Math.max(8, Math.min(120, Number.parseInt(value, 10) || 17));
    const fontSize = `${numericValue}px`;
    const selectedRange = getSelectedTextRange();

    if (!selectedRange) {
      updateSelectedElement({ styles: { fontSize } });
      return;
    }

    updateSelectedElement({
      richTextSizes: [
        ...(selectedElement.richTextSizes || []),
        { ...selectedRange, fontSize },
      ],
      styles: { selectedTextFontSize: fontSize },
    });
    window.getSelection()?.removeAllRanges();
  };

  const selectedElementSupportsInlineTextToolbar = Boolean(
    selected.type === "element" &&
      selectedElement &&
      inlineTextElementTypes.has(selectedElement.type)
  );

  const getInlineTextFormatValue = () => {
    if (!selectedElement) return "text";
    if (selectedElement.type === "heading") return "heading";
    if (selectedElement.type === "button") return "button";
    if (selectedElement.type === "list") {
      if (textSelection?.elementId === selectedElement.id && textSelection.field === "listTitle") {
        return "listTitle";
      }
      if (textSelection?.elementId === selectedElement.id && textSelection.field === "listItem") {
        return "listItem";
      }
      return selectedElement.listStyle === "decimal" ? "numbers" : "bullets";
    }
    return "text";
  };

  const updateSelectedElementTextFormat = (format) => {
    if (!selectedElement) return;

    if (format === "listTitle" || format === "listItem") return;

    if (format === "bullets" || format === "numbers") {
      const listItems =
        selectedElement.type === "list"
          ? getListItems(selectedElement)
          : splitLines(selectedElement.content || "List item");
      updateSelectedElement({
        type: "list",
        listStyle: format === "numbers" ? "decimal" : "disc",
        listItems,
        content: listItems.join("\n"),
      });
      return;
    }

    const content =
      selectedElement.type === "list"
        ? getListItems(selectedElement).join("\n")
        : selectedElement.content;
    updateSelectedElement({
      type: format,
      content,
    });
  };

  const applyInlineTextToolbarAction = (action) => {
    if (!selectedElement) return;

    if (action === "undo" || action === "redo") {
      document.execCommand?.(action);
      return;
    }

    if (action === "bold") {
      if (selectedTextTargetIsListPart()) {
        const selectedRange = getSelectedTextRange();
        if (!selectedRange) return;

        updateSelectedElement({
          richTextStyles: [
            ...(selectedElement.richTextStyles || []),
            { ...selectedRange, fontWeight: "700" },
          ],
        });
        window.getSelection()?.removeAllRanges();
        return;
      }

      updateSelectedElement({
        styles: {
          fontWeight:
            String(selectedElement.styles?.fontWeight || "").includes("700") ||
            String(selectedElement.styles?.fontWeight || "").includes("bold")
              ? ""
              : "700",
        },
      });
      return;
    }

    if (action === "italic") {
      if (selectedTextTargetIsListPart()) {
        const selectedRange = getSelectedTextRange();
        if (!selectedRange) return;

        updateSelectedElement({
          richTextStyles: [
            ...(selectedElement.richTextStyles || []),
            { ...selectedRange, fontStyle: "italic" },
          ],
        });
        window.getSelection()?.removeAllRanges();
        return;
      }

      updateSelectedElement({
        styles: {
          fontStyle: selectedElement.styles?.fontStyle === "italic" ? "" : "italic",
        },
      });
      return;
    }

    if (action === "underline") {
      if (selectedTextTargetIsListPart()) {
        const selectedRange = getSelectedTextRange();
        if (!selectedRange) return;

        updateSelectedElement({
          richTextStyles: [
            ...(selectedElement.richTextStyles || []),
            { ...selectedRange, textDecoration: "underline" },
          ],
        });
        window.getSelection()?.removeAllRanges();
        return;
      }

      updateSelectedElement({
        styles: {
          textDecoration:
            selectedElement.styles?.textDecoration === "underline" ? "" : "underline",
        },
      });
      return;
    }

    if (action === "bullets" || action === "numbers") {
      updateSelectedElementTextFormat(action);
      return;
    }

    if (action.startsWith("align-")) {
      const textAlign = action.replace("align-", "");
      updateSelectedElement({ styles: { textAlign } });
    }
  };

  const renderInlineTextToolbar = () => {
    if (!selectedElementSupportsInlineTextToolbar || !inlineToolbarPosition) return null;

    const selectedRangeFontSize = getSelectedTextRangeStyle("fontSize");
    const toolbarFontSize = Number.parseInt(
      selectedRangeFontSize ||
        selectedElement.styles?.selectedTextFontSize ||
        selectedElement.styles?.fontSize ||
        getSelectedElementFontSizeNumber(),
      10
    );

    return (
      <div
        className="builder-inline-text-toolbar is-floating"
        style={{
          left: `${inlineToolbarPosition.left}px`,
          top: `${inlineToolbarPosition.top}px`,
        }}
        role="toolbar"
        aria-label="Text formatting"
        onClick={(event) => event.stopPropagation()}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <select
          aria-label="Text style"
          value={getInlineTextFormatValue()}
          onChange={(event) => updateSelectedElementTextFormat(event.target.value)}
        >
          {selectedElement.type === "list" && (
            <>
              <option value="listTitle">Main sentence</option>
              <option value="listItem">Bullet point</option>
            </>
          )}
          <option value="text">Text</option>
          <option value="heading">Heading</option>
          <option value="button">Button</option>
          <option value="bullets">Bullets</option>
          <option value="numbers">Numbers</option>
        </select>
        <label className="builder-inline-toolbar-size" title="Text size">
          <span>Size</span>
          <input
            type="number"
            min="8"
            max="120"
            step="1"
            value={toolbarFontSize}
            onChange={(event) => applyTextFontSize(event.target.value)}
          />
        </label>
        {inlineTextToolbarButtons.map((item) => {
          const Icon = item.icon;
          const selectedRangeFontWeight = getSelectedTextRangeStyle("fontWeight");
          const selectedRangeFontStyle = getSelectedTextRangeStyle("fontStyle");
          const selectedRangeTextDecoration = getSelectedTextRangeStyle("textDecoration");
          const isActive =
            (item.id === "bold" &&
              (String(selectedRangeFontWeight || "").includes("700") ||
                String(selectedRangeFontWeight || "").includes("bold") ||
                String(selectedElement.styles?.fontWeight || "").includes("700") ||
                String(selectedElement.styles?.fontWeight || "").includes("bold"))) ||
            (item.id === "italic" &&
              (selectedRangeFontStyle === "italic" || selectedElement.styles?.fontStyle === "italic")) ||
            (item.id === "underline" &&
              (selectedRangeTextDecoration === "underline" || selectedElement.styles?.textDecoration === "underline")) ||
            (item.id === "bullets" &&
              selectedElement.type === "list" &&
              selectedElement.listStyle !== "decimal") ||
            (item.id === "numbers" &&
              selectedElement.type === "list" &&
              selectedElement.listStyle === "decimal") ||
            (item.id.startsWith("align-") &&
              (selectedElement.styles?.textAlign || "left") === item.id.replace("align-", ""));

          return (
            <button
              key={item.id}
              type="button"
              className={isActive ? "is-active" : ""}
              aria-label={item.label}
              title={item.label}
              onClick={() => applyInlineTextToolbarAction(item.id)}
            >
              <Icon size={16} aria-hidden="true" />
            </button>
          );
        })}
        <button
          type="button"
          className={selectedElement.styles?.direction === "ltr" ? "is-active" : ""}
          onClick={() => updateSelectedElement({ styles: { direction: "ltr" } })}
        >
          LTR
        </button>
        <button
          type="button"
          className={selectedElement.styles?.direction === "rtl" ? "is-active" : ""}
          onClick={() => updateSelectedElement({ styles: { direction: "rtl" } })}
        >
          RTL
        </button>
        <label className="builder-inline-toolbar-color" title="Text color">
          <Baseline size={16} aria-hidden="true" />
          <input
            type="color"
            value={selectedElement.styles?.selectedTextColor || selectedElement.styles?.color || "#162033"}
            onChange={(event) => applyTextColor(event.target.value)}
          />
        </label>
        <label className="builder-inline-toolbar-color" title="Background color">
          <Highlighter size={16} aria-hidden="true" />
          <input
            type="color"
            value={selectedElement.styles?.backgroundColor || "#fffdfa"}
            onChange={(event) => updateSelectedElement({ styles: { backgroundColor: event.target.value } })}
          />
        </label>
      </div>
    );
  };

  const handlePointerMove = (event) => {
    if (
      !dragState ||
      !selectedElement ||
      selectedElement.id !== dragState.elementId ||
      (dragState.pointerId !== undefined && event.pointerId !== dragState.pointerId)
    ) return;

    const deltaX = event.clientX - dragState.startClientX;
    const deltaY = event.clientY - dragState.startClientY;
    const section = getElementSection(selectedElement.id);
    if (!section) return;

    const canvasWidth = viewports[viewport] || viewports.desktop;
    const canvasHeight = getSectionCanvasHeight(section, viewport);
    const expandableCanvasHeight = Math.max(
      canvasHeight,
      (Number(dragState.startY) || 0) + Math.max(0, deltaY) + (Number(dragState.startHeight) || 0) + 48
    );
    const candidate = getDragCandidatePosition({
      dragState: { ...dragState, deltaX, deltaY },
      selectedElement,
      canvasWidth,
      canvasHeight: expandableCanvasHeight,
      snapToGrid,
    });
    const constrainedCandidate = dragState.interaction === "resize"
      ? (section.freeElements || [])
          .filter((element) => element.id !== selectedElement.id)
          .reduce((nextCandidate, element) => {
            const spacing = 12;
            const other = element.position?.[viewport] || createPosition()[viewport];
            if (!positionsOverlap(nextCandidate, other, spacing)) return nextCandidate;

            const minimumSize = getDirectElementMinimumSize(selectedElement);
            const clamped = { ...nextCandidate };
            const verticalRangesMeet = nextCandidate.y < other.y + other.height + spacing && nextCandidate.y + nextCandidate.height + spacing > other.y;
            const horizontalRangesMeet = nextCandidate.x < other.x + other.width + spacing && nextCandidate.x + nextCandidate.width + spacing > other.x;
            if (other.x >= dragState.startX + dragState.startWidth + spacing && verticalRangesMeet) {
              clamped.width = Math.max(
                Math.min(minimumSize.width, canvasWidth - nextCandidate.x),
                Math.round(other.x - nextCandidate.x - spacing)
              );
            }
            if (other.y >= nextCandidate.y && horizontalRangesMeet) {
              clamped.height = Math.max(minimumSize.height, Math.round(other.y - nextCandidate.y - spacing));
            }
            return clamped;
          }, candidate)
      : candidate;
    const current = selectedElement.position?.[viewport] || createPosition()[viewport];
    const previewPosition = { ...current, ...constrainedCandidate };
    const dropFrame = dragState.interaction === "move"
      ? getDirectFrameAtPoint(event.clientX, event.clientY)
      : null;
    const dropSectionId = dropFrame?.dataset?.sectionId;

    pendingDragPreviewRef.current = {
      previewPosition,
      previewSectionHeight: Math.max(
        canvasHeight,
        snapToGrid((Number(previewPosition.y) || 0) + (Number(previewPosition.height) || 0) + 48)
      ),
      dropSectionId: dropSectionId && dropSectionId !== section.id ? dropSectionId : "",
    };

    if (dragPreviewFrameRef.current !== null) return;
    dragPreviewFrameRef.current = window.requestAnimationFrame(() => {
      dragPreviewFrameRef.current = null;
      const previewUpdate = pendingDragPreviewRef.current;
      if (!previewUpdate) return;
      setDragState((currentState) => currentState ? { ...currentState, ...previewUpdate } : currentState);
    });
  };

  const handlePointerUp = (event) => {
    if (!dragState || !selectedElement || selectedElement.id !== dragState.elementId) return;

    if (dragPreviewFrameRef.current !== null) {
      window.cancelAnimationFrame(dragPreviewFrameRef.current);
      dragPreviewFrameRef.current = null;
    }
    const finalPreview = pendingDragPreviewRef.current || dragState;
    pendingDragPreviewRef.current = null;
    const sourceLocation = findElementLocation(selectedElement.id);
    const targetFrame = finalPreview.dropSectionId
      ? document.querySelector(`.direct-layout-frame[data-section-id="${CSS.escape(finalPreview.dropSectionId)}"]`)
      : null;
    const targetSection = activePage?.sections.find((section) => section.id === finalPreview.dropSectionId);

    if (targetFrame && targetSection && sourceLocation && sourceLocation.sectionId !== targetSection.id) {
      const frameRect = targetFrame.getBoundingClientRect();
      const nextPosition = getMovedElementPosition({
        selectedElement,
        targetSection,
        viewport,
        event,
        frameRect,
        viewports,
        createPosition,
        getSectionCanvasHeight,
      });
      const movedElement = createMovedFreeElement(selectedElement, nextPosition);

      updateSections((sections) => commitDirectElementInteraction(sections, {
        elementId: selectedElement.id,
        movedElement,
        sourceSectionId: sourceLocation.sectionId,
        targetSectionId: targetSection.id,
      }));
      showToast(`Moved ${selectedElement.name || "component"} to ${targetSection.name || "section"}.`);
    } else if (sourceLocation && finalPreview.previewPosition) {
      updateSections((sections) => commitDirectElementInteraction(sections, {
        elementId: selectedElement.id,
        previewPosition: finalPreview.previewPosition,
        previewSectionHeight: finalPreview.previewSectionHeight,
        sourceSectionId: sourceLocation.sectionId,
        viewportName: viewport,
      }));
    }

    setDragState(null);
    setSelected({ type: "element", id: selectedElement.id });
    window.setTimeout(() => {
      const committedProject = projectRef.current;
      if (committedProject) saveProject({ silent: true, projectOverride: committedProject });
    }, 0);
  };

  const handlePointerCancel = () => {
    if (dragPreviewFrameRef.current !== null) {
      window.cancelAnimationFrame(dragPreviewFrameRef.current);
      dragPreviewFrameRef.current = null;
    }
    pendingDragPreviewRef.current = null;
    setDragState(null);
  };

  const {
    renderConnectedForm,
  } = useMemo(
    // eslint-disable-next-line react-hooks/refs
    () => createRuntimeFormRenderers({
      project,
      preview,
      lang,
      runtimeAnswers,
      runtimeErrors,
      runtimeFormPages,
      setRuntimeFormPages,
      runtimeFormLanguages,
      setRuntimeFormLanguages,
      quizSessions,
      getFieldType,
      setAnswer,
      submitRuntimeForm,
      startQuizSession,
      moveQuizQuestion,
    }),
    [
      project,
      preview,
      lang,
      runtimeAnswers,
      runtimeErrors,
      runtimeFormPages,
      runtimeFormLanguages,
      quizSessions,
      setAnswer,
      submitRuntimeForm,
      startQuizSession,
      moveQuizQuestion,
    ]
  );

  const hasActiveQuizSession = useMemo(
    () => Object.values(quizSessions).some((session) => session?.active),
    [quizSessions]
  );

  useEffect(() => {
    if (!hasActiveQuizSession) return undefined;

    const timer = window.setInterval(() => {
      setQuizSessions((prev) => {
        let changed = false;
        const next = { ...prev };

        Object.entries(prev).forEach(([formId, session]) => {
          if (!session?.active) return;

          const nextSession = { ...session };
          if (nextSession.totalRemaining > 0) {
            nextSession.totalRemaining -= 1;
            changed = true;
          }

          if (nextSession.questionRemaining > 0) {
            nextSession.questionRemaining -= 1;
            changed = true;
          }

          next[formId] = nextSession;
        });

        return changed ? next : prev;
      });
    }, 1000);

    return () => window.clearInterval(timer);
  }, [hasActiveQuizSession]);

  useEffect(() => {
    Object.entries(quizSessions).forEach(([formId, session]) => {
      if (!session?.active) return;
      const form = project.forms.find((item) => item.id === formId);
      if (!form) return;
      const fields = getFormFields(form);

      if (session.totalRemaining === 0 && getQuizSettings(form).totalTimeLimitSec > 0) {
        submitRuntimeForm(form, { skipValidation: true });
        return;
      }

      if (session.questionRemaining === 0) {
        const questionLimit = Number(fields[session.currentIndex]?.quizTimeLimitSec || getQuizSettings(form).questionTimeLimitSec || 0);
        if (questionLimit <= 0) return;

        if (session.currentIndex >= fields.length - 1) {
          submitRuntimeForm(form, { skipValidation: true });
        } else {
          moveQuizQuestion(form, "next");
        }
      }
    });
  }, [moveQuizQuestion, quizSessions, project.forms, submitRuntimeForm]);

  useEffect(() => {
    const lockActiveFocusedQuizzes = () => {
      Object.entries(quizSessions).forEach(([formId, session]) => {
        if (!session?.active || session.locked) return;
        const form = project.forms.find((item) => item.id === formId);
        if (!form || form.mode !== "quiz" || !getQuizSettings(form).lockScreen) return;
        lockFocusedQuizAttempt(formId);
      });
    };

    const handleFullscreenChange = () => {
      if (!document.fullscreenElement) lockActiveFocusedQuizzes();
    };

    const handleVisibilityChange = () => {
      if (document.hidden) lockActiveFocusedQuizzes();
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", lockActiveFocusedQuizzes);
    window.addEventListener("pagehide", lockActiveFocusedQuizzes);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", lockActiveFocusedQuizzes);
      window.removeEventListener("pagehide", lockActiveFocusedQuizzes);
    };
  }, [lockFocusedQuizAttempt, quizSessions, project.forms]);

  const renderElement = useMemo(
    // eslint-disable-next-line react-hooks/refs
    () => createElementRenderer({
      carouselElementTypes,
      selected,
      preview,
      getFreeElementStyle,
      getElementStyle,
      startDrag,
      findElementLocation,
      setInsertTarget,
      setSelected,
      captureCanvasTextSelection,
      textSelection,
      updateElementInlineText,
      runElementAction,
      renderConnectedForm,
      getReservationBlockValue,
    }),
    [
      selected,
      preview,
      getFreeElementStyle,
      getElementStyle,
      startDrag,
      findElementLocation,
      captureCanvasTextSelection,
      textSelection,
      updateElementInlineText,
      runElementAction,
      renderConnectedForm,
      getReservationBlockValue,
    ]
  );

  const {
    renderSiteHeader,
    renderSiteFooter,
  } = createSiteChromeRenderers({
    project,
    activePage,
    selected,
    preview,
    selectPage,
    setSelected,
  });

  const siteChrome = useMemo(
    () => ({ ...defaultSiteChrome, ...(project.siteChrome || {}) }),
    [project.siteChrome]
  );
  const updateSiteChrome = useCallback((updates) => {
    updateProject((prev) => ({
      ...prev,
      siteChrome: {
        ...defaultSiteChrome,
        ...(prev.siteChrome || {}),
        ...updates,
      },
    }));
  }, [updateProject]);

  useEffect(() => {
    return deferEffectStateUpdate(() => {
      setLogoUrlDraft(siteChrome.logoUrl || "");
    });
  }, [siteChrome.logoUrl]);

  const applyLogoUrl = useCallback(() => {
    updateSiteChrome({ logoUrl: logoUrlDraft.trim() });
    showToast("Logo URL applied.");
  }, [logoUrlDraft, showToast, updateSiteChrome]);

  const getHeaderButtonPageTargetId = useCallback(
    (targetValue = "") => {
      const normalizedTarget = String(targetValue || "").toLowerCase().replace(/^\//, "").trim();
      if (!normalizedTarget) return "";

      const targetPage = safeProjectPages.find((page) => {
        const normalizedId = String(page.id || "").toLowerCase();
        const normalizedName = String(page.name || "").toLowerCase().trim();
        const normalizedSlug = String(page.slug || "").toLowerCase().replace(/^\//, "").trim();
        return (
          normalizedId === normalizedTarget ||
          normalizedName === normalizedTarget ||
          normalizedSlug === normalizedTarget
        );
      });

      return targetPage?.id || "";
    },
    [safeProjectPages]
  );

  const headerButtonPageId =
    getHeaderButtonPageTargetId(siteChrome.headerButtonPageId) ||
    getHeaderButtonPageTargetId(siteChrome.headerButtonHref) ||
    getHeaderButtonPageTargetId(siteChrome.headerButtonLabel) ||
    "";

  const updateHeaderButtonPageTarget = useCallback(
    (pageId) => {
      const targetPage = safeProjectPages.find((page) => page.id === pageId);
      updateSiteChrome({
        headerButtonPageId: pageId,
        headerButtonHref: targetPage?.slug || "",
      });
    },
    [safeProjectPages, updateSiteChrome]
  );

  const getSiteChromeListItems = useCallback(
    (fieldKey) => {
      const value = String(siteChrome[fieldKey] || "");
      const items = value.split("\n");
      return items.length && items.some((item) => item.trim()) ? items : [""];
    },
    [siteChrome]
  );

  const updateSiteChromeListItem = useCallback(
    (fieldKey, index, value) => {
      const items = getSiteChromeListItems(fieldKey);
      items[index] = value;
      updateSiteChrome({ [fieldKey]: items.join("\n") });
    },
    [getSiteChromeListItems, updateSiteChrome]
  );

  const addSiteChromeListItem = useCallback(
    (fieldKey) => {
      updateSiteChrome({ [fieldKey]: [...getSiteChromeListItems(fieldKey), ""].join("\n") });
    },
    [getSiteChromeListItems, updateSiteChrome]
  );

  const removeSiteChromeListItem = useCallback(
    (fieldKey, index) => {
      const nextItems = getSiteChromeListItems(fieldKey).filter((_, itemIndex) => itemIndex !== index);
      updateSiteChrome({ [fieldKey]: (nextItems.length ? nextItems : [""]).join("\n") });
    },
    [getSiteChromeListItems, updateSiteChrome]
  );

  const renderFooterPageLinksEditor = () => {
    const fieldKey = "footerShopLinks";
    const label = "Pages links";
    const items = getSiteChromeListItems(fieldKey);
    const selectedPageIds = items.map((item) => getHeaderButtonPageTargetId(item));

    return (
      <div className="site-chrome-list-editor">
        <div className="site-chrome-list-editor-header">
          <span>{label}</span>
          <button
            type="button"
            onClick={() => addSiteChromeListItem(fieldKey)}
            disabled={!safeProjectPages.length || safeProjectPages.every((page) => selectedPageIds.includes(page.id))}
          >
            + Add
          </button>
        </div>
        <div className="site-chrome-list-rows">
          {items.map((item, index) => {
            const selectedPageId = getHeaderButtonPageTargetId(item);

            return (
              <div className="site-chrome-list-row" key={`${fieldKey}-${index}`}>
                <span className="site-chrome-list-bullet" aria-hidden="true" />
                <select
                  aria-label={`${label} item ${index + 1}`}
                  value={selectedPageId}
                  onChange={(event) => {
                    updateSiteChromeListItem(fieldKey, index, event.target.value);
                  }}
                >
                  <option value="">Select a builder page</option>
                  {safeProjectPages.map((page) => (
                    <option
                      key={page.id}
                      value={page.id}
                      disabled={selectedPageIds.some((pageId, selectedIndex) => pageId === page.id && selectedIndex !== index)}
                    >
                      {page.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  aria-label={`Remove ${label} item ${index + 1}`}
                  title="Remove item"
                  onClick={() => removeSiteChromeListItem(fieldKey, index)}
                >
                  x
                </button>
              </div>
            );
          })}
        </div>
        <span className="site-chrome-field-help">Only pages created in this builder can be added to this footer column.</span>
      </div>
    );
  };

  const renderFooterListEditor = (fieldKey, label, placeholder) => {
    const items = getSiteChromeListItems(fieldKey);

    return (
      <div className="site-chrome-list-editor">
        <div className="site-chrome-list-editor-header">
          <span>{label}</span>
          <button type="button" onClick={() => addSiteChromeListItem(fieldKey)}>+ Add</button>
        </div>
        <div className="site-chrome-list-rows">
          {items.map((item, index) => (
            <div className="site-chrome-list-row" key={`${fieldKey}-${index}`}>
              <span className="site-chrome-list-bullet" aria-hidden="true" />
              <input
                aria-label={`${label} item ${index + 1}`}
                value={item}
                placeholder={placeholder}
                onChange={(event) => updateSiteChromeListItem(fieldKey, index, event.target.value)}
              />
              <button
                type="button"
                aria-label={`Remove ${label} item ${index + 1}`}
                title="Remove item"
                onClick={() => removeSiteChromeListItem(fieldKey, index)}
              >
                x
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderDesignTab = () => (
    <div className="builder-layout">
      {!preview && (
        <aside className="builder-sidebar">
            <div className="builder-side-panel">
              <div className="panel-mode-select">
                <div className="panel-navigator-heading">
                  <span>Editing tools</span>
                  <small>Choose what you want to manage</small>
                </div>
                <div className="panel-navigator" role="tablist" aria-label="Editing tools">
                  {designPanelOptions.map((panel) => {
                    const PanelIcon = panel.icon;

                    return (
                      <button
                        type="button"
                        role="tab"
                        aria-selected={designPanel === panel.id}
                        className={designPanel === panel.id ? "active" : ""}
                        key={panel.id}
                        onClick={() => setDesignPanel(panel.id)}
                      >
                        {PanelIcon && <PanelIcon size={18} aria-hidden="true" />}
                        <span>
                          <strong>{panel.id}</strong>
                          <small>{panel.hint}</small>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <BuilderSidebarActions
                isSavingProject={isSavingProject}
                onSave={saveProject}
                onGoLive={publishProject}
              />

            {designPanel === "Pages" && (
              <section className="builder-panel pages-manager-panel">
                <div className="pages-panel-heading">
                  <div>
                    <span className="pages-panel-eyebrow">Site structure</span>
                    <h2>Pages</h2>
                  </div>
                  <span className="pages-count" aria-label={`${project.pages.length} pages`}>
                    {project.pages.length}
                  </span>
                </div>
                <p className="panel-help">Create public pages, dashboards, forms, and review screens.</p>

                <label className="page-picker-field">
                  <span>Current page</span>
                  <select value={activePage?.id || ""} onChange={(event) => selectPage(event.target.value)}>
                    {project.pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
                  </select>
                </label>

                <div className="page-action-stack">
                  <button type="button" className="page-primary-action" onClick={addPage}>
                    <FilePlus2 size={17} aria-hidden="true" />
                    <span>New page</span>
                  </button>

                  <div className="page-utility-actions">
                    <button type="button" onClick={duplicatePage}>
                      <Copy size={16} aria-hidden="true" />
                      <span>Duplicate</span>
                    </button>
                    <button type="button" onClick={() => setModal("starter")}>
                      <LayoutTemplate size={16} aria-hidden="true" />
                      <span>Templates</span>
                    </button>
                  </div>

                  <div className="page-danger-actions">
                    <button
                      type="button"
                      className="page-delete-action page-clear-blocks-action"
                      onClick={eraseActivePageBlocks}
                      disabled={!activePage?.sections?.length}
                    >
                      <Trash2 size={16} aria-hidden="true" />
                      <span>Erase blocks</span>
                    </button>
                    <button
                      type="button"
                      className="page-delete-action"
                      onClick={requestDeleteActivePage}
                      disabled={safeProjectPages.length <= 1}
                    >
                      <Trash2 size={16} aria-hidden="true" />
                      <span>Delete page</span>
                    </button>
                  </div>
                </div>

              </section>
            )}

          {designPanel === "Sections" && (
            <section className="builder-panel">
              <h2>Components</h2>
              <p className="panel-help">Drag a component anywhere onto the continuous page canvas.</p>
              <div className="section-component-palette">
                <span>Page components</span>
                {elementGroups.map((group) => (
                  <div className="add-group" key={group}>
                    <span>{group}</span>
                    {elementTypes
                      .filter((item) => item.group === group)
                      .map((item) => (
                        <button
                          type="button"
                          draggable
                          key={item.id}
                          onDragStart={(event) => handlePaletteDragStart(event, item.id)}
                          onClick={() => addComponentToSection(item.id, selectedSection?.id || "")}
                        >
                          <strong>{item.label}</strong>
                          <small>Drag into a section</small>
                        </button>
                      ))}
                  </div>
                ))}
              </div>

            </section>
          )}

          {designPanel === "Themes" && (
            <section className="builder-panel builder-themes-panel">
              {renderThemeTab({ variant: "sidebar" })}
            </section>
          )}

          </div>
        </aside>
      )}

      <main
        className="builder-canvas-shell"
        onClick={() => {
          if (!preview) {
            setInlineToolbarPosition(null);
            setSelected({ type: "page", id: activePage?.id });
          }
        }}
      >
        {!preview && renderInlineTextToolbar()}
        <div
          className={`builder-canvas viewport-${viewport}`}
          style={{
            ...getPageBuilderThemeVars(project.theme),
            ...getPreviewCanvasStyle(viewport, preview, viewports),
          }}
        >
          {renderSiteHeader()}

          {activePage?.sections.map((section) => {
            const isSelected = selected.type === "section" && selected.id === section.id;
            const renderedSectionHeight = dragState?.elementId && getElementSection(dragState.elementId)?.id === section.id
              ? Math.max(getSectionCanvasHeight(section, viewport), Number(dragState.previewSectionHeight) || 0)
              : getSectionCanvasHeight(section, viewport);

            if (section.mode === "direct") {
              return (
                <section
                  key={section.id}
                  className={`site-section direct-layout-section width-${section.layout.width} ${isSelected ? "is-selected" : ""} ${dragState?.dropSectionId === section.id || paletteDropSectionId === section.id ? "is-drop-target" : ""}`}
                  style={{ backgroundColor: section.layout.background, minHeight: renderedSectionHeight }}
                  onClick={(event) => {
                    event.stopPropagation();
                    if (!preview) {
                      const frame = event.currentTarget.querySelector(".direct-layout-frame");
                      const rect = frame?.getBoundingClientRect();
                      setInsertTarget({
                        sectionId: section.id,
                        mode: "direct",
                        x: rect ? Math.max(0, Math.round(event.clientX - rect.left)) : 40,
                        y: rect ? Math.max(0, Math.round(event.clientY - rect.top)) : 40,
                      });
                      setSelected({ type: "section", id: section.id });
                    }
                  }}
                >
                  <div
                    className="direct-layout-frame"
                    data-section-id={section.id}
                    style={{ width: `min(100%, ${viewports[viewport]}px)`, minHeight: `${renderedSectionHeight}px` }}
                    onDragOver={(event) => {
                      event.preventDefault();
                      event.dataTransfer.dropEffect = "copy";
                      if (paletteDropSectionId !== section.id) setPaletteDropSectionId(section.id);
                    }}
                    onDragLeave={(event) => {
                      if (!event.currentTarget.contains(event.relatedTarget)) {
                        setPaletteDropSectionId("");
                      }
                    }}
                    onDrop={(event) => handlePaletteDrop(event, section)}
                  >
                    {(section.freeElements || []).map((element) => {
                      const elementSelected = selected.type === "element" && selected.id === element.id;
                      const DirectFrame = element.type === "formBlock" ? PageBuilderMeasuredFrame : "div";

                      return (
                        <DirectFrame
                          key={element.id}
                          {...(element.type === "formBlock"
                            ? {
                                measureEnabled: !preview && dragState?.elementId !== element.id,
                                measurementKey: `${element.id}:${viewport}`,
                                onMeasuredHeight: (height) =>
                                  reconcileDirectFormBlockSize(section.id, element.id, height),
                              }
                            : {})}
                          className={`direct-element-frame direct-element-frame-${element.type} ${elementSelected ? "is-selected" : ""}`}
                          style={getDirectElementFrameStyle(element)}
                          tabIndex={-1}
                          onPointerDownCapture={(event) => {
                            if (preview) return;
                            event.currentTarget.focus({ preventScroll: true });
                            setSelected({ type: "element", id: element.id });
                          }}
                          onPointerDown={
                            preview
                              ? undefined
                              : (event) =>
                                  startDrag(event, element, "move", element.type === "button")
                          }
                          onClick={(event) => {
                            if (preview) return;
                            event.stopPropagation();
                            setSelected({ type: "element", id: element.id });
                          }}
                        >
                          <div className="direct-element-content">
                            {renderElement(element, false)}
                          </div>
                          {elementSelected && !preview && (
                            <>
                              <button
                                type="button"
                                className="direct-move-handle"
                                aria-label={`Move ${element.name || "component"}`}
                                title="Drag to move in any direction"
                                onPointerDown={(event) => startDrag(event, element, "move", true)}
                              >
                                <Move size={13} aria-hidden="true" />
                              </button>
                              <button
                                type="button"
                                className="direct-resize-handle"
                                aria-label={`Resize ${element.name || "component"}`}
                                title="Drag to resize"
                                onPointerDown={(event) => startDrag(event, element, "resize", true)}
                              />
                            </>
                          )}
                        </DirectFrame>
                      );
                    })}
                  </div>
                </section>
              );
            }

            return (
              <section
                key={section.id}
                className={`site-section width-${section.layout.width} padding-${section.layout.paddingY} ${isSelected ? "is-selected" : ""}`}
                style={{ backgroundColor: section.layout.background }}
                onClick={(event) => {
                  event.stopPropagation();
                  if (!preview) {
                    const columnId = getClosestColumnIdFromEvent(event);
                      setInsertTarget({
                        sectionId: section.id,
                        mode: "auto",
                        columnId,
                        afterElementId: "",
                      });
                    setSelected({ type: "section", id: section.id });
                  }
                }}
              >
                {section.rows.map((row) => (
                  <div
                    key={row.id}
                    className={`site-row columns-${row.layout.columns} align-${row.layout.align} gap-${row.layout.gap}`}
                  >
                    {row.columns.map((column) => {
                      const columnSelected = selected.type === "column" && selected.id === column.id;

                      return (
                        <div
                          key={column.id}
                          data-column-id={column.id}
                          className={`site-column column-align-${column.layout.align} ${columnSelected ? "is-selected" : ""}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            if (!preview) {
                              setInsertTarget({
                                sectionId: section.id,
                                mode: "auto",
                                columnId: column.id,
                                afterElementId: "",
                              });
                              setSelected({ type: "column", id: column.id });
                            }
                          }}
                        >
                          {column.elements
                            .filter((element) => !carouselElementTypes.has(element.type))
                            .map((element) => renderElement(element, false))}
                          {!preview && column.elements.length === 0 && (
                            <div className="empty-column">Select this column, then add an element.</div>
                          )}
                        </div>
                      );
                    })}
                    {getRowCarouselElements(row, carouselElementTypes).map((element) => renderElement(element, false))}
                  </div>
                ))}
              </section>
            );
          })}

          {renderSiteFooter()}
        </div>
      </main>

      {!preview && renderInspector()}
    </div>
  );

  const renderInspector = () => (
    <aside className="builder-inspector">
      <div className="builder-side-panel">
        <div className="inspector-title">
          <h2>Inspector</h2>
          <span>{selected.type}</span>
        </div>

      {selected.type === "page" && activePage && (
        <div className="inspector-group">
          <h3>Page Settings</h3>
          <label>Page name<input value={activePage.name} onChange={(event) => updateActivePage((page) => ({ ...page, name: event.target.value }))} /></label>
          <label>
            Page link
            <input
              value={activePage.slug}
              disabled={activePage.isDefault === true}
              onChange={(event) => updateActivePage((page) => ({ ...page, slug: event.target.value }))}
            />
          </label>
          <label className="inspector-toggle-row">
            <input
              type="radio"
              name="builder-default-page"
              checked={activePage.isDefault === true}
              onChange={() => updateProject((prev) => setProjectDefaultPage(prev, activePage.id))}
            />
            <span>Use as homepage</span>
          </label>
          {collectPublicPageRoutingIssues(project).some((issue) =>
            issue.page_id === activePage.id ||
            issue.occurrences?.some((page) => page.page_id === activePage.id)
          ) && (
            <p className="builder-note" role="alert">Choose a unique, non-reserved page link before publishing.</p>
          )}
          <label className="inspector-toggle-row">
            <input type="checkbox" checked={activePage.showInNavigation !== false} onChange={(event) => updateActivePage((page) => ({ ...page, showInNavigation: event.target.checked }))} />
            <span>Show this page in the header</span>
          </label>
        </div>
      )}

      {(selected.type === "siteHeader" || selected.type === "siteFooter") && (
        <div className="inspector-group">
          <h3>{selected.type === "siteHeader" ? "Header" : "Footer"}</h3>
          <p className="builder-note">Use the Header & Footer workspace for global site chrome settings.</p>
          <button type="button" className="full-width-action" onClick={() => setActiveTab("chrome")}>
            Open Header & Footer
          </button>
        </div>
      )}

      {selected.type === "column" && selectedColumn && (
        <div className="inspector-group">
          <h3>Column</h3>
          <label>Alignment<select value={selectedColumn.layout.align} onChange={(event) => updateSelectedColumn({ layout: { align: event.target.value } })}>{alignmentOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        </div>
      )}

      {selected.type === "element" && selectedElement && (
        <div className="inspector-group">
          <h3>{selectedElement.type === "reservationBlock" ? "Reservation" : "Element"}</h3>
          {selectedElement.type !== "reservationBlock" && (
            <label>Name<input value={selectedElement.name} onChange={(event) => updateSelectedElement({ name: event.target.value })} /></label>
          )}
          {(selectedElement.type === "loginBlock" || selectedElement.type === "registrationBlock") && (
            <div className="auth-workflow-settings">
              <strong>Authentication workflow</strong>
              <label>
                {selectedElement.type === "registrationBlock" ? "Login page after registration" : "Page after login"}
                <select value={selectedElement.auth?.successPageId || ""} onChange={(event) => updateSelectedElement({ auth: { ...(selectedElement.auth || {}), successPageId: event.target.value } })}>
                  {selectedElement.type === "registrationBlock" ? (
                    <option value="">Find the Login page automatically</option>
                  ) : (
                    <option value="" hidden>Select a page</option>
                  )}
                  {project.pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
                </select>
              </label>
              <p className="builder-note">The destination page can stay hidden from the header.</p>
            </div>
          )}
          {carouselElementTypes.has(selectedElement.type) && (
            <div className="carousel-timing-controls">
              <strong>Slide timing</strong>
              <label>
                Auto slide
                <select
                  value={selectedElement.autoScroll ? "on" : "off"}
                  onChange={(event) =>
                    updateSelectedElement({ autoScroll: event.target.value === "on" })
                  }
                >
                  <option value="on">On</option>
                  <option value="off">Off</option>
                </select>
              </label>
              <label>
                Delay seconds
                <input
                  type="number"
                  min="1"
                  step="0.5"
                  value={(Number(selectedElement.autoScrollMs) || 4000) / 1000}
                  onChange={(event) =>
                    updateSelectedElement({
                      autoScrollMs: Math.max(1000, Number(event.target.value || 4) * 1000),
                    })
                  }
                />
              </label>
            </div>
          )}
          {carouselElementTypes.has(selectedElement.type) && (
            <details open className="carousel-slide-editor">
              <summary>Carousel slides</summary>
              <p className="builder-note">Edit every slide and choose or replace its image.</p>
              <div className="carousel-slide-list">
                {parseCarouselSlides(selectedElement.content).map((slide, index) => (
                  <details className="carousel-slide-card" defaultOpen={index === 0} key={`${selectedElement.id}_slide_${index}`}>
                    <summary>
                      <span>Slide {index + 1}</span>
                      <span className="carousel-slide-edit-hint primary-action">
                        {resolveMediaUrl(slide.image) ? "Edit image" : "Add image"}
                      </span>
                    </summary>
                    <div className="carousel-slide-card-body">
                  <div className="carousel-slide-copy-fields">
                    <label>Title<input value={slide.title} onChange={(event) => {
                      const slides = parseCarouselSlides(selectedElement.content).map((item, itemIndex) => itemIndex === index ? { ...item, title: event.target.value } : item);
                      updateSelectedElement({ content: serializeCarouselSlides(slides) });
                    }} /></label>
                    <label>Description<textarea value={slide.description} onChange={(event) => {
                      const slides = parseCarouselSlides(selectedElement.content).map((item, itemIndex) => itemIndex === index ? { ...item, description: event.target.value } : item);
                      updateSelectedElement({ content: serializeCarouselSlides(slides) });
                    }} /></label>
                  </div>
                  <div className="carousel-slide-image-control">
                    <div className="carousel-slide-image-preview">
                      {resolveMediaUrl(slide.image) ? (
                        <img src={resolveMediaUrl(slide.image)} alt={slide.title || `Slide ${index + 1}`} />
                      ) : (
                        <span>No image</span>
                      )}
                    </div>
                    <div className="carousel-slide-image-actions">
                      <label className="upload-image-button">
                        {assetUploadBusy ? "Uploading..." : resolveMediaUrl(slide.image) ? "Replace image" : "Choose image"}
                        <input type="file" accept="image/png,image/jpeg,image/webp" hidden disabled={assetUploadBusy} onChange={(event) => handleCarouselSlideImageUpload(event, index)} />
                      </label>
                      {resolveMediaUrl(slide.image) && (
                        <button type="button" className="carousel-remove-image" onClick={() => {
                          const slides = parseCarouselSlides(selectedElement.content).map((item, itemIndex) => itemIndex === index ? { ...item, image: "" } : item);
                          updateSelectedElement({ content: serializeCarouselSlides(slides) });
                        }}>Remove image</button>
                      )}
                    </div>
                  </div>
                  <details className="carousel-image-url-control">
                    <summary>Public image URL</summary>
                    <label>
                      HTTPS image URL
                      <input
                        key={`${selectedElement.id}_slide_url_${index}_${slide.image}`}
                        type="url"
                        inputMode="url"
                        autoComplete="off"
                        placeholder="https://example.com/image.jpg"
                        defaultValue={/^https:\/\//i.test(String(slide.image || "").trim()) ? slide.image : ""}
                        onBlur={(event) => {
                          const imageUrl = event.currentTarget.value.trim();
                          const urlError = getStoredUrlError(imageUrl, {
                            fieldName: "Image URL",
                            allowRelative: false,
                            allowEmpty: true,
                          });

                          if (urlError) {
                            showToast(urlError);
                            event.currentTarget.value = /^https:\/\//i.test(String(slide.image || "").trim()) ? slide.image : "";
                            return;
                          }

                          if (imageUrl === slide.image || (!imageUrl && !/^https:\/\//i.test(String(slide.image || "").trim()))) return;

                          const slides = parseCarouselSlides(selectedElement.content).map((item, itemIndex) =>
                            itemIndex === index ? { ...item, image: imageUrl } : item
                          );
                          updateSelectedElement({ content: serializeCarouselSlides(slides) });
                        }}
                      />
                      <small>Only public HTTPS image URLs are accepted. Uploaded file paths stay hidden.</small>
                    </label>
                  </details>
                  <button type="button" className="danger-lite" disabled={parseCarouselSlides(selectedElement.content).length <= 1} onClick={() => updateSelectedElement({ content: serializeCarouselSlides(parseCarouselSlides(selectedElement.content).filter((_, itemIndex) => itemIndex !== index)) })}>Remove slide</button>
                    </div>
                  </details>
                ))}
              </div>
              <button type="button" className="primary-action" onClick={() => updateSelectedElement({ content: serializeCarouselSlides([...parseCarouselSlides(selectedElement.content), { title: "New story", description: "Add your story here.", image: "" }]) })}>+ Add slide</button>
            </details>
          )}
          {selectedElement.type === "list" && (
            <details open className="list-editor">
              <summary>List content</summary>
              <label>Main sentence<input value={selectedElement.listTitle || ""} placeholder="Add a title for these points" onSelect={(event) => captureTextSelection(event, "listTitle")} onChange={(event) => updateSelectedElement({ listTitle: event.target.value, richTextColors: (selectedElement.richTextColors || []).filter((range) => range.field !== "listTitle"), richTextSizes: (selectedElement.richTextSizes || []).filter((range) => range.field !== "listTitle"), richTextStyles: (selectedElement.richTextStyles || []).filter((range) => range.field !== "listTitle") })} /></label>
              <label>
                Marker style
                <select value={selectedElement.listStyle || "disc"} onChange={(event) => updateSelectedElement({ listStyle: event.target.value })}>
                  <option value="disc">Bullet points</option>
                  <option value="decimal">Numbers</option>
                  <option value="check">Check marks</option>
                  <option value="arrow">Arrows</option>
                  <option value="none">No markers</option>
                </select>
              </label>
              {getListItems(selectedElement).map((item, index) => (
                <div className="list-editor-item" key={`${selectedElement.id}_list_${index}`}>
                  <label>Item {index + 1}<input value={item} onSelect={(event) => captureTextSelection(event, "listItem", index)} onChange={(event) => {
                    const listItems = getListItems(selectedElement).map((current, itemIndex) => itemIndex === index ? event.target.value : current);
                    updateSelectedElement({ listItems, content: listItems.join("\n"), richTextColors: (selectedElement.richTextColors || []).filter((range) => !(range.field === "listItem" && range.itemIndex === index)), richTextSizes: (selectedElement.richTextSizes || []).filter((range) => !(range.field === "listItem" && range.itemIndex === index)), richTextStyles: (selectedElement.richTextStyles || []).filter((range) => !(range.field === "listItem" && range.itemIndex === index)) });
                  }} /></label>
                  <button type="button" className="danger-lite" disabled={getListItems(selectedElement).length <= 1} onClick={() => {
                    const listItems = getListItems(selectedElement).filter((_, itemIndex) => itemIndex !== index);
                    updateSelectedElement({ listItems, content: listItems.join("\n") });
                  }}>Remove item</button>
                </div>
              ))}
              <button type="button" onClick={() => {
                const listItems = [...getListItems(selectedElement), `Item ${getListItems(selectedElement).length + 1}`];
                updateSelectedElement({ listItems, content: listItems.join("\n") });
              }}>+ Add item</button>
            </details>
          )}
          {!carouselElementTypes.has(selectedElement.type) &&
            selectedElement.type !== "list" &&
            selectedElement.type !== "metric" &&
            selectedElement.type !== "reservationBlock" &&
            selectedElement.type !== "loginBlock" &&
            selectedElement.type !== "registrationBlock" && (
            <label>Content<textarea value={selectedElement.content} onSelect={(event) => captureTextSelection(event, "content")} onChange={(event) => updateSelectedElement({ content: event.target.value, richTextColors: (selectedElement.richTextColors || []).filter((range) => range.field !== "content") })} /></label>
          )}
          {selectedElement.type === "metric" && (
            <details open className="metric-editor">
              <summary>Metrics</summary>
              <label>
                Items per row
                <select value={Math.max(2, Math.min(4, Number(selectedElement.metricColumns) || 2))} onChange={(event) => updateSelectedElement({ metricColumns: Number(event.target.value) })}>
                  <option value="2">2 columns</option>
                  <option value="3">3 columns</option>
                  <option value="4">4 columns</option>
                </select>
              </label>
              <label>
                Metric text color
                <input type="color" value={getColorInputValue(selectedElement.styles?.metricTextColor, "#162033")} onChange={(event) => updateSelectedElement({ styles: { metricTextColor: event.target.value } })} />
              </label>
              <label>
                Symbol color (+, %, etc.)
                <input type="color" value={getColorInputValue(selectedElement.styles?.metricSymbolColor, "#f1b84b")} onChange={(event) => updateSelectedElement({ styles: { metricSymbolColor: event.target.value } })} />
              </label>
              {getMetricItems(selectedElement).map((metric, index) => (
                <div className="metric-editor-item" key={`${selectedElement.id}_metric_${index}`}>
                  <label>Label<input value={metric.label} onChange={(event) => {
                    const metrics = getMetricItems(selectedElement).map((item, itemIndex) => itemIndex === index ? { ...item, label: event.target.value } : item);
                    updateSelectedElement({ metrics });
                  }} /></label>
                  <label>Value<input value={metric.value} placeholder="Value" onChange={(event) => {
                    const metrics = getMetricItems(selectedElement).map((item, itemIndex) => itemIndex === index ? { ...item, value: event.target.value } : item);
                    updateSelectedElement({ metrics });
                  }} /></label>
                  <label>Description<input value={metric.description || ""} onChange={(event) => {
                    const metrics = getMetricItems(selectedElement).map((item, itemIndex) => itemIndex === index ? { ...item, description: event.target.value } : item);
                    updateSelectedElement({ metrics });
                  }} /></label>
                  <button type="button" className="danger-lite" disabled={getMetricItems(selectedElement).length <= 1} onClick={() => updateSelectedElement({ metrics: getMetricItems(selectedElement).filter((_, itemIndex) => itemIndex !== index) })}>Remove metric</button>
                </div>
              ))}
              <button type="button" onClick={() => updateSelectedElement({ metrics: [...getMetricItems(selectedElement), { label: `Metric ${getMetricItems(selectedElement).length + 1}`, value: "0", description: "Description" }] })}>+ Add metric</button>
            </details>
          )}
          {selectedElement.mode !== "direct" && (
            <>
              <label>
                Component width
                <select
                  value={
                    selectedElement.styles.width ||
                    (carouselElementTypes.has(selectedElement.type) ? "100%" : "auto")
                  }
                  onChange={(event) => {
                    const width = event.target.value === "auto" ? "" : event.target.value;
                    updateSelectedElement({
                      styles: {
                        width,
                        ...(width === "100%" ? { alignSelf: "stretch" } : {}),
                      },
                    });
                  }}
                >
                  {!carouselElementTypes.has(selectedElement.type) && (
                    <option value="auto">Auto - content width</option>
                  )}
                  <option value="100%">Full - 100%</option>
                  <option value="70%">Comfort - 70%</option>
                  <option value="75%">Wide - 75%</option>
                  <option value="50%">Half - 50%</option>
                  <option value="33.333%">Third - 33%</option>
                  <option value="25%">Quarter - 25%</option>
                </select>
              </label>
              <label>
                Minimum height
                <input
                  value={selectedElement.styles.minHeight || ""}
                  placeholder="Example: 320px"
                  onChange={(event) => updateSelectedElement({ styles: { minHeight: event.target.value } })}
                />
              </label>
              <label>
                Component position
                <select
                  value={getElementAlignControlValue(selectedElement.styles.alignSelf)}
                  onChange={(event) => updateSelectedElementPlacement(event.target.value)}
                >
                  <option value="auto">Default</option>
                  <option value="flex-start">Left</option>
                  <option value="center">Center</option>
                  <option value="flex-end">Right</option>
                  <option value="stretch">Stretch full width</option>
                </select>
              </label>
              {carouselElementTypes.has(selectedElement.type) && (
                <>
                  <label>
                    Carousel height
                    <select
                      value={selectedElement.styles["--carousel-height"] || ""}
                      onChange={(event) =>
                        updateSelectedElement({
                          styles: { "--carousel-height": event.target.value },
                        })
                      }
                    >
                      <option value="">Default</option>
                      <option value="260px">Small - 260px</option>
                      <option value="340px">Medium - 340px</option>
                      <option value="420px">Large - 420px</option>
                      <option value="520px">Tall - 520px</option>
                    </select>
                  </label>
                  {selectedElement.type === "circularGallery" && (
                    <label>
                      Gallery depth
                      <select
                        value={selectedElement.styles["--gallery-depth"] || ""}
                        onChange={(event) =>
                          updateSelectedElement({
                            styles: { "--gallery-depth": event.target.value },
                          })
                        }
                      >
                        <option value="">Default</option>
                        <option value="220px">Tight</option>
                        <option value="300px">Medium</option>
                        <option value="360px">Deep</option>
                        <option value="440px">Wide ring</option>
                      </select>
                    </label>
                  )}
                </>
              )}
            </>
          )}

          {selectedElement.type === "formBlock" && (
            <label>Connected form<select value={normalizeFormReference(selectedElement.connectedFormId)} onChange={(event) => updateSelectedElement(buildFormConnectionUpdate(event.target.value))}><option value="">Choose a form</option>{project.forms.map((form) => <option key={form.id} value={String(form.id)}>{form.title}</option>)}</select></label>
          )}

          {selectedElement.type === "reservationBlock" && (
            <div className="reservation-form-picker">
              <span>Reservation forms</span>
              <div className="reservation-form-picker-list">
                {reservationFormOptions.length === 0 && (
                  <p className="builder-note">Create a reservation block first.</p>
                )}
                {reservationFormOptions.map((option) => {
                  const isSelected = (selectedElement.connectedReservationBlockId || selectedElement.id) === option.id;

                  return (
                    <button
                      type="button"
                      key={option.id}
                      className={`reservation-form-picker-item ${isSelected ? "is-selected" : ""}`}
                      onClick={() => {
                        const source = reservationBlocks.find((block) => block.element.id === option.id)?.element;
                        updateSelectedElement({
                          connectedReservationBlockId: option.id,
                          ...(source ? { reservation: source.reservation } : {}),
                        });
                      }}
                    >
                      <strong>{option.label}</strong>
                      <small>{option.meta}</small>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {selectedElement.type === "image" && (
            <label className="upload-image-button">
              {assetUploadBusy ? "Uploading..." : "Upload image"}
              <input type="file" accept="image/png,image/jpeg,image/webp" hidden disabled={assetUploadBusy} onChange={handleSelectedElementImageUpload} />
            </label>
          )}

          {selectedElement.type === "button" && (
            <details>
              <summary>Interaction</summary>
              <label>Action<select value={selectedElement.action?.type || "none"} onChange={(event) => updateSelectedElement({ action: { type: event.target.value, pageId: "", url: "", message: "" } })}>
                <option value="none">None</option>
                <option value="goToPage">Go to page</option>
                <option value="openUrl">Open URL</option>
                <option value="showMessage">Show message</option>
              </select></label>
              {selectedElement.action?.type === "goToPage" && (
                <label>Target page<select value={selectedElement.action?.pageId || ""} onChange={(event) => updateSelectedElement({ action: { pageId: event.target.value } })}>{project.pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}</select></label>
              )}
              {selectedElement.action?.type === "openUrl" && (
                <label>URL<input value={selectedElement.action?.url || ""} onChange={(event) => updateSelectedElement({ action: { url: event.target.value } })} /></label>
              )}
              {selectedElement.action?.type === "showMessage" && (
                <label>Message<input value={selectedElement.action?.message || ""} onChange={(event) => updateSelectedElement({ action: { message: event.target.value } })} /></label>
              )}
            </details>
          )}

          <button type="button" className="danger-button" onClick={deleteSelectedElement}>Delete Element</button>
          <p className="builder-note">You can also select an element on the canvas and press Delete or Backspace.</p>
        </div>
      )}
      </div>
    </aside>
  );

  const formatSavedValue = (value) => {
    if (Array.isArray(value) && !value.length) return "-";
    if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
    if (value === true) return "Yes";
    if (value === false) return "No";
    if (value === null || value === undefined || value === "") return "-";
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "object" && value.name) return value.name;
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  const renderSiteChromeTab = () => (
    <div className="workspace-page site-chrome-workspace">
      <header className="workspace-header">
        <div>
          <span className="workspace-kicker">Global site settings</span>
          <h2>Header & Footer</h2>
          <p>Manage the site header, navigation, footer links, and contact information.</p>
        </div>
      </header>

      <section className="site-chrome-layout">
        <div className="site-chrome-editor">
          <article className="site-chrome-card">
            <div className="site-chrome-card-header">
              <div>
                <span>Global</span>
                <h3>Visibility</h3>
              </div>
            </div>
            <div className="site-chrome-toggle-grid">
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={Boolean(siteChrome.showHeader)}
                  onChange={(event) => updateSiteChrome({ showHeader: event.target.checked })}
                />
                <span className="toggle-box" aria-hidden="true" />
                <span className="toggle-copy">
                  <strong>Show header</strong>
                  <small>Show the navigation bar on published pages.</small>
                </span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={Boolean(siteChrome.showFooter)}
                  onChange={(event) => updateSiteChrome({ showFooter: event.target.checked })}
                />
                <span className="toggle-box" aria-hidden="true" />
                <span className="toggle-copy">
                  <strong>Show footer</strong>
                  <small>Show footer links, rights, and contact details.</small>
                </span>
              </label>
            </div>
          </article>

          <article className="site-chrome-card site-chrome-combined-card">
            <div className="site-chrome-card-header">
              <div>
                <span>Header & footer</span>
                <h3>Brand, navigation, contact</h3>
              </div>
            </div>
            <div className="site-chrome-horizontal-settings">
              <div className="site-chrome-pane">
                <div className="site-chrome-pane-heading">
                  <span>Header</span>
                  <strong>Brand and navigation</strong>
                </div>
                <div className="site-chrome-form-grid compact">
                  <label>Brand name<input value={siteChrome.brand || ""} onChange={(event) => updateSiteChrome({ brand: event.target.value })} /></label>
                  <label>Button text<input value={siteChrome.headerButtonLabel || ""} onChange={(event) => updateSiteChrome({ headerButtonLabel: event.target.value })} /></label>
                  <label>
                    Redirects to page
                    <select value={headerButtonPageId} onChange={(event) => updateHeaderButtonPageTarget(event.target.value)}>
                      <option value="">Select a builder page</option>
                      {safeProjectPages.map((page) => (
                        <option key={page.id} value={page.id}>{page.name}</option>
                      ))}
                    </select>
                    <span className="site-chrome-field-help">Only pages created in this builder can be selected.</span>
                  </label>
                  <div className="span-2 site-chrome-logo-row">
                    <label className="site-chrome-field-title" htmlFor="site-chrome-logo-url">Logo</label>
                    <span className="site-chrome-logo-control">
                      <input id="site-chrome-logo-url" value={logoUrlDraft} placeholder="Image URL" onChange={(event) => setLogoUrlDraft(event.target.value)} />
                      <button type="button" className="upload-image-button site-chrome-logo-apply" onClick={applyLogoUrl}>
                        Apply URL
                      </button>
                      <label className="upload-image-button site-chrome-logo-upload">
                        {assetUploadBusy ? "Uploading" : "Choose file"}
                        <input type="file" accept="image/png,image/jpeg,image/webp" disabled={assetUploadBusy} onChange={handleSiteLogoUpload} />
                      </label>
                    </span>
                    <small>Paste an image URL or upload a PNG, JPG, or WebP from your computer.</small>
                  </div>
                  <label className="span-2">
                    Header alignment
                    <select value={siteChrome.headerAlign || "center"} onChange={(event) => updateSiteChrome({ headerAlign: event.target.value })}>
                      <option value="center">Centered navigation</option>
                      <option value="split">Split navigation</option>
                    </select>
                  </label>
                </div>
              </div>

              <div className="site-chrome-pane">
                <div className="site-chrome-pane-heading">
                  <span>Footer</span>
                  <strong>Contact and rights</strong>
                </div>
                <div className="site-chrome-form-grid compact">
                  <label>Footer brand name<input value={siteChrome.footerStoreName || ""} onChange={(event) => updateSiteChrome({ footerStoreName: event.target.value })} /></label>
                  <label>Contact email<input value={siteChrome.contactEmail || ""} onChange={(event) => updateSiteChrome({ contactEmail: event.target.value })} /></label>
                  <label>Phone<input value={siteChrome.phone || ""} onChange={(event) => updateSiteChrome({ phone: event.target.value })} /></label>
                  <label>Language badge<input value={siteChrome.footerLanguageLabel || ""} onChange={(event) => updateSiteChrome({ footerLanguageLabel: event.target.value })} /></label>
                  <label className="span-2">Footer description<textarea value={siteChrome.description || ""} onChange={(event) => updateSiteChrome({ description: event.target.value })} /></label>
                  <label className="span-2">Footer rights<input value={siteChrome.rights || ""} onChange={(event) => updateSiteChrome({ rights: event.target.value })} /></label>
                </div>
              </div>
            </div>
          </article>

          <article className="site-chrome-card">
            <div className="site-chrome-card-header">
              <div>
                <span>Footer links</span>
                <h3>Columns and social items</h3>
              </div>
            </div>
            <div className="site-chrome-form-grid">
              <label>Pages column title<input value={siteChrome.footerShopTitle || ""} onChange={(event) => updateSiteChrome({ footerShopTitle: event.target.value })} /></label>
              <label>Help column title<input value={siteChrome.footerHelpTitle || ""} onChange={(event) => updateSiteChrome({ footerHelpTitle: event.target.value })} /></label>
              {renderFooterPageLinksEditor()}
              {renderFooterListEditor("footerHelpLinks", "Help links", "Help item")}
              {renderFooterListEditor("footerSocialLinks", "Social links", "Social channel")}
              {renderFooterListEditor("footerPaymentMethods", "Payment labels", "Payment label")}
            </div>
          </article>
        </div>
      </section>
    </div>
  );

  const renderDataTab = () => (
  <DataTab
    project={project}
    lang={lang}
    user={user}
    selectForm={selectForm}
    setActiveTab={setActiveTab}
    getFormFields={getFormFields}
  />
);

  const renderQuizAnswerKeyEditor = (field) => {
    if (!correctableQuizTypes.has(field.type)) {
      return (
        <div className="quiz-answer-key is-muted">
          <strong>Correct answer</strong>
          <p>This field type is not automatically graded.</p>
        </div>
      );
    }

    if (field.type === "checkboxes") {
      const selectedAnswers = Array.isArray(field.quizCorrectAnswer) ? field.quizCorrectAnswer : [];

      return (
        <div className="quiz-answer-key">
          <strong>Correct answers</strong>
          <div className="quiz-answer-options">
            {getFieldOptions(field).map((option) => (
              <label className="checkbox-control" key={option}>
                <input
                  type="checkbox"
                  checked={selectedAnswers.includes(option)}
                  onChange={(event) => {
                    const nextAnswers = event.target.checked
                      ? [...selectedAnswers, option]
                      : selectedAnswers.filter((answer) => answer !== option);
                    updateFormField(field.id, { quizCorrectAnswer: nextAnswers });
                  }}
                />
                {option}
              </label>
            ))}
          </div>
        </div>
      );
    }

    if (singleAnswerQuizTypes.has(field.type)) {
      const options =
        field.type === "yesNo"
          ? ["Yes", "No"]
          : field.type === "linearScale"
            ? scaleRange(field)
            : field.type === "rating"
              ? Array.from({ length: Math.max(2, Math.min(10, Number(field.maxRating || 5))) }, (_, index) => String(index + 1))
              : getFieldOptions(field);

      return (
        <div className="quiz-answer-key">
          <label>
            Correct answer
            <select
              value={field.quizCorrectAnswer || ""}
              onChange={(event) => updateFormField(field.id, { quizCorrectAnswer: event.target.value })}
            >
              <option value="">Select the correct answer</option>
              {options.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
        </div>
      );
    }

    return (
      <div className="quiz-answer-key">
        <label>
          Accepted answers
          <textarea
            value={Array.isArray(field.quizCorrectAnswer) ? field.quizCorrectAnswer.join("\n") : field.quizCorrectAnswer || ""}
            placeholder="One accepted answer per line"
            onChange={(event) => updateFormField(field.id, { quizCorrectAnswer: splitLines(event.target.value) })}
          />
        </label>
      </div>
    );
  };

  const renderFormsTab = () => (
    <FormsTab
      project={project}
      updateProject={updateProject}
      activeForm={activeForm}
      fieldTypes={fieldTypes}
      selected={selected}
      lang={lang}
      selectForm={selectForm}
      selectPage={selectPage}
      setActiveTab={setActiveTab}
      setDesignPanel={setDesignPanel}
      setSelected={setSelected}
      addForm={addForm}
      deleteActiveForm={deleteActiveForm}
      addFormSection={addFormSection}
      addFieldToForm={addFieldToForm}
      updateActiveForm={updateActiveForm}
      updateActiveFormQuiz={updateActiveFormQuiz}
      updateFormField={updateFormField}
      updateFormSection={updateFormSection}
      renderQuizAnswerKeyEditor={renderQuizAnswerKeyEditor}
      moveFormField={moveFormField}
      duplicateFormField={duplicateFormField}
      deleteFormField={deleteFormField}
      deleteFormSection={deleteFormSection}
      getFormFields={getFormFields}
      getFormSections={getFormSections}
      getQuizSettings={getQuizSettings}
      getFormPlacements={getFormPlacements}
      addConnectedFormSectionToPage={addConnectedFormSectionToPage}
      renderConnectedForm={renderConnectedForm}
      openFormPreviewPage={openFormPreviewPage}
      openPreviewPage={openPreviewPage}
      saveProject={saveProject}
      restorePreviousDraft={restorePreviousDraft}
      publishProject={publishProject}
      quizOptionsOpen={quizOptionsOpen}
      setQuizOptionsOpen={setQuizOptionsOpen}
    />
  );

  const renderReservationsTab = () => (
    <ReservationsTab
      reservationBlocks={reservationBlocks}
      activeReservationId={
        selected.type === "element" && selectedElement?.type === "reservationBlock"
          ? selected.id
          : ""
      }
      onAddReservationBlock={(reservationOverrides = {}) =>
        addComponentToSection("reservationBlock", "", null, reservationOverrides)
      }
      onOpenReservationBlock={openReservationBlockOnPage}
      onSelectReservationBlock={selectReservationBlock}
      onUpdateReservationBlock={updateReservationBlock}
      onDeleteReservationBlock={deleteReservationBlock}
    />
  );

  const renderWorkflowsTab = () => (
    <WorkflowsTab
      project={project}
      activeWorkflow={activeWorkflow}
      workflowStepTypes={workflowStepTypes}
      selectWorkflow={selectWorkflow}
      addWorkflow={addWorkflow}
      addWorkflowStep={addWorkflowStep}
      updateActiveWorkflow={updateActiveWorkflow}
      updateWorkflowStep={updateWorkflowStep}
      deleteWorkflowStep={deleteWorkflowStep}
    />
  );

  const renderUsersTab = () => (
    <UsersTab
      project={project}
      selected={selected}
      selectedRole={selectedRole}
      permissionGroups={permissionGroups}
      addUser={addUser}
      addRole={addRole}
      updateUser={updateUser}
      updateRole={updateRole}
      deleteUser={deleteUser}
      setSelected={setSelected}
    />
  );

  const renderThemeTab = (themeTabProps = {}) => (
    <ThemeTab
      project={project}
      updateProject={updateProject}
      setThemeMode={setThemeMode}
      saveProject={saveThemeProject}
      {...themeTabProps}
    />
  );

  const renderResponsesTab = () => (
    <ResponsesTab
      project={project}
      builderProjectId={builderProjectRecord?.id || ""}
      lang={lang}
      user={user}
      activeForm={activeForm}
      selectForm={selectForm}
      setActiveTab={setActiveTab}
      getFormFields={getFormFields}
      formatSavedValue={formatSavedValue}
      showToast={showToast}
    />
  );

  const renderPublishTab = () => (
    <PublishTab
      project={project}
      saveProject={saveProject}
      loadProject={loadProject}
      exportProject={exportProject}
      persistProjectNow={persistProjectNow}
      liveSitePath={canonicalLiveSitePath}
      hasConfiguredSubdomain={Boolean(publicSiteSubdomain)}
      openWebsiteSettings={() => navigate("/settings")}
      openFormPreviewPage={openFormPreviewPage}
      onUnpublish={unpublishProject}
      isUnpublishing={isUnpublishingProject}
      lang={lang}
    />
  );

  const renderActiveTab = () => {
    if (activeTab === "design") return renderDesignTab();
    if (activeTab === "data") return renderDataTab();
    if (activeTab === "forms") return renderFormsTab();
    if (activeTab === "reservations") return renderReservationsTab();
    if (activeTab === "chrome") return renderSiteChromeTab();
    if (activeTab === "responses") return renderResponsesTab();
    if (activeTab === "workflows") return renderWorkflowsTab();
    if (activeTab === "users") return renderUsersTab();
    if (activeTab === "theme") return renderThemeTab();
    if (activeTab === "publish") return renderPublishTab();
    return renderDesignTab();
  };

  const builderCopy = builderWorkspaceCopy[lang] || builderWorkspaceCopy.en;

  const renderWorkspaceNavigator = () => (
    <nav className="workspace-tabs" aria-label={lang === "ar" ? "مساحات عمل المنشئ" : "Builder workspaces"}>
      {builderTabs
        .filter((tab) =>
          visibleTabIds
            ? visibleTabIds.includes(tab.id)
            : !mainBuilderHiddenTabs.includes(tab.id)
        )
        .map((tab) => (
        <button
          type="button"
          key={tab.id}
          className={activeTab === tab.id ? "active" : ""}
          onClick={() => setActiveTab(tab.id)}
        >
          {builderCopy.tabs[tab.id]?.label || tab.label}
        </button>
      ))}
    </nav>
  );

  if (hasUnrecoverableBrowserDraft && !builderProjectRecord) {
    return (
      <div className={getPageBuilderThemeClassName({ mode: appThemeMode || "light", renderMode: "editing" })}>
        <main className="workspace-page" role="alert" aria-live="assertive">
          <section className="workspace-header">
            <div>
              <span className="workspace-kicker">Draft recovery</span>
              <h2>{builderProjectLoading ? "Checking for a safe backend copy..." : "This browser draft cannot be read"}</h2>
              <p>
                The original browser value and its backup were left untouched. Saving and publishing are paused so neither value can be replaced with an empty project.
              </p>
            </div>
          </section>
        </main>
      </div>
    );
  }

  const activeHelper =
    builderCopy.tabs[activeTab]?.helper ||
    builderTabs.find((tab) => tab.id === activeTab)?.helper ||
    "";
  const templateCopy = templateModalText[templateLang] || templateModalText.en;
  const projectDisplayName =
    builderCopy.projectNames[project.name] ||
    project.name;
  const mobileCopy =
    (mobileBlockerCopy[lang] || mobileBlockerCopy.en)[activeTab] ||
    (mobileBlockerCopy[lang] || mobileBlockerCopy.en).default;
  const pageBuilderClassName =
    getPageBuilderThemeClassName({
      mode: appThemeMode || "light",
      preview,
      renderMode: preview ? "preview" : "editing",
    }) +
    (activeTab === "forms" ? " forms-workspace-active" : "") +
    (activeTab === "responses" ? " responses-workspace-active" : "") +
    (isPhoneDevice ? " builder-phone-blocked" : "");
  const getStarterDisplay = (starter) => {
    if (templateLang !== "ar") return starter;
    const translated = starterArabicText[starter.id] || {};
    return {
      ...starter,
      ...translated,
      tags: translated.tags || starter.tags,
    };
  };
  const handleBuilderTextFieldKeyDown = (event) => {
    if (!isBuilderTextEditingTarget(event.target)) return;

    if ((event.key === " " || event.code === "Space") && event.defaultPrevented) {
      if (insertSpaceIntoEditableTarget(event.target)) {
        event.stopPropagation();
      }
      return;
    }

    event.stopPropagation();
  };

  return (
    <div
      className={pageBuilderClassName}
      onKeyDown={handleBuilderTextFieldKeyDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
    >
      <div className="builder-desktop-shell">
        <PageBuilderWorkspaceHeader
          activeHelper={activeHelper}
          activeTab={activeTab}
          activeTopbarAction={activeTopbarAction}
          builderCopy={builderCopy}
          demoMode={demoMode}
          displayName={projectDisplayName}
          handlePreviewClick={handlePreviewClick}
          hideWorkspaceTabs={hideWorkspaceTabs}
          openPreviewPage={openPreviewPage}
          preview={preview}
          project={project}
          renderWorkspaceNavigator={renderWorkspaceNavigator}
          saveProject={saveProject}
          setActiveTopbarAction={setActiveTopbarAction}
          setModal={setModal}
          setPreview={setPreview}
          setViewport={setViewport}
          viewport={viewport}
          viewports={viewports}
        />

        {renderActiveTab()}
      </div>

      <div className="builder-mobile-blocker">
        <div>
          <h2>{mobileCopy.title}</h2>
          <p>{mobileCopy.message}</p>
        </div>
      </div>

      <PageBuilderModals
        activeTab={activeTab}
        applyStarter={applyStarter}
        closeStarterModal={() => setModal(null)}
        confirmDeletePendingUser={confirmDeletePendingUser}
        confirmDeletePendingPage={confirmDeletePendingPage}
        confirmDeleteSelectedElement={confirmDeleteSelectedElement}
        elementPendingDelete={elementPendingDelete}
        getStarterDisplay={getStarterDisplay}
        modal={modal}
        previewOverlapWarnings={previewOverlapWarnings}
        publishOverlapWarnings={publishOverlapWarnings}
        confirmPublishWithOverlaps={() => publishProject(true)}
        setElementPendingDelete={setElementPendingDelete}
        pagePendingDelete={pagePendingDelete}
        setPreviewOverlapWarnings={setPreviewOverlapWarnings}
        setPublishOverlapWarnings={setPublishOverlapWarnings}
        setPagePendingDelete={setPagePendingDelete}
        setUserPendingDelete={setUserPendingDelete}
        starterSystems={starterSystems}
        templateCopy={templateCopy}
        templateLang={templateLang}
        userPendingDelete={userPendingDelete}
      />

      <PageBuilderStatusBar toast={toast} />
    </div>
  );
}
