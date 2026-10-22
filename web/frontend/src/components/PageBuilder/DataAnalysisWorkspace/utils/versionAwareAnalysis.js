export const getAssistedAnalysisRequest = ({ dataset, projectId, body }) => {
  const datasetId = dataset?.persistent_dataset_id;
  const versionId = dataset?.dataset_version_id;

  if (projectId && datasetId && versionId) {
    return {
      path: `/analysis/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(datasetId)}/versions/${encodeURIComponent(versionId)}/assist`,
      body,
      versionAware: true,
    };
  }

  return {
    path: "/analysis/assist",
    body: { input_path: dataset?.file_path, ...body },
    versionAware: false,
  };
};
