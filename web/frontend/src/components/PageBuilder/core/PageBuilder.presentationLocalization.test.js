import { describe, expect, it } from "vitest";
import { localizePresentation } from "./PageBuilder.presentationLocalization";

describe("persisted presentation translations", () => {
  it("translates nested text while preserving identity, routes and references", () => {
    const original = {pages:[{id:"home",slug:"/",name:"Home",localized:{name:{ar:"الرئيسية"},slug:{ar:"/unsafe"}},
      sections:[{elements:[{id:"text",content:"Learn",localized:{content:{ar:"تعلّم"},id:{ar:"forged"}}}]}]}]};
    const arabic=localizePresentation(original,"ar");
    expect(arabic.pages[0]).toMatchObject({id:"home",slug:"/",name:"الرئيسية"});
    expect(arabic.pages[0].sections[0].elements[0]).toMatchObject({id:"text",content:"تعلّم"});
    expect(original.pages[0].name).toBe("Home");
    expect(localizePresentation(original,"en").pages[0].name).toBe("Home");
  });
  it("falls back to authored text when a translation is absent or blank", () => {
    expect(localizePresentation({content:"Speak",localized:{content:{ar:" "}}},"ar").content).toBe("Speak");
  });
  it('shows a persisted standard-inspector English edit without losing Arabic copy',()=>{
    const source={content:'Updated headline',localized:{content:{en:'Previous headline',ar:'عنوان عربي'}}};
    expect(localizePresentation(source,'en').content).toBe('Updated headline');
    expect(localizePresentation(source,'ar').content).toBe('عنوان عربي');
  });
});
