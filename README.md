# Day Blocks

Write your ideal day once, as plain text. Day Blocks turns it into repeating events for any calendar, warns you where blocks collide, and tells you what you should be doing right now.

No account. Just a text file, a small app, and the calendar you already use.

```
days: weekdays
05:00 05:15 Rise | Water first. Clothes laid out the night before.
05:15 05:35 Move
08:00 11:00 Deep work | One hard thing. Phone in another room.
21:30 05:00 Sleep

days: sat sun
07:00 08:00 Long walk
```

```
$ python3 dayblocks.py ics plan.txt --alarm 5
plan.ics: 5 repeating blocks from 2026-11-23. Import it into your calendar.

$ python3 dayblocks.py check plan.txt
Hours a week:
   37.5  Sleep
   15.0  Deep work
    2.0  Long walk
    1.7  Move
    1.2  Rise
   57.4  planned of 168

$ python3 dayblocks.py now plan.txt
Now:  Deep work  (until 11:00)
      One hard thing. Phone in another room.
Next: Sleep at 21:30
```

If two blocks collide, `check` names them and the line numbers, including a late night that runs into the next morning:
`Monday: 'Sleep' (line 4) runs into 'Rise' (line 2) by 15 min`.

## The app

```
python3 day_blocks_app.py
```

The app has three pages:
- **Today:** what your plan says to do right now, with its note, and the rest of today. It refreshes itself, so you can leave it open.
- **My plan:** write and edit the plan, with a guide beside it. **Save and check** warns about blocks that collide and shows your hours per week.
- **Calendar:** pick a start date and a reminder, then make the `.ics` file.

Your plan is kept in `~/.day-blocks/plan.txt`.

## From the command line

You need Python 3.9 or newer, and nothing else.

```
git clone https://github.com/sebaytlabs/day-blocks
cd day-blocks
cp examples/early-riser.txt my-day.txt        # edit it
python3 dayblocks.py check my-day.txt
python3 dayblocks.py ics my-day.txt --start 2026-12-01 --alarm 5
```

Then import `my-day.ics`:
- **Google Calendar:** Settings > Import. Make a separate calendar for it first, so you can switch it off in one click.
- **Apple Calendar:** File > Import.
- **Outlook, Fastmail and Thunderbird:** they all take `.ics` files.

Changed your plan? Delete that calendar and import the new file. Because the blocks live in their own calendar, that's one click.

## The plan file

| Line | Meaning |
|---|---|
| `days: weekdays` | the blocks below repeat Monday to Friday. Also `weekends`, `every day`, or a list like `mon wed fri` |
| `05:00 05:15 Rise` | a block from 5:00 to 5:15 called Rise |
| `... Rise \| Water first.` | everything after `\|` is the note inside the event |
| `21:30 05:00 Sleep` | blocks can run past midnight |
| `# ...` | a comment |

### Options for `ics`

| Option | What it does |
|---|---|
| `--start` | the date the blocks start (default today) |
| `--until` | the date they stop (default: they repeat forever) |
| `--alarm MIN` | a reminder that many minutes before each block |
| `--tz America/Chicago` | pin the times to one time zone. Without it, times follow you when you travel. |
| `--out FILE` | where to write the file |

## Why plain text

A plan you can read in one glance is a plan you'll keep. Five minutes in a text editor is quicker than dragging 15 events around a calendar. The file can live in your notes, in git, or on paper. `check` shows where the week's hours actually go, which is usually the real surprise.

## Tests

```
python3 dayblocks.py --selftest
```

## License

MIT. Made by [Sebayt Labs](https://sebaytlabs.com).
