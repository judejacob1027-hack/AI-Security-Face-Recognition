import os
import subprocess

KNOWN_FACES = "known_faces"


def show_users():
    print("\n========== REGISTERED USERS ==========\n")

    if not os.path.exists(KNOWN_FACES):
        print("No users registered.")
        return

    users = [
        name for name in os.listdir(KNOWN_FACES)
        if os.path.isdir(os.path.join(KNOWN_FACES, name))
    ]

    if not users:
        print("No users registered.")
        return

    for number, user in enumerate(users, 1):
        folder = os.path.join(KNOWN_FACES, user)

        photos = [
            file for file in os.listdir(folder)
            if file.lower().endswith(
                (".jpg", ".jpeg", ".png")
            )
        ]

        print(f"{number}. {user}  |  Photos: {len(photos)}")


def delete_user():
    show_users()

    name = input(
        "\nEnter user name to delete: "
    ).strip()

    folder = os.path.join(
        KNOWN_FACES,
        name
    )

    if not os.path.isdir(folder):
        print("\nUser not found.")
        return

    confirm = input(
        f"Delete '{name}' and all photos? (yes/no): "
    ).strip().lower()

    if confirm == "yes":

        import shutil

        shutil.rmtree(folder)

        print(
            f"\nUser '{name}' deleted successfully."
        )

        print("\nRetraining AI model...")

        subprocess.run(
            ["python", "main.py"]
        )

    else:
        print("\nDelete cancelled.")


def register_user():
    print("\n========== NEW USER REGISTRATION ==========\n")

    subprocess.run(
        ["python", "capture.py"]
    )

    print("\nRegistration finished.")

    print("\nUpdating AI model...")

    subprocess.run(
        ["python", "main.py"]
    )


while True:

    print("\n")
    print("==========================================")
    print("       AI SECURITY - USER MANAGEMENT")
    print("==========================================")
    print()
    print("1. Register New User")
    print("2. View Registered Users")
    print("3. Delete User")
    print("4. Exit")
    print()

    choice = input(
        "Select option: "
    ).strip()

    if choice == "1":

        register_user()

    elif choice == "2":

        show_users()

    elif choice == "3":

        delete_user()

    elif choice == "4":

        print("\nUser management closed.")
        break

    else:

        print("\nInvalid option.")