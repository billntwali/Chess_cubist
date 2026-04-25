/// Move ordering heuristics: MVV-LVA captures first, then quiet moves.
use shakmaty::{Chess, Move, MoveList, Position, Role};

/// Returns all legal moves sorted: captures (MVV-LVA) first, then quiet moves.
pub fn ordered_moves(pos: &Chess) -> MoveList {
    let mut moves = pos.legal_moves();
    moves.sort_by_key(|mv| -mvv_lva_score(pos, mv));
    moves
}

/// Returns only capture moves, sorted by MVV-LVA.
pub fn capture_moves(pos: &Chess) -> MoveList {
    let mut moves = pos.legal_moves();
    moves.retain(|mv| is_capture(pos, mv));
    moves.sort_by_key(|mv| -mvv_lva_score(pos, mv));
    moves
}

/// MVV-LVA: Most Valuable Victim - Least Valuable Attacker.
/// Higher score = explore first.
fn mvv_lva_score(pos: &Chess, mv: &Move) -> i32 {
    match mv {
        Move::Normal { from, to, .. } => {
            let victim = pos.board().piece_at(*to).map_or(0, |p| role_value(p.role));
            let attacker = pos.board().piece_at(*from).map_or(0, |p| role_value(p.role));
            victim * 10 - attacker
        }
        Move::EnPassant { .. } => 10 * 100 - 100, // pawn captures pawn
        _ => 0,
    }
}

fn is_capture(pos: &Chess, mv: &Move) -> bool {
    match mv {
        Move::Normal { to, .. } => pos.board().piece_at(*to).is_some(),
        Move::EnPassant { .. } => true,
        _ => false,
    }
}

fn role_value(role: Role) -> i32 {
    match role {
        Role::Pawn => 100,
        Role::Knight => 320,
        Role::Bishop => 330,
        Role::Rook => 500,
        Role::Queen => 900,
        Role::King => 20000,
    }
}
