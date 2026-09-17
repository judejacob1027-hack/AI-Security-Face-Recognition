# COMPLETE app.py
# AI SECURITY - FACE RECOGNITION
# Includes encrypted storage, login brute-force protection,
# face recognition, unknown-face encrypted snapshots + viewer,
# attendance, security logs, and a basic blink-based liveness challenge.
#
# IMPORTANT:
# The blink-based liveness check is a basic anti-spoof layer.
# It is NOT a high-assurance biometric anti-spoofing system.

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


APP_TITLE = "AI SECURITY - FACE RECOGNITION"

SECURE_DIR = "secure_data"
SECURE_FACES_DIR = os.path.join(SECURE_DIR, "known_faces")
SECURE_INCIDENTS_DIR = os.path.join(SECURE_DIR, "security_incidents")
ENCODINGS_FILE = os.path.join(SECURE_DIR, "face_encodings.pkl.enc")
ATTENDANCE_FILE = os.path.join(SECURE_DIR, "attendance.csv.enc")
SECURITY_LOG_FILE = os.path.join(SECURE_DIR, "security_events.csv.enc")
USER_PROFILES_FILE = os.path.join(SECURE_DIR, "user_profiles.pkl.enc")
ENCRYPTION_KEY_FILE = "vault.key"

LEGACY_KNOWN_FACES_DIR = "known_faces"
LEGACY_ENCODINGS_FILE = "face_encodings.pkl"
LEGACY_ATTENDANCE_FILE = "attendance.csv"
LEGACY_SECURITY_LOG_FILE = "security_events.csv"
LEGACY_INCIDENTS_DIR = "security_incidents"

ADMIN_PASSWORD = "admin123"
FACE_THRESHOLD = 0.48


# ============================================================
# BRUTE-FORCE PROTECTION
# ============================================================

# Maximum failed attempts before a lockout.
MAX_LOGIN_ATTEMPTS = 2

# Progressive lockout schedule:
# Level 1 = 5 minutes
# Level 2 = 15 minutes
# Level 3 = 30 minutes
# Level 4+ = 60 minutes maximum.
INITIAL_LOCKOUT_SECONDS = 5 * 60
MAX_LOCKOUT_SECONDS = 60 * 60


# Basic blink/liveness settings
BLINK_EAR_THRESHOLD = 0.21
BLINK_MIN_CLOSED_FRAMES = 2
LIVENESS_TIMEOUT_SECONDS = 8

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

os.makedirs(SECURE_DIR, exist_ok=True)
os.makedirs(SECURE_FACES_DIR, exist_ok=True)
os.makedirs(SECURE_INCIDENTS_DIR, exist_ok=True)

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

# Login security state
login_failed_attempts = 0
login_locked_until = 0
progressive_lock_level = 0

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
# AES-256-GCM ENCRYPTION
# ============================================================

def create_encryption_key():
    if not os.path.exists(ENCRYPTION_KEY_FILE):
        key = AESGCM.generate_key(bit_length=256)

        with open(ENCRYPTION_KEY_FILE, "wb") as file:
            file.write(key)

        print("AES-256 encryption key created.")


def load_encryption_key():
    if not os.path.exists(ENCRYPTION_KEY_FILE):
        create_encryption_key()

    with open(ENCRYPTION_KEY_FILE, "rb") as file:
        key = file.read()

    if len(key) != 32:
        raise ValueError(
            "Invalid encryption key. vault.key must contain 32 bytes."
        )

    return key


ENCRYPTION_KEY = load_encryption_key()


def encrypt_data(data):
    aes = AESGCM(ENCRYPTION_KEY)

    nonce = secrets.token_bytes(NONCE_SIZE)

    encrypted = aes.encrypt(
        nonce,
        data,
        MAGIC
    )

    return MAGIC + nonce + encrypted


def decrypt_data(data):
    if not data.startswith(MAGIC):
        raise ValueError(
            "File is not a valid encrypted AI Security file."
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

    aes = AESGCM(ENCRYPTION_KEY)

    return aes.decrypt(
        nonce,
        encrypted,
        MAGIC
    )


def write_encrypted_file(path, data):
    encrypted = encrypt_data(data)

    temp_path = path + ".tmp"

    with open(temp_path, "wb") as file:
        file.write(encrypted)

    os.replace(
        temp_path,
        path
    )


def read_encrypted_file(path):
    with open(path, "rb") as file:
        encrypted = file.read()

    return decrypt_data(encrypted)


def encrypt_plain_file(plain_path, encrypted_path):
    with open(plain_path, "rb") as file:
        data = file.read()

    write_encrypted_file(
        encrypted_path,
        data
    )

    check = read_encrypted_file(
        encrypted_path
    )

    if check != data:
        raise ValueError(
            "Encryption verification failed."
        )

    os.remove(plain_path)


# ============================================================
# SAFE NAME / DATA MIGRATION
# ============================================================

def safe_user_name(name):
    name = str(name).strip()

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

    if not name or name in {".", ".."}:
        return ""

    return name[:80]


def migrate_single_file(
    legacy_path,
    encrypted_path
):
    if (
        os.path.exists(legacy_path)
        and not os.path.exists(encrypted_path)
    ):
        try:
            encrypt_plain_file(
                legacy_path,
                encrypted_path
            )

            print(
                f"Migrated: "
                f"{legacy_path} -> {encrypted_path}"
            )

        except Exception as error:
            print(
                f"Migration failed for "
                f"{legacy_path}: {error}"
            )


def migrate_known_faces():
    if not os.path.isdir(
        LEGACY_KNOWN_FACES_DIR
    ):
        return

    for user_name in os.listdir(
        LEGACY_KNOWN_FACES_DIR
    ):
        old_user_dir = os.path.join(
            LEGACY_KNOWN_FACES_DIR,
            user_name
        )

        if not os.path.isdir(old_user_dir):
            continue

        safe_name = safe_user_name(
            user_name
        )

        if not safe_name:
            continue

        secure_user_dir = os.path.join(
            SECURE_FACES_DIR,
            safe_name
        )

        os.makedirs(
            secure_user_dir,
            exist_ok=True
        )

        for filename in os.listdir(
            old_user_dir
        ):
            old_file = os.path.join(
                old_user_dir,
                filename
            )

            if not os.path.isfile(old_file):
                continue

            extension = os.path.splitext(
                filename
            )[1].lower()

            if extension not in {
                ".jpg",
                ".jpeg",
                ".png",
                ".bmp"
            }:
                continue

            secure_filename = (
                filename
                + ".enc"
            )

            secure_file = os.path.join(
                secure_user_dir,
                secure_filename
            )

            try:
                if not os.path.exists(
                    secure_file
                ):
                    with open(
                        old_file,
                        "rb"
                    ) as file:
                        data = file.read()

                    write_encrypted_file(
                        secure_file,
                        data
                    )

                    if (
                        read_encrypted_file(
                            secure_file
                        ) == data
                    ):
                        os.remove(
                            old_file
                        )

            except Exception as error:
                print(
                    f"Face migration error: "
                    f"{old_file} | {error}"
                )

        try:
            if (
                os.path.isdir(old_user_dir)
                and not os.listdir(old_user_dir)
            ):
                os.rmdir(
                    old_user_dir
                )

        except Exception:
            pass

    try:
        if (
            os.path.isdir(
                LEGACY_KNOWN_FACES_DIR
            )
            and not os.listdir(
                LEGACY_KNOWN_FACES_DIR
            )
        ):
            os.rmdir(
                LEGACY_KNOWN_FACES_DIR
            )

    except Exception:
        pass


def migrate_incidents():
    if not os.path.isdir(
        LEGACY_INCIDENTS_DIR
    ):
        return

    for filename in os.listdir(
        LEGACY_INCIDENTS_DIR
    ):
        old_file = os.path.join(
            LEGACY_INCIDENTS_DIR,
            filename
        )

        if not os.path.isfile(old_file):
            continue

        extension = os.path.splitext(
            filename
        )[1].lower()

        if extension not in {
            ".jpg",
            ".jpeg",
            ".png"
        }:
            continue

        secure_file = os.path.join(
            SECURE_INCIDENTS_DIR,
            filename + ".enc"
        )

        try:
            if not os.path.exists(
                secure_file
            ):
                with open(
                    old_file,
                    "rb"
                ) as file:
                    data = file.read()

                write_encrypted_file(
                    secure_file,
                    data
                )

                if (
                    read_encrypted_file(
                        secure_file
                    ) == data
                ):
                    os.remove(
                        old_file
                    )

        except Exception as error:
            print(
                f"Incident migration error: "
                f"{error}"
            )

    try:
        if (
            os.path.isdir(
                LEGACY_INCIDENTS_DIR
            )
            and not os.listdir(
                LEGACY_INCIDENTS_DIR
            )
        ):
            os.rmdir(
                LEGACY_INCIDENTS_DIR
            )

    except Exception:
        pass


def migrate_existing_data():
    migrate_single_file(
        LEGACY_ENCODINGS_FILE,
        ENCODINGS_FILE
    )

    migrate_single_file(
        LEGACY_ATTENDANCE_FILE,
        ATTENDANCE_FILE
    )

    migrate_single_file(
        LEGACY_SECURITY_LOG_FILE,
        SECURITY_LOG_FILE
    )

    migrate_known_faces()
    migrate_incidents()


# ============================================================
# SECURITY EVENT LOG
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
                            data.decode("utf-8")
                        )
                    )
                )

            except Exception as error:
                print(
                    "Existing security log "
                    f"read error: {error}"
                )

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
        ).writerows(rows)

        write_encrypted_file(
            SECURITY_LOG_FILE,
            output.getvalue().encode(
                "utf-8"
            )
        )

        print(
            f"[SECURITY LOG] "
            f"{event_type} | {details}"
        )

    except Exception as error:
        print(
            "Security log error:",
            error
        )


# ============================================================
# PASSWORD AUTHENTICATION
# ============================================================

def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


ADMIN_PASSWORD_HASH = hash_password(
    ADMIN_PASSWORD
)


def verify_admin_password(password):
    return (
        hash_password(password)
        == ADMIN_PASSWORD_HASH
    )


# ============================================================
# FACE ENCODINGS
# ============================================================

def save_face_encodings(
    encodings,
    names
):
    payload = pickle.dumps(
        {
            "encodings": encodings,
            "names": names
        }
    )

    write_encrypted_file(
        ENCODINGS_FILE,
        payload
    )


def load_face_encodings():
    global known_encodings
    global known_names

    known_encodings = []
    known_names = []

    if not os.path.exists(
        ENCODINGS_FILE
    ):
        print(
            "No encrypted face encodings found."
        )

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
            f"Loaded "
            f"{len(known_encodings)} "
            f"encrypted face encodings."
        )

        return len(
            known_encodings
        ) > 0

    except Exception as error:
        print(
            "Encoding load error:",
            error
        )

        return False


# ============================================================
# USER STORAGE
# ============================================================

def get_users():
    users = []

    if not os.path.isdir(
        SECURE_FACES_DIR
    ):
        return users

    for name in os.listdir(
        SECURE_FACES_DIR
    ):
        path = os.path.join(
            SECURE_FACES_DIR,
            name
        )

        if os.path.isdir(path):
            users.append(name)

    users.sort(
        key=str.lower
    )

    return users


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
            "Could not encode face image."
        )

    filename = (
        f"face_{index:02d}.jpg.enc"
    )

    path = os.path.join(
        user_dir,
        filename
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
            "Could not decode encrypted face image."
        )

    return image


# ============================================================
# ENCRYPTED USER PROFILES
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

        profiles = pickle.loads(
            data
        )

        return (
            profiles
            if isinstance(
                profiles,
                dict
            )
            else {}
        )

    except Exception as error:
        print(
            "User profile read error:",
            error
        )

        return {}


def save_user_profiles(profiles):
    data = pickle.dumps(
        profiles,
        protocol=pickle.HIGHEST_PROTOCOL
    )

    write_encrypted_file(
        USER_PROFILES_FILE,
        data
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


def get_user_profile(name):
    profiles = load_user_profiles()

    return profiles.get(
        name,
        {}
    )


def delete_user_profile(name):
    profiles = load_user_profiles()

    if name in profiles:
        del profiles[name]

        save_user_profiles(
            profiles
        )


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
        "Register User - Personal Details"
    )

    window.geometry(
        "560x530"
    )

    window.configure(
        bg=BG
    )

    window.resizable(
        False,
        False
    )

    window.transient(root)
    window.grab_set()

    tk.Label(
        window,
        text="USER PROFILE",
        font=("Segoe UI", 20, "bold"),
        bg=BG,
        fg=GREEN
    ).pack(
        pady=(22, 4)
    )

    tk.Label(
        window,
        text=(
            "Details will be stored using "
            "AES-256-GCM encryption."
        ),
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
        label_text,
        key
    ) in enumerate(fields):

        tk.Label(
            form,
            text=label_text,
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
                width=35,
                bg=CARD2,
                fg=WHITE,
                insertbackground=WHITE,
                relief="flat"
            )

        else:
            widget = tk.Entry(
                form,
                width=37,
                font=("Segoe UI", 10),
                bg=CARD2,
                fg=WHITE,
                insertbackground=WHITE,
                relief="flat"
            )

        widget.grid(
            row=row,
            column=1,
            sticky="ew",
            padx=(15, 0),
            pady=6,
            ipady=(
                5
                if key != "notes"
                else 0
            )
        )

        entries[key] = widget

    form.columnconfigure(
        1,
        weight=1
    )

    def submit():
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

        if not result["full_name"]:
            messagebox.showwarning(
                "Missing Name",
                "Full Name is required.",
                parent=window
            )

            return

        if (
            result["email"]
            and (
                "@"
                not in result["email"]
                or "."
                not in result["email"].split("@")[-1]
            )
        ):
            messagebox.showwarning(
                "Invalid Email",
                "Please enter a valid email address.",
                parent=window
            )

            return

        result["registered_at"] = (
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        result["profile_version"] = 1

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
        activebackground=GREEN,
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        padx=18,
        pady=10,
        cursor="hand2"
    ).pack(
        side="left",
        padx=6
    )

    tk.Button(
        buttons,
        text="CANCEL",
        command=cancel,
        bg=CARD2,
        fg=TEXT,
        activebackground=CARD2,
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        padx=18,
        pady=10,
        cursor="hand2"
    ).pack(
        side="left",
        padx=6
    )

    root.wait_window(window)

    return result if result else None


def view_user_profiles():
    users = get_users()
    profiles = load_user_profiles()

    window = tk.Toplevel(root)

    window.title(
        "Registered User Profiles"
    )

    window.geometry(
        "980x650"
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
        pady=(18, 5)
    )

    tk.Label(
        window,
        text=(
            "Profiles and face images are "
            "protected by encrypted storage."
        ),
        font=("Segoe UI", 9),
        bg=BG,
        fg=MUTED
    ).pack(
        pady=(0, 12)
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

    list_frame = tk.Frame(
        body,
        bg=CARD
    )

    list_frame.pack(
        side="left",
        fill="y",
        padx=(0, 18)
    )

    detail_frame = tk.Frame(
        body,
        bg=CARD2,
        padx=20,
        pady=20
    )

    detail_frame.pack(
        side="left",
        fill="both",
        expand=True
    )

    listbox = tk.Listbox(
        list_frame,
        width=28,
        height=24,
        bg=CARD2,
        fg=TEXT,
        selectbackground=GREEN,
        selectforeground="#07111d",
        font=("Segoe UI", 11),
        relief="flat"
    )

    listbox.pack(
        fill="y",
        expand=True
    )

    for user in users:
        listbox.insert(
            "end",
            user
        )

    info = tk.Label(
        detail_frame,
        text="Select a registered user.",
        justify="left",
        anchor="nw",
        font=("Segoe UI", 11),
        bg=CARD2,
        fg=TEXT
    )

    info.pack(
        fill="both",
        expand=True,
        anchor="nw"
    )

    image_label = tk.Label(
        detail_frame,
        bg=CARD2
    )

    image_label.pack(
        pady=(10, 0)
    )

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

        text = (
            f"Name: "
            f"{profile.get('full_name', name) or name}\n"
            f"Phone: "
            f"{profile.get('phone', 'Not provided')}\n"
            f"Email: "
            f"{profile.get('email', 'Not provided')}\n"
            f"Department: "
            f"{profile.get('department', 'Not provided')}\n"
            f"Role: "
            f"{profile.get('role', 'Not provided')}\n"
            f"Registered: "
            f"{profile.get('registered_at', 'Legacy profile / not available')}\n\n"
            f"Notes:\n"
            f"{profile.get('notes', 'None') or 'None'}\n\n"
            "Access: AUTHENTICATED ADMIN"
        )

        info.config(
            text=text
        )

        image_label.config(
            image=""
        )

        image_label.image = None

        user_dir = os.path.join(
            SECURE_FACES_DIR,
            name
        )

        encrypted_images = (
            [
                os.path.join(
                    user_dir,
                    f
                )
                for f in sorted(
                    os.listdir(
                        user_dir
                    )
                )
                if (
                    f.lower().endswith(".enc")
                    and f.lower().startswith("face_")
                )
            ]
            if os.path.isdir(user_dir)
            else []
        )

        if encrypted_images:
            try:
                image = decrypt_face_image(
                    encrypted_images[0]
                )

                image = cv2.cvtColor(
                    image,
                    cv2.COLOR_BGR2RGB
                )

                pil_image = Image.fromarray(
                    image
                )

                pil_image.thumbnail(
                    (300, 220)
                )

                photo = ImageTk.PhotoImage(
                    pil_image
                )

                image_label.config(
                    image=photo
                )

                image_label.image = photo

            except Exception as error:
                print(
                    "Profile image display error:",
                    error
                )

    listbox.bind(
        "<<ListboxSelect>>",
        show_selected
    )

    if users:
        listbox.selection_set(0)
        show_selected()

    else:
        info.config(
            text="No registered users."
        )


# ============================================================
# CAMERA
# ============================================================

def open_camera():
    attempts = []

    if hasattr(
        cv2,
        "CAP_DSHOW"
    ):
        attempts.append(
            cv2.CAP_DSHOW
        )

    if hasattr(
        cv2,
        "CAP_MSMF"
    ):
        attempts.append(
            cv2.CAP_MSMF
        )

    attempts.append(
        cv2.CAP_ANY
    )

    for backend in attempts:
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

                print(
                    f"Camera opened with backend: "
                    f"{backend}"
                )

                return cap

            cap.release()

        except Exception as error:
            print(
                "Camera backend error:",
                error
            )

    return None


# ============================================================
# REGISTER USER
# ============================================================

def capture_user_faces(
    user_name,
    number_of_images=5
):
    cap = open_camera()

    if cap is None:
        messagebox.showerror(
            "Camera Error",
            "Could not open the camera."
        )

        return False

    captured = 0
    cancelled = False

    window_title = (
        "Register Face - "
        "SPACE = Capture | ESC = Cancel"
    )

    print(
        "Face registration started."
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
                f"Captured: "
                f"{captured}/{number_of_images}",
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
                window_title,
                preview
            )

            key = cv2.waitKey(1) & 0xFF

            if key == 27:
                cancelled = True
                break

            if key == 32:
                rgb = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )

                locations = (
                    face_recognition.face_locations(
                        rgb,
                        model="hog"
                    )
                )

                if len(locations) == 0:
                    print(
                        "No face detected."
                    )

                    continue

                if len(locations) > 1:
                    print(
                        "Multiple faces detected. "
                        "Only one face allowed."
                    )

                    continue

                captured += 1

                save_face_image_encrypted(
                    user_name,
                    frame,
                    captured
                )

                print(
                    f"Encrypted face image "
                    f"{captured}/{number_of_images} saved."
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
                for filename in os.listdir(
                    user_dir
                ):
                    os.remove(
                        os.path.join(
                            user_dir,
                            filename
                        )
                    )

                os.rmdir(
                    user_dir
                )

        except Exception:
            pass

        print(
            "Registration cancelled."
        )

        return False

    return (
        captured
        == number_of_images
    )


def train_face_encodings():
    global known_encodings
    global known_names

    new_encodings = []
    new_names = []

    print(
        "Training encrypted face database..."
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

                locations = (
                    face_recognition.face_locations(
                        rgb,
                        model="hog"
                    )
                )

                encodings = (
                    face_recognition.face_encodings(
                        rgb,
                        locations
                    )
                )

                for encoding in encodings:
                    new_encodings.append(
                        encoding
                    )

                    new_names.append(
                        user_name
                    )

            except Exception as error:
                print(
                    f"Training error: "
                    f"{path} | {error}"
                )

    save_face_encodings(
        new_encodings,
        new_names
    )

    known_encodings = new_encodings
    known_names = new_names

    print(
        f"Training complete. "
        f"{len(new_encodings)} encodings."
    )

    return len(
        new_encodings
    )


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
            "Invalid Name",
            "Please enter a valid user name."
        )

        return

    if name.lower() in [
        user.lower()
        for user in get_users()
    ]:
        messagebox.showwarning(
            "User Exists",
            "This user is already registered."
        )

        return

    profile["full_name"] = name

    success = capture_user_faces(
        name
    )

    if not success:
        return

    count = train_face_encodings()

    if count > 0:
        try:
            save_user_profile(
                name,
                profile
            )

            log_security_event(
                "USER_REGISTERED",
                (
                    f"User: {name} | "
                    "Encrypted profile created"
                )
            )

            messagebox.showinfo(
                "Registration Complete",
                (
                    f"{name} registered successfully.\n\n"
                    "Face data and personal profile "
                    "are encrypted."
                )
            )

            refresh_dashboard()

        except Exception as error:
            try:
                user_dir = os.path.join(
                    SECURE_FACES_DIR,
                    name
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

                train_face_encodings()

            except Exception:
                pass

            messagebox.showerror(
                "Profile Save Error",
                str(error)
            )

    else:
        messagebox.showerror(
            "Training Failed",
            "No valid face encoding was created."
        )


# ============================================================
# DELETE USER
# ============================================================

def delete_user():
    users = get_users()

    if not users:
        messagebox.showinfo(
            "Delete User",
            "No registered users."
        )

        return

    user_list = "\n".join(
        f"{index + 1}. {name}"
        for index, name in enumerate(users)
    )

    name = simpledialog.askstring(
        "Delete User",
        (
            "Registered users:\n\n"
            + user_list
            + "\n\nEnter exact user name to delete:"
        ),
        parent=root
    )

    if name is None:
        return

    selected = None

    for user in users:
        if user.lower() == name.strip().lower():
            selected = user
            break

    if selected is None:
        messagebox.showerror(
            "Delete User",
            "User not found."
        )

        return

    confirm = messagebox.askyesno(
        "Confirm Delete",
        (
            f"Delete user '{selected}' "
            "and encrypted face data?"
        )
    )

    if not confirm:
        return

    user_dir = os.path.join(
        SECURE_FACES_DIR,
        selected
    )

    try:
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
            "USER_DELETED",
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

    except Exception as error:
        print(
            "Attendance read error:",
            error
        )

        return []


def write_attendance_rows(rows):
    output = io.StringIO(
        newline=""
    )

    writer = csv.writer(
        output
    )

    writer.writerows(rows)

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
                row[0].strip().lower()
                == name.strip().lower()
                and row[1].strip()
                == today
            ):
                return False

    rows.append(
        [
            name,
            today,
            current_time
        ]
    )

    try:
        write_attendance_rows(
            rows
        )

        print(
            f"ATTENDANCE MARKED: "
            f"{name} | "
            f"{today} | "
            f"{current_time}"
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

    except Exception as error:
        print(
            "Attendance write error:",
            error
        )

        return False


def view_attendance():
    rows = read_attendance_rows()

    window = tk.Toplevel(root)

    window.title(
        "Attendance History"
    )

    window.geometry(
        "720x480"
    )

    window.configure(
        bg=BG
    )

    tk.Label(
        window,
        text="ATTENDANCE HISTORY",
        font=("Segoe UI", 18, "bold"),
        bg=BG,
        fg=GREEN
    ).pack(
        pady=15
    )

    text_box = tk.Text(
        window,
        bg=CARD,
        fg=TEXT,
        insertbackground=WHITE,
        font=("Consolas", 11),
        relief="flat"
    )

    text_box.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=10
    )

    if not rows:
        text_box.insert(
            "end",
            "No attendance records."
        )

    else:
        for row in rows:
            text_box.insert(
                "end",
                " | ".join(row)
                + "\n"
            )

    text_box.config(
        state="disabled"
    )


# ============================================================
# SECURITY LOG VIEWER
# ============================================================

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
        "900x520"
    )

    window.configure(
        bg=BG
    )

    tk.Label(
        window,
        text="SECURITY EVENT LOG",
        font=("Segoe UI", 18, "bold"),
        bg=BG,
        fg=RED
    ).pack(
        pady=15
    )

    text_box = tk.Text(
        window,
        bg=CARD,
        fg=TEXT,
        insertbackground=WHITE,
        font=("Consolas", 10),
        relief="flat"
    )

    text_box.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=10
    )

    if not rows:
        text_box.insert(
            "end",
            "No security events."
        )

    else:
        for row in rows:
            text_box.insert(
                "end",
                " | ".join(row)
                + "\n"
            )

    text_box.config(
        state="disabled"
    )


# ============================================================
# UNKNOWN FACE INCIDENT
# ============================================================

def create_unknown_incident(frame):
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

        filepath = os.path.join(
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
            log_security_event(
                "UNKNOWN_FACE_SNAPSHOT_FAILED",
                f"Incident ID: {incident_id}"
            )

            return None

        write_encrypted_file(
            filepath,
            buffer.tobytes()
        )

        if (
            read_encrypted_file(
                filepath
            )
            != buffer.tobytes()
        ):
            raise ValueError(
                "Encrypted snapshot verification failed."
            )

        last_incident_id = incident_id

        log_security_event(
            "UNKNOWN_FACE_DETECTED",
            (
                f"Incident ID: {incident_id} | "
                f"Encrypted Snapshot: {filepath}"
            )
        )

        print(
            f"UNKNOWN INCIDENT CREATED: "
            f"{incident_id}"
        )

        return incident_id

    except Exception as error:
        print(
            "Incident creation error:",
            error
        )

        log_security_event(
            "INCIDENT_CREATION_ERROR",
            str(error)
        )

        return None


# ============================================================
# UNKNOWN FACE SNAPSHOT VIEWER
# ============================================================

def view_unknown_incidents():
    window = tk.Toplevel(root)

    window.title(
        "Unknown Face Incidents"
    )

    window.geometry(
        "950x680"
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
                if f.lower().endswith(
                    ".jpg.enc"
                )
            ],
            reverse=True
        )

    if not files:
        tk.Label(
            window,
            text=(
                "No unknown face incidents recorded."
            ),
            font=("Segoe UI", 12),
            bg=BG,
            fg=MUTED
        ).pack(
            pady=40
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

    tk.Label(
        left,
        text="INCIDENTS",
        font=("Segoe UI", 10, "bold"),
        bg=BG,
        fg=MUTED
    ).pack(
        anchor="w",
        pady=(0, 5)
    )

    listbox = tk.Listbox(
        left,
        bg=CARD,
        fg=TEXT,
        selectbackground=BLUE,
        selectforeground=WHITE,
        font=("Consolas", 10),
        relief="flat",
        width=32
    )

    listbox.pack(
        side="left",
        fill="y"
    )

    image_frame = tk.Frame(
        content,
        bg="#000000"
    )

    image_frame.pack(
        side="right",
        fill="both",
        expand=True
    )

    image_label = tk.Label(
        image_frame,
        bg="#000000"
    )

    image_label.pack(
        fill="both",
        expand=True
    )

    info_label = tk.Label(
        window,
        text=(
            "Select an incident to view "
            "the encrypted snapshot."
        ),
        font=("Consolas", 10),
        bg=BG,
        fg=YELLOW
    )

    info_label.pack(
        pady=(0, 12)
    )

    for filename in files:
        incident_id = filename.replace(
            ".jpg.enc",
            ""
        )

        listbox.insert(
            "end",
            incident_id
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
                    "Could not decode encrypted snapshot."
                )

            image = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2RGB
            )

            pil_image = Image.fromarray(
                image
            )

            pil_image.thumbnail(
                (620, 500)
            )

            photo = ImageTk.PhotoImage(
                pil_image
            )

            image_label.config(
                image=photo
            )

            image_label.image = photo

            info_label.config(
                text=(
                    f"INCIDENT: "
                    f"{filename.replace('.jpg.enc', '')} "
                    "| Encrypted snapshot decrypted "
                    "for viewing"
                ),
                fg=YELLOW
            )

        except Exception as error:
            messagebox.showerror(
                "Snapshot Error",
                str(error)
            )

    listbox.bind(
        "<<ListboxSelect>>",
        show_selected
    )

    if files:
        listbox.selection_set(0)

        listbox.event_generate(
            "<<ListboxSelect>>"
        )


# ============================================================
# BASIC LIVENESS / BLINK DETECTION
# ============================================================

def eye_aspect_ratio(eye):
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
        (vertical_1 + vertical_2)
        / (2.0 * horizontal)
    )


def calculate_face_ear(landmarks):
    left_eye = landmarks.get(
        "left_eye",
        []
    )

    right_eye = landmarks.get(
        "right_eye",
        []
    )

    if (
        len(left_eye) != 6
        or len(right_eye) != 6
    ):
        return None

    left_ear = eye_aspect_ratio(
        left_eye
    )

    right_ear = eye_aspect_ratio(
        right_eye
    )

    return (
        left_ear
        + right_ear
    ) / 2.0


def update_liveness(ear):
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
    last_liveness_log_time = 0.0


# ============================================================
# FACE ANALYSIS
# ============================================================

def analyze_frame(frame):
    global processing_frame
    global latest_results

    try:
        small_frame = cv2.resize(
            frame,
            (0, 0),
            fx=0.25,
            fy=0.25
        )

        rgb_small = cv2.cvtColor(
            small_frame,
            cv2.COLOR_BGR2RGB
        )

        locations = (
            face_recognition.face_locations(
                rgb_small,
                model="hog"
            )
        )

        encodings = (
            face_recognition.face_encodings(
                rgb_small,
                locations
            )
        )

        landmarks_list = (
            face_recognition.face_landmarks(
                rgb_small,
                locations
            )
        )

        results = []

        for index, location in enumerate(
            locations
        ):
            top, right, bottom, left = (
                location
            )

            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            name = "Unknown"

            if (
                index < len(encodings)
                and known_encodings
            ):
                distances = (
                    face_recognition.face_distance(
                        known_encodings,
                        encodings[index]
                    )
                )

                if len(distances) > 0:
                    best_index = int(
                        np.argmin(
                            distances
                        )
                    )

                    best_distance = float(
                        distances[
                            best_index
                        ]
                    )

                    if (
                        best_distance
                        <= FACE_THRESHOLD
                    ):
                        name = known_names[
                            best_index
                        ]

            ear = None

            if (
                index
                < len(landmarks_list)
            ):
                ear = calculate_face_ear(
                    landmarks_list[index]
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
            "Face analysis error:",
            error
        )

    finally:
        processing_frame = False


# ============================================================
# SCANNER
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


def scanner_update():
    global camera_frame_count
    global processing_frame
    global unknown_alerted
    global stable_name
    global stable_count
    global last_recognized_name
    global latest_results
    global scanner_status_label
    global scanner_incident_label
    global scanner_liveness_label
    global last_liveness_log_time

    if not camera_running:
        return

    if camera is None:
        scanner_stop()
        return

    ret, frame = camera.read()

    if not ret:
        if scanner_window is not None:
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

    # Background processing every 6th frame.
    if (
        camera_frame_count % 6 == 0
        and not processing_frame
    ):
        processing_frame = True

        worker_frame = frame.copy()

        threading.Thread(
            target=analyze_frame,
            args=(worker_frame,),
            daemon=True
        ).start()

    with result_lock:
        results = list(
            latest_results
        )

    display_frame = frame.copy()

    found_known = False
    found_unknown = False
    current_known_name = ""
    best_ear = None

    for result in results:
        name = result["name"]

        top, right, bottom, left = (
            result["box"]
        )

        ear = result.get(
            "ear"
        )

        if name == "Unknown":
            found_unknown = True

            box_color = (
                255,
                77,
                103
            )

        else:
            found_known = True

            current_known_name = name

            box_color = (
                0,
                229,
                160
            )

        if ear is not None:
            best_ear = ear

        cv2.rectangle(
            display_frame,
            (left, top),
            (right, bottom),
            box_color,
            2
        )

        label = name

        cv2.rectangle(
            display_frame,
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
            box_color,
            -1
        )

        cv2.putText(
            display_frame,
            label,
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
        liveness_text = update_liveness(
            best_ear
        )

        if scanner_liveness_label is not None:
            if liveness_text == "LIVE":
                scanner_liveness_label.config(
                    text="LIVENESS: LIVE",
                    fg=GREEN
                )

            elif liveness_text == "FACE ONLY":
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

        if scanner_liveness_label is not None:
            scanner_liveness_label.config(
                text="LIVENESS: WAITING FOR FACE",
                fg=MUTED
            )

    # --------------------------------------------------------
    # UNKNOWN FACE INCIDENT
    # --------------------------------------------------------

    if found_unknown:
        stable_name = ""
        stable_count = 0
        last_recognized_name = ""

        if scanner_status_label is not None:
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
                is not None
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
        if stable_name == current_known_name:
            stable_count += 1

        else:
            stable_name = current_known_name
            stable_count = 1

        if (
            stable_count >= 2
            and liveness_verified
        ):
            if (
                last_recognized_name
                != current_known_name
            ):
                log_security_event(
                    "KNOWN_FACE_DETECTED",
                    (
                        f"Name: {current_known_name} | "
                        "Liveness: LIVE"
                    )
                )

                mark_attendance(
                    current_known_name
                )

                last_recognized_name = (
                    current_known_name
                )

            if scanner_status_label is not None:
                scanner_status_label.config(
                    text=(
                        f"VERIFIED: "
                        f"{current_known_name}"
                    ),
                    fg=GREEN
                )

        elif (
            stable_count >= 2
            and not liveness_verified
        ):
            if scanner_status_label is not None:
                scanner_status_label.config(
                    text=(
                        f"IDENTIFIED: "
                        f"{current_known_name} - "
                        "BLINK TO VERIFY"
                    ),
                    fg=YELLOW
                )

            if (
                time.time()
                - liveness_started_at
                > LIVENESS_TIMEOUT_SECONDS
                and time.time()
                - last_liveness_log_time
                > LIVENESS_TIMEOUT_SECONDS
            ):
                log_security_event(
                    "LIVENESS_NOT_VERIFIED",
                    (
                        f"Candidate: "
                        f"{current_known_name}"
                    )
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

        if scanner_status_label is not None:
            scanner_status_label.config(
                text="SCANNING...",
                fg=BLUE
            )

    if scanner_video_label is not None:
        rgb = cv2.cvtColor(
            display_frame,
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

    if len(known_encodings) == 0:
        messagebox.showwarning(
            "No Face Data",
            (
                "No registered face encodings found.\n\n"
                "Register a user first."
            )
        )

        return

    camera = open_camera()

    if camera is None:
        messagebox.showerror(
            "Camera Error",
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

    scanner_status_label.pack(
        pady=4
    )

    scanner_liveness_label = tk.Label(
        scanner_window,
        text="LIVENESS: WAITING FOR FACE",
        font=("Segoe UI", 11, "bold"),
        bg=BG,
        fg=MUTED
    )

    scanner_liveness_label.pack(
        pady=3
    )

    scanner_incident_label = tk.Label(
        scanner_window,
        text="",
        font=("Consolas", 11, "bold"),
        bg=BG,
        fg=YELLOW
    )

    scanner_incident_label.pack(
        pady=3
    )

    tk.Label(
        scanner_window,
        text=(
            "Blink once to complete "
            "the liveness check."
        ),
        font=("Segoe UI", 10),
        bg=BG,
        fg=MUTED
    ).pack(
        pady=(0, 5)
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
        activebackground=RED,
        activeforeground=WHITE,
        font=("Segoe UI", 11, "bold"),
        relief="flat",
        padx=25,
        pady=10,
        cursor="hand2"
    ).pack(
        pady=10
    )

    scanner_update()


# ============================================================
# DASHBOARD
# ============================================================

dashboard_user_count_label = None


def refresh_dashboard():
    global dashboard_user_count_label

    if dashboard_user_count_label is not None:
        dashboard_user_count_label.config(
            text=(
                f"Registered Users: "
                f"{len(get_users())}"
            )
        )


def clear_root():
    for widget in root.winfo_children():
        widget.destroy()


def show_dashboard():
    clear_root()

    root.title(
        APP_TITLE
    )

    root.geometry(
        "780x730"
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
        pady=(25, 10)
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

    card = tk.Frame(
        root,
        bg=CARD,
        padx=25,
        pady=25
    )

    card.pack(
        fill="both",
        expand=True,
        padx=30,
        pady=15
    )

    global dashboard_user_count_label

    dashboard_user_count_label = tk.Label(
        card,
        text=(
            f"Registered Users: "
            f"{len(get_users())}"
        ),
        font=("Segoe UI", 15, "bold"),
        bg=CARD,
        fg=TEXT
    )

    dashboard_user_count_label.pack(
        pady=(0, 8)
    )

    tk.Label(
        card,
        text="ENCRYPTED STORAGE ACTIVE",
        font=("Segoe UI", 11, "bold"),
        bg=CARD,
        fg=GREEN
    ).pack(
        pady=(0, 15)
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
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            padx=15,
            pady=10,
            cursor="hand2"
        )

    make_button(
        "START FACE SCANNER",
        start_scanner,
        GREEN
    ).pack(
        fill="x",
        pady=5
    )

    make_button(
        "REGISTER USER",
        register_user,
        BLUE
    ).pack(
        fill="x",
        pady=5
    )

    make_button(
        "DELETE USER",
        delete_user,
        RED
    ).pack(
        fill="x",
        pady=5
    )

    make_button(
        "VIEW REGISTERED USER PROFILES",
        view_user_profiles,
        BLUE
    ).pack(
        fill="x",
        pady=5
    )

    make_button(
        "VIEW ATTENDANCE",
        view_attendance,
        BLUE
    ).pack(
        fill="x",
        pady=5
    )

    make_button(
        "VIEW SECURITY EVENTS",
        view_security_log,
        YELLOW
    ).pack(
        fill="x",
        pady=5
    )

    make_button(
        "VIEW UNKNOWN FACE INCIDENTS",
        view_unknown_incidents,
        RED
    ).pack(
        fill="x",
        pady=5
    )

    make_button(
        "EXIT",
        root.destroy,
        RED
    ).pack(
        fill="x",
        pady=(15, 0)
    )


# ============================================================
# LOGIN - PROGRESSIVE BRUTE-FORCE PROTECTION
# ============================================================

def login():
    global login_failed_attempts
    global login_locked_until
    global progressive_lock_level

    current_time = time.time()

    # --------------------------------------------------------
    # CHECK ACTIVE LOCKOUT
    # --------------------------------------------------------

    if current_time < login_locked_until:
        remaining = int(
            login_locked_until
            - current_time
        ) + 1

        minutes = remaining // 60
        seconds = remaining % 60

        if minutes > 0:
            lock_text = (
                "ACCOUNT LOCKED - "
                f"Try again in "
                f"{minutes}m {seconds}s"
            )

        else:
            lock_text = (
                "ACCOUNT LOCKED - "
                f"Try again in "
                f"{seconds}s"
            )

        login_status.config(
            text=lock_text,
            fg=RED
        )

        # Keep countdown updated.
        root.after(
            1000,
            login
        )

        return

    # --------------------------------------------------------
    # READ PASSWORD
    # --------------------------------------------------------

    password = password_entry.get()

    # --------------------------------------------------------
    # SUCCESSFUL LOGIN
    # --------------------------------------------------------

    if verify_admin_password(password):

        # Reset failed attempts.
        login_failed_attempts = 0

        # Remove active lockout.
        login_locked_until = 0

        # Reset progressive lock level
        # after successful authentication.
        progressive_lock_level = 0

        log_security_event(
            "LOGIN_SUCCESS",
            "Admin authentication successful"
        )

        show_dashboard()

        return

    # --------------------------------------------------------
    # FAILED LOGIN
    # --------------------------------------------------------

    login_failed_attempts += 1

    log_security_event(
        "LOGIN_FAILED",
        (
            f"Attempt: "
            f"{login_failed_attempts}/"
            f"{MAX_LOGIN_ATTEMPTS}"
        )
    )

    # Clear password immediately.
    password_entry.delete(
        0,
        "end"
    )

    # --------------------------------------------------------
    # LOCKOUT AFTER 2 FAILED ATTEMPTS
    # --------------------------------------------------------

    if (
        login_failed_attempts
        >= MAX_LOGIN_ATTEMPTS
    ):

        # Increase progressive lock level.
        progressive_lock_level += 1

        # ----------------------------------------------------
        # PROGRESSIVE LOCKOUT SCHEDULE
        # ----------------------------------------------------
        #
        # Level 1 = 5 minutes
        # Level 2 = 15 minutes
        # Level 3 = 30 minutes
        # Level 4+ = 60 minutes
        #

        if progressive_lock_level == 1:
            lockout_seconds = (
                INITIAL_LOCKOUT_SECONDS
            )

        elif progressive_lock_level == 2:
            lockout_seconds = (
                15 * 60
            )

        elif progressive_lock_level == 3:
            lockout_seconds = (
                30 * 60
            )

        else:
            lockout_seconds = (
                MAX_LOCKOUT_SECONDS
            )

        login_locked_until = (
            time.time()
            + lockout_seconds
        )

        # Reset attempts for next cycle.
        login_failed_attempts = 0

        lock_minutes = (
            lockout_seconds // 60
        )

        login_status.config(
            text=(
                "ACCOUNT LOCKED - "
                f"{lock_minutes} minute"
                f"{'s' if lock_minutes != 1 else ''}"
            ),
            fg=RED
        )

        # Record detailed security event.
        log_security_event(
            "LOGIN_LOCKOUT",
            (
                f"Progressive Level: "
                f"{progressive_lock_level} | "
                f"Lockout: "
                f"{lock_minutes} minutes | "
                f"Trigger: "
                f"{MAX_LOGIN_ATTEMPTS} "
                "failed attempts"
            )
        )

    # --------------------------------------------------------
    # STILL HAS AN ATTEMPT BEFORE LOCKOUT
    # --------------------------------------------------------

    else:
        remaining = (
            MAX_LOGIN_ATTEMPTS
            - login_failed_attempts
        )

        login_status.config(
            text=(
                "Wrong password. "
                f"{remaining} attempt"
                f"{'s' if remaining != 1 else ''} "
                "remaining."
            ),
            fg=RED
        )


def show_login():
    clear_root()

    root.title(
        APP_TITLE
        + " - Login"
    )

    root.geometry(
        "520x420"
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
        pady=35
    )

    card.pack(
        fill="both",
        expand=True,
        padx=45,
        pady=45
    )

    tk.Label(
        card,
        text="AI SECURITY",
        font=("Segoe UI", 26, "bold"),
        bg=CARD,
        fg=GREEN
    ).pack(
        pady=(0, 5)
    )

    tk.Label(
        card,
        text="ADMIN LOGIN",
        font=("Segoe UI", 13, "bold"),
        bg=CARD,
        fg=TEXT
    ).pack(
        pady=(0, 25)
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

    global password_entry
    global login_status

    password_entry = tk.Entry(
        card,
        show="*",
        font=("Segoe UI", 13),
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
        lambda event: login()
    )

    tk.Button(
        card,
        text="LOGIN",
        command=login,
        bg=GREEN,
        fg="#07111d",
        activebackground=GREEN,
        activeforeground="#07111d",
        font=("Segoe UI", 11, "bold"),
        relief="flat",
        padx=20,
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
        pady=15
    )

    tk.Label(
        card,
        text=(
            "AES-256-GCM encrypted data storage"
        ),
        font=("Segoe UI", 9),
        bg=CARD,
        fg=MUTED
    ).pack()


# ============================================================
# MAIN
# ============================================================

def main():
    global root

    print("=" * 60)
    print(APP_TITLE)
    print("=" * 60)

    print(
        "Initializing AES-256-GCM encryption..."
    )

    load_encryption_key()

    migrate_existing_data()

    load_face_encodings()

    root = tk.Tk()

    log_security_event(
        "SYSTEM_START",
        (
            "AI Security started "
            "with encrypted storage"
        )
    )

    show_login()

    root.mainloop()


if __name__ == "__main__":
    main()