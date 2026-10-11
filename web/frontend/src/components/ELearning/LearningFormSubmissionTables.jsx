import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ResponsesTable from '../PageBuilder/responses/components/ResponsesTable';
import { learningFormsApi } from './learningFormsApi';
import { learningResponsesContent } from './learningFormResponsesContent';
import {submissionSchemaKey, submissionFields, formatSubmissionAnswer, submissionFieldKey, presentationResponse} from './learningFormSubmissionData';
export function SubmissionAnswer({field, value, responseId, onError}) {
  if (field.type === 'file' && value?.id && value?.name) return <button type="button" className="ecommerce-secondary-button elearning-submission-download" onClick={event => {event.stopPropagation(); learningFormsApi(`/responses/${responseId}/files/${value.id}`, {download:value.name}).catch(onError);}}>{value.name}</button>;
  return <span className="elearning-submission-answer" dir="auto">{formatSubmissionAnswer(value)}</span>;
}
export default function LearningFormSubmissionTables({data, forms, definitions, query, onError, selectedResponse, onSelect = () => {}}) {
  const {t, i18n} = useTranslation('dashboard');
  const label = key => key === 'member' ? t('elearning.ui.member') : t(`elearning.forms.${key}`);
  const content = learningResponsesContent(i18n.language);
  const groups = new Map();
  for (const row of data.items) {
    const definition = definitions.get(submissionSchemaKey(row));
    const group = groups.get(row.form_id) || {rows:[],columns:new Map(),name:forms.find(form => form.id === row.form_id)?.name || definition.name || definition.schema.title};
    const historicalFields = submissionFields(definition.schema);
    group.rows.push(presentationResponse(row,historicalFields,label));
    for (const field of historicalFields) group.columns.set(submissionFieldKey(field), field);
    groups.set(row.form_id, group);
  }
  return <div className="elearning-submission-tables">{[...groups].map(([formId, group]) => {
    const labels = new Map();
    const fields = [...group.columns].map(([key, field]) => {
      const occurrence = (labels.get(field.label) || 0) + 1; labels.set(field.label, occurrence);
      return {id:key, source:field, label:occurrence > 1 ? `${field.label} (${occurrence})` : field.label};
    });
    return <section key={formId} aria-label={group.name} className="elearning-submission-table-section"><h2>{group.name}</h2><ResponsesTable t={content} caption={`${label('all_responses')} · ${group.name}`} fields={fields} displayedResponses={group.rows} responses={group.rows} selectedResponse={selectedResponse} setSelectedResponseId={onSelect} formatSavedValue={formatSubmissionAnswer} extraHeaders={[label('version')]} renderExtraCells={row => <td>{row.version}</td>} trailingHeaders={[t('elearning.ui.actions')]} renderTrailingCells={row => <td><button type="button" onClick={() => onSelect(row.id)}>{content.submissionDetails}</button><Link className="ecommerce-secondary-button" onClick={event => event.stopPropagation()} to={`/e-learning/forms/responses/${row.id}${query ? `?${query}` : ''}`}>{label('open')}</Link></td>} renderAnswer={(field,value,row) => <SubmissionAnswer field={field.source} value={value} responseId={row.id} onError={onError}/>}/></section>;
  })}</div>;
}
