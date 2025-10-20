-- =========================
-- PHASE 1 — CORE ENTITIES
-- =========================

CREATE TABLE IF NOT EXISTS association (
  ass_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  founded_year SMALLINT,
  level TEXT NOT NULL CHECK (level IN ('federation','confederation','association','sub_confederation')),
  logo_filename TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Self-referential junction table for multi-parent hierarchy
CREATE TABLE IF NOT EXISTS association_parent (
  ass_id        BIGINT NOT NULL REFERENCES association(ass_id) ON DELETE CASCADE,
  parent_ass_id BIGINT NOT NULL REFERENCES association(ass_id) ON DELETE CASCADE,
  PRIMARY KEY (ass_id, parent_ass_id)
);

-- Country status enum
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'country_status') THEN
    CREATE TYPE country_status AS ENUM ('active','historical');
  END IF;
END$$;

-- Drop & recreate
DROP TABLE IF EXISTS country CASCADE;

CREATE TABLE country (
  country_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name              TEXT NOT NULL UNIQUE,
  nat_association   TEXT,
  flag_filename     TEXT,

  confed_ass_id     BIGINT REFERENCES association(ass_id) ON DELETE SET NULL,

  fifa_code VARCHAR(3) UNIQUE
    CHECK (char_length(fifa_code) = 3 AND fifa_code ~ '^[A-Z]{3}$'),

  c_status country_status NOT NULL DEFAULT 'active',

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_country_name ON country(name);
CREATE INDEX IF NOT EXISTS idx_country_confed_ass_id ON country(confed_ass_id);
CREATE INDEX IF NOT EXISTS ix_country_status ON country(c_status);

CREATE TABLE country_sub_confed (
  country_id        BIGINT NOT NULL REFERENCES country(country_id) ON DELETE CASCADE,
  sub_confed_ass_id BIGINT NOT NULL REFERENCES association(ass_id) ON DELETE CASCADE,
  PRIMARY KEY (country_id, sub_confed_ass_id)
);

CREATE INDEX idx_csc_sub_confed ON country_sub_confed(sub_confed_ass_id);

CREATE TABLE IF NOT EXISTS stadium (
  stadium_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name            TEXT NOT NULL,
  city            TEXT,
  country_id      BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  capacity        INTEGER,
  opened_year     SMALLINT,
  photo_filename  TEXT,
  lat             DOUBLE PRECISION,
  lng             DOUBLE PRECISION,
  renovated_years SMALLINT[],      
  closed_year     SMALLINT,       
  tenants         TEXT[],  

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()         
);

CREATE INDEX IF NOT EXISTS idx_stadium_country_id ON stadium(country_id);
CREATE INDEX IF NOT EXISTS idx_stadium_closed_year ON stadium(closed_year);
CREATE INDEX IF NOT EXISTS idx_stadium_name_ci ON stadium((lower(name)));

CREATE TABLE IF NOT EXISTS competition (
  competition_id      BIGSERIAL PRIMARY KEY,
  slug                TEXT NOT NULL UNIQUE,          
  name                TEXT NOT NULL,
  type                TEXT NOT NULL,                 
  tier                SMALLINT,                      
  cup_rank              TEXT,                          
  gender              TEXT,                          
  age_group           TEXT,                          
  status              TEXT NOT NULL DEFAULT 'active',
  notes               TEXT,
  logo_filename       TEXT,

  country_id          BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  organizer_ass_id    BIGINT REFERENCES association(ass_id) ON DELETE SET NULL,

  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- guard against exact duplicates across same country+organizer
  UNIQUE (name, country_id, organizer_ass_id)
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_comp_country       ON competition (country_id);
CREATE INDEX IF NOT EXISTS idx_comp_organizer     ON competition (organizer_ass_id);
CREATE INDEX IF NOT EXISTS idx_comp_type_tier     ON competition (type, tier);

CREATE TABLE IF NOT EXISTS club (
  club_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  short_name TEXT,
  founded SMALLINT,
  country_id BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  stadium_id BIGINT REFERENCES stadium(stadium_id) ON DELETE SET NULL,
  logo_filename TEXT,
  colors TEXT
);
CREATE INDEX IF NOT EXISTS idx_club_country_id ON club(country_id);
CREATE INDEX IF NOT EXISTS idx_club_stadium_id ON club(stadium_id);

CREATE TABLE IF NOT EXISTS team (
  team_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'club',
  club_id BIGINT REFERENCES club(club_id) ON DELETE SET NULL,
  national_country_id BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  logo_filename TEXT,
  gender TEXT,
  age_group TEXT,
  squad_level TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

  CONSTRAINT chk_team_affiliation
    CHECK (
      (type = 'club'     AND club_id IS NOT NULL AND national_country_id IS NULL)
      OR
      (type = 'national' AND national_country_id IS NOT NULL AND club_id IS NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_team_per_club_name ON team (club_id, name) WHERE type = 'club';
CREATE UNIQUE INDEX IF NOT EXISTS uniq_team_per_country_bucket ON team (national_country_id, COALESCE(age_group,''), COALESCE(gender,'')) WHERE type = 'national';
CREATE INDEX IF NOT EXISTS idx_team_club_id ON team(club_id);
CREATE INDEX IF NOT EXISTS idx_team_national_country_id ON team(national_country_id);
CREATE INDEX IF NOT EXISTS idx_team_type ON team(type);

CREATE TABLE IF NOT EXISTS season (
  season_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  competition_id  BIGINT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  start_date      DATE,
  end_date        DATE,
  UNIQUE (competition_id, name)
);

CREATE INDEX IF NOT EXISTS idx_season_competition_id ON season(competition_id);

CREATE TABLE competition_season_summary (
    id SERIAL PRIMARY KEY,
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    season_id INT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
    summary TEXT,
    --future expansions,
    --winner_team_id INT REFERENCES teams(id),
    --runner_up_team_id INT REFERENCES teams(id),
    --third_place_team_id INT REFERENCES teams(id),
    --top_scorer_player_id INT REFERENCES players(id),
    UNIQUE (competition_id, season_id)
);


-- ===========================================
-- Stage: phases within a season
-- ===========================================
CREATE TABLE IF NOT EXISTS stage (
  stage_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season_id    BIGINT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
  name         TEXT   NOT NULL,          -- "Regular Season", "Group Stage", "Knockout Phase"
  stage_order  SMALLINT NOT NULL,        -- 1,2,3... chronological order inside the season
  format       TEXT   NOT NULL,          -- 'league' | 'groups' | 'knockout' | 'qualification' | 'playoffs'
  CONSTRAINT chk_stage_format
    CHECK (format IN ('league','groups','knockout','qualification','playoffs')),
  CONSTRAINT uq_stage_name_per_season
    UNIQUE (season_id, name),
  CONSTRAINT uq_stage_order_per_season
    UNIQUE (season_id, stage_order)
);

CREATE INDEX IF NOT EXISTS idx_stage_season_id ON stage(season_id);
CREATE INDEX IF NOT EXISTS idx_stage_season_order ON stage(season_id, stage_order);
CREATE INDEX IF NOT EXISTS idx_stage_season_name ON stage(season_id, name);

-- ===========================================
-- Stage groups: only used when stage.format='groups'
-- ===========================================
CREATE TABLE IF NOT EXISTS stage_group (
  group_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  stage_id   BIGINT NOT NULL REFERENCES stage(stage_id) ON DELETE CASCADE,
  name       TEXT   NOT NULL,     -- "Group A", "Group B" ...
  code       TEXT,                 -- optional short code: 'A','B','C'...
  CONSTRAINT uq_stage_group_name UNIQUE (stage_id, name),
  CONSTRAINT uq_stage_group_code UNIQUE (stage_id, code)
);

CREATE INDEX IF NOT EXISTS idx_stage_group_stage_id ON stage_group(stage_id);

CREATE TABLE IF NOT EXISTS stage_group_team (
  stage_group_team_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  group_id            BIGINT NOT NULL REFERENCES stage_group(group_id) ON DELETE CASCADE,
  team_id             BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  UNIQUE (group_id, team_id)
);
CREATE INDEX IF NOT EXISTS idx_sgt_group ON stage_group_team(group_id);
CREATE INDEX IF NOT EXISTS idx_sgt_team ON stage_group_team(team_id);

-- ===========================================
-- Stage rounds: matchdays or knockout rounds inside a stage
-- ===========================================
CREATE TABLE IF NOT EXISTS stage_round (
  stage_round_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  stage_id           BIGINT NOT NULL REFERENCES stage(stage_id) ON DELETE CASCADE,
  name               TEXT   NOT NULL,     -- "Matchday 1", "Round of 16", "Final"
  stage_round_order  SMALLINT NOT NULL,   -- 1..N within the stage
  two_legs           BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_stage_round_name   UNIQUE (stage_id, name),
  CONSTRAINT uq_stage_round_order  UNIQUE (stage_id, stage_round_order)
);

CREATE INDEX IF NOT EXISTS idx_stage_round_stage_id ON stage_round(stage_id);
CREATE INDEX IF NOT EXISTS idx_stage_round_stage_order ON stage_round(stage_id, stage_round_order);

-- Official final table snapshot, one row per team per season.
CREATE TABLE IF NOT EXISTS league_table_snapshot (
  season_id     BIGINT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
  team_id       BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  position      INTEGER NOT NULL,
  played        INTEGER NOT NULL,
  wins          INTEGER NOT NULL,
  draws         INTEGER NOT NULL,
  losses        INTEGER NOT NULL,
  goals_for     INTEGER NOT NULL,
  goals_against INTEGER NOT NULL,
  goal_diff     INTEGER NOT NULL,
  points        INTEGER NOT NULL,
  notes         TEXT, -- e.g., "−3 pts (financial)", "Matchday 22 abandoned, 3–0 awarded"
  PRIMARY KEY (season_id, team_id)
);

-- Per-season adjustments (deductions/bonuses), summed into computed standings.
CREATE TABLE IF NOT EXISTS league_points_adjustment (
  adjustment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season_id     BIGINT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
  team_id       BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  points_delta  INTEGER NOT NULL,  -- negative for deductions
  reason        TEXT NOT NULL,     -- required: we want to display it
  applied_on    DATE DEFAULT CURRENT_DATE
);

-- Season points rules (defaults to 3-1-0 if absent).
CREATE TABLE IF NOT EXISTS season_points_rule (
  season_id   BIGINT PRIMARY KEY REFERENCES season(season_id) ON DELETE CASCADE,
  win_points  SMALLINT NOT NULL DEFAULT 3,
  draw_points SMALLINT NOT NULL DEFAULT 1,
  loss_points SMALLINT NOT NULL DEFAULT 0
);

-- Official group table snapshot. One row per team per group.
CREATE TABLE IF NOT EXISTS group_table_snapshot (
  group_id      BIGINT NOT NULL REFERENCES stage_group(group_id) ON DELETE CASCADE,
  team_id       BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  position      INTEGER NOT NULL,
  played        INTEGER NOT NULL,
  wins          INTEGER NOT NULL,
  draws         INTEGER NOT NULL,
  losses        INTEGER NOT NULL,
  goals_for     INTEGER NOT NULL,
  goals_against INTEGER NOT NULL,
  goal_diff     INTEGER NOT NULL,
  points        INTEGER NOT NULL,
  notes         TEXT,
  PRIMARY KEY (group_id, team_id)
);

-- Per-team points deltas within a group (deductions/bonuses).
CREATE TABLE IF NOT EXISTS group_points_adjustment (
  adjustment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  group_id      BIGINT NOT NULL REFERENCES stage_group(group_id) ON DELETE CASCADE,
  team_id       BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  points_delta  INTEGER NOT NULL,  -- negative for deductions
  reason        TEXT NOT NULL,
  applied_on    DATE DEFAULT CURRENT_DATE
);

CREATE INDEX IF NOT EXISTS idx_gpa_group ON group_points_adjustment(group_id);
CREATE INDEX IF NOT EXISTS idx_gts_group ON group_table_snapshot(group_id);

CREATE TABLE IF NOT EXISTS fixture (
  fixture_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  stage_round_id    BIGINT NOT NULL REFERENCES stage_round(stage_round_id) ON DELETE CASCADE,
  group_id          BIGINT REFERENCES stage_group(group_id) ON DELETE SET NULL,

  home_team_id      BIGINT NOT NULL REFERENCES team(team_id) ON DELETE RESTRICT,
  away_team_id      BIGINT NOT NULL REFERENCES team(team_id) ON DELETE RESTRICT,
  CONSTRAINT fixture_teams_different CHECK (home_team_id <> away_team_id),

  kickoff_utc       TIMESTAMPTZ NOT NULL,
  stadium_id        BIGINT REFERENCES stadium(stadium_id) ON DELETE SET NULL,
  attendance        INTEGER,

  fixture_status    TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled|live|played|postponed|canceled

  ht_home_score     SMALLINT,
  ht_away_score     SMALLINT,
  ft_home_score     SMALLINT,
  ft_away_score     SMALLINT,
  et_home_score     SMALLINT,
  et_away_score     SMALLINT,
  pen_home_score    SMALLINT,
  pen_away_score    SMALLINT,

  went_to_extra_time  BOOLEAN NOT NULL DEFAULT FALSE,
  went_to_penalties   BOOLEAN NOT NULL DEFAULT FALSE,

  home_score        SMALLINT DEFAULT 0,
  away_score        SMALLINT DEFAULT 0,

  winner_team_id    BIGINT REFERENCES team(team_id) ON DELETE SET NULL,
  optional_second_leg BOOLEAN NOT NULL DEFAULT FALSE
);

-- Basic indexes
CREATE INDEX IF NOT EXISTS ix_fixture_stage_round ON fixture(stage_round_id);
CREATE INDEX IF NOT EXISTS idx_fixture_group_id ON fixture(group_id);
CREATE INDEX IF NOT EXISTS ix_fixture_kickoff ON fixture(kickoff_utc);
CREATE INDEX IF NOT EXISTS ix_fixture_teams ON fixture(home_team_id, away_team_id);
CREATE INDEX IF NOT EXISTS idx_fixture_stadium_id ON fixture(stadium_id);
CREATE INDEX IF NOT EXISTS idx_fixture_home_team_id ON fixture(home_team_id);
CREATE INDEX IF NOT EXISTS idx_fixture_away_team_id ON fixture(away_team_id);
CREATE INDEX IF NOT EXISTS idx_fixture_winner_team_id ON fixture(winner_team_id);

CREATE TABLE IF NOT EXISTS person (
  person_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  first_name         TEXT,
  last_name          TEXT,
  full_name          TEXT,
  known_as           TEXT,
  birth_date         DATE,
  birth_place        TEXT,
  country_id         BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  second_country_id  BIGINT REFERENCES country(country_id) ON DELETE SET NULL,
  gender             TEXT,
  height_cm          SMALLINT,
  weight_kg          SMALLINT,
  photo_url          TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_person_name_dob ON person (lower(full_name), birth_date) WHERE full_name IS NOT NULL AND birth_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_person_country ON person(country_id);

CREATE TABLE IF NOT EXISTS player (
  player_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  person_id   BIGINT NOT NULL UNIQUE REFERENCES person(person_id) ON DELETE CASCADE,
  player_position    TEXT,
  player_active      BOOLEAN DEFAULT TRUE,
  CONSTRAINT chk_player_position
    CHECK (player_position IS NULL OR player_position IN ('GK','DF','MF','FW'))
);

CREATE TABLE IF NOT EXISTS coach (
  coach_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  person_id     BIGINT NOT NULL UNIQUE REFERENCES person(person_id) ON DELETE CASCADE,
  role_default  TEXT,                 -- 'head','assistant','gk','fitness',...
  coach_active  BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS official (
  official_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  person_id         BIGINT NOT NULL UNIQUE REFERENCES person(person_id) ON DELETE CASCADE,
  association_id    BIGINT REFERENCES association(ass_id) ON DELETE SET NULL,
  roles             TEXT,             -- e.g. "referee;assistant;VAR"
  official_active   BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_official_association ON official(association_id);

CREATE TABLE IF NOT EXISTS player_registration (
  registration_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  player_id        BIGINT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  team_id          BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  start_date       DATE NOT NULL,
  end_date         DATE,
  shirt_no         SMALLINT,
  on_loan          BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_player_reg_player ON player_registration(player_id);
CREATE INDEX IF NOT EXISTS idx_player_reg_team ON player_registration(team_id);
CREATE INDEX IF NOT EXISTS idx_player_reg_period ON player_registration(start_date, end_date);

CREATE TABLE IF NOT EXISTS staff_assignment (
  assignment_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  person_id      BIGINT NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
  team_id        BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  staff_role     TEXT NOT NULL,          -- 'head coach','assistant','gk coach',...
  start_date     DATE NOT NULL,
  end_date       DATE
);

CREATE INDEX IF NOT EXISTS idx_staff_person ON staff_assignment(person_id);
CREATE INDEX IF NOT EXISTS idx_staff_team ON staff_assignment(team_id);
CREATE INDEX IF NOT EXISTS idx_staff_period ON staff_assignment(start_date, end_date);

CREATE TABLE IF NOT EXISTS season_team (
  season_team_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season_id       BIGINT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
  team_id         BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  seeding         TEXT,
  pot             TEXT,
  invited         BOOLEAN DEFAULT FALSE,
  UNIQUE (season_id, team_id)
);

CREATE TABLE IF NOT EXISTS match_official (
  match_official_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fixture_id        BIGINT NOT NULL REFERENCES fixture(fixture_id) ON DELETE CASCADE,
  person_id         BIGINT NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
  duty              TEXT NOT NULL          -- 'referee','AR1','AR2','4th','VAR','AVAR'
);

CREATE INDEX IF NOT EXISTS idx_match_official_fixture ON match_official(fixture_id);
CREATE INDEX IF NOT EXISTS idx_match_official_person ON match_official(person_id);

CREATE TABLE IF NOT EXISTS lineup (
  lineup_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fixture_id      BIGINT NOT NULL REFERENCES fixture(fixture_id) ON DELETE CASCADE,
  team_id         BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  player_id       BIGINT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  formation       TEXT,
  UNIQUE (fixture_id, team_id)
);

CREATE TABLE IF NOT EXISTS appearance (
  appearance_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fixture_id        BIGINT NOT NULL REFERENCES fixture(fixture_id) ON DELETE CASCADE,
  team_id         BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  player_id       BIGINT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  shirt_number    SMALLINT,
  is_starter      BOOLEAN NOT NULL DEFAULT FALSE,
  minute_on       SMALLINT DEFAULT 0,
  minute_off      SMALLINT,
  captain         BOOLEAN DEFAULT FALSE,
  position        TEXT,
  UNIQUE (fixture_id, player_id)
);
CREATE INDEX IF NOT EXISTS ix_app_fixture_team ON appearance(fixture_id, team_id);
CREATE INDEX IF NOT EXISTS ix_app_fixture_player ON appearance(fixture_id, player_id);

CREATE TABLE IF NOT EXISTS substitution (
  sub_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fixture_id        BIGINT NOT NULL REFERENCES fixture(fixture_id) ON DELETE CASCADE,
  team_id         BIGINT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
  minute          SMALLINT NOT NULL,
  player_off_id   BIGINT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
  player_on_id    BIGINT NOT NULL REFERENCES player(player_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_sub_fixture ON substitution(fixture_id);

CREATE TABLE IF NOT EXISTS match_event (
  match_event_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fixture_id        BIGINT NOT NULL REFERENCES fixture(fixture_id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS ix_match_event_fixture ON match_event(fixture_id);
CREATE INDEX IF NOT EXISTS ix_match_event_fixture_player ON match_event(fixture_id, player_id);
CREATE INDEX IF NOT EXISTS ix_match_event_type ON match_event(type);

CREATE TABLE IF NOT EXISTS team_fixture_stats (
  fixture_id        BIGINT NOT NULL REFERENCES fixture(fixture_id) ON DELETE CASCADE,
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
  PRIMARY KEY (fixture_id, team_id)
);

CREATE TABLE IF NOT EXISTS player_fixture_stats (
  fixture_id        BIGINT NOT NULL REFERENCES fixture(fixture_id) ON DELETE CASCADE,
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
  PRIMARY KEY (fixture_id, player_id)
);

CREATE TABLE IF NOT EXISTS table_standings (
  standing_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  season_id       BIGINT NOT NULL REFERENCES season(season_id) ON DELETE CASCADE,
  stage_id        BIGINT REFERENCES stage(stage_id) ON DELETE SET NULL,
  group_id        BIGINT REFERENCES stage_group(group_id) ON DELETE SET NULL,
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
  UNIQUE (season_id, stage_id, group_id, team_id)
);

-- ======================================================
-- Added indexes and constraints
-- ======================================================

-- Countries / People / Clubs / Stadiums

-- Teams & Entries

CREATE INDEX IF NOT EXISTS idx_season_team_season_id ON season_team(season_id);
CREATE INDEX IF NOT EXISTS idx_season_team_team_id ON season_team(team_id);


-- Lineups / Appearances / Subs / Match events
CREATE INDEX IF NOT EXISTS idx_lineup_fixture_id ON lineup(fixture_id);
CREATE INDEX IF NOT EXISTS idx_lineup_team_id ON lineup(team_id);
CREATE INDEX IF NOT EXISTS idx_lineup_player_id ON lineup(player_id);

CREATE INDEX IF NOT EXISTS idx_appearance_fixture_id ON appearance(fixture_id);
CREATE INDEX IF NOT EXISTS idx_appearance_player_id ON appearance(player_id);
CREATE INDEX IF NOT EXISTS idx_appearance_team_id ON appearance(team_id);

CREATE INDEX IF NOT EXISTS idx_substitution_fixture_id ON substitution(fixture_id);
CREATE INDEX IF NOT EXISTS idx_substitution_team_id ON substitution(team_id);
CREATE INDEX IF NOT EXISTS idx_substitution_player_on_id ON substitution(player_on_id);
CREATE INDEX IF NOT EXISTS idx_substitution_player_off_id ON substitution(player_off_id);

CREATE INDEX IF NOT EXISTS idx_match_event_fixture_id ON match_event(fixture_id);
CREATE INDEX IF NOT EXISTS idx_match_event_team_id ON match_event(team_id);
CREATE INDEX IF NOT EXISTS idx_match_event_player_id ON match_event(player_id);

-- Stats / Standings
CREATE INDEX IF NOT EXISTS idx_team_fixture_stats_fixture_id ON team_fixture_stats(fixture_id);
CREATE INDEX IF NOT EXISTS idx_team_fixture_stats_team_id ON team_fixture_stats(team_id);

CREATE INDEX IF NOT EXISTS idx_player_fixture_stats_fixture_id ON player_fixture_stats(fixture_id);
CREATE INDEX IF NOT EXISTS idx_player_fixture_stats_player_id ON player_fixture_stats(player_id);

CREATE INDEX IF NOT EXISTS idx_table_standings_scope ON table_standings(season_id, stage_id, group_id, team_id);



CREATE UNIQUE INDEX IF NOT EXISTS uniq_team_per_club
  ON team(club_id)
  WHERE type = 'club';

-- ===============================================
-- Extra helpful indexes on foreign key fixture_id
-- ===============================================
CREATE INDEX IF NOT EXISTS idx_lineup_fixture_id ON lineup(fixture_id);
CREATE INDEX IF NOT EXISTS idx_appearance_fixture_id ON appearance(fixture_id);
CREATE INDEX IF NOT EXISTS idx_substitution_fixture_id ON substitution(fixture_id);
CREATE INDEX IF NOT EXISTS idx_match_event_fixture_id ON match_event(fixture_id);
--CREATE INDEX IF NOT EXISTS idx_team_match_stats_fixture_id       ON team_match_stats(fixture_id);
--CREATE INDEX IF NOT EXISTS idx_player_match_stats_fixture_id     ON player_match_stats(fixture_id);

INSERT INTO association (code, name, founded_year, level, logo_filename) VALUES ('FIFA','Fédération Internationale de Football Association',1904,'federation','fifa.png');