#!/usr/bin/env python3
"""Day Blocks app: plan your ideal day in plain words, see what to do right now, put it in your calendar.

  python3 day_blocks_app.py

Pages: Today (what to do now and the rest of today), My plan (write and check it), Calendar (make the file to
import into Google, Apple, Outlook and the rest). Your plan is kept in ~/.day-blocks/plan.txt.
"""
import datetime as dt
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import dayblocks as db
from appkit import BG, DIM, FG, FONT, LINE, PANEL, App, Page, open_path

ACCENT = "#e8590c"
HERE = Path(__file__).resolve().parent
HOME = Path(os.environ.get("DAY_BLOCKS_HOME", Path.home() / ".day-blocks"))
PLAN = HOME / "plan.txt"
ABOUT = ("Day Blocks\n\nWrite your ideal day once, in plain words. See what you should be doing right now, catch "
         "blocks that collide, and put the whole week in any calendar.\n\nFree and open source (MIT), by Sebayt Labs."
         f"\n\nYour plan: {PLAN}")


def load_plan():
    if not PLAN.exists():
        HOME.mkdir(parents=True, exist_ok=True)
        PLAN.write_text((HERE / "examples" / "early-riser.txt").read_text(encoding="utf-8"), encoding="utf-8")
    return PLAN.read_text(encoding="utf-8")


def blocks_or_error():
    try:
        return db.parse(load_plan()), None
    except ValueError as e:
        return [], str(e)


def todays(blocks, day):
    d = db.DAYS[day.weekday()]
    return sorted((b for b in blocks if d in b.days), key=lambda b: b.start)


class TodayPage(Page):
    HELP = ("Today\n\nThe big card is what your plan says to do right now, with its note. Below it is the rest of "
            "today, with the current block marked.\n\nThis page comes from your plan. To change it, go to My plan. "
            "It refreshes by itself every half minute, so you can leave it open.")
    HINT = "This is what your plan says right now. Change the plan on the My plan page."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.job = None

    def shown(self):
        self.refresh()

    def hidden(self):
        if self.job:
            self.after_cancel(self.job)
            self.job = None

    def refresh(self):
        self.clear()
        now = dt.datetime.now()
        blocks, err = blocks_or_error()
        self.title(f"{now:%A, %B %d}", "What your plan says to do now, and the rest of today.")
        if err:
            self.text(f"Your plan has a mistake: {err}", 12, "#c92a2a")
            self.button(self.row(), "Fix it in My plan", lambda: self.app.show("plan")).pack(side="left")
            return
        cur, nxt = db.on(blocks, now)
        c = self.card()
        tk.Label(c, text="RIGHT NOW", bg=PANEL, fg=DIM, font=(FONT, 10, "bold"), anchor="w").pack(fill="x", padx=18,
                                                                                               pady=(14, 0))
        tk.Label(c, text=cur.title if cur else "Free time", bg=PANEL, fg=self.app.accent, font=(FONT, 28, "bold"),
                 anchor="w").pack(fill="x", padx=18)
        sub = f"until {cur.end:%H:%M}" if cur else "nothing planned right now"
        if cur and cur.note:
            sub += f"   ·   {cur.note}"
        tk.Label(c, text=sub, bg=PANEL, fg=FG, font=(FONT, 13), anchor="w", wraplength=740,
                 justify="left").pack(fill="x", padx=18)
        if nxt:
            tk.Label(c, text=f"Next: {nxt.title} at {nxt.start:%H:%M}", bg=PANEL, fg=DIM, font=(FONT, 12),
                     anchor="w").pack(fill="x", padx=18, pady=(6, 14))
        self.text("The rest of today", 13, bold=True, pady=(14, 4))
        for b in todays(blocks, now.date()):
            is_now = b is cur
            r = tk.Frame(self.body, bg=self.app.accent if is_now else BG)
            r.pack(fill="x", pady=1)
            fg = "white" if is_now else FG
            tk.Label(r, text=f"{b.start:%H:%M}–{b.end:%H:%M}", bg=r["bg"], fg=fg, font=("Monospace", 11),
                     width=12, anchor="w").pack(side="left", padx=8, pady=3)
            tk.Label(r, text=b.title, bg=r["bg"], fg=fg, font=(FONT, 11, "bold" if is_now else "normal")).pack(side="left")
        self.job = self.after(30000, self.refresh)


class PlanPage(Page):
    HELP = ("My plan\n\nEach line is one block:   05:00 05:20 Rise | a note\nStart time, end time, a name, and "
            "after | an optional note.\n\nA line 'days: weekdays' says which days the blocks below it are for. You "
            "can also write weekends, every day, or days like mon wed fri.\n\nPress Save and check. It saves the "
            "plan, warns you about blocks that collide (including a late night running into the morning), and "
            "shows how many hours a week each block takes.")
    HINT = "Edit your plan, then press Save and check."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.title("My plan", "Your ideal week in plain words. One block per line.")
        split = tk.Frame(self.body, bg=BG)
        split.pack(fill="both", expand=True)
        left = tk.Frame(split, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        self.box = tk.Text(left, font=("Monospace", 11), relief="solid", bd=1, wrap="none", padx=8, pady=6, undo=True,
                           width=40)
        self.box.pack(fill="both", expand=True)
        self.box.insert("1.0", load_plan())
        r = tk.Frame(left, bg=BG)
        r.pack(fill="x", pady=8)
        self.button(r, "Save and check", self.save).pack(side="left")
        self.button(r, "Start over from the example", self.reset, primary=False).pack(side="left", padx=8)
        right = tk.Frame(split, bg=BG, width=330)
        left.pack_forget()   # the guide claims its width first, the editor takes the rest
        right.pack(side="right", fill="y", padx=(14, 0))
        right.pack_propagate(False)
        left.pack(side="left", fill="both", expand=True)
        guide = tk.Frame(right, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        guide.pack(fill="x")
        for t, s in (("How to write it", True), ("days: weekdays", False), ("05:00 05:20 Rise | Water first", False),
                     ("09:00 12:00 Deep work", False), ("21:30 05:00 Sleep", False), ("", True),
                     ("days: also weekends, every day, or mon wed fri.\nAfter | is a note shown in the event.\n"
                      "Blocks can run past midnight.\nLines starting with # are notes to yourself.", True)):
            tk.Label(guide, text=t, bg=PANEL, fg=FG if s else self.app.accent, justify="left", anchor="w",
                     font=(FONT, 10, "bold") if t == "How to write it" else ((FONT, 10) if s else ("Monospace", 10)),
                     wraplength=300).pack(fill="x", padx=12, pady=1)
        tk.Frame(guide, bg=PANEL, height=8).pack()
        self.result = tk.Label(right, text="", bg=BG, fg=FG, justify="left", anchor="nw", font=("Monospace", 10),
                               wraplength=320)
        self.result.pack(fill="both", expand=True, pady=10)

    def save(self):
        text = self.box.get("1.0", "end").rstrip() + "\n"
        try:
            blocks = db.parse(text)
        except ValueError as e:
            self.result.config(text=f"Not saved. Fix this first:\n{e}", fg="#c92a2a")
            return
        PLAN.write_text(text, encoding="utf-8")
        lines = db.check(blocks)
        clash = [l for l in lines if "runs into" in l]
        self.result.config(text=("Saved. Two blocks collide:\n" if clash else "Saved. No blocks collide.\n\n")
                           + "\n".join(lines), fg="#c92a2a" if clash else FG)
        self.app.say("Saved. The Today page uses it straight away.")

    def reset(self):
        if messagebox.askyesno("Start over", "Replace your plan with the example? Your current plan is lost."):
            self.box.delete("1.0", "end")
            self.box.insert("1.0", (HERE / "examples" / "early-riser.txt").read_text(encoding="utf-8"))


class CalendarPage(Page):
    HELP = ("Calendar\n\nMakes one .ics file with every block as a repeating event. Import it into your calendar:\n"
            "Google Calendar: Settings > Import (make a separate calendar for it first, so you can switch it off in "
            "one click).\nApple Calendar: File > Import.\nOutlook, Fastmail, Thunderbird: they all take .ics.\n\n"
            "Changed your plan? Delete that calendar and import a new file.")
    HINT = "Pick the start date and a reminder, then press Make calendar file."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.title("Put it in your calendar", "One file with every block as a repeating event, for any calendar app.")
        self.steps(["Save your plan on the My plan page.",
                    "Pick when it starts and whether you want a reminder before each block.",
                    "Press Make calendar file, then import it (Help shows how for each calendar)."])
        self.start = tk.StringVar(value=dt.date.today().isoformat())
        self.until = tk.StringVar()
        self.alarm = tk.StringVar(value="5")
        for label, var, note in (("Starts on", self.start, "YYYY-MM-DD"),
                                 ("Ends on", self.until, "leave empty to repeat forever"),
                                 ("Reminder", self.alarm, "minutes before each block; empty for none")):
            r = self.row()
            tk.Label(r, text=label, bg=BG, fg=FG, font=(FONT, 11), width=12, anchor="w").pack(side="left")
            tk.Entry(r, textvariable=var, font=(FONT, 11), relief="solid", bd=1, width=14).pack(side="left", ipady=4)
            tk.Label(r, text=note, bg=BG, fg=DIM, font=(FONT, 10)).pack(side="left", padx=10)
        self.button(self.row(pady=14), "Make calendar file", self.make).pack(side="left")
        self.done = self.text("", 12)

    def make(self):
        blocks, err = blocks_or_error()
        if err:
            messagebox.showerror("Day Blocks", f"Your plan has a mistake: {err}")
            return
        try:
            start = dt.date.fromisoformat(self.start.get().strip())
            until = dt.date.fromisoformat(self.until.get().strip()) if self.until.get().strip() else None
            alarm = int(self.alarm.get()) if self.alarm.get().strip() else None
        except ValueError:
            messagebox.showerror("Day Blocks", "Dates look like 2026-12-01, and the reminder is a number of minutes.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".ics", initialfile="my-day.ics",
                                           filetypes=[("Calendar file", "*.ics")])
        if not out:
            return
        with open(out, "w", encoding="utf-8", newline="") as f:
            f.write(db.ics(blocks, start, until, alarm))
        self.done.config(text=f"Made {out} with {len(blocks)} repeating blocks. Now import it into your calendar "
                              "(press Help for how).")
        self.button(self.row(), "Show the file", lambda: open_path(Path(out).parent), primary=False).pack(side="left")


def main():
    app = App("Day Blocks", "Your ideal day, in your calendar.", ACCENT, ABOUT, class_name="DayBlocks")
    app.add_page("today", "Today", TodayPage)
    app.add_page("plan", "My plan", PlanPage)
    app.add_page("calendar", "Calendar", CalendarPage)
    if (HERE / "icon.png").exists():
        app.iconphoto(True, tk.PhotoImage(file=str(HERE / "icon.png")))
    app.run("today")


if __name__ == "__main__":
    main()
