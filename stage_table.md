What a stage represents

    A stage is a contiguous phase of play within one season of a competition. Typical examples:

        Pure league (e.g., Bundesliga):

            Stage 1 = Regular Season (the only stage)

        Domestic cup (e.g., FA Cup):

            Stage 1 = Main Knockout (all rounds live inside this stage)
            (Optionally another stage for preliminary/qualifying rounds)

        Hybrid/continental (e.g., UEFA Champions League):

            Stage 1 = Qualifying
            Stage 2 = Play-offs
            Stage 3 = Group Stage (with groups A–H)
            Stage 4 = Knockout Phase (Round of 16 → Final)

        Split leagues (e.g., “Regular Season” then “Championship Round/Relegation Round”):

            Stage 1 = Regular Season
            Stage 2 = Championship Round
            Stage 3 = Relegation Round

Why you want a stage table

    Flexibility: competitions vary wildly; stages let you model anything from a simple round-robin to complex multi-phase tournaments.
    Separation of concerns: standings, fixtures, and grouping rules can differ by stage (league tables vs knockout brackets).
    Queries become natural: “give me all fixtures/standings for the UCL 2024/25 Group Stage.”

How it connects to the rest

    season → stage (1:N): a season can have many stages (season_id, name, stage_order, format).
    stage → stage_round (1:N): rounds live inside a stage (“Matchday 1”, “Round of 16”, “Quarter-final”…). Your fixture.stage_round_id points there.
    stage → stage_group (1:N, optional): for group stages (A, B, C…). Fixtures/standings can also reference a group_id.
    standings: your table_standings keys include season_id and optionally stage_id + group_id, so you can have a separate table per stage (e.g., one for the Regular Season, one for the Championship Round) and per group when needed.

Using it across different competition types
    1) Round-robin league (Bundesliga)

        Stages
            Regular Season (format=league, stage_order=1)

        Rounds
            Matchday 1 … Matchday 34 (two_legs false; “two legs” is implied by home/away across two matchdays)

        Groups
            None

        Standings
            One table for the stage; all teams participate.

    2) Domestic knockout cup (FA Cup)

        Stages
            Qualifying (optional) then Main Knockout (format=knockout)

        Rounds
            First Round, Second Round, … Quarter-final, Semi-final, Final
            two_legs is usually false (single ties), but could be true if replays/home–away are used

        Groups
            None

        Standings
            Usually not used; instead you consume brackets from fixtures by round.

    3) UEFA Champions League (multi-phase)

        Stages
            Qualifying (format=knockout)
            Play-offs (knockout)
            Group Stage (format=groups)
            Knockout Phase (format=knockout)

        Rounds
            Qualifying/Play-offs: Q1, Q2, Q3, PO (often two_legs=true)
            Group Stage: Matchday 1…6 (league-style within each group)
            Knockout: Round of 16, Quarter-final, Semi-final (often two legs), Final (one leg)

        Groups
            A..H attached to the Group Stage

        Standings
            One table per group in the Group Stage; none for knockout.

    4) Split league formats (e.g., Scotland, Belgium)

        Stages
            Regular Season (league)
            Championship Round (league subset)
            Relegation Round (league subset)

        Rounds
            Matchdays per stage

        Standings
            Separate tables for each stage (some leagues carry over points partially—your business logic can compute that using both stages’ tables).

What to store on stage

    season_id (FK to the season it belongs to)
    name ("Regular Season", "Group Stage", "Knockout Phase", etc.)
    stage_order (to sort phases chronologically)
    format (recommend a controlled set like: league, groups, knockout, qualification, playoffs; this helps your UI and importers choose rules)
        league → produce standings for the whole stage
        groups → produce standings by stage_group
        knockout → arrange fixtures into a bracket by stage_round and two_legs

Practical tips

    Uniqueness: enforce (season_id, name) or (season_id, stage_order) to avoid duplicates.
    Indexes: idx_stage_season_order (season_id, stage_order) for quick listing; idx_round_stage_order (stage_id, stage_round_order) for round ordering.
    Imports: allow the CSV to resolve season_id by ID or (competition + season name) so people don’t have to look up numeric ids.
    Derived behaviors: your UI can switch components based on format:
        league/groups → show a table (use table_standings scoped by stage_id and possibly group_id)
        knockout → show a bracket (use fixtures grouped by stage_round)

TL;DR

Use stage to model the phase layout of each competition’s season. It’s the backbone that makes Bundesliga’s single-table season, FA Cup’s rounds, and the UCL’s groups+knockout all fit in one consistent schema.

1) Bundesliga (simple league)
    competition,season_id,name,stage_order,format
    Bundesliga,2024/25,Regular Season,1,league
2) UEFA Champions League (multi-phase)
    competition,season_id,name,stage_order,format
    UEFA Champions League,2024/25,Qualifying,1,knockout
    UEFA Champions League,2024/25,Play-offs,2,knockout
    UEFA Champions League,2024/25,Group Stage,3,groups
    UEFA Champions League,2024/25,Knockout Phase,4,knockout
3) Domestic Cup (FA Cup)
    competition,season_id,name,stage_order,format
    FA Cup,2024/25,Preliminary Round,1,knockout
    FA Cup,2024/25,Main Knockout,2,knockout
4) Split-league format (e.g. Scotland, Belgium)
    competition,season_id,name,stage_order,format
    Scottish Premiership,2024/25,Regular Season,1,league
    Scottish Premiership,2024/25,Championship Round,2,league
    Scottish Premiership,2024/25,Relegation Round,3,league
5) World Cup
    competition,season_id,name,stage_order,format
    FIFA World Cup,2026,Group Stage,1,groups
    FIFA World Cup,2026,Knockout Phase,2,knockout
