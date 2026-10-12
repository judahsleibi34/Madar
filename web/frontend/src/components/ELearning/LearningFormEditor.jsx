import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { createField } from "../PageBuilder/core/PageBuilder.factories";
import FormsTab from "../PageBuilder/tabs/FormsTab";
import { learningFormsApi } from "./learningFormsApi";
import LearningFormRenderer from "./LearningFormRenderer";
import { OwnerHeader, OwnerPage, OwnerState } from "./OwnerUI";
import "../../styles/admin/PageBuilder/app.css";
import "../../styles/admin/PageBuilder/forms.css";
import "../../styles/admin/PageBuilder/modals.css";
import "../../styles/admin/PageBuilder/theme-consistency.css";
import "../../styles/admin/PageBuilder/button-colors.css";
import "../../styles/learning-form-editor.css";

const types = ['shortText', 'paragraph', 'email', 'phone', 'number', 'dropdown', 'radio', 'checkboxes', 'date', 'file'];
const features = {fieldTypes: types, import: false, templates: false, localization: false, theme: false, richText: false, quiz: false, placement: false, pageDescription: false};
const fieldKeys = ['id', 'type', 'label', 'required', 'helpText', 'placeholder', 'options', 'defaultValue', 'validation', 'maxFileSizeMb'];
const schemaKeys = ['title', 'description', 'submitLabel', 'successMessage', 'access', 'notifyOwner', 'confirmSubmitter', 'pageMode', 'logicRules'];
const pick = (value, keys) => Object.fromEntries(keys.filter(key => value[key] !== undefined).map(key => [key, value[key]]));
const fieldFor = type => pick(createField('Question', type), fieldKeys);
const fresh = () => ({name: '', status: 'inactive', schema: {title: '', description: '', submitLabel: '', successMessage: '', access: 'public', notifyOwner: true, confirmSubmitter: false, pageMode: 'paged', sections: [{id: crypto.randomUUID(), title: '', fields: [fieldFor('shortText')]}], logicRules: []}});
// Builder localization helpers produce editor metadata. This adapter extracts only
// the current text into E-Learning's supported schema, never Builder storage.
const plain = (value, key, lang) => value.localized?.[key]?.[lang] ?? value[key];

export default function LearningFormEditor() {
  const {id} = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const {t, i18n} = useTranslation('dashboard');
  const label = key => t(`elearning.forms.${key}`);
  const ui = key => t(`elearning.ui.${key}`);
  const lang = i18n.language.startsWith('ar') ? 'ar' : 'en';
  const [draft, setDraft] = useState(() => {
    const value = fresh();
    value.schema.sections[0].fields[0].label = label('shortText');
    return value;
  });
  const [library, setLibrary] = useState([]);
  const [themeMode, setThemeMode] = useState(() => document.documentElement.dataset.theme || 'light');
  useEffect(() => {
    const changed = () => setThemeMode(document.documentElement.dataset.theme || 'light');
    window.addEventListener('madar-theme-change', changed);
    return () => window.removeEventListener('madar-theme-change', changed);
  }, []);
  const [loading, setLoading] = useState(Boolean(id));
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [selected, setSelected] = useState({type: 'form', id: id || 'new'});
  const [details, setDetails] = useState({});
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [preview, setPreview] = useState(false);
  const [device, setDevice] = useState('desktop');
  const editorRef = useRef(null);
  const returnTo = new URLSearchParams(location.search).get('returnTo');
  const safeReturn = (returnTo?.startsWith('/e-learning/landing-page/projects/') || /^\/e-learning\/exchange-opportunities\/(?:new|[0-9a-f-]{36}\/edit)$/.test(returnTo || '')) && !returnTo.includes('://') ? returnTo : null;
  const suffix = safeReturn ? `?returnTo=${encodeURIComponent(safeReturn)}` : '';

  useEffect(() => {
    let active = true;
    learningFormsApi('').then(value => {if (active) setLibrary(value.items || []);}).catch(() => {});
    return () => {active = false;};
  }, [id, saved]);
  useEffect(() => {
    if (!id) return;
    let active = true;
    learningFormsApi(`/${id}`).then(value => {
      if (active) {setDraft(value); setDirty(false); setLoading(false); setError(false);}
    }).catch(() => {if (active) {setError(true); setLoading(false);}});
    return () => {active = false;};
  }, [id, attempt]);

  const schema = draft.schema;
  const fields = schema.sections.flatMap(section => section.fields);
  const update = patch => {setDraft(value => ({...value, ...patch})); setSaved(false); setDirty(true);};
  const updateSchema = patch => update({schema: {...schema, ...patch}});
  const editorId = draft.id || 'new';
  const activeForm = {
    ...schema, id: editorId, name: draft.name, mode: 'form', responses: [], languageMode: lang,
    sections: schema.sections.map((section, index) => ({...section,
      title: index === 0 ? schema.title : section.title,
      description: index === 0 ? schema.description : '',
      fields: section.fields.map(field => ({...field, showDetailsEditor: details[field.id] ?? Boolean(field.helpText || field.placeholder)}))
    }))
  };
  const project = {forms: [activeForm, ...library.filter(form => form.id !== editorId && form.status !== 'archived').map(form => ({...form, title: form.name}))], theme: {}, pages: [], collections: []};
  const updateActiveForm = updater => {
    const next = updater(activeForm);
    update({name: next.name, schema: {...schema, ...pick(next, schemaKeys),
      ...Object.fromEntries(['title','description','successMessage'].map(key => [key, plain(next, key, lang) || '']))
    }});
  };
  const updateFormField = (fieldId, patch) => {
    if (patch.showDetailsEditor !== undefined) setDetails(value => ({...value, [fieldId]: patch.showDetailsEditor}));
    updateSchema({sections: schema.sections.map(section => ({...section, fields: section.fields.map(field => {
      if (field.id !== fieldId) return field;
      const next = {...field, ...pick(patch, fieldKeys)};
      for (const key of ['label','helpText','placeholder','options']) {
        if (patch.localized?.[key]?.[lang] !== undefined) next[key] = patch.localized[key][lang];
      }
      if (patch.type && patch.type !== field.type) {
        next.defaultValue = ''; next.validation = {};
        next.options = ['dropdown','radio','checkboxes'].includes(patch.type) ? [1,2].map(number => t('elearning.ui.option_number', {number})) : [];
      }
      return next;
    })}))});
  };
  const updateFormSection = (sectionId, patch) => {
    const index = schema.sections.findIndex(section => section.id === sectionId);
    if (index === 0) {updateSchema({...(patch.title !== undefined ? {title: patch.title} : {}), ...(patch.description !== undefined ? {description: patch.description} : {})}); return;}
    updateSchema({sections: schema.sections.map(section => section.id === sectionId ? {...section, ...pick(patch, ['title'])} : section)});
  };
  const addField = (sectionId, type) => {
    if (fields.length >= 100) return;
    const field = fieldFor(type);
    field.label = label(type);
    if (['dropdown','radio','checkboxes'].includes(type)) field.options = [1,2].map(number => t('elearning.ui.option_number', {number}));
    updateSchema({sections: schema.sections.map(section => section.id === sectionId ? {...section, fields: [...section.fields, field]} : section)});
    setSelected({type: 'field', id: field.id});
  };
  const addPage = afterId => {
    if (schema.sections.length >= 10) return;
    const sections = [...schema.sections];
    const index = sections.findIndex(section => section.id === afterId);
    sections.splice(index < 0 ? sections.length : index + 1, 0, {id: crypto.randomUUID(), title: '', fields: []});
    updateSchema({sections});
  };
  const removeFields = ids => updateSchema({sections: schema.sections.map(section => ({...section, fields: section.fields.filter(field => !ids.has(field.id))})), logicRules: schema.logicRules.filter(rule => !ids.has(rule.sourceFieldId) && !ids.has(rule.targetFieldId))});
  const moveField = (fieldId, direction) => {
    updateSchema({sections: schema.sections.map(section => {
      const index = section.fields.findIndex(field => field.id === fieldId);
      const target = index + (direction === 'up' ? -1 : 1);
      if (index < 0 || target < 0 || target >= section.fields.length) return section;
      const next = [...section.fields]; [next[index], next[target]] = [next[target], next[index]];
      return {...section, fields: next};
    })});
  };
  const duplicateField = fieldId => {
    if (fields.length >= 100) return;
    let copy;
    updateSchema({sections: schema.sections.map(section => ({...section, fields: section.fields.flatMap(field => {
      if (field.id !== fieldId) return [field];
      copy = {...field, id: crypto.randomUUID()}; return [field, copy];
    })}))});
    if (copy) setSelected({type: 'field', id: copy.id});
  };
  const deletePage = sectionId => {
    if (schema.sections.length <= 1) return;
    const ids = new Set(schema.sections.find(section => section.id === sectionId)?.fields.map(field => field.id));
    updateSchema({sections: schema.sections.filter(section => section.id !== sectionId), logicRules: schema.logicRules.filter(rule => !ids.has(rule.sourceFieldId) && !ids.has(rule.targetFieldId))});
  };
  const switchForm = nextId => {
    if (nextId === editorId) return;
    if (dirty && !window.confirm(ui('discard_form_changes'))) return;
    navigate(`/e-learning/forms/${nextId}/edit${suffix}`);
  };
  async function save() {
    if (busy || !editorRef.current?.reportValidity()) return false;
    if (!draft.name.trim() || !schema.title.trim() || !fields.length || fields.some(field => !field.label.trim())) {setError(true); return false;}
    setBusy(true); setError(false);
    try {
      const result = await learningFormsApi(draft.id ? `/${draft.id}` : '', {method: draft.id ? 'PUT' : 'POST', body: {name: draft.name, status: draft.status, expected_version: draft.version || 1, schema}});
      setDraft(result); setSaved(true); setDirty(false);
      window.dispatchEvent(new Event('learning-forms-changed'));
      if (!id) navigate(`/e-learning/forms/${result.id}/edit${suffix}`, {replace: true, state:location.state});
      return true;
    } catch {setError(true); return false;} finally {setBusy(false);}
  }
  const settingsFields = <>
    <section className="quiz-settings-section"><h4>{label('access')}</h4><label>{label('access')}<select value={schema.access} onChange={event => updateSchema({access: event.target.value})}>{['public','authenticated','enrolled'].map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label><label>{ui('page_mode')}<select value={schema.pageMode} onChange={event => updateSchema({pageMode: event.target.value})}><option value="paged">{ui('paged')}</option><option value="single">{ui('single')}</option></select></label><label>{label('submitLabel')}<input maxLength={120} value={schema.submitLabel || ''} onChange={event => updateSchema({submitLabel: event.target.value})}/></label></section>
    <section className="quiz-settings-section"><h4>{ui('notifications')}</h4>{['notifyOwner','confirmSubmitter'].map(key => <label className="checkbox-control" key={key}><input type="checkbox" checked={Boolean(schema[key])} onChange={event => updateSchema({[key]: event.target.checked})}/>{label(key)}</label>)}</section>
  </>;
  const renderFieldSettings = field => <details className="learning-field-validation"><summary>{ui('validation')}</summary>
    {!['file','checkboxes'].includes(field.type) && <label>{label('defaultValue')}<input value={field.defaultValue ?? ''} onChange={event => updateFormField(field.id, {defaultValue: event.target.value})}/></label>}
    {['min','max','minLength','maxLength'].filter(key => field.type === 'number' ? ['min','max'].includes(key) : ['shortText','paragraph'].includes(field.type) && key.includes('Length')).map(key => <label key={key}>{label(key)}<input type="number" value={field.validation?.[key] ?? ''} onChange={event => {
      const validation = {...field.validation}; if (event.target.value === '') delete validation[key]; else validation[key] = Number(event.target.value); updateFormField(field.id, {validation});
    }}/></label>)}
    {field.type === 'file' && <label>{label('file_limit')}<input type="number" min={0.1} max={5} step={0.1} value={field.maxFileSizeMb || 5} onChange={event => updateFormField(field.id, {maxFileSizeMb: Number(event.target.value)})}/></label>}
  </details>;
  if (loading || (id && !draft.id)) return <OwnerPage><OwnerHeader title={label('edit')} back={{to:'/e-learning/forms',label:label('manage')}}/><OwnerState loading={loading} error={error} retry={() => setAttempt(value => value + 1)}/></OwnerPage>;
  return <OwnerPage><OwnerHeader title={label(id ? 'edit' : 'create')} back={{to:'/e-learning/forms',label:label('manage')}} actions={<>{safeReturn && <Link className="ecommerce-secondary-button" to={safeReturn} state={safeReturn.includes('exchange-opportunities') ? {exchangeDraft:location.state?.exchangeDraft,selectedForm:id} : undefined}>{safeReturn.includes('exchange-opportunities') ? t('elearning.exchange.return_opportunity') : ui('return_builder')}</Link>}{preview && <button className="ecommerce-secondary-button" onClick={() => setPreview(false)}>{ui('back_to_editor')}</button>}</>}/><OwnerState error={error} message={label('error')}/>{saved && <p role="status">{t('elearning.saved')}</p>}
    {preview ? <section><div className="elearning-course-actions">{['desktop','mobile'].map(value => <button key={value} className="ecommerce-secondary-button" aria-pressed={device === value} onClick={() => setDevice(value)}>{ui(value)}</button>)}</div><p>{ui('preview_help')}</p><div className={`elearning-form-preview ${device === 'mobile' ? 'is-mobile' : ''}`}><LearningFormRenderer key={JSON.stringify(schema)} form={{...draft,version:draft.version || 1}} preview/></div></section> : <form ref={editorRef} className={`learning-builder-editor page-builder theme-${themeMode}`} onSubmit={event => {event.preventDefault(); void save();}}><fieldset disabled={busy}>
      <FormsTab project={project} activeForm={activeForm} fieldTypes={types.map(type => ({id:type,label:label(type)}))} selected={selected} setSelected={setSelected} lang={lang} features={features}
        libraryHelp={ui('builder_forms_help')} responseCount={library.find(form => form.id === draft.id)?.responses ?? 0} editorLabels={{name:label('name'),title:ui('form_title'),fieldType:label('field_type')}} constraints={{required:true,formText:160,fieldText:200,description:4000}}
        selectForm={switchForm} addForm={() => {if (!dirty || window.confirm(ui('discard_form_changes'))) {if (!id) {setDraft(fresh());setDetails({});setDirty(false);setSaved(false);} else navigate(`/e-learning/forms/new${suffix}`);}}}
        updateActiveForm={updateActiveForm} addFieldToForm={addField} addFormSection={addPage} updateFormField={updateFormField} updateFormSection={updateFormSection}
        moveFormField={moveField} duplicateFormField={duplicateField} deleteFormField={fieldId => removeFields(new Set([fieldId]))} deleteFormSection={deletePage}
        getFormFields={form => form.sections.flatMap(section => section.fields)} getFormSections={form => form.sections} getFormPlacements={() => []}
        quizOptionsOpen={settingsOpen} setQuizOptionsOpen={setSettingsOpen} saveProject={save} openFormPreviewPage={() => setPreview(true)} previewWithoutSave
        canAddField={fields.length < 100} canAddPage={schema.sections.length < 10} settingsFields={settingsFields} renderFieldSettings={renderFieldSettings}
        sidebarFields={<label>{label('status')}<select value={draft.status} onChange={event => update({status:event.target.value})}>{['active','inactive','archived'].map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label>}
      />
    </fieldset></form>}
  </OwnerPage>;
}
