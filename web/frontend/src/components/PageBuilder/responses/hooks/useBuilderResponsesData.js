import { useEffect, useState } from "react";
import {
  deleteBuilderFormRecord,
  updateBuilderFormRecord,
  fetchBuilderFormDraftsPage,
  fetchBuilderFormSubmissionsPage,
  updateBuilderFormSubmissionStatus,
} from "../../services/PageBuilder.api";
import { RESPONSE_PAGE_SIZE } from "../constants";
import {
  getAnswerSearchText,
  getDynamicStatusOptions,
  getResponseLoadMessage,
  getResponseStatusValues,
  hasAnswerValue,
  isStatusField,
  normalizeBackendResponse,
  normalizeStatus,
} from "../utils/responsesUtils";
import {
  createResponsesCacheKey,
  getOrCreateResponsesRequest,
  readResponsesCache,
  writeResponsesCache,
} from "../utils/responsesCache";

const deferEffectStateUpdate = (callback) => {
  let cancelled = false;
  queueMicrotask(() => {
    if (!cancelled) callback();
  });
  return () => {
    cancelled = true;
  };
};

export function useBuilderResponsesData({
  project,
  builderProjectId,
  activeForm,
  getFormFields,
  formatSavedValue,
  showToast,
  user,
  t,
  responseView = "completed",
}) {
  const selectedForm = activeForm || project.forms?.[0];
  const selectedFormId = selectedForm?.id || "";
  const allForms = project.forms || [];
  const userScope =
    user?.id || user?.auth_id || user?.authId || user?.email || "authenticated";
  const [initialCache] = useState(() => {
    if (!builderProjectId || !selectedFormId) return null;
    return readResponsesCache(
      createResponsesCacheKey({
        userScope,
        projectId: builderProjectId,
        formId: selectedFormId,
        view: responseView,
        limit: RESPONSE_PAGE_SIZE,
        offset: 0,
      })
    );
  });
  const [backendResponsesByForm, setBackendResponsesByForm] = useState(() =>
    initialCache ? { [selectedFormId]: initialCache.responses } : {}
  );
  const [backendPaginationByForm, setBackendPaginationByForm] = useState(() =>
    initialCache ? { [selectedFormId]: initialCache.pagination } : {}
  );
  const [responsePageByForm, setResponsePageByForm] = useState({});
  const [responsesLoading, setResponsesLoading] = useState(false);
  const [responsesError, setResponsesError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFieldIds, setSelectedFieldIds] = useState([]);
  const [selectedStatuses, setSelectedStatuses] = useState([]);
  const [selectedResponseId, setSelectedResponseId] = useState("");
  const [statusUpdatingById, setStatusUpdatingById] = useState({});
  const [recordMutatingById, setRecordMutatingById] = useState({});
  const [refreshKey, setRefreshKey] = useState(0);
  const selectedPage = responsePageByForm[selectedFormId] || 0;
  const selectedOffset = selectedPage * RESPONSE_PAGE_SIZE;
  const selectedCacheKey =
    builderProjectId && selectedFormId
      ? createResponsesCacheKey({
          userScope,
          projectId: builderProjectId,
          formId: selectedFormId,
          view: responseView,
          limit: RESPONSE_PAGE_SIZE,
          offset: selectedOffset,
        })
      : "";

  useEffect(() => {
    if (!builderProjectId || !selectedFormId) {
      return deferEffectStateUpdate(() => {
        setResponsesLoading(false);
        setResponsesError("");
      });
    }

    let cancelled = false;
    const cached = readResponsesCache(selectedCacheKey);
    const forceRefresh = refreshKey > 0;

    queueMicrotask(() => {
      if (cancelled) return;

      if (cached) {
        setBackendResponsesByForm((current) => ({
          ...current,
          [selectedFormId]: cached.responses,
        }));
        setBackendPaginationByForm((current) => ({
          ...current,
          [selectedFormId]: cached.pagination,
        }));
      }

      setResponsesLoading(forceRefresh || !cached);
      setResponsesError("");
    });

    // A fresh cached page is enough for normal navigation. The Refresh button
    // deliberately bypasses this return and replaces the cached page.
    if (cached && !forceRefresh) {
      return () => {
        cancelled = true;
      };
    }

    getOrCreateResponsesRequest(selectedCacheKey, () =>
      (responseView === "incomplete" ? fetchBuilderFormDraftsPage : fetchBuilderFormSubmissionsPage)(
        builderProjectId,
        {
          form_id: selectedFormId,
          limit: RESPONSE_PAGE_SIZE,
          offset: selectedOffset,
          user_id: user?.id,
        }
      )
    )
      .then(({ submissions, pagination }) => {
        if (cancelled) return;

        const normalizedResponses = submissions.map(normalizeBackendResponse);
        setBackendResponsesByForm((current) => ({
          ...current,
          [selectedFormId]: normalizedResponses,
        }));
        setBackendPaginationByForm((current) => ({
          ...current,
          [selectedFormId]: pagination,
        }));
        writeResponsesCache(
          selectedCacheKey,
          normalizedResponses,
          pagination
        );
      })
      .catch((error) => {
        if (!cancelled && !cached) {
          setResponsesError(getResponseLoadMessage(error, t));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setResponsesLoading(false);
          if (forceRefresh) setRefreshKey(0);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [
    builderProjectId,
    refreshKey,
    selectedCacheKey,
    selectedFormId,
    selectedOffset,
    responseView,
    t,
    user?.id,
  ]);

  const getDisplayResponsesForForm = (form) => {
    if (!form) return [];
    if (builderProjectId && backendResponsesByForm[form.id]) return backendResponsesByForm[form.id];
    return [];
  };

  const fields = selectedForm ? getFormFields(selectedForm) : [];
  const responses = getDisplayResponsesForForm(selectedForm);
  const statusFields = fields.filter(isStatusField);
  const dynamicStatusOptions = getDynamicStatusOptions(fields, responses);
  const selectedFieldSet = new Set(selectedFieldIds);
  const selectedStatusSet = new Set(selectedStatuses.map(normalizeStatus));
  const normalizedQuery = searchQuery.trim().toLowerCase();

  const getFieldValueText = (response, field) =>
    String(formatSavedValue(response.answers?.[field.id]) || "").toLowerCase();

  const responseMatchesSearch = (response) => {
    const matchesStatus = selectedStatusSet.size === 0 || getResponseStatusValues(
      response,
      statusFields
    ).some((status) => selectedStatusSet.has(normalizeStatus(status)));

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

    // Include values retained from an older form schema or supplied by a
    // connected ecommerce record, such as a product name.
    if (getAnswerSearchText(response.answers, formatSavedValue).includes(normalizedQuery)) {
      return true;
    }

    return [
      response.status,
      response.createdAt,
      response.quiz?.score,
      response.submittedBy?.name,
      response.submittedBy?.email,
      response.submittedBy?.role,
    ]
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
    return deferEffectStateUpdate(() => {
      setSelectedResponseId("");
      setSelectedFieldIds([]);
      setSearchQuery("");
      setSelectedStatuses([]);
    });
  }, [responseView, selectedFormId]);

  useEffect(() => {
    if (!selectedResponseId && displayedResponses[0]?.id) {
      return deferEffectStateUpdate(() => {
        setSelectedResponseId(displayedResponses[0].id);
      });
    }
    return undefined;
  }, [displayedResponses, selectedResponseId]);

  const refreshResponses = () => {
    if (!builderProjectId || !selectedFormId || responsesLoading) return;
    setRefreshKey((current) => current + 1);
  };

  const resetFilteredView = () => {
    setSelectedResponseId("");
    if (selectedFormId) {
      setResponsePageByForm((current) => ({
        ...current,
        [selectedFormId]: 0,
      }));
    }
  };

  const updateSearchQuery = (query) => {
    setSearchQuery(query);
    resetFilteredView();
  };

  const setSelectedPage = (page) => {
    if (!builderProjectId || !selectedFormId || responsesLoading) return;
    setResponsePageByForm((current) => ({
      ...current,
      [selectedFormId]: Math.max(0, page),
    }));
  };

  const toggleSelectedField = (fieldId) => {
    resetFilteredView();
    setSelectedFieldIds((current) =>
      current.includes(fieldId) ? current.filter((id) => id !== fieldId) : [...current, fieldId]
    );
  };

  const toggleSelectedStatus = (status) => {
    const normalized = normalizeStatus(status);
    resetFilteredView();
    setSelectedStatuses((current) =>
      current.some((item) => normalizeStatus(item) === normalized)
        ? current.filter((item) => normalizeStatus(item) !== normalized)
        : [...current, status]
    );
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

      setBackendResponsesByForm((current) => {
        const nextResponses = (current[selectedFormId] || []).map((submission) =>
          submission.id === submissionId
            ? {
                ...normalizedSubmission,
                submittedBy:
                  updatedSubmission?.submitted_by || updatedSubmission?.submittedBy
                    ? normalizedSubmission.submittedBy
                    : submission.submittedBy,
              }
            : submission
        );

        if (selectedPagination) {
          writeResponsesCache(
            selectedCacheKey,
            nextResponses,
            selectedPagination
          );
        }

        return {
          ...current,
          [selectedFormId]: nextResponses,
        };
      });
    } catch (error) {
      showToast?.(error?.message || t.updateStatusFailed);
    } finally {
      setStatusUpdatingById((current) => ({ ...current, [submissionId]: false }));
    }
  };

  const updateResponseRecord = async (recordId, answers) => {
    if (!builderProjectId || !selectedFormId || !recordId) return false;
    setRecordMutatingById((current) => ({ ...current, [recordId]: "updating" }));

    try {
      const updatedRecord = await updateBuilderFormRecord(
        builderProjectId,
        recordId,
        answers,
        { incomplete: responseView === "incomplete" }
      );
      const normalizedRecord = normalizeBackendResponse(updatedRecord);

      setBackendResponsesByForm((current) => {
        const nextResponses = (current[selectedFormId] || []).map((record) =>
          record.id === recordId
            ? {
                ...normalizedRecord,
                submittedBy:
                  updatedRecord?.submitted_by || updatedRecord?.submittedBy
                    ? normalizedRecord.submittedBy
                    : record.submittedBy,
              }
            : record
        );
        if (selectedPagination) {
          writeResponsesCache(selectedCacheKey, nextResponses, selectedPagination);
        }
        return { ...current, [selectedFormId]: nextResponses };
      });
      showToast?.(t.recordUpdated);
      return true;
    } catch (error) {
      showToast?.(error?.message || t.recordUpdateFailed);
      return false;
    } finally {
      setRecordMutatingById((current) => ({ ...current, [recordId]: "" }));
    }
  };

  const deleteResponseRecord = async (recordId) => {
    if (!builderProjectId || !selectedFormId || !recordId) return false;
    setRecordMutatingById((current) => ({ ...current, [recordId]: "deleting" }));

    try {
      await deleteBuilderFormRecord(
        builderProjectId,
        recordId,
        { incomplete: responseView === "incomplete" }
      );

      const remainingCount = responses.filter(
        (record) => record.id !== recordId
      ).length;
      const nextPagination = selectedPagination
        ? {
            ...selectedPagination,
            count: Math.max(0, Number(selectedPagination.count || 0) - 1),
          }
        : selectedPagination;

      setBackendResponsesByForm((current) => {
        const nextResponses = (current[selectedFormId] || []).filter(
          (record) => record.id !== recordId
        );
        if (nextPagination) {
          writeResponsesCache(selectedCacheKey, nextResponses, nextPagination);
        }
        return { ...current, [selectedFormId]: nextResponses };
      });
      if (nextPagination) {
        setBackendPaginationByForm((current) => ({
          ...current,
          [selectedFormId]: nextPagination,
        }));
      }
      setSelectedResponseId("");
      if (remainingCount === 0 && selectedPage > 0) {
        setResponsePageByForm((current) => ({
          ...current,
          [selectedFormId]: selectedPage - 1,
        }));
      }
      showToast?.(t.recordDeleted);
      return true;
    } catch (error) {
      showToast?.(error?.message || t.recordDeleteFailed);
      return false;
    } finally {
      setRecordMutatingById((current) => ({ ...current, [recordId]: "" }));
    }
  };

  const clearFilters = () => {
    resetFilteredView();
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
    setSearchQuery: updateSearchQuery,
    selectedFieldIds,
    selectedFieldSet,
    toggleSelectedField,
    selectedStatuses,
    selectedStatusSet,
    dynamicStatusOptions,
    toggleSelectedStatus,
    clearFilters,
    hasFilters: Boolean(searchQuery || selectedFieldIds.length > 0 || selectedStatuses.length > 0),
    statusUpdatingById,
    updateSubmissionStatus,
    recordMutatingById,
    updateResponseRecord,
    deleteResponseRecord,
  };
}
