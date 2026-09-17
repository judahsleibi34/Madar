const MINIMUM_VISIBLE_ROWS = 24;

const getColumnLabel = (index) => {
  let value = index + 1;
  let label = "";

  while (value > 0) {
    value -= 1;
    label = String.fromCharCode(65 + (value % 26)) + label;
    value = Math.floor(value / 26);
  }

  return label;
};

const addElement = (documentRef, parent, tagName, className = "", text = "") => {
  const element = documentRef.createElement(tagName);
  if (className) element.className = className;
  if (text !== "") element.textContent = String(text);
  parent.appendChild(element);
  return element;
};

const TAB_STYLES = `
  :root {
    color-scheme: dark;
    font-family: Inter, Poppins, Arial, sans-serif;
    background: #10151b;
    color: #f4f7fb;
  }

  * { box-sizing: border-box; }

  html, body {
    width: 100%;
    height: 100%;
    margin: 0;
    overflow: hidden;
    background: #10151b;
  }

  body {
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr);
  }

  .sheet-header {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 64px;
    padding: 10px 18px;
    border-bottom: 1px solid #34404d;
    background: #171d24;
  }

  .sheet-mark {
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border-radius: 9px;
    background: #9b2f25;
    color: #fff;
    font-size: 18px;
    font-weight: 900;
  }

  .sheet-title {
    display: grid;
    gap: 2px;
    min-width: 0;
  }

  .sheet-title strong {
    overflow: hidden;
    font-size: 15px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sheet-title span {
    color: #9eabb9;
    font-size: 11px;
  }

  .sheet-close {
    min-height: 36px;
    margin-left: auto;
    padding: 8px 16px;
    border: 1px solid #495666;
    border-radius: 10px;
    background: #222b35;
    color: #f4f7fb;
    font: inherit;
    font-size: 12px;
    font-weight: 800;
    cursor: pointer;
  }

  .sheet-close:hover {
    border-color: #b53a2e;
    background: #9b2f25;
  }

  .sheet-toolbar {
    display: flex;
    align-items: center;
    gap: 4px;
    min-height: 42px;
    padding: 6px 14px;
    border-bottom: 1px solid #34404d;
    background: #202832;
  }

  .sheet-tool {
    display: grid;
    place-items: center;
    min-width: 34px;
    height: 28px;
    padding: 0 8px;
    border-radius: 6px;
    color: #b9c3ce;
    font-size: 12px;
    font-weight: 800;
  }

  .sheet-scroll {
    min-width: 0;
    min-height: 0;
    overflow: auto;
  }

  .sheet-grid {
    width: max-content;
    min-width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    table-layout: fixed;
    font-size: 12px;
  }

  .sheet-grid th,
  .sheet-grid td {
    width: 180px;
    min-width: 180px;
    height: 34px;
    padding: 6px 10px;
    overflow: hidden;
    border-right: 1px solid #34404d;
    border-bottom: 1px solid #34404d;
    background: #10151b;
    color: #f4f7fb;
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sheet-grid thead th {
    position: sticky;
    top: 0;
    z-index: 4;
    height: 30px;
    background: #202832;
    color: #9eabb9;
    text-align: center;
    font-size: 11px;
    font-weight: 800;
  }

  .sheet-grid tbody th,
  .sheet-grid .sheet-corner {
    position: sticky;
    left: 0;
    z-index: 3;
    width: 48px;
    min-width: 48px;
    padding: 0;
    background: #202832;
    color: #9eabb9;
    text-align: center;
    font-size: 11px;
    font-weight: 800;
  }

  .sheet-grid .sheet-corner { z-index: 6; }

  .sheet-grid .sheet-field {
    position: sticky;
    top: 30px;
    z-index: 2;
    background: #372321;
    color: #fff;
    font-weight: 900;
  }

  .sheet-grid tr:hover td:not(.sheet-field) { background: #171d24; }

  @media (max-width: 720px) {
    .sheet-header { padding-inline: 10px; }
    .sheet-title span { display: none; }
    .sheet-grid th,
    .sheet-grid td {
      width: 150px;
      min-width: 150px;
    }
  }
`;

export function openResponsesSpreadsheetTab({
  form,
  fields,
  responses,
  formatSavedValue,
  isQuiz,
  labels,
}) {
  const previewWindow = window.open("about:blank", "_blank");
  if (!previewWindow) return false;

  const documentRef = previewWindow.document;
  documentRef.title = String(form?.title || labels.form) + " ? Spreadsheet";
  documentRef.documentElement.lang = "en";
  documentRef.head.replaceChildren();
  documentRef.body.replaceChildren();

  const charset = documentRef.createElement("meta");
  charset.setAttribute("charset", "utf-8");
  documentRef.head.appendChild(charset);

  const viewport = documentRef.createElement("meta");
  viewport.name = "viewport";
  viewport.content = "width=device-width, initial-scale=1";
  documentRef.head.appendChild(viewport);

  const style = documentRef.createElement("style");
  style.textContent = TAB_STYLES;
  documentRef.head.appendChild(style);

  const header = addElement(documentRef, documentRef.body, "header", "sheet-header");
  addElement(documentRef, header, "div", "sheet-mark", "M");
  const title = addElement(documentRef, header, "div", "sheet-title");
  addElement(documentRef, title, "strong", "", form?.title || labels.form);
  addElement(documentRef, title, "span", "", labels.spreadsheetSubtitle);
  const closeButton = addElement(documentRef, header, "button", "sheet-close", labels.closeSpreadsheet);
  closeButton.type = "button";
  closeButton.addEventListener("click", () => previewWindow.close());

  const toolbar = addElement(documentRef, documentRef.body, "div", "sheet-toolbar");
  ["100%", "B", "I", "123", "?"].forEach((tool) => {
    addElement(documentRef, toolbar, "span", "sheet-tool", tool);
  });

  const scroll = addElement(documentRef, documentRef.body, "div", "sheet-scroll");
  const table = addElement(documentRef, scroll, "table", "sheet-grid");
  const tableHead = addElement(documentRef, table, "thead");
  const lettersRow = addElement(documentRef, tableHead, "tr");
  addElement(documentRef, lettersRow, "th", "sheet-corner");

  const headers = [labels.status, labels.created, labels.submittedBy];
  if (isQuiz) headers.push(labels.score);
  headers.push(...fields.map((field) => field.label));

  headers.forEach((headerLabel, index) => {
    const cell = addElement(documentRef, lettersRow, "th", "", getColumnLabel(index));
    cell.title = String(headerLabel || "");
  });

  const responseRows = responses.map((response) => {
    const row = [
      response.status || labels.newStatus,
      response.createdAt ? new Date(response.createdAt).toLocaleString() : "",
      response.submittedBy?.email || response.submittedBy?.name || labels.guestSubmitter,
    ];
    if (isQuiz) row.push(response.quiz?.score ?? "");
    row.push(...fields.map((field) => formatSavedValue(response.answers?.[field.id]) || ""));
    return row;
  });

  const rows = [
    headers,
    ...responseRows,
    ...Array.from(
      { length: Math.max(0, MINIMUM_VISIBLE_ROWS - responseRows.length) },
      () => Array(headers.length).fill("")
    ),
  ];

  const tableBody = addElement(documentRef, table, "tbody");
  rows.forEach((row, rowIndex) => {
    const tableRow = addElement(documentRef, tableBody, "tr");
    addElement(documentRef, tableRow, "th", "", rowIndex + 1);

    headers.forEach((headerLabel, columnIndex) => {
      const value = row[columnIndex] ?? "";
      const cell = addElement(
        documentRef,
        tableRow,
        "td",
        rowIndex === 0 ? "sheet-field" : "",
        value
      );
      cell.title = String(value);
      cell.dataset.column = String(headerLabel || "");
    });
  });

  previewWindow.opener = null;
  previewWindow.focus();
  return true;
}
