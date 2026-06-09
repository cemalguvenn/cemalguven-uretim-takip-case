import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

// jsPDF's built-in fonts don't cover Turkish glyphs; transliterate to ASCII so
// PDF reports stay readable without embedding a large Unicode font.
const TR_MAP = { ş: "s", Ş: "S", ğ: "g", Ğ: "G", ı: "i", İ: "I", ö: "o", Ö: "O", ü: "u", Ü: "U", ç: "c", Ç: "C" };
function ascii(v) {
  if (v === null || v === undefined) return "";
  return String(v).replace(/[şŞğĞıİöÖüÜçÇ]/g, (c) => TR_MAP[c] || c);
}

// Client-side CSV export. Builds a UTF-8 CSV (BOM for Excel) and triggers download.
function toCsvValue(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function downloadCsv(filename, rows, columns) {
  if (!rows || rows.length === 0) {
    const blob = new Blob(["﻿"], { type: "text/csv;charset=utf-8;" });
    return triggerDownload(filename, blob);
  }
  const cols = columns || Object.keys(rows[0]);
  const header = cols.join(",");
  const body = rows
    .map((row) => cols.map((c) => toCsvValue(row[c])).join(","))
    .join("\n");
  const blob = new Blob(["﻿" + header + "\n" + body], {
    type: "text/csv;charset=utf-8;",
  });
  triggerDownload(filename, blob);
}

function triggerDownload(filename, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// PDF export via jsPDF + autotable. `columns` = [{key,label}].
export function downloadPdf(filename, title, columns, rows) {
  const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
  doc.setFontSize(14);
  doc.text(ascii(title), 40, 36);
  doc.setFontSize(9);
  doc.setTextColor(120);
  doc.text(
    `${new Date().toLocaleString("tr-TR")} · ${rows.length} kayit`,
    40,
    52
  );
  autoTable(doc, {
    startY: 64,
    head: [columns.map((c) => ascii(c.label))],
    body: rows.map((r) => columns.map((c) => ascii(r[c.key]))),
    styles: { fontSize: 7, cellPadding: 3 },
    headStyles: { fillColor: [59, 130, 246] },
    alternateRowStyles: { fillColor: [245, 247, 250] },
    margin: { left: 40, right: 40 },
  });
  doc.save(filename);
}
