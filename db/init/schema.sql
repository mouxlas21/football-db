-- =========================
-- PHASE 1 — CORE ENTITIES
-- =========================

CREATE TABLE IF NOT EXISTS country (
  country_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE,
  iso2            CHAR(2) UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_country_name ON country(name);

CREATE TABLE IF NOT EXISTS stadium (
  stadium_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name            TEXT NOT NULL,
  city            TEXT,
  country_id      BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  capacity        INTEGER,
  opened_year     SMALLINT,
  lat             DOUBLE PRECISION,
  lng             DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS club (
  club_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE,
  short_name      TEXT,
  founded         SMALLINT,
  country_id      BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  stadium_id      BIGINT REFERENCES stadium(stadium_id) ON DELETE SET NULL,
  colors          TEXT
);
CREATE INDEX IF NOT EXISTS ix_club_country  ON club(country_id);
CREATE INDEX IF NOT EXISTS ix_club_stadium  ON club(stadium_id);

CREATE TABLE IF NOT EXISTS team (
  team_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name            TEXT NOT NULL,
  type            TEXT NOT NULL DEFAULT 'club',
  club_id         BIGINT REFERENCES club(club_id) ON DELETE SET NULL,
  national_country_id BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  CONSTRAINT team_kind_ck CHECK (
    (club_id IS NOT NULL AND national_country_id IS NULL)
    OR
    (club_id IS NULL AND national_country_id IS NOT NULL)
  )
);

CREATE TABLE IF NOT EXISTS person (
  person_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  full_name       TEXT NOT NULL,
  known_as        TEXT,
  dob             DATE,
  country_id      BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  height_cm       SMALLINT,
  weight_kg       SMALLINT
);

CREATE TABLE IF NOT EXISTS player (
  player_id       BIGINT PRIMARY KEY REFERENCES person(person_id) ON DELETE CASCADE,
  foot            TEXT,
  primary_position TEXT
);

CREATE TABLE IF NOT EXISTS competition (
  competition_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE,
  type            TEXT NOT NULL,
  organizer       TEXT,
  country_id      BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  confederation   TEXT
);

CREATE TABLE IF NOT EXISTS season (
  season_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  competition_id  BIGINT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  start_date      DATE,
  end_date        DATE,
  UNIQUE (competition_id, name)
);

CREATE TABLE IF NOT EXISTS stage (
  stage_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season_id       BIGINT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  stage_order     SMALLINT NOT NULL,
  format          TEXT NOT NULL,
  UNIQUE (season_id, name)
);

CREATE TABLE IF NOT EXISTS round (
  round_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  stage_id        BIGINT NOT NULL REFERENCES stage(stage_id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  round_order     SMALLINT NOT NULL,
  two_legs        BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (stage_id, name)
);

CREATE TABLE IF NOT EXISTS "group" (
  group_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  stage_id        BIGINT NOT NULL REFERENCES stage(stage_id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  UNIQUE (stage_id, name)
);

CREATE TABLE IF NOT EXISTS entry (
  entry_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season_id       BIGINT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
  team_id         BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  seeding         TEXT,
  pot             TEXT,
  invited         BOOLEAN DEFAULT FALSE,
  UNIQUE (season_id, team_id)
);

CREATE TABLE IF NOT EXISTS match (
  match_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  round_id        BIGINT NOT NULL REFERENCES round(round_id) ON DELETE CASCADE,
  group_id        BIGINT REFERENCES "group"(group_id) ON DELETE SET NULL,
  home_team_id    BIGINT NOT NULL REFERENCES team(team_id) ON DELETE RESTRICT,
  away_team_id    BIGINT NOT NULL REFERENCES team(team_id) ON DELETE RESTRICT,
  kickoff_utc     TIMESTAMPTZ NOT NULL,
  stadium_id      BIGINT REFERENCES stadium(stadium_id) ON DELETE SET NULL,
  attendance      INTEGER,
  status          TEXT NOT NULL DEFAULT 'scheduled',
  home_score      SMALLINT DEFAULT 0,
  away_score      SMALLINT DEFAULT 0,
  winner_team_id  BIGINT REFERENCES team(team_id) ON DELETE SET NULL,
  CONSTRAINT match_teams_different CHECK (home_team_id <> away_team_id)
);
CREATE INDEX IF NOT EXISTS ix_match_round ON match(round_id);
CREATE INDEX IF NOT EXISTS ix_match_kickoff ON match(kickoff_utc);
CREATE INDEX IF NOT EXISTS ix_match_teams ON match(home_team_id, away_team_id);

CREATE TABLE IF NOT EXISTS lineup (
  lineup_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  match_id        BIGINT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  team_id         BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  formation       TEXT,
  UNIQUE (match_id, team_id)
);

CREATE TABLE IF NOT EXISTS appearance (
  appearance_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  match_id        BIGINT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  team_id         BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  player_id       BIGINT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  shirt_number    SMALLINT,
  is_starter      BOOLEAN NOT NULL DEFAULT FALSE,
  minute_on       SMALLINT DEFAULT 0,
  minute_off      SMALLINT,
  captain         BOOLEAN DEFAULT FALSE,
  position        TEXT,
  UNIQUE (match_id, player_id)
);
CREATE INDEX IF NOT EXISTS ix_app_match_team ON appearance(match_id, team_id);
CREATE INDEX IF NOT EXISTS ix_app_match_player ON appearance(match_id, player_id);

CREATE TABLE IF NOT EXISTS substitution (
  sub_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  match_id        BIGINT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  team_id         BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  minute          SMALLINT NOT NULL,
  player_off_id   BIGINT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  player_on_id    BIGINT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_sub_match ON substitution(match_id);

CREATE TABLE IF NOT EXISTS event (
  event_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  match_id        BIGINT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  team_id         BIGINT REFERENCES team(team_id) ON DELETE SET NULL,
  player_id       BIGINT REFERENCES player(player_id) ON DELETE SET NULL,
  minute          SMALLINT NOT NULL,
  second          SMALLINT DEFAULT 0,
  period          TEXT NOT NULL DEFAULT '1',
  type            TEXT NOT NULL,
  x               NUMERIC(5,2),
  y               NUMERIC(5,2),
  end_x           NUMERIC(5,2),
  end_y           NUMERIC(5,2),
  outcome         TEXT,
  body_part       TEXT,
  qualifiers      JSONB
);
CREATE INDEX IF NOT EXISTS ix_event_match ON event(match_id);
CREATE INDEX IF NOT EXISTS ix_event_match_player ON event(match_id, player_id);
CREATE INDEX IF NOT EXISTS ix_event_type ON event(type);

CREATE TABLE IF NOT EXISTS team_match_stats (
  match_id        BIGINT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  team_id         BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  possession_pct  NUMERIC(5,2),
  shots           SMALLINT,
  shots_ot        SMALLINT,
  xg              NUMERIC(6,3),
  passes          INTEGER,
  pass_pct        NUMERIC(5,2),
  corners         SMALLINT,
  fouls           SMALLINT,
  offsides        SMALLINT,
  PRIMARY KEY (match_id, team_id)
);

CREATE TABLE IF NOT EXISTS player_match_stats (
  match_id        BIGINT NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
  player_id       BIGINT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  minutes         SMALLINT,
  touches         INTEGER,
  passes          INTEGER,
  pass_completed  INTEGER,
  tackles         SMALLINT,
  interceptions   SMALLINT,
  blocks          SMALLINT,
  clearances      SMALLINT,
  aerials_won     SMALLINT,
  duels_won       SMALLINT,
  shots           SMALLINT,
  xg              NUMERIC(6,3),
  xa              NUMERIC(6,3),
  key_passes      SMALLINT,
  PRIMARY KEY (match_id, player_id)
);

CREATE TABLE IF NOT EXISTS table_standings (
  standing_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season_id       BIGINT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
  stage_id        BIGINT REFERENCES stage(stage_id) ON DELETE SET NULL,
  group_id        BIGINT REFERENCES "group"(group_id) ON DELETE SET NULL,
  team_id         BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  played          SMALLINT NOT NULL DEFAULT 0,
  w               SMALLINT NOT NULL DEFAULT 0,
  d               SMALLINT NOT NULL DEFAULT 0,
  l               SMALLINT NOT NULL DEFAULT 0,
  gf              SMALLINT NOT NULL DEFAULT 0,
  ga              SMALLINT NOT NULL DEFAULT 0,
  gd              SMALLINT NOT NULL DEFAULT 0,
  pts             SMALLINT NOT NULL DEFAULT 0,
  position        SMALLINT,
  UNIQUE (season_id, COALESCE(stage_id,0), COALESCE(group_id,0), team_id)
);
