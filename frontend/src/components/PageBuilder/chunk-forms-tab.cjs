const fs = require("fs");
const path = "PageBuilder.jsx";

let source = fs.readFileSync(path, "utf8");

const importLine = 'import { FormsTab } from "./tabs";\n';

if (!source.includes(importLine.trim())) {
  source = source.replace(
    'import PageBuilderWorkflowsTab from "./PageBuilderWorkflowsTab";\n',
    'import PageBuilderWorkflowsTab from "./PageBuilderWorkflowsTab";\n' + importLine
  );
}

const start = source.indexOf("  const renderFormsTab = () => {");
const end = source.indexOf("  const renderWorkflowsTab = () =>", start);

if (start === -1) {
  throw new Error("Could not find renderFormsTab start.");
}

if (end === -1) {
  throw new Error("Could not find renderWorkflowsTab after renderFormsTab.");
}

const replacement = `  const renderFormsTab = () => (
    <FormsTab
      project={project}
      activeForm={activeForm}
      fieldTypes={fieldTypes}
      selected={selected}
      selectForm={selectForm}
      selectPage={selectPage}
      setActiveTab={setActiveTab}
      setDesignPanel={setDesignPanel}
      setSelected={setSelected}
      addForm={addForm}
      addFormSection={addFormSection}
      addFieldToForm={addFieldToForm}
      updateActiveForm={updateActiveForm}
      updateActiveFormQuiz={updateActiveFormQuiz}
      updateFormField={updateFormField}
      updateFormSection={updateFormSection}
      renderQuizAnswerKeyEditor={renderQuizAnswerKeyEditor}
      moveFormField={moveFormField}
      duplicateFormField={duplicateFormField}
      deleteFormField={deleteFormField}
      deleteFormSection={deleteFormSection}
      getFormFields={getFormFields}
      getFormSections={getFormSections}
      getQuizSettings={getQuizSettings}
      getFormPlacements={getFormPlacements}
      addConnectedFormSectionToPage={addConnectedFormSectionToPage}
      renderConnectedForm={renderConnectedForm}
      quizOptionsOpen={quizOptionsOpen}
      setQuizOptionsOpen={setQuizOptionsOpen}
    />
  );

`;

source = source.slice(0, start) + replacement + source.slice(end);

fs.writeFileSync(path, source);
console.log("Chunked FormsTab out of PageBuilder.jsx");
