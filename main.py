from __future__ import annotations

import json
import tkinter as tk
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk


# Shared palette keeps the sidebar, cards, and controls visually consistent.
BACKGROUND = "#F5F7FB"
SURFACE = "#FFFFFF"
SIDEBAR = "#172033"
TEXT = "#172033"
MUTED = "#7B8497"
ACCENT = "#5B6CFA"
BORDER = "#E8EBF2"
GREEN = "#1F9D72"
AMBER = "#C98616"
RED = "#D05252"


@dataclass
class Task:
    # Store dates as ISO strings so they can be sorted and serialized directly.
    title: str
    notes: str = ""
    due_date: str = ""
    priority: str = "Medium"
    completed: bool = False


class TodoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        # Set a comfortable default window size while still allowing smaller screens.
        self.title("Daylight — To-do list")
        self.geometry("1180x780")
        self.minsize(900, 640)
        self.configure(bg=BACKGROUND)

        # Keep tasks between launches in the user's home directory.
        self.data_path = Path.home() / ".daylight-todo" / "tasks.json"
        self.tasks: list[Task] = []
        self.current_view = "Today"
        self.search_text = tk.StringVar()
        # Load data before drawing widgets so the first refresh shows saved tasks.
        self._load_tasks()
        self._configure_styles()
        self._build_layout()
        self.refresh()
        self._schedule_midnight_refresh()

    def _configure_styles(self) -> None:
        # Use the same theme for ttk inputs across supported desktop platforms.
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "TEntry",
            padding=(11, 9),
            fieldbackground=SURFACE,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            insertcolor=TEXT,
        )
        style.configure(
            "TCombobox",
            padding=(9, 7),
            fieldbackground=SURFACE,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            arrowsize=12,
        )

    def _build_layout(self) -> None:
        # The fixed-width sidebar contains navigation; the main panel expands.
        self.sidebar = tk.Frame(self, bg=SIDEBAR, width=238)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=SIDEBAR)
        brand.pack(fill="x", padx=25, pady=(30, 42))
        mark = tk.Label(
            brand,
            text="D",
            bg=ACCENT,
            fg="white",
            font=("TkDefaultFont", 15, "bold"),
            width=2,
            height=1,
            pady=6,
        )
        mark.pack(side="left")
        tk.Label(
            brand,
            text="  daylight",
            bg=SIDEBAR,
            fg="white",
            font=("TkDefaultFont", 17, "bold"),
        ).pack(side="left")

        tk.Label(
            self.sidebar,
            text="WORKSPACE",
            bg=SIDEBAR,
            fg="#7D879A",
            font=("TkDefaultFont", 9, "bold"),
        ).pack(anchor="w", padx=27, pady=(0, 12))

        self.nav_buttons: dict[str, tk.Button] = {}
        # Capture each label as a default argument so callbacks keep their own view.
        for label, icon in (
            ("Today", "◷"),
            ("Upcoming", "▦"),
            ("Pending", "◌"),
            ("All tasks", "☷"),
            ("Completed", "✓"),
        ):
            button = tk.Button(
                self.sidebar,
                text=f"  {icon}    {label}",
                command=lambda view=label: self.set_view(view),
                anchor="w",
                padx=17,
                pady=11,
                bd=0,
                relief="flat",
                cursor="hand2",
                font=("TkDefaultFont", 10),
                bg=SIDEBAR,
                fg="#C1C8D5",
                activebackground="#27334A",
                activeforeground="white",
            )
            button.pack(fill="x", padx=13, pady=2)
            self.nav_buttons[label] = button

        spacer = tk.Frame(self.sidebar, bg=SIDEBAR)
        spacer.pack(fill="both", expand=True)
        tk.Label(
            self.sidebar,
            text="A little progress each day\nadds up to big results.",
            bg=SIDEBAR,
            fg="#8791A4",
            justify="left",
            font=("TkDefaultFont", 9),
        ).pack(anchor="w", padx=27, pady=(0, 28))

        self.content = tk.Frame(self, bg=BACKGROUND)
        self.content.pack(side="left", fill="both", expand=True)

        # The header combines the current date with the primary add-task action.
        header = tk.Frame(self.content, bg=BACKGROUND)
        header.pack(fill="x", padx=38, pady=(30, 24))
        title_block = tk.Frame(header, bg=BACKGROUND)
        title_block.pack(side="left")
        self.page_title = tk.Label(
            title_block,
            text="Good morning",
            bg=BACKGROUND,
            fg=TEXT,
            font=("TkDefaultFont", 23, "bold"),
        )
        self.page_title.pack(anchor="w")
        self.date_label = tk.Label(
            title_block,
            text=date.today().strftime("%A, %B %d, %Y"),
            bg=BACKGROUND,
            fg=MUTED,
            font=("TkDefaultFont", 10),
        )
        self.date_label.pack(anchor="w", pady=(5, 0))

        add_button = tk.Button(
            header,
            text="+   Add task",
            command=self.open_add_dialog,
            bg=ACCENT,
            fg="white",
            activebackground="#4958E8",
            activeforeground="white",
            bd=0,
            padx=18,
            pady=11,
            cursor="hand2",
            font=("TkDefaultFont", 10, "bold"),
        )
        add_button.pack(side="right", anchor="center")

        # Summary cards are updated from the full task collection on each refresh.
        self.stats_frame = tk.Frame(self.content, bg=BACKGROUND)
        self.stats_frame.pack(fill="x", padx=38, pady=(0, 25))
        self.stat_values: dict[str, tk.Label] = {}
        for label, color in (
            ("Open tasks", ACCENT),
            ("Due today", AMBER),
            ("Completed", GREEN),
        ):
            card = tk.Frame(self.stats_frame, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
            card.pack(side="left", fill="x", expand=True, padx=(0, 12))
            inner = tk.Frame(card, bg=SURFACE)
            inner.pack(fill="both", padx=18, pady=15)
            tk.Label(
                inner,
                text=label.upper(),
                bg=SURFACE,
                fg=MUTED,
                font=("TkDefaultFont", 8, "bold"),
            ).pack(anchor="w")
            value = tk.Label(
                inner,
                text="0",
                bg=SURFACE,
                fg=color,
                font=("TkDefaultFont", 21, "bold"),
            )
            value.pack(anchor="w", pady=(5, 0))
            self.stat_values[label] = value

        # A non-modal banner reminds users about due and overdue tasks.
        self.notification_frame = tk.Frame(
            self.content,
            bg="#FFF6E7",
            highlightthickness=1,
            highlightbackground="#F1DEB9",
        )
        self.notification_icon = tk.Label(
            self.notification_frame,
            text="!",
            bg="#FFF6E7",
            fg=AMBER,
            font=("TkDefaultFont", 11, "bold"),
        )
        self.notification_icon.pack(side="left", padx=(14, 9), pady=11)
        self.notification_label = tk.Label(
            self.notification_frame,
            text="",
            bg="#FFF6E7",
            fg=TEXT,
            font=("TkDefaultFont", 9, "bold"),
            anchor="w",
        )
        self.notification_label.pack(side="left", fill="x", expand=True, pady=11)

        # Search is shared by every navigation view.
        toolbar = tk.Frame(self.content, bg=BACKGROUND)
        self.list_toolbar = toolbar
        toolbar.pack(fill="x", padx=38, pady=(0, 12))
        self.list_heading = tk.Label(
            toolbar,
            text="Your tasks",
            bg=BACKGROUND,
            fg=TEXT,
            font=("TkDefaultFont", 14, "bold"),
        )
        self.list_heading.pack(side="left")
        search_box = ttk.Entry(toolbar, textvariable=self.search_text, width=27)
        search_box.pack(side="right", ipady=2)
        search_box.insert(0, "")
        self.search_text.trace_add("write", lambda *_: self.refresh())
        tk.Label(
            toolbar,
            text="⌕",
            bg=BACKGROUND,
            fg=MUTED,
            font=("TkDefaultFont", 14),
        ).pack(side="right", padx=(0, 7))

        # Put the task rows in a canvas so long lists remain scrollable.
        list_shell = tk.Frame(self.content, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        list_shell.pack(fill="both", expand=True, padx=38, pady=(0, 30))
        self.task_canvas = tk.Canvas(list_shell, bg=SURFACE, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(list_shell, orient="vertical", command=self.task_canvas.yview)
        self.task_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.task_canvas.pack(side="left", fill="both", expand=True)
        self.task_list = tk.Frame(self.task_canvas, bg=SURFACE)
        self.list_window = self.task_canvas.create_window((0, 0), window=self.task_list, anchor="nw")
        self.task_list.bind("<Configure>", self._update_scroll_region)
        self.task_canvas.bind("<Configure>", self._resize_task_list)
        self.task_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _update_scroll_region(self, _event: tk.Event) -> None:
        # Keep the canvas scroll bounds in sync as rows are added or removed.
        self.task_canvas.configure(scrollregion=self.task_canvas.bbox("all"))

    def _resize_task_list(self, event: tk.Event) -> None:
        self.task_canvas.itemconfigure(self.list_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.task_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _schedule_midnight_refresh(self) -> None:
        # Recheck due dates at midnight even if the app stays open overnight.
        now = datetime.now()
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        delay_ms = max(1000, int((next_midnight - now).total_seconds() * 1000) + 1000)
        self.after(delay_ms, self._refresh_for_new_day)

    def _refresh_for_new_day(self) -> None:
        self.date_label.configure(text=date.today().strftime("%A, %B %d, %Y"))
        self.refresh()
        self._schedule_midnight_refresh()

    def _load_tasks(self) -> None:
        # A first launch has no file yet; malformed saved data is reported to the user.
        if not self.data_path.exists():
            return
        try:
            data = json.loads(self.data_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("The saved task data must be a list.")
            loaded: list[Task] = []
            for item in data:
                task = Task(**item)
                # Reject invalid saved values instead of displaying broken task rows.
                if task.priority not in {"Low", "Medium", "High"}:
                    raise ValueError(f"Unknown priority for task: {task.title}")
                if task.due_date:
                    datetime.strptime(task.due_date, "%Y-%m-%d")
                loaded.append(task)
            self.tasks = loaded
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            messagebox.showerror(
                "Could not load tasks",
                f"Your saved tasks could not be loaded from:\n{self.data_path}\n\n{error}",
            )

    def _save_tasks(self) -> bool:
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            # Replace the destination only after the complete JSON file is written.
            temporary_path = self.data_path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps([asdict(task) for task in self.tasks], indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(self.data_path)
            return True
        except OSError as error:
            messagebox.showerror(
                "Could not save tasks",
                f"Your changes could not be saved to:\n{self.data_path}\n\n{error}",
            )
            return False

    def set_view(self, view: str) -> None:
        self.current_view = view
        self.refresh()

    def _visible_tasks(self) -> list[Task]:
        # Apply the selected section first, then search within its matching tasks.
        today = date.today()
        query = self.search_text.get().strip().casefold()
        visible: list[Task] = []
        for task in self.tasks:
            if self.current_view == "Today":
                include = not task.completed and (not task.due_date or task.due_date <= today.isoformat())
            elif self.current_view == "Upcoming":
                include = not task.completed and bool(task.due_date) and task.due_date > today.isoformat()
            elif self.current_view == "Pending":
                include = not task.completed
            elif self.current_view == "Completed":
                include = task.completed
            else:
                include = True
            if include and query and query not in f"{task.title} {task.notes}".casefold():
                include = False
            if include:
                visible.append(task)

        # Open tasks come first, then earliest due date and highest priority.
        def sort_key(task: Task) -> tuple[bool, str, int]:
            priority_order = {"High": 0, "Medium": 1, "Low": 2}
            return (task.completed, task.due_date or "9999-12-31", priority_order[task.priority])

        return sorted(visible, key=sort_key)

    def refresh(self) -> None:
        # Update navigation selection, heading, and counts before rebuilding the list.
        for label, button in self.nav_buttons.items():
            selected = label == self.current_view
            button.configure(
                bg="#27334A" if selected else SIDEBAR,
                fg="white" if selected else "#C1C8D5",
                font=("TkDefaultFont", 10, "bold" if selected else "normal"),
            )
        titles = {
            "Today": "Good morning",
            "Upcoming": "Coming up",
            "Pending": "Tasks in progress",
            "All tasks": "All your tasks",
            "Completed": "Nicely done",
        }
        self.page_title.configure(text=titles[self.current_view])
        today = date.today().isoformat()
        open_tasks = sum(not task.completed for task in self.tasks)
        due_today = sum(
            not task.completed and task.due_date == today
            for task in self.tasks
        )
        overdue = sum(
            not task.completed and bool(task.due_date) and task.due_date < today
            for task in self.tasks
        )
        completed = sum(task.completed for task in self.tasks)
        self.stat_values["Open tasks"].configure(text=str(open_tasks))
        self.stat_values["Due today"].configure(text=str(due_today))
        self.stat_values["Completed"].configure(text=str(completed))
        self.list_heading.configure(text=f"{self.current_view} tasks")
        self._update_notification(due_today, overdue)

        # Rebuild rows to reflect changed filters, task states, or search text.
        for child in self.task_list.winfo_children():
            child.destroy()
        visible = self._visible_tasks()
        if not visible:
            empty = tk.Frame(self.task_list, bg=SURFACE)
            empty.pack(fill="x", padx=26, pady=55)
            tk.Label(
                empty,
                text="You’re all caught up",
                bg=SURFACE,
                fg=TEXT,
                font=("TkDefaultFont", 15, "bold"),
            ).pack()
            tk.Label(
                empty,
                text="Add a task to get your day moving.",
                bg=SURFACE,
                fg=MUTED,
                font=("TkDefaultFont", 10),
            ).pack(pady=(7, 0))
            return

        for index, task in enumerate(visible):
            self._create_task_row(task, index)

    def _update_notification(self, due_today: int, overdue: int) -> None:
        # Keep the reminder visible without opening repeated pop-ups.
        if not due_today and not overdue:
            self.notification_frame.pack_forget()
            return

        messages = []
        if overdue:
            messages.append(f"{overdue} overdue")
        if due_today:
            messages.append(f"{due_today} due today")
        message = "Reminder: " + " · ".join(messages) + ". Review your Pending tasks."

        if overdue:
            background, foreground, border = "#FCEEEE", RED, "#F2D2D2"
        else:
            background, foreground, border = "#FFF6E7", AMBER, "#F1DEB9"
        self.notification_frame.configure(bg=background, highlightbackground=border)
        self.notification_icon.configure(bg=background, fg=foreground)
        self.notification_label.configure(text=message, bg=background)
        self.notification_frame.pack(
            before=self.list_toolbar,
            fill="x",
            padx=38,
            pady=(0, 12),
        )

    def _create_task_row(self, task: Task, index: int) -> None:
        # Each row keeps completion, task details, due date, priority, and delete together.
        row = tk.Frame(self.task_list, bg=SURFACE)
        row.pack(fill="x", padx=22)
        body = tk.Frame(row, bg=SURFACE)
        body.pack(fill="x", pady=(15, 14))

        check = tk.Button(
            body,
            text="✓" if task.completed else "",
            command=lambda item=task: self.toggle_task(item),
            bg=GREEN if task.completed else SURFACE,
            fg="white" if task.completed else MUTED,
            activebackground=GREEN if task.completed else "#F1F3F8",
            activeforeground="white" if task.completed else TEXT,
            bd=1 if not task.completed else 0,
            relief="solid",
            highlightthickness=0,
            highlightbackground=BORDER,
            width=2,
            height=1,
            cursor="hand2",
            font=("TkDefaultFont", 10, "bold"),
        )
        check.pack(side="left", padx=(0, 13))

        text_block = tk.Frame(body, bg=SURFACE)
        text_block.pack(side="left", fill="x", expand=True)
        tk.Label(
            text_block,
            text=task.title,
            bg=SURFACE,
            fg="#9AA1AF" if task.completed else TEXT,
            font=("TkDefaultFont", 10, "overstrike" if task.completed else "bold"),
            anchor="w",
        ).pack(fill="x", anchor="w")
        detail = task.notes.strip()
        if detail:
            tk.Label(
                text_block,
                text=detail,
                bg=SURFACE,
                fg=MUTED,
                font=("TkDefaultFont", 9),
                anchor="w",
            ).pack(fill="x", anchor="w", pady=(4, 0))

        if task.due_date:
            try:
                # Highlight overdue dates while showing a friendly label for today.
                due = datetime.strptime(task.due_date, "%Y-%m-%d").date()
                due_text = "Today" if due == date.today() else due.strftime("%b %d")
                due_color = RED if due < date.today() and not task.completed else MUTED
            except ValueError:
                due_text, due_color = task.due_date, MUTED
            tk.Label(
                body,
                text=due_text,
                bg=SURFACE,
                fg=due_color,
                font=("TkDefaultFont", 9),
            ).pack(side="left", padx=(10, 16))

        priority_color = {"High": RED, "Medium": AMBER, "Low": GREEN}[task.priority]
        tk.Label(
            body,
            text=task.priority,
            bg={"High": "#FCEEEE", "Medium": "#FFF6E7", "Low": "#EAF7F2"}[task.priority],
            fg=priority_color,
            padx=9,
            pady=4,
            font=("TkDefaultFont", 8, "bold"),
        ).pack(side="left", padx=(0, 12))

        delete = tk.Button(
            body,
            text="×",
            command=lambda item=task: self.delete_task(item),
            bg=SURFACE,
            fg="#A4AABA",
            activebackground="#FCEEEE",
            activeforeground=RED,
            bd=0,
            cursor="hand2",
            font=("TkDefaultFont", 15),
        )
        delete.pack(side="right")
        if index < len(self._visible_tasks()) - 1:
            tk.Frame(row, bg=BORDER, height=1).pack(fill="x")

    def toggle_task(self, task: Task) -> None:
        # Restore the previous state if the updated task could not be saved.
        task.completed = not task.completed
        if self._save_tasks():
            self.refresh()
        else:
            task.completed = not task.completed

    def delete_task(self, task: Task) -> None:
        # Confirm destructive actions and restore the row if persistence fails.
        if not messagebox.askyesno("Delete task", f'Delete “{task.title}”?'):
            return
        original_index = self.tasks.index(task)
        self.tasks.remove(task)
        if self._save_tasks():
            self.refresh()
        else:
            self.tasks.insert(original_index, task)

    def open_add_dialog(self) -> None:
        # Keep task creation focused in a small modal form.
        dialog = tk.Toplevel(self)
        dialog.title("Add a task")
        dialog.configure(bg=SURFACE)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("440x420")

        form = tk.Frame(dialog, bg=SURFACE)
        form.pack(fill="both", expand=True, padx=28, pady=25)
        tk.Label(
            form,
            text="Create a task",
            bg=SURFACE,
            fg=TEXT,
            font=("TkDefaultFont", 18, "bold"),
        ).pack(anchor="w")
        tk.Label(
            form,
            text="Capture it now, and keep moving.",
            bg=SURFACE,
            fg=MUTED,
            font=("TkDefaultFont", 9),
        ).pack(anchor="w", pady=(5, 20))

        tk.Label(form, text="TASK NAME", bg=SURFACE, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
        title_entry = ttk.Entry(form)
        title_entry.pack(fill="x", pady=(6, 14), ipady=2)

        tk.Label(form, text="NOTES (OPTIONAL)", bg=SURFACE, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
        notes_entry = ttk.Entry(form)
        notes_entry.pack(fill="x", pady=(6, 14), ipady=2)

        fields = tk.Frame(form, bg=SURFACE)
        fields.pack(fill="x")
        due_column = tk.Frame(fields, bg=SURFACE)
        due_column.pack(side="left", fill="x", expand=True, padx=(0, 12))
        priority_column = tk.Frame(fields, bg=SURFACE)
        priority_column.pack(side="left", fill="x", expand=True)
        tk.Label(due_column, text="DUE DATE", bg=SURFACE, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
        due_entry = ttk.Entry(due_column)
        due_entry.insert(0, date.today().isoformat())
        due_entry.pack(fill="x", pady=(6, 0), ipady=2)
        tk.Label(priority_column, text="PRIORITY", bg=SURFACE, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
        priority = tk.StringVar(value="Medium")
        priority_box = ttk.Combobox(
            priority_column,
            textvariable=priority,
            values=("Low", "Medium", "High"),
            state="readonly",
        )
        priority_box.pack(fill="x", pady=(6, 0), ipady=2)

        buttons = tk.Frame(form, bg=SURFACE)
        buttons.pack(fill="x", side="bottom", pady=(24, 0))
        tk.Button(
            buttons,
            text="Cancel",
            command=dialog.destroy,
            bg=SURFACE,
            fg=MUTED,
            activebackground="#F1F3F8",
            bd=0,
            padx=16,
            pady=10,
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))

        def save_task() -> None:
            # Validate user input before changing the in-memory task list.
            title = title_entry.get().strip()
            due_text = due_entry.get().strip()
            if not title:
                messagebox.showwarning("Task name required", "Enter a name for your task.", parent=dialog)
                title_entry.focus_set()
                return
            if due_text:
                try:
                    datetime.strptime(due_text, "%Y-%m-%d")
                except ValueError:
                    messagebox.showwarning(
                        "Check the due date",
                        "Use the date format YYYY-MM-DD, or leave the field blank.",
                        parent=dialog,
                    )
                    due_entry.focus_set()
                    return
            task = Task(
                title=title,
                notes=notes_entry.get().strip(),
                due_date=due_text,
                priority=priority.get(),
            )
            self.tasks.append(task)
            if self._save_tasks():
                dialog.destroy()
                # Show the new task immediately, including when it has a future date.
                self.set_view("Pending")
            else:
                self.tasks.remove(task)

        tk.Button(
            buttons,
            text="Save task",
            command=save_task,
            bg=ACCENT,
            fg="white",
            activebackground="#4958E8",
            activeforeground="white",
            bd=0,
            padx=18,
            pady=10,
            cursor="hand2",
            font=("TkDefaultFont", 9, "bold"),
        ).pack(side="right")
        title_entry.focus_set()
        dialog.bind("<Return>", lambda _event: save_task())


if __name__ == "__main__":
    app = TodoApp()
    app.mainloop()