"""Two-step Claude pipeline: interpret philosophy → generate evaluate() function."""
import ast
import math
import uuid
import os
import chess
import anthropic

_client = anthropic.Anthropic()

BANNED_NAMES = {"os", "subprocess", "open", "eval", "exec", "random", "time", "__import__"}

INTERPRET_PROMPT = """\
The user wants a chess engine with this philosophy: "{description}"

Restate this as a concrete chess POSITION evaluation strategy in one sentence —
something expressible as: "score this board state highly when [X]."

Use only chess concepts: piece activity, king safety, pawn structure, material
balance, mobility, open files, outposts, etc.

If the input describes a move rule (e.g. "only move pawns"): redirect to the
closest positional philosophy and prefix with:
"Note: your input was a move rule — here's the closest positional equivalent:"

Return ONLY the one-sentence restatement."""

CODEGEN_PROMPT = """\
You are a chess engine programmer. Write a Python function:

    def evaluate(board: chess.Board) -> int

returning a centipawn score from White's perspective (positive = White better).

Philosophy: {interpreted}

Hard rules:
- Import only: chess, math
- No random, time, network, file I/O, or side effects
- Must not raise exceptions on any legal board state
- Deterministic — same board always returns same score
- Return an integer
- Return ONLY the function, no explanation

Material: pawn=100, knight=320, bishop=330, rook=500, queen=900"""


def interpret(description: str) -> str:
    """Step 1: map user description to a chess-expressible concept."""
    msg = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": INTERPRET_PROMPT.format(description=description)}],
    )
    return msg.content[0].text.strip()


def generate(interpreted: str) -> str:
    """Step 2: generate a Python evaluate() function from the interpreted description."""
    msg = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": CODEGEN_PROMPT.format(interpreted=interpreted)}],
    )
    return msg.content[0].text.strip()


def validate(code: str) -> tuple[bool, str]:
    """Run all 5 validation gates. Returns (passed, error_message)."""
    # Gate 1: Syntax
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    # Gate 2: Safety — AST node visitor
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            return False, f"Safety: banned name '{node.id}'"
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ("chess", "math"):
                    return False, f"Safety: banned import '{alias.name}'"
        if isinstance(node, ast.ImportFrom):
            if node.module not in ("chess", "math"):
                return False, f"Safety: banned import from '{node.module}'"

    # Execute the function definition
    namespace: dict = {"chess": chess, "math": math}
    try:
        exec(code, namespace)
    except Exception as e:
        return False, f"Execution error: {e}"

    fn = namespace.get("evaluate")
    if fn is None:
        return False, "No 'evaluate' function defined"

    # Gate 3: Sanity — canonical positions
    sanity_cases = [
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", -50, 50),    # start ≈ 0
        ("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 200, None),  # black missing queen → white winning
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1", None, -200), # white missing queen → black winning
    ]
    scores = []
    for fen, lo, hi in sanity_cases:
        try:
            s = int(fn(chess.Board(fen)))
        except Exception as e:
            return False, f"Sanity error on '{fen}': {e}"
        if lo is not None and s < lo:
            return False, f"Sanity: expected >{lo}cp, got {s} on '{fen}'"
        if hi is not None and s > hi:
            return False, f"Sanity: expected <{hi}cp, got {s} on '{fen}'"
        scores.append(s)

    # Gate 4: Determinism — reuse the same three canonical FENs
    for fen, _, _ in sanity_cases:
        b = chess.Board(fen)
        if fn(b) != fn(b):
            return False, "Determinism: same position returned different scores"

    # Gate 5: Variance across 10 diverse positions
    variance_fens = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "r1bqk2r/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 6",
        "rnbq1rk1/ppp1bppp/4pn2/3p4/2PP4/2N1PN2/PP3PPP/R1BQKB1R w KQ - 0 7",
        "r2q1rk1/ppp2ppp/2np1n2/2b1p1B1/2B1P3/2NP1N2/PPP2PPP/R2QK2R w KQ - 0 8",
        "8/5pkp/6p1/8/8/6P1/5PKP/8 w - - 0 1",
        "4k3/8/8/8/8/8/8/4K2R w K - 0 1",
        "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P3/P1NP1N2/1PP2PPP/R2QR1K1 w - - 0 11",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    ]
    var_scores = []
    for fen in variance_fens:
        try:
            var_scores.append(int(fn(chess.Board(fen))))
        except Exception as e:
            return False, f"Variance eval error: {e}"

    mean = sum(var_scores) / len(var_scores)
    variance = sum((s - mean) ** 2 for s in var_scores) / len(var_scores)
    std_dev = math.sqrt(variance)
    if std_dev < 50:
        return False, f"Variance: std dev {std_dev:.1f}cp is too low — eval is not position-sensitive"

    return True, ""


def save_eval(code: str, slug: str) -> str:
    """Save a validated eval to eval/generated/ and return the file path."""
    filename = f"{uuid.uuid4().hex[:8]}_{slug[:32].replace(' ', '_')}.py"
    path = os.path.join(os.path.dirname(__file__), "generated", filename)
    with open(path, "w") as f:
        f.write("import chess\nimport math\n\n")
        f.write(code)
        f.write("\n")
    return path
