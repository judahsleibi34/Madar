export function addCompletedFormPage(completedPages = [], pageIndex) {
  return Array.from(new Set([...completedPages, pageIndex])).sort((a, b) => a - b);
}

export function completedFormPagesBefore(pageIndex) {
  return Array.from({ length: Math.max(0, Number(pageIndex) || 0) }, (_, index) => index);
}

export function getFormPageNavigationItems(pageCount, currentPageIndex, completedPages = []) {
  const completed = new Set(completedPages);
  return Array.from({ length: Math.max(0, Number(pageCount) || 0) }, (_, index) => ({
    index,
    isCurrent: index === currentPageIndex,
    isCompleted: completed.has(index),
    isDisabled: index !== currentPageIndex && !completed.has(index),
  }));
}