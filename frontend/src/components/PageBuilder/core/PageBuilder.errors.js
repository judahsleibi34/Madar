export const isBuilderError = (error, code) => error?.code === code;

export const isBuilderRevisionError = (error) =>
  isBuilderError(error, "project_revision_conflict") ||
  isBuilderError(error, "project_revision_required");

export const getBuilderConflictMessage = (error) => {
  const currentRevision = Number(error?.context?.current_revision);
  const revisionNote = Number.isInteger(currentRevision)
    ? ` The server is now on revision ${currentRevision}.`
    : "";

  return `This site was updated in another tab or session.${revisionNote} Your local edits are still here; review them before reloading.`;
};

const getPageElements = (page) =>
  (page?.sections || []).flatMap((section) => [
    ...(section?.elements || []),
    ...(section?.freeElements || []),
    ...(section?.rows || []).flatMap((row) =>
      (row?.columns || []).flatMap((column) => column?.elements || [])
    ),
  ]);

export const collectProjectIdIssues = (project) => {
  const issues = [];
  const collectCollectionIssues = (items, kind) => {
    const occurrences = new Map();
    (items || []).forEach((item, index) => {
      const id = String(item?.id || "").trim();
      const entry = {
        id,
        occurrence_index: index,
        ...(kind === "page"
          ? { page_id: id, page_name: String(item?.name || item?.title || "Untitled page") }
          : { form_id: id, form_name: String(item?.name || item?.title || "Untitled form") }),
      };
      if (!id) {
        issues.push({ issue_type: `missing_${kind}_id`, occurrences: [entry] });
        return;
      }
      occurrences.set(id, [...(occurrences.get(id) || []), entry]);
    });
    occurrences.forEach((entries, id) => {
      if (entries.length > 1) {
        issues.push({
          issue_type: `duplicate_${kind}_id`,
          duplicate_id: id,
          occurrences: entries,
        });
      }
    });
  };

  collectCollectionIssues(project?.pages, "page");
  collectCollectionIssues(project?.forms, "form");

  const blockOccurrences = new Map();
  (project?.pages || []).forEach((page) => {
    getPageElements(page).forEach((element, occurrenceIndex) => {
      const blockId = String(element?.id || "").trim();
      const entry = {
        page_id: String(page?.id || ""),
        page_name: String(page?.name || page?.title || "Untitled page"),
        block_id: blockId,
        block_type: String(element?.type || "unknown"),
        occurrence_index: occurrenceIndex,
      };
      if (!blockId) {
        issues.push({ issue_type: "missing_block_id", occurrences: [entry] });
        return;
      }
      blockOccurrences.set(blockId, [...(blockOccurrences.get(blockId) || []), entry]);
    });
  });
  blockOccurrences.forEach((occurrences, id) => {
    if (occurrences.length > 1) {
      issues.push({
        issue_type: "duplicate_block_id",
        duplicate_id: id,
        occurrences,
      });
    }
  });

  return issues;
};

export const getProjectIdIssueMessage = (issue) => {
  if (issue?.issue_type === "duplicate_block_id" || issue?.issue_type === "missing_block_id") {
    return "Some blocks have duplicate or missing internal IDs. Save your site to repair them, then try Go Live again.";
  }
  return "This draft contains duplicate or missing internal IDs. Save it to repair them, then try Go Live again.";
};

export const collectFormConnectionIssues = (project) => {
  const formIds = new Set(
    (project?.forms || []).map((form) => String(form?.id || "").trim()).filter(Boolean)
  );

  return (project?.pages || []).flatMap((page) =>
    getPageElements(page)
      .filter((element) => element?.type === "formBlock")
      .map((element) => {
        const formId = String(element.connectedFormId || "").trim();
        if (formId && formIds.has(formId)) return null;
        return {
          issue_type: "orphaned_form_block",
          page_id: String(page?.id || ""),
          page_name: String(page?.name || page?.title || "Untitled page"),
          block_id: String(element?.id || ""),
          block_label: String(element?.name || element?.label || "Form block"),
          form_id: formId,
        };
      })
      .filter(Boolean)
  );
};

export const getFormConnectionIssueMessage = (issue) =>
  `${issue?.block_label || "Form block"} on ${issue?.page_name || "this page"} is not connected to a valid form. Create or select a form, connect this block, or remove the block.`;

export const getFormConnectionFocusTarget = (issue) => ({
  pageId: String(issue?.page_id || ""),
  selection: { type: "element", id: String(issue?.block_id || "") },
});
