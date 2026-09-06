import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";

const STARTUPS_SOURCE = "C:/Users/Inteli/Desktop/PS_Ligas/files/startups.csv";
const DOCUMENTS_SOURCE = "C:/Users/Inteli/Desktop/PS_Ligas/files/documentos.csv";
const OUTPUT_DIR = "outputs/pgadmin-import";
const GENERATED_AT = new Date().toISOString();
const UUID_NAMESPACE_URL = "6ba7b811-9dad-11d1-80b4-00c04fd430c8";

const startupHeaders = [
  "id", "name", "website", "sector", "stage", "location",
  "short_description", "founded_year", "team_size", "created_at", "updated_at",
];
const documentHeaders = [
  "id", "startup_id", "document_type", "title", "content_text", "source_url",
  "published_at", "created_at", "updated_at",
];

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  const input = text.replace(/^\uFEFF/, "");

  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    if (quoted) {
      if (char === '"' && input[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }

  if (quoted) throw new Error("CSV inválido: campo entre aspas não foi encerrado");
  if (field.length > 0 || row.length > 0) {
    row.push(field.replace(/\r$/, ""));
    rows.push(row);
  }
  return rows;
}

function recordsFromCsv(text, expectedHeaders) {
  const [headers, ...rows] = parseCsv(text);
  if (JSON.stringify(headers) !== JSON.stringify(expectedHeaders)) {
    throw new Error(`Cabeçalhos inesperados: ${headers.join(",")}`);
  }
  return rows.map((row, rowIndex) => {
    if (row.length !== headers.length) {
      throw new Error(`Linha ${rowIndex + 2} tem ${row.length} campos; esperado ${headers.length}`);
    }
    return Object.fromEntries(headers.map((header, columnIndex) => [header, row[columnIndex]]));
  });
}

function csvEscape(value) {
  const text = value == null ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function toCsv(headers, records) {
  return `${[headers, ...records.map((record) => headers.map((header) => record[header]))]
    .map((row) => row.map(csvEscape).join(","))
    .join("\r\n")}\r\n`;
}

function uuidToBytes(uuid) {
  return Buffer.from(uuid.replaceAll("-", ""), "hex");
}

function uuidV5(name) {
  const hash = crypto.createHash("sha1").update(uuidToBytes(UUID_NAMESPACE_URL)).update(name, "utf8").digest();
  const bytes = Buffer.from(hash.subarray(0, 16));
  bytes[6] = (bytes[6] & 0x0f) | 0x50;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function firstInteger(value, fieldName) {
  if (!value.trim() || /^N\/?D$/i.test(value.trim())) return "";
  const match = value.match(/\d+/);
  if (!match) throw new Error(`${fieldName} sem número reconhecível: ${value}`);
  return String(Number.parseInt(match[0], 10));
}

function utcPublishedAt(value) {
  if (!value.trim()) return "";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error(`Data inválida: ${value}`);
  return `${value}T00:00:00Z`;
}

function assertUuid(value, label) {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value)) {
    throw new Error(`${label} não é UUID v5: ${value}`);
  }
}

function assertLength(records, field, maximum) {
  for (const [index, record] of records.entries()) {
    if (record[field].length > maximum) {
      throw new Error(`${field} excede ${maximum} caracteres na linha ${index + 2}`);
    }
  }
}

const [startupText, documentText] = await Promise.all([
  fs.readFile(STARTUPS_SOURCE, "utf8"),
  fs.readFile(DOCUMENTS_SOURCE, "utf8"),
]);

const sourceStartups = recordsFromCsv(startupText, [
  "id", "nome", "site", "setor_vertical", "estagio", "localizacao",
  "descricao_curta", "ano_fundacao", "tamanho_time",
]);
const sourceDocuments = recordsFromCsv(documentText, [
  "id", "startup_id", "tipo", "titulo", "conteudo_texto", "url_fonte", "data_publicacao",
]);

const startupIdMap = new Map(sourceStartups.map((record) => [
  record.id,
  uuidV5(`nvidia-startup-ai-radar/startup/${record.id}`),
]));

const startups = sourceStartups.map((record) => ({
  id: startupIdMap.get(record.id),
  name: record.nome,
  website: record.site,
  sector: record.setor_vertical,
  stage: record.estagio,
  location: record.localizacao,
  short_description: record.descricao_curta,
  founded_year: firstInteger(record.ano_fundacao, "ano_fundacao"),
  team_size: firstInteger(record.tamanho_time, "tamanho_time"),
  created_at: GENERATED_AT,
  updated_at: GENERATED_AT,
}));

const documents = sourceDocuments.map((record) => {
  const startupId = startupIdMap.get(record.startup_id);
  if (!startupId) throw new Error(`Documento ${record.id} referencia startup inexistente: ${record.startup_id}`);
  return {
    id: uuidV5(`nvidia-startup-ai-radar/startup-document/${record.id}`),
    startup_id: startupId,
    document_type: record.tipo,
    title: record.titulo,
    content_text: record.conteudo_texto,
    source_url: record.url_fonte,
    published_at: utcPublishedAt(record.data_publicacao),
    created_at: GENERATED_AT,
    updated_at: GENERATED_AT,
  };
});

if (sourceStartups.length !== 12 || sourceDocuments.length !== 36) {
  throw new Error(`Contagem inesperada: ${sourceStartups.length} startups e ${sourceDocuments.length} documentos`);
}

for (const [label, records] of [["startup", startups], ["documento", documents]]) {
  const ids = records.map((record) => record.id);
  if (new Set(ids).size !== ids.length) throw new Error(`IDs duplicados em ${label}`);
  ids.forEach((id) => assertUuid(id, `${label}.id`));
}
documents.forEach((record) => assertUuid(record.startup_id, "documento.startup_id"));

for (const field of ["id", "name", "created_at", "updated_at"]) {
  if (startups.some((record) => !record[field])) throw new Error(`Campo obrigatório vazio: startups.${field}`);
}
for (const field of ["id", "startup_id", "document_type", "title", "content_text", "source_url", "created_at", "updated_at"]) {
  if (documents.some((record) => !record[field])) throw new Error(`Campo obrigatório vazio: startup_documents.${field}`);
}

for (const [field, maximum] of [["name", 255], ["website", 2048], ["sector", 120], ["stage", 80], ["location", 160]]) {
  assertLength(startups, field, maximum);
}
for (const [field, maximum] of [["document_type", 80], ["title", 500], ["source_url", 2048]]) {
  assertLength(documents, field, maximum);
}

await fs.mkdir(OUTPUT_DIR, { recursive: true });
const startupOutput = path.join(OUTPUT_DIR, "startups_pgadmin.csv");
const documentOutput = path.join(OUTPUT_DIR, "startup_documents_pgadmin.csv");
const startupCsv = toCsv(startupHeaders, startups);
const documentCsv = toCsv(documentHeaders, documents);
await Promise.all([
  fs.writeFile(startupOutput, startupCsv, "utf8"),
  fs.writeFile(documentOutput, documentCsv, "utf8"),
]);

const roundTripStartups = recordsFromCsv(await fs.readFile(startupOutput, "utf8"), startupHeaders);
const roundTripDocuments = recordsFromCsv(await fs.readFile(documentOutput, "utf8"), documentHeaders);
if (JSON.stringify(roundTripStartups) !== JSON.stringify(startups)) throw new Error("Falha no round-trip de startups");
if (JSON.stringify(roundTripDocuments) !== JSON.stringify(documents)) throw new Error("Falha no round-trip de documentos");

console.log(JSON.stringify({
  generatedAt: GENERATED_AT,
  outputs: [startupOutput, documentOutput],
  rows: { startups: startups.length, startup_documents: documents.length },
  sampleStartup: startups[0],
  sampleDocument: documents[0],
}, null, 2));
