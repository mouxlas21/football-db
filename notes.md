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

matches take teams_ids from team table and resolve name from team.name

### Build order (safe topological order)

## Phase A - bases
1)associations
2)countries
3)stadiums
4)competitions
5)clubs
6)teams

## Phase B - seasons and structure
7)seasons
    7a)if need be league_points_adjustment and/or league_table_snapshot
8)stages
9)stages rounds
10)stages groups
    10a)stages groups teams

## Phase C - fixtures
11) fixture

## Phase D - people
12)person
    12a)player
    12b)coach
    12c)official

## Phase D – match data
13) lineup
14) appearance
15) substitution
16) event
17) team_match_stats
18) player_match_stats
19) table_standings

    See the plan and import via CLI:

        docker compose exec backend python app/import_runner.py --dry-run
        docker compose exec backend python app/import_runner.py


    From the UI: open http://localhost:8000/admin/import and click Import CSVs.

    Only a pack later (when you adopt packs/):

    CLI: --pack bundesliga_2024_25

    UI: put bundesliga_2024_25 in the text field (uncomment the query string in JS if you want it wired).

/admin/import

football-db/
└─ data/
   ├─ base/
   │  ├─ associations.csv
   │  ├─ countries.csv
   │  ├─ stadiums.csv
   │  ├─ competitions.csv
   │  ├─ clubs.csv
   │  └─ teams.csv
   │
   ├─ people/                
   │  ├─ players.csv
   │  ├─ coaches.csv
   │  └─ officials.csv
   ├─ packs/
   │  ├─ uefa_cl_2023_24/
   │  │  ├─ season.csv
   │  │  ├─ stages.csv
   │  │  ├─ stage_rounds.csv
   │  │  ├─ stage_groups.csv
   │  │  ├─ stage_group_teams.csv
   │  │  ├─ fixtures.csv
   │  │  ├─ people/            
   │  │  │  ├─ players.csv
   │  │  │  └─ coaches.csv
   │  │  └─ match_data/
   │  │     ├─ lineups.csv
   │  │     ├─ appearances.csv
   │  │     ├─ substitutions.csv
   │  │     ├─ events.csv
   │  │     ├─ team_match_stats.csv
   │  │     ├─ player_match_stats.csv
   │  │     └─ table_standings.csv
   │  │
   │  └─ bundesliga_2024_25/
   │     ├─ season.csv
   │     ├─ stages.csv
   │     ├─ stage_rounds.csv
   │     ├─ fixtures.csv
   └─ import_manifest.json
