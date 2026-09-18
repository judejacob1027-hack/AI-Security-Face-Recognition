# ============================================================
# AI SECURITY - FACE RECOGNITION
# COMPLETE SINGLE-FILE app.py
#
# Features:
# - Admin login
# - User account creation/login
# - Password hashing
# - Brute-force protection
# - Progressive lockout
# - AES-256-GCM encrypted storage
# - Face registration
# - Face recognition
# - Basic blink liveness
# - Unknown-face encrypted snapshots
# - Incident viewer
# - Attendance
# - Security event log
# - User profiles
# - Delete users
# - Auto face retraining
#
# IMPORTANT:
# Blink liveness is a BASIC anti-spoof layer.
# It is NOT a high-assurance biometric anti-spoofing system.
# ============================================================

import os
import csv
import io
import pickle
import threading
import hashlib
import uuid
import time
import re
import secrets
import tkinter as tk
from tkinter import messagebox, simpledialog
from datetime import datetime

import cv2
import numpy as np
import face_recognition
from PIL import Image, ImageTk
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ============================================================
# CONFIGURATION
# ============================================================

APP_TITLE = "AI SECURITY - FACE RECOGNITION"

SECURE_DIR = "secure_data"
SECURE_FACES_DIR = os.path.join(
    SECURE_DIR, "known_faces"
)
SECURE_INCIDENTS_DIR = os.path.join(
    SECURE_DIR, "security_incidents"
)

ENCODINGS_FILE = os.path.join(
    SECURE_DIR, "face_encodings.pkl.enc"
)

ATTENDANCE_FILE = os.path.join(
    SECURE_DIR, "attendance.csv.enc"
)

SECURITY_LOG_FILE = os.path.join(
    SECURE_DIR, "security_events.csv.enc"
)

USER_PROFILES_FILE = os.path.join(
    SECURE_DIR, "user_profiles.pkl.enc"
)

USER_ACCOUNTS_FILE = os.path.join(
    SECURE_DIR, "user_accounts.pkl.enc"
)

ENCRYPTION_KEY_FILE = "vault.key"

# Legacy files
LEGACY_KNOWN_FACES_DIR = "known_faces"
LEGACY_ENCODINGS_FILE = "face_encodings.pkl"
LEGACY_ATTENDANCE_FILE = "attendance.csv"
LEGACY_SECURITY_LOG_FILE = "security_events.csv"
LEGACY_INCIDENTS_DIR = "security_incidents"

# Admin password.
# Change this before using the application in production.
ADMIN_PASSWORD = "admin123"

FACE_THRESHOLD = 0.48

# Login protection
MAX_LOGIN_ATTEMPTS = 2

INITIAL_LOCKOUT_SECONDS = 5 * 60
MAX_LOCKOUT_SECONDS = 60 * 60

# User account protection
USER_MAX_LOGIN_ATTEMPTS = 3
USER_INITIAL_LOCKOUT = 60
USER_MAX_LOCKOUT = 30 * 60

# Liveness
BLINK_EAR_THRESHOLD = 0.21
BLINK_MIN_CLOSED_FRAMES = 2
LIVENESS_TIMEOUT_SECONDS = 8

# UI
BG = "#0b1220"
CARD = "#111827"
CARD2 = "#172033"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
GREEN = "#00e5a0"
RED = "#ff4d67"
YELLOW = "#f5c451"
BLUE = "#4da3ff"
WHITE = "#ffffff"

MAGIC = b"AISF-ENC-V1"
NONCE_SIZE = 12


# ============================================================
# CREATE DIRECTORIES
# ============================================================

os.makedirs(
    SECURE_DIR,
    exist_ok=True
)

os.makedirs(
    SECURE_FACES_DIR,
    exist_ok=True
)

os.makedirs(
    SECURE_INCIDENTS_DIR,
    exist_ok=True
)


# ============================================================
# GLOBAL STATE
# ============================================================

root = None

camera = None
camera_running = False

scanner_window = None
scanner_video_label = None
scanner_status_label = None
scanner_incident_label = None
scanner_liveness_label = None

known_encodings = []
known_names = []

# Admin authentication
admin_failed_attempts = 0
admin_locked_until = 0
admin_progressive_level = 0

# User authentication
user_failed_attempts = 0
user_locked_until = 0
user_progressive_level = 0

current_user = None
current_user_role = None

password_entry = None
username_entry = None
login_status = None

processing_frame = False
result_lock = threading.Lock()
latest_results = []

stable_name = ""
stable_count = 0
last_recognized_name = ""
unknown_alerted = False
last_incident_id = ""

camera_frame_count = 0

liveness_started_at = 0.0
liveness_verified = False
liveness_closed_frames = 0
liveness_was_closed = False
last_liveness_log_time = 0.0


# ============================================================
# ENCRYPTION
# ============================================================

def create_encryption_key():
    if not os.path.exists(
        ENCRYPTION_KEY_FILE
    ):
        key = AESGCM.generate_key(
            bit_length=256
        )

        with open(
            ENCRYPTION_KEY_FILE,
            "wb"
        ) as file:
            file.write(key)

        print(
            "AES-256 encryption key created."
        )


def load_encryption_key():
    if not os.path.exists(
        ENCRYPTION_KEY_FILE
    ):
        create_encryption_key()

    with open(
        ENCRYPTION_KEY_FILE,
        "rb"
    ) as file:
        key = file.read()

    if len(key) != 32:
        raise ValueError(
            "Invalid vault.key. "
            "AES-256 requires 32 bytes."
        )

    return key


ENCRYPTION_KEY = load_encryption_key()


def encrypt_data(data):
    aes = AESGCM(
        ENCRYPTION_KEY
    )

    nonce = secrets.token_bytes(
        NONCE_SIZE
    )

    encrypted = aes.encrypt(
        nonce,
        data,
        MAGIC
    )

    return (
        MAGIC
        + nonce
        + encrypted
    )


def decrypt_data(data):
    if not data.startswith(MAGIC):
        raise ValueError(
            "Invalid encrypted file."
        )

    start = len(MAGIC)

    nonce = data[
        start:start + NONCE_SIZE
    ]

    encrypted = data[
        start + NONCE_SIZE:
    ]

    if len(nonce) != NONCE_SIZE:
        raise ValueError(
            "Invalid encryption nonce."
        )

    aes = AESGCM(
        ENCRYPTION_KEY
    )

    return aes.decrypt(
        nonce,
        encrypted,
        MAGIC
    )


def write_encrypted_file(
    path,
    data
):
    encrypted = encrypt_data(
        data
    )

    temp_path = path + ".tmp"

    with open(
        temp_path,
        "wb"
    ) as file:
        file.write(
            encrypted
        )

    os.replace(
        temp_path,
        path
    )


def read_encrypted_file(path):
    with open(
        path,
        "rb"
    ) as file:
        encrypted = file.read()

    return decrypt_data(
        encrypted
    )


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def valid_password(password):
    return (
        len(password) >= 6
    )


ADMIN_PASSWORD_HASH = hash_password(
    ADMIN_PASSWORD
)


# ============================================================
# USER ACCOUNT STORAGE
# ============================================================

def load_user_accounts():
    if not os.path.exists(
        USER_ACCOUNTS_FILE
    ):
        return {}

    try:
        data = read_encrypted_file(
            USER_ACCOUNTS_FILE
        )

        accounts = pickle.loads(
            data
        )

        if isinstance(
            accounts,
            dict
        ):
            return accounts

    except Exception as error:
        print(
            "User account load error:",
            error
        )

    return {}


def save_user_accounts(accounts):
    data = pickle.dumps(
        accounts,
        protocol=pickle.HIGHEST_PROTOCOL
    )

    write_encrypted_file(
        USER_ACCOUNTS_FILE,
        data
    )


def username_valid(username):
    return bool(
        re.fullmatch(
            r"[A-Za-z0-9_.-]{3,32}",
            username
        )
    )


def create_user_account(
    username,
    password,
    role="USER"
):
    username = username.strip()

    if not username_valid(
        username
    ):
        return False, (
            "Username must contain "
            "3-32 letters, numbers, "
            "underscore, dot or hyphen."
        )

    if not valid_password(
        password
    ):
        return False, (
            "Password must contain "
            "at least 6 characters."
        )

    accounts = load_user_accounts()

    key = username.lower()

    if key in accounts:
        return False, (
            "Username already exists."
        )

    accounts[key] = {
        "username": username,
        "password_hash": hash_password(
            password
        ),
        "role": role,
        "created_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "failed_attempts": 0,
        "locked_until": 0,
        "lock_level": 0,
    }

    save_user_accounts(
        accounts
    )

    log_security_event(
        "USER_ACCOUNT_CREATED",
        f"Username: {username} | Role: {role}"
    )

    return True, "Account created successfully."


def verify_user_account(
    username,
    password
):
    accounts = load_user_accounts()

    key = username.strip().lower()

    account = accounts.get(
        key
    )

    if not account:
        return False, (
            "Invalid username or password."
        )

    now = time.time()

    locked_until = float(
        account.get(
            "locked_until",
            0
        )
    )

    if now < locked_until:
        remaining = int(
            locked_until - now
        ) + 1

        return False, (
            f"Account locked. "
            f"Try again in {remaining} seconds."
        )

    if (
        hash_password(password)
        == account.get(
            "password_hash"
        )
    ):
        account["failed_attempts"] = 0
        account["locked_until"] = 0
        account["lock_level"] = 0

        accounts[key] = account

        save_user_accounts(
            accounts
        )

        return True, account

    account["failed_attempts"] = (
        int(
            account.get(
                "failed_attempts",
                0
            )
        ) + 1
    )

    if (
        account["failed_attempts"]
        >= USER_MAX_LOGIN_ATTEMPTS
    ):
        account["lock_level"] = (
            int(
                account.get(
                    "lock_level",
                    0
                )
            ) + 1
        )

        level = account[
            "lock_level"
        ]

        if level == 1:
            lock_time = USER_INITIAL_LOCKOUT
        elif level == 2:
            lock_time = 5 * 60
        elif level == 3:
            lock_time = 15 * 60
        else:
            lock_time = USER_MAX_LOCKOUT

        account["locked_until"] = (
            time.time()
            + lock_time
        )

        account["failed_attempts"] = 0

        log_security_event(
            "USER_ACCOUNT_LOCKOUT",
            (
                f"Username: {username} | "
                f"Level: {level} | "
                f"Seconds: {lock_time}"
            )
        )

        accounts[key] = account

        save_user_accounts(
            accounts
        )

        return False, (
            f"Account locked for "
            f"{lock_time // 60 if lock_time >= 60 else lock_time} "
            f"{'minutes' if lock_time >= 60 else 'seconds'}."
        )

    remaining = (
        USER_MAX_LOGIN_ATTEMPTS
        - account["failed_attempts"]
    )

    accounts[key] = account

    save_user_accounts(
        accounts
    )

    return False, (
        f"Invalid username or password. "
        f"{remaining} attempt(s) remaining."
    )


def delete_user_account(username):
    accounts = load_user_accounts()

    key = username.lower()

    if key not in accounts:
        return False

    del accounts[key]

    save_user_accounts(
        accounts
    )

    log_security_event(
        "USER_ACCOUNT_DELETED",
        f"Username: {username}"
    )

    return True


def change_user_password(
    username
):
    window = tk.Toplevel(root)

    window.title(
        "Change Password"
    )

    window.geometry(
        "480x350"
    )

    window.configure(
        bg=BG
    )

    window.transient(root)
    window.grab_set()

    tk.Label(
        window,
        text="CHANGE PASSWORD",
        font=("Segoe UI", 20, "bold"),
        bg=BG,
        fg=GREEN
    ).pack(
        pady=(25, 20)
    )

    form = tk.Frame(
        window,
        bg=CARD,
        padx=25,
        pady=25
    )

    form.pack(
        padx=30,
        fill="both",
        expand=True
    )

    tk.Label(
        form,
        text="New Password",
        bg=CARD,
        fg=TEXT
    ).pack(
        anchor="w"
    )

    entry = tk.Entry(
        form,
        show="*",
        bg=CARD2,
        fg=WHITE,
        insertbackground=WHITE,
        relief="flat"
    )

    entry.pack(
        fill="x",
        pady=8,
        ipady=7
    )

    tk.Label(
        form,
        text="Confirm Password",
        bg=CARD,
        fg=TEXT
    ).pack(
        anchor="w"
    )

    confirm = tk.Entry(
        form,
        show="*",
        bg=CARD2,
        fg=WHITE,
        insertbackground=WHITE,
        relief="flat"
    )

    confirm.pack(
        fill="x",
        pady=8,
        ipady=7
    )

    def save():
        p1 = entry.get()
        p2 = confirm.get()

        if not valid_password(p1):
            messagebox.showwarning(
                "Password",
                "Minimum 6 characters.",
                parent=window
            )
            return

        if p1 != p2:
            messagebox.showwarning(
                "Password",
                "Passwords do not match.",
                parent=window
            )
            return

        accounts = load_user_accounts()

        key = username.lower()

        if key not in accounts:
            messagebox.showerror(
                "Error",
                "Account not found.",
                parent=window
            )
            return

        accounts[key][
            "password_hash"
        ] = hash_password(p1)

        save_user_accounts(
            accounts
        )

        log_security_event(
            "USER_PASSWORD_CHANGED",
            f"Username: {username}"
        )

        messagebox.showinfo(
            "Success",
            "Password changed successfully.",
            parent=window
        )

        window.destroy()

    tk.Button(
        form,
        text="CHANGE PASSWORD",
        command=save,
        bg=GREEN,
        fg="#07111d",
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        pady=9
    ).pack(
        fill="x",
        pady=15
    )


# ============================================================
# SECURITY LOG
# ============================================================

def log_security_event(
    event_type,
    details=""
):
    try:
        rows = []

        if os.path.exists(
            SECURITY_LOG_FILE
        ):
            try:
                data = read_encrypted_file(
                    SECURITY_LOG_FILE
                )

                rows = list(
                    csv.reader(
                        io.StringIO(
                            data.decode(
                                "utf-8"
                            )
                        )
                    )
                )

            except Exception:
                rows = []

        if not rows:
            rows = [
                [
                    "Timestamp",
                    "Event",
                    "Details"
                ]
            ]

        rows.append(
            [
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                str(event_type),
                str(details)
            ]
        )

        output = io.StringIO(
            newline=""
        )

        csv.writer(
            output
        ).writerows(
            rows
        )

        write_encrypted_file(
            SECURITY_LOG_FILE,
            output.getvalue().encode(
                "utf-8"
            )
        )

        print(
            f"[SECURITY] {event_type} | {details}"
        )

    except Exception as error:
        print(
            "Security log error:",
            error
        )


def read_security_log_rows():
    if not os.path.exists(
        SECURITY_LOG_FILE
    ):
        return []

    try:
        data = read_encrypted_file(
            SECURITY_LOG_FILE
        )

        return list(
            csv.reader(
                io.StringIO(
                    data.decode("utf-8")
                )
            )
        )

    except Exception as error:
        print(
            "Security log read error:",
            error
        )

        return []


def view_security_log():
    rows = read_security_log_rows()

    window = tk.Toplevel(root)

    window.title(
        "Security Events"
    )

    window.geometry(
        "950x550"
    )

    window.configure(
        bg=BG
    )

    tk.Label(
        window,
        text="SECURITY EVENT LOG",
        font=("Segoe UI", 20, "bold"),
        bg=BG,
        fg=RED
    ).pack(
        pady=15
    )

    box = tk.Text(
        window,
        bg=CARD,
        fg=TEXT,
        font=("Consolas", 10),
        relief="flat"
    )

    box.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=10
    )

    if not rows:
        box.insert(
            "end",
            "No security events."
        )
    else:
        for row in rows:
            box.insert(
                "end",
                " | ".join(row)
                + "\n"
            )

    box.config(
        state="disabled"
    )


# ============================================================
# FACE ENCODINGS
# ============================================================

def save_face_encodings(
    encodings,
    names
):
    data = pickle.dumps(
        {
            "encodings": encodings,
            "names": names
        },
        protocol=pickle.HIGHEST_PROTOCOL
    )

    write_encrypted_file(
        ENCODINGS_FILE,
        data
    )


def load_face_encodings():
    global known_encodings
    global known_names

    known_encodings = []
    known_names = []

    if not os.path.exists(
        ENCODINGS_FILE
    ):
        return False

    try:
        data = read_encrypted_file(
            ENCODINGS_FILE
        )

        payload = pickle.loads(
            data
        )

        known_encodings = payload.get(
            "encodings",
            []
        )

        known_names = payload.get(
            "names",
            []
        )

        print(
            f"Loaded {len(known_encodings)} "
            "encrypted face encodings."
        )

        return bool(
            known_encodings
        )

    except Exception as error:
        print(
            "Encoding load error:",
            error
        )

        return False


# ============================================================
# USER PROFILE STORAGE
# ============================================================

def load_user_profiles():
    if not os.path.exists(
        USER_PROFILES_FILE
    ):
        return {}

    try:
        data = read_encrypted_file(
            USER_PROFILES_FILE
        )

        result = pickle.loads(
            data
        )

        return (
            result
            if isinstance(result, dict)
            else {}
        )

    except Exception as error:
        print(
            "Profile load error:",
            error
        )

        return {}


def save_user_profiles(
    profiles
):
    write_encrypted_file(
        USER_PROFILES_FILE,
        pickle.dumps(
            profiles,
            protocol=pickle.HIGHEST_PROTOCOL
        )
    )


def save_user_profile(
    name,
    profile
):
    profiles = load_user_profiles()

    profiles[name] = profile

    save_user_profiles(
        profiles
    )


def delete_user_profile(
    name
):
    profiles = load_user_profiles()

    if name in profiles:
        del profiles[name]

        save_user_profiles(
            profiles
        )


# ============================================================
# USER LIST
# ============================================================

def get_users():
    if not os.path.isdir(
        SECURE_FACES_DIR
    ):
        return []

    users = []

    for name in os.listdir(
        SECURE_FACES_DIR
    ):
        path = os.path.join(
            SECURE_FACES_DIR,
            name
        )

        if os.path.isdir(path):
            users.append(name)

    return sorted(
        users,
        key=str.lower
    )


def safe_user_name(name):
    name = str(
        name
    ).strip()

    name = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    if name in {
        "",
        ".",
        ".."
    }:
        return ""

    return name[:80]


# ============================================================
# USER PROFILE FORM
# ============================================================

def collect_user_profile():
    fields = [
        ("Full Name", "full_name"),
        ("Phone", "phone"),
        ("Email", "email"),
        ("Department", "department"),
        ("Role", "role"),
        ("Notes", "notes"),
    ]

    result = {}

    window = tk.Toplevel(root)

    window.title(
        "Register User"
    )

    window.geometry(
        "580x570"
    )

    window.configure(
        bg=BG
    )

    window.transient(root)
    window.grab_set()

    tk.Label(
        window,
        text="USER PROFILE",
        font=("Segoe UI", 22, "bold"),
        bg=BG,
        fg=GREEN
    ).pack(
        pady=(20, 5)
    )

    tk.Label(
        window,
        text="AES-256-GCM encrypted profile",
        font=("Segoe UI", 9),
        bg=BG,
        fg=MUTED
    ).pack(
        pady=(0, 15)
    )

    form = tk.Frame(
        window,
        bg=CARD,
        padx=25,
        pady=20
    )

    form.pack(
        fill="both",
        expand=True,
        padx=25,
        pady=(0, 20)
    )

    entries = {}

    for row, (
        label,
        key
    ) in enumerate(fields):

        tk.Label(
            form,
            text=label,
            font=("Segoe UI", 10, "bold"),
            bg=CARD,
            fg=TEXT
        ).grid(
            row=row,
            column=0,
            sticky="w",
            pady=6
        )

        if key == "notes":
            widget = tk.Text(
                form,
                height=4,
                width=38,
                bg=CARD2,
                fg=WHITE,
                insertbackground=WHITE,
                relief="flat"
            )
        else:
            widget = tk.Entry(
                form,
                bg=CARD2,
                fg=WHITE,
                insertbackground=WHITE,
                relief="flat",
                font=("Segoe UI", 10)
            )

        widget.grid(
            row=row,
            column=1,
            sticky="ew",
            padx=(15, 0),
            pady=6,
            ipady=6
        )

        entries[key] = widget

    form.columnconfigure(
        1,
        weight=1
    )

    def submit():
        result.clear()

        for key, widget in entries.items():

            if isinstance(
                widget,
                tk.Text
            ):
                result[key] = widget.get(
                    "1.0",
                    "end"
                ).strip()
            else:
                result[key] = widget.get().strip()

        if not result.get(
            "full_name"
        ):
            messagebox.showwarning(
                "Missing Name",
                "Full Name is required.",
                parent=window
            )
            return

        email = result.get(
            "email",
            ""
        )

        if email and (
            "@" not in email
            or "." not in email.split("@")[-1]
        ):
            messagebox.showwarning(
                "Email",
                "Enter a valid email address.",
                parent=window
            )
            return

        result[
            "registered_at"
        ] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        result[
            "profile_version"
        ] = 1

        window.destroy()

    def cancel():
        result.clear()
        window.destroy()

    buttons = tk.Frame(
        window,
        bg=BG
    )

    buttons.pack(
        pady=(0, 20)
    )

    tk.Button(
        buttons,
        text="CONTINUE TO FACE CAPTURE",
        command=submit,
        bg=GREEN,
        fg="#07111d",
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        padx=18,
        pady=10
    ).pack(
        side="left",
        padx=5
    )

    tk.Button(
        buttons,
        text="CANCEL",
        command=cancel,
        bg=CARD2,
        fg=TEXT,
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        padx=18,
        pady=10
    ).pack(
        side="left",
        padx=5
    )

    root.wait_window(
        window
    )

    return result or None


# ============================================================
# CAMERA
# ============================================================

def open_camera():
    backends = []

    if hasattr(
        cv2,
        "CAP_DSHOW"
    ):
        backends.append(
            cv2.CAP_DSHOW
        )

    if hasattr(
        cv2,
        "CAP_MSMF"
    ):
        backends.append(
            cv2.CAP_MSMF
        )

    backends.append(
        cv2.CAP_ANY
    )

    for backend in backends:
        try:
            cap = cv2.VideoCapture(
                0,
                backend
            )

            if cap.isOpened():
                cap.set(
                    cv2.CAP_PROP_FRAME_WIDTH,
                    640
                )

                cap.set(
                    cv2.CAP_PROP_FRAME_HEIGHT,
                    480
                )

                cap.set(
                    cv2.CAP_PROP_FPS,
                    30
                )

                return cap

            cap.release()

        except Exception as error:
            print(
                "Camera error:",
                error
            )

    return None


# ============================================================
# FACE CAPTURE
# ============================================================

def save_face_image_encrypted(
    user_name,
    frame,
    index
):
    user_dir = os.path.join(
        SECURE_FACES_DIR,
        user_name
    )

    os.makedirs(
        user_dir,
        exist_ok=True
    )

    success, buffer = cv2.imencode(
        ".jpg",
        frame,
        [
            cv2.IMWRITE_JPEG_QUALITY,
            95
        ]
    )

    if not success:
        raise ValueError(
            "Could not encode image."
        )

    path = os.path.join(
        user_dir,
        f"face_{index:02d}.jpg.enc"
    )

    write_encrypted_file(
        path,
        buffer.tobytes()
    )

    return path


def decrypt_face_image(path):
    data = read_encrypted_file(
        path
    )

    array = np.frombuffer(
        data,
        dtype=np.uint8
    )

    image = cv2.imdecode(
        array,
        cv2.IMREAD_COLOR
    )

    if image is None:
        raise ValueError(
            "Invalid encrypted image."
        )

    return image


def capture_user_faces(
    user_name,
    number_of_images=5
):
    cap = open_camera()

    if cap is None:
        messagebox.showerror(
            "Camera",
            "Could not open camera."
        )
        return False

    captured = 0
    cancelled = False

    title = (
        "Register Face - "
        "SPACE = Capture | ESC = Cancel"
    )

    try:
        while captured < number_of_images:
            ret, frame = cap.read()

            if not ret:
                continue

            frame = cv2.flip(
                frame,
                1
            )

            preview = frame.copy()

            cv2.putText(
                preview,
                f"User: {user_name}",
                (15, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 255, 255),
                2
            )

            cv2.putText(
                preview,
                f"Captured: {captured}/{number_of_images}",
                (15, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0),
                2
            )

            cv2.putText(
                preview,
                "Look at camera and press SPACE",
                (15, 450),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

            cv2.imshow(
                title,
                preview
            )

            key = cv2.waitKey(
                1
            ) & 0xFF

            if key == 27:
                cancelled = True
                break

            if key == 32:
                rgb = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )

                locations = face_recognition.face_locations(
                    rgb,
                    model="hog"
                )

                if len(locations) == 0:
                    print(
                        "No face detected."
                    )
                    continue

                if len(locations) > 1:
                    print(
                        "Multiple faces detected."
                    )
                    continue

                captured += 1

                save_face_image_encrypted(
                    user_name,
                    frame,
                    captured
                )

                time.sleep(
                    0.25
                )

    finally:
        cap.release()

        cv2.destroyAllWindows()

    if cancelled:
        user_dir = os.path.join(
            SECURE_FACES_DIR,
            user_name
        )

        try:
            if os.path.isdir(
                user_dir
            ):
                for file in os.listdir(
                    user_dir
                ):
                    os.remove(
                        os.path.join(
                            user_dir,
                            file
                        )
                    )

                os.rmdir(
                    user_dir
                )

        except Exception:
            pass

        return False

    return captured == number_of_images


# ============================================================
# FACE TRAINING
# ============================================================

def train_face_encodings():
    global known_encodings
    global known_names

    encodings = []
    names = []

    print(
        "Training face database..."
    )

    for user_name in get_users():

        user_dir = os.path.join(
            SECURE_FACES_DIR,
            user_name
        )

        for filename in sorted(
            os.listdir(user_dir)
        ):

            if not filename.lower().endswith(
                ".enc"
            ):
                continue

            path = os.path.join(
                user_dir,
                filename
            )

            try:
                image = decrypt_face_image(
                    path
                )

                rgb = cv2.cvtColor(
                    image,
                    cv2.COLOR_BGR2RGB
                )

                locations = face_recognition.face_locations(
                    rgb,
                    model="hog"
                )

                face_encodings = face_recognition.face_encodings(
                    rgb,
                    locations
                )

                for encoding in face_encodings:
                    encodings.append(
                        encoding
                    )

                    names.append(
                        user_name
                    )

            except Exception as error:
                print(
                    "Training error:",
                    error
                )

    save_face_encodings(
        encodings,
        names
    )

    known_encodings = encodings
    known_names = names

    print(
        f"Training complete: "
        f"{len(encodings)} encodings."
    )

    return len(encodings)


# ============================================================
# REGISTER USER
# ============================================================

def register_user():
    profile = collect_user_profile()

    if not profile:
        return

    name = safe_user_name(
        profile.get(
            "full_name",
            ""
        )
    )

    if not name:
        messagebox.showwarning(
            "Name",
            "Invalid name."
        )
        return

    existing = [
        user.lower()
        for user in get_users()
    ]

    if name.lower() in existing:
        messagebox.showwarning(
            "User Exists",
            "This user is already registered."
        )
        return

    profile[
        "full_name"
    ] = name

    success = capture_user_faces(
        name
    )

    if not success:
        return

    count = train_face_encodings()

    if count <= 0:
        messagebox.showerror(
            "Training",
            "No valid face encoding created."
        )
        return

    try:
        save_user_profile(
            name,
            profile
        )

        log_security_event(
            "FACE_USER_REGISTERED",
            f"User: {name}"
        )

        messagebox.showinfo(
            "Registration Complete",
            (
                f"{name} registered successfully.\n\n"
                "Face images and profile are encrypted."
            )
        )

        refresh_dashboard()

    except Exception as error:
        messagebox.showerror(
            "Registration Error",
            str(error)
        )


# ============================================================
# DELETE USER
# ============================================================

def delete_user():
    users = get_users()

    if not users:
        messagebox.showinfo(
            "Delete",
            "No registered users."
        )
        return

    text = "\n".join(
        f"{i + 1}. {name}"
        for i, name in enumerate(users)
    )

    name = simpledialog.askstring(
        "Delete User",
        (
            "Registered users:\n\n"
            + text
            + "\n\nEnter user name:"
        ),
        parent=root
    )

    if not name:
        return

    selected = None

    for user in users:
        if user.lower() == name.strip().lower():
            selected = user
            break

    if selected is None:
        messagebox.showerror(
            "Delete",
            "User not found."
        )
        return

    if not messagebox.askyesno(
        "Confirm",
        f"Delete '{selected}' and all face data?"
    ):
        return

    try:
        user_dir = os.path.join(
            SECURE_FACES_DIR,
            selected
        )

        if os.path.isdir(
            user_dir
        ):
            for filename in os.listdir(
                user_dir
            ):
                path = os.path.join(
                    user_dir,
                    filename
                )

                if os.path.isfile(path):
                    os.remove(path)

            os.rmdir(
                user_dir
            )

        delete_user_profile(
            selected
        )

        train_face_encodings()

        log_security_event(
            "FACE_USER_DELETED",
            f"User: {selected}"
        )

        messagebox.showinfo(
            "Deleted",
            f"{selected} deleted successfully."
        )

        refresh_dashboard()

    except Exception as error:
        messagebox.showerror(
            "Delete Error",
            str(error)
        )


# ============================================================
# USER PROFILE VIEWER
# ============================================================

def view_user_profiles():
    users = get_users()
    profiles = load_user_profiles()

    window = tk.Toplevel(root)

    window.title(
        "Registered User Profiles"
    )

    window.geometry(
        "1000x680"
    )

    window.configure(
        bg=BG
    )

    tk.Label(
        window,
        text="REGISTERED USER PROFILES",
        font=("Segoe UI", 20, "bold"),
        bg=BG,
        fg=GREEN
    ).pack(
        pady=18
    )

    body = tk.Frame(
        window,
        bg=CARD,
        padx=18,
        pady=18
    )

    body.pack(
        fill="both",
        expand=True,
        padx=22,
        pady=(0, 22)
    )

    left = tk.Frame(
        body,
        bg=CARD
    )

    left.pack(
        side="left",
        fill="y",
        padx=(0, 18)
    )

    right = tk.Frame(
        body,
        bg=CARD2,
        padx=20,
        pady=20
    )

    right.pack(
        side="left",
        fill="both",
        expand=True
    )

    listbox = tk.Listbox(
        left,
        width=28,
        height=25,
        bg=CARD2,
        fg=TEXT,
        selectbackground=GREEN,
        selectforeground="#07111d",
        font=("Segoe UI", 11),
        relief="flat"
    )

    listbox.pack(
        fill="y"
    )

    for user in users:
        listbox.insert(
            "end",
            user
        )

    info = tk.Label(
        right,
        text="Select a user.",
        justify="left",
        anchor="nw",
        bg=CARD2,
        fg=TEXT,
        font=("Segoe UI", 11)
    )

    info.pack(
        fill="both",
        expand=True
    )

    image_label = tk.Label(
        right,
        bg=CARD2
    )

    image_label.pack()

    def show_selected(event=None):
        selection = listbox.curselection()

        if not selection:
            return

        name = listbox.get(
            selection[0]
        )

        profile = profiles.get(
            name,
            {}
        )

        info.config(
            text=(
                f"Name: {profile.get('full_name', name)}\n"
                f"Phone: {profile.get('phone', 'Not provided')}\n"
                f"Email: {profile.get('email', 'Not provided')}\n"
                f"Department: {profile.get('department', 'Not provided')}\n"
                f"Role: {profile.get('role', 'Not provided')}\n"
                f"Registered: {profile.get('registered_at', 'Legacy')}\n\n"
                f"Notes:\n{profile.get('notes', 'None') or 'None'}\n\n"
                "Access: AUTHENTICATED ADMIN"
            )
        )

        image_label.config(
            image=""
        )

        image_label.image = None

        user_dir = os.path.join(
            SECURE_FACES_DIR,
            name
        )

        if not os.path.isdir(
            user_dir
        ):
            return

        files = [
            os.path.join(
                user_dir,
                f
            )
            for f in sorted(
                os.listdir(
                    user_dir
                )
            )
            if f.startswith("face_")
            and f.endswith(".enc")
        ]

        if not files:
            return

        try:
            image = decrypt_face_image(
                files[0]
            )

            image = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2RGB
            )

            pil = Image.fromarray(
                image
            )

            pil.thumbnail(
                (320, 230)
            )

            photo = ImageTk.PhotoImage(
                pil
            )

            image_label.config(
                image=photo
            )

            image_label.image = photo

        except Exception as error:
            print(
                "Profile image error:",
                error
            )

    listbox.bind(
        "<<ListboxSelect>>",
        show_selected
    )

    if users:
        listbox.selection_set(0)
        show_selected()


# ============================================================
# ATTENDANCE
# ============================================================

def read_attendance_rows():
    if not os.path.exists(
        ATTENDANCE_FILE
    ):
        return []

    try:
        data = read_encrypted_file(
            ATTENDANCE_FILE
        )

        return list(
            csv.reader(
                io.StringIO(
                    data.decode("utf-8")
                )
            )
        )

    except Exception:
        return []


def write_attendance_rows(
    rows
):
    output = io.StringIO(
        newline=""
    )

    csv.writer(
        output
    ).writerows(
        rows
    )

    write_encrypted_file(
        ATTENDANCE_FILE,
        output.getvalue().encode(
            "utf-8"
        )
    )


def mark_attendance(name):
    now = datetime.now()

    today = now.strftime(
        "%Y-%m-%d"
    )

    current_time = now.strftime(
        "%H:%M:%S"
    )

    rows = read_attendance_rows()

    if not rows:
        rows = [
            [
                "Name",
                "Date",
                "Time"
            ]
        ]

    for row in rows[1:]:
        if len(row) >= 2:
            if (
                row[0].lower()
                == name.lower()
                and row[1] == today
            ):
                return False

    rows.append(
        [
            name,
            today,
            current_time
        ]
    )

    write_attendance_rows(
        rows
    )

    log_security_event(
        "ATTENDANCE_MARKED",
        (
            f"Name: {name} | "
            f"Date: {today} | "
            f"Time: {current_time}"
        )
    )

    return True


def view_attendance():
    rows = read_attendance_rows()

    window = tk.Toplevel(root)

    window.title(
        "Attendance History"
    )

    window.geometry(
        "760x500"
    )

    window.configure(
        bg=BG
    )

    tk.Label(
        window,
        text="ATTENDANCE HISTORY",
        font=("Segoe UI", 20, "bold"),
        bg=BG,
        fg=GREEN
    ).pack(
        pady=15
    )

    box = tk.Text(
        window,
        bg=CARD,
        fg=TEXT,
        font=("Consolas", 11),
        relief="flat"
    )

    box.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=10
    )

    if not rows:
        box.insert(
            "end",
            "No attendance records."
        )
    else:
        for row in rows:
            box.insert(
                "end",
                " | ".join(row)
                + "\n"
            )

    box.config(
        state="disabled"
    )


# ============================================================
# UNKNOWN FACE INCIDENT
# ============================================================

def create_unknown_incident(
    frame
):
    global last_incident_id

    try:
        timestamp = datetime.now()

        incident_id = (
            "INC-"
            + timestamp.strftime(
                "%Y%m%d-%H%M%S"
            )
            + "-"
            + uuid.uuid4().hex[:6].upper()
        )

        filename = (
            incident_id
            + ".jpg.enc"
        )

        path = os.path.join(
            SECURE_INCIDENTS_DIR,
            filename
        )

        success, buffer = cv2.imencode(
            ".jpg",
            frame,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                95
            ]
        )

        if not success:
            return None

        data = buffer.tobytes()

        write_encrypted_file(
            path,
            data
        )

        if read_encrypted_file(
            path
        ) != data:
            raise ValueError(
                "Snapshot verification failed."
            )

        last_incident_id = incident_id

        log_security_event(
            "UNKNOWN_FACE_DETECTED",
            (
                f"Incident ID: {incident_id} | "
                "Encrypted snapshot created"
            )
        )

        return incident_id

    except Exception as error:
        print(
            "Incident error:",
            error
        )

        log_security_event(
            "INCIDENT_CREATION_ERROR",
            str(error)
        )

        return None


def view_unknown_incidents():
    window = tk.Toplevel(root)

    window.title(
        "Unknown Face Incidents"
    )

    window.geometry(
        "1000x700"
    )

    window.configure(
        bg=BG
    )

    tk.Label(
        window,
        text="UNKNOWN FACE INCIDENTS",
        font=("Segoe UI", 20, "bold"),
        bg=BG,
        fg=RED
    ).pack(
        pady=15
    )

    files = []

    if os.path.isdir(
        SECURE_INCIDENTS_DIR
    ):
        files = sorted(
            [
                f
                for f in os.listdir(
                    SECURE_INCIDENTS_DIR
                )
                if f.endswith(
                    ".jpg.enc"
                )
            ],
            reverse=True
        )

    if not files:
        tk.Label(
            window,
            text="No incidents recorded.",
            font=("Segoe UI", 12),
            bg=BG,
            fg=MUTED
        ).pack(
            pady=50
        )
        return

    content = tk.Frame(
        window,
        bg=BG
    )

    content.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=10
    )

    left = tk.Frame(
        content,
        bg=BG
    )

    left.pack(
        side="left",
        fill="y",
        padx=(0, 15)
    )

    listbox = tk.Listbox(
        left,
        width=34,
        height=28,
        bg=CARD,
        fg=TEXT,
        selectbackground=BLUE,
        font=("Consolas", 10),
        relief="flat"
    )

    listbox.pack(
        fill="y"
    )

    for filename in files:
        listbox.insert(
            "end",
            filename.replace(
                ".jpg.enc",
                ""
            )
        )

    right = tk.Frame(
        content,
        bg="#000000"
    )

    right.pack(
        side="right",
        fill="both",
        expand=True
    )

    image_label = tk.Label(
        right,
        bg="#000000"
    )

    image_label.pack(
        fill="both",
        expand=True
    )

    info = tk.Label(
        window,
        text="Select an incident.",
        bg=BG,
        fg=YELLOW,
        font=("Consolas", 10)
    )

    info.pack(
        pady=10
    )

    def show_selected(event=None):
        selection = listbox.curselection()

        if not selection:
            return

        filename = files[
            selection[0]
        ]

        path = os.path.join(
            SECURE_INCIDENTS_DIR,
            filename
        )

        try:
            data = read_encrypted_file(
                path
            )

            array = np.frombuffer(
                data,
                dtype=np.uint8
            )

            image = cv2.imdecode(
                array,
                cv2.IMREAD_COLOR
            )

            if image is None:
                raise ValueError(
                    "Invalid snapshot."
                )

            image = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2RGB
            )

            pil = Image.fromarray(
                image
            )

            pil.thumbnail(
                (650, 500)
            )

            photo = ImageTk.PhotoImage(
                pil
            )

            image_label.config(
                image=photo
            )

            image_label.image = photo

            info.config(
                text=(
                    f"INCIDENT: "
                    f"{filename.replace('.jpg.enc', '')} "
                    "| ENCRYPTED SNAPSHOT DECRYPTED"
                )
            )

        except Exception as error:
            messagebox.showerror(
                "Snapshot Error",
                str(error),
                parent=window
            )

    listbox.bind(
        "<<ListboxSelect>>",
        show_selected
    )

    listbox.selection_set(0)
    show_selected()


# ============================================================
# LIVENESS
# ============================================================

def eye_aspect_ratio(
    eye
):
    points = np.asarray(
        eye,
        dtype=np.float32
    )

    if len(points) < 6:
        return 1.0

    vertical_1 = np.linalg.norm(
        points[1] - points[5]
    )

    vertical_2 = np.linalg.norm(
        points[2] - points[4]
    )

    horizontal = np.linalg.norm(
        points[0] - points[3]
    )

    if horizontal <= 1e-6:
        return 1.0

    return float(
        (
            vertical_1
            + vertical_2
        )
        / (
            2.0 * horizontal
        )
    )


def calculate_face_ear(
    landmarks
):
    left = landmarks.get(
        "left_eye",
        []
    )

    right = landmarks.get(
        "right_eye",
        []
    )

    if (
        len(left) != 6
        or len(right) != 6
    ):
        return None

    return (
        eye_aspect_ratio(left)
        + eye_aspect_ratio(right)
    ) / 2.0


def reset_liveness():
    global liveness_started_at
    global liveness_verified
    global liveness_closed_frames
    global liveness_was_closed
    global last_liveness_log_time

    liveness_started_at = time.time()

    liveness_verified = False

    liveness_closed_frames = 0

    liveness_was_closed = False

    last_liveness_log_time = 0


def update_liveness(
    ear
):
    global liveness_verified
    global liveness_closed_frames
    global liveness_was_closed

    if liveness_verified:
        return "LIVE"

    if ear is None:
        return "FACE ONLY"

    if ear < BLINK_EAR_THRESHOLD:

        liveness_closed_frames += 1

        if (
            liveness_closed_frames
            >= BLINK_MIN_CLOSED_FRAMES
        ):
            liveness_was_closed = True

    else:

        if liveness_was_closed:
            liveness_verified = True
            liveness_was_closed = False
            liveness_closed_frames = 0

            return "LIVE"

        liveness_closed_frames = 0

    return "BLINK TO VERIFY"


# ============================================================
# FACE ANALYSIS
# ============================================================

def analyze_frame(
    frame
):
    global processing_frame
    global latest_results

    try:
        small = cv2.resize(
            frame,
            (0, 0),
            fx=0.25,
            fy=0.25
        )

        rgb = cv2.cvtColor(
            small,
            cv2.COLOR_BGR2RGB
        )

        locations = face_recognition.face_locations(
            rgb,
            model="hog"
        )

        encodings = face_recognition.face_encodings(
            rgb,
            locations
        )

        landmarks = face_recognition.face_landmarks(
            rgb,
            locations
        )

        results = []

        for i, location in enumerate(
            locations
        ):
            top, right, bottom, left = location

            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            name = "Unknown"

            if (
                i < len(encodings)
                and known_encodings
            ):
                distances = face_recognition.face_distance(
                    known_encodings,
                    encodings[i]
                )

                if len(distances):

                    best = int(
                        np.argmin(
                            distances
                        )
                    )

                    if (
                        float(
                            distances[best]
                        )
                        <= FACE_THRESHOLD
                    ):
                        name = known_names[
                            best
                        ]

            ear = None

            if i < len(landmarks):
                ear = calculate_face_ear(
                    landmarks[i]
                )

            results.append(
                {
                    "name": name,
                    "box": (
                        top,
                        right,
                        bottom,
                        left
                    ),
                    "ear": ear
                }
            )

        with result_lock:
            latest_results = results

    except Exception as error:
        print(
            "Analysis error:",
            error
        )

    finally:
        processing_frame = False


# ============================================================
# SCANNER STOP
# ============================================================

def scanner_stop():
    global camera
    global camera_running
    global scanner_window
    global stable_name
    global stable_count
    global last_recognized_name
    global unknown_alerted
    global latest_results

    camera_running = False

    if camera is not None:
        try:
            camera.release()
        except Exception:
            pass

    camera = None

    with result_lock:
        latest_results = []

    stable_name = ""
    stable_count = 0
    last_recognized_name = ""
    unknown_alerted = False

    reset_liveness()

    try:
        cv2.destroyAllWindows()
    except Exception:
        pass

    if scanner_window is not None:
        try:
            scanner_window.destroy()
        except Exception:
            pass

    scanner_window = None


# ============================================================
# SCANNER UPDATE
# ============================================================

def scanner_update():
    global camera_frame_count
    global processing_frame
    global unknown_alerted
    global stable_name
    global stable_count
    global last_recognized_name
    global latest_results
    global last_liveness_log_time

    if not camera_running:
        return

    if camera is None:
        scanner_stop()
        return

    ret, frame = camera.read()

    if not ret:
        scanner_window.after(
            30,
            scanner_update
        )
        return

    frame = cv2.flip(
        frame,
        1
    )

    camera_frame_count += 1

    # Process every 6th frame in background.
    if (
        camera_frame_count % 6 == 0
        and not processing_frame
    ):
        processing_frame = True

        threading.Thread(
            target=analyze_frame,
            args=(frame.copy(),),
            daemon=True
        ).start()

    with result_lock:
        results = list(
            latest_results
        )

    display = frame.copy()

    found_known = False
    found_unknown = False
    current_name = ""
    best_ear = None

    for result in results:

        name = result["name"]

        top, right, bottom, left = result["box"]

        ear = result.get(
            "ear"
        )

        if name == "Unknown":
            found_unknown = True

            color = (
                255,
                77,
                103
            )

        else:
            found_known = True

            current_name = name

            color = (
                0,
                229,
                160
            )

        if ear is not None:
            best_ear = ear

        cv2.rectangle(
            display,
            (left, top),
            (right, bottom),
            color,
            2
        )

        cv2.rectangle(
            display,
            (
                left,
                max(
                    0,
                    top - 30
                )
            ),
            (
                right,
                top
            ),
            color,
            -1
        )

        cv2.putText(
            display,
            name,
            (
                left + 5,
                top - 8
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (10, 18, 32),
            2
        )

    # --------------------------------------------------------
    # LIVENESS
    # --------------------------------------------------------

    if results:

        liveness = update_liveness(
            best_ear
        )

        if scanner_liveness_label:

            if liveness == "LIVE":
                scanner_liveness_label.config(
                    text="LIVENESS: LIVE",
                    fg=GREEN
                )

            elif liveness == "FACE ONLY":
                scanner_liveness_label.config(
                    text="LIVENESS: FACE DETECTED",
                    fg=YELLOW
                )

            else:
                scanner_liveness_label.config(
                    text="LIVENESS: BLINK TO VERIFY",
                    fg=YELLOW
                )

    else:

        reset_liveness()

        if scanner_liveness_label:
            scanner_liveness_label.config(
                text="LIVENESS: WAITING FOR FACE",
                fg=MUTED
            )

    # --------------------------------------------------------
    # UNKNOWN FACE
    # --------------------------------------------------------

    if found_unknown:

        stable_name = ""
        stable_count = 0
        last_recognized_name = ""

        if scanner_status_label:
            scanner_status_label.config(
                text="UNKNOWN FACE DETECTED",
                fg=RED
            )

        if not unknown_alerted:

            incident_id = create_unknown_incident(
                frame.copy()
            )

            unknown_alerted = True

            if (
                incident_id
                and scanner_incident_label
            ):
                scanner_incident_label.config(
                    text=f"INCIDENT ID: {incident_id}",
                    fg=YELLOW
                )

            try:
                import winsound

                winsound.Beep(
                    1000,
                    500
                )

            except Exception:
                try:
                    root.bell()
                except Exception:
                    pass

    # --------------------------------------------------------
    # KNOWN FACE
    # --------------------------------------------------------

    elif found_known:

        if stable_name == current_name:
            stable_count += 1
        else:
            stable_name = current_name
            stable_count = 1

        if (
            stable_count >= 2
            and liveness_verified
        ):

            if (
                last_recognized_name
                != current_name
            ):

                log_security_event(
                    "KNOWN_FACE_DETECTED",
                    (
                        f"Name: {current_name} | "
                        "Liveness: LIVE"
                    )
                )

                marked = mark_attendance(
                    current_name
                )

                last_recognized_name = (
                    current_name
                )

            if scanner_status_label:
                scanner_status_label.config(
                    text=f"VERIFIED: {current_name}",
                    fg=GREEN
                )

        elif stable_count >= 2:

            if scanner_status_label:
                scanner_status_label.config(
                    text=(
                        f"IDENTIFIED: {current_name} "
                        "- BLINK TO VERIFY"
                    ),
                    fg=YELLOW
                )

            if (
                time.time()
                - liveness_started_at
                > LIVENESS_TIMEOUT_SECONDS
                and
                time.time()
                - last_liveness_log_time
                > LIVENESS_TIMEOUT_SECONDS
            ):

                log_security_event(
                    "LIVENESS_NOT_VERIFIED",
                    f"Candidate: {current_name}"
                )

                last_liveness_log_time = (
                    time.time()
                )

    # --------------------------------------------------------
    # NO FACE
    # --------------------------------------------------------

    else:

        stable_name = ""
        stable_count = 0

        if scanner_status_label:
            scanner_status_label.config(
                text="SCANNING...",
                fg=BLUE
            )

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    if scanner_video_label:

        rgb = cv2.cvtColor(
            display,
            cv2.COLOR_BGR2RGB
        )

        image = Image.fromarray(
            rgb
        )

        image.thumbnail(
            (820, 500)
        )

        photo = ImageTk.PhotoImage(
            image
        )

        scanner_video_label.config(
            image=photo
        )

        scanner_video_label.image = photo

    if (
        camera_running
        and scanner_window is not None
    ):
        scanner_window.after(
            15,
            scanner_update
        )


# ============================================================
# START SCANNER
# ============================================================

def start_scanner():
    global camera
    global camera_running
    global scanner_window
    global scanner_video_label
    global scanner_status_label
    global scanner_incident_label
    global scanner_liveness_label
    global stable_name
    global stable_count
    global last_recognized_name
    global unknown_alerted
    global last_incident_id
    global camera_frame_count

    if camera_running:
        return

    load_face_encodings()

    if not known_encodings:
        messagebox.showwarning(
            "No Face Data",
            "Register a user first."
        )
        return

    camera = open_camera()

    if camera is None:
        messagebox.showerror(
            "Camera",
            "Could not open camera."
        )
        return

    camera_running = True

    stable_name = ""
    stable_count = 0
    last_recognized_name = ""
    unknown_alerted = False
    last_incident_id = ""
    camera_frame_count = 0

    reset_liveness()

    scanner_window = tk.Toplevel(
        root
    )

    scanner_window.title(
        "AI Security - Face Scanner"
    )

    scanner_window.geometry(
        "900x760"
    )

    scanner_window.configure(
        bg=BG
    )

    scanner_window.protocol(
        "WM_DELETE_WINDOW",
        scanner_stop
    )

    tk.Label(
        scanner_window,
        text="AI SECURITY - FACE SCANNER",
        font=("Segoe UI", 20, "bold"),
        bg=BG,
        fg=GREEN
    ).pack(
        pady=(15, 5)
    )

    scanner_status_label = tk.Label(
        scanner_window,
        text="SCANNING...",
        font=("Segoe UI", 14, "bold"),
        bg=BG,
        fg=BLUE
    )

    scanner_status_label.pack()

    scanner_liveness_label = tk.Label(
        scanner_window,
        text="LIVENESS: WAITING FOR FACE",
        font=("Segoe UI", 11, "bold"),
        bg=BG,
        fg=MUTED
    )

    scanner_liveness_label.pack(
        pady=5
    )

    scanner_incident_label = tk.Label(
        scanner_window,
        text="",
        font=("Consolas", 10, "bold"),
        bg=BG,
        fg=YELLOW
    )

    scanner_incident_label.pack()

    tk.Label(
        scanner_window,
        text="Blink once to complete the liveness check.",
        font=("Segoe UI", 10),
        bg=BG,
        fg=MUTED
    ).pack(
        pady=5
    )

    scanner_video_label = tk.Label(
        scanner_window,
        bg="#000000"
    )

    scanner_video_label.pack(
        padx=15,
        pady=10
    )

    tk.Button(
        scanner_window,
        text="STOP SCANNER",
        command=scanner_stop,
        bg=RED,
        fg=WHITE,
        font=("Segoe UI", 11, "bold"),
        relief="flat",
        padx=25,
        pady=10
    ).pack(
        pady=10
    )

    scanner_update()


# ============================================================
# ACCOUNT CREATION WINDOW
# ============================================================

def create_account_window():
    window = tk.Toplevel(root)

    window.title(
        "Create User Account"
    )

    window.geometry(
        "520x470"
    )

    window.configure(
        bg=BG
    )

    window.transient(root)
    window.grab_set()

    tk.Label(
        window,
        text="CREATE USER ACCOUNT",
        font=("Segoe UI", 21, "bold"),
        bg=BG,
        fg=GREEN
    ).pack(
        pady=(25, 5)
    )

    tk.Label(
        window,
        text=(
            "Create an account for application access."
        ),
        font=("Segoe UI", 9),
        bg=BG,
        fg=MUTED
    ).pack(
        pady=(0, 20)
    )

    card = tk.Frame(
        window,
        bg=CARD,
        padx=30,
        pady=25
    )

    card.pack(
        fill="both",
        expand=True,
        padx=35,
        pady=(0, 30)
    )

    tk.Label(
        card,
        text="Username",
        bg=CARD,
        fg=TEXT
    ).pack(
        anchor="w"
    )

    username = tk.Entry(
        card,
        bg=CARD2,
        fg=WHITE,
        insertbackground=WHITE,
        relief="flat"
    )

    username.pack(
        fill="x",
        pady=(5, 15),
        ipady=7
    )

    tk.Label(
        card,
        text="Password",
        bg=CARD,
        fg=TEXT
    ).pack(
        anchor="w"
    )

    password = tk.Entry(
        card,
        show="*",
        bg=CARD2,
        fg=WHITE,
        insertbackground=WHITE,
        relief="flat"
    )

    password.pack(
        fill="x",
        pady=(5, 15),
        ipady=7
    )

    tk.Label(
        card,
        text="Confirm Password",
        bg=CARD,
        fg=TEXT
    ).pack(
        anchor="w"
    )

    confirm = tk.Entry(
        card,
        show="*",
        bg=CARD2,
        fg=WHITE,
        insertbackground=WHITE,
        relief="flat"
    )

    confirm.pack(
        fill="x",
        pady=(5, 15),
        ipady=7
    )

    def create():
        user = username.get().strip()
        p1 = password.get()
        p2 = confirm.get()

        if p1 != p2:
            messagebox.showwarning(
                "Password",
                "Passwords do not match.",
                parent=window
            )
            return

        success, message = create_user_account(
            user,
            p1,
            "USER"
        )

        if success:
            messagebox.showinfo(
                "Account Created",
                message,
                parent=window
            )

            window.destroy()

        else:
            messagebox.showwarning(
                "Account",
                message,
                parent=window
            )

    tk.Button(
        card,
        text="CREATE ACCOUNT",
        command=create,
        bg=GREEN,
        fg="#07111d",
        font=("Segoe UI", 11, "bold"),
        relief="flat",
        pady=10
    ).pack(
        fill="x",
        pady=5
    )


# ============================================================
# ACCOUNT MANAGEMENT
# ============================================================

def manage_accounts():
    accounts = load_user_accounts()

    window = tk.Toplevel(root)

    window.title(
        "User Account Management"
    )

    window.geometry(
        "700x560"
    )

    window.configure(
        bg=BG
    )

    tk.Label(
        window,
        text="USER ACCOUNT MANAGEMENT",
        font=("Segoe UI", 20, "bold"),
        bg=BG,
        fg=GREEN
    ).pack(
        pady=20
    )

    listbox = tk.Listbox(
        window,
        bg=CARD,
        fg=TEXT,
        selectbackground=GREEN,
        selectforeground="#07111d",
        font=("Consolas", 11),
        relief="flat"
    )

    listbox.pack(
        fill="both",
        expand=True,
        padx=30,
        pady=10
    )

    def refresh():
        listbox.delete(
            0,
            "end"
        )

        accounts = load_user_accounts()

        for key, account in sorted(
            accounts.items()
        ):
            listbox.insert(
                "end",
                (
                    f"{account.get('username', key)} "
                    f"| Role: {account.get('role', 'USER')} "
                    f"| Created: "
                    f"{account.get('created_at', '-')}"
                )
            )

    refresh()

    buttons = tk.Frame(
        window,
        bg=BG
    )

    buttons.pack(
        pady=15
    )

    def delete_selected():
        selection = listbox.curselection()

        if not selection:
            return

        line = listbox.get(
            selection[0]
        )

        username = line.split(
            "|"
        )[0].strip()

        if not messagebox.askyesno(
            "Delete Account",
            f"Delete account '{username}'?",
            parent=window
        ):
            return

        delete_user_account(
            username
        )

        refresh()

    tk.Button(
        buttons,
        text="CREATE ACCOUNT",
        command=create_account_window,
        bg=GREEN,
        fg="#07111d",
        relief="flat",
        padx=18,
        pady=9
    ).pack(
        side="left",
        padx=5
    )

    tk.Button(
        buttons,
        text="DELETE ACCOUNT",
        command=delete_selected,
        bg=RED,
        fg=WHITE,
        relief="flat",
        padx=18,
        pady=9
    ).pack(
        side="left",
        padx=5
    )


# ============================================================
# DASHBOARD
# ============================================================

dashboard_user_count_label = None


def refresh_dashboard():
    if dashboard_user_count_label:
        dashboard_user_count_label.config(
            text=(
                f"Registered Face Users: "
                f"{len(get_users())}"
            )
        )


def clear_root():
    for widget in root.winfo_children():
        widget.destroy()


def logout():
    global current_user
    global current_user_role

    log_security_event(
        "LOGOUT",
        f"User: {current_user or 'ADMIN'}"
    )

    current_user = None
    current_user_role = None

    show_login()


def show_dashboard():
    clear_root()

    root.title(
        APP_TITLE
    )

    root.geometry(
        "820x820"
    )

    root.configure(
        bg=BG
    )

    root.resizable(
        False,
        False
    )

    header = tk.Frame(
        root,
        bg=BG
    )

    header.pack(
        fill="x",
        padx=30,
        pady=(22, 8)
    )

    tk.Label(
        header,
        text="AI SECURITY",
        font=("Segoe UI", 28, "bold"),
        bg=BG,
        fg=GREEN
    ).pack()

    tk.Label(
        header,
        text=(
            "FACE RECOGNITION "
            "& SECURITY SYSTEM"
        ),
        font=("Segoe UI", 12),
        bg=BG,
        fg=MUTED
    ).pack()

    session_text = (
        f"Logged in as: "
        f"{current_user or 'ADMIN'}"
    )

    tk.Label(
        header,
        text=session_text,
        font=("Segoe UI", 10, "bold"),
        bg=BG,
        fg=YELLOW
    ).pack(
        pady=5
    )

    card = tk.Frame(
        root,
        bg=CARD,
        padx=25,
        pady=22
    )

    card.pack(
        fill="both",
        expand=True,
        padx=30,
        pady=12
    )

    global dashboard_user_count_label

    dashboard_user_count_label = tk.Label(
        card,
        text=(
            f"Registered Face Users: "
            f"{len(get_users())}"
        ),
        font=("Segoe UI", 15, "bold"),
        bg=CARD,
        fg=TEXT
    )

    dashboard_user_count_label.pack(
        pady=(0, 7)
    )

    tk.Label(
        card,
        text="AES-256-GCM ENCRYPTED STORAGE ACTIVE",
        font=("Segoe UI", 10, "bold"),
        bg=CARD,
        fg=GREEN
    ).pack(
        pady=(0, 12)
    )

    def make_button(
        text,
        command,
        color=BLUE
    ):
        return tk.Button(
            card,
            text=text,
            command=command,
            bg=color,
            fg=WHITE,
            activebackground=color,
            activeforeground=WHITE,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            pady=9,
            cursor="hand2"
        )

    make_button(
        "START FACE SCANNER",
        start_scanner,
        GREEN
    ).pack(
        fill="x",
        pady=4
    )

    make_button(
        "REGISTER FACE USER",
        register_user,
        BLUE
    ).pack(
        fill="x",
        pady=4
    )

    make_button(
        "DELETE FACE USER",
        delete_user,
        RED
    ).pack(
        fill="x",
        pady=4
    )

    make_button(
        "VIEW USER PROFILES",
        view_user_profiles,
        BLUE
    ).pack(
        fill="x",
        pady=4
    )

    make_button(
        "VIEW ATTENDANCE",
        view_attendance,
        BLUE
    ).pack(
        fill="x",
        pady=4
    )

    make_button(
        "VIEW SECURITY EVENTS",
        view_security_log,
        YELLOW
    ).pack(
        fill="x",
        pady=4
    )

    make_button(
        "VIEW UNKNOWN FACE INCIDENTS",
        view_unknown_incidents,
        RED
    ).pack(
        fill="x",
        pady=4
    )

    make_button(
        "USER ACCOUNT MANAGEMENT",
        manage_accounts,
        BLUE
    ).pack(
        fill="x",
        pady=4
    )

    if (
        current_user
        and current_user_role == "USER"
    ):
        make_button(
            "CHANGE MY PASSWORD",
            lambda: change_user_password(
                current_user
            ),
            BLUE
        ).pack(
            fill="x",
            pady=4
        )

    make_button(
        "LOGOUT",
        logout,
        YELLOW
    ).pack(
        fill="x",
        pady=(12, 4)
    )

    make_button(
        "EXIT",
        root.destroy,
        RED
    ).pack(
        fill="x",
        pady=4
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

def admin_login():
    global admin_failed_attempts
    global admin_locked_until
    global admin_progressive_level
    global current_user
    global current_user_role

    now = time.time()

    if now < admin_locked_until:

        remaining = int(
            admin_locked_until - now
        ) + 1

        login_status.config(
            text=(
                f"ADMIN LOCKED - "
                f"{remaining} seconds remaining"
            ),
            fg=RED
        )

        root.after(
            1000,
            admin_login
        )

        return

    password = password_entry.get()

    password_entry.delete(
        0,
        "end"
    )

    if (
        hash_password(password)
        == ADMIN_PASSWORD_HASH
    ):

        admin_failed_attempts = 0
        admin_locked_until = 0
        admin_progressive_level = 0

        current_user = None
        current_user_role = "ADMIN"

        log_security_event(
            "ADMIN_LOGIN_SUCCESS",
            "Admin authentication successful"
        )

        show_dashboard()

        return

    admin_failed_attempts += 1

    log_security_event(
        "ADMIN_LOGIN_FAILED",
        (
            f"Attempt: "
            f"{admin_failed_attempts}/"
            f"{MAX_LOGIN_ATTEMPTS}"
        )
    )

    if (
        admin_failed_attempts
        >= MAX_LOGIN_ATTEMPTS
    ):

        admin_progressive_level += 1

        level = admin_progressive_level

        if level == 1:
            lockout = 5 * 60
        elif level == 2:
            lockout = 15 * 60
        elif level == 3:
            lockout = 30 * 60
        else:
            lockout = MAX_LOCKOUT_SECONDS

        admin_locked_until = (
            time.time()
            + lockout
        )

        admin_failed_attempts = 0

        log_security_event(
            "ADMIN_LOGIN_LOCKOUT",
            (
                f"Level: {level} | "
                f"Lockout: {lockout} seconds"
            )
        )

        login_status.config(
            text=(
                f"ADMIN LOCKED - "
                f"{lockout // 60} minutes"
            ),
            fg=RED
        )

    else:

        remaining = (
            MAX_LOGIN_ATTEMPTS
            - admin_failed_attempts
        )

        login_status.config(
            text=(
                f"Wrong password. "
                f"{remaining} attempt(s) remaining."
            ),
            fg=RED
        )


# ============================================================
# USER LOGIN
# ============================================================

def user_login():
    global current_user
    global current_user_role

    username = username_entry.get().strip()
    password = password_entry.get()

    password_entry.delete(
        0,
        "end"
    )

    if not username or not password:
        login_status.config(
            text="Enter username and password.",
            fg=RED
        )
        return

    success, result = verify_user_account(
        username,
        password
    )

    if success:

        current_user = result.get(
            "username",
            username
        )

        current_user_role = result.get(
            "role",
            "USER"
        )

        log_security_event(
            "USER_LOGIN_SUCCESS",
            f"Username: {current_user}"
        )

        show_dashboard()

    else:

        log_security_event(
            "USER_LOGIN_FAILED",
            f"Username: {username}"
        )

        login_status.config(
            text=result,
            fg=RED
        )


# ============================================================
# LOGIN MODE SWITCH
# ============================================================

login_mode = "ADMIN"


def switch_login_mode():
    global login_mode

    if login_mode == "ADMIN":
        login_mode = "USER"

        username_entry.pack(
            fill="x",
            pady=(5, 10),
            ipady=8,
            before=password_entry
        )

        mode_button.config(
            text="SWITCH TO ADMIN LOGIN"
        )

        title_label.config(
            text="USER LOGIN"
        )

    else:
        login_mode = "ADMIN"

        username_entry.pack_forget()

        mode_button.config(
            text="SWITCH TO USER LOGIN"
        )

        title_label.config(
            text="ADMIN LOGIN"
        )


def perform_login():
    if login_mode == "ADMIN":
        admin_login()
    else:
        user_login()


# ============================================================
# LOGIN SCREEN
# ============================================================

def show_login():
    clear_root()

    root.title(
        APP_TITLE + " - Login"
    )

    root.geometry(
        "540x600"
    )

    root.configure(
        bg=BG
    )

    root.resizable(
        False,
        False
    )

    card = tk.Frame(
        root,
        bg=CARD,
        padx=40,
        pady=30
    )

    card.pack(
        fill="both",
        expand=True,
        padx=45,
        pady=35
    )

    tk.Label(
        card,
        text="AI SECURITY",
        font=("Segoe UI", 27, "bold"),
        bg=CARD,
        fg=GREEN
    ).pack(
        pady=(0, 5)
    )

    global title_label

    title_label = tk.Label(
        card,
        text="ADMIN LOGIN",
        font=("Segoe UI", 13, "bold"),
        bg=CARD,
        fg=TEXT
    )

    title_label.pack(
        pady=(0, 22)
    )

    global username_entry
    global password_entry
    global login_status
    global mode_button

    tk.Label(
        card,
        text="Username",
        font=("Segoe UI", 10),
        bg=CARD,
        fg=MUTED
    ).pack(
        anchor="w"
    )

    username_entry = tk.Entry(
        card,
        font=("Segoe UI", 12),
        bg=CARD2,
        fg=WHITE,
        insertbackground=WHITE,
        relief="flat"
    )

    # Hidden in admin mode.
    if login_mode == "USER":
        username_entry.pack(
            fill="x",
            pady=(5, 10),
            ipady=8
        )

    tk.Label(
        card,
        text="Password",
        font=("Segoe UI", 10),
        bg=CARD,
        fg=MUTED
    ).pack(
        anchor="w"
    )

    password_entry = tk.Entry(
        card,
        show="*",
        font=("Segoe UI", 12),
        bg=CARD2,
        fg=WHITE,
        insertbackground=WHITE,
        relief="flat"
    )

    password_entry.pack(
        fill="x",
        pady=(5, 15),
        ipady=8
    )

    password_entry.bind(
        "<Return>",
        lambda event: perform_login()
    )

    tk.Button(
        card,
        text="LOGIN",
        command=perform_login,
        bg=GREEN,
        fg="#07111d",
        font=("Segoe UI", 11, "bold"),
        relief="flat",
        pady=10,
        cursor="hand2"
    ).pack(
        fill="x"
    )

    login_status = tk.Label(
        card,
        text="",
        font=("Segoe UI", 10, "bold"),
        bg=CARD,
        fg=RED
    )

    login_status.pack(
        pady=12
    )

    mode_button = tk.Button(
        card,
        text=(
            "SWITCH TO ADMIN LOGIN"
            if login_mode == "USER"
            else "SWITCH TO USER LOGIN"
        ),
        command=switch_login_mode,
        bg=CARD2,
        fg=TEXT,
        font=("Segoe UI", 9, "bold"),
        relief="flat",
        pady=8
    )

    mode_button.pack(
        fill="x",
        pady=4
    )

    tk.Button(
        card,
        text="CREATE NEW USER ACCOUNT",
        command=create_account_window,
        bg=BLUE,
        fg=WHITE,
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        pady=9
    ).pack(
        fill="x",
        pady=8
    )

    tk.Label(
        card,
        text=(
            "AES-256-GCM encrypted storage\n"
            "Basic blink-based liveness protection"
        ),
        font=("Segoe UI", 9),
        bg=CARD,
        fg=MUTED
    ).pack(
        pady=10
    )


# ============================================================
# LEGACY MIGRATION
# ============================================================

def encrypt_plain_file(
    plain_path,
    encrypted_path
):
    try:
        with open(
            plain_path,
            "rb"
        ) as file:
            data = file.read()

        write_encrypted_file(
            encrypted_path,
            data
        )

        if read_encrypted_file(
            encrypted_path
        ) != data:
            raise ValueError(
                "Encryption verification failed."
            )

        os.remove(
            plain_path
        )

    except Exception as error:
        print(
            "Migration error:",
            error
        )


def migrate_existing_data():

    migrate = [
        (
            LEGACY_ENCODINGS_FILE,
            ENCODINGS_FILE
        ),
        (
            LEGACY_ATTENDANCE_FILE,
            ATTENDANCE_FILE
        ),
        (
            LEGACY_SECURITY_LOG_FILE,
            SECURITY_LOG_FILE
        )
    ]

    for old, new in migrate:
        if (
            os.path.exists(old)
            and not os.path.exists(new)
        ):
            encrypt_plain_file(
                old,
                new
            )

    # Migrate face images.
    if os.path.isdir(
        LEGACY_KNOWN_FACES_DIR
    ):

        for username in os.listdir(
            LEGACY_KNOWN_FACES_DIR
        ):

            old_dir = os.path.join(
                LEGACY_KNOWN_FACES_DIR,
                username
            )

            if not os.path.isdir(
                old_dir
            ):
                continue

            safe = safe_user_name(
                username
            )

            if not safe:
                continue

            new_dir = os.path.join(
                SECURE_FACES_DIR,
                safe
            )

            os.makedirs(
                new_dir,
                exist_ok=True
            )

            for filename in os.listdir(
                old_dir
            ):

                old_file = os.path.join(
                    old_dir,
                    filename
                )

                if not os.path.isfile(
                    old_file
                ):
                    continue

                ext = os.path.splitext(
                    filename
                )[1].lower()

                if ext not in {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".bmp"
                }:
                    continue

                new_file = os.path.join(
                    new_dir,
                    filename + ".enc"
                )

                if os.path.exists(
                    new_file
                ):
                    continue

                try:
                    with open(
                        old_file,
                        "rb"
                    ) as file:
                        data = file.read()

                    write_encrypted_file(
                        new_file,
                        data
                    )

                    if read_encrypted_file(
                        new_file
                    ) == data:
                        os.remove(
                            old_file
                        )

                except Exception as error:
                    print(
                        "Face migration error:",
                        error
                    )

    # Migrate unknown incidents.
    if os.path.isdir(
        LEGACY_INCIDENTS_DIR
    ):

        for filename in os.listdir(
            LEGACY_INCIDENTS_DIR
        ):

            old_file = os.path.join(
                LEGACY_INCIDENTS_DIR,
                filename
            )

            if not os.path.isfile(
                old_file
            ):
                continue

            ext = os.path.splitext(
                filename
            )[1].lower()

            if ext not in {
                ".jpg",
                ".jpeg",
                ".png"
            }:
                continue

            new_file = os.path.join(
                SECURE_INCIDENTS_DIR,
                filename + ".enc"
            )

            if os.path.exists(
                new_file
            ):
                continue

            try:
                with open(
                    old_file,
                    "rb"
                ) as file:
                    data = file.read()

                write_encrypted_file(
                    new_file,
                    data
                )

                if read_encrypted_file(
                    new_file
                ) == data:
                    os.remove(
                        old_file
                    )

            except Exception as error:
                print(
                    "Incident migration error:",
                    error
                )


# ============================================================
# MAIN
# ============================================================

def main():
    global root

    print("=" * 65)
    print(
        "AI SECURITY - FACE RECOGNITION"
    )
    print("=" * 65)

    print(
        "Initializing AES-256-GCM..."
    )

    load_encryption_key()

    migrate_existing_data()

    load_face_encodings()

    root = tk.Tk()

    root.protocol(
        "WM_DELETE_WINDOW",
        root.destroy
    )

    log_security_event(
        "SYSTEM_START",
        (
            "AI Security started | "
            "AES-256-GCM active | "
            "User account system active"
        )
    )

    show_login()

    root.mainloop()


if __name__ == "__main__":
    main()