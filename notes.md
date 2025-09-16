## Daily start-up

cd ~/Documents/football-db
docker compose up -d         # start/recreate containers (backend, db, pgAdmin)
docker compose logs -f backend 

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