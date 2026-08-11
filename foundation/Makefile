.PHONY: up up-native down down-native build logs seed-check test approval wipe visualize web octave cli

# Primary turnkey entry point (Docker)
up:
	./scripts/up.sh

# Native turnkey entry point (Zero-container, lightweight for Pixel 10 Pro XL / Weston)
up-native:
	./scripts/up_native.sh

down-native:
	./scripts/down_native.sh

build:
	docker compose build

down:
	docker compose down

wipe:
	docker compose down -v

logs:
	docker compose logs -f --tail=100

seed-check:
	docker compose exec -T postgres psql -U dag -d dag_substrate -c "\
	SELECT 'nodes' AS t, count(*) FROM nodes \
	UNION ALL SELECT 'edges', count(*) FROM edges \
	UNION ALL SELECT 'events', count(*) FROM events \
	UNION ALL SELECT 'wo_current_state', count(*) FROM wo_current_state \
	UNION ALL SELECT 'buckets', count(*) FROM buckets \
	UNION ALL SELECT 'fragments', count(*) FROM fragments;"

approval:
	docker compose --profile approval up -d

# Visualizer targets
visualize:
	python3 visualizer/dag_visualizer.py

web:
	python3 visualizer/dag_web_live.py

octave:
	octave --no-gui matlab/octave_visualizer.m

cli:
	python3 visualizer/dag_cli.py

# Host-side tests (requires stack already up)
test:
	cd tests && pip install --break-system-packages -q pytest httpx psycopg2-binary redis && pytest -v test_closed_loop.py

