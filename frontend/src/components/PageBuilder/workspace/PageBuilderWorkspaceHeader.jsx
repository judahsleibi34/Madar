import PageBuilderTopbar from "../ui/PageBuilderTopbar";
import PageBuilderSubbar from "../ui/PageBuilderSubbar";

export default function PageBuilderWorkspaceHeader({
  activeHelper,
  activeTab,
  activeTopbarAction,
  builderCopy,
  demoMode,
  displayName,
  handlePreviewClick,
  hideWorkspaceTabs,
  openPreviewPage,
  preview,
  project,
  renderWorkspaceNavigator,
  saveProject,
  setActiveTopbarAction,
  setModal,
  setPreview,
  setViewport,
  viewport,
  viewports,
}) {
  return (
    <>
      <PageBuilderTopbar
        project={project}
        displayName={displayName}
        activeHelper={activeHelper}
        hideWorkspaceTabs={hideWorkspaceTabs}
        hideActions
        activeTab={activeTab}
        preview={preview}
        demoMode={demoMode}
        copy={builderCopy.topbar}
        activeTopbarAction={activeTopbarAction}
        setActiveTopbarAction={setActiveTopbarAction}
        setModal={setModal}
        openPreviewPage={openPreviewPage}
        setPreview={setPreview}
        saveProject={saveProject}
      />

      <PageBuilderSubbar
        preview={preview}
        hideWorkspaceTabs={hideWorkspaceTabs}
        viewports={viewports}
        viewport={viewport}
        setViewport={setViewport}
        copy={builderCopy.topbar}
        onPreviewClick={handlePreviewClick}
        renderWorkspaceNavigator={renderWorkspaceNavigator}
      />
    </>
  );
}
