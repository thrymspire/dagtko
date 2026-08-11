% %% DAG Substrate — Turnkey Closed-Loop + Graph View (MATLAB)
% Analytics-only. Reads live Projection + supporting tables and draws the DAG.
% Prerequisite: ./scripts/up.sh has completed successfully.
%
% After this script runs, these variables remain in the workspace:
%   conn, wo, nodes, edges, events, buckets, frags, G
% Connection is left OPEN so you can keep querying.

clear; clc; close all;

%% ------------------------------------------------------------------------
% 1. Connection
% -------------------------------------------------------------------------
host     = '127.0.0.1';
port     = 5432;
dbname   = 'dag_substrate';
username = 'dag';
password = 'dag_substrate';

% Load PostgreSQL JDBC jar if available
scriptDir = fileparts(mfilename('fullpath'));
jarPath   = fullfile(scriptDir, 'postgresql-42.7.3.jar');
if exist(jarPath, 'file')
    javaaddpath(jarPath);
end

conn = [];
portsToTry = [5432, 5433];
connectedPort = port;

for p = portsToTry
    % Method 1: Modern MATLAB postgresql interface (with Port specified)
    try
        conn = postgresql(host, dbname, username, password, 'Port', p);
        if ~isempty(conn) && isopen(conn)
            connectedPort = p;
            break;
        end
    catch
    end

    % Method 2: Database Toolbox Vendor syntax
    try
        conn = database(dbname, username, password, ...
            'Vendor', 'PostgreSQL', ...
            'Server', host, ...
            'PortNumber', p);
        if ~isempty(conn) && isopen(conn)
            connectedPort = p;
            break;
        end
    catch
    end

    % Method 3: Direct JDBC Driver URL
    try
        jdbcUrl = sprintf('jdbc:postgresql://%s:%d/%s', host, p, dbname);
        conn = database(dbname, username, password, ...
            'org.postgresql.Driver', jdbcUrl);
        if ~isempty(conn) && isopen(conn)
            connectedPort = p;
            break;
        end
    catch
    end
end

if isempty(conn) || ~isopen(conn)
    errMsg = 'Could not connect to Postgres.';
    if ~isempty(conn) && isfield(conn, 'Message') && ~isempty(conn.Message)
        errMsg = sprintf('%s\nDatabase message: %s', errMsg, conn.Message);
    end
    error('DAG:ConnectionFailed', ...
          '%s\nIs the turnkey stack running? (./scripts/up.sh)', ...
          errMsg);
end

fprintf('Connected to %s@%s:%d/%s\n\n', username, host, connectedPort, dbname);

%% ------------------------------------------------------------------------
% 2. Closed-loop proof counts
% -------------------------------------------------------------------------
sqlCounts = [
    "SELECT 'nodes_WorkOrder' AS metric, count(*)::int AS n FROM nodes WHERE node_type = 'WorkOrder'"
    "UNION ALL SELECT 'edges_Creates', count(*)::int FROM edges WHERE edge_type = 'Creates'"
    "UNION ALL SELECT 'events_WorkOrderCreated', count(*)::int FROM events WHERE event_type = 'WorkOrderCreated'"
    "UNION ALL SELECT 'wo_current_state', count(*)::int FROM wo_current_state"
    "UNION ALL SELECT 'buckets', count(*)::int FROM buckets"
    "UNION ALL SELECT 'fragments', count(*)::int FROM fragments"
];

counts = fetch(conn, join(sqlCounts, " "));
fprintf('========== CLOSED-LOOP PROOF ==========\n');
disp(counts);

metricCol = string(counts.metric);
nWO   = counts.n(metricCol == "nodes_WorkOrder");
nEdge = counts.n(metricCol == "edges_Creates");
nEv   = counts.n(metricCol == "events_WorkOrderCreated");
nProj = counts.n(metricCol == "wo_current_state");

if all([nWO, nEdge, nEv, nProj] >= 1)
    fprintf('\nCLOSED LOOP: GREEN  (Node + Edge + Event + Projection jointly present)\n\n');
else
    fprintf('\nCLOSED LOOP: RED   — investigate seed / init order\n\n');
end

%% ------------------------------------------------------------------------
% 3. Load all tables into workspace (stay open)
% -------------------------------------------------------------------------
wo      = fetch(conn, 'SELECT * FROM wo_current_state ORDER BY updated_at DESC');
nodes   = fetch(conn, 'SELECT id, node_type, external_ref, props, created_at FROM nodes ORDER BY created_at');
edges   = fetch(conn, 'SELECT id, edge_type, from_node_id, to_node_id, props, correlation_id, occurred_at FROM edges ORDER BY occurred_at');
events  = fetch(conn, 'SELECT id, event_id, event_type, edge_id, node_id, payload, occurred_at FROM events ORDER BY id');
buckets = fetch(conn, 'SELECT bucket_name, version, constraint_body, effective_from FROM buckets ORDER BY bucket_name, version');

try
    frags = fetch(conn, 'SELECT * FROM fragments ORDER BY created_at');
catch
    frags = table();
end

fprintf('========== PROJECTION: wo_current_state ==========\n');
disp(wo);
fprintf('\n========== NODES ==========\n');
disp(nodes);
fprintf('\n========== EDGES ==========\n');
disp(edges);
fprintf('\n========== EVENTS ==========\n');
disp(events);
fprintf('\n========== BUCKETS ==========\n');
disp(buckets);
if ~isempty(frags)
    fprintf('\n========== FRAGMENTS ==========\n');
    disp(frags);
end
fprintf('\n');

%% ------------------------------------------------------------------------
% 4. Build and plot the directed graph
% -------------------------------------------------------------------------
if height(nodes) == 0 || height(edges) == 0
    fprintf('Not enough nodes/edges to draw a graph yet.\n');
    G = digraph();
else
    % Node labels: prefer external_ref, fall back to short id + type
    nodeIds   = string(nodes.id);
    nodeLabel = strings(height(nodes), 1);
    for i = 1:height(nodes)
        ref = string(nodes.external_ref(i));
        typ = string(nodes.node_type(i));
        if strlength(ref) > 0 && ref ~= "missing" && ref ~= ""
            nodeLabel(i) = typ + newline + ref;
        else
            nodeLabel(i) = typ + newline + extractBefore(nodeIds(i), 9);
        end
    end

    % Edge endpoints as strings matching node ids
    s = string(edges.from_node_id);
    t = string(edges.to_node_id);
    edgeType = string(edges.edge_type);

    % digraph with explicit node list so isolated nodes still appear
    % Note: 3rd arg in digraph(s,t,w,names) is numeric weight; use [] for unweighted
    G = digraph(s, t, [], nodeIds);
    G.Edges.Type = edgeType;

    % Map labels onto the graph node order
    [~, loc] = ismember(G.Nodes.Name, nodeIds);
    G.Nodes.Label = nodeLabel(loc);
    G.Nodes.Type  = string(nodes.node_type(loc));

    % --- Figure: full DAG ---
    figure('Name', 'DAG Substrate — Live Graph', 'Color', 'w', ...
           'Position', [100 100 900 650]);

    h = plot(G, 'Layout', 'layered', ...
        'NodeLabel', G.Nodes.Label, ...
        'EdgeLabel', G.Edges.Type, ...
        'ArrowSize', 12, ...
        'MarkerSize', 10, ...
        'LineWidth', 1.5, ...
        'NodeFontSize', 9, ...
        'EdgeFontSize', 8, ...
        'NodeColor', [0.45 0.30 0.80], ...
        'EdgeColor', [0.25 0.75 0.75]);

    title({'DAG Substrate — Turnkey Live Graph'; ...
           'Node · Edge (Projection is current truth)'}, ...
           'FontSize', 13, 'FontWeight', 'bold');
    subtitle('MATLAB analytics view — read-only');

    % Color nodes by type
    types = unique(G.Nodes.Type);
    cmap  = lines(max(numel(types), 1));
    for k = 1:numel(types)
        idx = find(G.Nodes.Type == types(k));
        highlight(h, idx, 'NodeColor', cmap(k, :));
    end

    % Summary in command window
    fprintf('========== GRAPH SUMMARY ==========\n');
    fprintf('Nodes: %d   Edges: %d\n', numnodes(G), numedges(G));
    if numedges(G) > 0
        fprintf('\nDirected edges:\n');
        for e = 1:numedges(G)
            fprintf('  %s  --(%s)-->  %s\n', ...
                G.Edges.EndNodes{e,1}, ...
                string(G.Edges.Type(e)), ...
                G.Edges.EndNodes{e,2});
        end
    end
    fprintf('\n');
end

%% ------------------------------------------------------------------------
% 5. Optional critical-path length on first WorkOrder
% -------------------------------------------------------------------------
if height(wo) >= 1
    rootId = string(wo.work_order_id(1));
    try
        cp = fetch(conn, sprintf( ...
            "SELECT compute_critical_path_len('%s'::uuid) AS critical_path_len", rootId));
        fprintf('========== CRITICAL-PATH (derived) ==========\n');
        fprintf('Root WorkOrder: %s\n', rootId);
        disp(cp);
        fprintf('\n');
    catch ME
        fprintf('Critical-path call skipped: %s\n\n', ME.message);
    end
end

%% ------------------------------------------------------------------------
% 6. Leave everything open for interactive use
% -------------------------------------------------------------------------
fprintf('============================================================\n');
fprintf('  TURNKEY PRESENTATION COMPLETE — CONNECTION LEFT OPEN\n');
fprintf('  Workspace variables: conn, wo, nodes, edges, events,\n');
fprintf('                       buckets, frags, G, counts\n');
fprintf('  Graph figure is open. Use openvar wo  (or any table)\n');
fprintf('  to inspect in the Variable Editor.\n');
fprintf('  API: http://localhost:8008   MCP: http://localhost:8001\n');
fprintf('============================================================\n');
fprintf('\nWhen finished:  close(conn)\n');

% Do NOT close(conn) — left open on purpose.
% Do NOT clear variables — left for interactive inspection.
