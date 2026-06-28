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
  clearSelectedFields,
  dynamicStatusOptions,
  selectedStatusSet,
  toggleSelectedStatus,
  clearSelectedStatuses,
  clearFilters,
  hasFilters,
}) {
  return (
    <aside className="results-form-list">
      <div className="results-panel-title">
        <h3>{t.chooseForm}</h3>
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
            <h3>{t.searchData}</h3>
            <p>{t.searchDataText}</p>
          </div>

          <label className="responses-search-field">
            <span>{t.search}</span>
            <input
              type="search"
              value={searchQuery}
              placeholder={t.searchPlaceholder}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </label>

          <div className="responses-checkbox-filter">
            <div className="responses-filter-heading">
              <span>{t.searchIn}</span>
              <button type="button" onClick={clearSelectedFields}>
                {t.allFields}
              </button>
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
              <button type="button" onClick={clearSelectedStatuses}>
                {t.allStatuses}
              </button>
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
