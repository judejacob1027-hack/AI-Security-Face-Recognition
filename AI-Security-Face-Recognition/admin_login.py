import tkinter as tk
from tkinter import messagebox
import hashlib

# ==============================
# ADMIN SECURITY
# ==============================

ADMIN_PASSWORD = "admin123"

PASSWORD_HASH = hashlib.sha256(
    ADMIN_PASSWORD.encode()
).hexdigest()


# ==============================
# COLORS
# ==============================

BG = "#080b10"
PANEL = "#10151d"
BORDER = "#252d38"
TEXT = "#f2f5f7"
MUTED = "#7f8b99"
ACCENT = "#00e5a0"
RED = "#ff4d67"


# ==============================
# LOGIN FUNCTION
# ==============================

def login():

    password = password_entry.get()

    entered_hash = hashlib.sha256(
        password.encode()
    ).hexdigest()

    if entered_hash == PASSWORD_HASH:

        status_label.config(
            text="● ACCESS GRANTED",
            fg=ACCENT
        )

        root.after(
            500,
            open_dashboard
        )

    else:

        status_label.config(
            text="● ACCESS DENIED",
            fg=RED
        )

        password_entry.delete(
            0,
            tk.END
        )

        root.after(
            2000,
            reset_status
        )


def reset_status():

    status_label.config(
        text="● SYSTEM ONLINE",
        fg=ACCENT
    )


def toggle_password():

    if password_entry.cget("show") == "*":

        password_entry.config(
            show=""
        )

        show_button.config(
            text="HIDE"
        )

    else:

        password_entry.config(
            show="*"
        )

        show_button.config(
            text="SHOW"
        )


def open_dashboard():

    messagebox.showinfo(
        "Authentication",
        "Admin authentication successful.\n\nDashboard will be connected next."
    )


# ==============================
# MAIN WINDOW
# ==============================

root = tk.Tk()

root.title(
    "AI SECURITY — Admin Portal"
)

root.geometry(
    "900x600"
)

root.resizable(
    False,
    False
)

root.configure(
    bg=BG
)


# ==============================
# LEFT BRANDING PANEL
# ==============================

left_panel = tk.Frame(
    root,
    bg=BG,
    width=450,
    height=600
)

left_panel.pack(
    side="left",
    fill="both"
)

left_panel.pack_propagate(False)


# Logo

logo = tk.Label(
    left_panel,
    text="◈",
    font=("Segoe UI", 54, "bold"),
    fg=ACCENT,
    bg=BG
)

logo.pack(
    pady=(115, 10)
)


brand = tk.Label(
    left_panel,
    text="AI SECURITY",
    font=("Segoe UI", 28, "bold"),
    fg=TEXT,
    bg=BG
)

brand.pack()


tagline = tk.Label(
    left_panel,
    text="INTELLIGENT FACE RECOGNITION",
    font=("Segoe UI", 9, "bold"),
    fg=MUTED,
    bg=BG
)

tagline.pack(
    pady=(6, 0)
)


line = tk.Frame(
    left_panel,
    bg=ACCENT,
    height=2,
    width=100
)

line.pack(
    pady=25
)


description = tk.Label(
    left_panel,
    text="Secure identity verification\nand automated attendance system.",
    font=("Segoe UI", 10),
    fg=MUTED,
    bg=BG,
    justify="center"
)

description.pack()


# System status

system_status = tk.Label(
    left_panel,
    text="●  SYSTEM ONLINE",
    font=("Segoe UI", 9, "bold"),
    fg=ACCENT,
    bg=BG
)

system_status.pack(
    pady=(70, 0)
)


# ==============================
# RIGHT LOGIN PANEL
# ==============================

right_panel = tk.Frame(
    root,
    bg=PANEL,
    width=450,
    height=600,
    highlightbackground=BORDER,
    highlightthickness=1
)

right_panel.pack(
    side="right",
    fill="both"
)

right_panel.pack_propagate(False)


# Header

login_title = tk.Label(
    right_panel,
    text="ADMIN PORTAL",
    font=("Segoe UI", 22, "bold"),
    fg=TEXT,
    bg=PANEL
)

login_title.pack(
    pady=(105, 5)
)


login_subtitle = tk.Label(
    right_panel,
    text="Restricted administrator access",
    font=("Segoe UI", 9),
    fg=MUTED,
    bg=PANEL
)

login_subtitle.pack(
    pady=(0, 35)
)


# Password label

password_label = tk.Label(
    right_panel,
    text="ADMIN PASSWORD",
    font=("Segoe UI", 8, "bold"),
    fg=MUTED,
    bg=PANEL
)

password_label.pack(
    anchor="w",
    padx=70
)


# Password container

password_frame = tk.Frame(
    right_panel,
    bg=BG,
    highlightbackground=BORDER,
    highlightthickness=1
)

password_frame.pack(
    padx=70,
    pady=(8, 5),
    fill="x"
)


password_entry = tk.Entry(
    password_frame,
    show="*",
    font=("Segoe UI", 12),
    fg=TEXT,
    bg=BG,
    insertbackground=ACCENT,
    relief="flat",
    bd=0
)

password_entry.pack(
    side="left",
    padx=14,
    pady=13,
    fill="x",
    expand=True
)


show_button = tk.Button(
    password_frame,
    text="SHOW",
    command=toggle_password,
    font=("Segoe UI", 8, "bold"),
    fg=ACCENT,
    bg=BG,
    activeforeground=ACCENT,
    activebackground=BG,
    relief="flat",
    bd=0,
    cursor="hand2"
)

show_button.pack(
    side="right",
    padx=10
)


# Login button

login_button = tk.Button(
    right_panel,
    text="AUTHENTICATE  →",
    command=login,
    font=("Segoe UI", 10, "bold"),
    fg=BG,
    bg=ACCENT,
    activeforeground=BG,
    activebackground=ACCENT,
    relief="flat",
    bd=0,
    cursor="hand2",
    height=2
)

login_button.pack(
    padx=70,
    pady=(25, 15),
    fill="x"
)


# Status

status_label = tk.Label(
    right_panel,
    text="● SYSTEM ONLINE",
    font=("Segoe UI", 8, "bold"),
    fg=ACCENT,
    bg=PANEL
)

status_label.pack(
    pady=5
)


# Footer

footer = tk.Label(
    right_panel,
    text="AUTHORIZED PERSONNEL ONLY  •  AI SECURITY",
    font=("Segoe UI", 7),
    fg=MUTED,
    bg=PANEL
)

footer.pack(
    side="bottom",
    pady=25
)


# Enter key

root.bind(
    "<Return>",
    lambda event: login()
)


password_entry.focus()


# Start application

root.mainloop()