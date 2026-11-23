#!/usr/bin/env python3
"""Day Blocks: write your ideal day as plain text once, get it as repeating events in any calendar.

  dayblocks.py ics  PLAN.txt [--start YYYY-MM-DD] [--until YYYY-MM-DD] [--alarm MIN] [--tz Area/City] [--out FILE]
  dayblocks.py now  PLAN.txt          what you should be doing right now, and what's next
  dayblocks.py check PLAN.txt         overlaps, gaps, and hours per block
  dayblocks.py --selftest

PLAN.txt looks like this:

  days: weekdays                    # weekdays, weekends, every day, or a list: mon wed fri
  05:00 05:20 Rise | Water, then get dressed by the bed.
  05:20 06:00 Move
  09:00 12:00 Deep work | One hard thing. Phone in another room.

  days: sat sun
  08:00 09:00 Long walk

Everything after | is the note shown in the event. Blocks can cross midnight (23:00 06:00 Sleep).
The .ics file imports into Google Calendar, Apple Calendar, Outlook, Fastmail, Thunderbird and the rest.
Times are your local time wherever you are, unless you give --tz.
Standard library only.
"""
import datetime as dt
import re
import sys
import uuid

GAP = 30  # minutes: shorter unplanned stretches are just the walk between blocks

DAYS = ["mo", "tu", "we", "th", "fr", "sa", "su"]
NAMED = {"weekdays": DAYS[:5], "weekends": DAYS[5:], "every day": DAYS, "everyday": DAYS, "daily": DAYS}
FULL = dict(zip(DAYS, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]))
LINE = re.compile(r"^(\d{1,2}):(\d{2})\s+(\d{1,2}):(\d{2})\s+(.+)$")


class Block:
    def __init__(self, start, end, title, note, days, line):
        self.start, self.end, self.title, self.note, self.days, self.line = start, end, title, note, days, line

    @property
    def minutes(self):
        a = self.start.hour * 60 + self.start.minute
        b = self.end.hour * 60 + self.end.minute
        return (b - a) % 1440 or 1440

    def __repr__(self):
        return f"{self.start:%H:%M}-{self.end:%H:%M} {self.title} {self.days}"


def parse_days(text):
    t = text.strip().lower()
    if t in NAMED:
        return list(NAMED[t])
    out = []
    for w in re.split(r"[\s,]+", t):
        if w[:2] not in DAYS:
            raise ValueError(f"unknown day '{w}'")
        out.append(w[:2])
    return sorted(set(out), key=DAYS.index)


def parse(text):
    blocks, days = [], list(DAYS)
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.lower().startswith("days:"):
            days = parse_days(line[5:])
            continue
        m = LINE.match(line)
        if not m:
            raise ValueError(f"line {n}: expected 'HH:MM HH:MM Title | note', got: {raw.strip()}")
        h1, m1, h2, m2, rest = m.groups()
        title, _, note = (p.strip() for p in rest.partition("|"))
        try:
            start, end = dt.time(int(h1), int(m1)), dt.time(int(h2), int(m2))
        except ValueError:
            raise ValueError(f"line {n}: not a real time: {raw.strip()}") from None
        blocks.append(Block(start, end, title, note, days, n))
    return blocks


def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    """iCalendar lines are at most 75 bytes; longer ones continue on the next line after a space."""
    out, b = [], line.encode("utf-8")
    while len(b) > 75:
        cut = 75 if not out else 74
        while (b[cut] & 0xC0) == 0x80:  # don't split a multi-byte character
            cut -= 1
        out.append(b[:cut].decode("utf-8"))
        b = b[cut:]
    out.append(b.decode("utf-8"))
    return "\r\n ".join(out)


def first_day(start, days):
    d = start
    while DAYS[d.weekday()] not in days:
        d += dt.timedelta(days=1)
    return d


def ics(blocks, start, until=None, alarm=None, tz=None):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "CALSCALE:GREGORIAN", "PRODID:-//Sebayt Labs//Day Blocks//EN",
             "X-WR-CALNAME:Day Blocks"]
    when = (lambda d: f";TZID={tz}:{d:%Y%m%dT%H%M%S}") if tz else (lambda d: f":{d:%Y%m%dT%H%M%S}")
    seen = {}
    for b in blocks:
        # The same block keeps the same UID in every file made from the plan, so importing a new file
        # replaces or skips its events instead of doubling them (a moved time is the same event).
        key = f"{b.title.lower()}|{','.join(b.days)}"
        seen[key] = seen.get(key, 0) + 1
        uid = uuid.uuid5(uuid.NAMESPACE_URL, f"dayblocks:{key}|{seen[key]}")
        day = first_day(start, b.days)
        s = dt.datetime.combine(day, b.start)
        e = s + dt.timedelta(minutes=b.minutes)
        rule = "RRULE:FREQ=WEEKLY;BYDAY=" + ",".join(d.upper() for d in b.days)
        if until:
            rule += f";UNTIL={until:%Y%m%d}T235959" + ("Z" if tz else "")
        lines += ["BEGIN:VEVENT", f"UID:{uid}@dayblocks", f"DTSTAMP:{stamp}",
                  "DTSTART" + when(s), "DTEND" + when(e), rule, fold("SUMMARY:" + esc(b.title))]
        if b.note:
            lines.append(fold("DESCRIPTION:" + esc(b.note)))
        if alarm is not None:
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", fold("DESCRIPTION:" + esc(b.title)),
                      f"TRIGGER:-PT{int(alarm)}M", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def on(blocks, moment):
    """(block happening at this moment or None, next block within the coming week or None)."""
    today, yesterday = DAYS[moment.weekday()], DAYS[(moment.weekday() - 1) % 7]
    mins = moment.hour * 60 + moment.minute
    current = None
    for b in blocks:
        a = b.start.hour * 60 + b.start.minute
        if today in b.days and a <= mins < a + b.minutes:
            current = b
        elif yesterday in b.days and a + b.minutes > 1440 and mins < a + b.minutes - 1440:
            current = b
    nxt = next_block(blocks, moment)
    return current, nxt[0] if nxt else None


def next_block(blocks, moment):
    """(block, datetime it starts) for the next start after this moment, looking a week ahead; or None.
    A weekdays-only plan on Friday night still says what Monday starts with."""
    for ahead in range(8):
        day = moment.date() + dt.timedelta(days=ahead)
        starts = sorted((dt.datetime.combine(day, b.start), b.line, b) for b in blocks
                        if DAYS[day.weekday()] in b.days)
        later = [(when, b) for when, _, b in starts if when > moment.replace(second=0, microsecond=0)
                 and (ahead or when.time() > moment.time())]
        if later:
            return later[0][1], later[0][0]
    return None


def when_text(start, moment):
    """'at 05:00', 'tomorrow at 05:00' or 'Monday at 05:00'."""
    days = (start.date() - moment.date()).days
    day = "" if days == 0 else "tomorrow " if days == 1 else f"{start:%A} "
    return f"{day}at {start:%H:%M}"


def gaps(blocks):
    """{day: [(start minute, end minute)]} for unplanned stretches of GAP minutes or more between a day's blocks."""
    out = {}
    for i, d in enumerate(DAYS):
        prev, segs = DAYS[i - 1], []
        for b in blocks:
            a = b.start.hour * 60 + b.start.minute
            if d in b.days:
                segs.append((a, min(a + b.minutes, 1440)))
            if prev in b.days and a + b.minutes > 1440:
                segs.append((0, a + b.minutes - 1440))
        segs.sort()
        found, end = [], None
        for s, e in segs:
            if end is not None and s - end >= GAP:
                found.append((end, s))
            end = e if end is None else max(end, e)
        out[d] = found
    return out


def check(blocks):
    """Lines of text: overlaps per day, unplanned gaps, and hours per block over a week."""
    out = []
    for i, d in enumerate(DAYS):
        prev = DAYS[i - 1]
        segs = []   # (start minute, end minute, block) on this day, counting last night's blocks that run past midnight
        for b in blocks:
            a = b.start.hour * 60 + b.start.minute
            if d in b.days:
                segs.append((a, a + b.minutes, b))
            if prev in b.days and a + b.minutes > 1440:
                segs.append((-1440 + a, a + b.minutes - 1440, b))
        segs.sort(key=lambda s: (s[0], s[2].line))
        for (s1, e1, a), (s2, e2, b) in zip(segs, segs[1:]):
            if s2 < e1:
                out.append(f"{FULL[d]}: '{a.title}' (line {a.line}) runs into '{b.title}' (line {b.line}) "
                           f"by {min(e1, e2) - s2} min")
    by_gaps = {}
    for d, g in gaps(blocks).items():
        if g:
            by_gaps.setdefault(tuple(g), []).append(d)
    hm = lambda m: f"{m // 60:02d}:{m % 60:02d}"
    for g, ds in by_gaps.items():
        names = "Weekdays" if ds == DAYS[:5] else "Weekends" if ds == DAYS[5:] else "Every day" if ds == DAYS \
            else ", ".join(FULL[d] for d in ds)
        out.append(f"{names}: nothing planned " + ", ".join(f"{hm(a)}-{hm(b)}" for a, b in g))
    week = {}
    for b in blocks:
        week[b.title] = week.get(b.title, 0) + b.minutes * len(b.days)
    out.append("Hours a week:")
    out += [f"  {m / 60:5.1f}  {t}" for t, m in sorted(week.items(), key=lambda x: -x[1])]
    planned = sum(week.values()) / 60
    out.append(f"  {planned:5.1f}  planned of 168")
    return out


def selftest():
    plan = """days: weekdays
    05:00 05:20 Rise | Water; then dress, quickly
    05:20 06:00 Move
    21:30 05:00 Sleep
    days: sat, sun
    08:00 09:00 Walk  # comment"""
    bs = parse(plan)
    assert [b.title for b in bs] == ["Rise", "Move", "Sleep", "Walk"]
    assert bs[2].minutes == 450 and bs[3].days == ["sa", "su"]
    text = ics(bs, dt.date(2026, 1, 3), until=dt.date(2026, 12, 31), alarm=5)  # a Saturday
    assert "DTSTART:20260105T050000" in text, "weekday blocks start on the first weekday"
    assert "DTSTART:20260103T080000" in text and "DTEND:20260106T050000" in text
    assert "SUMMARY:Rise" in text and "Water\\; then dress\\, quickly" in text
    assert "UNTIL=20261231T235959" in text and "TRIGGER:-PT5M" in text
    assert all(len(l.encode()) <= 75 for l in text.split("\r\n"))
    long = fold("DESCRIPTION:" + "é" * 100)
    assert all(len(p.encode()) <= 75 for p in long.split("\r\n"))
    cur, nxt = on(bs, dt.datetime(2026, 1, 6, 3, 0))      # Tuesday 3 am: still Monday night's sleep
    assert cur.title == "Sleep" and nxt.title == "Rise"
    cur, nxt = on(bs, dt.datetime(2026, 1, 9, 23, 30))    # Friday 23:30: next is Saturday's walk
    assert cur.title == "Sleep" and nxt.title == "Walk"
    assert any("runs into" in l for l in check(parse("05:00 06:00 A\n05:30 07:00 B")))
    spill = check(parse("days: sun\n22:00 06:30 Sleep\ndays: mon\n05:00 05:15 Rise"))
    assert any(l.startswith("Monday: 'Sleep'") and "by 15 min" in l for l in spill), spill
    assert not any("runs into" in l for l in check(bs))
    assert text.count("UID:") == 4 and text.split("UID:")[1][:36] == ics(bs, dt.date(2027, 5, 1)).split("UID:")[1][:36]
    assert len(set(l for l in text.split("\r\n") if l.startswith("UID:"))) == 4  # same plan, same UIDs; all distinct
    moved = ics(parse(plan.replace("05:00 05:20 Rise", "05:10 05:20 Rise")), dt.date(2026, 1, 3))
    assert moved.split("UID:")[1][:36] == text.split("UID:")[1][:36]  # a moved time is the same event
    wk = parse("days: weekdays\n09:00 12:00 Work")
    assert on(wk, dt.datetime(2026, 1, 9, 20, 0))[1].title == "Work"  # Friday night: Monday's first block
    b, when = next_block(wk, dt.datetime(2026, 1, 9, 20, 0))
    assert when == dt.datetime(2026, 1, 12, 9, 0) and when_text(when, dt.datetime(2026, 1, 9, 20)) == "Monday at 09:00"
    assert when_text(dt.datetime(2026, 1, 10, 9), dt.datetime(2026, 1, 9, 20)) == "tomorrow at 09:00"
    assert next_block(wk, dt.datetime(2026, 1, 12, 9, 0))[1] == dt.datetime(2026, 1, 13, 9, 0)  # just started: the next one
    assert next_block([], dt.datetime(2026, 1, 12)) is None
    g = gaps(parse("days: weekdays\n06:00 08:00 A\n08:10 09:00 B\n12:00 13:00 C\n22:00 06:00 Sleep"))
    assert g["mo"] == [(540, 720), (780, 1320)] and g["sa"] == [] and g["su"] == []
    lines = check(parse("days: weekdays\n06:00 08:00 A\n12:00 13:00 C"))
    assert "Weekdays: nothing planned 08:00-12:00" in lines, lines
    assert "Saturday: nothing planned 05:00-08:00" in check(bs)  # Friday night's sleep ends at 5, the walk is at 8
    try:
        parse("5 to 6 Rise")
        raise AssertionError("bad line accepted")
    except ValueError:
        pass
    print("selftest ok")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        sys.exit(__doc__)
    if argv[0] == "--selftest":
        return selftest()
    cmd, path, opts = argv[0], argv[1] if len(argv) > 1 else None, argv[2:]
    if not path:
        sys.exit(__doc__)

    def opt(name, default=None):
        return opts[opts.index(name) + 1] if name in opts else default
    with open(path, encoding="utf-8") as f:
        try:
            blocks = parse(f.read())
        except ValueError as e:
            sys.exit(f"{path}: {e}")
    if cmd == "ics":
        start = dt.date.fromisoformat(opt("--start", dt.date.today().isoformat()))
        until = opt("--until")
        alarm = opt("--alarm")
        out = opt("--out", path.rsplit(".", 1)[0] + ".ics")
        with open(out, "w", encoding="utf-8", newline="") as f:
            f.write(ics(blocks, start, dt.date.fromisoformat(until) if until else None,
                        int(alarm) if alarm else None, opt("--tz")))
        print(f"{out}: {len(blocks)} repeating blocks from {start}. Import it into your calendar.")
    elif cmd == "now":
        cur, nxt = on(blocks, dt.datetime.now())
        print(f"Now:  {cur.title}  (until {cur.end:%H:%M})" + (f"\n      {cur.note}" if cur.note else "")
              if cur else "Now:  nothing planned")
        upcoming = next_block(blocks, dt.datetime.now())
        if upcoming:
            print(f"Next: {upcoming[0].title} {when_text(upcoming[1], dt.datetime.now())}")
    elif cmd == "check":
        print("\n".join(check(blocks)))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
