
import { jsPDF } from "jspdf";

/*
 * FraudShield AI v11 — Phase 5
 * Professional client-side PDF report generation.
 *
 * This module:
 * - Uses existing AI investigation results
 * - Does not contact an external PDF API
 * - Supports multiple pages
 * - Adds report metadata and human-review notices
 * - Does not include uploaded screenshot bytes
 */

const PAGE_WIDTH = 210;
const PAGE_HEIGHT = 297;

const MARGIN = 18;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2;
const BODY_BOTTOM = 269;

const COLORS = {
  navy: [12, 26, 49],
  blue: [39, 101, 224],
  text: [31, 45, 66],
  muted: [101, 118, 143],
  light: [239, 244, 251],
  border: [215, 224, 237],
  warning: [142, 88, 23],
};


function safeText(value) {
  return String(value ?? "")
    .replace(/\r\n/g, "\n")
    .replace(/\t/g, "    ")
    .replace(/\u20b9/g, "INR ")
    .replace(/\u2013|\u2014/g, "-")
    .replace(/\u2018|\u2019/g, "'")
    .replace(/\u201c|\u201d/g, '"')
    .replace(/\u2022/g, "-")
    .replace(/[^\x0A\x20-\x7E]/g, "?");
}


function formattedDate(value) {
  const date = value ? new Date(value) : new Date();

  if (Number.isNaN(date.getTime())) {
    return "Not available";
  }

  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}


function normalizeMarkdown(markdown) {
  return safeText(markdown)
    .replace(/```[\w-]*\n?/g, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)");
}


function drawPageFrame(pdf, page) {
  pdf.setFillColor(...COLORS.navy);
  pdf.rect(0, 0, PAGE_WIDTH, 16, "F");

  pdf.setTextColor(255, 255, 255);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(10);
  pdf.text("FRAUDSHIELD AI", MARGIN, 10);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(7.5);
  pdf.text(
    "FINANCIAL INTELLIGENCE / ACADEMIC SANDBOX",
    PAGE_WIDTH - MARGIN,
    10,
    { align: "right" }
  );

  pdf.setDrawColor(...COLORS.border);
  pdf.line(MARGIN, 277, PAGE_WIDTH - MARGIN, 277);

  pdf.setFont("helvetica", "normal");
  pdf.setTextColor(...COLORS.muted);
  pdf.setFontSize(7.5);

  pdf.text(
    "CONFIDENTIAL ACADEMIC DRAFT - HUMAN REVIEW REQUIRED",
    MARGIN,
    283
  );

  pdf.text(
    `Page ${page}`,
    PAGE_WIDTH - MARGIN,
    283,
    { align: "right" }
  );
}


export function downloadInvestigationPdf({
  reportText,
  transactionId,
  provider,
  model,
  createdAt,
  historyId,
}) {
  if (!reportText || !String(reportText).trim()) {
    throw new Error("No investigation report available.");
  }

  const pdf = new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
    compress: true,
  });

  const date = formattedDate(createdAt);
  const transactionRef = safeText(
    transactionId || "Not linked"
  );
  const providerName = safeText(
    provider || "Not available"
  ).toUpperCase();
  const modelName = safeText(model || "Not recorded");
  const reference = safeText(
    historyId || "Unsaved draft"
  );

  pdf.setProperties({
    title: "FraudShield AI - Investigation Report",
    subject: "Synthetic UPI Fraud Investigation Draft",
    author: "FraudShield AI",
    keywords: "FraudShield, academic, investigation",
    creator: "FraudShield AI - jsPDF",
  });

  drawPageFrame(pdf, 1);

  let y = 27;

  pdf.setFont("helvetica", "bold");
  pdf.setTextColor(...COLORS.navy);
  pdf.setFontSize(19);

  pdf.text(
    "Fraud Investigation Report",
    MARGIN,
    y
  );

  y += 8;

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.setTextColor(...COLORS.muted);

  pdf.text(
    "AI-assisted assessment of a simulated transaction",
    MARGIN,
    y
  );

  y += 11;

  // Report metadata
  pdf.setFillColor(...COLORS.light);
  pdf.roundedRect(
    MARGIN,
    y,
    CONTENT_WIDTH,
    40,
    3,
    3,
    "F"
  );

  const fields = [
    ["TRANSACTION", transactionRef],
    ["PROVIDER", providerName],
    ["MODEL", modelName],
    ["GENERATED", date],
    ["HISTORY ID", reference],
  ];

  let fieldY = y + 7;

  for (const [label, value] of fields) {
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(7);
    pdf.setTextColor(...COLORS.muted);
    pdf.text(label, MARGIN + 6, fieldY);

    pdf.setFont("helvetica", "normal");
    pdf.setTextColor(...COLORS.text);

    const lines = pdf.splitTextToSize(
      value,
      CONTENT_WIDTH - 44
    );

    pdf.text(
      String(lines[0] || ""),
      MARGIN + 40,
      fieldY
    );

    fieldY += 7;
  }

  y += 49;

  // Advisory notice
  pdf.setFillColor(255, 248, 232);
  pdf.setDrawColor(230, 201, 144);

  pdf.roundedRect(
    MARGIN,
    y,
    CONTENT_WIDTH,
    17,
    2,
    2,
    "FD"
  );

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(9);
  pdf.setTextColor(...COLORS.warning);

  pdf.text(
    "DRAFT - HUMAN REVIEW REQUIRED",
    MARGIN + 5,
    y + 6
  );

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(7.5);

  pdf.text(
    "AI output is advisory and does not establish confirmed fraud.",
    MARGIN + 5,
    y + 12
  );

  y += 29;

  let pageNumber = 1;

  function ensureSpace(height = 10) {
    if (y + height <= BODY_BOTTOM) {
      return;
    }

    pdf.addPage();
    pageNumber += 1;
    drawPageFrame(pdf, pageNumber);
    y = 27;
  }

  function writeLines(
    text,
    {
      bold = false,
      fontSize = 9.5,
      color = COLORS.text,
      indent = 0,
      lineHeight = 5.2,
      after = 3,
    } = {}
  ) {
    pdf.setFont(
      "helvetica",
      bold ? "bold" : "normal"
    );
    pdf.setFontSize(fontSize);
    pdf.setTextColor(...color);

    const availableWidth =
      CONTENT_WIDTH - indent;

    const lines = pdf.splitTextToSize(
      safeText(text),
      availableWidth
    );

    for (const line of lines) {
      ensureSpace(lineHeight);
      pdf.text(line, MARGIN + indent, y);
      y += lineHeight;
    }

    y += after;
  }

  function sectionHeading(title) {
    ensureSpace(14);

    y += 2;

    pdf.setDrawColor(...COLORS.blue);
    pdf.setLineWidth(0.8);
    pdf.line(MARGIN, y - 3, MARGIN, y + 5);

    writeLines(title, {
      bold: true,
      fontSize: 11,
      color: COLORS.navy,
      indent: 5,
      lineHeight: 6,
      after: 3,
    });
  }

  sectionHeading("AI Investigation Findings");

  const paragraphs = normalizeMarkdown(
    reportText
  ).split("\n");

  for (const rawLine of paragraphs) {
    const line = rawLine.trim();

    if (!line) {
      y += 2;
      continue;
    }

    if (/^#{1,6}\s+/.test(line)) {
      sectionHeading(
        line.replace(/^#{1,6}\s+/, "")
      );
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      writeLines(
        "- " + line.replace(/^[-*]\s+/, ""),
        { indent: 4 }
      );
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      writeLines(line, {
        indent: 4,
      });
      continue;
    }

    if (/^---+$/.test(line)) {
      ensureSpace(8);
      pdf.setDrawColor(...COLORS.border);
      pdf.line(
        MARGIN,
        y,
        PAGE_WIDTH - MARGIN,
        y
      );
      y += 7;
      continue;
    }

    writeLines(line);
  }

  ensureSpace(26);
  y += 6;

  pdf.setDrawColor(...COLORS.border);
  pdf.line(
    MARGIN,
    y,
    PAGE_WIDTH - MARGIN,
    y
  );

  y += 8;

  writeLines("Investigator Review", {
    bold: true,
    fontSize: 10,
  });

  writeLines(
    "Final status: PENDING HUMAN VERIFICATION",
    {
      bold: true,
      fontSize: 8.5,
      color: COLORS.warning,
    }
  );

  writeLines(
    "This document was generated from a synthetic or redacted academic investigation. The AI assessment must be verified against authorized evidence before any operational decision.",
    {
      fontSize: 8,
      color: COLORS.muted,
    }
  );

  const safeId = transactionRef
    .replace(/[^a-zA-Z0-9_-]/g, "")
    .slice(0, 32) || "draft";

  pdf.save(
    `FraudShield_Investigation_${safeId}.pdf`
  );
}
