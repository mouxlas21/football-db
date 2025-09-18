## Daily start-up

cd ~/Documents/football-db
docker compose up -d         # start/recreate containers (backend, db, pgAdmin)
docker compose logs -f backend 
docker compose logs --tail=200 backend

## password changes

- For backend (DATABASE_URL) and pgAdmin creds → recreate the containers:
    docker compose up -d --build

- For Postgres (POSTGRES_PASSWORD) → that env var is only used on first DB initialization. Changing it in .env later doesn’t change the real password.

    # Change DB password in one of two ways:

    A) Alter the user (keeps data)
        1) get the actual db container name:
        docker ps  # look for something like football-db-db-1
        2) change the password inside Postgres: docker exec -it <db-container> psql -U footuser -d football -c "ALTER USER footuser WITH PASSWORD 'NEWPASS';"
        3) update .env (POSTGRES_PASSWORD=NEWPASS) and restart backend so it uses the new pass: docker compose up -d --build

    B) Re-initialize the database (DESTROYS data)
        docker compose down
        docker volume rm football-db_dbdata
        # edit .env with the new password
        docker compose up -d --build

    Tip: since this is dev, option B is fine early on; once we store real data, use A.

## URLS
- http://localhost:8000/
- http://localhost:5050/


docker compose build backend
docker compose up -d backend
docker compose restart backend

Competition
   └── Season (e.g. Bundesliga 2024/25)
        └── Stage (e.g. Regular Season, Group Stage, Knockout)
             └── Round (e.g. Matchday 1, Quarterfinals)
                  └── Match (e.g. Bayern vs Dortmund, 15 Jan 2025)

matches take teams_ids from team table

### Build order (safe topological order)

## Phase A – bases
1)associations
2)countries
3)stadiums
4)competitions
5)clubs
6)teams

7)seasons
8)stages
9)stages rounds
10)stages groups

11)person → player, coach, official


entry

Phase B – fixtures
12) match

Phase C – match data
13) lineup
14) appearance
15) substitution
16) event
17) team_match_stats
18) player_match_stats
19) table_standings