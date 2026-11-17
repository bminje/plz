// NOT EXECUTED by the author. See neo4j/README.md for the expected values.

// Q1. Stop served by the most routes
MATCH (s:Stop)<-[:PASSES]-(r:Route)
RETURN s.sid AS sid, s.name AS name, count(r) AS n_routes ORDER BY n_routes DESC LIMIT 1;

// Q2. Number of stops served by 10 or more routes
MATCH (s:Stop)<-[:PASSES]-(r:Route)
WITH s, count(r) AS n WHERE n >= 10
RETURN count(s) AS large_hubs;

// Q6a. Stops reachable by one ride from the stops within 300 m of the HUFS campus point
//      (:param src => list of sids, see neo4j/hufs_stops.json)
MATCH (a:Stop) WHERE a.sid IN $src
OPTIONAL MATCH (a)<-[:PASSES]-(:Route)-[:PASSES]->(b:Stop)
WITH $src + collect(DISTINCT b.sid) AS ids
UNWIND ids AS x RETURN count(DISTINCT x) AS one_ride;

// Q6b. ... reachable with at most one transfer
MATCH (a:Stop) WHERE a.sid IN $src
OPTIONAL MATCH (a)<-[:PASSES]-(:Route)-[:PASSES]->(b:Stop)
OPTIONAL MATCH (b)<-[:PASSES]-(:Route)-[:PASSES]->(c:Stop)
WITH $src + collect(DISTINCT b.sid) + collect(DISTINCT c.sid) AS ids
UNWIND ids AS x RETURN count(DISTINCT x) AS up_to_one_transfer;
