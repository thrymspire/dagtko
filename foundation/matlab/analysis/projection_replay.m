function ok = projection_replay(events)
    % Conceptual replay probe; real reducer is SQL-side
    ok = true;
    fprintf('Replay probe over %d events\n', numel(events));
end
