function toDateString(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

function parseScanTime(scanTime) {
  const [hourStr, minuteStr] = scanTime.split(':');
  const hour = Number(hourStr);
  const minute = Number(minuteStr);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return null;
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
  return { hour, minute };
}

function nextRunAt(scanTime, now = new Date()) {
  const parsed = parseScanTime(scanTime);
  if (!parsed) return null;
  const target = new Date(now);
  target.setHours(parsed.hour, parsed.minute, 0, 0);
  if (target <= now) {
    target.setDate(target.getDate() + 1);
  }
  return target;
}

module.exports = {
  toDateString,
  parseScanTime,
  nextRunAt,
};
