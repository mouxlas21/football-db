# backend/app/services/importers/utils/bulk_team_sync.py
from sqlalchemy.orm import Session
from sqlalchemy import text

def ensure_club_teams(db: Session) -> None:
    """
    Ensure every club has at least one 'club' team.
    Then sync the *default* team name to the club name when it matches the default.
    This is idempotent and safe to re-run.
    """
    # Create a default 'club' team for clubs with no team at all
    db.execute(text("""
        INSERT INTO team (name, type, club_id, national_country_id, gender, age_group, squad_level)
        SELECT c.name, 'club', c.club_id, NULL, 'men', 'senior', 'first'
        FROM club c
        LEFT JOIN team t
               ON t.type = 'club'
              AND t.club_id = c.club_id
        WHERE t.team_id IS NULL;
    """))

    # Keep the default team's name in sync if it equals the club name (don’t touch custom-named variants)
    db.execute(text("""
        UPDATE team t
        SET name = c.name
        FROM club c
        WHERE t.type = 'club'
          AND t.club_id = c.club_id
          AND t.name IS DISTINCT FROM c.name
          -- only update teams whose name *was meant* to mirror the club (the default row)
          AND (
                -- heuristic: if there's only one 'club' team for this club, treat it as the default
                (SELECT COUNT(*) FROM team tt WHERE tt.type='club' AND tt.club_id=c.club_id) = 1
              );
    """))

def ensure_national_teams(db: Session) -> None:
    """
    Ensure every country has a senior default 'national' team (age_group NULL, gender NULL).
    Then sync that default team’s name to the country name. Leaves U- and gendered teams alone.
    """
    # Insert missing senior default national team
    db.execute(text("""
        INSERT INTO team (name, type, club_id, national_country_id, gender, age_group, squad_level)
        SELECT co.name, 'national', NULL, co.country_id, 'men', 'senior', 'first'
        FROM country co
        LEFT JOIN team t
               ON t.type = 'national'
              AND t.national_country_id = co.country_id
              AND t.age_group IS NULL
              AND t.gender    IS NULL
        WHERE t.team_id IS NULL;
    """))

    # Sync *only* the senior default national team’s name
    db.execute(text("""
        UPDATE team t
        SET name = co.name
        FROM country co
        WHERE t.type = 'national'
          AND t.national_country_id = co.country_id
          AND t.age_group IS NULL
          AND t.gender    IS NULL
          AND t.name IS DISTINCT FROM co.name;
    """))
