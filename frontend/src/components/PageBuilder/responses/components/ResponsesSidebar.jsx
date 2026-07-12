import { normalizeStatus } from "../utils/responsesUtils";

export default function ResponsesSidebar({
  t,
  allForms,
  selectedForm,
  selectForm,
  getDisplayResponsesForForm,
  getFormFields,
  searchQuery,
  setSearchQuery,
  fields,
  selectedFieldSet,
  toggleSelectedField,
  dynamicStatusOptions,
  selectedStatusSet,
  toggleSelectedStatus,
  clearFilters,
  hasFilters,
}) {
  const hasSearchQuery = searchQuery.trim().length > 0;

  return (
    <aside className="results-form-list">
      <div className="results-panel-title">
        <h2>{t.chooseForm}</h2>
        <p>{t.selectForm}</p>
      </div>

      <label className="responses-form-picker">
        <span>{t.form}</span>
        <select
          value={selectedForm?.id || ""}
          onChange={(event) => selectForm(event.target.value)}
        >
          {allForms.map((form) => (
            <option key={form.id} value={form.id}>
              {form.title}
            </option>
          ))}
        </select>
      </label>

      <div className="results-form-list-scroll">
        {allForms.map((form) => {
          const isActive = selectedForm?.id === form.id;
          const count = getDisplayResponsesForForm(form).length;
          const formFields = getFormFields(form);

          return (
            <button
              key={form.id}
              type="button"
              className={isActive ? "active" : ""}
              onClick={() => selectForm(form.id)}
            >
              <strong>{form.title}</strong>
              <span>
                {count} {count === 1 ? t.submission : t.submissionsLower} /{" "}
                {formFields.length} {formFields.length === 1 ? t.field : t.fields}
              </span>
            </button>
          );
        })}
      </div>

      {selectedForm && (
        <div className="responses-search-panel">
          <div className="results-panel-title">
            <h2>{t.searchData}</h2>
            <p>{t.searchDataText}</p>
          </div>

          <label className="responses-search-field">
            <span>{t.search}</span>
            <div className="responses-search-input-wrap">
              <input
                type="search"
                value={searchQuery}
                placeholder={t.searchPlaceholder}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
              {hasSearchQuery ? (
                <button
                  type="button"
                  className="responses-search-reset"
                  onClick={() => setSearchQuery("")}
                  aria-label={t.clearSearch}
                >
                  x
                </button>
              ) : null}
            </div>
          </label>

          <div className="responses-checkbox-filter">
            <div className="responses-filter-heading">
              <span>{t.searchIn}</span>
            </div>
            <div className="responses-checkbox-list">
              {fields.map((field) => (
                <label key={field.id}>
                  <input
                    type="checkbox"
                    checked={selectedFieldSet.has(field.id)}
                    onChange={() => toggleSelectedField(field.id)}
                  />
                  <span>{field.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="responses-checkbox-filter">
            <div className="responses-filter-heading">
              <span>{t.statusFilter}</span>
            </div>
            <div className="responses-checkbox-list compact">
              {dynamicStatusOptions.map((status) => (
                <label key={status}>
                  <input
                    type="checkbox"
                    checked={selectedStatusSet.has(normalizeStatus(status))}
                    onChange={() => toggleSelectedStatus(status)}
                  />
                  <span>{status}</span>
                </label>
              ))}
            </div>
          </div>

          {hasFilters && (
            <button type="button" className="responses-clear-search" onClick={clearFilters}>
              {t.clearSearch}
            </button>
          )}
        </div>
      )}
    </aside>
  );
}
