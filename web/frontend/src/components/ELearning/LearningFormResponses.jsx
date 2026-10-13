import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import useAcademyCapabilities from "../../hooks/useAcademyCapabilities";
import { learningFormsApi } from "./learningFormsApi";
import { OwnerPage, OwnerState } from "./OwnerUI";
import ResponsesHeader from "../PageBuilder/responses/components/ResponsesHeader";
import ResponsesSummary from "../PageBuilder/responses/components/ResponsesSummary";
import ResponsesSidebar from "../PageBuilder/responses/components/ResponsesSidebar";
import ResponsesToolbar from "../PageBuilder/responses/components/ResponsesToolbar";
import ResponsesDataBrowser from "../PageBuilder/responses/components/ResponsesDataBrowser";
import {openResponsesSpreadsheetTab} from "../PageBuilder/responses/utils/openResponsesSpreadsheetTab";
import {hasAnswerValue} from "../PageBuilder/responses/utils/responsesUtils";
import {learningResponsesContent} from "./learningFormResponsesContent";
import LearningSubmissionReview from "./LearningSubmissionReview";
import "../../styles/admin/PageBuilder/data-pages.css";
import "../../styles/admin/PageBuilder/incomplete-drafts.css";
import "../../styles/admin/PageBuilder/responses-spreadsheet-actions.css";
import "../../styles/admin/PageBuilder/response-record-actions.css";
import "../../styles/learning-form-responses.css";
import LearningFormSubmissionTables, {SubmissionAnswer} from "./LearningFormSubmissionTables";
import {submissionSchemaKey, submissionFields, formatSubmissionAnswer, presentationResponse, submissionFieldKey} from "./learningFormSubmissionData";
export default function LearningFormResponses({
  user
}) {
  const access = useAcademyCapabilities(user),
    {
      t, i18n
    } = useTranslation('dashboard'),
    label = k => t(`elearning.forms.${k}`);
  const [params, setParams] = useSearchParams(),
    [formResult, setForms] = useState(null),
    [selectedId, setSelectedId] = useState(null),
    [view, setView] = useState("both"),
    [notice,setNotice] = useState(""),
    [result, setData] = useState(null),
    [failure, setFailure] = useState(null),
    [formsError, setFormsError] = useState(false),
    [definitions, setDefinitions] = useState(new Map()),
    [page, setPage] = useState(0),
    [revision, setRevision] = useState(0);
  const query = params.toString();
  const identity = `${user?.tenant_id}:${user?.id}`;
  const requestKey = `${identity}:${query}:${page}:${revision}`;
  const forms = formResult?.identity === identity ? formResult.items : [];
  const content = learningResponsesContent(i18n.language);
  const data = result?.requestKey === requestKey ? result.data : null;
  const error = failure === requestKey;
  const schemaCache = useRef({identity:null, definitions:new Map()});
  useEffect(() => {
    let active = true;
    learningFormsApi().then(v => {
      if (active) {setForms({identity,items:v.items || []}); setFormsError(false);}
    }).catch(() => {
      if (active) setFormsError(true);
    });
    return () => {
      active = false;
    };
  }, [revision, identity]);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const value = await learningFormsApi(`/responses?${query}&offset=${page * 50}`);
        // Fetch one immutable schema per form/version, never today's definition
        // for historical answers. Reuse the existing tenant-guarded detail API.
        const definitionCache = new Map(schemaCache.current.identity === identity ? schemaCache.current.definitions : []);
        const missing = new Map();
        for (const row of value.items) if (!definitionCache.has(submissionSchemaKey(row))) missing.set(submissionSchemaKey(row), row);
        const entries = [...missing];
        for (let offset = 0; offset < entries.length && active; offset += 4) {
          const results = await Promise.all(entries.slice(offset, offset + 4).map(async ([key, row]) => {
            const detail = await learningFormsApi(`/responses/${row.id}`);
            if (!detail.definition?.schema?.sections) throw new Error('Historical schema unavailable');
            return [key, detail.definition];
          }));
          if (active) for (const [key, definition] of results) definitionCache.set(key, definition);
        }
        if (active) {schemaCache.current = {identity,definitions:definitionCache}; setDefinitions(definitionCache); setData({requestKey,data:value});}
      } catch {if (active) setFailure(requestKey);}
    }
    void load();
    return () => {active = false;};
  }, [query, page, revision, identity, requestKey]);
  function filter(k, v) {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);else next.delete(k);
    if (k === "form_id") next.delete("opportunity_id");
    setParams(next);
    setPage(0);
  }
  const allForms = forms.map(form => ({...form,title:form.name || form.schema?.title}));
  const selectedForm = allForms.find(form => form.id === params.get('form_id')) || {id:'',title:content.all};
  const rows = data?.items || [];
  const displayLabel = key => key === 'member' ? t('elearning.ui.member') : label(key);
  const responses = rows.map(row => presentationResponse(row,submissionFields(definitions.get(submissionSchemaKey(row))?.schema),displayLabel));
  const selectedResponse = responses.find(row => row.id === selectedId);
  const detailFields = selectedResponse ? submissionFields(definitions.get(submissionSchemaKey(selectedResponse))?.schema) : [];
  const columns = new Map();
  rows.forEach(row => submissionFields(definitions.get(submissionSchemaKey(row))?.schema).forEach(field => columns.set(submissionFieldKey(field),{...field,id:submissionFieldKey(field)})));
  const fields = [...columns.values()];
  const currentSchema = form => form.schema || definitions.get(submissionSchemaKey({form_id:form.id,version:form.version}))?.schema;
  const summaryFields = selectedForm.id && currentSchema(selectedForm) ? submissionFields(currentSchema(selectedForm)) : fields;
  let cellCount = 0, answered = 0;
  rows.forEach(row => submissionFields(definitions.get(submissionSchemaKey(row))?.schema).forEach(field => {cellCount++;if(hasAnswerValue(row.answers?.[field.id]))answered++;}));
  const totalResponses = forms.every(form => Number.isFinite(form.responses)) ? forms.reduce((total,form) => total+form.responses,0) : '—';
  const loading = !data && !error && !formsError;
  const reportError = () => setFailure(requestKey);
  function spreadsheet() {
    if(!openResponsesSpreadsheetTab({form:selectedForm,fields,responses,formatSavedValue:formatSubmissionAnswer,isQuiz:false,language:i18n.language,direction:i18n.dir(),labels:{...content,spreadsheetSubtitle:`${content.spreadsheetSubtitle} · ${content.page} ${page+1}`}}))setNotice(content.spreadsheetPopupBlocked);
  }
  return <OwnerPage><div className="page-builder elearning-forms-workspace"><div className="workspace-page responses-results-page" dir={i18n.dir()}>
    <ResponsesHeader t={content}/>
    <ResponsesSummary t={content} allForms={allForms} totalResponses={totalResponses} fields={summaryFields} completionRate={cellCount ? Math.round(answered/cellCount*100) : 0}/>
    <div className="results-layout">
      <ResponsesSidebar t={content} allForms={allForms} selectedForm={selectedForm} selectForm={id => filter('form_id',id)} emptyOption={content.all} getResponseCount={form => form.responses ?? '—'} getFieldCount={form => currentSchema(form) ? submissionFields(currentSchema(form)).length : '—'} getFormFields={form => submissionFields(currentSchema(form))} searchQuery={params.get('search') || ''} setSearchQuery={value => filter('search',value)} showFieldFilters={false} fields={fields} dynamicStatusOptions={[label('unread')]} selectedStatusSet={new Set(params.get('unread') === 'true' ? [label('unread').toLowerCase()] : [])} toggleSelectedStatus={() => filter('unread',params.get('unread') === 'true' ? '' : 'true')} clearFilters={() => {setParams({});setPage(0);}} hasFilters={query.length > 0}/>
      <section className="results-table-card">
        <ResponsesToolbar t={content} responseView="completed" setResponseView={() => {}} views={[["completed","completedTab"]]} settingsEnabled={false} data={{selectedForm,hasBackendPagination:true,selectedPage:page,setSelectedPage:setPage,hasPreviousPage:page>0,hasNextPage:data?.has_more,responsesLoading:loading,refreshResponses:() => setRevision(value => value+1),displayedResponses:responses}}/>
        <p className="learning-response-lifecycle">{content.noDrafts}</p>
        {params.has('opportunity_id') && <p role="status">{t('elearning.exchange.filtered_applications')} <button onClick={() => filter('opportunity_id','')}>{t('elearning.exchange.clear_filter')}</button></p>}
        <div className="learning-response-controls">
          <label>{content.display}<select value={view} onChange={event => setView(event.target.value)}><option value="both">{content.combinedView}</option><option value="table">{content.tableView}</option><option value="list">{content.listView}</option></select></label>
          <label>{label('identity')}<select value={params.get('identity') || ''} onChange={event => filter('identity',event.target.value)}><option value="">{label('all')}</option><option value="guest">{label('guest')}</option><option value="authenticated">{t('elearning.ui.member')}</option></select></label>
          {['date_from','date_to'].map(key => <label key={key}>{label(key)}<input type="datetime-local" value={params.get(key) ? new Date(new Date(params.get(key)).getTime()-new Date(params.get(key)).getTimezoneOffset()*60000).toISOString().slice(0,16) : ''} onChange={event => filter(key,event.target.value ? new Date(event.target.value).toISOString() : '')}/></label>)}
          {access?.capabilities?.reports && <button onClick={() => learningFormsApi(`/responses/export?${query}`,{download:'learning-form-responses.csv'}).catch(reportError)}>{label('export')}</button>}
        </div>
        {notice && <p role="status">{notice}</p>}
        <OwnerState error={error || formsError} retry={() => { setFormsError(false); setRevision(value => value+1); }}/>
        {!(error || formsError) && <div className={view === 'table' && rows.length ? 'learning-response-detail-only' : ''}><ResponsesDataBrowser t={content} fields={fields} detailFields={detailFields} displayedResponses={responses} responses={responses} responsesLoading={loading} selectedResponse={selectedResponse} selectedOffset={page*50} setSelectedResponseId={setSelectedId} formatSavedValue={formatSubmissionAnswer} readOnly onOpenSpreadsheet={spreadsheet} renderAnswer={(field,value,row) => <SubmissionAnswer field={field} value={value} responseId={row.id} onError={reportError}/>} detailFooter={selectedResponse && <LearningSubmissionReview key={`${identity}:${selectedResponse.id}`} responseId={selectedResponse.id} onSaved={() => {setNotice(t('elearning.saved'));setRevision(value => value+1);}}/>}/></div>}
        {view !== 'list' && data?.items.length > 0 && <LearningFormSubmissionTables data={data} forms={forms} definitions={definitions} query={query} onError={reportError} selectedResponse={selectedResponse} onSelect={setSelectedId}/>}
      </section>
    </div>
  </div></div></OwnerPage>;
}
