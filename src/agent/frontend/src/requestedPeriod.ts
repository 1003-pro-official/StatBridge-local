export type RequestedPeriod = { start: string; end: string; adjusted: boolean };

export function requestedPeriod(query: string, available?: { min: string; max: string }): RequestedPeriod | null {
  if (!available?.min || !available.max) return null;
  const dates = query.match(/((?:19|20)\d{2}-\d{2}-\d{2})\s*(?:부터|~|∼|-)\s*((?:19|20)\d{2}-\d{2}-\d{2})/);
  const years = query.match(/((?:19|20)\d{2})\s*년?\s*(?:부터|~|∼|-)\s*((?:19|20)\d{2})\s*년?(?:까지)?/);
  const from = query.match(/((?:19|20)\d{2})\s*년\s*(?:부터|이후)/);
  const through = query.match(/((?:19|20)\d{2})\s*년\s*(까지|이전)/);
  const recent = query.match(/(?:최근|지난)\s*(\d{1,2})\s*년/);
  const singleYear = query.match(/((?:19|20)\d{2})\s*년(?:도)?/);
  let start: string;
  let end: string;
  if (dates) {
    [, start, end] = dates;
  } else if (years) {
    start = `${years[1]}-01-01`;
    end = `${years[2]}-12-31`;
  } else if (from) {
    start = `${from[1]}-01-01`;
    end = available.max;
  } else if (through) {
    start = available.min;
    end = `${Number(through[1]) - (through[2] === "이전" ? 1 : 0)}-12-31`;
  } else if (recent) {
    const count = Number(recent[1]);
    if (count < 1) return null;
    const first = new Date(`${available.max}T00:00:00Z`);
    first.setUTCFullYear(first.getUTCFullYear() - count);
    first.setUTCDate(first.getUTCDate() + 1);
    start = first.toISOString().slice(0, 10);
    end = available.max;
  } else if (singleYear) {
    start = `${singleYear[1]}-01-01`;
    end = `${singleYear[1]}-12-31`;
  } else {
    return null;
  }
  if (start > end || end < available.min || start > available.max) return null;
  const boundedStart = start < available.min ? available.min : start;
  const boundedEnd = end > available.max ? available.max : end;
  return { start: boundedStart, end: boundedEnd, adjusted: boundedStart !== start || boundedEnd !== end };
}
