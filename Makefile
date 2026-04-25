.PHONY: setup build test agent tournament bench dev

setup:
	pip install -r requirements.txt
	cd frontend && npm install
	@echo "Note: install Stockfish separately for benchmarking:"
	@echo "  Mac:   brew install stockfish"
	@echo "  Linux: apt install stockfish"

build:
	cd core && cargo build --release

test:
	pytest tests/ -v

agent:
	python3 agent/tester.py

tournament:
	python3 -c "\
from backend.tournament_runner import run_tournament; \
from pathlib import Path; \
base = Path('eval/personalities'); \
r = run_tournament({'Tal': str(base/'tal.py'), 'Karpov': str(base/'karpov.py'), 'Petrosian': str(base/'petrosian.py'), 'Classic': 'eval/classic.py'}, games_per_pair=10); \
print(f'\nSession: {r[\"session_id\"]}'); \
print(f'{\"Engine\":<12} {\"W\":>4} {\"D\":>4} {\"L\":>4} {\"Pts\":>6}'); \
print('-' * 34); \
rows = sorted(r['standings'].items(), key=lambda x: x[1]['W']*2 + x[1]['D'], reverse=True); \
[print(f'{n:<12} {s[\"W\"]:>4} {s[\"D\"]:>4} {s[\"L\"]:>4} {s[\"W\"]*2+s[\"D\"]:>6}') for n, s in rows]; \
print(f'\nResults saved to tournament/results/{r[\"session_id\"]}.json')"

bench:
	@which stockfish > /dev/null 2>&1 || (echo "ERROR: stockfish not found. Run: brew install stockfish  (Mac) or  apt install stockfish  (Linux)" && exit 1)
	python3 tournament/bench_stockfish.py --skill 5 --games 10

dev:
	set -a && source .env && set +a && python3 -m uvicorn backend.main:app --reload --port 8000 &
	cd frontend && npm run dev
