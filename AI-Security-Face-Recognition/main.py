import cv2
import os
import numpy as np

KNOWN_FACES_FOLDER = "known_faces"
MODEL_FILE = "face_model.yml"
USERS_FILE = "users.txt"

detector = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    "haarcascade_frontalface_default.xml"
)

faces = []
labels = []
label_names = {}

print()
print("==========================================")
print("        AI FACE MODEL TRAINING")
print("==========================================")
print()

if not os.path.exists(KNOWN_FACES_FOLDER):
    print("known_faces folder not found.")
    raise SystemExit

# Stable user IDs
users = sorted([
    folder for folder in os.listdir(KNOWN_FACES_FOLDER)
    if os.path.isdir(
        os.path.join(KNOWN_FACES_FOLDER, folder)
    )
])

if not users:
    print("No registered users found.")
    raise SystemExit

current_id = 1

for user_name in users:

    user_folder = os.path.join(
        KNOWN_FACES_FOLDER,
        user_name
    )

    label_names[current_id] = user_name

    print(f"Processing user: {user_name}")

    image_count = 0

    files = sorted(os.listdir(user_folder))

    for filename in files:

        if not filename.lower().endswith(
            (".jpg", ".jpeg", ".png")
        ):
            continue

        image_path = os.path.join(
            user_folder,
            filename
        )

        image = cv2.imread(image_path)

        if image is None:
            print("  Could not read:", filename)
            continue

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        gray = cv2.equalizeHist(gray)

        detected_faces = detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=6,
            minSize=(100, 100)
        )

        if len(detected_faces) == 0:
            print("  No face found:", filename)
            continue

        # Select the largest detected face
        x, y, w, h = max(
            detected_faces,
            key=lambda rect: rect[2] * rect[3]
        )

        face = gray[y:y+h, x:x+w]

        # Fixed size for better training
        face = cv2.resize(
            face,
            (200, 200)
        )

        # Normalize face lighting
        face = cv2.equalizeHist(face)

        faces.append(face)
        labels.append(current_id)

        image_count += 1

    print(f"  Training images: {image_count}")
    print()

    current_id += 1


if len(faces) == 0:
    print("No usable face images found.")
    raise SystemExit


print("Training AI model...")
print()

recognizer = cv2.face.LBPHFaceRecognizer_create(
    radius=1,
    neighbors=8,
    grid_x=8,
    grid_y=8
)

recognizer.train(
    faces,
    np.array(labels)
)

recognizer.save(MODEL_FILE)


# Save user ID mapping
with open(USERS_FILE, "w") as file:

    for user_id, user_name in label_names.items():

        file.write(
            f"{user_id},{user_name}\n"
        )


print("==========================================")
print("     TRAINING COMPLETED SUCCESSFULLY")
print("==========================================")
print()

print("Registered users:")

for user_id, user_name in label_names.items():

    print(
        f"  ID {user_id} -> {user_name}"
    )

print()

print("Model saved as:", MODEL_FILE)
print("User database saved as:", USERS_FILE)
print()