from encryption import encrypt_data, decrypt_data

message = "Test User Data"

encrypted = encrypt_data(message)

print("Encrypted:", encrypted)

decrypted = decrypt_data(encrypted)

print("Decrypted:", decrypted)