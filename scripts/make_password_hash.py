import argparse
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def main():
    ap = argparse.ArgumentParser(description="Genera password_hash bcrypt para secrets.toml")
    ap.add_argument("--password", required=True, help="Password en texto plano")
    args = ap.parse_args()

    print(hash_password(args.password))

if __name__ == "__main__":
    main()
