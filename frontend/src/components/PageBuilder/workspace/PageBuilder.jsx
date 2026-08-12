import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Baseline,
  Bold,
  ClipboardPaste,
  Copy,
  CopyPlus,
  Eye,
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
import LoadingBar from "../../common/LoadingBar";
import {
  deferEffectStateUpdate,
  normalizeRuntimeAnswerValue,
} from "./pageBuilderWorkspace.helpers";
import {
  STORAGE_KEY,
  MAX_BUILDER_TEXT_FONT_SIZE_PX,
  parseBuilderTextFontSize,
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
  createAction,
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
  createNextGeneratedPageName,
  createUniqueBuilderPageName,
  createUniquePublicPageSlug,
  getStandaloneFormPath,
  normalizeProjectPageRouting,
  sanitizeSubdomain,
  setProjectDefaultPage,
} from "../core/PageBuilder.routing";
import { parseCarouselSlides, serializeCarouselSlides } from "../ui/PageBuilderCarousel.utils";
import PageBuilderModals from "./PageBuilderModals";
import PageDeleteConfirmModal from "../modals/PageDeleteConfirmModal";
import PageBuilderStatusBar from "./PageBuilderStatusBar";
import PageBuilderWorkspaceHeader from "./PageBuilderWorkspaceHeader";
import SiteRenderer from "../core/PageBuilder.siteRenderer";
import {
  clampEditorZoom,
  getArtboardElementPosition,
  getArtboardLogicalWidth,
  getEditorCameraStageWidth,
} from "../core/PageBuilder.artboard";
import {
  isSmartResponsiveProject,
  withAutoResponsiveOverride,
} from "../core/PageBuilder.responsiveCapabilities";
import {
  compareLegacyPageWithSmartShadow,
  getSmartProjectLayoutDiagnostics,
  resolvePageResponsiveLayout,
} from "../core/PageBuilder.responsiveLayout";
import ButtonColorControls from "./ButtonColorControls";
import PageBuilderPageInspector from "./PageBuilderPageInspector";
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
  createBuilderSiteMember,
  deleteBuilderSiteMember,
  fetchBuilderProject,
  fetchBuilderSiteMembers,
  fetchWebsiteSettings,
  publishBuilderProject,
  unpublishBuilderProject,
  updateBuilderSiteBinding,
  updateBuilderProject,
  updateBuilderSiteMember,
  updateWebsiteSettings,
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
  isBuilderTerminalConflictError,
} from "../core/PageBuilder.errors";
import {
  applyThemeModeToProject,
  getThemeFontStack,
  getPageBuilderThemeClassName,
  pageBuilderFontFamilyOptions,
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
  getFooterLinkItems,
  getFooterLinkUrlError,
} from "../core/PageBuilder.footerLinks";
import {
  splitLines,
  splitEditableLines,
  getListItems,
  getCanvasTextSelectionRange,
  createDomTextRange,
  getFloatingToolbarPlacement,
  createInputTextSelection,
  getTextBlockFormats,
  getTextBlockIndexesForRange,
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
  builderVideoMaxBytes,
  builderVideoMimeTypes,
  builderDocumentMaxBytes,
  builderDocumentMimeTypes,
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
  getMetricMinimumHeight,
  getDirectElementMinimumSize,
  getSectionCanvasHeight,
  compactDirectSectionAfterElementRemoval,
  convertSectionToDirectLayout,
  positionsOverlap,
  getProjectOverlapWarnings as getProjectOverlapWarningsFromLayout,
  snapToGrid,
  getDragCandidatePosition,
  constrainResizeToSiblingElements,
  getMovedElementPosition,
  createMovedFreeElement,
  commitDirectElementInteraction,
  commitDirectElementGroupInteraction,
  getGroupDragPreviewPositions,
  getMarqueeSelectionIds,
  getSmartGuideSnap,
  getPositionCollectionBounds,
  moveElementBehindText,
  moveElementToFront,
} from "../core/PageBuilder.layout";
import {
  clampElementToBounds,
  clientPointToCanvasLocal,
  getVisibleCanvasLocalBounds,
  getImmediateParentCanvasGeometry,
} from "../core/PageBuilder.bounds";
import {
  buildFormConnectionUpdate,
  cleanBuilderProject,
  cleanBuilderProjectWithRepairs,
  normalizeFormReference,
  getBuilderProjectName,
  getBuilderProjectSlug,
  getDraftProjectFromRecord,
  getDraftProjectFromRecordWithRepairs,
} from "../core/PageBuilder.project";
import {
  normalizeElementAlignSelf,
  getElementLayoutWidth,
  getElementAlignControlValue,
  getElementPlacementMargins,
  isDirectionalElementPlacement,
  getClosestColumnIdFromEvent,
} from "../core/PageBuilder.elementLayout";
import {
  getBuilderDraftReadStatus,
  hasUnreadableBuilderDraft,
  loadInitialProject,
} from "../core/PageBuilder.storage";
import {
  clearBuilderRecovery,
  getBuilderRecoveryStorageKey,
  hashBuilderRecoverySchema,
} from "../core/PageBuilder.recovery";
import {
  BUILDER_SAVE_STATES,
  canStartBuilderCloudMutation,
  deriveBuilderCloudSaveState,
  getAcknowledgedBuilderSaveState,
  getBuilderSaveStateLabel,
  isNewerBuilderCloudSaveMessage,
  shouldDeferBuilderCloudSave,
  shouldBlockBuilderUnload,
  stopBuilderSaveScheduling,
} from "../core/PageBuilder.saveState";
import {
  isBuilderReloadShortcut,
  requestBuilderUnloadWarning,
} from "../core/PageBuilder.unloadGuard";
import {
  createBuilderSaveCoordinator,
  createBuilderSaveEntry,
} from "../core/PageBuilder.saveCoordinator";
import {
  getBuilderPublicationLabel,
  getBuilderPublicationState,
  prepareBuilderProjectForPublish,
  runBuilderPublishSingleFlight,
} from "../core/PageBuilder.publishState";
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
  validateBuilderSaveAcknowledgement,
  validateBuilderSchemaAcknowledgement,
} from "../core/PageBuilder.persistence";
import {
  getPersistableProject,
  serializePersistableProject,
} from "../core/PageBuilder.editorState";
import {
  mergeBuilderDraftSchemas,
  resolveBuilderDraftConflicts,
  resolveBuilderDraftConflictsPreferLocal,
} from "../core/PageBuilder.merge";
import {
  resolveInspectorMode,
  resolveInspectorPage,
} from "../core/PageBuilder.inspector";
import {
  getBuilderProjectIdFromPath,
  getBuilderWorkspaceFromPath,
  getBuilderWorkspacePath,
} from "../core/PageBuilder.workspaceRouting";
import useDebouncedProjectStorage, {
  isNewerExternalDraftMessage,
} from "./hooks/useDebouncedProjectStorage";
import BuilderConflictResolution from "./BuilderConflictResolution";
import {
  adoptBuilderServerRuntime,
  prepareBuilderServerAdoption,
  runBuilderAutomaticRebase,
} from "../core/PageBuilder.conflict";

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
  getBuilderAssetFileName,
  parsePhotoProofingContent,
  serializePhotoProofingContent,
} from "../core/PageBuilder.uploadHandlers";
import {
  createRuntimeFormRenderers,
} from "../core/PageBuilder.runtime";
import {
  createElementRenderer,
} from "../core/PageBuilder.elementRenderer";
import { getElementHeadingTag, getHeadingLevelFromFormat } from "../core/PageBuilder.heading";
import {
  resolveReservationBlockValue,
} from "../core/PageBuilder.reservations";
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
const BUILDER_CLOUD_SYNC_CHANNEL = "madar-builder-cloud-sync";

const inlineTextElementTypes = new Set(["heading", "text", "button", "list"]);

const findBuilderDataElement = (root, attribute, value) => {
  if (!root || value === null || value === undefined) return null;
  const expectedValue = String(value);
  return Array.from(root.querySelectorAll(`[${attribute}]`))
    .find((candidate) => candidate.getAttribute(attribute) === expectedValue) || null;
};

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
  const match = pathname.match(/^\/page-builder\/(?:projects\/[^/?#]+\/)?([^/?#]+)/);
  if (!match) return null;
  return builderTabIdByPathSegment[match[1]] || null;
};

const getBuilderDesignPanelFromPath = (pathname = "") => {
  const builderPath = String(pathname).replace(/^\/page-builder\/projects\/[^/?#]+/, "/page-builder");
  if (/^\/page-builder\/(?:theme|themes|website-theme|site-theme)(?:[/?#]|$)/.test(builderPath)) {
    return "Themes";
  }
  const match = builderPath.match(/^\/page-builder\/(?:pages|design)\/([^/?#]+)/);
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

const getWebsiteSettingsPayload = (project = {}) => {
  const siteChrome = { ...defaultSiteChrome, ...(project.siteChrome || {}) };
  return {
    standard_path_slug: sanitizeSubdomain(project.publish?.subdomain || ""),
    brand: String(siteChrome.brand || "").trim(),
    footer_store_name: String(siteChrome.footerStoreName || "").trim(),
    logo_url: String(siteChrome.logoUrl || "").trim(),
    contact_email: String(siteChrome.contactEmail || "").trim(),
    phone: String(siteChrome.phone || "").trim(),
    description: String(siteChrome.description || "").trim(),
  };
};

const websiteSettingsPayloadChanged = (previousProject, nextProject) =>
  JSON.stringify(getWebsiteSettingsPayload(previousProject)) !==
  JSON.stringify(getWebsiteSettingsPayload(nextProject));

// Non-content placeholder used only while an existing routed project is being
// fetched. It is never rendered, persisted, recovered, or published.
const createHydrationPlaceholder = () => ({
  id: "",
  name: "",
  pages: [],
  forms: [],
  workflows: [],
  roles: [],
  users: [],
  collections: [],
  theme: {},
  siteChrome: {},
  publish: {},
  activePageId: "",
  activeFormId: "",
  activeWorkflowId: "",
  activeRoleId: "",
});

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

const stripAutosaveMetadata = (project = {}) => getPersistableProject(project);

const getAutosaveSnapshot = (project = {}) => serializePersistableProject(project);

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

export function BuilderSidebarActions({
  isSavingProject,
  lastCloudSavedAt,
  onSave,
  onPreview,
  onGoLive,
  publicationState,
  saveDisabled = false,
  saveState,
}) {
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
      <p className="builder-note" role="status" aria-live="polite">
        {getBuilderSaveStateLabel(saveState)}
        {saveState === BUILDER_SAVE_STATES.savedCloud && lastCloudSavedAt
          ? ` at ${lastCloudSavedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
          : ""}
      </p>
      <button
        type="button"
        className="page-primary-action builder-sidebar-save-button"
        disabled={isSavingProject || saveDisabled || !onSave}
        onClick={() => onSave?.()}
      >
        <Save size={17} aria-hidden="true" />
        <span>
          {isSavingProject
            ? "Saving..."
            : saveState === BUILDER_SAVE_STATES.saveFailed
              ? "Retry save"
              : "Save"}
        </span>
      </button>
      <p className="builder-note" data-testid="builder-publication-state">
        {saveState === BUILDER_SAVE_STATES.conflict
          ? "Publish blocked by conflict"
          : getBuilderPublicationLabel(publicationState)}
      </p>
      <button
        type="button"
        className="page-primary-action builder-sidebar-save-button"
        disabled={!onPreview}
        onClick={() => onPreview?.()}
      >
        <Eye size={17} aria-hidden="true" />
        <span>Preview site</span>
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
  const routeProjectId = getBuilderProjectIdFromPath(location.pathname);
  const routeWorkspace = getBuilderWorkspaceFromPath(location.pathname);
  const routeTab = getBuilderTabFromPath(location.pathname);
  const routeDesignPanel = getBuilderDesignPanelFromPath(location.pathname);
  const legacyStorageKey = getBuilderStorageKey(user?.id);
  const recoveryIdentity = useMemo(() => ({
    userId: user?.id,
    tenantId: user?.tenant_id ?? user?.tenantId,
    projectId: routeProjectId,
  }), [routeProjectId, user?.id, user?.tenantId, user?.tenant_id]);
  const scopedStorageKey = getBuilderRecoveryStorageKey(recoveryIdentity);
  const [project, setProject] = useState(() =>
    withDefaultLandingPage(
      demoMode
        ? getInitialWorkspaceProject({ demoMode, storageKey: legacyStorageKey })
        : createHydrationPlaceholder()
    )
  );
  const hasProtectedUnreadableDraft = demoMode && hasUnreadableBuilderDraft(legacyStorageKey);
  const hasUnrecoverableBrowserDraft =
    demoMode && getBuilderDraftReadStatus(legacyStorageKey) === "unrecoverable";
  const [builderProjectRecord, setBuilderProjectRecord] = useState(null);
  const [builderProjectLoading, setBuilderProjectLoading] = useState(
    !demoMode && Boolean(routeProjectId)
  );
  const recoveryContext = useMemo(() => ({
    ...recoveryIdentity,
    baseDraftRevision: Number(builderProjectRecord?.draft_revision) || 0,
    baseSchemaHash: hashBuilderRecoverySchema(builderProjectRecord?.draft_schema || {}),
  }), [builderProjectRecord?.draft_revision, builderProjectRecord?.draft_schema, recoveryIdentity]);
  const {
    acknowledgeCloudSave,
    adoptCloudRevision,
    getLastPersistedAt: getLastLocalDraftPersistedAt,
    hasUnsavedChanges: hasUnsavedLocalDraftChanges,
    persistNow: persistProjectNow,
    sourceId: draftSourceId,
  } = useDebouncedProjectStorage({
    delay: 2000,
    disabled: demoMode || builderProjectLoading || hasProtectedUnreadableDraft,
    enableBrowserPersistence: demoMode,
    project,
    recoveryContext,
    storageKey: scopedStorageKey,
  });
  const [internalActiveTab, setInternalActiveTab] = useState(initialTab || routeTab || "design");
  const activeTab = hideWorkspaceTabs ? internalActiveTab : (routeTab || "design");
  const [designPanel, setDesignPanelState] = useState(routeDesignPanel || "Pages");
  const [viewport, setViewport] = useState("desktop");
  const [preview, setPreview] = useState(false);
  const [legacyShadowEnabled, setLegacyShadowEnabled] = useState(false);
  const [editorViewportWidth, setEditorViewportWidth] = useState(0);
  const [manualEditorZoom, setManualEditorZoom] = useState(1);
  const logicalArtboardWidth = getArtboardLogicalWidth(viewport);
  const canvasScale = manualEditorZoom;
  const cameraStageWidth = getEditorCameraStageWidth(logicalArtboardWidth, canvasScale);
  const [selected, setSelected] = useState(() => ({
    type: "page",
    id: getDefaultBuilderPageId(project) || null,
  }));
  const [storedSelectedElementIds, setSelectedElementIds] = useState([]);
  const [modal, setModal] = useState(null);
  const [dragState, setDragState] = useState(null);
  const [selectionMarquee, setSelectionMarquee] = useState(null);
  const [paletteDropSectionId, setPaletteDropSectionId] = useState("");
  const [elementPendingDelete, setElementPendingDelete] = useState(null);
  const [userPendingDelete, setUserPendingDelete] = useState(null);
  const [pagePendingDelete, setPagePendingDelete] = useState(null);
  const [homepageOverridePending, setHomepageOverridePending] = useState(null);
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
  const [reloadConfirmationOpen, setReloadConfirmationOpen] = useState(false);
  const [conflictDetails, setConflictDetails] = useState(null);
  const [conflictServerCandidate, setConflictServerCandidate] = useState(null);
  const [conflictMergeState, setConflictMergeState] = useState(null);
  const [saveState, setSaveState] = useState(
    demoMode ? BUILDER_SAVE_STATES.clean : BUILDER_SAVE_STATES.loading
  );
  const [lastCloudSavedAt, setLastCloudSavedAt] = useState(null);
  const [isSavingProject, setIsSavingProject] = useState(false);
  const [isUnpublishingProject, setIsUnpublishingProject] = useState(false);
  const [isBindingPublicProject, setIsBindingPublicProject] = useState(false);
  const [liveSitePath, setLiveSitePath] = useState("");
  const [websiteSettings, setWebsiteSettings] = useState(null);
  const [siteMembers, setSiteMembers] = useState([]);
  const [siteMembersLoading, setSiteMembersLoading] = useState(false);
  const [siteMembersError, setSiteMembersError] = useState("");
  const [siteMemberMutationId, setSiteMemberMutationId] = useState("");
  const [activeTopbarAction, setActiveTopbarAction] = useState("");
  const [quizOptionsOpen, setQuizOptionsOpen] = useState(false);
  const [assetUploadBusy, setAssetUploadBusy] = useState(false);
  const [logoUrlDraft, setLogoUrlDraft] = useState(() => project.siteChrome?.logoUrl || "");
  const [logoUrlDraftEdited, setLogoUrlDraftEdited] = useState(false);
  const projectRef = useRef(project);
  const appliedWebsiteSettingsSignatureRef = useRef("");
  const canvasShellRef = useRef(null);
  const dragPreviewFrameRef = useRef(null);
  const selectionMarqueeRef = useRef(null);
  const suppressCanvasClickRef = useRef(false);
  const preserveCanvasViewportRef = useRef(null);
  const pendingDragPreviewRef = useRef(null);
  const recentMetricAddRef = useRef(null);
  const userId = user?.id;
  const [textSelection, setTextSelection] = useState(null);
  const textSelectionRef = useRef(null);
  const [inlineFontSizeDraft, setInlineFontSizeDraft] = useState(null);
  const [hasCopiedElement, setHasCopiedElement] = useState(false);
  const [inlineToolbarPosition, setInlineToolbarPosition] = useState(null);
  const inlineToolbarRef = useRef(null);
  const inlineToolbarInteractionRef = useRef(false);
  const elementClipboardRef = useRef(null);
  const backendAutosaveTimerRef = useRef(null);
  const backendProjectSnapshotRef = useRef("");
  const baseSchemaRef = useRef(getPersistableProject(project));
  const pendingBackendProjectSnapshotRef = useRef("");
  const builderProjectRecordRef = useRef(builderProjectRecord);
  const currentDraftRevisionRef = useRef(Number(builderProjectRecord?.draft_revision) || 0);
  const serverAdoptionGenerationRef = useRef(0);
  const latestAcknowledgedSaveOperationRef = useRef(0);
  const remoteSaveInFlightRef = useRef(false);
  const remoteSaveActiveSnapshotRef = useRef("");
  const remoteSavePromiseRef = useRef(null);
  const saveCoordinatorRef = useRef(null);
  const publishPromiseRef = useRef(null);
  const pendingRemoteSaveRef = useRef(null);
  const conflictRef = useRef(false);
  const siteChromeConflictResolutionRef = useRef(false);
  const cloudSyncChannelRef = useRef(null);
  const hydrationCompleteRef = useRef(demoMode);
  const pendingExternalDraftRef = useRef(null);
  const dragStateRef = useRef(dragState);
  const urlValidationToastShownRef = useRef(false);
  const allowNextUnloadRef = useRef(false);

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

  const broadcastCloudSave = useCallback((savedRecord) => {
    const revision = Number(savedRecord?.draft_revision) || 0;
    if (!revision) return;
    cloudSyncChannelRef.current?.postMessage({
      type: "cloud_saved",
      sourceId: draftSourceId,
      projectId: routeProjectId,
      tenantId: String(recoveryIdentity.tenantId || ""),
      revision,
      timestamp: Date.parse(savedRecord?.updated_at) || Date.now(),
    });
  }, [draftSourceId, recoveryIdentity.tenantId, routeProjectId]);

  const loadSiteMembers = useCallback(async () => {
    if (demoMode) {
      setSiteMembers(Array.isArray(projectRef.current?.users) ? projectRef.current.users : []);
      setSiteMembersError("");
      return;
    }
    if (!routeProjectId) return;

    setSiteMembersLoading(true);
    setSiteMembersError("");
    try {
      const members = await fetchBuilderSiteMembers(routeProjectId);
      setSiteMembers(Array.isArray(members) ? members : []);
    } catch (error) {
      setSiteMembersError(error?.message || "Could not load subdomain users.");
    } finally {
      setSiteMembersLoading(false);
    }
  }, [demoMode, routeProjectId]);

  useEffect(() => {
    if (activeTab !== "users") return;
    loadSiteMembers();
  }, [activeTab, loadSiteMembers]);

  const stopAllCloudScheduling = useCallback(() => {
    stopBuilderSaveScheduling({
      autosaveTimerRef: backendAutosaveTimerRef,
      pendingRequestRef: pendingRemoteSaveRef,
      pendingSnapshotRef: pendingBackendProjectSnapshotRef,
      clearTimeoutFn: window.clearTimeout.bind(window),
      clearIntervalFn: window.clearInterval.bind(window),
    });
  }, []);

  const setActiveTab = useCallback(
    (nextTab) => {
      if (hideWorkspaceTabs) {
        setInternalActiveTab(nextTab);
        return;
      }

      const nextPath = routeProjectId
        ? getBuilderWorkspacePath(routeProjectId, nextTab, routeWorkspace)
        : builderTabPathById[nextTab];
      if (nextPath && location.pathname !== nextPath) {
        navigate(nextPath);
      }
    },
    [hideWorkspaceTabs, location.pathname, navigate, routeProjectId, routeWorkspace]
  );

  const setDesignPanel = useCallback(
    (nextPanel) => {
      setDesignPanelState(nextPanel);
      if (hideWorkspaceTabs) return;

      const designBasePath = routeProjectId
        ? getBuilderWorkspacePath(routeProjectId, "design", routeWorkspace)
        : builderTabPathById.design;
      const nextPath = routeProjectId
        ? nextPanel === "Pages"
          ? designBasePath
          : `${designBasePath}/${nextPanel.toLowerCase()}`
        : builderDesignPanelPathById[nextPanel] || builderTabPathById.design;
      if (nextPath && location.pathname !== nextPath) {
        navigate(nextPath);
      }
    },
    [hideWorkspaceTabs, location.pathname, navigate, routeProjectId, routeWorkspace]
  );

  useEffect(() => {
    projectRef.current = project;
  }, [project]);

  useLayoutEffect(() => {
    const shell = canvasShellRef.current;
    if (!shell || activeTab !== "design") return undefined;

    const updateEditorViewport = () => {
      const computedStyle = window.getComputedStyle(shell);
      const horizontalPadding =
        (Number.parseFloat(computedStyle.paddingLeft) || 0) +
        (Number.parseFloat(computedStyle.paddingRight) || 0);
      const availableWidth = Math.max(0, shell.clientWidth - horizontalPadding);
      setEditorViewportWidth(availableWidth);
    };

    updateEditorViewport();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateEditorViewport);
      return () => window.removeEventListener("resize", updateEditorViewport);
    }

    const observer = new ResizeObserver(updateEditorViewport);
    observer.observe(shell);

    return () => observer.disconnect();
  }, [activeTab]);

  useEffect(() => () => {
    serverAdoptionGenerationRef.current += 1;
    saveCoordinatorRef.current?.invalidate();
  }, []);

  useEffect(() => {
    if (
      demoMode ||
      builderProjectLoading ||
      !hydrationCompleteRef.current ||
      !builderProjectRecordRef.current
    ) return;
    const currentSnapshot = getAutosaveSnapshot(project);
    return deferEffectStateUpdate(() => {
      setSaveState((current) => deriveBuilderCloudSaveState({
        hydrated: hydrationCompleteRef.current,
        conflict: conflictRef.current,
        saveActive: remoteSaveInFlightRef.current,
        currentSnapshot,
        acknowledgedSnapshot: backendProjectSnapshotRef.current,
        latestFailureRelevant:
          current === BUILDER_SAVE_STATES.saveFailed &&
          currentSnapshot !== backendProjectSnapshotRef.current,
      }));
    });
  }, [builderProjectLoading, demoMode, isSavingProject, project, saveState]);

  useEffect(() => {
    if (demoMode) return undefined;

    const handleBeforeUnload = (event) => {
      if (allowNextUnloadRef.current) return;
      requestBuilderUnloadWarning(event, shouldBlockBuilderUnload(saveState));
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [demoMode, saveState]);

  useEffect(() => {
    if (demoMode || !shouldBlockBuilderUnload(saveState)) return undefined;

    const handleReloadShortcut = (event) => {
      if (!isBuilderReloadShortcut(event)) return;
      event.preventDefault();
      setReloadConfirmationOpen(true);
    };

    window.addEventListener("keydown", handleReloadShortcut, true);
    return () => window.removeEventListener("keydown", handleReloadShortcut, true);
  }, [demoMode, saveState]);

  useEffect(() => {
    builderProjectRecordRef.current = builderProjectRecord;
  }, [builderProjectRecord]);

  useEffect(() => {
    dragStateRef.current = dragState;
  }, [dragState]);

  useLayoutEffect(() => {
    if (selected.type !== "element" || !selected.id) return undefined;

    const preservedViewport = preserveCanvasViewportRef.current;
    preserveCanvasViewportRef.current = null;
    if (preservedViewport?.selectedId === String(selected.id)) {
      const shell = canvasShellRef.current;
      if (shell) {
        shell.scrollLeft = preservedViewport.scrollLeft;
        shell.scrollTop = preservedViewport.scrollTop;
      }
      return undefined;
    }

    const frame = window.requestAnimationFrame(() => {
      const selectedId = String(selected.id);
      const elementFrame = Array.from(
        canvasShellRef.current?.querySelectorAll("[data-builder-element-id]") || []
      ).find((candidate) => candidate.dataset.builderElementId === selectedId);
      elementFrame?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [selected.id, selected.type, viewport]);

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
      navigate(
        routeProjectId
          ? getBuilderWorkspacePath(routeProjectId, "design", routeWorkspace)
          : builderTabPathById.design,
        { replace: true }
      );
    }
  }, [hideWorkspaceTabs, location.pathname, navigate, routeProjectId, routeTab, routeWorkspace]);

  useEffect(() => {
    const layoutVersion = Number(project.directLayoutVersion);
    const requiresLayoutNormalization =
      Number.isInteger(layoutVersion) && layoutVersion > 0 && layoutVersion < 4;

    if (!requiresLayoutNormalization) return;

    return deferEffectStateUpdate(() => {
      setProject((currentProject) => cleanBuilderProject(currentProject));
    });
  }, [project]);

  useEffect(() => {
    const pages = Array.isArray(project.pages) ? project.pages : [];
    const normalizedNames = pages.map((page) =>
      String(page?.name || page?.title || "Untitled page").trim().toLowerCase()
    );
    if (new Set(normalizedNames).size === normalizedNames.length) return;

    return deferEffectStateUpdate(() => {
      setProject((currentProject) => normalizeProjectPageRouting(currentProject));
    });
  }, [project.pages]);

  useEffect(() => {
    if (demoMode) return undefined;

    const considerExternalDraft = (candidate) => {
      if (!isNewerExternalDraftMessage(candidate, {
        currentBackendRevision: currentDraftRevisionRef.current,
        currentProjectId: recoveryIdentity.projectId,
        currentTenantId: String(recoveryIdentity.tenantId || ""),
        lastPersistedAt: getLastLocalDraftPersistedAt(),
        sourceId: draftSourceId,
      })) return;

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

      showToast("Another tab has unsaved changes for this project. Reload from Madar before choosing which copy to keep.");
    };

    const handleDraftStorageUpdate = (event) => {
      if (draftSyncChannel) return;
      if (event.key !== scopedStorageKey || !event.newValue) return;
      try {
        const envelope = JSON.parse(event.newValue);
        considerExternalDraft({
          baseDraftRevision: Number(envelope?.base_draft_revision) || 0,
          sourceId: "storage-fallback",
          revision: 0,
          storageKey: scopedStorageKey,
          projectId: String(envelope?.project_id || ""),
          tenantId: String(envelope?.tenant_id || ""),
          timestamp: Date.parse(envelope?.saved_at) || Date.now(),
          serializedProject: envelope?.schema ? serializePersistableProject(envelope.schema) : "",
        });
      } catch {
        // Malformed recovery values are handled by the recovery reader.
      }
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
    demoMode,
    draftSourceId,
    getLastLocalDraftPersistedAt,
    hasUnsavedLocalDraftChanges,
    recoveryIdentity.projectId,
    recoveryIdentity.tenantId,
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

    if (
      (pending.projectId && pending.projectId !== recoveryIdentity.projectId) ||
      (pending.tenantId && String(pending.tenantId) !== String(recoveryIdentity.tenantId || "")) ||
      Number(pending.baseDraftRevision || 0) < currentDraftRevisionRef.current
    ) {
      pendingExternalDraftRef.current = null;
      return;
    }
    pendingExternalDraftRef.current = null;
    showToast("Another tab has a local copy. The current server-backed editor was not changed.");
  }, [
    dragState,
    getLastLocalDraftPersistedAt,
    hasUnsavedLocalDraftChanges,
    isSavingProject,
    recoveryIdentity.projectId,
    recoveryIdentity.tenantId,
    showToast,
  ]);

  useEffect(() => {
    if (demoMode) return;

    let cancelled = false;
    if (!routeProjectId) {
      return undefined;
    }

    const cacheKey = `${user?.id || "current"}:${routeProjectId}`;
    const loadBackendProject = async () => {
      stopAllCloudScheduling();
      hydrationCompleteRef.current = false;
      conflictRef.current = false;
      setConflictDetails(null);
      setConflictServerCandidate(null);
      setBuilderProjectLoading(true);
      setSaveState(BUILDER_SAVE_STATES.loading);

      try {
        if (!builderInitialProjectLoadPromises.has(cacheKey)) {
          builderInitialProjectLoadPromises.set(
            cacheKey,
            fetchBuilderProject(routeProjectId)
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
            builderProjectRecordRef.current = null;
            backendProjectSnapshotRef.current = "";
            setSaveState(BUILDER_SAVE_STATES.saveFailed);
          }
          return;
        }

        const loadedResult = getDraftProjectFromRecordWithRepairs(fullRecord);
        const loadedProject = withDefaultLandingPage(loadedResult.project);

        if (!loadedProject) return;

        if (!cancelled) {
          const nextProject = loadedProject;
          const adoption = prepareBuilderServerAdoption({
            serverRecord: fullRecord,
            routedProjectId: routeProjectId,
            normalizeProject: () => nextProject,
            createSnapshot: getAutosaveSnapshot,
          });
          saveCoordinatorRef.current?.invalidate();
          adoptBuilderServerRuntime({
            adoption,
            refs: {
              builderProjectRecord: builderProjectRecordRef,
              backendDraftRevision: currentDraftRevisionRef,
              requestGeneration: serverAdoptionGenerationRef,
              project: projectRef,
              baseSchema: baseSchemaRef,
              acknowledgedSnapshot: backendProjectSnapshotRef,
              pendingSnapshot: pendingBackendProjectSnapshotRef,
              pendingRequest: pendingRemoteSaveRef,
              activeSnapshot: remoteSaveActiveSnapshotRef,
              savePromise: remoteSavePromiseRef,
              saveInFlight: remoteSaveInFlightRef,
              pendingExternalDraft: pendingExternalDraftRef,
              hydrationComplete: hydrationCompleteRef,
              conflict: conflictRef,
            },
            stopScheduling: stopAllCloudScheduling,
          });
          setBuilderProjectRecord(fullRecord);
          // Hydration, including compatibility normalization, is read-only.
          // Establish the normalized server draft as the baseline so opening
          // an editor can never schedule a write by itself.
          setProject(nextProject);
          setSelected({ type: "page", id: nextProject.activePageId });
          adoptCloudRevision(
            serializePersistableProject(nextProject),
            Date.parse(fullRecord.updated_at) || Date.now(),
            Number(fullRecord.draft_revision) || 0
          );
          setSaveState(BUILDER_SAVE_STATES.savedCloud);

          // The server draft is authoritative. Remove any obsolete browser recovery
          // for this project instead of offering it as an alternate version.
          clearBuilderRecovery(recoveryIdentity);
          // Compatibility normalization is an in-memory read model. It never
          // schedules a cloud write until the user makes a real content edit.
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
          hydrationCompleteRef.current = false;
          setSaveState(BUILDER_SAVE_STATES.saveFailed);
          showToast("The cloud project could not be loaded. Local recovery was not applied.");
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
  }, [
    adoptCloudRevision,
    demoMode,
    recoveryIdentity,
    routeProjectId,
    showToast,
    stopAllCloudScheduling,
    user?.id,
  ]);

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

    const subdomain = sanitizeSubdomain(
      websiteSettings?.standard_path_slug || websiteSettings?.subdomain || ""
    );

    if (!subdomain) return;

    return deferEffectStateUpdate(() => {
      const nextPath = resolveLiveSitePath(subdomain);
      setLiveSitePath((current) => (current === nextPath ? current : nextPath));
    });
  }, [demoMode, websiteSettings?.standard_path_slug, websiteSettings?.subdomain]);

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
    () => resolveInspectorPage(project),
    [project]
  );
  const smartResponsiveEnabled = isSmartResponsiveProject(project);
  const activeSmartDiagnostics = useMemo(
    () => {
      if (!smartResponsiveEnabled || !activePage) return [];
      const resolved = resolvePageResponsiveLayout({
        project,
        page: activePage,
        viewportMode: viewport,
        layoutWidth: logicalArtboardWidth,
      });
      return (resolved?.diagnostics || []).map((diagnostic) => ({
        ...diagnostic,
        pageId: activePage.id,
        layoutWidth: logicalArtboardWidth,
        viewportMode: viewport,
      }));
    },
    [activePage, logicalArtboardWidth, project, smartResponsiveEnabled, viewport]
  );
  const legacyShadowComparison = useMemo(
    () => legacyShadowEnabled && !smartResponsiveEnabled
      ? compareLegacyPageWithSmartShadow({
          project,
          page: activePage,
          viewportMode: viewport,
          layoutWidth: logicalArtboardWidth,
        })
      : null,
    [
      activePage,
      legacyShadowEnabled,
      logicalArtboardWidth,
      project,
      smartResponsiveEnabled,
      viewport,
    ]
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
    const activePageSlug = activePage?.slug === "/" ? "" : activePage?.slug || "";
    window.open(
      `/page-builder/projects/${encodeURIComponent(routeProjectId)}/preview${activePageSlug}`,
      "_blank",
      "noopener,noreferrer"
    );
  };

  const openFormPreviewPage = (formId = activeForm?.id) => {
    if (!formId) return;
    window.open(
      `/page-builder/projects/${encodeURIComponent(routeProjectId)}/form-preview/${encodeURIComponent(formId)}`,
      "_blank",
      "noopener,noreferrer"
    );
  };

  const openPublicFormPage = (formId = activeForm?.id) => {
    if (!formId) return;
    const publicFormPath = getStandaloneFormPath(project, formId);
    window.open(publicFormPath, "_blank", "noopener,noreferrer");
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

  const activePageLayers = useMemo(() =>
    (activePage?.sections || []).flatMap((section) =>
      [...(section.freeElements || [])].reverse().map((element) => ({
        element,
        sectionId: section.id,
        sectionName: section.name || "Section",
      }))
    ), [activePage]);

  const effectiveSelectedElementIds = useMemo(() => {
    if (selected.type !== "element" || !selected.id) return [];

    const availableElementIds = new Set(
      activePageLayers.map(({ element }) => element.id)
    );
    if (!availableElementIds.has(selected.id)) return [];

    const validSelection = storedSelectedElementIds.filter((elementId) =>
      availableElementIds.has(elementId)
    );
    return validSelection.includes(selected.id) ? validSelection : [selected.id];
  }, [activePageLayers, selected.id, selected.type, storedSelectedElementIds]);

  const selectCanvasElement = useCallback((elementId, {
    additive = false,
    forceSingle = false,
  } = {}) => {
    const targetLayer = activePageLayers.find(({ element }) => element.id === elementId);
    if (!targetLayer) return;

    const sameSectionSelection = effectiveSelectedElementIds.filter((selectedId) =>
      activePageLayers.some(({ element, sectionId }) =>
        element.id === selectedId && sectionId === targetLayer.sectionId
      )
    );
    let nextSelection;

    if (forceSingle) {
      nextSelection = [elementId];
    } else if (additive) {
      nextSelection = sameSectionSelection.includes(elementId)
        ? sameSectionSelection.filter((selectedId) => selectedId !== elementId)
        : [...sameSectionSelection, elementId];
    } else if (sameSectionSelection.includes(elementId) && sameSectionSelection.length > 1) {
      nextSelection = sameSectionSelection;
    } else {
      nextSelection = [elementId];
    }

    setSelectedElementIds(nextSelection);
    setSelected(nextSelection.length
      ? { type: "element", id: nextSelection.includes(elementId) ? elementId : nextSelection[nextSelection.length - 1] }
      : { type: "section", id: targetLayer.sectionId }
    );
  }, [activePageLayers, effectiveSelectedElementIds]);

  const selectAllCanvasElements = useCallback(() => {
    const selectedLayer = activePageLayers.find(({ element }) => element.id === selected.id);
    const sectionId = selected.type === "section"
      ? selected.id
      : selectedLayer?.sectionId || activePageLayers[0]?.sectionId;
    const elementIds = activePageLayers
      .filter((layer) => layer.sectionId === sectionId)
      .map(({ element }) => element.id);
    if (!elementIds.length) return;

    const shell = canvasShellRef.current;
    preserveCanvasViewportRef.current = {
      selectedId: String(elementIds[0]),
      scrollLeft: shell?.scrollLeft || 0,
      scrollTop: shell?.scrollTop || 0,
    };
    setSelectedElementIds(elementIds);
    setSelected({ type: "element", id: elementIds[0] });
    window.requestAnimationFrame(() => {
      const preservedViewport = preserveCanvasViewportRef.current;
      if (preservedViewport?.selectedId !== String(elementIds[0])) return;
      preserveCanvasViewportRef.current = null;
      if (shell) {
        shell.scrollLeft = preservedViewport.scrollLeft;
        shell.scrollTop = preservedViewport.scrollTop;
      }
    });
  }, [activePageLayers, selected.id, selected.type]);

  const clearCanvasElementSelection = useCallback(() => {
    const selectedLayer = activePageLayers.find(({ element }) => element.id === selected.id);
    setSelectedElementIds([]);
    setSelected({
      type: "section",
      id: selectedLayer?.sectionId || activePageLayers[0]?.sectionId || activePage?.sections?.[0]?.id || null,
    });
  }, [activePage?.sections, activePageLayers, selected.id]);

  const inspectorMode = resolveInspectorMode({
    selected,
    selectedElement,
    selectedSection,
    selectedColumn,
    activePage,
  });

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

  const reservationDefinitions = useMemo(
    () => reservationBlocks.filter(({ element }) => {
      const sourceId = element.connectedReservationBlockId;
      return !sourceId || sourceId === element.id;
    }),
    [reservationBlocks]
  );

  const reservationFormOptions = useMemo(
    () =>
      reservationDefinitions.map((block, index) => {
        const reservation = block.element.reservation || {};
        const title = reservation.title || block.element.name || `Reservation ${index + 1}`;
        const mode = reservation.bookingMode === "flexible" ? "flexible" : "restricted";
        const modeLabel = mode === "flexible" ? "Date request" : "Fixed slots";

        return {
          id: block.element.id,
          label: title,
          meta: `${modeLabel} - ${block.page.name}`,
          mode,
        };
      }),
    [reservationDefinitions]
  );
  const getReservationBlockValue = useCallback(
    (element) => resolveReservationBlockValue(element, project.pages),
    [project.pages]
  );

  const selectedRole = useMemo(() => {
    if (selected.type !== "role") return null;
    return safeProjectRoles.find((role) => role.id === selected.id) || null;
  }, [safeProjectRoles, selected]);

  const updateProject = useCallback((updater) => {
    setProject((prev) => updater(prev));
  }, []);

  useEffect(() => {
    if (demoMode || builderProjectLoading || !websiteSettings) return;

    const syncedValues = {
      subdomain: sanitizeSubdomain(
        websiteSettings.standard_path_slug || websiteSettings.subdomain || ""
      ),
      brand: String(websiteSettings.brand || ""),
      footerStoreName: String(websiteSettings.footer_store_name || ""),
      logoUrl: String(websiteSettings.logo_url || ""),
      contactEmail: String(websiteSettings.contact_email || ""),
      phone: String(websiteSettings.phone || ""),
      description: String(websiteSettings.description || ""),
    };
    if (!syncedValues.subdomain || !syncedValues.brand) return;

    const signature = JSON.stringify(syncedValues);
    if (appliedWebsiteSettingsSignatureRef.current === signature) return;
    appliedWebsiteSettingsSignatureRef.current = signature;

    updateProject((current) => {
      const currentPayload = getWebsiteSettingsPayload(current);
      const nextPayload = {
        standard_path_slug: syncedValues.subdomain,
        brand: syncedValues.brand.trim(),
        footer_store_name: syncedValues.footerStoreName.trim(),
        logo_url: syncedValues.logoUrl.trim(),
        contact_email: syncedValues.contactEmail.trim(),
        phone: syncedValues.phone.trim(),
        description: syncedValues.description.trim(),
      };
      if (JSON.stringify(currentPayload) === JSON.stringify(nextPayload)) return current;

      return {
        ...current,
        publish: {
          ...(current.publish || {}),
          subdomain: syncedValues.subdomain,
        },
        siteChrome: {
          ...defaultSiteChrome,
          ...(current.siteChrome || {}),
          brand: syncedValues.brand,
          footerStoreName: syncedValues.footerStoreName,
          logoUrl: syncedValues.logoUrl,
          contactEmail: syncedValues.contactEmail,
          phone: syncedValues.phone,
          description: syncedValues.description,
        },
      };
    });
  }, [builderProjectLoading, demoMode, updateProject, websiteSettings]);

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

  const getElementParentGeometry = useCallback((elementId) => {
    const elementFrame = findBuilderDataElement(
      canvasShellRef.current,
      "data-builder-element-id",
      elementId
    );
    return getImmediateParentCanvasGeometry(elementFrame, {
      coordinateScale: 1,
    });
  }, []);


  const updateSelectedSection = useCallback((changes) => {
    if (!selectedSection) return;
    updateSections((sections) => sections.map((section) =>
      section.id === selectedSection.id
        ? {
            ...section,
            ...changes,
            ...(changes.layout
              ? { layout: { ...(section.layout || {}), ...changes.layout } }
              : {}),
          }
        : section
    ));
  }, [selectedSection, updateSections]);

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
    const page = createPage(createNextGeneratedPageName(project.pages), [canvasSection], {
      canvasLayoutVersion: 1,
    });
    updateProject((prev) => normalizeProjectPageRouting({
      ...prev,
      pages: [...prev.pages, page],
      activePageId: page.id,
    }));
    setSelected({ type: "page", id: page.id });
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
    const reservationPlacementMode = type === "reservationRequest"
      ? "flexible"
      : type === "reservationFixedSlots"
        ? "restricted"
        : "";
    const elementType = reservationPlacementMode ? "reservationBlock" : type;
    const activePageIndex = project.pages.findIndex((page) => page.id === activePage?.id);
    const defaultNextPage = activePageIndex >= 0 ? project.pages[activePageIndex + 1] : null;
    const preferredReservationDefinition = reservationPlacementMode
      ? reservationDefinitions.find(({ element: candidate }) => {
          const candidateMode = candidate.reservation?.bookingMode === "flexible" ? "flexible" : "restricted";
          return candidateMode === reservationPlacementMode;
        })?.element
      : null;
    const element = createElement(
      elementType,
      elementType === "formBlock"
        ? { connectedFormId: project.activeFormId }
        : elementType === "imageButton"
          ? { action: createAction("goToPage", { pageId: defaultNextPage?.id || "" }) }
        : {}
    );
    const reservationPlacementOverrides = reservationPlacementMode
      ? {
          name: reservationPlacementMode === "flexible" ? "Date request" : "Fixed slots",
          reservationPlacementType: reservationPlacementMode,
          ...(preferredReservationDefinition
            ? {
                connectedReservationBlockId: preferredReservationDefinition.id,
                reservation: preferredReservationDefinition.reservation,
              }
            : {
                reservation: {
                  ...(element.reservation || {}),
                  bookingMode: reservationPlacementMode,
                  title: reservationPlacementMode === "flexible"
                    ? "Request an appointment"
                    : "Book an available slot",
                  description: reservationPlacementMode === "flexible"
                    ? "Choose the service, date, and time that works for you."
                    : "Choose one of the available dates and times.",
                  submitLabel: reservationPlacementMode === "flexible" ? "Send request" : "Book slot",
                },
              }),
        }
      : {};
    const resolvedOverrides = { ...reservationPlacementOverrides, ...overrides };
    const nextElementConnectedFormId = resolvedOverrides.connectedFormId || element.connectedFormId;
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
      const canvasHeight = getSectionCanvasHeight(targetSection, viewportName);
      const nextY = (targetSection.freeElements || []).reduce((bottom, item) => {
        const position = item.position?.[viewportName] || createPosition()[viewportName];
        return Math.max(bottom, (Number(position.y) || 0) + (Number(position.height) || 80));
      }, 8) + 16;
      const useDropPoint = viewportName === viewport && dropPoint;
      const responsiveEdge = viewportName === "mobile" ? 12 : 24;
      const width = elementType === "formBlock"
        ? canvasWidth - responsiveEdge * 2
        : Math.min(Number(base.width) || 380, canvasWidth - 24);
      const connectedForm = elementType === "formBlock"
        ? project.forms.find((form) => form.id === nextElementConnectedFormId)
        : null;
      const height = elementType === "formBlock"
        ? estimateFormBlockHeight(connectedForm, viewportName)
        : directElementHeight(element);

      const requestedPosition = {
        ...base,
        width,
        height,
        x: useDropPoint
          ? dropPoint.x - width / 2
          : responsiveEdge,
        y: useDropPoint ? dropPoint.y - height / 2 : nextY,
      };
      nextPosition[viewportName] = clampElementToBounds(
        requestedPosition,
        useDropPoint && dropPoint.bounds
          ? dropPoint.bounds
          : { x: 0, y: 0, width: canvasWidth, height: canvasHeight },
        {
          minWidth: getDirectElementMinimumSize(element).width,
          minHeight: getDirectElementMinimumSize(element).height,
          allowBottomOverflow: true,
        }
      );
      requiredHeights[viewportName] = Math.max(
        canvasHeight,
        nextPosition[viewportName].y + nextPosition[viewportName].height + 48
      );
    });

    const nextElement = { ...element, ...resolvedOverrides, mode: "direct", position: nextPosition };
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

      if (elementType === "metric") {
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
    return nextElement;
  };

  const handlePaletteDragStart = (event, type) => {
    event.dataTransfer.effectAllowed = "copy";
    event.dataTransfer.setData("application/x-madar-component", type);
    event.dataTransfer.setData("text/plain", type);
  };

  const getVisibleCanvasInsertPoint = (sectionId = "") => {
    const shell = canvasShellRef.current;
    if (!shell) return null;

    const frame = sectionId
      ? findBuilderDataElement(shell, "data-section-id", sectionId)
      : shell.querySelector(".direct-layout-frame");
    if (!frame) return null;

    const shellRect = shell.getBoundingClientRect();
    const frameRect = frame.getBoundingClientRect();
    const visibleLeft = Math.max(shellRect.left, frameRect.left);
    const visibleRight = Math.min(shellRect.right, frameRect.right);
    const visibleTop = Math.max(shellRect.top, frameRect.top);
    const visibleBottom = Math.min(shellRect.bottom, frameRect.bottom);

    if (visibleRight <= visibleLeft || visibleBottom <= visibleTop) return null;

    return clientPointToCanvasLocal(
      frame,
      (visibleLeft + visibleRight) / 2,
      (visibleTop + visibleBottom) / 2,
      { coordinateScale: 1 }
    );
  };

  const handlePaletteDrop = (event, section) => {
    event.preventDefault();
    event.stopPropagation();
    const type =
      event.dataTransfer.getData("application/x-madar-component") ||
      event.dataTransfer.getData("text/plain");
    if (!elementTypes.some((item) => item.id === type)) return;

    const localPoint = clientPointToCanvasLocal(
      event.currentTarget,
      event.clientX,
      event.clientY,
      { coordinateScale: 1 }
    );
    addComponentToSection(type, section.id, localPoint);
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

  const applyResponsiveDiagnosticAction = useCallback((diagnostic, action) => {
    const elementId = diagnostic?.elementIds?.[0];
    if (!elementId) return;
    if (action === "move_element") {
      setSelected({ type: "element", id: elementId });
      window.requestAnimationFrame(() => {
        findBuilderDataElement(document, "data-element-id", elementId)?.scrollIntoView?.({
          block: "center",
          inline: "center",
        });
      });
      showToast("Element selected. Drag it to resolve the collision.");
      return;
    }
    updateSections((sections) => sections.map((section) => {
      if (!["direct", "free"].includes(section.mode)) return section;
      let changed = false;
      const freeElements = (section.freeElements || []).map((element) => {
        if (element.id !== elementId) return element;
        changed = true;
        if (action === "reset_to_auto") {
          return withAutoResponsiveOverride(element, diagnostic.viewportMode || viewport);
        }
        const collisionPolicy = action === "mark_background" ? "background" : "overlay";
        return {
          ...element,
          responsive: {
            ...(element.responsive || {}),
            capabilities: {
              ...(element.responsive?.capabilities || {}),
              collisionPolicy,
            },
          },
        };
      });
      return changed ? { ...section, freeElements } : section;
    }));
    showToast(action === "reset_to_auto"
      ? "Responsive geometry reset to Auto."
      : action === "mark_background"
        ? "Element marked as an intentional background."
        : "Element marked as an intentional overlay.");
  }, [showToast, updateSections, viewport]);

  const setSelectedImageBehindText = useCallback((behindText) => {
    if (!selectedElement || selectedElement.type !== "image") return;

    const targetSection = activePage?.sections.find((section) =>
      section.mode === "direct" &&
      (section.freeElements || []).some((element) => element.id === selectedElement.id)
    );
    if (!targetSection) {
      showToast("Place the image on the free canvas to layer it behind text.");
      return;
    }
    if (behindText && !(targetSection.freeElements || []).some((element) =>
      ["heading", "text", "list"].includes(element.type)
    )) {
      showToast("Add a text, heading, or list element to this section first.");
      return;
    }

    const reorderedElements = behindText
      ? moveElementBehindText(targetSection.freeElements, selectedElement.id)
      : moveElementToFront(targetSection.freeElements, selectedElement.id);
    if (reorderedElements === targetSection.freeElements) {
      showToast(behindText ? "Image is already behind the text." : "Image is already in front.");
      return;
    }

    updateSections((sections) =>
      sections.map((section) => {
        if (section.id !== targetSection.id) return section;
        return { ...section, freeElements: reorderedElements };
      })
    );

    showToast(behindText ? "Image placed behind the text." : "Image moved in front of the text.");
  }, [activePage, selectedElement, updateSections]);

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
    const target = reservationBlocks.find((block) => block.element.id === elementId)?.element;
    const sourceId = target?.connectedReservationBlockId || elementId;
    const shouldUpdate = (element) =>
      element.id === elementId ||
      element.id === sourceId ||
      element.connectedReservationBlockId === sourceId;

    updateProject((prev) => ({
      ...prev,
      pages: prev.pages.map((page) => ({
        ...page,
        sections: page.sections.map((section) => {
          if (section.mode === "direct") {
            return {
              ...section,
              freeElements: (section.freeElements || []).map((element) =>
                shouldUpdate(element) ? merge(element) : element
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
                  shouldUpdate(element) ? merge(element) : element
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

  const copySelectedElement = ({ announce = true } = {}) => {
    if (!selectedElement) return false;
    elementClipboardRef.current = {
      element: selectedElement,
      pageId: activePage?.id || "",
      location: findElementLocation(selectedElement.id),
    };
    setHasCopiedElement(true);
    if (announce) showToast("Element copied. Press Ctrl+V or Cmd+V to paste.");
    return true;
  };

  const pasteCopiedElement = ({ announce = true } = {}) => {
    const clipboard = elementClipboardRef.current;
    if (!clipboard?.element || !activePage) return false;

    const selectedLocation = selectedElement ? findElementLocation(selectedElement.id) : null;
    const targetLocation = selectedLocation ||
      (clipboard.pageId === activePage.id ? clipboard.location : null);
    if (!targetLocation?.sectionId) {
      if (announce) showToast("Select an element where you want to paste the copy.");
      return false;
    }

    const copy = cloneWithNewIds(clipboard.element);
    copy.name = `${clipboard.element.name || "Element"} Copy`;

    if (targetLocation.isFree) {
      copy.mode = "direct";
      const anchor = selectedElement?.position || clipboard.element.position || createPosition();
      copy.position = Object.fromEntries(
        ["desktop", "tablet", "mobile"].map((viewportName) => {
          const sourcePosition = copy.position?.[viewportName] || createPosition()[viewportName];
          const anchorPosition = anchor?.[viewportName] || sourcePosition;
          return [viewportName, {
            ...sourcePosition,
            x: Math.max(0, (Number(anchorPosition.x) || 0) + 24),
            y: Math.max(0, (Number(anchorPosition.y) || 0) + 24),
          }];
        })
      );
    } else {
      copy.mode = "auto";
    }

    updateSections((sections) => sections.map((section) => {
      if (section.id !== targetLocation.sectionId) return section;

      if (targetLocation.isFree) {
        const elements = [...(section.freeElements || [])];
        elements.splice(Math.max(0, targetLocation.elementIndex + 1), 0, copy);
        return { ...section, freeElements: elements };
      }

      return {
        ...section,
        rows: (section.rows || []).map((row) => ({
          ...row,
          columns: (row.columns || []).map((column) => {
            if (column.id !== targetLocation.columnId) return column;
            const elements = [...(column.elements || [])];
            elements.splice(Math.max(0, targetLocation.elementIndex + 1), 0, copy);
            return { ...column, elements };
          }),
        })),
      };
    }));

    setSelected({ type: "element", id: copy.id });
    if (announce) showToast("Element pasted.");
    return true;
  };

  const duplicateSelectedElement = () => {
    if (!copySelectedElement({ announce: false })) return;
    if (pasteCopiedElement({ announce: false })) showToast("Element duplicated.");
  };

  useEffect(() => {
    if (activeTab !== "design" || preview || modal || elementPendingDelete) return undefined;

    const handleElementClipboardShortcut = (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      const key = String(event.key || "").toLowerCase();
      if (key !== "c" && key !== "v") return;

      const target = event.target;
      if (
        target instanceof Element &&
        target.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])")
      ) return;

      if (key === "c") {
        if (!selectedElement) return;
        event.preventDefault();
        copySelectedElement();
        return;
      }

      if (!elementClipboardRef.current) return;
      event.preventDefault();
      pasteCopiedElement();
    };

    document.addEventListener("keydown", handleElementClipboardShortcut, true);
    return () => document.removeEventListener("keydown", handleElementClipboardShortcut, true);
  }, [activePage, activeTab, elementPendingDelete, modal, preview, selectedElement]);

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
          return compactDirectSectionAfterElementRemoval(section, elementId);
        }

        const containsElement = section.rows.some((row) =>
          row.columns.some((column) => column.elements.some((element) => element.id === elementId))
        );
        if (!containsElement) return section;

        const rows = section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.filter((element) => element.id !== elementId),
            })),
          })).filter((row) => row.columns.some((column) => column.elements.length > 0));

        return {
          ...section,
          layout: {
            ...(section.layout || {}),
            minHeight: 120,
            minHeightByViewport: { desktop: 120, tablet: 120, mobile: 120 },
          },
          rows,
        };
      })
    );

    setSelected({ type: "page", id: activePage.id });
    setElementPendingDelete(null);
    showToast("Element deleted.");
  };

  const confirmDeletePendingUser = async () => {
    if (!userPendingDelete?.id) return;
    const membershipId = userPendingDelete.id;
    setSiteMemberMutationId(String(membershipId));
    try {
      if (!demoMode) {
        await deleteBuilderSiteMember(routeProjectId, membershipId);
      }
      setSiteMembers((current) =>
        current.filter((member) => String(member.id) !== String(membershipId))
      );
      if (selected.type === "user" && String(selected.id) === String(membershipId)) {
        setSelected({ type: "page", id: activePage?.id || project.activePageId || null });
      }
      setUserPendingDelete(null);
      showToast("Website access removed.");
    } catch (error) {
      setSiteMembersError(error?.message || "Could not remove website access.");
      showToast("Could not remove website access.");
    } finally {
      setSiteMemberMutationId("");
    }
  };

  const addSiteUser = async (payload) => {
    if (demoMode) {
      const fallbackUser = {
        ...createUser(),
        name: payload.full_name,
        email: payload.email,
        roleId: payload.role_id,
        status: payload.status === "disabled" ? "Disabled" : "Active",
        source: "admin",
      };
      setSiteMembers((current) => [fallbackUser, ...current]);
      showToast("User added.");
      return fallbackUser;
    }

    const member = await createBuilderSiteMember(routeProjectId, payload);
    if (!member) throw new Error("The server did not return the new user.");
    setSiteMembers((current) => [member, ...current]);
    setSelected({ type: "user", id: member.id });
    showToast("User created on the server.");
    return member;
  };

  const updateSiteUser = async (membershipId, updates) => {
    setSiteMemberMutationId(String(membershipId));
    setSiteMembersError("");
    try {
      if (demoMode) {
        setSiteMembers((current) =>
          current.map((member) =>
            String(member.id) === String(membershipId) ? { ...member, ...updates } : member
          )
        );
        return;
      }

      const member = await updateBuilderSiteMember(routeProjectId, membershipId, {
        ...(updates.roleId !== undefined ? { role_id: updates.roleId } : {}),
        ...(updates.status !== undefined ? { status: updates.status.toLowerCase() } : {}),
      });
      if (!member) throw new Error("The server did not return the updated user.");
      setSiteMembers((current) =>
        current.map((item) =>
          String(item.id) === String(membershipId) ? member : item
        )
      );
      showToast("User access updated.");
    } catch (error) {
      setSiteMembersError(error?.message || "Could not update this user.");
      showToast("Could not update this user.");
      await loadSiteMembers();
    } finally {
      setSiteMemberMutationId("");
    }
  };

  const requestDeleteSiteUser = (membershipId) => {
    const member = siteMembers.find(
      (item) => String(item.id) === String(membershipId)
    );
    if (member) setUserPendingDelete(member);
  };

  const findElementLocation = useCallback(
    (elementId) => findElementLocationInPage(activePage, elementId),
    [activePage]
  );

  const {
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
      writeBrowserDraft: demoMode,
    }), [demoMode, scopedStorageKey, showToast]);

  const enterTerminalConflict = useCallback((error, mergeState = null) => {
    conflictRef.current = true;
    stopAllCloudScheduling();
    persistProjectNow(projectRef.current);
    setConflictServerCandidate(mergeState?.serverRecord || null);
    setConflictMergeState(mergeState);
    setConflictDetails({
      detectedAt: Date.now(),
      localSavedAt: new Date().toISOString(),
      localBaseRevision: currentDraftRevisionRef.current,
      serverRevision:
        Number(mergeState?.serverRecord?.draft_revision) ||
        Number(error?.context?.current_revision) ||
        null,
      serverUpdatedAt: mergeState?.serverRecord?.updated_at || null,
      conflicts: mergeState?.mergeResult?.conflicts || [],
    });
    setSaveState(BUILDER_SAVE_STATES.conflict);
    showToast(
      isBuilderError(error, "builder_client_upgrade_required")
        ? "This Madar editor is out of date. Reload before editing or publishing."
        : getBuilderConflictMessage(error)
    );
  }, [persistProjectNow, showToast, stopAllCloudScheduling]);

  const attemptAutomaticRebase = useCallback(async ({
    conflictError,
    localProject,
    submittedBaseSchema,
    requestGeneration,
    operationId,
    silent,
  }) => {
    stopAllCloudScheduling();
    if (
      requestGeneration !== serverAdoptionGenerationRef.current ||
      operationId < latestAcknowledgedSaveOperationRef.current
    ) return false;
    setSaveState(BUILDER_SAVE_STATES.savingCloud);
    showToast("Changes were made in another session. Madar is merging your edits.");

    try {
      const localSchema = stripAutosaveMetadata(localProject);
      const baseSchema = stripAutosaveMetadata(submittedBaseSchema || baseSchemaRef.current);
      const rebaseResult = await runBuilderAutomaticRebase({
        baseSchema,
        localSchema,
        routedProjectId: routeProjectId,
        fetchServerProject: (projectId) => fetchBuilderProject(projectId, userId),
        normalizeServerSchema: (record) => stripAutosaveMetadata(getDraftProjectFromRecord(record)),
        prepareMergedProject: (mergedSchema) => cleanBuilderProject({
          ...mergedSchema,
          activePageId: localProject.activePageId,
          activeFormId: localProject.activeFormId,
          activeWorkflowId: localProject.activeWorkflowId,
          activeRoleId: localProject.activeRoleId,
        }),
        createRetryPayload: ({ mergedProject, serverRecord, serverRevision }) =>
          createBuilderProjectPayload({
            project: mergedProject,
            builderProjectRecord: { ...serverRecord, draft_revision: serverRevision },
            getBuilderProjectName,
            getBuilderProjectSlug,
          }),
        updateServerProject: (projectId, payload) => updateBuilderProject(projectId, payload, userId),
        validateAcknowledgement: validateBuilderSaveAcknowledgement,
        resolveConflicts: ({ mergeResult }) => resolveBuilderDraftConflictsPreferLocal({
          mergeResult,
          pathPrefix: "siteChrome",
        }),
        isCurrent: () =>
          requestGeneration === serverAdoptionGenerationRef.current &&
          operationId >= latestAcknowledgedSaveOperationRef.current,
      });
      if (
        requestGeneration !== serverAdoptionGenerationRef.current ||
        operationId < latestAcknowledgedSaveOperationRef.current
      ) return false;
      if (rebaseResult.status === "obsolete") return false;
      if (rebaseResult.status === "conflict") {
        enterTerminalConflict(conflictError, {
          baseSchema: rebaseResult.baseSchema,
          localSchema: rebaseResult.localSchema,
          serverSchema: rebaseResult.serverSchema,
          serverRecord: rebaseResult.serverRecord,
          mergeResult: rebaseResult.mergeResult,
        });
        showToast("Some edits conflict with changes from another session.");
        return false;
      }
      const {
        mergedProject,
        savedRecord,
        savedRevision,
      } = rebaseResult;
      const mergedSnapshot = getAutosaveSnapshot(mergedProject);
      validateBuilderSchemaAcknowledgement({
        savedRecord,
        submittedProject: mergedProject,
      });

      // Edits may continue while the latest server record is fetched and the
      // merged retry is saving. Rebase those newer editor changes onto the
      // acknowledged merge instead of replacing them with the submitted copy.
      const latestEditorProject = projectRef.current;
      const latestEditorSchema = stripAutosaveMetadata(latestEditorProject);
      let nextEditorProject = mergedProject;
      if (getAutosaveSnapshot(latestEditorSchema) !== getAutosaveSnapshot(localSchema)) {
        const latestMerge = mergeBuilderDraftSchemas({
          baseSchema: localSchema,
          localSchema: latestEditorSchema,
          serverSchema: stripAutosaveMetadata(mergedProject),
        });
        const latestResolvedSchema = latestMerge.conflicts.length > 0
          ? resolveBuilderDraftConflictsPreferLocal({
              mergeResult: latestMerge,
              pathPrefix: "siteChrome",
            })
          : latestMerge.mergedSchema;
        if (!latestResolvedSchema) {
          enterTerminalConflict(conflictError, {
            baseSchema: localSchema,
            localSchema: latestEditorSchema,
            serverSchema: stripAutosaveMetadata(mergedProject),
            serverRecord: savedRecord,
            mergeResult: latestMerge,
          });
          return false;
        }
        nextEditorProject = cleanBuilderProject({
          ...latestResolvedSchema,
          activePageId: latestEditorProject.activePageId,
          activeFormId: latestEditorProject.activeFormId,
          activeWorkflowId: latestEditorProject.activeWorkflowId,
          activeRoleId: latestEditorProject.activeRoleId,
        });
      }
      const nextEditorSnapshot = getAutosaveSnapshot(nextEditorProject);

      builderProjectRecordRef.current = savedRecord;
      currentDraftRevisionRef.current = savedRevision;
      latestAcknowledgedSaveOperationRef.current = operationId;
      baseSchemaRef.current = stripAutosaveMetadata(savedRecord?.draft_schema || mergedProject);
      backendProjectSnapshotRef.current = mergedSnapshot;
      pendingBackendProjectSnapshotRef.current = "";
      pendingRemoteSaveRef.current = null;
      remoteSaveActiveSnapshotRef.current = mergedSnapshot;
      projectRef.current = nextEditorProject;
      setBuilderProjectRecord(savedRecord);
      setProject(nextEditorProject);
      acknowledgeCloudSave(mergedProject, savedRevision);
      setConflictDetails(null);
      setConflictServerCandidate(null);
      setConflictMergeState(null);
      const hasNewerEditorChanges = nextEditorSnapshot !== mergedSnapshot;
      if (!hasNewerEditorChanges) clearBuilderRecovery(recoveryIdentity);
      setSaveState(hasNewerEditorChanges
        ? BUILDER_SAVE_STATES.dirty
        : BUILDER_SAVE_STATES.savedCloud);
      if (!hasNewerEditorChanges) setLastCloudSavedAt(new Date());
      broadcastCloudSave(savedRecord);
      showToast(hasNewerEditorChanges
        ? "Changes from another session were merged. Saving your latest edit…"
        : "Your edits were merged and saved.");
      return true;
    } catch (error) {
      if (
        requestGeneration !== serverAdoptionGenerationRef.current ||
        operationId < latestAcknowledgedSaveOperationRef.current
      ) return false;
      if (isBuilderTerminalConflictError(error)) {
        // One automatic rebase PUT is the hard boundary. A second 409 pauses.
        enterTerminalConflict(error, error.builderMergeState || null);
      } else {
        setSaveState(BUILDER_SAVE_STATES.saveFailed);
        if (!silent) showToast("Your changes are safe here. Please retry when the connection is available.");
      }
      return false;
    }
  }, [
    acknowledgeCloudSave,
    broadcastCloudSave,
    enterTerminalConflict,
    recoveryIdentity,
    routeProjectId,
    showToast,
    stopAllCloudScheduling,
    userId,
  ]);

  const saveSingleProjectRevision = useCallback(async ({
    nextProject,
    silent,
    repairs = [],
    successMessage = "",
    expectedRevision = null,
    requestGeneration = null,
    operationId = 0,
  }) => {
    if (!canStartBuilderCloudMutation({
      hydrated: hydrationCompleteRef.current,
      conflict: conflictRef.current,
    })) return false;
    const urlErrors = collectBuilderUrlErrors(nextProject);
    if (urlErrors.length > 0) {
      setSaveState(BUILDER_SAVE_STATES.saveFailed);
      if (!silent) showToast(urlErrors[0]);
      return false;
    }

    if (demoMode) {
      persistProject(nextProject, successMessage || "Changes saved for this preview.", { silent });
      return true;
    }
    if (builderProjectLoading) {
      setSaveState(BUILDER_SAVE_STATES.saveFailed);
      if (!silent) showToast("Still loading your site. Try saving again in a moment.");
      return false;
    }

    setSaveState(BUILDER_SAVE_STATES.savingLocal);
    if (silent && repairs.length === 0) {
      persistProjectNow(nextProject);
    } else {
      persistProject(nextProject, "Saving your changes...", { silent });
    }

    const activeRequestGeneration = requestGeneration ?? serverAdoptionGenerationRef.current;
    const isCurrentOperation = () =>
      activeRequestGeneration === serverAdoptionGenerationRef.current &&
      operationId >= latestAcknowledgedSaveOperationRef.current;
    const submittedBaseSchema = baseSchemaRef.current;
    try {
      const currentRecord = {
        ...(builderProjectRecordRef.current || {}),
        draft_revision: expectedRevision ?? currentDraftRevisionRef.current,
      };
      if (!currentRecord?.id || currentRecord.id !== routeProjectId) {
        throw new Error("Explicit builder project is not hydrated");
      }
      const payload = createBuilderProjectPayload({
        project: nextProject,
        builderProjectRecord: currentRecord,
        getBuilderProjectName,
        getBuilderProjectSlug,
      });
      setSaveState(BUILDER_SAVE_STATES.savingCloud);
      const savedRecord = await updateBuilderProject(routeProjectId, payload, userId);
      if (!isCurrentOperation()) return false;
      const savedRevision = validateBuilderSaveAcknowledgement({
        projectId: routeProjectId,
        previousRevision: currentRecord.draft_revision,
        savedRecord,
      });
      validateBuilderSchemaAcknowledgement({
        savedRecord,
        submittedProject: nextProject,
      });

      let websiteSettingsSyncFailed = false;
      if (websiteSettingsPayloadChanged(submittedBaseSchema, nextProject)) {
        const websitePayload = getWebsiteSettingsPayload(nextProject);
        if (websitePayload.standard_path_slug && websitePayload.brand) {
          try {
            const savedWebsite = await updateWebsiteSettings(websitePayload);
            if (savedWebsite) {
              setWebsiteSettings((current) => ({ ...(current || {}), ...savedWebsite }));
            }
          } catch {
            websiteSettingsSyncFailed = true;
          }
        }
      }

      builderProjectRecordRef.current = savedRecord;
      currentDraftRevisionRef.current = savedRevision;
      latestAcknowledgedSaveOperationRef.current = operationId;
      baseSchemaRef.current = stripAutosaveMetadata(savedRecord?.draft_schema || nextProject);
      setBuilderProjectRecord(savedRecord);
      backendProjectSnapshotRef.current = getAutosaveSnapshot(nextProject);
      pendingBackendProjectSnapshotRef.current = "";
      const latestIsDirty = acknowledgeCloudSave(nextProject, savedRevision) ||
        getAutosaveSnapshot(projectRef.current) !== backendProjectSnapshotRef.current;
      setSaveState(getAcknowledgedBuilderSaveState({
        acknowledgedSnapshot: backendProjectSnapshotRef.current,
        currentSnapshot: latestIsDirty
          ? getAutosaveSnapshot(projectRef.current)
          : backendProjectSnapshotRef.current,
      }));
      if (!latestIsDirty) setLastCloudSavedAt(new Date());
      broadcastCloudSave(savedRecord);
      if (!silent) {
        showToast(
          websiteSettingsSyncFailed
            ? "Your builder changes are saved, but Website Settings could not be synchronized."
            : repairs.length > 0
              ? "Duplicate internal IDs were repaired and your changes are saved."
              : successMessage || "Your changes are saved."
        );
      }
      return true;
    } catch (error) {
      if (!isCurrentOperation()) return false;
      if (import.meta.env.DEV) {
        console.error("Could not save builder project.");
      }
      if (isLikelySessionFailure(error)) {
        setSaveState(BUILDER_SAVE_STATES.saveFailed);
        if (!silent) {
          showToast("Please sign in again, then save your changes.");
        }
        return false;
      }

      if (isBuilderTerminalConflictError(error)) {
        return attemptAutomaticRebase({
          conflictError: error,
          localProject: nextProject,
          submittedBaseSchema,
          requestGeneration: activeRequestGeneration,
          operationId,
          silent,
        });
      }

      setSaveState(BUILDER_SAVE_STATES.saveFailed);
      if (!silent) {
        showToast("Your changes are safe here. Please try saving again.");
      }
      return false;
    }
  }, [
    acknowledgeCloudSave,
    attemptAutomaticRebase,
    broadcastCloudSave,
    builderProjectLoading,
    demoMode,
    persistProject,
    persistProjectNow,
    routeProjectId,
    showToast,
    userId,
  ]);

  const saveProject = useCallback(({
    silent = false,
    projectOverride = null,
    successMessage = "",
  } = {}) => {
    if (!canStartBuilderCloudMutation({
      hydrated: hydrationCompleteRef.current,
      conflict: conflictRef.current,
    })) {
      if (!silent && conflictRef.current) {
        showToast("Resolve the draft conflict before saving again.");
      }
      return Promise.resolve(false);
    }
    if (hasProtectedUnreadableDraft) {
      if (!silent) {
        showToast("The stored draft is unreadable and was preserved. Export your current view before resolving it.");
      }
      return Promise.resolve(false);
    }

    const sourceProject = projectOverride || projectRef.current;
    const nextProject = sourceProject;
    const repaired = cleanBuilderProjectWithRepairs(nextProject);
    const request = createBuilderSaveEntry({
      project: repaired.project,
      silent,
      repairs: repaired.repairs,
      snapshot: getAutosaveSnapshot(repaired.project),
      successMessage,
      reason: silent ? "autosave" : "manual",
      force: !silent,
    });

    if (!silent) setActiveTopbarAction("save");

    if (!saveCoordinatorRef.current) {
      saveCoordinatorRef.current = createBuilderSaveCoordinator({
        getProjectId: () => builderProjectRecordRef.current?.id || "",
        getGeneration: () => serverAdoptionGenerationRef.current,
        getRevision: () => currentDraftRevisionRef.current,
        getAcknowledgedSnapshot: () => backendProjectSnapshotRef.current,
        getLatestEntry: () => {
          const latestRepair = cleanBuilderProjectWithRepairs(projectRef.current);
          return createBuilderSaveEntry({
            project: latestRepair.project,
            repairs: latestRepair.repairs,
            silent: true,
            snapshot: getAutosaveSnapshot(latestRepair.project),
            reason: "latest",
          });
        },
        dispatch: async (entry, context) => {
          remoteSaveActiveSnapshotRef.current = entry.snapshot;
          const saved = await saveSingleProjectRevision({
            nextProject: entry.project,
            silent: entry.silent,
            repairs: entry.repairs,
            expectedRevision: context.expectedRevision,
            requestGeneration: context.generation,
            operationId: context.operationId,
            successMessage: entry.successMessage,
          });
          if (context.generation !== serverAdoptionGenerationRef.current) {
            return { status: "obsolete" };
          }
          if (saved) return { status: "saved" };
          return { status: conflictRef.current ? "conflict" : "failed" };
        },
      });
    }

    saveCoordinatorRef.current.resume();
    const operation = saveCoordinatorRef.current.requestSave(request);
    remoteSaveInFlightRef.current = true;
    remoteSavePromiseRef.current = operation;
    setIsSavingProject(true);
    operation.finally(() => {
      if (remoteSavePromiseRef.current !== operation) return;
      remoteSaveInFlightRef.current = false;
      remoteSaveActiveSnapshotRef.current = "";
      remoteSavePromiseRef.current = null;
      setIsSavingProject(false);
    });
    return operation.then((result) => result?.status === "saved");
  }, [hasProtectedUnreadableDraft, saveSingleProjectRevision, showToast]);

  const resolveOverlappingConflicts = useCallback(async (resolutions) => {
    const mergeState = conflictMergeState;
    if (!mergeState?.serverRecord || !mergeState?.mergeResult?.conflicts?.length) return false;
    if (mergeState.mergeResult.conflicts.some((_, index) => !resolutions?.[index])) {
      showToast("Choose which version to keep for every conflicting edit.");
      return false;
    }

    try {
      let activeResolutions = resolutions;
      const latestRecord = await fetchBuilderProject(routeProjectId, userId);
      if (!latestRecord?.id || latestRecord.id !== routeProjectId) {
        throw new Error("The routed project could not be verified");
      }
      let currentMergeState = mergeState;
      if (Number(latestRecord.draft_revision) !== Number(mergeState.serverRecord.draft_revision)) {
        const latestServerSchema = stripAutosaveMetadata(getDraftProjectFromRecord(latestRecord));
        const latestMergeResult = mergeBuilderDraftSchemas({
          baseSchema: mergeState.baseSchema,
          localSchema: mergeState.localSchema,
          serverSchema: latestServerSchema,
        });
        currentMergeState = {
          ...mergeState,
          serverSchema: latestServerSchema,
          serverRecord: latestRecord,
          mergeResult: latestMergeResult,
        };
        if (latestMergeResult.conflicts.length > 0) {
          const isSiteChromeOnly = latestMergeResult.conflicts.every(
            ({ path }) => path === "siteChrome" || String(path || "").startsWith("siteChrome.")
          );
          if (activeTab === "chrome" && isSiteChromeOnly) {
            activeResolutions = Object.fromEntries(
              latestMergeResult.conflicts.map((_, index) => [index, "local"])
            );
          } else {
            setConflictMergeState(currentMergeState);
            setConflictServerCandidate(latestRecord);
            setConflictDetails((current) => ({
              ...(current || {}),
              detectedAt: Date.now(),
              serverRevision: Number(latestRecord.draft_revision),
              serverUpdatedAt: latestRecord.updated_at || null,
              conflicts: latestMergeResult.conflicts,
            }));
            showToast("The server changed again. Review the updated conflicts before saving.");
            return false;
          }
        }
      }

      const resolvedSchema = resolveBuilderDraftConflicts({
        mergedSchema: currentMergeState.mergeResult.mergedSchema,
        conflicts: currentMergeState.mergeResult.conflicts,
        resolutions: activeResolutions,
      });
      const resolvedProject = cleanBuilderProject({
        ...resolvedSchema,
        activePageId: projectRef.current.activePageId,
        activeFormId: projectRef.current.activeFormId,
        activeWorkflowId: projectRef.current.activeWorkflowId,
        activeRoleId: projectRef.current.activeRoleId,
      });
      const serverAdoption = prepareBuilderServerAdoption({
        serverRecord: currentMergeState.serverRecord,
        routedProjectId: routeProjectId,
        normalizeProject: (record) => getDraftProjectFromRecord(record),
        createSnapshot: getAutosaveSnapshot,
      });
      saveCoordinatorRef.current?.invalidate();
      adoptBuilderServerRuntime({
        adoption: serverAdoption,
        refs: {
          builderProjectRecord: builderProjectRecordRef,
          backendDraftRevision: currentDraftRevisionRef,
          requestGeneration: serverAdoptionGenerationRef,
          project: projectRef,
          baseSchema: baseSchemaRef,
          acknowledgedSnapshot: backendProjectSnapshotRef,
          pendingSnapshot: pendingBackendProjectSnapshotRef,
          pendingRequest: pendingRemoteSaveRef,
          activeSnapshot: remoteSaveActiveSnapshotRef,
          savePromise: remoteSavePromiseRef,
          saveInFlight: remoteSaveInFlightRef,
          pendingExternalDraft: pendingExternalDraftRef,
          hydrationComplete: hydrationCompleteRef,
          conflict: conflictRef,
        },
        stopScheduling: stopAllCloudScheduling,
      });
      baseSchemaRef.current = currentMergeState.serverSchema;
      backendProjectSnapshotRef.current = getAutosaveSnapshot(currentMergeState.serverSchema);
      projectRef.current = resolvedProject;
      setBuilderProjectRecord(currentMergeState.serverRecord);
      setProject(resolvedProject);
      setConflictMergeState(null);
      setConflictDetails(null);
      setConflictServerCandidate(null);
      setSaveState(BUILDER_SAVE_STATES.dirty);

      const saved = await saveProject({ silent: true, projectOverride: resolvedProject });
      if (saved) showToast("Your conflict choices were saved.");
      return saved;
    } catch (error) {
      if (isBuilderTerminalConflictError(error)) enterTerminalConflict(error, mergeState);
      else showToast("The conflict resolution could not be saved. Your local version remains protected.");
      return false;
    }
  }, [
    activeTab,
    conflictMergeState,
    enterTerminalConflict,
    routeProjectId,
    saveProject,
    showToast,
    stopAllCloudScheduling,
    userId,
  ]);

  useEffect(() => {
    const conflicts = conflictMergeState?.mergeResult?.conflicts || [];
    const isSiteChromeOnly = conflicts.length > 0 && conflicts.every(
      ({ path }) => path === "siteChrome" || String(path || "").startsWith("siteChrome.")
    );
    if (
      activeTab !== "chrome" ||
      saveState !== BUILDER_SAVE_STATES.conflict ||
      !isSiteChromeOnly ||
      siteChromeConflictResolutionRef.current
    ) return;

    siteChromeConflictResolutionRef.current = true;
    const resolutions = Object.fromEntries(conflicts.map((_, index) => [index, "local"]));
    showToast("Saving your latest Header & Footer changes to Madar.");
    resolveOverlappingConflicts(resolutions).finally(() => {
      siteChromeConflictResolutionRef.current = false;
    });
  }, [activeTab, conflictMergeState, resolveOverlappingConflicts, saveState, showToast]);

  useEffect(() => {
    if (demoMode || builderProjectLoading || !canStartBuilderCloudMutation({ hydrated: hydrationCompleteRef.current, conflict: conflictRef.current })) return;
    if (!project) return;

    window.clearTimeout(backendAutosaveTimerRef.current);
    const attemptLatestSave = () => {
      if (!canStartBuilderCloudMutation({ hydrated: hydrationCompleteRef.current, conflict: conflictRef.current })) return;
      const latestProject = projectRef.current;
      const latestSnapshot = getAutosaveSnapshot(latestProject);
      if (
        !latestSnapshot ||
        latestSnapshot === backendProjectSnapshotRef.current ||
        latestSnapshot === pendingBackendProjectSnapshotRef.current
      ) return;
      if (shouldDeferBuilderCloudSave({
        activeTab,
        dragActive: Boolean(dragStateRef.current),
        textEditing: isBuilderTextEditingTarget(document.activeElement),
      })) {
        backendAutosaveTimerRef.current = window.setTimeout(attemptLatestSave, 500);
        return;
      }
      pendingBackendProjectSnapshotRef.current = latestSnapshot;
      saveProject({ silent: true, projectOverride: latestProject }).finally(() => {
        pendingBackendProjectSnapshotRef.current = "";
      });
    };
    backendAutosaveTimerRef.current = window.setTimeout(attemptLatestSave, 2000);

    return () => {
      window.clearTimeout(backendAutosaveTimerRef.current);
    };
  }, [activeTab, builderProjectLoading, demoMode, project, saveProject]);

  const fetchConflictServerCandidate = useCallback(async () => {
    try {
      if (!routeProjectId) throw new Error("An explicit project URL is required");
      const fullRecord = await fetchBuilderProject(routeProjectId, userId);
      if (!fullRecord || fullRecord.id !== routeProjectId) {
        throw new Error("The routed project could not be verified");
      }
      setConflictServerCandidate(fullRecord);
      setConflictDetails((current) => ({
        ...(current || {}),
        serverRevision: Number(fullRecord.draft_revision) || 0,
        serverUpdatedAt: fullRecord.updated_at || null,
      }));
      return fullRecord;
    } catch (error) {
      if (import.meta.env.DEV) console.warn("Could not inspect latest server project.", error);
      showToast("The latest server metadata could not be loaded. Your local copy remains protected.");
      return null;
    }
  }, [routeProjectId, showToast, userId]);

  const adoptServerProject = useCallback(async (candidate = null, {
    preserveSelection = false,
    successMessage = "Latest server version loaded. Saving will resume after your next edit.",
  } = {}) => {
    if (demoMode) return;
    try {
      const serverRecord = candidate?.id === routeProjectId
        ? candidate
        : await fetchConflictServerCandidate();
      if (!serverRecord) throw new Error("The server project is unavailable");
      const adoption = prepareBuilderServerAdoption({
        serverRecord,
        routedProjectId: routeProjectId,
        normalizeProject: (record) => {
          const loaded = getDraftProjectFromRecord(record);
          return isDefaultShowcaseProject(loaded) ? createCleanBlankProject() : loaded;
        },
        createSnapshot: getAutosaveSnapshot,
      });

      saveCoordinatorRef.current?.invalidate();
      adoptBuilderServerRuntime({
        adoption,
        refs: {
          builderProjectRecord: builderProjectRecordRef,
          backendDraftRevision: currentDraftRevisionRef,
          requestGeneration: serverAdoptionGenerationRef,
          project: projectRef,
          baseSchema: baseSchemaRef,
          acknowledgedSnapshot: backendProjectSnapshotRef,
          pendingSnapshot: pendingBackendProjectSnapshotRef,
          pendingRequest: pendingRemoteSaveRef,
          activeSnapshot: remoteSaveActiveSnapshotRef,
          savePromise: remoteSavePromiseRef,
          saveInFlight: remoteSaveInFlightRef,
          pendingExternalDraft: pendingExternalDraftRef,
          hydrationComplete: hydrationCompleteRef,
          conflict: conflictRef,
        },
        stopScheduling: stopAllCloudScheduling,
      });
      adoptCloudRevision(
        serializePersistableProject(adoption.persistableProject),
        Date.parse(serverRecord.updated_at) || Date.now(),
        adoption.revision
      );
      clearBuilderRecovery(recoveryIdentity);
      setBuilderProjectRecord(serverRecord);
      setProject(adoption.project);
      if (!preserveSelection) {
        setSelected({ type: "page", id: adoption.project.activePageId });
      }
      setConflictDetails(null);
      setConflictServerCandidate(null);
      setConflictMergeState(null);
      setIsSavingProject(false);
      setSaveState(BUILDER_SAVE_STATES.savedCloud);
      setLastCloudSavedAt(
        serverRecord.updated_at ? new Date(serverRecord.updated_at) : new Date()
      );
      if (successMessage) showToast(successMessage);
      return true;
    } catch (error) {
      if (import.meta.env.DEV) console.warn("Could not adopt backend builder project.", error);
      conflictRef.current = true;
      hydrationCompleteRef.current = true;
      setSaveState(BUILDER_SAVE_STATES.conflict);
      showToast("The latest server version could not be loaded. Your local copy remains protected.");
      return false;
    }
  }, [
    adoptCloudRevision,
    demoMode,
    fetchConflictServerCandidate,
    recoveryIdentity,
    routeProjectId,
    showToast,
    stopAllCloudScheduling,
  ]);

  useEffect(() => {
    if (demoMode || typeof BroadcastChannel === "undefined") return undefined;
    const channel = new BroadcastChannel(BUILDER_CLOUD_SYNC_CHANNEL);
    cloudSyncChannelRef.current = channel;
    let adopting = false;

    const handleCloudSave = async ({ data } = {}) => {
      if (
        adopting ||
        !isNewerBuilderCloudSaveMessage(data, {
          currentRevision: currentDraftRevisionRef.current,
          projectId: routeProjectId,
          sourceId: draftSourceId,
          tenantId: recoveryIdentity.tenantId,
        })
      ) return;

      const localIsBusy =
        remoteSaveInFlightRef.current ||
        Boolean(dragStateRef.current) ||
        isBuilderTextEditingTarget(document.activeElement) ||
        getAutosaveSnapshot(projectRef.current) !== backendProjectSnapshotRef.current;
      if (localIsBusy) {
        showToast("A newer saved version is available from another tab. Finish your current edit before reloading it.");
        return;
      }

      adopting = true;
      try {
        await adoptServerProject(null, {
          preserveSelection: true,
          successMessage: "Updated from another open Madar tab.",
        });
      } finally {
        adopting = false;
      }
    };

    channel.addEventListener("message", handleCloudSave);
    return () => {
      channel.removeEventListener("message", handleCloudSave);
      channel.close();
      if (cloudSyncChannelRef.current === channel) cloudSyncChannelRef.current = null;
    };
  }, [
    adoptServerProject,
    demoMode,
    draftSourceId,
    recoveryIdentity.tenantId,
    routeProjectId,
    showToast,
  ]);

  const reloadServerProject = async () => {
    if (conflictRef.current) {
      setConflictDetails((current) => current || {
        localBaseRevision: currentDraftRevisionRef.current,
      });
      return false;
    }
    if (getAutosaveSnapshot(projectRef.current) !== backendProjectSnapshotRef.current) {
      showToast("Unsaved local changes are present. Save or resolve them before loading the server version.");
      return false;
    }
    return adoptServerProject();
  };

  const publicSiteSubdomain = sanitizeSubdomain(
    websiteSettings?.standard_path_slug ||
      websiteSettings?.subdomain ||
      project?.publish?.subdomain ||
      ""
  );
  const canonicalLiveSitePath = publicSiteSubdomain
    ? resolveLiveSitePath(publicSiteSubdomain)
    : liveSitePath;
  const publicationState = useMemo(
    () => getBuilderPublicationState(builderProjectRecord),
    [builderProjectRecord]
  );

  const publishProject = async (skipOverlapCheck = false) => {
    return runBuilderPublishSingleFlight(publishPromiseRef, async () => {
      setActiveTopbarAction("publish");
      setToast("");

    if (hasProtectedUnreadableDraft) {
      showToast("The stored draft is unreadable and was preserved. Publishing is paused for safety.");
      return false;
    }

    const hadPendingSave = Boolean(remoteSavePromiseRef.current) ||
      getAutosaveSnapshot(projectRef.current) !== backendProjectSnapshotRef.current;
    if (hadPendingSave) {
      showToast("Saving your latest changes before publishing…");
    }

    const prepared = await prepareBuilderProjectForPublish({
      getState: () => ({
        hydrated: hydrationCompleteRef.current,
        routedProjectId: routeProjectId,
        loadedProjectId: builderProjectRecordRef.current?.id,
        draftRevision: currentDraftRevisionRef.current,
        currentSnapshot: getAutosaveSnapshot(projectRef.current),
        acknowledgedSnapshot: backendProjectSnapshotRef.current,
        acknowledgedSchema: baseSchemaRef.current,
        conflict: conflictRef.current,
        operationInFlight: Boolean(remoteSavePromiseRef.current),
      }),
      getActiveOperation: () => remoteSavePromiseRef.current,
      flushSave: () => saveProject({ silent: true, projectOverride: projectRef.current }),
    });
    if (!prepared.ready) {
      const messages = {
        conflict: "Resolve the draft conflict before publishing.",
        save_failed: "Could not save the latest draft. Retry before publishing.",
        saving: "Saving latest changes before publishing.",
        unsaved_changes: "The latest changes are still unsaved. Retry before publishing.",
        loading: "The exact cloud project is still loading.",
      };
      showToast(messages[prepared.reason] || "This draft is not ready to publish.");
      return false;
    }

    if (!publicSiteSubdomain) {
      setActiveTab("publish");
      showToast("Choose your website address before going live.");
      return false;
    }

    const publishCandidate = projectRef.current;
    const pageRoutingIssues = collectPublicPageRoutingIssues(publishCandidate);
    if (pageRoutingIssues.length > 0) {
      const issue = pageRoutingIssues[0];
      if (issue.page_id) {
        updateProject((prev) => ({ ...prev, activePageId: issue.page_id }));
        setSelected({ type: "page", id: issue.page_id });
      }
      setActiveTab("design");
      setDesignPanel("Pages");
      showToast("Review the homepage and page links before going live.");
      return false;
    }

    const projectIdIssues = collectProjectIdIssues(publishCandidate);
    if (projectIdIssues.length > 0) {
      showToast(getProjectIdIssueMessage(projectIdIssues[0]));
      return false;
    }

    const formConnectionIssues = collectFormConnectionIssues(publishCandidate);
    if (formConnectionIssues.length > 0) {
      const issue = formConnectionIssues[0];
      const target = getFormConnectionFocusTarget(issue);
      if (publishCandidate.activePageId !== target.pageId) {
        updateProject((prev) => ({ ...prev, activePageId: target.pageId }));
      }
      setSelected(target.selection);
      setActiveTab("design");
      setDesignPanel("Pages");
      showToast(getFormConnectionIssueMessage(issue));
      return false;
    }

    const savedAt = new Date().toISOString();
    const draftForPublish = {
      ...publishCandidate,
      publish: {
        ...publishCandidate.publish,
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
      return false;
    }
    const urlErrors = collectBuilderUrlErrors(publishedProject);

    if (urlErrors.length > 0) {
      showToast(urlErrors[0]);
      return false;
    }

    const overlapWarnings = isSmartResponsiveProject(publishedProject)
      ? []
      : getProjectOverlapWarnings(publishedProject);

    if (isSmartResponsiveProject(publishedProject)) {
      const blockingDiagnostics = getSmartProjectLayoutDiagnostics(publishedProject).filter((diagnostic) =>
        ["unresolved_manual_collision", "manual_out_of_bounds", "collision_iteration_limit"].includes(diagnostic.code)
      );
      if (blockingDiagnostics.length > 0) {
        showToast("Smart responsive layout has unresolved manual collisions or out-of-bounds components. Reset or reposition them before publishing.");
        return false;
      }
    }

    if (!skipOverlapCheck && overlapWarnings.length > 0) {
      setPublishOverlapWarnings(overlapWarnings);
      return false;
    }

    setPublishOverlapWarnings([]);

    if (demoMode) {
      persistProject(publishedProject, "Your site is live for this preview.");
      return true;
    }

    if (builderProjectLoading) {
      showToast("Your site is still getting ready. Please try Go Live again in a moment.");
      return false;
    }

    try {
      const savedRecord = builderProjectRecordRef.current;
      const latestPublicationState = getBuilderPublicationState(savedRecord);

      if (
        latestPublicationState.publishedHasMorePages &&
        !window.confirm(
          "The saved draft has fewer pages than the currently published site. Continue publishing this smaller draft?"
        )
      ) return false;

      showToast("Publishing site…");
      const publishResponse = await publishBuilderProject(
        prepared.projectId,
        prepared.draftRevision
      );
      const publishedRecord = publishResponse?.project || savedRecord;
      if (publishedRecord?.id && publishedRecord.id !== prepared.projectId) {
        throw new Error("Publish acknowledgement did not match the routed project");
      }
      const publishedSite = publishResponse?.site || {};
      if (publishedSite?.published_project_id) {
        setWebsiteSettings((current) => ({
          ...(current || {}),
          published_project_id: publishedSite.published_project_id,
        }));
      }
      const resolvedPublicSubdomain = sanitizeSubdomain(
        publishedSite?.standard_path_slug ||
          websiteSettings?.standard_path_slug ||
          publishedSite?.subdomain ||
          websiteSettings?.subdomain ||
          publishCandidate?.publish?.subdomain ||
          ""
      );
      const resolvedLiveSitePath = resolvedPublicSubdomain
        ? resolveLiveSitePath(resolvedPublicSubdomain)
        : "";

      // The server publish has already committed at this point. Reflect that
      // durable state even if the optional public-link metadata is incomplete.
      setBuilderProjectRecord(publishedRecord);
      builderProjectRecordRef.current = publishedRecord;
      pendingBackendProjectSnapshotRef.current = "";

      if (import.meta.env.DEV) {
        console.debug("Builder publish completed.");
      }

      if (!resolvedLiveSitePath) {
        showToast("Your site is live, but its public link could not be loaded. Refresh the Publish page.");
        return false;
      }

      setLiveSitePath(resolvedLiveSitePath);
      showToast(
        `Your site is live${publishedRecord?.published_version ? ` (version ${publishedRecord.published_version})` : ""}. Go to the Publish page to open your website.`
      );
      return true;
    } catch (error) {
      console.error("Could not publish builder project:", error);

      if (isLikelySessionFailure(error)) {
        showToast("Please sign in again, then choose Go Live.");
        return false;
      }

      if (isBuilderTerminalConflictError(error)) {
        enterTerminalConflict(error);
        return false;
      }

      if (isBuilderError(error, "entitlement_pending")) {
        showToast("Your publishing access is still pending. No changes were lost.");
        return false;
      }

      if (
        isBuilderError(error, "entitlement_inactive") ||
        isBuilderError(error, "payment_required")
      ) {
        showToast("Publishing is not active for this workspace. Review your plan; your edits are still saved locally.");
        return false;
      }

      if (isBuilderError(error, "publish_validation_failed")) {
        if (String(error.context?.issue_type || "").includes("_id")) {
          showToast(getProjectIdIssueMessage(error.context));
          return false;
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
        return false;
      }

      showToast("We couldn't put your site live. Please try again.");
      return false;
    }
    });
  };

  const unpublishProject = async () => {
    if (conflictRef.current) {
      showToast("Resolve the draft conflict before changing the published site.");
      return;
    }
    if (!builderProjectRecord?.id || project.status !== "published") return;
    if (!window.confirm("Take this website offline? The current published content will be preserved for a later republish.")) {
      return;
    }

    setIsUnpublishingProject(true);

    try {
      const response = await unpublishBuilderProject(
        builderProjectRecord.id,
        currentDraftRevisionRef.current
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
      } else if (isBuilderTerminalConflictError(error)) {
        enterTerminalConflict(error);
      } else if (isBuilderError(error, "project_not_published")) {
        showToast("This website is already offline.");
      } else {
        showToast("We could not take the website offline. It remains published.");
      }
    } finally {
      setIsUnpublishingProject(false);
    }
  };

  const makeCurrentProjectLive = async () => {
    const projectId = builderProjectRecordRef.current?.id;
    if (!projectId || project.status !== "published" || isBindingPublicProject) return;
    setIsBindingPublicProject(true);
    try {
      const result = await updateBuilderSiteBinding(projectId);
      setWebsiteSettings((current) => ({
        ...(current || {}),
        published_project_id: result?.binding?.project_id || projectId,
      }));
      showToast("This project is now live on your public website.");
    } catch (error) {
      showToast(error?.message || "The live project could not be changed.");
    } finally {
      setIsBindingPublicProject(false);
    }
  };

  const exportProject = () => exportBuilderProjectJson({ project, showToast });

  const applyStarter = (starterId) => {
    rememberStarterChoice();

    if (starterId === "blankPage") {
      const canvasSection = createBlankCanvasSection();
      const page = createPage(createNextGeneratedPageName(project.pages), [canvasSection], {
        canvasLayoutVersion: 1,
      });

      updateProject((prev) => ({
        ...prev,
        pages: [...prev.pages, page],
        activePageId: page.id,
      }));
      setSelected({ type: "page", id: page.id });
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
      canvasScale: 1,
    }), [activePage, findElementLocation, viewport]);

  const getRenderedDirectElementPosition = (element) => {
    const previewPosition =
      dragState?.previewPositions?.[element.id] ||
      (dragState?.elementId === element.id ? dragState.previewPosition : null);
    if (previewPosition) return previewPosition;
    return smartResponsiveEnabled ? null : getArtboardElementPosition(element, viewport);
  };


  const {
    handleSelectedElementImageUpload,
    handleSelectedElementVideoUpload,
    handleSelectedElementDocumentUpload,
    handleSiteLogoUpload,
    handleLoadingImageUpload,
    handleCarouselSlideImageUpload,
    handlePhotoProofingImagesUpload,
    uploadPhotoProofingFiles,
  } = useMemo(
    // eslint-disable-next-line react-hooks/refs
    () => createUploadHandlers({
      selectedElement,
      carouselElementTypes,
      defaultSiteChrome,
      builderAssetMimeTypes,
      builderAssetMaxBytes,
      builderVideoMimeTypes,
      builderVideoMaxBytes,
      builderDocumentMimeTypes,
      builderDocumentMaxBytes,
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
      setViewport("desktop");
      setPreview(false);
      showToast("Preview closed.");
      return;
    }

    setPreviewOverlapWarnings([]);
    setActiveTab("design");
    setPreview(true);
    showToast("Previewing the current builder draft.");
  };

  const startDrag = useCallback((event, element, interaction = "move", forceInteraction = false) => {
    if (preview || element.mode !== "direct") return;

    const additiveSelection = event.shiftKey || event.ctrlKey || event.metaKey;
    if (interaction === "move" && additiveSelection) {
      event.stopPropagation();
      event.preventDefault();
      return;
    }

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

    const elementFrame = event.currentTarget.closest?.(".direct-element-frame");
    const parentGeometry = getImmediateParentCanvasGeometry(elementFrame, {
      coordinateScale: 1,
    });
    const immediateParent = parentGeometry?.parent;
    const pointer = immediateParent
      ? clientPointToCanvasLocal(
          immediateParent,
          event.clientX,
          event.clientY,
          { coordinateScale: 1 }
        )
      : null;
    if (!immediateParent || !pointer) return;

    const sourceSectionId = immediateParent.dataset?.sectionId || "";
    const sourceSection = activePage?.sections.find((section) => section.id === sourceSectionId);
    const sourceElements = sourceSection?.freeElements || [];
    const selectedIdsInSection = effectiveSelectedElementIds.filter((elementId) =>
      sourceElements.some((candidate) => candidate.id === elementId)
    );
    const groupElementIds = interaction === "move" && selectedIdsInSection.includes(element.id)
      ? selectedIdsInSection
      : [element.id];
    const groupElements = groupElementIds
      .map((elementId) => sourceElements.find((candidate) => candidate.id === elementId))
      .filter(Boolean);
    const getRenderedFramePosition = (candidate) => {
      const frame = findBuilderDataElement(immediateParent, "data-builder-element-id", candidate.id);
      if (!frame) return null;
      const position = {
        x: Number(frame.dataset.logicalX),
        y: Number(frame.dataset.logicalY),
        width: Number(frame.dataset.logicalWidth),
        height: Number(frame.dataset.logicalHeight),
      };
      return Object.values(position).every(Number.isFinite) ? position : null;
    };
    const groupStartPositions = Object.fromEntries(groupElements.map((candidate) => {
      const minimumSize = getDirectElementMinimumSize(candidate);
      const position = clampElementToBounds(
        getRenderedFramePosition(candidate) || candidate.position?.[viewport] || createPosition()[viewport],
        pointer.bounds,
        {
          minWidth: minimumSize.width,
          minHeight: minimumSize.height,
          allowBottomOverflow: true,
        }
      );
      return [candidate.id, position];
    }));

    const minimumSize = getDirectElementMinimumSize(element);
    let current = groupStartPositions[element.id] || clampElementToBounds(
      getRenderedFramePosition(element) || element.position?.[viewport] || createPosition()[viewport],
      pointer.bounds,
      {
        minWidth: minimumSize.width,
        minHeight: minimumSize.height,
        allowBottomOverflow: true,
      }
    );
    if (
      interaction === "resize" &&
      element.type === "heading" &&
      element.directWidthMode !== "fixed"
    ) {
      current = {
        ...current,
        width: Math.max(minimumSize.width, pointer.bounds.width - current.x),
      };
    }

    if (!effectiveSelectedElementIds.includes(element.id)) {
      setSelectedElementIds([element.id]);
    }
    setSelected({ type: "element", id: element.id });
    setDragState({
      elementId: element.id,
      groupElementIds,
      groupStartPositions,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: current.x || 0,
      startY: current.y || 0,
      startWidth: current.width || 240,
      startHeight: current.height || 80,
      startPointerLocalX: pointer.x,
      startPointerLocalY: pointer.y,
      parentSectionId: sourceSectionId,
      pointerId: event.pointerId,
      previewPosition: { ...current },
      previewPositions: groupStartPositions,
      previewSectionHeight: 0,
      interaction,
    });
  }, [activePage, preview, effectiveSelectedElementIds, viewport]);

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

  const shouldIgnoreInlineTextBlur = useCallback(
    () => inlineToolbarInteractionRef.current,
    []
  );
  const clearCanvasTextSelectionHighlight = useCallback(() => {
    globalThis.CSS?.highlights?.delete?.("builder-text-selection");
  }, []);
  const preserveCanvasTextSelectionHighlight = useCallback((range) => {
    const highlights = globalThis.CSS?.highlights;
    const HighlightConstructor = globalThis.Highlight;
    if (!range || !highlights || typeof HighlightConstructor !== "function") return;

    try {
      const documentRef = range.startContainer?.ownerDocument || globalThis.document;
      if (documentRef?.head && !documentRef.getElementById("builder-text-selection-style")) {
        const style = documentRef.createElement("style");
        style.id = "builder-text-selection-style";
        style.textContent =
          "::highlight(builder-text-selection){color:inherit;background:rgba(133,44,33,.24)}";
        documentRef.head.append(style);
      }
      highlights.set("builder-text-selection", new HighlightConstructor(range.cloneRange()));
    } catch {
      // Native selection remains the fallback on browsers without CSS Highlights.
    }
  }, []);
  const positionInlineToolbarNear = useCallback((target, preferredRect = null) => {
    if (!target || typeof window === "undefined") return;

    const targetRect = target.getBoundingClientRect();
    const sourceRect = preferredRect
      && Number.isFinite(preferredRect.top)
      && (preferredRect.width > 0 || preferredRect.height > 0)
        ? preferredRect
        : targetRect;
    const canvasRect = canvasShellRef.current?.getBoundingClientRect();
    const margin = 12;
    const horizontalBounds = {
      left: Math.max(margin, (canvasRect?.left || 0) + margin),
      right: Math.min(
        window.innerWidth - margin,
        (canvasRect?.right || window.innerWidth) - margin
      ),
    };
    const anchorRect = {
      left: sourceRect.left,
      top: sourceRect.top,
      right: sourceRect.right,
      bottom: sourceRect.bottom,
      width: sourceRect.width,
      height: sourceRect.height,
    };

    setInlineToolbarPosition({
      anchorRect,
      horizontalBounds,
      left: anchorRect.left,
      top: anchorRect.bottom + 10,
      maxWidth: Math.max(1, horizontalBounds.right - horizontalBounds.left),
      placement: "below",
    });
  }, []);

  useLayoutEffect(() => {
    const toolbar = inlineToolbarRef.current;
    if (!toolbar || !inlineToolbarPosition?.anchorRect) return;

    const toolbarRect = toolbar.getBoundingClientRect();
    const placement = getFloatingToolbarPlacement({
      anchorRect: inlineToolbarPosition.anchorRect,
      toolbarRect,
      horizontalBounds: inlineToolbarPosition.horizontalBounds,
      viewportHeight: window.innerHeight,
    });

    setInlineToolbarPosition((current) => {
      if (
        !current ||
        (Math.abs(current.left - placement.left) < 0.5 &&
          Math.abs(current.top - placement.top) < 0.5 &&
          current.placement === placement.placement)
      ) return current;

      return { ...current, ...placement };
    });
  }, [
    inlineToolbarPosition?.anchorRect,
    inlineToolbarPosition?.horizontalBounds,
    inlineToolbarPosition?.maxWidth,
  ]);
  const captureCanvasTextSelection = useCallback((event, field, itemIndex = null, elementId = selectedElement?.id, options = {}) => {
    const range = getCanvasTextSelectionRange(event);

    if (!range) return;

    const browserSelection = window.getSelection();
    const browserRangeForBlocks = browserSelection?.rangeCount
      ? browserSelection.getRangeAt(0)
      : null;
    const textBlocks = [...event.currentTarget.children].filter((node) =>
      node.hasAttribute("data-builder-text-block")
    );
    const getBlockIndex = (node) => {
      const elementNode = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
      const block = elementNode?.closest?.("[data-builder-text-block]");
      return block ? textBlocks.indexOf(block) : -1;
    };
    const startBlockIndex = getBlockIndex(browserRangeForBlocks?.startContainer);
    const endBlockIndex = getBlockIndex(browserRangeForBlocks?.endContainer);
    const firstBlockIndex = startBlockIndex >= 0 ? startBlockIndex : 0;
    const lastBlockIndex = endBlockIndex >= firstBlockIndex ? endBlockIndex : firstBlockIndex;
    const blockIndexes = textBlocks.length
      ? Array.from({ length: lastBlockIndex - firstBlockIndex + 1 }, (_, index) => firstBlockIndex + index)
      : [];
    const blockFormat = textBlocks[firstBlockIndex]?.dataset.builderTextBlock || null;
    const nextTextSelection = {
      elementId,
      field,
      itemIndex,
      start: range.start,
      end: range.end,
      blockIndexes,
      blockFormat,
    };
    textSelectionRef.current = nextTextSelection;
    if (options.silent) return;

    const browserRange = !range.collapsed && browserSelection?.rangeCount
      ? browserSelection.getRangeAt(0)
      : null;
    const selectedRangeRect = browserRange
      ? browserRange.getBoundingClientRect?.()
      : null;
    positionInlineToolbarNear(event.currentTarget, selectedRangeRect);
    setInlineFontSizeDraft(null);

    if (range.collapsed) {
      clearCanvasTextSelectionHighlight();
      setTextSelection(nextTextSelection);
      return;
    }

    preserveCanvasTextSelectionHighlight(browserRange);

    setTextSelection(nextTextSelection);
  }, [
    clearCanvasTextSelectionHighlight,
    positionInlineToolbarNear,
    preserveCanvasTextSelectionHighlight,
    selectedElement?.id,
  ]);

  useEffect(() => clearCanvasTextSelectionHighlight,
    [clearCanvasTextSelectionHighlight, selectedElement?.id]
  );

  useEffect(() => {
    textSelectionRef.current = textSelection;
  }, [textSelection]);

  useLayoutEffect(() => {
    if (
      !selectedElement?.id ||
      textSelection?.elementId !== selectedElement.id ||
      Number(textSelection.start) === Number(textSelection.end)
    ) return;

    const frame = findBuilderDataElement(
      canvasShellRef.current,
      "data-builder-element-id",
      selectedElement.id
    );
    const editable = frame?.querySelector('[contenteditable="true"]');
    const range = createDomTextRange(editable, textSelection.start, textSelection.end);
    preserveCanvasTextSelectionHighlight(range);
  }, [preserveCanvasTextSelectionHighlight, selectedElement, textSelection]);

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

    if (start === end && textSelection.blockIndexes?.length && textSelection.field === "content") {
      const activeLineIndex = textSelection.blockIndexes[0];
      const lines = String(targetText).split("\n");
      const lineStart = lines.slice(0, activeLineIndex).reduce((total, line) => total + line.length + 1, 0);
      return {
        field: "content",
        itemIndex: null,
        start: lineStart,
        end: lineStart + (lines[activeLineIndex]?.length || 0),
      };
    }

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

  const hasExplicitSelectedTextRange = () =>
    textSelection?.elementId === selectedElement?.id &&
    Number(textSelection.start) !== Number(textSelection.end);
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

  const applyTextBackgroundColor = (backgroundColor) => {
    const selectedRange = hasExplicitSelectedTextRange()
      ? getSelectedTextRange()
      : null;

    if (!selectedRange) {
      updateSelectedElement({ styles: { backgroundColor } });
      return;
    }

    updateSelectedElement({
      richTextColors: [
        ...(selectedElement.richTextColors || []),
        { ...selectedRange, backgroundColor },
      ],
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
    const numericValue = parseBuilderTextFontSize(value);
    if (numericValue === null) return;
    const fontSize = `${numericValue}px`;
    const selectedRange = getSelectedTextRange();

    if (!selectedRange) {
      updateSelectedElement({ styles: { fontSize } });
      return;
    }

    updateSelectedElement({
      richTextSizes: [
        ...(selectedElement.richTextSizes || []).filter((range) =>
          range.field !== selectedRange.field ||
          (range.itemIndex ?? null) !== selectedRange.itemIndex ||
          range.end <= selectedRange.start ||
          range.start >= selectedRange.end
        ),
        { ...selectedRange, fontSize },
      ],
      styles: { selectedTextFontSize: fontSize },
    });
    window.getSelection()?.removeAllRanges();
  };

  const applyTextOpacity = (value) => {
    const numericValue = Math.max(0, Math.min(100, Number.parseInt(value, 10) || 0));
    const opacity = String(numericValue / 100);
    const selectedRange = getSelectedTextRange();

    if (!selectedRange) {
      updateSelectedElement({ styles: { opacity: Number(opacity) } });
      return;
    }

    updateSelectedElement({
      richTextStyles: [
        ...(selectedElement.richTextStyles || []),
        { ...selectedRange, opacity },
      ],
    });
    window.getSelection()?.removeAllRanges();
  };

  const applyTextFontFamily = (value) => {
    const fontFamily = getThemeFontStack(value);
    const selectedRange = getSelectedTextRange();

    if (!selectedRange) {
      updateSelectedElement({ styles: { fontFamily } });
      return;
    }

    updateSelectedElement({
      richTextStyles: [
        ...(selectedElement.richTextStyles || []),
        { ...selectedRange, fontFamily },
      ],
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
    if (["heading", "text"].includes(selectedElement.type)) {
      if (textSelection?.elementId === selectedElement.id && textSelection.blockFormat) {
        return textSelection.blockFormat;
      }
      const formats = getTextBlockFormats(selectedElement);
      const offset = textSelection?.elementId === selectedElement.id ? Number(textSelection.start) || 0 : 0;
      const [lineIndex] = getTextBlockIndexesForRange(selectedElement.content, offset, offset);
      return formats[lineIndex] || (selectedElement.type === "heading" ? getElementHeadingTag(selectedElement) : "text");
    }
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
      if (["heading", "text"].includes(selectedElement.type)) {
        const formats = getTextBlockFormats(selectedElement);
        const activeSelection = textSelectionRef.current?.elementId === selectedElement.id
          ? textSelectionRef.current
          : textSelection;
        const hasSelectionTarget = activeSelection?.elementId === selectedElement.id;
        const start = hasSelectionTarget ? Number(activeSelection.start) || 0 : 0;
        const end = hasSelectionTarget ? Number(activeSelection.end) || start : selectedElement.content.length;
        const targetLineIndexes = hasSelectionTarget && activeSelection.blockIndexes?.length
          ? activeSelection.blockIndexes
          : getTextBlockIndexesForRange(selectedElement.content, start, end);
        const shouldRemoveList = targetLineIndexes.every((lineIndex) => formats[lineIndex] === format);
        targetLineIndexes.forEach((lineIndex) => {
          formats[lineIndex] = shouldRemoveList ? "text" : format;
        });
        updateSelectedElement({ textBlockFormats: formats });
        textSelectionRef.current = textSelectionRef.current?.elementId === selectedElement.id
          ? { ...textSelectionRef.current, blockFormat: shouldRemoveList ? "text" : format }
          : textSelectionRef.current;
        setTextSelection((current) => current?.elementId === selectedElement.id
          ? { ...current, blockFormat: shouldRemoveList ? "text" : format }
          : current
        );
        return;
      }

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

    const headingLevel = getHeadingLevelFromFormat(format);
    if ((headingLevel || format === "text") && ["heading", "text"].includes(selectedElement.type)) {
      const nextFormat = headingLevel ? `h${headingLevel}` : "text";
      const formats = getTextBlockFormats(selectedElement);
      const activeSelection = textSelectionRef.current?.elementId === selectedElement.id
        ? textSelectionRef.current
        : textSelection;
      const hasSelectionTarget = activeSelection?.elementId === selectedElement.id;
      const start = hasSelectionTarget ? Number(activeSelection.start) || 0 : 0;
      const end = hasSelectionTarget ? Number(activeSelection.end) || start : selectedElement.content.length;
      const targetLineIndexes = hasSelectionTarget && activeSelection.blockIndexes?.length
        ? activeSelection.blockIndexes
        : getTextBlockIndexesForRange(selectedElement.content, start, end);
      targetLineIndexes.forEach((lineIndex) => {
        formats[lineIndex] = nextFormat;
      });
      const targetLines = new Set(targetLineIndexes);
      const lineBounds = String(selectedElement.content || "").split("\n").map((line, index, lines) => {
        const startOffset = lines.slice(0, index).reduce((total, item) => total + item.length + 1, 0);
        return { start: startOffset, end: startOffset + line.length };
      });
      const richTextSizes = (selectedElement.richTextSizes || []).filter((range) =>
        !lineBounds.some((bounds, lineIndex) =>
          targetLines.has(lineIndex) && range.field === "content" && range.end > bounds.start && range.start < bounds.end
        )
      );
      updateSelectedElement({ textBlockFormats: formats, richTextSizes });
      textSelectionRef.current = textSelectionRef.current?.elementId === selectedElement.id
        ? { ...textSelectionRef.current, blockFormat: nextFormat }
        : textSelectionRef.current;
      setTextSelection((current) => current?.elementId === selectedElement.id
        ? { ...current, blockFormat: nextFormat }
        : current
      );
      return;
    }

    if (headingLevel) {
      const content =
        selectedElement.type === "list"
          ? getListItems(selectedElement).join("\n")
          : selectedElement.content;
      updateSelectedElement({
        type: "heading",
        headingLevel,
        content,
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

    const applySelectedRangeStyle = (
      property,
      activeValue,
      inactiveValue,
      isActive
    ) => {
      if (hasExplicitSelectedTextRange() || selectedTextTargetIsListPart()) {
        const selectedRange = getSelectedTextRange();
        if (!selectedRange) return false;
        const currentValue = getSelectedTextRangeStyle(property);

        updateSelectedElement({
          richTextStyles: [
            ...(selectedElement.richTextStyles || []),
            {
              ...selectedRange,
              [property]: isActive(currentValue) ? inactiveValue : activeValue,
            },
          ],
        });
        window.getSelection()?.removeAllRanges();
        return true;
      }

      return false;
    };

    if (action === "bold") {
      if (applySelectedRangeStyle(
        "fontWeight",
        "700",
        "400",
        (value) => String(value).includes("700") || String(value).includes("bold")
      )) return;

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
      if (applySelectedRangeStyle(
        "fontStyle",
        "italic",
        "normal",
        (value) => value === "italic"
      )) return;

      updateSelectedElement({
        styles: {
          fontStyle: selectedElement.styles?.fontStyle === "italic" ? "" : "italic",
        },
      });
      return;
    }

    if (action === "underline") {
      if (applySelectedRangeStyle(
        "textDecoration",
        "underline",
        "none",
        (value) => value === "underline"
      )) return;

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
    const selectedRangeFontFamily = getSelectedTextRangeStyle("fontFamily");
    const selectedRangeOpacity = getSelectedTextRangeStyle("opacity");
    const activeFontFamily = selectedRangeFontFamily ||
      selectedElement.styles?.fontFamily ||
      getThemeFontStack(project.theme?.fontFamily);
    const activeTextOpacity = selectedRangeOpacity !== ""
      ? Number(selectedRangeOpacity)
      : Number(selectedElement.styles?.opacity ?? 1);
    const selectedRangeBackgroundColor = getSelectedTextRangeStyle("backgroundColor");
    const activeTextFormat = getInlineTextFormatValue();
    const blockDefaultFontSize = ({ h1: 46, h2: 36, h3: 28, text: 17, bullets: 17, numbers: 17 })[activeTextFormat];
    const toolbarFontSize = Number.parseInt(
      selectedRangeFontSize ||
        (blockDefaultFontSize && textSelection?.elementId === selectedElement.id
          ? blockDefaultFontSize
          : selectedElement.styles?.selectedTextFontSize ||
            selectedElement.styles?.fontSize ||
            getSelectedElementFontSizeNumber()),
      10
    );

    return (
      <div
        className="builder-inline-text-toolbar is-floating"
        ref={inlineToolbarRef}
        data-placement={inlineToolbarPosition.placement}
        style={{
          left: `${inlineToolbarPosition.left}px`,
          top: `${inlineToolbarPosition.top}px`,
          maxWidth: `${inlineToolbarPosition.maxWidth}px`,
        }}
        role="toolbar"
        aria-label="Text formatting"
        onClick={(event) => event.stopPropagation()}
        onMouseDown={(event) => event.stopPropagation()}
        onPointerDownCapture={() => {
          inlineToolbarInteractionRef.current = true;
        }}
        onPointerUpCapture={() => {
          window.setTimeout(() => {
            inlineToolbarInteractionRef.current = false;
          }, 0);
        }}
        onPointerCancelCapture={() => {
          inlineToolbarInteractionRef.current = false;
        }}
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
          <option value="h1">H1</option>
          <option value="h2">H2</option>
          <option value="h3">H3</option>
          <option value="button">Button</option>
          <option value="bullets">Bullets</option>
          <option value="numbers">Numbers</option>
        </select>
        <select
          aria-label="Font family"
          className="builder-inline-toolbar-font-family"
          value={
            pageBuilderFontFamilyOptions.find((fontFamily) =>
              activeFontFamily === fontFamily || String(activeFontFamily).startsWith(`"${fontFamily}"`)
            ) || "Inter"
          }
          onChange={(event) => applyTextFontFamily(event.target.value)}
          style={{ fontFamily: activeFontFamily }}
        >
          {pageBuilderFontFamilyOptions.map((fontFamily) => (
            <option key={fontFamily} value={fontFamily} style={{ fontFamily: getThemeFontStack(fontFamily) }}>
              {fontFamily}
            </option>
          ))}
        </select>
        <label className="builder-inline-toolbar-size" title="Text size">
          <span>Size</span>
          <input
            type="number"
            min="8"
            max={MAX_BUILDER_TEXT_FONT_SIZE_PX}
            step="1"
            value={inlineFontSizeDraft ?? toolbarFontSize}
            onFocus={() => setInlineFontSizeDraft(String(toolbarFontSize))}
            onChange={(event) => {
              const nextValue = event.target.value;
              setInlineFontSizeDraft(nextValue);
              if (parseBuilderTextFontSize(nextValue) !== null) {
                applyTextFontSize(nextValue);
              }
            }}
            onBlur={(event) => {
              if (event.target.value.trim()) applyTextFontSize(event.target.value);
              setInlineFontSizeDraft(null);
            }}
          />
        </label>
        <label className="builder-inline-toolbar-size" title="Text opacity">
          <span>Opacity</span>
          <input
            type="number"
            min="0"
            max="100"
            step="1"
            aria-label="Text opacity"
            value={Math.round(Math.max(0, Math.min(1, activeTextOpacity)) * 100)}
            onChange={(event) => applyTextOpacity(event.target.value)}
          />
          <span aria-hidden="true">%</span>
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
              (activeTextFormat === "bullets" ||
                (selectedElement.type === "list" && selectedElement.listStyle !== "decimal"))) ||
            (item.id === "numbers" &&
              (activeTextFormat === "numbers" ||
                (selectedElement.type === "list" && selectedElement.listStyle === "decimal"))) ||
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
            value={selectedElement.styles?.selectedTextColor || selectedElement.styles?.color || "#000000"}
            onChange={(event) => applyTextColor(event.target.value)}
          />
        </label>
        <label className="builder-inline-toolbar-color" title="Background color">
          <Highlighter size={16} aria-hidden="true" />
          <input
            type="color"
            value={selectedRangeBackgroundColor || selectedElement.styles?.backgroundColor || "#fffdfa"}
            onChange={(event) => applyTextBackgroundColor(event.target.value)}
          />
        </label>
      </div>
    );
  };

  const startMarqueeSelection = useCallback((event, section) => {
    if (
      preview ||
      dragState ||
      event.button !== 0 ||
      event.target?.closest?.(".direct-element-frame")
    ) return;

    const point = clientPointToCanvasLocal(
      event.currentTarget,
      event.clientX,
      event.clientY,
      { coordinateScale: 1 }
    );
    if (!point) return;

    const nextMarquee = {
      sectionId: section.id,
      pointerId: event.pointerId,
      startX: point.x,
      startY: point.y,
      currentX: point.x,
      currentY: point.y,
      additive: event.shiftKey || event.ctrlKey || event.metaKey,
    };
    selectionMarqueeRef.current = nextMarquee;
    setSelectionMarquee(nextMarquee);
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.stopPropagation();
    event.preventDefault();
  }, [dragState, preview]);

  const expandActiveSectionToHeight = useCallback((sectionId, requiredHeight) => {
    const nextRequiredHeight = Math.ceil(Number(requiredHeight) || 0);
    if (!sectionId || !nextRequiredHeight) return;

    updateSections((sections) => sections.map((section) => {
      if (section.id !== sectionId) return section;
      const currentHeight = getSectionCanvasHeight(section, viewport);
      if (nextRequiredHeight <= currentHeight) return section;

      return {
        ...section,
        layout: {
          ...(section.layout || {}),
          minHeight: viewport === "desktop" ? nextRequiredHeight : section.layout?.minHeight,
          minHeightByViewport: {
            ...(section.layout?.minHeightByViewport || {}),
            [viewport]: nextRequiredHeight,
          },
        },
      };
    }));
  }, [updateSections, viewport]);

  const handlePointerMove = (event) => {
    const activeMarquee = selectionMarqueeRef.current;
    if (
      activeMarquee &&
      (activeMarquee.pointerId === undefined || event.pointerId === activeMarquee.pointerId)
    ) {
      const frame = findBuilderDataElement(
        canvasShellRef.current,
        "data-section-id",
        activeMarquee.sectionId
      );
      const point = frame
        ? clientPointToCanvasLocal(frame, event.clientX, event.clientY, { coordinateScale: 1 })
        : null;
      if (point) {
        const nextMarquee = {
          ...activeMarquee,
          currentX: point.x,
          currentY: point.y,
        };
        selectionMarqueeRef.current = nextMarquee;
        setSelectionMarquee(nextMarquee);
      }
      event.stopPropagation();
      event.preventDefault();
      return;
    }

    if (
      !dragState ||
      !selectedElement ||
      selectedElement.id !== dragState.elementId ||
      (dragState.pointerId !== undefined && event.pointerId !== dragState.pointerId)
    ) return;

    const section = getElementSection(selectedElement.id);
    if (!section) return;
    const parentGeometry = getElementParentGeometry(selectedElement.id);
    const localPointer = parentGeometry?.parent
      ? clientPointToCanvasLocal(
          parentGeometry.parent,
          event.clientX,
          event.clientY,
          { coordinateScale: 1 }
        )
      : null;
    if (!parentGeometry?.geometry || !localPointer) return;

    const bounds = parentGeometry.geometry.bounds;
    const deltaX = localPointer.x - dragState.startPointerLocalX;
    const deltaY = localPointer.y - dragState.startPointerLocalY;
    const canvasWidth = bounds.width;
    const canvasHeight = bounds.height;
    const visibleCanvasBounds = getVisibleCanvasLocalBounds(
      parentGeometry.parent,
      canvasShellRef.current,
      { coordinateScale: 1 }
    ) || bounds;
    const candidate = getDragCandidatePosition({
      dragState: { ...dragState, deltaX, deltaY },
      selectedElement,
      bounds,
      allowBottomOverflow: true,
      snapToGrid,
    });
    const constrainedCandidate = dragState.interaction === "resize"
      ? constrainResizeToSiblingElements({
          candidate,
          siblings: (section.freeElements || []).filter(
            (element) => element.id !== selectedElement.id
          ),
          selectedElement,
          viewport,
          createPosition,
          dragState,
          canvasWidth,
        })
      : candidate;
    const groupElementIds = dragState.groupElementIds || [selectedElement.id];
    const guideSiblings = (section.freeElements || [])
      .filter((element) => !groupElementIds.includes(element.id))
      .map((element) => element.position?.[viewport])
      .filter(Boolean);
    const minimumSize = getDirectElementMinimumSize(selectedElement);
    let previewPosition = clampElementToBounds(
      {
        ...(selectedElement.position?.[viewport] || createPosition()[viewport]),
        ...constrainedCandidate,
      },
      bounds,
      {
        minWidth: minimumSize.width,
        minHeight: minimumSize.height,
        mode: dragState.interaction === "resize" ? "resize" : "move",
        allowBottomOverflow: true,
      }
    );
    let previewPositions = { [selectedElement.id]: previewPosition };
    let smartGuides = [];

    if (dragState.interaction === "move" && groupElementIds.length > 1) {
      previewPositions = getGroupDragPreviewPositions({
        startPositions: dragState.groupStartPositions,
        primaryElementId: selectedElement.id,
        primaryPreview: previewPosition,
        bounds,
      });
      const groupBounds = getPositionCollectionBounds(previewPositions);
      const groupGuideSnap = getSmartGuideSnap({
        candidate: groupBounds,
        siblings: guideSiblings,
        canvasWidth,
        canvasHeight,
        canvasBounds: visibleCanvasBounds,
        interaction: "move",
      });
      const groupPrimary = previewPositions[selectedElement.id];
      if (groupBounds && groupPrimary) {
        const requestedDeltaX = groupGuideSnap.position.x - groupBounds.x;
        const requestedDeltaY = groupGuideSnap.position.y - groupBounds.y;
        previewPositions = getGroupDragPreviewPositions({
          startPositions: dragState.groupStartPositions,
          primaryElementId: selectedElement.id,
          primaryPreview: {
            ...groupPrimary,
            x: groupPrimary.x + requestedDeltaX,
            y: groupPrimary.y + requestedDeltaY,
          },
          bounds,
        });
        const finalGroupBounds = getPositionCollectionBounds(previewPositions);
        const appliedX = (finalGroupBounds?.x || 0) - groupBounds.x;
        const appliedY = (finalGroupBounds?.y || 0) - groupBounds.y;
        smartGuides = groupGuideSnap.guides.filter((guide) =>
          guide.dimension === "x"
            ? Math.abs(appliedX - requestedDeltaX) < 0.5
            : Math.abs(appliedY - requestedDeltaY) < 0.5
        );
      }
      previewPosition = previewPositions[selectedElement.id] || previewPosition;
    } else {
      const guideSnap = getSmartGuideSnap({
        candidate: previewPosition,
        siblings: guideSiblings,
        canvasWidth,
        canvasHeight,
        canvasBounds: visibleCanvasBounds,
        interaction: dragState.interaction,
      });
      previewPosition = clampElementToBounds(
        { ...previewPosition, ...guideSnap.position },
        bounds,
        {
          minWidth: minimumSize.width,
          minHeight: minimumSize.height,
          mode: dragState.interaction === "resize" ? "resize" : "move",
          allowBottomOverflow: true,
        }
      );
      previewPositions = { [selectedElement.id]: previewPosition };
      smartGuides = guideSnap.guides;
    }

    const dropFrame = dragState.interaction === "move" && groupElementIds.length === 1
      ? getDirectFrameAtPoint(event.clientX, event.clientY)
      : null;
    const dropSectionId = dropFrame?.dataset?.sectionId;
    const previewSectionHeight = Math.max(
      canvasHeight,
      ...Object.values(previewPositions).map((position) => Math.ceil(
        (Number(position.y) || 0) + (Number(position.height) || 0) + 48
      ))
    );

    pendingDragPreviewRef.current = {
      previewPosition,
      previewPositions,
      previewSectionHeight,
      smartGuides,
      dropSectionId: dropSectionId && dropSectionId !== section.id ? dropSectionId : "",
    };

    if (dragPreviewFrameRef.current !== null) return;
    dragPreviewFrameRef.current = window.requestAnimationFrame(() => {
      dragPreviewFrameRef.current = null;
      const previewUpdate = pendingDragPreviewRef.current;
      if (!previewUpdate) return;
      setDragState((currentState) => currentState ? { ...currentState, ...previewUpdate } : currentState);
      expandActiveSectionToHeight(section.id, previewUpdate.previewSectionHeight);
    });
  };

  const handlePointerUp = (event) => {
    const activeMarquee = selectionMarqueeRef.current;
    if (
      activeMarquee &&
      (activeMarquee.pointerId === undefined || event.pointerId === activeMarquee.pointerId)
    ) {
      const width = Math.abs(activeMarquee.currentX - activeMarquee.startX);
      const height = Math.abs(activeMarquee.currentY - activeMarquee.startY);
      const completedSelection = width >= 4 || height >= 4;
      const section = activePage?.sections.find((item) => item.id === activeMarquee.sectionId);

      selectionMarqueeRef.current = null;
      setSelectionMarquee(null);

      if (completedSelection && section) {
        const hitIds = getMarqueeSelectionIds(
          section.freeElements || [],
          viewport,
          activeMarquee
        );
        const nextSelection = activeMarquee.additive
          ? [...new Set([...effectiveSelectedElementIds, ...hitIds])]
          : hitIds;
        setSelectedElementIds(nextSelection);
        setSelected(nextSelection.length
          ? { type: "element", id: hitIds[hitIds.length - 1] || nextSelection[0] }
          : { type: "section", id: section.id }
        );
        suppressCanvasClickRef.current = true;
        window.setTimeout(() => {
          suppressCanvasClickRef.current = false;
        }, 0);
        event.stopPropagation();
        event.preventDefault();
        return;
      }
    }

    if (!dragState || !selectedElement || selectedElement.id !== dragState.elementId) return;

    if (dragPreviewFrameRef.current !== null) {
      window.cancelAnimationFrame(dragPreviewFrameRef.current);
      dragPreviewFrameRef.current = null;
    }
    const finalPreview = pendingDragPreviewRef.current || dragState;
    pendingDragPreviewRef.current = null;
    const sourceLocation = findElementLocation(selectedElement.id);
    const targetFrame = finalPreview.dropSectionId
      ? findBuilderDataElement(document, "data-section-id", finalPreview.dropSectionId)
      : null;
    const targetSection = activePage?.sections.find((section) => section.id === finalPreview.dropSectionId);

    const groupElementIds = dragState.groupElementIds || [selectedElement.id];
    const committingGroup =
      dragState.interaction === "move" &&
      groupElementIds.length > 1 &&
      finalPreview.previewPositions;

    if (committingGroup && sourceLocation) {
      updateSections((sections) => commitDirectElementGroupInteraction(sections, {
        sourceSectionId: sourceLocation.sectionId,
        previewPositions: finalPreview.previewPositions,
        previewSectionHeight: finalPreview.previewSectionHeight,
        viewportName: viewport,
        smartResponsive: smartResponsiveEnabled,
      }));
      showToast(`Moved ${groupElementIds.length} components together.`);
    } else if (targetFrame && targetSection && sourceLocation && sourceLocation.sectionId !== targetSection.id) {
      const frameRect = targetFrame.getBoundingClientRect();
      const targetPoint = clientPointToCanvasLocal(
        targetFrame,
        event.clientX,
        event.clientY,
        { coordinateScale: 1 }
      );
      const nextPosition = getMovedElementPosition({
        selectedElement,
        targetSection,
        viewport,
        event,
        frameRect,
        canvasScale,
        activeBounds: targetPoint?.bounds,
        activePoint: targetPoint,
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
        viewportName: viewport,
        smartResponsive: smartResponsiveEnabled,
      }));
      showToast(`Moved ${selectedElement.name || "component"} to ${targetSection.name || "section"}.`);
    } else if (sourceLocation && finalPreview.previewPosition) {
      updateSections((sections) => commitDirectElementInteraction(sections, {
        elementId: selectedElement.id,
        previewPosition: finalPreview.previewPosition,
        previewSectionHeight: finalPreview.previewSectionHeight,
        sourceSectionId: sourceLocation.sectionId,
        viewportName: viewport,
        smartResponsive: smartResponsiveEnabled,
        elementUpdates:
          dragState.interaction === "resize"
            ? selectedElement.type === "heading"
              ? { directWidthMode: "fixed" }
              : selectedElement.type === "reservationBlock"
                ? { directSizeMode: "fixed" }
                : null
            : null,
      }));
    }

    setDragState(null);
    setSelected({ type: "element", id: selectedElement.id });
  };

  const handlePointerCancel = () => {
    if (selectionMarqueeRef.current) {
      selectionMarqueeRef.current = null;
      setSelectionMarquee(null);
    }
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
      shouldIgnoreInlineTextBlur,
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
      shouldIgnoreInlineTextBlur,
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
    publicRuntime: preview,
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
      setLogoUrlDraftEdited(false);
    });
  }, [siteChrome.logoUrl]);

  const applyLogoUrl = useCallback(() => {
    updateSiteChrome({ logoUrl: logoUrlDraft.trim() });
    setLogoUrlDraftEdited(false);
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
      return splitEditableLines(siteChrome[fieldKey]);
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

  const renderFooterDestinationEditor = ({ itemsKey, legacyKey, label, itemPlaceholder }) => {
    const items = getFooterLinkItems(siteChrome[itemsKey], siteChrome[legacyKey], { preserveEmpty: true });
    const saveItems = (nextItems) => updateSiteChrome({
      [itemsKey]: nextItems,
      [legacyKey]: nextItems.map((item) => item.label || "").join("\n"),
    });

    return (
      <div className="site-chrome-list-editor site-chrome-destination-editor">
        <div className="site-chrome-list-editor-header">
          <span>{label}</span>
          <button
            type="button"
            onClick={() => saveItems([...items, { label: "", url: "" }])}
          >
            + Add
          </button>
        </div>
        <div className="site-chrome-list-rows">
          {items.map((item, index) => {
            const urlError = getFooterLinkUrlError(item.url, item.label || itemPlaceholder);
            return (
              <div className="site-chrome-list-row site-chrome-destination-row" key={`${itemsKey}-${index}`}>
                <span className="site-chrome-list-bullet" aria-hidden="true" />
                <div className="site-chrome-destination-fields">
                  <input
                    aria-label={`${label} label ${index + 1}`}
                    value={item.label}
                    placeholder={itemPlaceholder}
                    onChange={(event) => saveItems(items.map((entry, itemIndex) => (
                      itemIndex === index ? { ...entry, label: event.target.value } : entry
                    )))}
                  />
                  <input
                    aria-label={`${label} destination ${index + 1}`}
                    value={item.url}
                    placeholder="https://example.com or /endpoint"
                    aria-invalid={Boolean(urlError)}
                    onChange={(event) => saveItems(items.map((entry, itemIndex) => (
                      itemIndex === index ? { ...entry, url: event.target.value } : entry
                    )))}
                  />
                  {urlError ? <small className="site-chrome-url-error">{urlError}</small> : null}
                </div>
                <button
                  type="button"
                  aria-label={`Remove ${label} item ${index + 1}`}
                  title="Remove item"
                  onClick={() => {
                    const nextItems = items.filter((_, itemIndex) => itemIndex !== index);
                    saveItems(nextItems.length ? nextItems : [{ label: "", url: "" }]);
                  }}
                >
                  x
                </button>
              </div>
            );
          })}
        </div>
        <span className="site-chrome-field-help">Add an HTTPS link or an internal endpoint beginning with /.</span>
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
                lastCloudSavedAt={lastCloudSavedAt}
                onSave={() => saveProject({ successMessage: "Changes saved." })}
                onPreview={handlePreviewClick}
                onGoLive={publishProject}
                publicationState={publicationState}
                saveDisabled={
                  builderProjectLoading ||
                  hasProtectedUnreadableDraft ||
                  saveState === BUILDER_SAVE_STATES.conflict
                }
                saveState={saveState}
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
                          onClick={() => {
                            const targetSectionId = selectedSection?.id || "";
                            addComponentToSection(
                              item.id,
                              targetSectionId,
                              getVisibleCanvasInsertPoint(targetSectionId)
                            );
                          }}
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
        className="builder-canvas-shell editor-viewport camera-manual"
        ref={canvasShellRef}
        onClick={() => {
          if (!preview) {
            setInlineToolbarPosition(null);
            setSelected({ type: "page", id: activePage?.id });
          }
        }}
      >
        {!preview && renderInlineTextToolbar()}
        <div
          className="editor-camera-stage"
          data-logical-width={logicalArtboardWidth}
          data-editor-zoom={canvasScale}
          style={{ width: cameraStageWidth + "px" }}
        >
        <SiteRenderer
          project={project}
          activePage={activePage}
          viewportMode={viewport}
          presentationZoom={canvasScale}
          availablePresentationWidth={editorViewportWidth}
          responsiveLayoutWidth={logicalArtboardWidth}
          responsiveChangedElementIds={smartResponsiveEnabled && dragState
            ? dragState.groupElementIds || [dragState.elementId]
            : []}
          responsiveTransientRectsBySection={smartResponsiveEnabled && dragState?.parentSectionId
            ? {
                [dragState.parentSectionId]: dragState.previewPositions || (
                  dragState.previewPosition ? { [dragState.elementId]: dragState.previewPosition } : {}
                ),
              }
            : {}}
          renderElement={renderElement}
          renderSiteHeader={renderSiteHeader}
          renderSiteFooter={renderSiteFooter}
          carouselElementTypes={carouselElementTypes}
          getDirectElementPosition={getRenderedDirectElementPosition}
          getSectionLogicalHeight={(section) =>
            dragState?.elementId && getElementSection(dragState.elementId)?.id === section.id
              ? Math.max(getSectionCanvasHeight(section, viewport), Number(dragState.previewSectionHeight) || 0)
              : getSectionCanvasHeight(section, viewport)
          }
          getSectionProps={(section) => {
            const isSelected = selected.type === "section" && selected.id === section.id;
            const isDirect = section.mode === "direct" || section.mode === "free";
            return {
              className: [
                isSelected ? "is-selected" : "",
                isDirect && (dragState?.dropSectionId === section.id || paletteDropSectionId === section.id) ? "is-drop-target" : "",
              ].filter(Boolean).join(" "),
              onClick: (event) => {
                if (suppressCanvasClickRef.current) {
                  suppressCanvasClickRef.current = false;
                  event.stopPropagation();
                  return;
                }
                event.stopPropagation();
                if (preview) return;
                if (isDirect) {
                  const frame = event.currentTarget.querySelector(".direct-layout-frame");
                  const point = frame ? clientPointToCanvasLocal(frame, event.clientX, event.clientY, { coordinateScale: 1 }) : { x: 40, y: 40 };
                  setInsertTarget({ sectionId: section.id, mode: "direct", x: Math.max(0, Math.round(point.x)), y: Math.max(0, Math.round(point.y)) });
                } else {
                  setInsertTarget({ sectionId: section.id, mode: "auto", columnId: getClosestColumnIdFromEvent(event), afterElementId: "" });
                }
                setSelected({ type: "section", id: section.id });
              },
              renderOverlay: isDirect ? () => (
                <div className="editor-overlay editor-section-overlay">
                  {dragState?.parentSectionId === section.id && (dragState.smartGuides || []).map((guide, guideIndex) => {
                    const vertical = guide.axis === "vertical";
                    const start = Math.min(Number(guide.start) || 0, Number(guide.end) || 0);
                    const length = Math.max(1, Math.abs((Number(guide.end) || 0) - (Number(guide.start) || 0)));
                    return (
                      <div
                        key={guide.axis + "-" + guide.value + "-" + guideIndex}
                        className={"direct-smart-guide is-" + guide.axis + " is-" + (guide.kind || "alignment")}
                        aria-hidden="true"
                        style={vertical ? { left: guide.value + "px", top: start + "px", height: length + "px" } : { left: start + "px", top: guide.value + "px", width: length + "px" }}
                      >
                        {guide.label && <span>{guide.label}</span>}
                      </div>
                    );
                  })}
                  {selectionMarquee?.sectionId === section.id && (
                    <div
                      className="direct-selection-marquee"
                      aria-hidden="true"
                      style={{
                        left: Math.min(selectionMarquee.startX, selectionMarquee.currentX) + "px",
                        top: Math.min(selectionMarquee.startY, selectionMarquee.currentY) + "px",
                        width: Math.abs(selectionMarquee.currentX - selectionMarquee.startX) + "px",
                        height: Math.abs(selectionMarquee.currentY - selectionMarquee.startY) + "px",
                      }}
                    />
                  )}
                </div>
              ) : undefined,
            };
          }}
          getDirectCanvasProps={(section) => ({
            className: selectedElement?.layer === "behindText" && (section.freeElements || []).some((element) => element.id === selectedElement.id) ? "is-editing-behind-text" : "",
            onPointerDown: (event) => startMarqueeSelection(event, section),
            onDragOver: (event) => {
              event.preventDefault();
              event.dataTransfer.dropEffect = "copy";
              if (paletteDropSectionId !== section.id) setPaletteDropSectionId(section.id);
            },
            onDragLeave: (event) => {
              if (!event.currentTarget.contains(event.relatedTarget)) setPaletteDropSectionId("");
            },
            onDrop: (event) => handlePaletteDrop(event, section),
          })}
          getDirectFrameProps={(element) => {
            const elementSelected = effectiveSelectedElementIds.includes(element.id);
            const elementIsPrimary = selected.type === "element" && selected.id === element.id;
            const usesDetachedEditBoundary = elementSelected && element.layer === "behindText" && !preview;
            return {
              className: [elementSelected && !usesDetachedEditBoundary ? "is-selected" : "", elementSelected && !elementIsPrimary ? "is-group-selected" : ""].filter(Boolean).join(" "),
              tabIndex: -1,
              onPointerDownCapture: (event) => {
                if (preview) return;
                event.currentTarget.focus({ preventScroll: true });
                selectCanvasElement(element.id, { additive: event.shiftKey || event.ctrlKey || event.metaKey });
              },
              onPointerDown: preview ? undefined : (event) => startDrag(event, element, "move", element.type === "button"),
              onClick: (event) => { if (!preview) event.stopPropagation(); },
            };
          }}
          renderDirectElementOverlay={(element) => {
            const elementSelected = effectiveSelectedElementIds.includes(element.id);
            const usesDetachedEditBoundary = elementSelected && element.layer === "behindText" && !preview;
            if (!elementSelected || preview || usesDetachedEditBoundary) return null;
            return (
              <div className="editor-overlay editor-element-overlay">
                <button type="button" className="direct-move-handle" aria-label={"Move " + (element.name || "component")} title="Drag to move in any direction" onPointerDown={(event) => startDrag(event, element, "move", true)}>
                  <Move size={13} aria-hidden="true" />
                </button>
                <button type="button" className="direct-resize-handle" aria-label={"Resize " + (element.name || "component")} title="Drag to resize" onPointerDown={(event) => startDrag(event, element, "resize", true)} />
              </div>
            );
          }}
          renderAfterDirectElement={(element, section, frameStyle) => {
            const elementSelected = effectiveSelectedElementIds.includes(element.id);
            if (!elementSelected || element.layer !== "behindText" || preview) return null;
            return (
              <div className="direct-element-frame direct-element-edit-boundary is-selected" style={{ ...frameStyle, zIndex: 6 }} tabIndex={-1} onPointerDownCapture={(event) => event.currentTarget.focus({ preventScroll: true })} onPointerDown={(event) => startDrag(event, element, "move")} onClick={(event) => event.stopPropagation()}>
                <div className="editor-overlay editor-element-overlay">
                <button type="button" className="direct-move-handle" aria-label={"Move " + (element.name || "component")} title="Drag to move in any direction" onPointerDown={(event) => startDrag(event, element, "move", true)}>
                  <Move size={13} aria-hidden="true" />
                </button>
                <button type="button" className="direct-resize-handle" aria-label={"Resize " + (element.name || "component")} title="Drag to resize" onPointerDown={(event) => startDrag(event, element, "resize", true)} />
                </div>
              </div>
            );
          }}
          getColumnProps={(column, section) => ({
            className: selected.type === "column" && selected.id === column.id ? "is-selected" : "",
            onClick: (event) => {
              event.stopPropagation();
              if (!preview) {
                setInsertTarget({ sectionId: section.id, mode: "auto", columnId: column.id, afterElementId: "" });
                setSelected({ type: "column", id: column.id });
              }
            },
          })}
          renderEmptyColumn={(column) => !preview && column.elements.length === 0 ? <div className="empty-column">Select this column, then add an element.</div> : null}
        />
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
          <span>{inspectorMode}</span>
        </div>

      {activePageLayers.length > 0 && (
        <div className="inspector-group element-layer-picker">
          <h3>Layers</h3>
          <label>
            Select an element
            <select
              value={selectedElement?.id || ""}
              onChange={(event) => {
                if (!event.target.value) return;
                setInlineToolbarPosition(null);
                selectCanvasElement(event.target.value, { forceSingle: true });
              }}
            >
              <option value="">Choose a layer</option>
              {activePageLayers.map(({ element, sectionName }) => (
                <option value={element.id} key={element.id}>
                  {element.name || element.type} · {sectionName}{element.layer === "behindText" ? " · Behind text" : ""}
                </option>
              ))}
            </select>
          </label>
          <div className="layer-selection-actions">
            <button type="button" className="primary-action" onClick={selectAllCanvasElements}>
              Select all in section
            </button>
            {effectiveSelectedElementIds.length > 0 && (
              <button type="button" className="danger-lite" onClick={clearCanvasElementSelection}>
                Clear selection
              </button>
            )}
          </div>
          <p className="builder-note" role="status">
            {effectiveSelectedElementIds.length > 0
              ? `${effectiveSelectedElementIds.length} component${effectiveSelectedElementIds.length === 1 ? "" : "s"} selected. Drag any selected component to move the group.`
              : "Shift, Ctrl, or Cmd-click components to select a custom group."}
          </p>
        </div>
      )}

      {smartResponsiveEnabled && activeSmartDiagnostics.some(
        (diagnostic) => diagnostic.code === "unresolved_manual_collision"
      ) && (
        <div className="inspector-group responsive-layout-control">
          <h3>Responsive issues</h3>
          {activeSmartDiagnostics
          .filter((diagnostic) => diagnostic.code === "unresolved_manual_collision")
          .map((diagnostic) => (
            <div
              className="responsive-collision-diagnostic"
              key={`${diagnostic.sectionId}:${diagnostic.elementIds.join(":")}:${diagnostic.layoutWidth}`}
              role="alert"
            >
              <strong>Manual collision</strong>
              <p className="builder-note">
                {diagnostic.elementIds.join(" and ")} conflict at {diagnostic.layoutWidth}px.
                Publishing remains blocked until this is resolved.
              </p>
              <div className="layer-selection-actions">
                <button type="button" onClick={() => applyResponsiveDiagnosticAction(diagnostic, "move_element")}>
                  Move element
                </button>
                <button type="button" onClick={() => applyResponsiveDiagnosticAction(diagnostic, "reset_to_auto")}>
                  Reset to Auto
                </button>
                <button type="button" onClick={() => applyResponsiveDiagnosticAction(diagnostic, "mark_intentional_overlay")}>
                  Mark overlay
                </button>
                <button type="button" onClick={() => applyResponsiveDiagnosticAction(diagnostic, "mark_background")}>
                  Mark background
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {inspectorMode === "page" && activePage && (
        <PageBuilderPageInspector
          page={activePage}
          loadingImagePreviewUrl={resolveMediaUrl(siteChrome.loadingImageUrl || siteChrome.logoUrl)}
          hasCustomLoadingImage={Boolean(siteChrome.loadingImageUrl)}
          assetUploadBusy={assetUploadBusy}
          onLoadingImageUpload={handleLoadingImageUpload}
          onResetLoadingImage={() => {
            updateSiteChrome({ loadingImageUrl: "" });
            showToast("Loading image reset to the site logo.");
          }}
          hasRoutingIssue={collectPublicPageRoutingIssues(project).some((issue) =>
            issue.page_id === activePage.id ||
            issue.occurrences?.some((page) => page.page_id === activePage.id)
          )}
          onSetDefault={(checked) => {
            if (!checked) {
              showToast("Every site needs a homepage. Choose another page to replace this one.");
              return;
            }

            const currentHomepage = project.pages.find((page) => page.isDefault === true);
            if (!currentHomepage) {
              updateProject((prev) => setProjectDefaultPage(prev, activePage.id));
              return;
            }
            if (currentHomepage.id === activePage.id) return;

            setHomepageOverridePending({
              pageId: activePage.id,
              pageName: activePage.name || "This page",
              currentHomepageName: currentHomepage.name || "Current homepage",
            });
          }}
          onUpdate={(changes) => updateProject((prev) => {
            const currentPage = prev.pages.find((page) => page.id === activePage.id);
            const nextChanges = { ...changes };
            if (Object.prototype.hasOwnProperty.call(changes, "name")) {
              nextChanges.name = createUniqueBuilderPageName({
                name: changes.name,
                pages: prev.pages,
                currentPageId: activePage.id,
                preserveOuterWhitespace: true,
              });
              nextChanges.slug = createUniquePublicPageSlug({
                name: nextChanges.name,
                pages: prev.pages,
                currentPageId: activePage.id,
                isDefault: currentPage?.isDefault === true,
              });
            }
            return {
              ...prev,
              pages: prev.pages.map((page) =>
                page.id === activePage.id ? { ...page, ...nextChanges } : page
              ),
            };
          })}
        />
      )}

      {(inspectorMode === "siteHeader" || inspectorMode === "siteFooter") && (
        <div className="inspector-group">
          <h3>{selected.type === "siteHeader" ? "Header" : "Footer"}</h3>
          <p className="builder-note">Use the Header & Footer workspace for global site chrome settings.</p>
          <button type="button" className="full-width-action" onClick={() => setActiveTab("chrome")}>
            Open Header & Footer
          </button>
        </div>
      )}

      {inspectorMode === "section" && selectedSection && (
        <div className="inspector-group">
          <h3>Section</h3>
          <label>
            Section name
            <input
              value={selectedSection.name || ""}
              onChange={(event) => updateSelectedSection({ name: event.target.value })}
            />
          </label>
          <label>
            Background
            <input
              type="color"
              value={getColorInputValue(selectedSection.layout?.background, "#ffffff")}
              onChange={(event) => updateSelectedSection({ layout: { background: event.target.value } })}
            />
          </label>
        </div>
      )}

      {inspectorMode === "column" && selectedColumn && (
        <div className="inspector-group">
          <h3>Column</h3>
          <label>Alignment<select value={selectedColumn.layout.align} onChange={(event) => updateSelectedColumn({ layout: { align: event.target.value } })}>{alignmentOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        </div>
      )}

      {inspectorMode === "element" && selectedElement && (
        <div className="inspector-group">
          <h3>{selectedElement.type === "reservationBlock" ? "Reservation" : "Element"}</h3>
          {smartResponsiveEnabled && ["tablet", "mobile"].includes(viewport) && (
            <div className="responsive-element-override">
              <p className="builder-note">
                {selectedElement.responsive?.overrides?.[viewport]?.mode === "manual"
                  ? `${viewport} geometry is manually overridden.`
                  : `${viewport} geometry is generated automatically.`}
              </p>
              <button
                type="button"
                className="danger-lite"
                onClick={() => {
                  const resetElement = withAutoResponsiveOverride(selectedElement, viewport);
                  updateSelectedElement({ responsive: resetElement.responsive });
                  showToast(`${viewport} layout reset to Auto.`);
                }}
              >
                Reset {viewport} to Auto
              </button>
            </div>
          )}
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
              <summary>Carousel cards</summary>
              <p className="builder-note">Edit each card and choose or replace its image.</p>
              <div className="carousel-slide-list">
                {parseCarouselSlides(selectedElement.content).map((slide, index) => (
                  <details className="carousel-slide-card" defaultOpen={index === 0} key={`${selectedElement.id}_slide_${index}`}>
                    <summary>
                      <span>Card {index + 1}</span>
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
                    <label>Description<textarea value={slide.description || ""} onChange={(event) => {
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
                  <button type="button" className="danger-lite" disabled={parseCarouselSlides(selectedElement.content).length <= 1} onClick={() => updateSelectedElement({ content: serializeCarouselSlides(parseCarouselSlides(selectedElement.content).filter((_, itemIndex) => itemIndex !== index)) })}>Remove card</button>
                    </div>
                  </details>
                ))}
              </div>
              <button type="button" className="primary-action" onClick={() => updateSelectedElement({ content: serializeCarouselSlides([...parseCarouselSlides(selectedElement.content), { title: "New card", description: "Add supporting text here.", image: "" }]) })}>+ Add card</button>
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
          {selectedElement.type === "photoProofing" && (() => {
            const photos = parsePhotoProofingContent(selectedElement.content);
            const cover = photos[0] || null;
            return (
              <details open className="photo-proofing-settings">
                <summary>Photo selection</summary>
                <label>Card title<input value={selectedElement.proofing?.title || ""} onChange={(event) => updateSelectedElement({ proofing: { ...(selectedElement.proofing || {}), title: event.target.value } })} /></label>
                <label>Cover description<textarea value={selectedElement.proofing?.description || ""} onChange={(event) => updateSelectedElement({ proofing: { ...(selectedElement.proofing || {}), description: event.target.value } })} /></label>
                <p className="builder-note">This description belongs only to the first image, which is the cover of the card.</p>
                <label>Button text<input value={selectedElement.proofing?.buttonText || ""} onChange={(event) => updateSelectedElement({ proofing: { ...(selectedElement.proofing || {}), buttonText: event.target.value } })} /></label>

                <div className="photo-proofing-cover-editor">
                  <div className="photo-proofing-editor-heading"><strong>Cover image</strong><span>First image</span></div>
                  {cover ? (
                    <div className="photo-proofing-cover-preview">
                      <img src={resolveMediaUrl(cover.image)} alt="" />
                      <span>{cover.title}</span>
                    </div>
                  ) : (
                    <div className="photo-proofing-cover-empty">Choose the first image for the card.</div>
                  )}
                  <div className="photo-proofing-cover-actions">
                    <label className="upload-image-button">
                      {assetUploadBusy ? "Uploading..." : cover ? "Replace cover" : "Upload cover"}
                      <input type="file" accept="image/png,image/jpeg,image/webp" hidden disabled={assetUploadBusy} onChange={(event) => handlePhotoProofingImagesUpload(event, { replaceCover: true })} />
                    </label>
                    {cover && <button type="button" className="danger-lite" onClick={() => updateSelectedElement({ content: serializePhotoProofingContent(photos.slice(1)) })}>Remove cover</button>}
                  </div>
                </div>

                <div
                  className="photo-proofing-gallery-upload"
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    uploadPhotoProofingFiles(event.dataTransfer.files);
                  }}
                >
                  <strong>Upload gallery images</strong>
                  <span>Drop any number of images here, or choose them together.</span>
                  <label className="upload-image-button">
                    {assetUploadBusy ? "Uploading..." : "Choose images"}
                    <input type="file" accept="image/png,image/jpeg,image/webp" multiple hidden disabled={assetUploadBusy} onChange={handlePhotoProofingImagesUpload} />
                  </label>
                </div>

                <div className="photo-proofing-gallery-list">
                  <div className="photo-proofing-editor-heading"><strong>Gallery</strong><span>{Math.max(0, photos.length - 1)} images</span></div>
                  {photos.slice(1).map((photo, galleryIndex) => {
                    const photoIndex = galleryIndex + 1;
                    return (
                      <div className="photo-proofing-gallery-item" key={`${photo.image}-${photoIndex}`}>
                        <img src={resolveMediaUrl(photo.image)} alt="" />
                        <input
                          aria-label={`Photo ${photoIndex + 1} title`}
                          value={photo.title || ""}
                          onChange={(event) => updateSelectedElement({
                            content: serializePhotoProofingContent(photos.map((item, index) => index === photoIndex ? { ...item, title: event.target.value } : item)),
                          })}
                        />
                        <button type="button" onClick={() => updateSelectedElement({
                          content: serializePhotoProofingContent([
                            { ...photo, description: selectedElement.proofing?.description || "" },
                            ...photos.filter((_, index) => index !== photoIndex),
                          ]),
                        })}>Make cover</button>
                        <button type="button" className="danger-lite" aria-label={`Remove ${photo.title || `photo ${photoIndex + 1}`}`} onClick={() => updateSelectedElement({
                          content: serializePhotoProofingContent(photos.filter((_, index) => index !== photoIndex)),
                        })}>Remove</button>
                      </div>
                    );
                  })}
                  {photos.length <= 1 && <p className="builder-note">Gallery images will be loaded one by one after the cover.</p>}
                </div>
              </details>
            );
          })()}
          {selectedElement.type === "thinDivider" && (
            <details open className="horizontal-line-editor">
              <summary>Horizontal line</summary>
              <label>
                Thickness
                <input
                  type="number"
                  min="1"
                  max="20"
                  step="1"
                  value={Math.max(1, Math.min(20, Number.parseInt(selectedElement.styles?.["--divider-thickness"], 10) || 1))}
                  onChange={(event) => {
                    const thickness = Math.max(1, Math.min(20, Number.parseInt(event.target.value, 10) || 1));
                    updateSelectedElement({ styles: { "--divider-thickness": `${thickness}px` } });
                  }}
                />
              </label>
              <label>
                Line color
                <input
                  type="color"
                  value={getColorInputValue(selectedElement.styles?.color, "#6b7280")}
                  onChange={(event) => updateSelectedElement({ styles: { color: event.target.value } })}
                />
              </label>
            </details>
          )}
          {!carouselElementTypes.has(selectedElement.type) &&
            selectedElement.type !== "list" &&
            selectedElement.type !== "metric" &&
            selectedElement.type !== "photoProofing" &&
            selectedElement.type !== "reservationBlock" &&
            selectedElement.type !== "loginBlock" &&
            selectedElement.type !== "registrationBlock" &&
            selectedElement.type !== "image" &&
            selectedElement.type !== "imageButton" &&
            selectedElement.type !== "document" &&
            selectedElement.type !== "divider" &&
            selectedElement.type !== "thinDivider" && (
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

          {selectedElement.type === "reservationBlock" && (() => {
            const selectedReservationId = selectedElement.connectedReservationBlockId || selectedElement.id;
            const compatibleOptions = reservationFormOptions.filter((option) =>
              !selectedElement.reservationPlacementType ||
              option.mode === selectedElement.reservationPlacementType ||
              option.id === selectedReservationId
            );

            return (
              <div className="reservation-form-picker">
                <label>
                  Reservation form
                  <select
                    value={selectedReservationId}
                    onChange={(event) => {
                      const source = reservationDefinitions.find(
                        (block) => block.element.id === event.target.value
                      )?.element;
                      if (!source) return;
                      updateSelectedElement({
                        connectedReservationBlockId: source.id,
                        reservation: source.reservation,
                      });
                    }}
                  >
                    {compatibleOptions.length === 0 && (
                      <option value="">Create a compatible reservation form first</option>
                    )}
                    {compatibleOptions.map((option) => (
                      <option value={option.id} key={option.id}>
                        {option.label} - {option.meta}
                      </option>
                    ))}
                  </select>
                </label>
                {compatibleOptions.length > 1 && (
                  <p className="builder-note">Choose which reservation form this section should use.</p>
                )}
              </div>
            );
          })()}
          {["image", "imageButton"].includes(selectedElement.type) && (
            <>
              <label>
                File name
                <input
                  readOnly
                  value={selectedElement.assetFileName || getBuilderAssetFileName(selectedElement.content)}
                  placeholder="No image selected"
                />
              </label>
              <label className="upload-image-button">
                {assetUploadBusy ? "Uploading..." : "Upload image"}
                <input type="file" accept="image/png,image/jpeg,image/webp" hidden disabled={assetUploadBusy} onChange={handleSelectedElementImageUpload} />
              </label>
              <label className="image-opacity-control">
                <span>
                  <span>Opacity</span>
                  <output>{Math.round(Math.max(0, Math.min(1, Number(selectedElement.styles?.opacity ?? 1))) * 100)}%</output>
                </span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  aria-label="Image opacity"
                  value={Math.round(Math.max(0, Math.min(1, Number(selectedElement.styles?.opacity ?? 1))) * 100)}
                  onChange={(event) =>
                    updateSelectedElement({ styles: { opacity: Number(event.target.value) / 100 } })
                  }
                />
              </label>
              <label className="image-opacity-control">
                <span>
                  <span>Image size inside boundary</span>
                  <output>{Math.round(Math.max(0.25, Math.min(3, Number.parseFloat(selectedElement.styles?.["--image-scale"]) || 1)) * 100)}%</output>
                </span>
                <input
                  type="range"
                  min="25"
                  max="300"
                  step="1"
                  aria-label="Image size inside boundary"
                  value={Math.round(Math.max(0.25, Math.min(3, Number.parseFloat(selectedElement.styles?.["--image-scale"]) || 1)) * 100)}
                  onChange={(event) =>
                    updateSelectedElement({
                      styles: { "--image-scale": String(Number(event.target.value) / 100) },
                    })
                  }
                />
              </label>
              <button
                type="button"
                className="full-width-action"
                onClick={() => updateSelectedElement({
                  styles: { "--image-scale": "1" },
                })}
              >
                Reset image scale
              </button>
              {selectedElement.type === "image" && (selectedElement.mode === "direct" ? (
                <label className="inspector-toggle-row image-layer-toggle">
                  <input
                    type="checkbox"
                    checked={selectedElement.layer === "behindText"}
                    onChange={(event) => setSelectedImageBehindText(event.target.checked)}
                  />
                  <span>Place image behind text</span>
                </label>
              ) : (
                <p className="builder-note">Place the image on the free canvas to layer it behind text.</p>
              ))}
              {selectedElement.type === "image" && selectedElement.layer === "behindText" && (
                <p className="builder-note">Image editing mode is active. Elements above it are click-through so you can move or resize this image.</p>
              )}
            </>
          )}

          {selectedElement.type === "video" && (
            <>
              <label>
                File name
                <input
                  readOnly
                  value={selectedElement.assetFileName || getBuilderAssetFileName(selectedElement.content)}
                  placeholder="No video selected"
                />
              </label>
              <label className="upload-image-button">
                {assetUploadBusy ? "Uploading..." : "Upload video"}
                <input type="file" accept="video/mp4,video/webm" hidden disabled={assetUploadBusy} onChange={handleSelectedElementVideoUpload} />
              </label>
              <p className="builder-note">MP4 or WebM, up to 250 MB.</p>
              <label className="inspector-toggle-row">
                <input
                  type="checkbox"
                  checked={selectedElement.video?.controls !== false}
                  onChange={(event) => updateSelectedElement({ video: { ...selectedElement.video, controls: event.target.checked } })}
                />
                <span>Show playback controls</span>
              </label>
              <label className="inspector-toggle-row">
                <input
                  type="checkbox"
                  checked={Boolean(selectedElement.video?.muted)}
                  onChange={(event) => updateSelectedElement({ video: { ...selectedElement.video, muted: event.target.checked } })}
                />
                <span>Muted</span>
              </label>
              <label className="inspector-toggle-row">
                <input
                  type="checkbox"
                  checked={Boolean(selectedElement.video?.loop)}
                  onChange={(event) => updateSelectedElement({ video: { ...selectedElement.video, loop: event.target.checked } })}
                />
                <span>Loop video</span>
              </label>
            </>
          )}

          {selectedElement.type === "document" && (
            <>
              <label>
                Viewer title
                <input
                  value={selectedElement.document?.title || ""}
                  placeholder="View document"
                  onChange={(event) => updateSelectedElement({
                    document: { ...selectedElement.document, title: event.target.value },
                  })}
                />
              </label>
              <label>
                Description
                <textarea
                  value={selectedElement.document?.description || ""}
                  placeholder="Open this file in a focused viewer."
                  onChange={(event) => updateSelectedElement({
                    document: { ...selectedElement.document, description: event.target.value },
                  })}
                />
              </label>
              <label>
                File name
                <input
                  readOnly
                  value={selectedElement.assetFileName || getBuilderAssetFileName(selectedElement.content)}
                  placeholder="No file selected"
                />
              </label>
              <label className="upload-image-button">
                {assetUploadBusy ? "Uploading..." : "Upload file"}
                <input
                  type="file"
                  accept="application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.pdf,.doc,.docx"
                  hidden
                  disabled={assetUploadBusy}
                  onChange={handleSelectedElementDocumentUpload}
                />
              </label>
              <p className="builder-note">PDF, DOC, or DOCX, up to 50 MB. PDFs preview inside the viewer; Word files open with a compatible app.</p>
            </>
          )}

          {["button", "imageButton"].includes(selectedElement.type) && (
            <>
              {selectedElement.type === "button" && (
                <ButtonColorControls key={selectedElement.id} element={selectedElement} onChange={updateSelectedElement} />
              )}
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
            </>
          )}

          <div className="element-clipboard-actions">
            <button type="button" onClick={() => copySelectedElement()}><Copy size={15} aria-hidden="true" /><span>Copy</span></button>
            <button type="button" disabled={!hasCopiedElement} onClick={() => pasteCopiedElement()}><ClipboardPaste size={15} aria-hidden="true" /><span>Paste</span></button>
            <button type="button" onClick={duplicateSelectedElement}><CopyPlus size={15} aria-hidden="true" /><span>Duplicate</span></button>
          </div>
          <button type="button" className="danger-button" onClick={deleteSelectedElement}>Delete Element</button>
          <p className="builder-note">Shortcuts: Ctrl/Cmd+C to copy, Ctrl/Cmd+V to paste, and Delete or Backspace to remove.</p>
        </div>
      )}
      {inspectorMode === "empty" && (
        <p className="builder-note">Select or create a page to edit its settings.</p>
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
                      <input
                        id="site-chrome-logo-url"
                        value={logoUrlDraftEdited ? logoUrlDraft : getBuilderAssetFileName(siteChrome.logoUrl)}
                        placeholder="Image URL"
                        onChange={(event) => {
                          setLogoUrlDraftEdited(true);
                          setLogoUrlDraft(event.target.value);
                        }}
                      />
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
                  <label className="span-2">
                    Header color
                    <span className="site-chrome-color-control">
                      <input
                        aria-label="Header color"
                        type="color"
                        value={getColorInputValue(
                          siteChrome.headerBackgroundColor,
                          getColorInputValue(
                            project.theme?.headerBackground,
                            getColorInputValue(project.theme?.surface, "#FFFDFA")
                          )
                        )}
                        onChange={(event) => updateSiteChrome({
                          headerBackgroundColor: event.target.value.toUpperCase(),
                        })}
                      />
                      <output>{siteChrome.headerBackgroundColor || "Theme color"}</output>
                      <button
                        type="button"
                        onClick={() => updateSiteChrome({ headerBackgroundColor: "" })}
                        disabled={!siteChrome.headerBackgroundColor}
                      >
                        Use theme color
                      </button>
                    </span>
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
            <div className="site-chrome-footer-structure">
              <div className="site-chrome-footer-title-row">
                <label>Pages column title<input value={siteChrome.footerShopTitle || ""} onChange={(event) => updateSiteChrome({ footerShopTitle: event.target.value })} /></label>
                <label>Help column title<input value={siteChrome.footerHelpTitle || ""} onChange={(event) => updateSiteChrome({ footerHelpTitle: event.target.value })} /></label>
              </div>
              <div className="site-chrome-footer-panel-row">
                {renderFooterPageLinksEditor()}
                {renderFooterListEditor("footerHelpLinks", "Help links", "Help item")}
              </div>
              <div className="site-chrome-footer-panel-row">
                {renderFooterDestinationEditor({
                  itemsKey: "footerSocialItems",
                  legacyKey: "footerSocialLinks",
                  label: "Social links",
                  itemPlaceholder: "Social channel",
                })}
                {renderFooterDestinationEditor({
                  itemsKey: "footerPaymentItems",
                  legacyKey: "footerPaymentMethods",
                  label: "Payment labels",
                  itemPlaceholder: "Payment label",
                })}
              </div>
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
      openFormPreviewPage={openFormPreviewPage}
      saveProject={saveProject}
      openPreviewPage={openPreviewPage}
      publishProject={publishProject}
      quizOptionsOpen={quizOptionsOpen}
      setQuizOptionsOpen={setQuizOptionsOpen}
    />
  );

  const renderReservationsTab = () => (
    <ReservationsTab
      reservationBlocks={reservationDefinitions}
      activeReservationId={
        selected.type === "element" && selectedElement?.type === "reservationBlock"
          ? selectedElement.connectedReservationBlockId || selected.id
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
      users={siteMembers}
      usersLoading={siteMembersLoading}
      usersError={siteMembersError}
      userMutationId={siteMemberMutationId}
      selected={selected}
      selectedRole={selectedRole}
      permissionGroups={permissionGroups}
      addUser={addSiteUser}
      addRole={addRole}
      updateUser={updateSiteUser}
      updateRole={updateRole}
      deleteUser={requestDeleteSiteUser}
      reloadUsers={loadSiteMembers}
      setSelected={setSelected}
      isSavingProject={isSavingProject}
      onSave={() => publishProject()}
      saveDisabled={
        builderProjectLoading ||
        hasProtectedUnreadableDraft ||
        saveState === BUILDER_SAVE_STATES.conflict
      }
      saveState={saveState}
    />
  );

  const renderThemeTab = (themeTabProps = {}) => (
    <ThemeTab
      project={project}
      updateProject={updateProject}
      setThemeMode={setThemeMode}
      legacyShadowEnabled={legacyShadowEnabled}
      legacyShadowComparison={legacyShadowComparison}
      onToggleLegacyShadow={() => setLegacyShadowEnabled((current) => !current)}
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
      loadProject={reloadServerProject}
      exportProject={exportProject}
      liveSitePath={canonicalLiveSitePath}
      hasConfiguredSubdomain={Boolean(publicSiteSubdomain)}
      openWebsiteSettings={() => navigate("/settings")}
      openPublicFormPage={openPublicFormPage}
      onPreviewSite={handlePreviewClick}
      onUnpublish={unpublishProject}
      isUnpublishing={isUnpublishingProject}
      isLiveProject={
        Boolean(builderProjectRecord?.id) &&
        String(websiteSettings?.published_project_id || "") ===
          String(builderProjectRecord?.id || "")
      }
      onMakeLive={makeCurrentProjectLive}
      isMakingLive={isBindingPublicProject}
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
        .map((tab) => {
          const tabPath = routeProjectId
            ? getBuilderWorkspacePath(routeProjectId, tab.id, routeWorkspace)
            : builderTabPathById[tab.id];

          return (
            <Link
              key={tab.id}
              to={tabPath}
              className={activeTab === tab.id ? "active" : ""}
              aria-current={activeTab === tab.id ? "page" : undefined}
            >
              {builderCopy.tabs[tab.id]?.label || tab.label}
            </Link>
          );
        })}
    </nav>
  );

  if (!demoMode && builderProjectLoading) {
    return (
      <div className={getPageBuilderThemeClassName({ mode: appThemeMode || "light", renderMode: "editing" })}>
        <main
          className="builder-project-loading builder-project-loading-silent"
          aria-busy="true"
          aria-label="Loading project"
        >
          <LoadingBar label="Loading project" />
        </main>
      </div>
    );
  }

  if (!demoMode && !builderProjectRecord) {
    return (
      <div className={getPageBuilderThemeClassName({ mode: appThemeMode || "light", renderMode: "editing" })}>
        <main className="builder-project-loading" role="alert">
          <div className="builder-project-loading-card">
            <h2>Project could not be loaded</h2>
            <p>No browser copy was opened. Reload this page to retry the server request.</p>
            <button type="button" className="page-primary-action" onClick={() => window.location.reload()}>
              Retry
            </button>
          </div>
        </main>
      </div>
    );
  }

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
    String(websiteSettings?.brand || "").trim() ||
    String(project.siteChrome?.brand || project.siteChrome?.brandName || "").trim() ||
    builderCopy.projectNames[project.name] ||
    project.name ||
    "Untitled Site";
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
          artboardCameraControls={(
            <div className="artboard-camera-controls" role="toolbar" aria-label="Artboard zoom">
              <button type="button" className={manualEditorZoom === 1 ? "is-active" : ""} onClick={() => setManualEditorZoom(1)}>100%</button>
              <button type="button" aria-label="Zoom out" onClick={() => setManualEditorZoom((value) => clampEditorZoom(value - 0.1))}>-</button>
              <output>{Math.round(canvasScale * 100)}%</output>
              <button type="button" aria-label="Zoom in" onClick={() => setManualEditorZoom((value) => clampEditorZoom(value + 0.1))}>+</button>
            </div>
          )}
          builderCopy={builderCopy}
          demoMode={demoMode}
          displayName={projectDisplayName}
          handlePreviewClick={handlePreviewClick}
          hideWorkspaceTabs={hideWorkspaceTabs}
          openPreviewPage={openPreviewPage}
          preview={preview}
          project={project}
          renderWorkspaceNavigator={renderWorkspaceNavigator}
          setActiveTopbarAction={setActiveTopbarAction}
          setModal={setModal}
          setPreview={setPreview}
          setViewport={setViewport}
          viewport={viewport}
          viewports={viewports}
        />


        <BuilderConflictResolution
          key={conflictDetails?.detectedAt || "no-conflict"}
          conflict={saveState === BUILDER_SAVE_STATES.conflict ? conflictDetails || {} : null}
          onDownload={exportProject}
          onLoadCandidate={fetchConflictServerCandidate}
          onResolveConflicts={resolveOverlappingConflicts}
          onUseServer={() => adoptServerProject(conflictServerCandidate)}
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

      {homepageOverridePending && (
        <PageDeleteConfirmModal
          title="Replace the homepage?"
          message={
            <>
              <strong>{homepageOverridePending.currentHomepageName}</strong> is currently the homepage. Make{" "}
              <strong>{homepageOverridePending.pageName}</strong> the new homepage instead?
            </>
          }
          cancelLabel="Keep current homepage"
          confirmLabel="Replace homepage"
          onCancel={() => setHomepageOverridePending(null)}
          onConfirm={() => {
            updateProject((prev) => setProjectDefaultPage(prev, homepageOverridePending.pageId));
            setHomepageOverridePending(null);
          }}
        />
      )}

      {reloadConfirmationOpen && (
        <PageDeleteConfirmModal
          title="Reload this page?"
          message="Your latest changes have not finished saving. Reloading now will discard them."
          cancelLabel="Keep editing"
          confirmLabel="Reload page"
          onCancel={() => setReloadConfirmationOpen(false)}
          onConfirm={() => {
            allowNextUnloadRef.current = true;
            setReloadConfirmationOpen(false);
            window.location.reload();
          }}
        />
      )}

      <PageBuilderStatusBar toast={toast} />
    </div>
  );
}
