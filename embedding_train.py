import os
import pickle
import face_recognition

KNOWN_FACES_DIR = "known_faces"
OUTPUT_FILE = "face_encodings.pkl"

known_encodings = []
known_names = []

print("\n======================================")
print("   AI FACE RECOGNITION - TRAINING")
print("======================================\n")

if not os.path.exists(KNOWN_FACES_DIR):
    print("known_faces folder not found.")
    exit()

for person_name in os.listdir(KNOWN_FACES_DIR):

    person_folder = os.path.join(KNOWN_FACES_DIR, person_name)

    if not os.path.isdir(person_folder):
        continue

    print(f"Processing: {person_name}")

    for filename in os.listdir(person_folder):

        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        image_path = os.path.join(person_folder, filename)

        try:
            image = face_recognition.load_image_file(image_path)

            face_locations = face_recognition.face_locations(image)

            if len(face_locations) == 0:
                print(f"  SKIPPED - No face: {filename}")
                continue

            if len(face_locations) > 1:
                print(f"  SKIPPED - Multiple faces: {filename}")
                continue

            encoding = face_recognition.face_encodings(
                image,
                known_face_locations=face_locations
            )[0]

            known_encodings.append(encoding)
            known_names.append(person_name)

            print(f"  Added: {filename}")

        except Exception as e:
            print(f"  ERROR: {filename} -> {e}")

data = {
    "encodings": known_encodings,
    "names": known_names
}

with open(OUTPUT_FILE, "wb") as file:
    pickle.dump(data, file)

print("\n======================================")
print("TRAINING COMPLETED")
print("======================================")
print(f"Total face encodings: {len(known_encodings)}")
print(f"Users: {len(set(known_names))}")
print(f"Saved to: {OUTPUT_FILE}")
print("======================================\n")