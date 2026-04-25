/// Negamax search with alpha-beta pruning, iterative deepening, quiescence, and TT.
use std::io::Write;
use std::time::Instant;

use shakmaty::{CastlingMode, Chess, Move, Position};

use crate::tt::{NodeType, TranspositionTable};

pub const INFINITY: i32 = 1_000_000;
pub const MATE_SCORE: i32 = 900_000;

pub struct SearchResult {
    pub best_move: Option<Move>,
    pub score: i32,
    pub depth: u8,
}

/// Iterative deepening driver. Searches to increasing depths until deadline or max_depth.
/// Emits UCI `info` lines to `out` after each completed depth.
pub fn iterative_deepening(
    pos: &Chess,
    max_depth: u8,
    deadline: Option<Instant>,
    eval_fn: &mut dyn FnMut(&Chess) -> i32,
    tt: &mut TranspositionTable,
    out: &mut impl Write,
) -> SearchResult {
    let mut result = SearchResult { best_move: None, score: 0, depth: 0 };

    for depth in 1..=max_depth {
        if deadline.map_or(false, |d| Instant::now() >= d) {
            break;
        }

        let (mv, score) = negamax(pos, depth, -INFINITY, INFINITY, eval_fn, tt);

        result.best_move = mv.clone().or(result.best_move.clone());
        result.score = score;
        result.depth = depth;

        let pv_str = mv.as_ref().map_or("(none)".to_string(), |m| {
            format!("{}", m.to_uci(CastlingMode::Standard))
        });

        let _ = writeln!(
            out,
            "info depth {} score cp {} pv {}",
            depth, score, pv_str
        );
        let _ = out.flush();

        // Don't start a deeper iteration if we're already over time
        if deadline.map_or(false, |d| Instant::now() >= d) {
            break;
        }
    }

    result
}

/// Negamax with alpha-beta pruning and transposition table.
fn negamax(
    pos: &Chess,
    depth: u8,
    mut alpha: i32,
    mut beta: i32,
    eval_fn: &mut dyn FnMut(&Chess) -> i32,
    tt: &mut TranspositionTable,
) -> (Option<Move>, i32) {
    let original_alpha = alpha;

    // Probe transposition table
    if let Some(entry) = tt.probe(pos) {
        if entry.depth >= depth {
            match entry.node_type {
                NodeType::Exact => return (None, entry.score),
                NodeType::LowerBound => alpha = alpha.max(entry.score),
                NodeType::UpperBound => beta = beta.min(entry.score),
            }
            if alpha >= beta {
                return (None, entry.score);
            }
        }
    }

    if depth == 0 {
        let score = quiescence(pos, alpha, beta, eval_fn);
        return (None, score);
    }

    let moves = crate::move_order::ordered_moves(pos);

    if moves.is_empty() {
        if pos.is_check() {
            return (None, -MATE_SCORE - depth as i32);
        }
        return (None, 0); // stalemate
    }

    let mut best_move: Option<Move> = None;
    let mut best_score = -INFINITY;

    for mv in moves {
        let mut child = pos.clone();
        child.play_unchecked(&mv);
        let (_, score) = negamax(&child, depth - 1, -beta, -alpha, eval_fn, tt);
        let score = -score;

        if score > best_score {
            best_score = score;
            best_move = Some(mv);
        }
        if score > alpha {
            alpha = score;
        }
        if alpha >= beta {
            break; // beta cutoff
        }
    }

    // Store in transposition table
    let node_type = if best_score <= original_alpha {
        NodeType::UpperBound
    } else if best_score >= beta {
        NodeType::LowerBound
    } else {
        NodeType::Exact
    };
    tt.store(pos, depth, best_score, node_type);

    (best_move, best_score)
}

/// Quiescence search: only explore captures to resolve tactical noise at leaf nodes.
fn quiescence(
    pos: &Chess,
    mut alpha: i32,
    beta: i32,
    eval_fn: &mut dyn FnMut(&Chess) -> i32,
) -> i32 {
    let stand_pat = eval_fn(pos);
    if stand_pat >= beta {
        return beta;
    }
    if stand_pat > alpha {
        alpha = stand_pat;
    }

    for mv in crate::move_order::capture_moves(pos) {
        let mut child = pos.clone();
        child.play_unchecked(&mv);
        let score = -quiescence(&child, -beta, -alpha, eval_fn);

        if score >= beta {
            return beta;
        }
        if score > alpha {
            alpha = score;
        }
    }

    alpha
}
