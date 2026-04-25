/// Negamax search with alpha-beta pruning, iterative deepening, and quiescence.
use shakmaty::{Chess, Position, Move};

pub const INFINITY: i32 = 1_000_000;
pub const MATE_SCORE: i32 = 900_000;

/// Result of a search: best move and its score.
pub struct SearchResult {
    pub best_move: Option<Move>,
    pub score: i32,
    pub depth: u8,
}

/// Iterative deepening driver. Searches to increasing depths until time runs out.
pub fn iterative_deepening(
    pos: &Chess,
    max_depth: u8,
    eval_fn: &mut dyn FnMut(&Chess) -> i32,
) -> SearchResult {
    let mut result = SearchResult { best_move: None, score: 0, depth: 0 };

    for depth in 1..=max_depth {
        let (mv, score) = negamax(pos, depth, -INFINITY, INFINITY, eval_fn);
        result.best_move = mv;
        result.score = score;
        result.depth = depth;
    }

    result
}

/// Negamax with alpha-beta pruning.
fn negamax(
    pos: &Chess,
    depth: u8,
    mut alpha: i32,
    beta: i32,
    eval_fn: &mut dyn FnMut(&Chess) -> i32,
) -> (Option<Move>, i32) {
    if depth == 0 {
        return (None, quiescence(pos, alpha, beta, eval_fn));
    }

    let moves = crate::move_order::ordered_moves(pos);

    if moves.is_empty() {
        if pos.is_check() {
            return (None, -MATE_SCORE - depth as i32); // checkmate
        }
        return (None, 0); // stalemate
    }

    let mut best_move = None;

    for mv in moves {
        let mut child = pos.clone();
        child.play_unchecked(&mv);
        let (_, score) = negamax(&child, depth - 1, -beta, -alpha, eval_fn);
        let score = -score;

        if score > alpha {
            alpha = score;
            best_move = Some(mv);
        }
        if alpha >= beta {
            break; // beta cutoff
        }
    }

    (best_move, alpha)
}

/// Quiescence search: only explore captures to resolve tactical noise.
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

    let captures = crate::move_order::capture_moves(pos);

    for mv in captures {
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
