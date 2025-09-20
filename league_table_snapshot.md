1)Points Adjustment CSV (deductions, bonuses, fines)

    Create a CSV specifically for team adjustments:
    league_points_adjustment.csv

    season_id,team_id,points_delta,reason
    42,15,-3,"Disciplinary sanction: crowd trouble (Oct 2024)"


    season_id=42 → the season_id you got when importing the season.
    team_id=15 → the team id for AEK Athens in your team table.
    points_delta=-3 → deduction.
    reason → free text shown in Notes.

    When you import this file, it inserts into:

    INSERT INTO league_points_adjustment (season_id, team_id, points_delta, reason)
    VALUES (42, 15, -3, 'Disciplinary sanction: crowd trouble (Oct 2024)');

2) With snapshot (you import the official final table)

    You insert one row per team into league_table_snapshot with the federation’s published numbers, e.g.:

    season_id,team_id,position,played,wins,draws,losses,goals_for,goals_against,goal_diff,points,notes
    42,11,1,36,23,7,6,65,30,35,76,""
    42,15,2,36,21,10,5,60,28,32,70,"Includes -3 pts (disciplinary)"
    42,18,3,36,20,9,7,58,33,25,69,""
    42,20,4,36,18,11,7,55,31,24,65,""

## When to use which

    - Only deductions/bonuses and your fixtures reflect the real match outcomes → Adjustments only (A) is enough.
    - Awarded games, voided matches, federation quirks, or you want an immutable historical record → add a Snapshot (B).
    - You can also do both: keep adjustments for as-you-go accuracy during the season, then load a final snapshot once the federation publishes the official table.