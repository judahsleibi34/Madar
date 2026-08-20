import { FilePlus2, Plus } from "lucide-react";

import { getFormThemeVars } from "../../core/PageBuilder.theme";
import FormButton from "./FormButton";

export default function FormsEmptyState({ addForm, copy, project }) {
  return (
    <div className="workspace-page forms-workbench forms-simple-workbench" style={getFormThemeVars(project.theme)}>
      <section className="forms-empty-state">
        <FilePlus2 size={34} aria-hidden="true" />
        <h2>{copy.messages.createFirstFormTitle}</h2>
        <p>{copy.messages.createFirstFormBody}</p>
        <FormButton variant="primary" icon={Plus} onClick={addForm}>
          {copy.messages.newForm}
        </FormButton>
      </section>
    </div>
  );
}
