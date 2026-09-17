import cv2
import csv
import os
import winsound
from datetime import datetime

# ==========================================
# SETTINGS
# ==========================================

MODEL_FILE = "face_model.yml"
ATTENDANCE_FILE = "attendance.csv"
USERS_FILE = "users.txt"

# ==========================================
# LOAD AI MODEL
# ==========================================

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read(MODEL_FILE)

detector = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    "haarcascade_frontalface_default.xml"
)

# ==========================================
# LOAD REGISTERED USERS
# ==========================================

users = {}

if os.path.exists(USERS_FILE):

    with open(USERS_FILE, "r") as file:

        for line in file:

            line = line.strip()

            if not line:
                continue

            parts = line.split(",", 1)

            if len(parts) == 2:

                user_id = int(parts[0])
                user_name = parts[1]

                users[user_id] = user_name

print()
print("==========================================")
print("        AI FACE RECOGNITION SYSTEM")
print("==========================================")
print()

print("Registered users:")

for user_id, name in users.items():

    print(
        f"ID {user_id} -> {name}"
    )

print()

# ==========================================
# ATTENDANCE FUNCTION
# ==========================================

def mark_attendance(name):

    now = datetime.now()

    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")

    # --------------------------------------
    # CREATE FILE
    # --------------------------------------

    if not os.path.exists(ATTENDANCE_FILE):

        with open(
            ATTENDANCE_FILE,
            "w",
            newline=""
        ) as file:

            writer = csv.writer(file)

            writer.writerow(
                ["Name", "Date", "Time"]
            )

    # --------------------------------------
    # CHECK EXISTING ATTENDANCE
    # --------------------------------------

    with open(
        ATTENDANCE_FILE,
        "r",
        newline=""
    ) as file:

        reader = csv.reader(file)

        for row in reader:

            if len(row) >= 2:

                if (
                    row[0] == name
                    and row[1] == today
                ):

                    print(
                        f"ATTENDANCE ALREADY MARKED: "
                        f"{name} | {today}"
                    )

                    return False

    # --------------------------------------
    # ADD NEW ATTENDANCE
    # --------------------------------------

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

    return True


# ==========================================
# LOAD ATTENDANCE
# ==========================================

def load_attendance():

    records = []

    if not os.path.exists(
        ATTENDANCE_FILE
    ):

        return records

    with open(
        ATTENDANCE_FILE,
        "r",
        newline=""
    ) as file:

        reader = csv.reader(file)

        next(reader, None)

        for row in reader:

            if len(row) >= 3:

                records.append(row)

    return records


# ==========================================
# TEXT FUNCTION
# ==========================================

def draw_text(
    frame,
    value,
    position,
    size=0.6,
    color=(255, 255, 255),
    thickness=1
):

    cv2.putText(
        frame,
        str(value),
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        size,
        color,
        thickness,
        cv2.LINE_AA
    )


# ==========================================
# CAMERA
# ==========================================

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

    print("ERROR: Camera could not be opened.")
    raise SystemExit


# ==========================================
# VARIABLES
# ==========================================

unknown_alerted = False

last_recognized_name = "NO USER"

# ==========================================
# MAIN LOOP
# ==========================================

while True:

    ret, frame = camera.read()

    if not ret:

        print("ERROR: Could not read camera.")
        break

    # Mirror camera
    frame = cv2.flip(
        frame,
        1
    )

    # Convert to grayscale
    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    # Detect faces
    detected_faces = detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80)
    )

    recognized_name = "NO USER"
    verified = False

    # ======================================
    # FACE RECOGNITION
    # ======================================

    for (
        x,
        y,
        w,
        h
    ) in detected_faces:

        face_gray = gray[
            y:y+h,
            x:x+w
        ]

        user_id, confidence = recognizer.predict(
            face_gray
        )

        # ----------------------------------
        # VERIFIED USER
        # ----------------------------------

        if (
            confidence < 100
            and user_id in users
        ):

            recognized_name = users[
                user_id
            ]

            verified = True

            # Mark attendance
            mark_attendance(
                recognized_name
            )

            unknown_alerted = False

            box_color = (
                0,
                220,
                120
            )

        # ----------------------------------
        # UNKNOWN USER
        # ----------------------------------

        else:

            recognized_name = "UNKNOWN"

            verified = False

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

                winsound.Beep(
                    1000,
                    300
                )

                unknown_alerted = True

        # ==================================
        # FACE BOX
        # ==================================

        cv2.rectangle(
            frame,
            (
                int(x),
                int(y)
            ),
            (
                int(x + w),
                int(y + h)
            ),
            box_color,
            2
        )

        # ==================================
        # NAME ABOVE FACE
        # ==================================

        draw_text(
            frame,
            recognized_name,
            (
                int(x),
                int(y - 10)
            ),
            0.7,
            box_color,
            2
        )

    # ==========================================
    # NO FACE
    # ==========================================

    if len(detected_faces) == 0:

        unknown_alerted = False

    # ==========================================
    # DASHBOARD SIZE
    # ==========================================

    height, width = frame.shape[:2]

    # ==========================================
    # HEADER
    # ==========================================

    cv2.rectangle(
        frame,
        (0, 0),
        (width, 70),
        (25, 25, 25),
        -1
    )

    draw_text(
        frame,
        "AI SECURITY",
        (30, 32),
        0.8,
        (255, 255, 255),
        2
    )

    draw_text(
        frame,
        "FACE RECOGNITION / ATTENDANCE",
        (30, 57),
        0.45,
        (170, 170, 170),
        1
    )

    draw_text(
        frame,
        "SYSTEM ONLINE",
        (width - 180, 38),
        0.5,
        (0, 220, 120),
        1
    )

    # ==========================================
    # RIGHT DASHBOARD PANEL
    # ==========================================

    panel_x = width - 330

    cv2.rectangle(
        frame,
        (
            panel_x,
            90
        ),
        (
            width - 20,
            height - 20
        ),
        (30, 30, 30),
        -1
    )

    cv2.rectangle(
        frame,
        (
            panel_x,
            90
        ),
        (
            width - 20,
            height - 20
        ),
        (70, 70, 70),
        1
    )

    # ==========================================
    # IDENTITY
    # ==========================================

    draw_text(
        frame,
        "IDENTITY",
        (
            panel_x + 20,
            125
        ),
        0.45,
        (150, 150, 150),
        1
    )

    draw_text(
        frame,
        recognized_name,
        (
            panel_x + 20,
            165
        ),
        0.9,
        (255, 255, 255),
        2
    )

    # ==========================================
    # VERIFICATION
    # ==========================================

    draw_text(
        frame,
        "VERIFICATION",
        (
            panel_x + 20,
            220
        ),
        0.4,
        (150, 150, 150),
        1
    )

    if verified:

        draw_text(
            frame,
            "VERIFIED",
            (
                panel_x + 20,
                260
            ),
            0.75,
            (0, 220, 120),
            2
        )

    elif recognized_name == "UNKNOWN":

        draw_text(
            frame,
            "ALERT",
            (
                panel_x + 20,
                260
            ),
            0.75,
            (0, 0, 255),
            2
        )

    else:

        draw_text(
            frame,
            "WAITING",
            (
                panel_x + 20,
                260
            ),
            0.7,
            (180, 180, 180),
            2
        )

    # ==========================================
    # TODAY ATTENDANCE
    # ==========================================

    records = load_attendance()

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    today_records = []

    for row in records:

        if (
            len(row) >= 2
            and row[1] == today
        ):

            today_records.append(row)

    draw_text(
        frame,
        "TODAY ATTENDANCE",
        (
            panel_x + 20,
            325
        ),
        0.4,
        (150, 150, 150),
        1
    )

    draw_text(
        frame,
        str(len(today_records)),
        (
            panel_x + 20,
            360
        ),
        0.8,
        (255, 255, 255),
        2
    )

    # ==========================================
    # TOTAL RECORDS
    # ==========================================

    draw_text(
        frame,
        "TOTAL RECORDS",
        (
            panel_x + 20,
            410
        ),
        0.4,
        (150, 150, 150),
        1
    )

    draw_text(
        frame,
        str(len(records)),
        (
            panel_x + 20,
            445
        ),
        0.8,
        (255, 255, 255),
        2
    )

    # ==========================================
    # SECURITY STATUS
    # ==========================================

    draw_text(
        frame,
        "SECURITY STATUS",
        (
            panel_x + 20,
            495
        ),
        0.4,
        (150, 150, 150),
        1
    )

    if recognized_name == "UNKNOWN":

        draw_text(
            frame,
            "ALERT",
            (
                panel_x + 20,
                530
            ),
            0.7,
            (0, 0, 255),
            2
        )

    elif verified:

        draw_text(
            frame,
            "NORMAL",
            (
                panel_x + 20,
                530
            ),
            0.7,
            (0, 220, 120),
            2
        )

    else:

        draw_text(
            frame,
            "STANDBY",
            (
                panel_x + 20,
                530
            ),
            0.7,
            (180, 180, 180),
            2
        )

    # ==========================================
    # FOOTER
    # ==========================================

    draw_text(
        frame,
        "Press Q to exit",
        (
            30,
            height - 20
        ),
        0.45,
        (150, 150, 150),
        1
    )

    # ==========================================
    # DISPLAY
    # ==========================================

    cv2.imshow(
        "AI SECURITY - FACE RECOGNITION",
        frame
    )

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):

        break


# ==========================================
# CLOSE SYSTEM
# ==========================================

camera.release()

cv2.destroyAllWindows()

print()
print("==========================================")
print("       RECOGNITION SYSTEM STOPPED")
print("==========================================")