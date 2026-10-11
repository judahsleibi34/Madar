// Pure ordered Builder equality/show/hide model; no persistence or project access.
export function isFormFieldVisible(form, field, answers, normalize = value => value) {
  return (form.logicRules || []).filter(rule => rule.targetFieldId === field.id).reduce((visible, rule) => {
    const matched = String(normalize(answers[rule.sourceFieldId]) ?? "").trim() === String(rule.value ?? "").trim();
    if (rule.action === "show") return matched;
    if (rule.action === "hide") return matched ? false : visible;
    return visible;
  }, true);
}
export function visibleLearningFields(schema, answers) {
  const values = {}, visible = [];
  for (const field of schema.sections.flatMap(section => section.fields)) {
    if (!isFormFieldVisible(schema, field, values)) continue;
    visible.push(field);values[field.id] = answers[field.id] ?? field.defaultValue ?? "";
  }
  return visible;
}
