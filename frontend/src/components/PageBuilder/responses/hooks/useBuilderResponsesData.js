import { useEffect, useState } from "react";
import {
  fetchBuilderFormSubmissionsPage,
  updateBuilderFormSubmissionStatus,
} from "../../services/PageBuilder.api";
import { RESPONSE_PAGE_SIZE, SUBMISSION_STATUSES } from "../constants";
import {
  getResponseLoadMessage,
  hasAnswerValue,
  normalizeBackendResponse,
  normalizeStatus,
  uniqueByNormalizedStatus,
} from "../utils/responsesUtils";

export function useBuilderResponsesData({
  project,
  builderProjectId,
  activeForm,
  getFormFields,
  formatSavedValue,
  showToast,
  user,
  t,
}) {
  const selectedForm = activeForm || project.forms?.[0];
  const selectedFormId = selectedForm?.id || "";
  const allForms = project.forms || [];
  const [backendResponsesByForm, setBackendResponsesByForm] = useState({});
  const [backendPaginationByForm, setBackendPaginationByForm] = useState({});
  const [responsePageByForm, setResponsePageByForm] = useState({});
  const [responsesLoading, setResponsesLoading] = useState(false);
  const [responsesError, setResponsesError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFieldIds, setSelectedFieldIds] = useState([]);
  const [selectedStatuses, setSelectedStatuses] = useState([]);
  const [selectedResponseId, setSelectedResponseId] = useState("");
  const [statusUpdatingById, setStatusUpdatingById] = useState({});
  const [refreshKey, setRefreshKey] = useState(0);
  const selectedPage = responsePageByForm[selectedFormId] || 0;
  const selectedOffset = selectedPage * RESPONSE_PAGE_SIZE;

  useEffect(() => {
    if (!builderProjectId || !selectedFormId) {
      setResponsesLoading(false);
      setResponsesError("");
      return undefined;
    }

    let cancelled = false;
    setResponsesLoading(true);
    setResponsesError("");

    fetchBuilderFormSubmissionsPage(builderProjectId, {
      form_id: selectedFormId,
      limit: RESPONSE_PAGE_SIZE,
      offset: selectedOffset,
      user_id: user?.id,
    })
      .then(({ submissions, pagination }) => {
        if (cancelled) return;
        setBackendResponsesByForm((current) => ({
          ...current,
          [selectedFormId]: submissions.map(normalizeBackendResponse),
        }));
        setBackendPaginationByForm((current) => ({
          ...current,
          [selectedFormId]: pagination,
        }));
      })
      .catch((error) => {
        if (!cancelled) setResponsesError(getResponseLoadMessage(error, t));
      })
      .finally(() => {
        if (!cancelled) setResponsesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [builderProjectId, selectedFormId, selectedOffset, refreshKey, t, user?.id]);

  const getDisplayResponsesForForm = (form) => {
    if (!form) return [];
    if (builderProjectId && backendResponsesByForm[form.id]) return backendResponsesByForm[form.id];
    if (builderProjectId) return [];
    return form.responses || [];
  };

  const fields = selectedForm ? getFormFields(selectedForm) : [];
  const responses = getDisplayResponsesForForm(selectedForm);
  const dynamicStatusOptions = uniqueByNormalizedStatus([
    ...responses.map((response) => response.status || "New"),
    ...SUBMISSION_STATUSES,
  ]);
  const selectedFieldSet = new Set(selectedFieldIds);
  const selectedStatusSet = new Set(selectedStatuses.map(normalizeStatus));
  const normalizedQuery = searchQuery.trim().toLowerCase();

  const getFieldValueText = (response, field) =>
    String(formatSavedValue(response.answers?.[field.id]) || "").toLowerCase();

  const responseMatchesSearch = (response) => {
    const matchesStatus =
      selectedStatusSet.size === 0 ||
      selectedStatusSet.has(normalizeStatus(response.status || "New"));

    if (!matchesStatus) return false;
    if (!normalizedQuery) return true;

    const searchableFields =
      selectedFieldSet.size > 0
        ? fields.filter((field) => selectedFieldSet.has(field.id))
        : fields;

    if (searchableFields.some((field) => getFieldValueText(response, field).includes(normalizedQuery))) {
      return true;
    }

    if (selectedFieldSet.size > 0) return false;

    return [response.status, response.createdAt, response.quiz?.score]
      .filter((value) => value !== undefined && value !== null)
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery);
  };

  const displayedResponses = responses.filter(responseMatchesSearch);
  const selectedPagination = backendPaginationByForm[selectedFormId];
  const requiredFields = fields.filter((field) => field.required);
  const optionalFields = Math.max(0, fields.length - requiredFields.length);
  const answeredCells = displayedResponses.reduce(
    (total, response) =>
      total + fields.filter((field) => hasAnswerValue(response.answers?.[field.id])).length,
    0
  );
  const completionRate =
    displayedResponses.length && fields.length
      ? Math.round((answeredCells / (displayedResponses.length * fields.length)) * 100)
      : 0;
  const selectedResponse =
    displayedResponses.find((response) => response.id === selectedResponseId) ||
    displayedResponses[0] ||
    null;
  const totalResponses = allForms.reduce(
    (total, form) => total + getDisplayResponsesForForm(form).length,
    0
  );
  const formsWithResponses = allForms.filter(
    (form) => getDisplayResponsesForForm(form).length > 0
  ).length;

  useEffect(() => {
    setSelectedResponseId("");
    setSelectedFieldIds([]);
    setSearchQuery("");
    setSelectedStatuses([]);
  }, [selectedFormId]);

  useEffect(() => {
    if (!selectedResponseId && displayedResponses[0]?.id) {
      setSelectedResponseId(displayedResponses[0].id);
    }
  }, [displayedResponses, selectedResponseId]);

  const refreshResponses = () => {
    if (!builderProjectId || !selectedFormId || responsesLoading) return;
    setRefreshKey((current) => current + 1);
  };

  const setSelectedPage = (page) => {
    if (!builderProjectId || !selectedFormId || responsesLoading) return;
    setResponsePageByForm((current) => ({
      ...current,
      [selectedFormId]: Math.max(0, page),
    }));
  };

  const toggleSelectedField = (fieldId) => {
    setSelectedFieldIds((current) =>
      current.includes(fieldId) ? current.filter((id) => id !== fieldId) : [...current, fieldId]
    );
  };

  const toggleSelectedStatus = (status) => {
    const normalized = normalizeStatus(status);
    setSelectedStatuses((current) =>
      current.some((item) => normalizeStatus(item) === normalized)
        ? current.filter((item) => normalizeStatus(item) !== normalized)
        : [...current, status]
    );
  };

  const clearSelectedFields = () => {
    setSelectedFieldIds([]);
  };

  const clearSelectedStatuses = () => {
    setSelectedStatuses([]);
  };

  const updateSubmissionStatus = async (submissionId, status) => {
    if (!builderProjectId || !selectedFormId || !submissionId) return;

    setStatusUpdatingById((current) => ({ ...current, [submissionId]: true }));

    try {
      const updatedSubmission = await updateBuilderFormSubmissionStatus(
        builderProjectId,
        submissionId,
        status,
        user?.id
      );
      const normalizedSubmission = normalizeBackendResponse(updatedSubmission);

      setBackendResponsesByForm((current) => ({
        ...current,
        [selectedFormId]: (current[selectedFormId] || []).map((submission) =>
          submission.id === submissionId ? normalizedSubmission : submission
        ),
      }));
    } catch (error) {
      showToast?.(error?.message || t.updateStatusFailed);
    } finally {
      setStatusUpdatingById((current) => ({ ...current, [submissionId]: false }));
    }
  };

  const clearFilters = () => {
    setSearchQuery("");
    setSelectedFieldIds([]);
    setSelectedStatuses([]);
  };

  return {
    allForms,
    fields,
    selectedForm,
    selectedFormId,
    responses,
    displayedResponses,
    selectedResponse,
    selectedResponseId,
    setSelectedResponseId,
    getDisplayResponsesForForm,
    totalResponses,
    formsWithResponses,
    requiredFields,
    optionalFields,
    completionRate,
    latestResponse: selectedPage === 0 ? responses[0] : null,
    selectedPage,
    selectedOffset,
    selectedPagination,
    hasBackendPagination: Boolean(builderProjectId && selectedFormId),
    hasNextPage: Boolean(builderProjectId && selectedFormId && selectedPagination?.has_more),
    hasPreviousPage: Boolean(builderProjectId && selectedFormId && selectedPage > 0),
    setSelectedPage,
    refreshResponses,
    responsesLoading,
    responsesError,
    searchQuery,
    setSearchQuery,
    selectedFieldIds,
    selectedFieldSet,
    toggleSelectedField,
    clearSelectedFields,
    selectedStatuses,
    selectedStatusSet,
    dynamicStatusOptions,
    toggleSelectedStatus,
    clearSelectedStatuses,
    clearFilters,
    hasFilters: Boolean(searchQuery || selectedFieldIds.length > 0 || selectedStatuses.length > 0),
    statusUpdatingById,
    updateSubmissionStatus,
  };
}
