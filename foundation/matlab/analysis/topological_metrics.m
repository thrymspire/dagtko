function topological_metrics(G)
    % See ledger_full_analysis.m
    if isdag(G)
        disp('DAG: yes');
    else
        disp('DAG: no');
    end
end
