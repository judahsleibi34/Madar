import PageBuilderTopbar from "../ui/PageBuilderTopbar";
import PageBuilderSubbar from "../ui/PageBuilderSubbar";

export default function PageBuilderWorkspaceHeader({
  activeHelper,
  activeTab,
  activeTopbarAction,
  artboardCameraControls,
  builderCopy,
  demoMode,
  displayName,
  handlePreviewClick,
  hideWorkspaceTabs,
  historyControls,
  openPreviewPage,
  preview,
  project,
  renderWorkspaceNavigator,
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
        onPreviewClick={handlePreviewClick}
        activeTopbarAction={activeTopbarAction}
        setActiveTopbarAction={setActiveTopbarAction}
        setModal={setModal}
        openPreviewPage={openPreviewPage}
        setPreview={setPreview}
      />

      <PageBuilderSubbar
        preview={preview}
        hideWorkspaceTabs={hideWorkspaceTabs}
        historyControls={historyControls}
        viewports={viewports}
        viewport={viewport}
        setViewport={setViewport}
        renderWorkspaceNavigator={renderWorkspaceNavigator}
        artboardCameraControls={artboardCameraControls}
      />
    </>
  );
}
