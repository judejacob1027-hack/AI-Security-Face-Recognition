import tkinter as tk
from tkinter import messagebox, simpledialog
import cv2
import os
import csv
import subprocess
import winsound
from datetime import datetime


# =========================================================
# COLORS
# =========================================================

BG = "#070a0f"
SIDEBAR = "#0c1118"
PANEL = "#101720"
CARD = "#141c26"
BORDER = "#202b38"

TEXT = "#f5f7fa"
MUTED = "#788594"

GREEN = "#00e5a0"
RED = "#ff4d67"
YELLOW = "#ffc857"
BLUE = "#5c9dff"


# =========================================================
# FILES
# =========================================================

USERS_FOLDER = "known_faces"
ATTENDANCE_FILE = "attendance.csv"
MODEL_FILE = "face_model.yml"
USERS_FILE = "users.txt"
MAIN_FILE = "main.py"


# =========================================================
# GLOBALS
# =========================================================

scanner_running = False
unknown_alerted = False

last_scan_status = "READY TO SCAN"
last_scan_name = "NO USER"
last_scan_time = "--:--:--"
last_scan_color = MUTED


# =========================================================
# USER FUNCTIONS
# =========================================================

def get_users():

    if not os.path.exists(USERS_FOLDER):
        return []

    return sorted([
        name
        for name in os.listdir(USERS_FOLDER)
        if os.path.isdir(
            os.path.join(
                USERS_FOLDER,
                name
            )
        )
    ])


def get_user_photos(name):

    folder = os.path.join(
        USERS_FOLDER,
        name
    )

    if not os.path.isdir(folder):
        return []

    return [
        file
        for file in os.listdir(folder)
        if file.lower().endswith(
            (".jpg", ".jpeg", ".png")
        )
    ]


# =========================================================
# ATTENDANCE FUNCTIONS
# =========================================================

def get_attendance():

    records = []

    if not os.path.exists(
        ATTENDANCE_FILE
    ):
        return records

    try:

        with open(
            ATTENDANCE_FILE,
            "r",
            newline=""
        ) as file:

            reader = csv.reader(file)

            next(
                reader,
                None
            )

            for row in reader:

                if len(row) >= 3:
                    records.append(row)

    except Exception as e:

        print(
            "Attendance read error:",
            e
        )

    return records


def today_attendance():

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    records = get_attendance()

    return [
        row
        for row in records
        if len(row) >= 3
        and row[1] == today
    ]


def attendance_exists_today(name):

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    target = name.strip().casefold()

    for row in get_attendance():

        if len(row) < 3:
            continue

        stored_name = row[0].strip().casefold()
        stored_date = row[1].strip()

        if (
            stored_name == target
            and stored_date == today
        ):

            return True, row[2]

    return False, None


def mark_attendance(name):

    global last_scan_status
    global last_scan_name
    global last_scan_time
    global last_scan_color

    now = datetime.now()

    today = now.strftime(
        "%Y-%m-%d"
    )

    current_time = now.strftime(
        "%H:%M:%S"
    )

    # Create CSV if needed
    if not os.path.exists(
        ATTENDANCE_FILE
    ):

        with open(
            ATTENDANCE_FILE,
            "w",
            newline=""
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "Name",
                "Date",
                "Time"
            ])

    # Case-insensitive duplicate check
    already_marked, old_time = attendance_exists_today(
        name
    )

    if already_marked:

        print(
            f"ATTENDANCE ALREADY MARKED: "
            f"{name} | {today} | First marked: {old_time}"
        )

        last_scan_status = "ALREADY MARKED"
        last_scan_name = name
        last_scan_time = old_time
        last_scan_color = YELLOW

        return False

    # Add attendance
    with open(
        ATTENDANCE_FILE,
        "a",
        newline=""
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            name,
            today,
            current_time
        ])

    print(
        f"ATTENDANCE MARKED: "
        f"{name} | {today} | {current_time}"
    )

    last_scan_status = "ATTENDANCE MARKED"
    last_scan_name = name
    last_scan_time = current_time
    last_scan_color = GREEN

    return True


# =========================================================
# TRAIN MODEL
# =========================================================

def train_model():

    if not os.path.exists(
        MAIN_FILE
    ):

        messagebox.showerror(
            "Training Error",
            "main.py not found.\n\n"
            "Make sure the file is named:\n"
            "main.py"
        )

        return False

    try:

        result = subprocess.run(
            ["python", MAIN_FILE],
            capture_output=True,
            text=True
        )

        print(
            result.stdout
        )

        if result.returncode != 0:

            print(
                result.stderr
            )

            messagebox.showerror(
                "Training Error",
                "AI model training failed.\n\n"
                "Check the Terminal for details."
            )

            return False

        return True

    except Exception as e:

        messagebox.showerror(
            "Training Error",
            str(e)
        )

        return False


# =========================================================
# REGISTER USER
# =========================================================

def register_user():

    name = simpledialog.askstring(
        "Register New User",
        "Enter user name:"
    )

    if name is None:
        return

    name = name.strip()

    if not name:

        messagebox.showwarning(
            "Invalid Name",
            "Please enter a valid name."
        )

        return

    # Prevent duplicate folder names ignoring case
    existing_users = get_users()

    for user in existing_users:

        if user.casefold() == name.casefold():

            messagebox.showwarning(
                "User Exists",
                f"User '{user}' already exists."
            )

            return

    folder = os.path.join(
        USERS_FOLDER,
        name
    )

    os.makedirs(
        folder,
        exist_ok=True
    )

    messagebox.showinfo(
        "Camera Registration",
        "Camera will open now.\n\n"
        "SPACE = Capture photo\n"
        "Q = Finish registration"
    )

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        messagebox.showerror(
            "Camera Error",
            "Camera could not be opened."
        )

        return

    count = 1

    while True:

        ret, frame = camera.read()

        if not ret:
            break

        frame = cv2.flip(
            frame,
            1
        )

        cv2.putText(
            frame,
            f"REGISTERING: {name}",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 229, 160),
            2
        )

        cv2.putText(
            frame,
            "SPACE = CAPTURE     Q = FINISH",
            (30, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (200, 200, 200),
            1
        )

        cv2.putText(
            frame,
            f"PHOTOS: {count - 1}",
            (30, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        cv2.imshow(
            "USER REGISTRATION",
            frame
        )

        key = cv2.waitKey(1) & 0xFF

        if key == 32:

            filename = os.path.join(
                folder,
                f"{name}_{count}.jpg"
            )

            cv2.imwrite(
                filename,
                frame
            )

            print(
                "Saved:",
                filename
            )

            count += 1

        elif key == ord("q"):

            break

    camera.release()

    cv2.destroyAllWindows()

    photo_count = count - 1

    if photo_count == 0:

        try:
            os.rmdir(folder)
        except:
            pass

        messagebox.showwarning(
            "Registration Cancelled",
            "No photos were captured."
        )

        return

    # Retrain
    messagebox.showinfo(
        "Training AI",
        f"{photo_count} photos captured.\n\n"
        "Updating AI face model..."
    )

    success = train_model()

    if success:

        messagebox.showinfo(
            "Registration Complete",
            f"User '{name}' registered successfully.\n\n"
            f"Photos: {photo_count}\n"
            "AI model updated."
        )

    refresh_dashboard()


# =========================================================
# DELETE USER
# =========================================================

def delete_user():

    users = get_users()

    if not users:

        messagebox.showinfo(
            "Delete User",
            "No registered users found."
        )

        return

    window = tk.Toplevel(root)

    window.title(
        "Delete User"
    )

    window.geometry(
        "500x520"
    )

    window.resizable(
        False,
        False
    )

    window.configure(
        bg=BG
    )

    tk.Label(
        window,
        text="DELETE USER",
        font=(
            "Segoe UI",
            20,
            "bold"
        ),
        fg=TEXT,
        bg=BG
    ).pack(
        pady=(30, 10)
    )

    tk.Label(
        window,
        text="Select a registered user",
        font=(
            "Segoe UI",
            9
        ),
        fg=MUTED,
        bg=BG
    ).pack(
        pady=(0, 20)
    )

    selected_user = tk.StringVar()

    list_frame = tk.Frame(
        window,
        bg=BG
    )

    list_frame.pack(
        fill="both",
        expand=True,
        padx=40
    )

    for user in users:

        radio = tk.Radiobutton(
            list_frame,
            text=f"{user}   ({len(get_user_photos(user))} photos)",
            variable=selected_user,
            value=user,
            font=(
                "Segoe UI",
                10,
                "bold"
            ),
            fg=TEXT,
            bg=PANEL,
            selectcolor=PANEL,
            activebackground=PANEL,
            activeforeground=GREEN,
            anchor="w"
        )

        radio.pack(
            fill="x",
            pady=5,
            ipady=8
        )

    def confirm_delete():

        user = selected_user.get()

        if not user:

            messagebox.showwarning(
                "Select User",
                "Please select a user first.",
                parent=window
            )

            return

        answer = messagebox.askyesno(
            "Confirm Delete",
            f"Delete '{user}' and all registered photos?",
            parent=window
        )

        if not answer:
            return

        import shutil

        folder = os.path.join(
            USERS_FOLDER,
            user
        )

        try:

            shutil.rmtree(
                folder
            )

            print(
                f"USER DELETED: {user}"
            )

            window.destroy()

            messagebox.showinfo(
                "User Deleted",
                f"User '{user}' deleted successfully.\n\n"
                "AI model will now be retrained."
            )

            train_model()

            refresh_dashboard()

        except Exception as e:

            messagebox.showerror(
                "Delete Error",
                str(e),
                parent=window
            )

    tk.Button(
        window,
        text="DELETE SELECTED USER",
        command=confirm_delete,
        font=(
            "Segoe UI",
            10,
            "bold"
        ),
        fg="#ffffff",
        bg=RED,
        activeforeground="#ffffff",
        activebackground=RED,
        relief="flat",
        bd=0,
        cursor="hand2",
        height=2
    ).pack(
        fill="x",
        padx=40,
        pady=25
    )


# =========================================================
# SHOW USERS
# =========================================================

def show_users():

    users = get_users()

    window = tk.Toplevel(root)

    window.title(
        "Registered Users"
    )

    window.geometry(
        "550x550"
    )

    window.resizable(
        False,
        False
    )

    window.configure(
        bg=BG
    )

    tk.Label(
        window,
        text="REGISTERED USERS",
        font=(
            "Segoe UI",
            20,
            "bold"
        ),
        fg=TEXT,
        bg=BG
    ).pack(
        pady=(30, 10)
    )

    tk.Label(
        window,
        text=f"{len(users)} active identities",
        font=(
            "Segoe UI",
            9
        ),
        fg=MUTED,
        bg=BG
    ).pack(
        pady=(0, 20)
    )

    if not users:

        tk.Label(
            window,
            text="No registered users.",
            font=(
                "Segoe UI",
                11
            ),
            fg=MUTED,
            bg=BG
        ).pack(
            pady=30
        )

        return

    for number, user in enumerate(
        users,
        1
    ):

        photos = len(
            get_user_photos(user)
        )

        row = tk.Frame(
            window,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        row.pack(
            fill="x",
            padx=40,
            pady=5
        )

        tk.Label(
            row,
            text=f"{number}.  {user}",
            font=(
                "Segoe UI",
                11,
                "bold"
            ),
            fg=TEXT,
            bg=CARD
        ).pack(
            side="left",
            padx=15,
            pady=15
        )

        tk.Label(
            row,
            text=f"{photos} photos",
            font=(
                "Segoe UI",
                9
            ),
            fg=MUTED,
            bg=CARD
        ).pack(
            side="right",
            padx=15
        )


# =========================================================
# ATTENDANCE HISTORY
# =========================================================

def show_attendance():

    records = get_attendance()

    window = tk.Toplevel(root)

    window.title(
        "Attendance History"
    )

    window.geometry(
        "750x560"
    )

    window.resizable(
        False,
        False
    )

    window.configure(
        bg=BG
    )

    tk.Label(
        window,
        text="ATTENDANCE HISTORY",
        font=(
            "Segoe UI",
            20,
            "bold"
        ),
        fg=TEXT,
        bg=BG
    ).pack(
        pady=(25, 5)
    )

    tk.Label(
        window,
        text=f"{len(records)} total records",
        font=(
            "Segoe UI",
            9
        ),
        fg=MUTED,
        bg=BG
    ).pack(
        pady=(0, 20)
    )

    container = tk.Frame(
        window,
        bg=BG
    )

    container.pack(
        fill="both",
        expand=True,
        padx=30
    )

    header = tk.Frame(
        container,
        bg=PANEL
    )

    header.pack(
        fill="x"
    )

    for text in [
        "NAME",
        "DATE",
        "TIME"
    ]:

        tk.Label(
            header,
            text=text,
            font=(
                "Segoe UI",
                9,
                "bold"
            ),
            fg=MUTED,
            bg=PANEL,
            width=23
        ).pack(
            side="left",
            pady=12
        )

    if not records:

        tk.Label(
            container,
            text="No attendance records.",
            font=(
                "Segoe UI",
                10
            ),
            fg=MUTED,
            bg=BG
        ).pack(
            pady=30
        )

        return

    for row in records:

        data = tk.Frame(
            container,
            bg=CARD
        )

        data.pack(
            fill="x",
            pady=2
        )

        for value in row[:3]:

            tk.Label(
                data,
                text=value,
                font=(
                    "Segoe UI",
                    9
                ),
                fg=TEXT,
                bg=CARD,
                width=23
            ).pack(
                side="left",
                pady=10
            )


# =========================================================
# SCANNER
# =========================================================

def scan_face():

    global scanner_running
    global unknown_alerted

    global last_scan_status
    global last_scan_name
    global last_scan_time
    global last_scan_color

    if not os.path.exists(
        MODEL_FILE
    ):

        messagebox.showerror(
            "Scanner Error",
            "face_model.yml not found.\n\n"
            "Register a user first."
        )

        return

    if not os.path.exists(
        USERS_FILE
    ):

        messagebox.showerror(
            "Scanner Error",
            "users.txt not found.\n\n"
            "Register a user first."
        )

        return

    # Load AI model
    try:

        recognizer = cv2.face.LBPHFaceRecognizer_create()

        recognizer.read(
            MODEL_FILE
        )

    except Exception as e:

        messagebox.showerror(
            "AI Model Error",
            str(e)
        )

        return

    # Load users
    users = {}

    try:

        with open(
            USERS_FILE,
            "r"
        ) as file:

            for line in file:

                line = line.strip()

                if not line:
                    continue

                parts = line.split(
                    ",",
                    1
                )

                if len(parts) == 2:

                    user_id = int(
                        parts[0]
                    )

                    user_name = parts[1]

                    users[user_id] = user_name

    except Exception as e:

        messagebox.showerror(
            "User Database Error",
            str(e)
        )

        return

    if not users:

        messagebox.showwarning(
            "No Users",
            "No registered users found."
        )

        return

    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades
        + "haarcascade_frontalface_default.xml"
    )

    camera = cv2.VideoCapture(0)

    camera.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )

    camera.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )

    if not camera.isOpened():

        messagebox.showerror(
            "Camera Error",
            "Camera could not be opened."
        )

        return

    scanner_running = True
    unknown_alerted = False

    current_status = "READY TO SCAN"
    current_name = "NO USER"
    current_color = (
        180,
        180,
        180
    )

    print()
    print(
        "=========================================="
    )
    print(
        "             FACE SCANNER"
    )
    print(
        "=========================================="
    )
    print(
        "Press Q to exit scanner."
    )
    print()

    while scanner_running:

        ret, frame = camera.read()

        if not ret:

            print(
                "ERROR: Could not read camera."
            )

            break

        frame = cv2.flip(
            frame,
            1
        )

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        detected_faces = detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80)
        )

        current_status = "READY TO SCAN"
        current_name = "NO USER"
        current_color = (
            180,
            180,
            180
        )

        if len(detected_faces) == 0:

            unknown_alerted = False

        for (x, y, w, h) in detected_faces:

            x = int(x)
            y = int(y)
            w = int(w)
            h = int(h)

            face_gray = gray[
                y:y+h,
                x:x+w
            ]

            try:

                user_id, confidence = recognizer.predict(
                    face_gray
                )

            except:

                user_id = -1
                confidence = 999

            # =================================================
            # VERIFIED FACE
            # =================================================

            if (
                confidence < 100
                and user_id in users
            ):

                recognized_name = users[
                    user_id
                ]

                marked = mark_attendance(
                    recognized_name
                )

                if marked:

                    current_status = "ATTENDANCE MARKED"

                    current_color = (
                        0,
                        229,
                        160
                    )

                else:

                    current_status = "ALREADY MARKED"

                    current_color = (
                        0,
                        200,
                        255
                    )

                current_name = recognized_name

                unknown_alerted = False

                box_color = (
                    0,
                    229,
                    160
                )

            # =================================================
            # UNKNOWN FACE
            # =================================================

            else:

                current_name = "UNKNOWN"
                current_status = "UNKNOWN FACE"

                current_color = (
                    0,
                    0,
                    255
                )

                box_color = (
                    0,
                    0,
                    255
                )

                if not unknown_alerted:

                    print(
                        "SECURITY ALERT: "
                        "Unknown face detected!"
                    )

                    try:

                        winsound.Beep(
                            1200,
                            500
                        )

                    except:

                        pass

                    unknown_alerted = True

            # =================================================
            # FACE RECTANGLE
            # =================================================

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                box_color,
                2
            )

            # =================================================
            # FACE NAME
            # =================================================

            cv2.putText(
                frame,
                current_name,
                (x, y - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                box_color,
                2,
                cv2.LINE_AA
            )

        # =====================================================
        # CAMERA HEADER
        # =====================================================

        height, width = frame.shape[:2]

        cv2.rectangle(
            frame,
            (0, 0),
            (width, 80),
            (15, 20, 26),
            -1
        )

        cv2.putText(
            frame,
            "AI SECURITY",
            (30, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            "FACE RECOGNITION / ATTENDANCE",
            (30, 62),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (160, 170, 180),
            1
        )

        # =====================================================
        # STATUS PANEL
        # =====================================================

        panel_x = width - 370

        cv2.rectangle(
            frame,
            (panel_x, 105),
            (width - 25, 410),
            (25, 30, 38),
            -1
        )

        cv2.rectangle(
            frame,
            (panel_x, 105),
            (width - 25, 410),
            (65, 75, 85),
            1
        )

        cv2.putText(
            frame,
            "SCAN STATUS",
            (panel_x + 25, 140),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (150, 160, 170),
            1
        )

        cv2.putText(
            frame,
            current_status,
            (panel_x + 25, 185),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            current_color,
            2
        )

        cv2.putText(
            frame,
            "IDENTITY",
            (panel_x + 25, 235),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (150, 160, 170),
            1
        )

        cv2.putText(
            frame,
            current_name,
            (panel_x + 25, 275),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            "TIME",
            (panel_x + 25, 320),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (150, 160, 170),
            1
        )

        cv2.putText(
            frame,
            datetime.now().strftime(
                "%H:%M:%S"
            ),
            (panel_x + 25, 355),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        # =====================================================
        # BOTTOM
        # =====================================================

        cv2.putText(
            frame,
            "Q = EXIT SCANNER",
            (30, height - 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (150, 160, 170),
            1
        )

        cv2.imshow(
            "AI SECURITY - FACE SCANNER",
            frame
        )

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):

            break

    scanner_running = False

    camera.release()

    cv2.destroyAllWindows()

    # Update dashboard
    refresh_dashboard()

    print()
    print(
        "FACE SCANNER CLOSED"
    )


# =========================================================
# DASHBOARD HELPERS
# =========================================================

def create_card(
    parent,
    title,
    value,
    subtitle
):

    frame = tk.Frame(
        parent,
        bg=CARD,
        highlightbackground=BORDER,
        highlightthickness=1,
        width=250,
        height=130
    )

    frame.pack(
        side="left",
        padx=(0, 15)
    )

    frame.pack_propagate(
        False
    )

    tk.Label(
        frame,
        text=title,
        font=(
            "Segoe UI",
            8,
            "bold"
        ),
        fg=MUTED,
        bg=CARD
    ).pack(
        anchor="w",
        padx=20,
        pady=(18, 3)
    )

    number = tk.Label(
        frame,
        text=value,
        font=(
            "Segoe UI",
            27,
            "bold"
        ),
        fg=TEXT,
        bg=CARD
    )

    number.pack(
        anchor="w",
        padx=20
    )

    tk.Label(
        frame,
        text=subtitle,
        font=(
            "Segoe UI",
            8
        ),
        fg=MUTED,
        bg=CARD
    ).pack(
        anchor="w",
        padx=20
    )

    return number


def sidebar_button(
    text,
    command,
    color=MUTED
):

    button = tk.Button(
        sidebar,
        text=text,
        command=command,
        font=(
            "Segoe UI",
            10,
            "bold"
        ),
        fg=color,
        bg=SIDEBAR,
        activeforeground=GREEN,
        activebackground=SIDEBAR,
        relief="flat",
        bd=0,
        anchor="w",
        cursor="hand2"
    )

    button.pack(
        fill="x",
        padx=18,
        pady=5,
        ipady=10
    )

    return button


# =========================================================
# ROOT WINDOW
# =========================================================

root = tk.Tk()

root.title(
    "AI SECURITY — Admin Dashboard"
)

root.geometry(
    "1200x720"
)

root.resizable(
    False,
    False
)

root.configure(
    bg=BG
)


# =========================================================
# SIDEBAR
# =========================================================

sidebar = tk.Frame(
    root,
    bg=SIDEBAR,
    width=240
)

sidebar.pack(
    side="left",
    fill="y"
)

sidebar.pack_propagate(
    False
)


tk.Label(
    sidebar,
    text="◈",
    font=(
        "Segoe UI",
        38,
        "bold"
    ),
    fg=GREEN,
    bg=SIDEBAR
).pack(
    pady=(45, 0)
)


tk.Label(
    sidebar,
    text="AI SECURITY",
    font=(
        "Segoe UI",
        17,
        "bold"
    ),
    fg=TEXT,
    bg=SIDEBAR
).pack(
    pady=5
)


tk.Label(
    sidebar,
    text="ADMIN CONTROL CENTER",
    font=(
        "Segoe UI",
        7,
        "bold"
    ),
    fg=MUTED,
    bg=SIDEBAR
).pack(
    pady=(0, 35)
)


sidebar_button(
    "▣   DASHBOARD",
    lambda: None
)

sidebar_button(
    "◉   SCAN FACE",
    scan_face,
    GREEN
)

sidebar_button(
    "＋   REGISTER USER",
    register_user
)

sidebar_button(
    "♙   USERS",
    show_users
)

sidebar_button(
    "✕   DELETE USER",
    delete_user,
    RED
)

sidebar_button(
    "▤   ATTENDANCE",
    show_attendance
)


status_frame = tk.Frame(
    sidebar,
    bg=SIDEBAR
)

status_frame.pack(
    side="bottom",
    pady=35
)


tk.Label(
    status_frame,
    text="●  SYSTEM ONLINE",
    font=(
        "Segoe UI",
        9,
        "bold"
    ),
    fg=GREEN,
    bg=SIDEBAR
).pack()


tk.Label(
    status_frame,
    text="AI ENGINE READY",
    font=(
        "Segoe UI",
        7
    ),
    fg=MUTED,
    bg=SIDEBAR
).pack(
    pady=5
)


# =========================================================
# MAIN CONTENT
# =========================================================

content = tk.Frame(
    root,
    bg=BG
)

content.pack(
    side="right",
    fill="both",
    expand=True
)


# =========================================================
# HEADER
# =========================================================

header = tk.Frame(
    content,
    bg=BG
)

header.pack(
    fill="x",
    padx=35,
    pady=(30, 20)
)


tk.Label(
    header,
    text="SECURITY OVERVIEW",
    font=(
        "Segoe UI",
        24,
        "bold"
    ),
    fg=TEXT,
    bg=BG
).pack(
    side="left"
)


tk.Label(
    header,
    text="ADMINISTRATOR",
    font=(
        "Segoe UI",
        9,
        "bold"
    ),
    fg=MUTED,
    bg=BG
).pack(
    side="right",
    pady=10
)


# =========================================================
# STAT CARDS
# =========================================================

cards = tk.Frame(
    content,
    bg=BG
)

cards.pack(
    fill="x",
    padx=35
)


users_count = create_card(
    cards,
    "REGISTERED USERS",
    "0",
    "Active identities"
)


today_count = create_card(
    cards,
    "TODAY ATTENDANCE",
    "0",
    "Present today"
)


total_count = create_card(
    cards,
    "TOTAL RECORDS",
    "0",
    "Attendance database"
)


# =========================================================
# LOWER AREA
# =========================================================

lower = tk.Frame(
    content,
    bg=BG
)

lower.pack(
    fill="both",
    expand=True,
    padx=35,
    pady=25
)


# =========================================================
# ATTENDANCE PANEL
# =========================================================

attendance_panel = tk.Frame(
    lower,
    bg=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1
)

attendance_panel.pack(
    side="left",
    fill="both",
    expand=True,
    padx=(0, 15)
)


tk.Label(
    attendance_panel,
    text="TODAY'S ATTENDANCE",
    font=(
        "Segoe UI",
        13,
        "bold"
    ),
    fg=TEXT,
    bg=PANEL
).pack(
    anchor="w",
    padx=20,
    pady=(20, 5)
)


# Latest status
latest_status_label = tk.Label(
    attendance_panel,
    text="● READY TO SCAN",
    font=(
        "Segoe UI",
        9,
        "bold"
    ),
    fg=MUTED,
    bg=PANEL
)

latest_status_label.pack(
    anchor="w",
    padx=20,
    pady=(0, 10)
)


attendance_list = tk.Frame(
    attendance_panel,
    bg=PANEL
)

attendance_list.pack(
    fill="both",
    expand=True
)


# =========================================================
# SCANNER PANEL
# =========================================================

scanner_panel = tk.Frame(
    lower,
    bg=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1,
    width=300
)

scanner_panel.pack(
    side="right",
    fill="y"
)

scanner_panel.pack_propagate(
    False
)


tk.Label(
    scanner_panel,
    text="FACE SCANNER",
    font=(
        "Segoe UI",
        13,
        "bold"
    ),
    fg=TEXT,
    bg=PANEL
).pack(
    pady=(30, 8)
)


tk.Label(
    scanner_panel,
    text="AI-powered identity\nverification",
    font=(
        "Segoe UI",
        9
    ),
    fg=MUTED,
    bg=PANEL,
    justify="center"
).pack()


scan_button = tk.Button(
    scanner_panel,
    text="◉  SCAN FACE",
    command=scan_face,
    font=(
        "Segoe UI",
        10,
        "bold"
    ),
    fg=BG,
    bg=GREEN,
    activeforeground=BG,
    activebackground=GREEN,
    relief="flat",
    bd=0,
    cursor="hand2",
    height=2
)

scan_button.pack(
    fill="x",
    padx=35,
    pady=25
)


register_button = tk.Button(
    scanner_panel,
    text="＋ REGISTER USER",
    command=register_user,
    font=(
        "Segoe UI",
        9,
        "bold"
    ),
    fg=TEXT,
    bg=CARD,
    activeforeground=GREEN,
    activebackground=CARD,
    relief="flat",
    bd=0,
    cursor="hand2",
    height=2
)

register_button.pack(
    fill="x",
    padx=35,
    pady=5
)


delete_button = tk.Button(
    scanner_panel,
    text="✕ DELETE USER",
    command=delete_user,
    font=(
        "Segoe UI",
        9,
        "bold"
    ),
    fg=RED,
    bg=CARD,
    activeforeground=RED,
    activebackground=CARD,
    relief="flat",
    bd=0,
    cursor="hand2",
    height=2
)

delete_button.pack(
    fill="x",
    padx=35,
    pady=5
)


tk.Label(
    scanner_panel,
    text="Recognition Engine",
    font=(
        "Segoe UI",
        8
    ),
    fg=MUTED,
    bg=PANEL
).pack(
    pady=(20, 3)
)


tk.Label(
    scanner_panel,
    text="● ONLINE",
    font=(
        "Segoe UI",
        9,
        "bold"
    ),
    fg=GREEN,
    bg=PANEL
).pack()


tk.Label(
    scanner_panel,
    text="LBPH FACE RECOGNITION",
    font=(
        "Segoe UI",
        7
    ),
    fg=MUTED,
    bg=PANEL
).pack(
    pady=5
)


# =========================================================
# UPDATE ATTENDANCE LIST
# =========================================================

def update_attendance_list():

    for widget in attendance_list.winfo_children():

        widget.destroy()

    records = today_attendance()

    if not records:

        tk.Label(
            attendance_list,
            text="No attendance recorded today.",
            font=(
                "Segoe UI",
                10
            ),
            fg=MUTED,
            bg=PANEL
        ).pack(
            pady=25
        )

        return

    for row in records[-8:]:

        item = tk.Frame(
            attendance_list,
            bg=CARD
        )

        item.pack(
            fill="x",
            padx=15,
            pady=3
        )

        tk.Label(
            item,
            text=row[0],
            font=(
                "Segoe UI",
                9,
                "bold"
            ),
            fg=TEXT,
            bg=CARD,
            anchor="w"
        ).pack(
            side="left",
            padx=10,
            pady=10
        )

        tk.Label(
            item,
            text=row[2],
            font=(
                "Segoe UI",
                9
            ),
            fg=MUTED,
            bg=CARD
        ).pack(
            side="right",
            padx=15
        )


# =========================================================
# REFRESH DASHBOARD
# =========================================================

def refresh_dashboard():

    users_count.config(
        text=str(
            len(get_users())
        )
    )

    today_count.config(
        text=str(
            len(today_attendance())
        )
    )

    total_count.config(
        text=str(
            len(get_attendance())
        )
    )

    update_attendance_list()

    # Latest scan status
    latest_status_label.config(
        text=(
            f"● {last_scan_status}  |  "
            f"{last_scan_name}  |  "
            f"{last_scan_time}"
        ),
        fg=last_scan_color
    )

    root.after(
        2000,
        refresh_dashboard
    )


# =========================================================
# START
# =========================================================

refresh_dashboard()

root.mainloop()