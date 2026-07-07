const textEncoder = new TextEncoder();
const DANGEROUS_SPREADSHEET_PREFIXES = new Set(["=", "+", "-", "@", "\t", "\r"]);

export const sanitizeSpreadsheetCell = (value) => {
  if (typeof value !== "string") return value;

  const firstContentCharacter = value.replace(/^ +/, "").charAt(0);
  if (DANGEROUS_SPREADSHEET_PREFIXES.has(firstContentCharacter)) {
    return `'${value}`;
  }

  return value;
};

export const sanitizeSpreadsheetRows = (rows) =>
  rows.map((row) => row.map((value) => sanitizeSpreadsheetCell(value)));

const sanitizeExportName = (value, fallback = "madar-dataset") => {
  const name = String(value || fallback)
    .split(/[\\/]/)
    .pop()
    .replace(/\.[^.]+$/, "")
    .replace(/[^\w.-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  return name || fallback;
};

const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
};

const escapeCsvCell = (value) => {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

const buildCsv = (rows) =>
  rows.map((row) => row.map((value) => escapeCsvCell(value)).join(",")).join("\n");

export const sanitizeCsvForSpreadsheetExport = (csv) => {
  const contents = String(csv || "");
  const withoutBom = contents.charCodeAt(0) === 0xfeff ? contents.slice(1) : contents;
  const rows = parseCsv(withoutBom);

  if (!rows.length) return withoutBom;

  return buildCsv(sanitizeSpreadsheetRows(rows));
};

export const downloadCsv = (csv, filenameBase) => {
  const contents = sanitizeCsvForSpreadsheetExport(csv);
  const prefixedContents = contents.charCodeAt(0) === 0xfeff ? contents : `\uFEFF${contents}`;
  downloadBlob(
    new Blob([prefixedContents], { type: "text/csv;charset=utf-8" }),
    `${sanitizeExportName(filenameBase)}.csv`
  );
};

const parseCsv = (csv) => {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let index = 0; index < csv.length; index += 1) {
    const character = csv[index];
    const nextCharacter = csv[index + 1];

    if (inQuotes) {
      if (character === '"' && nextCharacter === '"') {
        field += '"';
        index += 1;
      } else if (character === '"') {
        inQuotes = false;
      } else {
        field += character;
      }
      continue;
    }

    if (character === '"') {
      inQuotes = true;
    } else if (character === ",") {
      row.push(field);
      field = "";
    } else if (character === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (character !== "\r") {
      field += character;
    }
  }

  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }

  return rows;
};

const escapeXml = (value) =>
  String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const columnName = (index) => {
  let value = index + 1;
  let name = "";

  while (value > 0) {
    const remainder = (value - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    value = Math.floor((value - 1) / 26);
  }

  return name;
};

const buildWorksheetXml = (rows) => {
  const sheetRows = rows
    .map((row, rowIndex) => {
      const cells = row
        .map((value, columnIndex) => {
          const ref = `${columnName(columnIndex)}${rowIndex + 1}`;
          return `<c r="${ref}" t="inlineStr"><is><t>${escapeXml(value)}</t></is></c>`;
        })
        .join("");

      return `<row r="${rowIndex + 1}">${cells}</row>`;
    })
    .join("");

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${sheetRows}</sheetData></worksheet>`;
};

const crcTable = Array.from({ length: 256 }, (_, index) => {
  let value = index;
  for (let bit = 0; bit < 8; bit += 1) {
    value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  }
  return value >>> 0;
});

const crc32 = (bytes) => {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
};

const concatBytes = (chunks) => {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const output = new Uint8Array(length);
  let offset = 0;

  chunks.forEach((chunk) => {
    output.set(chunk, offset);
    offset += chunk.length;
  });

  return output;
};

const writeZipHeader = (length) => {
  const bytes = new Uint8Array(length);
  return {
    bytes,
    view: new DataView(bytes.buffer),
  };
};

const createZip = (files) => {
  const localChunks = [];
  const centralChunks = [];
  let offset = 0;

  files.forEach((file) => {
    const nameBytes = textEncoder.encode(file.name);
    const contents = textEncoder.encode(file.contents);
    const checksum = crc32(contents);

    const local = writeZipHeader(30 + nameBytes.length);
    local.view.setUint32(0, 0x04034b50, true);
    local.view.setUint16(4, 20, true);
    local.view.setUint16(6, 0x0800, true);
    local.view.setUint16(8, 0, true);
    local.view.setUint32(14, checksum, true);
    local.view.setUint32(18, contents.length, true);
    local.view.setUint32(22, contents.length, true);
    local.view.setUint16(26, nameBytes.length, true);
    local.bytes.set(nameBytes, 30);

    localChunks.push(local.bytes, contents);

    const central = writeZipHeader(46 + nameBytes.length);
    central.view.setUint32(0, 0x02014b50, true);
    central.view.setUint16(4, 20, true);
    central.view.setUint16(6, 20, true);
    central.view.setUint16(8, 0x0800, true);
    central.view.setUint16(10, 0, true);
    central.view.setUint32(16, checksum, true);
    central.view.setUint32(20, contents.length, true);
    central.view.setUint32(24, contents.length, true);
    central.view.setUint16(28, nameBytes.length, true);
    central.view.setUint32(42, offset, true);
    central.bytes.set(nameBytes, 46);

    centralChunks.push(central.bytes);
    offset += local.bytes.length + contents.length;
  });

  const centralDirectory = concatBytes(centralChunks);
  const end = writeZipHeader(22);
  end.view.setUint32(0, 0x06054b50, true);
  end.view.setUint16(8, files.length, true);
  end.view.setUint16(10, files.length, true);
  end.view.setUint32(12, centralDirectory.length, true);
  end.view.setUint32(16, offset, true);

  return concatBytes([...localChunks, centralDirectory, end.bytes]);
};

export const downloadXlsxFromCsv = (csv, filenameBase) => {
  const rows = sanitizeSpreadsheetRows(parseCsv(String(csv || "")));
  const workbook = createZip([
    {
      name: "[Content_Types].xml",
      contents:
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
    },
    {
      name: "_rels/.rels",
      contents:
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    },
    {
      name: "xl/workbook.xml",
      contents:
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Dataset" sheetId="1" r:id="rId1"/></sheets></workbook>',
    },
    {
      name: "xl/_rels/workbook.xml.rels",
      contents:
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
    },
    {
      name: "xl/worksheets/sheet1.xml",
      contents: buildWorksheetXml(rows),
    },
  ]);

  downloadBlob(
    new Blob([workbook], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }),
    `${sanitizeExportName(filenameBase)}.xlsx`
  );
};
