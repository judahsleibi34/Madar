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
  const [refreshKey, setRefreshKey] = useState(0);
  const selectedPage = responsePageByForm[selectedFormId] || 0;
  const selectedOffset = selectedPage * RESPONSE_PAGE_SIZE;
  const selectedCacheKey =
    builderProjectId && selectedFormId
      ? createResponsesCacheKey({
          userScope,
          projectId: builderProjectId,
          formId: selectedFormId,
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
      fetchBuilderFormSubmissionsPage(builderProjectId, {
        form_id: selectedFormId,
        limit: RESPONSE_PAGE_SIZE,
        offset: selectedOffset,
        user_id: user?.id,
      })
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
    return deferEffectStateUpdate(() => {
      setSelectedResponseId("");
      setSelectedFieldIds([]);
      setSearchQuery("");
      setSelectedStatuses([]);
    });
  }, [selectedFormId]);

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
          submission.id === submissionId ? normalizedSubmission : submission
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
  };
}
