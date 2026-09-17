import cv2
import os

# ==========================================
# USER NAME
# ==========================================

name = input("Enter user name: ").strip()

if not name:
    print("Name cannot be empty.")
    exit()

# ==========================================
# USER FOLDER
# ==========================================

folder = os.path.join("known_faces", name)

os.makedirs(folder, exist_ok=True)

print()
print("Registration started for:", name)
print("Press SPACE to capture photo")
print("Press Q to finish")
print()

# ==========================================
# CAMERA
# ==========================================

camera = cv2.VideoCapture(0)

count = 1

while True:

    ret, frame = camera.read()

    if not ret:
        print("Camera could not be opened.")
        break

    frame = cv2.flip(frame, 1)

    cv2.putText(
        frame,
        f"REGISTERING: {name}",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )

    cv2.putText(
        frame,
        "SPACE = CAPTURE   Q = FINISH",
        (30, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (180, 180, 180),
        1
    )

    cv2.imshow("USER REGISTRATION", frame)

    key = cv2.waitKey(1) & 0xFF

    # SPACE
    if key == 32:

        filename = os.path.join(
            folder,
            f"{name}_{count}.jpg"
        )

        cv2.imwrite(filename, frame)

        print("Saved:", filename)

        count += 1

    # Q
    elif key == ord("q"):

        break


camera.release()
cv2.destroyAllWindows()

print()
print("Registration completed.")
print("Photos saved:", count - 1)