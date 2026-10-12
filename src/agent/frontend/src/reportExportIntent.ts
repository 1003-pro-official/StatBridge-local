/** Standalone export requests only; never swallow a combined chart edit. */
export function reportExportIntent(instruction:string):'png'|'svg'|'pdf'|'json'|null {
  const match=instruction.trim().match(/^(?:인쇄용\s*)?(PNG|SVG|PDF|JSON)(?:\s*파일)?(?:로|으로)?\s*(?:출력|저장|다운로드)(?:해\s*줘|해\s*주세요|해주세요|해줘)?[.!]?$/i);
  return match?match[1].toLowerCase() as 'png'|'svg'|'pdf'|'json':null;
}
