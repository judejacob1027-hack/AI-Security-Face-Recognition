import csv
import os
from datetime import datetime

FILE_NAME = "attendance.csv"


def mark_attendance(name):

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")

    # Create CSV if it doesn't exist
    if not os.path.exists(FILE_NAME):

        with open(FILE_NAME, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Name", "Date", "Time"])

    # Check today's attendance
    with open(FILE_NAME, "r", newline="") as file:

        reader = csv.reader(file)

        for row in reader:

            if len(row) >= 2:

                if row[0] == name and row[1] == today:
                    return False

    # Mark attendance
    with open(FILE_NAME, "a", newline="") as file:

        writer = csv.writer(file)
        writer.writerow([
            name,
            today,
            current_time
        ])

    print(f"ATTENDANCE MARKED: {name} | {today} | {current_time}")

    return True