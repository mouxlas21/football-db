stage_id,name,stage_round_order,two_legs
1,Matchday 1,1,false
1,Matchday 2,2,false
1,Matchday 3,3,false
...
1,Matchday 34,34,false


Stage rounds per stage
    Qualifying (knockout, usually two legs)
        stage_id,name,stage_round_order,two_legs
        10,First Qualifying Round,1,true
        10,Second Qualifying Round,2,true
        10,Third Qualifying Round,3,true
    Play-offs (knockout, two legs)
        stage_id,name,stage_round_order,two_legs
        11,Play-offs,1,true
    Group Stage (groups format, 6 matchdays)
        stage_id,name,stage_round_order,two_legs
        12,Matchday 1,1,false
        12,Matchday 2,2,false
        12,Matchday 3,3,false
        12,Matchday 4,4,false
        12,Matchday 5,5,false
        12,Matchday 6,6,false
    Knockout Phase (two legs until the final)
        stage_id,name,stage_round_order,two_legs
        13,Round of 16,1,true
        13,Quarter-final,2,true
        13,Semi-final,3,true
        13,Final,4,false
