from app.db.session import SessionLocal, create_schema
from app.services.bootstrap import seed_demo_data


def main() -> None:
    create_schema()
    with SessionLocal() as db:
        seed_demo_data(db)
    print("Demo policies, runbooks, and dependencies are ready.")


if __name__ == "__main__":
    main()
