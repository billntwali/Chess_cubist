/// UCI protocol loop with position parsing, search, eval-server bridge, and time management.
use std::io::{self, BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::time::{Duration, Instant};

use shakmaty::fen::Fen;
use shakmaty::uci::Uci;
use shakmaty::{CastlingMode, Chess, Color, EnPassantMode, Position, Role};

use crate::tt::TranspositionTable;

// ---------------------------------------------------------------------------
// Eval server subprocess
// ---------------------------------------------------------------------------

pub struct EvalServer {
    process: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

impl EvalServer {
    pub fn spawn(cmd: &str) -> Self {
        let mut parts = cmd.split_whitespace();
        let program = parts.next().expect("--eval-server cmd is empty");
        let args: Vec<&str> = parts.collect();

        let mut child = Command::new(program)
            .args(&args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .expect("failed to spawn eval server");

        let stdin = child.stdin.take().unwrap();
        let stdout = BufReader::new(child.stdout.take().unwrap());
        EvalServer { process: child, stdin, stdout }
    }

    /// Send a FEN string, return centipawn score. Returns 0 on error.
    pub fn eval(&mut self, fen: &str) -> i32 {
        if writeln!(self.stdin, "{}", fen).is_err() {
            return 0;
        }
        if self.stdin.flush().is_err() {
            return 0;
        }
        let mut line = String::new();
        if self.stdout.read_line(&mut line).is_err() {
            return 0;
        }
        let line = line.trim();
        if line.starts_with("ERR") {
            eprintln!("[eval-server] {}", line);
            return 0;
        }
        line.parse::<i32>().unwrap_or(0)
    }
}

impl Drop for EvalServer {
    fn drop(&mut self) {
        let _ = writeln!(self.stdin, "quit");
        let _ = self.process.wait();
    }
}

// ---------------------------------------------------------------------------
// Built-in material fallback evaluation
// ---------------------------------------------------------------------------

fn material_eval(pos: &Chess) -> i32 {
    const VALUES: [i32; 6] = [100, 320, 330, 500, 900, 0]; // P N B R Q K
    let board = pos.board();
    let mut score = 0i32;
    for (i, role) in Role::ALL.iter().enumerate() {
        let white_count = (board.by_role(*role) & *board.white()).count() as i32;
        let black_count = (board.by_role(*role) & *board.black()).count() as i32;
        score += VALUES[i] * (white_count - black_count);
    }
    // Negamax convention: return from the side-to-move's perspective
    if pos.turn() == Color::Black { -score } else { score }
}

// ---------------------------------------------------------------------------
// Game state
// ---------------------------------------------------------------------------

struct GameState {
    pos: Chess,
    tt: TranspositionTable,
    eval_server: Option<EvalServer>,
}

impl GameState {
    fn new(eval_server: Option<EvalServer>) -> Self {
        GameState {
            pos: Chess::default(),
            tt: TranspositionTable::new(32), // 32 MB
            eval_server,
        }
    }
}

// ---------------------------------------------------------------------------
// Position command parsing
// ---------------------------------------------------------------------------

fn parse_position(line: &str, state: &mut GameState) {
    // "position startpos [moves m1 m2 ...]"
    // "position fen <fen> [moves m1 m2 ...]"
    let rest = line.strip_prefix("position").unwrap_or("").trim();

    let (mut pos, moves_str) = if let Some(r) = rest.strip_prefix("startpos") {
        (Chess::default(), r.trim())
    } else if let Some(r) = rest.strip_prefix("fen") {
        let r = r.trim();
        // FEN ends at " moves " or end of string
        let (fen_str, moves_part) = if let Some(idx) = r.find(" moves ") {
            (&r[..idx], &r[idx..])
        } else {
            (r, "")
        };
        let parsed: Result<Fen, _> = fen_str.parse();
        match parsed {
            Ok(fen) => match fen.into_position::<Chess>(CastlingMode::Standard) {
                Ok(p) => (p, moves_part.trim()),
                Err(_) => return,
            },
            Err(_) => return,
        }
    } else {
        return;
    };

    // Apply move list
    if let Some(moves_part) = moves_str.strip_prefix("moves") {
        for token in moves_part.split_whitespace() {
            match token.parse::<Uci>() {
                Ok(uci_mv) => match uci_mv.to_move(&pos) {
                    Ok(mv) => pos.play_unchecked(&mv),
                    Err(_) => break,
                },
                Err(_) => break,
            }
        }
    }

    state.pos = pos;
}

// ---------------------------------------------------------------------------
// Go command — time parsing + search
// ---------------------------------------------------------------------------

fn parse_go(line: &str, state: &mut GameState, out: &mut impl Write) {
    let mut movetime_ms: Option<u64> = None;
    let mut wtime_ms: Option<u64> = None;
    let mut btime_ms: Option<u64> = None;
    let mut max_depth: u8 = 8;

    let tokens: Vec<&str> = line.split_whitespace().collect();
    let mut i = 1; // skip "go"
    while i < tokens.len() {
        match tokens[i] {
            "movetime" => {
                if i + 1 < tokens.len() {
                    movetime_ms = tokens[i + 1].parse().ok();
                    i += 2;
                } else { i += 1; }
            }
            "depth" => {
                if i + 1 < tokens.len() {
                    max_depth = tokens[i + 1].parse().unwrap_or(8).min(20);
                    i += 2;
                } else { i += 1; }
            }
            "wtime" => {
                if i + 1 < tokens.len() {
                    wtime_ms = tokens[i + 1].parse().ok();
                    i += 2;
                } else { i += 1; }
            }
            "btime" => {
                if i + 1 < tokens.len() {
                    btime_ms = tokens[i + 1].parse().ok();
                    i += 2;
                } else { i += 1; }
            }
            _ => { i += 1; }
        }
    }

    // Determine deadline
    let deadline: Option<Instant> = if let Some(ms) = movetime_ms {
        Some(Instant::now() + Duration::from_millis(ms))
    } else if let Some(ms) = match state.pos.turn() {
        Color::White => wtime_ms,
        Color::Black => btime_ms,
    } {
        // Crude time management: use 1/30 of remaining time
        Some(Instant::now() + Duration::from_millis((ms / 30).max(100)))
    } else {
        // No time info: default 3 seconds
        Some(Instant::now() + Duration::from_millis(3000))
    };

    let pos_snapshot = state.pos.clone();

    // Build eval closure that borrows state.eval_server
    // We need to work around the borrow checker: extract eval_server temporarily
    let result = {
        let eval_server = &mut state.eval_server;
        let tt = &mut state.tt;
        let mut eval_fn = |pos: &Chess| -> i32 {
            match eval_server {
                Some(srv) => {
                    let fen = Fen::from_position(pos.clone(), EnPassantMode::Legal).to_string();
                    srv.eval(&fen)
                }
                None => material_eval(pos),
            }
        };
        crate::search::iterative_deepening(&pos_snapshot, max_depth, deadline, &mut eval_fn, tt, out)
    };

    let best_uci = match result.best_move {
        Some(mv) => format!("{}", mv.to_uci(CastlingMode::Standard)),
        None => {
            // No move found (shouldn't happen in legal positions) — pick first legal move
            let moves = pos_snapshot.legal_moves();
            moves.first()
                .map(|m| format!("{}", m.to_uci(CastlingMode::Standard)))
                .unwrap_or_else(|| "0000".to_string())
        }
    };

    let _ = writeln!(out, "bestmove {}", best_uci);
    let _ = out.flush();
}

// ---------------------------------------------------------------------------
// Main UCI loop
// ---------------------------------------------------------------------------

pub fn run() {
    let args: Vec<String> = std::env::args().collect();
    let eval_server_cmd = args.windows(2)
        .find(|w| w[0] == "--eval-server")
        .map(|w| w[1].clone());

    let eval_server = eval_server_cmd.map(|cmd| EvalServer::spawn(&cmd));
    let mut state = GameState::new(eval_server);

    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        let trimmed = line.trim();

        if trimmed == "uci" {
            let _ = writeln!(out, "id name ChessForge");
            let _ = writeln!(out, "id author Chess Cubist");
            let _ = writeln!(out, "uciok");
            let _ = out.flush();
        } else if trimmed == "isready" {
            let _ = writeln!(out, "readyok");
            let _ = out.flush();
        } else if trimmed == "ucinewgame" {
            state.tt.clear();
            state.pos = Chess::default();
        } else if trimmed.starts_with("position") {
            parse_position(trimmed, &mut state);
        } else if trimmed.starts_with("go") {
            parse_go(trimmed, &mut state, &mut out);
        } else if trimmed == "quit" {
            break;
        }
        // Ignore unknown commands (UCI spec allows this)
    }
}
