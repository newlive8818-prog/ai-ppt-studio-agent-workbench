const ISO_INSTANT = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/;

export function parseIsoInstantMicros(value: unknown): bigint | null {
  if (typeof value !== "string") return null;
  const match = ISO_INSTANT.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  if (year < 1 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) return null;
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
  if (day < 1 || day > daysInMonth) return null;

  let offsetMinutes = 0;
  if (match[8] !== "Z") {
    const offsetHour = Number(match[8].slice(1, 3));
    const offsetMinute = Number(match[8].slice(4, 6));
    if (offsetHour > 23 || offsetMinute > 59) return null;
    const magnitude = (offsetHour * 60) + offsetMinute;
    offsetMinutes = match[8].startsWith("+") ? magnitude : -magnitude;
  }

  const utc = new Date(0);
  utc.setUTCFullYear(year, month - 1, day);
  utc.setUTCHours(hour, minute, second, 0);
  const epochMilliseconds = utc.getTime();
  if (!Number.isFinite(epochMilliseconds)) return null;
  const fraction = (match[7] || "").padEnd(6, "0");
  return (BigInt(epochMilliseconds) * 1000n)
    + BigInt(fraction || "0")
    - (BigInt(offsetMinutes) * 60_000_000n);
}

export function isIsoInstant(value: unknown): value is string {
  return parseIsoInstantMicros(value) !== null;
}
