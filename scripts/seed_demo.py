"""Populate an empty demo database: python -m scripts.seed_demo --confirm-demo."""

import argparse
from datetime import datetime, timedelta, timezone
from random import Random

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import create_database_engine
from app.models import HelpRequest, IssueCategory, RequestStatus


def seed_demo_data(session: Session, *, now: datetime | None = None) -> int:
    """Add fictional requests; the caller owns the transaction."""
    # Hold off new submissions until the empty-table check and inserts finish together.
    session.execute(text("LOCK TABLE help_requests IN SHARE ROW EXCLUSIVE MODE"))
    if session.scalar(select(func.count()).select_from(HelpRequest)):
        raise ValueError("Demo data requires an empty help_requests table. Use a separate demo database.")
    now = now or datetime.now(timezone.utc)
    random = Random(17)
    names = ["Taylor Example", "Morgan Sample", "Casey Demo", "Avery Example", "Jordan Sample", "Riley Demo"]
    assignments = ["Lab 3 — Loops", "Lab 4 — Lists", "Lab 5 — Functions", "Lab 6 — Files"]
    descriptions = {
        IssueCategory.DEBUGGING: "My loop skips the final list item. I tried printing the index before each iteration.",
        IssueCategory.SYNTAX: "The function definition raises a SyntaxError. I can't find the missing punctuation.",
        IssueCategory.CONCEPTUAL: "I'm not sure when to return a value instead of printing it.",
        IssueCategory.ENVIRONMENT: "My editor is using a different Python interpreter than the terminal.",
        IssueCategory.OTHER: "I'd like help choosing a starting point for this problem.",
    }
    records = []
    daily_counts = [3, 5, 4, 7, 9, 6, 2, 4, 8, 7, 5, 9, 4, 6]
    for day, count in zip(reversed(range(14)), daily_counts):
        for index in range(count):
            category = random.choices(list(descriptions), weights=[5, 2, 3, 1, 1])[0]
            created = now - timedelta(days=day, hours=3, minutes=index * 12)
            started = created + timedelta(minutes=random.choice([2, 3, 5, 8, 12, 18]))
            records.append(HelpRequest(
                student_name=random.choice(names), assignment=random.choice(assignments),
                issue_category=category, description=descriptions[category],
                status=RequestStatus.RESOLVED, assigned_ta=random.choice(["Alex Example", "Jamie Example"]),
                created_at=created, claimed_at=created + timedelta(minutes=1), started_at=started,
                resolved_at=started + timedelta(minutes=random.choice([3, 6, 10, 14, 22])),
            ))
    for index in range(6):
        created = now - timedelta(minutes=6 + index * 4)
        helping = index < 2
        assigned = index < 3
        records.append(HelpRequest(
            student_name=names[index], assignment=assignments[index % len(assignments)],
            issue_category=IssueCategory.DEBUGGING if helping else IssueCategory.CONCEPTUAL,
            description=descriptions[IssueCategory.DEBUGGING if helping else IssueCategory.CONCEPTUAL],
            status=RequestStatus.IN_PROGRESS if helping else RequestStatus.PENDING,
            assigned_ta=("Alex Example" if index % 2 == 0 else "Jamie Example") if assigned else None,
            created_at=created, claimed_at=created + timedelta(minutes=1) if assigned else None,
            started_at=created + timedelta(minutes=3) if helping else None,
        ))
    session.add_all(records)
    session.flush()
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-demo", action="store_true", help="Confirm this is a database for fictional demo data")
    if not parser.parse_args().confirm_demo:
        parser.error("Use --confirm-demo with an empty demo database. Existing requests are never cleared.")
    engine = create_database_engine(Settings())
    try:
        with Session(engine) as session, session.begin():
            count = seed_demo_data(session)
        print(f"Created {count} fictional demo requests.")
        return 0
    except ValueError as error:
        print(str(error))
        return 1
    except SQLAlchemyError:
        print("Could not seed demo data. Check the database connection and run Alembic migrations first.")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
