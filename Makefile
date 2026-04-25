.PHONY: setup build test tournament bench dev

setup:
	pip install -r requirements.txt
	cd frontend && npm install

build:
	cd core && cargo build --release

test:
	pytest tests/ -v

tournament:
	python -c "\
from backend.tournament_runner import run_tournament; \
from pathlib import Path; \
base = Path('eval/personalities'); \
results = run_tournament({ \
    'Tal': str(base / 'tal.py'), \
    'Karpov': str(base / 'karpov.py'), \
    'Petrosian': str(base / 'petrosian.py'), \
    'Classic': 'eval/classic.py', \
}, games_per_pair=10); \
print(results['standings'])"

bench:
	python -c "\
import chess, subprocess; \
from pathlib import Path; \
binary = Path('core/target/release/chess_forge'); \
print('Testing engine on start position...'); \
proc = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True); \
out, _ = proc.communicate('uci\nisready\nposition startpos\ngo movetime 1000\nquit\n', timeout=10); \
print(out)"

dev:
	uvicorn backend.main:app --reload --port 8000 &
	cd frontend && npm run dev
