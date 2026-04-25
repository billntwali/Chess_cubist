"""Two-step LLM pipeline: interpret philosophy → generate evaluate() function."""
import ast
import math
import uuid
import os
import chess
from openai import OpenAI

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client

BANNED_NAMES = {"os", "subprocess", "open", "eval", "exec", "random", "time", "__import__"}
DISALLOWED_SHADOW_NAMES = {
    "int",
    "float",
    "str",
    "bool",
    "list",
    "dict",
    "set",
    "tuple",
    "sum",
    "max",
    "min",
    "abs",
    "len",
    "round",
    "sorted",
}

INTERPRET_PROMPT = """\
The user wants a chess engine with this personality: "{description}"

Describe how this player approaches chess in 1-2 vivid sentences. Write it as a character portrait —
what does this player obsess over, fear, ignore, or crave on the board?

Ground it in real chess concepts (piece activity, king safety, pawn structure, open files, outposts, material),
but let the personality come through. Be specific and colorful, not clinical.

Return ONLY the 1-2 sentence description."""

CODEGEN_PROMPT = """\
You are a chess engine programmer. Write a Python function:

    def evaluate(board: chess.Board) -> int

returning a centipawn score from White's perspective (positive = White better).

Philosophy: {interpreted}

Hard rules:
- Python 3.9 compatible syntax only (no match statements, no X | Y union types)
- Import only: chess, math
- Do NOT call board.push() or board.pop() — treat the board as read-only
- Do NOT use chess.Move.null() or any null move tricks
- No random, time, network, file I/O, or side effects
- Do not shadow Python built-ins (e.g., never assign to int, list, dict, sum, max)
- Must not raise exceptions on any legal board state
- Deterministic — same board always returns same score
- Return an integer
- Return ONLY the function, no explanation
- Every if/for/while/def block must have a complete indented body
- Do not leave placeholders, ellipses, unfinished branches, or TODO comments
- Keep the function under 180 lines
- Prefer simple loops and helper constants over deeply nested logic

Useful read-only board methods:
  board.pieces(piece_type, color)  -> SquareSet (iterable of square ints)
  board.piece_at(square)           -> Piece or None
  board.king(color)                -> int (a single square number, NOT iterable — never loop over it)
  board.is_check()                 -> bool
  board.turn                       -> chess.WHITE or chess.BLACK
  chess.square_file(sq), chess.square_rank(sq)  -> int 0-7
  len(list(board.legal_moves))     -> mobility count (call once per side via board.turn)

Common mistakes to avoid:
  BAD:  for sq in board.king(chess.WHITE)   # king() returns an int, not iterable
  GOOD: king_sq = board.king(chess.WHITE); if king_sq is not None: ...
  BAD:  score += board.pieces(...)          # SquareSet can't be added to int
  GOOD: score += len(board.pieces(...))

Material: pawn=100, knight=320, bishop=330, rook=500, queen=900, king=0
IMPORTANT: Never use board.piece_map() — it includes kings and will cause KeyError.
Instead use board.pieces(piece_type, color) for each piece type explicitly.
IMPORTANT: Every heuristic should be computed as WHITE minus BLACK (relative advantage),
not as absolute totals. The starting position should score near 0 (roughly within +/-150cp).
Keep typical score magnitudes reasonable (usually within +/-3000cp).

Bonus sizing — this is critical for the personality to actually show up in play:
- Personality bonuses must be LARGE enough to compete with material (50–150cp per feature)
- If the philosophy prizes aggression, king-attack bonuses should reach 100–200cp total
- If the philosophy ignores safety, penalize own king safety by -100 to -200cp
- Weak bonuses (5–20cp) get drowned out by material and the personality disappears
- Do NOT be conservative — the whole point is that this engine plays differently"""

RETRY_PROMPT = """\
The function you wrote has this error: {error}

Rewrite the evaluate() function fixing the error. Key constraints:
- Do NOT call board.push() or board.pop()
- Do NOT use board.piece_map() — it includes kings and causes KeyError: 6
- Do NOT iterate over board.king() — it returns an int, not iterable
- Do NOT add SquareSets to ints — use len(board.pieces(...)) instead
- Ensure all terms are relative (white advantage - black advantage), not absolute totals
- Starting position must evaluate near 0 (within +/-300cp)
- Use board.pieces(piece_type, color) for each piece type explicitly
- Do NOT use nested functions or closures — they can capture mutable state and break determinism
- Use only Python 3.9 syntax
- Return ONLY the function."""


def interpret(description: str) -> str:
    """Step 1: map user description to a chess-expressible concept."""
    try:
        msg = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=256,
            messages=[{"role": "user", "content": INTERPRET_PROMPT.format(description=description)}],
        )
        return msg.choices[0].message.content.strip()
    except Exception:
        return _fallback_interpretation(description)


def _fallback_interpretation(description: str) -> str:
    """Local interpretation used when the API is unavailable."""
    cleaned = " ".join(description.strip().split())
    if not cleaned:
        cleaned = "balanced practical chess"
    lowered = cleaned.lower()
    if "magnus" in lowered or "carlsen" in lowered:
        return (
            "Plays like Magnus Carlsen by rewarding tiny positional advantages, "
            "centralized pieces, durable pawn structures, active kings in simplified "
            "positions, and steady pressure over reckless material grabs."
        )
    if any(word in lowered for word in ("reckless", "attacker", "attack", "sacrifice", "tal")):
        return (
            "Plays as a reckless attacker by rewarding piece activity, open files, "
            "advanced pieces near the enemy king, and initiative even when material "
            "is temporarily sacrificed."
        )
    if "pawn" in lowered:
        return (
            "Plays as a pawn-driven strategist by rewarding advanced connected pawns, "
            "central pawn control, passed-pawn potential, and long-term space."
        )
    if any(word in lowered for word in ("coward", "avoid", "trade", "defensive", "safe")):
        return (
            "Plays defensively by rewarding king safety, compact pawn shields, "
            "piece preservation, and stable structures while avoiding unnecessary trades."
        )
    return (
        f"Plays {cleaned.removeprefix('play like ').strip()} by prioritizing sound material balance, active centralized "
        "pieces, king safety, and steady conversion of small positional advantages."
    )


def _strip_markdown(code: str) -> str:
    """Remove markdown code fences if Claude wrapped the response in them."""
    lines = code.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def generate(interpreted: str, max_retries: int = 2) -> str:
    """Step 2: generate a Python evaluate() function.

    Claude output is never trusted blindly. If every retry fails validation,
    return a conservative built-in eval template so the UI never receives
    malformed Python.
    """
    messages = [{"role": "user", "content": CODEGEN_PROMPT.format(interpreted=interpreted)}]
    last_error = "Claude did not return a valid evaluate() function"

    for attempt in range(max_retries + 1):
        try:
            msg = _get_client().chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=4096,
                messages=messages,
            )
        except Exception as exc:
            return _fallback_eval_code(interpreted, f"API error: {exc}")
        raw = msg.choices[0].message.content
        code = _strip_markdown(raw)

        error = _quick_check(code)
        if error is None:
            return code
        last_error = error
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": RETRY_PROMPT.format(error=error)})

    return _fallback_eval_code(interpreted, last_error)


def _fallback_eval_code(interpreted: str, error: str) -> str:
    """Return a deterministic, validated eval if Claude repeatedly fails."""
    lowered = interpreted.lower()
    aggressive = any(word in lowered for word in ("attack", "attacker", "reckless", "sacrifice", "initiative", "tal"))
    positional = any(word in lowered for word in ("magnus", "carlsen", "positional", "pressure", "tiny", "small", "centralized"))
    pawn_focused = "pawn" in lowered
    defensive = any(word in lowered for word in ("coward", "defensive", "safe", "king safety", "avoid", "preservation"))
    return f'''\
def evaluate(board: chess.Board) -> int:
    """Fallback eval used after invalid Claude output.

    Philosophy requested: {interpreted[:160]!r}
    Generator failure: {error[:160]!r}
    """
    values = {{
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
    }}
    aggressive = {aggressive!r}
    positional = {positional!r}
    pawn_focused = {pawn_focused!r}
    defensive = {defensive!r}
    score = 0

    center_squares = [chess.D4, chess.E4, chess.D5, chess.E5]
    extended_center = [
        chess.C3, chess.D3, chess.E3, chess.F3,
        chess.C4, chess.F4, chess.C5, chess.F5,
        chess.C6, chess.D6, chess.E6, chess.F6,
    ]

    for piece_type, value in values.items():
        white_pieces = board.pieces(piece_type, chess.WHITE)
        black_pieces = board.pieces(piece_type, chess.BLACK)
        score += value * len(white_pieces)
        score -= value * len(black_pieces)

        for square in white_pieces:
            file_index = chess.square_file(square)
            rank_index = chess.square_rank(square)
            distance_from_center = abs(file_index - 3.5) + abs(rank_index - 3.5)
            score += int(28 - distance_from_center * 6)
            if square in center_squares:
                score += 45
            elif square in extended_center:
                score += 20
            if aggressive and piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                score += rank_index * 10
            if positional and piece_type in (chess.KNIGHT, chess.BISHOP):
                score += int(24 - distance_from_center * 5)
            if pawn_focused and piece_type == chess.PAWN:
                score += rank_index * 14

        for square in black_pieces:
            file_index = chess.square_file(square)
            rank_index = chess.square_rank(square)
            distance_from_center = abs(file_index - 3.5) + abs(rank_index - 3.5)
            score -= int(28 - distance_from_center * 6)
            if square in center_squares:
                score -= 45
            elif square in extended_center:
                score -= 20
            if aggressive and piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                score -= (7 - rank_index) * 10
            if positional and piece_type in (chess.KNIGHT, chess.BISHOP):
                score -= int(24 - distance_from_center * 5)
            if pawn_focused and piece_type == chess.PAWN:
                score -= (7 - rank_index) * 14

    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)
    if white_king is not None:
        white_file = chess.square_file(white_king)
        white_rank = chess.square_rank(white_king)
        for pawn_square in board.pieces(chess.PAWN, chess.WHITE):
            if abs(chess.square_file(pawn_square) - white_file) <= 1:
                if chess.square_rank(pawn_square) >= white_rank:
                    score += 18
                    if defensive:
                        score += 18
    if black_king is not None:
        black_file = chess.square_file(black_king)
        black_rank = chess.square_rank(black_king)
        for pawn_square in board.pieces(chess.PAWN, chess.BLACK):
            if abs(chess.square_file(pawn_square) - black_file) <= 1:
                if chess.square_rank(pawn_square) <= black_rank:
                    score -= 18
                    if defensive:
                        score -= 18

    white_bishops = len(board.pieces(chess.BISHOP, chess.WHITE))
    black_bishops = len(board.pieces(chess.BISHOP, chess.BLACK))
    if white_bishops >= 2:
        score += 55
        if positional:
            score += 35
    if black_bishops >= 2:
        score -= 55
        if positional:
            score -= 35

    white_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
    black_queens = len(board.pieces(chess.QUEEN, chess.BLACK))
    if defensive:
        score += 25 * (white_queens - black_queens)
    if aggressive:
        score += 30 * (len(board.pieces(chess.ROOK, chess.WHITE)) - len(board.pieces(chess.ROOK, chess.BLACK)))

    if board.is_check():
        if board.turn == chess.WHITE:
            score -= 35
            if aggressive:
                score -= 45
        else:
            score += 35
            if aggressive:
                score += 45

    return int(score)
'''


def _quick_check(code: str):
    """Return an error string if the code has a syntax error or crashes on the start position,
    otherwise return None."""
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    namespace: dict = {"chess": chess, "math": math}
    try:
        exec(code, namespace)
    except Exception as e:
        return f"Execution error: {e}"

    fn = namespace.get("evaluate")
    if fn is None:
        return "No 'evaluate' function defined"

    try:
        result = fn(chess.Board())
        int(result)
    except Exception as e:
        return f"Crashed on starting position: {e}"

    # Early sanity + determinism checks
    sanity_cases = [
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", -300, 300),
        ("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 200, None),
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1", None, -200),
    ]
    for fen, lo, hi in sanity_cases:
        b = chess.Board(fen)
        try:
            s1 = int(fn(b))
            s2 = int(fn(b))
        except Exception as e:
            return f"Sanity crash on '{fen}': {e}"
        if s1 != s2:
            return f"Determinism: same position returned {s1} then {s2} — do not use mutable state or closures"
        if lo is not None and s1 < lo:
            return f"Sanity: expected >{lo}cp, got {s1} on '{fen}'"
        if hi is not None and s1 > hi:
            return f"Sanity: expected <{hi}cp, got {s1} on '{fen}'"

    return None


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
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in DISALLOWED_SHADOW_NAMES:
            return False, f"Safety: cannot assign to built-in name '{node.id}'"
        if isinstance(node, ast.arg) and node.arg in DISALLOWED_SHADOW_NAMES:
            return False, f"Safety: function arg shadows built-in name '{node.arg}'"
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
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", -300, 300),   # start ≈ 0
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
