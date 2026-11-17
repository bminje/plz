// NOT EXECUTED by the author. Copy neo4j/*.csv into Neo4j's import directory first.
CREATE CONSTRAINT stop_sid IF NOT EXISTS FOR (s:Stop) REQUIRE s.sid IS UNIQUE;
CREATE CONSTRAINT route_no IF NOT EXISTS FOR (r:Route) REQUIRE r.route IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///stops.csv' AS row
MERGE (s:Stop {sid: row.sid})
SET s.name = row.name, s.lat = toFloat(row.lat), s.lon = toFloat(row.lon), s.n_routes = toInteger(row.n_routes);

LOAD CSV WITH HEADERS FROM 'file:///routes.csv' AS row
MERGE (r:Route {route: row.route})
SET r.mode = row.mode, r.n_stops = toInteger(row.n_stops), r.peak_share = toFloat(row.peak_share);

LOAD CSV WITH HEADERS FROM 'file:///passes.csv' AS row
MATCH (r:Route {route: row.route}), (s:Stop {sid: row.sid})
MERGE (r)-[:PASSES]->(s);
