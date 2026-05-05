-- All-time Cascadiens roster (by primary team)
SELECT 
    p.first_name,
    p.last_name,
    p.team_name,
    COUNT(DISTINCT p.season_id) as seasons_played,
    SUM(ps.gp) as total_games,
    SUM(ps.points) as total_points
FROM players p
LEFT JOIN player_stats ps ON p.id = ps.player_id AND p.season_id = ps.season_id
WHERE p.team_name = 'Cascadiens' -- and p.division_level = 'D'
GROUP BY p.id
ORDER BY total_games DESC;