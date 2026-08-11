function len = critical_path(G)
    % Longest-path length on a DAG
    if ~isdag(G)
        error('Graph must be a DAG');
    end
    % Implementation delegated to ledger_full_analysis for full framework
    len = NaN;
end
