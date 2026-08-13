export type CsvPreview = { headers: string[]; rows: Record<string, string>[]; errors: string[] };

export function parseCsv(text: string): CsvPreview {
  const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) return { headers: [], rows: [], errors: ["The CSV file is empty."] };
  const matrix = lines.map(parseLine); const headers = matrix[0].map((value) => value.trim()); const errors: string[] = [];
  if (new Set(headers).size !== headers.length) errors.push("CSV headers must be unique.");
  const rows = matrix.slice(1).map((values, index) => { if (values.length !== headers.length) errors.push(`Row ${index + 2} has ${values.length} columns; expected ${headers.length}.`); return Object.fromEntries(headers.map((header, column) => [header, values[column]?.trim() ?? ""])); });
  return { headers, rows, errors };
}

function parseLine(line: string) { const values: string[] = []; let value = ""; let quoted = false; for (let index = 0; index < line.length; index++) { const char = line[index]; if (char === '"' && quoted && line[index + 1] === '"') { value += '"'; index++; } else if (char === '"') quoted = !quoted; else if (char === "," && !quoted) { values.push(value); value = ""; } else value += char; } values.push(value); return values; }
