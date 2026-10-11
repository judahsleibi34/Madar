export const submissionSchemaKey = row => `${row.form_id}:${row.version}`;
export const submissionFields = schema => schema?.sections?.flatMap(section => section.fields) || [];
export function formatSubmissionAnswer(value) {
  if (value === undefined || value === null || value === '') return '—';
  if (Array.isArray(value)) return value.length ? value.join(', ') : '—';
  if (typeof value === 'object') return value.name || '—';
  return String(value);
}

export const submissionFieldKey = field => JSON.stringify([field.id, field.label, field.type]);
export function presentationResponse(row, fields, label) {
  return {...row, createdAt:row.submitted_at, status:label(row.read_at ? 'read' : 'unread'), submittedBy:{name:row.user_id ? label('member') : label('guest'),role:row.user_id ? label('member') : label('guest')}, answers:{...row.answers,...Object.fromEntries(fields.map(field => [submissionFieldKey(field),row.answers?.[field.id]]))}};
}
